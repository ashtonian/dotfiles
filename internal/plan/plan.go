// Package plan turns the enabled features into what a machine should have:
// links, managed copies, generated outputs, local stubs, LaunchAgents and app
// settings.
package plan

import (
	"bytes"
	"errors"
	"fmt"
	"io/fs"
	"maps"
	"os"
	"path/filepath"
	"slices"
	"sort"
	"strings"

	"github.com/ashtonian/dotfiles/internal/launchd"
	"github.com/ashtonian/dotfiles/internal/manifest"
	"github.com/ashtonian/dotfiles/internal/prefs"
	"github.com/ashtonian/dotfiles/internal/resolve"
)

// ErrPlan wraps failures caused by the features themselves, such as a missing
// source file or two features claiming one target.
var ErrPlan = errors.New("cannot plan features")

// Env is where a plan lands.
type Env struct {
	Home         string // the user's home directory
	GeneratedDir string // where generated outputs go, such as ~/.config/dotfiles/generated
	GOOS         string
}

// Link is a file in $HOME that should be a symlink to a tracked file.
type Link struct {
	Target, Source, Feature string
	// UnlessExists are absolute paths; while any exists, something else owns
	// Target and apply leaves it alone.
	UnlessExists []string
}

// Copy is a file in $HOME that should be a managed copy of a tracked file.
type Copy struct {
	Target, Source, Feature string
}

// File is a generated output.
type File struct {
	Path    string
	Content []byte
}

// Stub is a local entry point that must exist and contain Line; see
// manifest.Stub for Before and KeepExisting.
type Stub struct {
	Path, Line, Feature string
	Before              []string
	KeepExisting        bool
}

// LaunchAgent is a launchd job to install into ~/Library/LaunchAgents and load.
type LaunchAgent struct {
	Label   string
	Target  string // ~/Library/LaunchAgents/<Label>.plist
	Source  string // the template in the feature
	Content []byte // the template with $HOME replaced
	// Definition fingerprints the job Content defines (launchd.Definition):
	// a template change that leaves it alone needs no reload.
	Definition string
	Feature    string
	// KeepAlive marks a service launchd keeps running, which a reload
	// restarts, rather than a job that runs on a schedule and exits.
	KeepAlive bool
	// WhenExists are absolute paths that must all exist before the agent is
	// installed.
	WhenExists []string
	// LogDirs are the directories, under $HOME, of its StandardOutPath and
	// StandardErrorPath. launchd does not create them.
	LogDirs []string
}

// Pref is one app setting a feature owns; see package prefs.
type Pref struct {
	Store, Key string
	// Value is what the setting should be here: the feature's value, unless
	// a profile's or the machine manifest's [prefs] table overrides it. As
	// TOML decoded it.
	Value   any
	Feature string
	// Shared is the feature's own value, which an override replaces.
	Shared any
	// Origin is the layer Value comes from: empty for the feature's prefs
	// file, else "profile:<name>" or "machine".
	Origin string
	// File sets Value, and is what adopt rewrites: the feature's prefs file,
	// or the manifest whose [prefs] table overrides it.
	File string
}

// ID names the setting in reports, the state file, `dotfiles adopt` and
// [prefs] overrides, as <store>:<key>.
func (p Pref) ID() string { return p.Store + ":" + p.Key }

// SetBy names where Value comes from: the feature that owns the setting, or
// the layer that overrides it.
func (p Pref) SetBy() string {
	if p.Origin == "" {
		return p.Feature
	}
	return p.Origin
}

// Plan is the desired state for one machine.
type Plan struct {
	Links        []Link
	Copies       []Copy
	Generated    []File
	Stubs        []Stub
	LaunchAgents []LaunchAgent
	// Prefs lists the app settings to own, in feature order.
	Prefs []Pref
	// IgnoredPrefs lists the machine manifest's [prefs] overrides of settings
	// whose features are off here, which change nothing.
	IgnoredPrefs []IgnoredPref
	// OffAgents maps the labels of the LaunchAgents that features not
	// enabled here declare to their install paths. apply removes such a plist
	// it finds without a record of installing it: the retired installer's.
	OffAgents map[string]string
	// Retire lists old install paths to remove when they are still links into
	// the repository.
	Retire []string
}

// Build plans the enabled features, in dependency order. values holds the
// resolved settings, by setting name; overrides are the [prefs] tables that
// replace the values the features' prefs files give, lowest precedence first.
func Build(features map[string]*manifest.Feature, order []string, values map[string]any,
	overrides []resolve.PrefLayer, env Env) (*Plan, error) {
	p := &Plan{}
	owner := map[string]string{} // target -> feature, to catch two features claiming one file
	claim := func(target, feature string) error {
		if prev, ok := owner[target]; ok {
			return fmt.Errorf("%w: %s and %s both install %s", ErrPlan, prev, feature, target)
		}
		owner[target] = feature
		return nil
	}

	for _, id := range order {
		f := features[id]
		for _, entry := range f.Provides.Link {
			files, err := expand(f, entry)
			if err != nil {
				return nil, err
			}
			var unless []string
			if held, ok := f.Provides.LinkUnlessExists[entry]; ok {
				if underLibrary(entry) {
					return nil, fmt.Errorf("%w: %s: link_unless_exists %s: files under Library/ are installed as copies on macOS, which it cannot hold", ErrPlan, id, entry)
				}
				for _, path := range held {
					unless = append(unless, homePath(path, env.Home))
				}
			}
			for _, rel := range files {
				target := filepath.Join(env.Home, rel)
				if err := claim(target, id); err != nil {
					return nil, err
				}
				source := filepath.Join(f.Dir, "home", rel)
				// macOS apps and `defaults` refuse to read or save a symlinked
				// preference file, so anything under ~/Library is a copy.
				if env.GOOS == "darwin" && underLibrary(rel) {
					p.Copies = append(p.Copies, Copy{Target: target, Source: source, Feature: id})
				} else {
					p.Links = append(p.Links, Link{Target: target, Source: source, Feature: id, UnlessExists: unless})
				}
			}
		}
		for _, entry := range f.Provides.Copy {
			files, err := expand(f, entry)
			if err != nil {
				return nil, err
			}
			for _, rel := range files {
				target := filepath.Join(env.Home, rel)
				if err := claim(target, id); err != nil {
					return nil, err
				}
				p.Copies = append(p.Copies, Copy{Target: target, Source: filepath.Join(f.Dir, "home", rel), Feature: id})
			}
		}
		for _, script := range f.Provides.Bin {
			source := filepath.Join(f.Dir, filepath.FromSlash(script))
			if info, err := os.Stat(source); err != nil || !info.Mode().IsRegular() {
				return nil, fmt.Errorf("%w: %s: bin %s is not a file", ErrPlan, id, script)
			}
			target := filepath.Join(env.Home, ".local", "bin", filepath.Base(source))
			if err := claim(target, id); err != nil {
				return nil, err
			}
			p.Links = append(p.Links, Link{Target: target, Source: source, Feature: id})
		}
		for _, s := range f.Provides.Stub {
			target := filepath.Join(env.Home, filepath.FromSlash(s.Path))
			if err := claim(target, id); err != nil {
				return nil, err
			}
			p.Stubs = append(p.Stubs, Stub{Path: target, Line: s.Line, Feature: id, Before: s.Before, KeepExisting: s.KeepExisting})
		}
		for _, a := range f.Provides.LaunchAgent {
			if env.GOOS != "darwin" {
				break
			}
			agent, err := launchAgent(f, a, env.Home)
			if err != nil {
				return nil, err
			}
			if err := claim(agent.Target, id); err != nil {
				return nil, err
			}
			p.LaunchAgents = append(p.LaunchAgents, agent)
		}
		for _, store := range slices.Sorted(maps.Keys(f.Provides.Prefs)) {
			source := filepath.Join(f.Dir, filepath.FromSlash(f.Provides.Prefs[store]))
			entries, err := prefs.ReadFile(source)
			if err != nil {
				return nil, fmt.Errorf("%w: %s: %w", ErrPlan, id, err)
			}
			for _, e := range entries {
				if err := prefs.CheckSetting(store, e.Key, e.Value); err != nil {
					return nil, fmt.Errorf("%w: %s: %s:%d: %w", ErrPlan, id, source, e.Line, err)
				}
				pref := Pref{Store: store, Key: e.Key, Value: e.Value, Feature: id, Shared: e.Value, File: source}
				if err := claim(pref.ID(), id); err != nil {
					return nil, err
				}
				p.Prefs = append(p.Prefs, pref)
			}
		}
	}

	if err := overridePrefs(p, features, order, overrides); err != nil {
		return nil, err
	}

	// Every feature's retired paths, enabled or not: an old link is a leftover
	// whichever way the feature is set now.
	ids := make([]string, 0, len(features))
	for id := range features {
		ids = append(ids, id)
	}
	sort.Strings(ids)
	for _, id := range ids {
		for _, rel := range features[id].Retire {
			target := filepath.Join(env.Home, filepath.FromSlash(rel))
			if _, installed := owner[target]; !installed {
				p.Retire = append(p.Retire, target)
			}
		}
	}
	if env.GOOS == "darwin" {
		for _, id := range ids {
			if slices.Contains(order, id) {
				continue
			}
			for _, a := range features[id].Provides.LaunchAgent {
				if p.OffAgents == nil {
					p.OffAgents = map[string]string{}
				}
				p.OffAgents[a.Label()] = agentTarget(env.Home, a.Label())
			}
		}
	}

	generated, err := generate(features, order, values, env)
	if err != nil {
		return nil, err
	}
	p.Generated = generated
	return p, nil
}

// overridePrefs applies the [prefs] tables over the values the features'
// prefs files give, in order, so the last layer that names a setting decides
// it. A table names only settings a feature owns. The machine manifest
// describes this machine, so it names one a feature enabled here owns. A
// profile is shared by machines that turn features on and off, so one it
// names may belong to a feature that is off here, and is then left out.
// IgnoredPref is a machine manifest override of an app setting that only a
// feature off on this machine owns.
type IgnoredPref struct {
	ID      string // <store>:<key>
	Feature string // the feature that owns it
	File    string // the machine manifest
}

func overridePrefs(p *Plan, features map[string]*manifest.Feature, order []string, layers []resolve.PrefLayer) error {
	at := make(map[string]int, len(p.Prefs))
	for i, pr := range p.Prefs {
		at[pr.ID()] = i
	}
	var off map[string]string // setting -> owner off here; read the first time it is needed
	for _, layer := range layers {
		where := layer.File
		if where == "" {
			where = layer.Source
		}
		for _, id := range slices.Sorted(maps.Keys(layer.Values)) {
			value := layer.Values[id]
			store, key, err := prefs.ParseID(id)
			if err != nil {
				return fmt.Errorf("%w: %s: [prefs]: %w", ErrPlan, where, err)
			}
			if err := prefs.CheckValue(value); err != nil {
				return fmt.Errorf("%w: %s: [prefs] %q: %w", ErrPlan, where, id, err)
			}
			if err := prefs.CheckSetting(store, key, value); err != nil {
				return fmt.Errorf("%w: %s: [prefs] %q: %w", ErrPlan, where, id, err)
			}
			i, owned := at[id]
			if !owned {
				if off == nil {
					if off, err = offPrefs(features, order); err != nil {
						return err
					}
				}
				feature, ok := off[id]
				if !ok {
					return fmt.Errorf("%w: %s: [prefs] %q: no feature owns this setting", ErrPlan, where, id)
				}
				// Its feature is off here. A profile is shared by machines
				// that turn features on and off, so only the machine's own
				// manifest is told.
				if layer.Source == "machine" {
					p.IgnoredPrefs = append(p.IgnoredPrefs, IgnoredPref{ID: id, Feature: feature, File: layer.File})
				}
				continue
			}
			p.Prefs[i].Value = value
			p.Prefs[i].Origin = layer.Source
			p.Prefs[i].File = layer.File
		}
	}
	return nil
}

// offPrefs maps the settings that features not planned here own to those
// features.
func offPrefs(features map[string]*manifest.Feature, order []string) (map[string]string, error) {
	owned := map[string]string{}
	for _, id := range slices.Sorted(maps.Keys(features)) {
		f := features[id]
		if slices.Contains(order, id) {
			continue
		}
		for store, file := range f.Provides.Prefs {
			entries, err := prefs.ReadFile(filepath.Join(f.Dir, filepath.FromSlash(file)))
			if err != nil {
				return nil, fmt.Errorf("%w: %s: %w", ErrPlan, id, err)
			}
			for _, e := range entries {
				owned[store+":"+e.Key] = id
			}
		}
	}
	return owned, nil
}

// expand lists the files under <feature>/home/<entry>, relative to home/. A
// directory expands to every file inside it, so no directory is ever linked.
func expand(f *manifest.Feature, entry string) ([]string, error) {
	root := filepath.Join(f.Dir, "home")
	start := filepath.Join(root, filepath.FromSlash(entry))
	info, err := os.Lstat(start)
	if err != nil {
		return nil, fmt.Errorf("%w: %s: %s: %w", ErrPlan, f.ID, entry, err)
	}
	if !info.IsDir() {
		rel, err := filepath.Rel(root, start)
		return []string{rel}, err
	}
	var files []string
	err = filepath.WalkDir(start, func(path string, d fs.DirEntry, err error) error {
		if err != nil {
			return err
		}
		if d.IsDir() {
			return nil
		}
		rel, err := filepath.Rel(root, path)
		if err != nil {
			return err
		}
		files = append(files, rel)
		return nil
	})
	if err != nil {
		return nil, fmt.Errorf("%w: %s: %s: %w", ErrPlan, f.ID, entry, err)
	}
	if len(files) == 0 {
		return nil, fmt.Errorf("%w: %s: %s holds no files", ErrPlan, f.ID, entry)
	}
	return files, nil
}

// launchAgent renders a feature's LaunchAgent template for home. The template
// must be a property list whose Label is its file name without .plist, which
// is also the installed file's name, so the two can never disagree.
func launchAgent(f *manifest.Feature, a manifest.LaunchAgent, home string) (LaunchAgent, error) {
	source := filepath.Join(f.Dir, filepath.FromSlash(a.Plist))
	template, err := os.ReadFile(source)
	if err != nil {
		return LaunchAgent{}, fmt.Errorf("%w: %s: launch_agent: %w", ErrPlan, f.ID, err)
	}
	content := bytes.ReplaceAll(template, []byte("$HOME"), []byte(home))
	job, err := launchd.Read(content)
	if err != nil {
		return LaunchAgent{}, fmt.Errorf("%w: %s: %s: %w", ErrPlan, f.ID, a.Plist, err)
	}
	if job.Label != a.Label() {
		return LaunchAgent{}, fmt.Errorf("%w: %s: %s has Label %q; name the file <Label>.plist", ErrPlan, f.ID, a.Plist, job.Label)
	}
	def, err := launchd.Definition(content)
	if err != nil {
		return LaunchAgent{}, fmt.Errorf("%w: %s: %s: %w", ErrPlan, f.ID, a.Plist, err)
	}
	agent := LaunchAgent{Label: job.Label, Target: agentTarget(home, job.Label), Source: source, Content: content,
		Definition: def, Feature: f.ID, KeepAlive: job.KeepAlive}
	for _, path := range a.WhenExists {
		agent.WhenExists = append(agent.WhenExists, homePath(path, home))
	}
	for _, log := range []string{job.StandardOutPath, job.StandardErrorPath} {
		if log == "" {
			continue
		}
		dir := filepath.Dir(log)
		if strings.HasPrefix(dir, home+string(filepath.Separator)) && !slices.Contains(agent.LogDirs, dir) {
			agent.LogDirs = append(agent.LogDirs, dir)
		}
	}
	return agent, nil
}

func agentTarget(home, label string) string {
	return filepath.Join(home, "Library", "LaunchAgents", label+".plist")
}

// homePath turns a manifest path that starts with ~/ into one under home;
// an absolute path stays as it is.
func homePath(path, home string) string {
	if rest, ok := strings.CutPrefix(path, "~/"); ok {
		return filepath.Join(home, filepath.FromSlash(rest))
	}
	return path
}

func underLibrary(rel string) bool {
	first, _, _ := strings.Cut(filepath.ToSlash(rel), "/")
	return first == "Library"
}

// packageLine renders a Brewfile brew or cask entry. Homebrew refuses to load
// a formula or cask from a third-party tap until it is trusted. Naming one in
// full (user/repo/name) in a feature is that decision, so the entry trusts
// that one item, never its whole tap; `brew bundle` records it before it loads
// anything.
func packageLine(kind, name string, opts ...string) string {
	if strings.Count(name, "/") == 2 {
		opts = append(opts, "trusted: true")
	}
	var line strings.Builder
	fmt.Fprintf(&line, "%s %q", kind, name)
	for _, o := range opts {
		line.WriteString(", ")
		line.WriteString(o)
	}
	return line.String()
}

// generate renders the outputs shells and tools read, so no shell startup
// parses a manifest. Every output is written even when empty, so stubs and
// includes can load it unconditionally.
func generate(features map[string]*manifest.Feature, order []string, values map[string]any, env Env) ([]File, error) {
	var brew bytes.Buffer
	brew.WriteString("# Generated by `dotfiles apply` from the enabled features; edits are replaced.\n")
	seen := map[string]bool{}
	entry := func(line, feature string) {
		if seen[line] {
			return
		}
		seen[line] = true
		fmt.Fprintf(&brew, "%s # %s\n", line, feature)
	}
	for _, kind := range []string{"tap", "brew", "cask", "mas", "flatpak", "vscode", "go"} {
		for _, id := range order {
			pr := features[id].Provides
			switch kind {
			case "tap":
				for _, n := range pr.Tap {
					entry(fmt.Sprintf("tap %q", n), id)
				}
			case "brew":
				for _, n := range pr.Brew {
					var opts []string
					if link, ok := pr.BrewLink[n]; ok {
						opts = append(opts, fmt.Sprintf("link: %t", link))
					}
					entry(packageLine("brew", n, opts...), id)
				}
			case "cask":
				if env.GOOS == "darwin" {
					for _, n := range pr.Cask {
						entry(packageLine("cask", n), id)
					}
				}
			case "mas":
				if env.GOOS == "darwin" {
					for _, app := range pr.Mas {
						entry(fmt.Sprintf("mas %q, id: %d", app.Name, app.ID), id)
					}
				}
			case "flatpak":
				if env.GOOS == "linux" {
					for _, n := range pr.Flatpak {
						entry(fmt.Sprintf("flatpak %q", n), id)
					}
				}
			case "vscode":
				for _, n := range pr.Vscode {
					entry(fmt.Sprintf("vscode %q", n), id)
				}
			case "go":
				for _, n := range pr.Go {
					entry(fmt.Sprintf("go %q", n), id)
				}
			}
		}
	}

	files := []File{{Path: filepath.Join(env.GeneratedDir, "Brewfile"), Content: brew.Bytes()}}
	fragments := []struct {
		name, header string
		pick         func(manifest.Provides) string
	}{
		{"env.sh", "# Generated by `dotfiles apply`; POSIX sh, sourced by every shell and agent.\n", func(p manifest.Provides) string { return p.Env }},
		{"zshrc.zsh", "# Generated by `dotfiles apply`; interactive zsh fragments.\n", func(p manifest.Provides) string { return p.Zshrc }},
		{"gitconfig", "# Generated by `dotfiles apply`; included by ~/.config/git/config.\n", func(p manifest.Provides) string { return p.Gitconfig }},
		{"ssh_config", "# Generated by `dotfiles apply`; included by ~/.ssh/config.\n", func(p manifest.Provides) string { return p.SSHConfig }},
	}
	for _, frag := range fragments {
		var b bytes.Buffer
		b.WriteString(frag.header)
		for _, id := range order {
			name := frag.pick(features[id].Provides)
			if name == "" {
				continue
			}
			content, err := os.ReadFile(filepath.Join(features[id].Dir, filepath.FromSlash(name)))
			if err != nil {
				return nil, fmt.Errorf("%w: %s: %s: %w", ErrPlan, id, name, err)
			}
			fmt.Fprintf(&b, "\n# --- %s\n", id)
			b.Write(content)
			if len(content) > 0 && content[len(content)-1] != '\n' {
				b.WriteByte('\n')
			}
		}
		if frag.name == "env.sh" {
			writeExports(&b, features, order, values)
		}
		files = append(files, File{Path: filepath.Join(env.GeneratedDir, frag.name), Content: b.Bytes()})
	}
	return files, nil
}

// writeExports appends an export for every enabled feature's setting that
// declares an environment name and has a value, unless the variable is
// already set. A path starting with ~/ is written relative to $HOME, so the
// file stays valid for any user.
func writeExports(b *bytes.Buffer, features map[string]*manifest.Feature, order []string, values map[string]any) {
	var lines []string
	for _, id := range order {
		for name, s := range features[id].Settings {
			v, ok := values[name]
			if s.Env == "" || !ok {
				continue
			}
			var rendered string
			switch val := v.(type) {
			case string:
				if s.Type == "path" && strings.HasPrefix(val, "~/") {
					rendered = `"$HOME"/` + shellQuote(strings.TrimPrefix(val, "~/"))
				} else {
					rendered = shellQuote(val)
				}
			default:
				rendered = shellQuote(fmt.Sprint(val))
			}
			// A value the shell inherited wins, as a variable set by hand would.
			lines = append(lines, fmt.Sprintf(`[ -n "${%[1]s:-}" ] || %[1]s=%[2]s; export %[1]s # %[3]s`, s.Env, rendered, name))
		}
	}
	if len(lines) == 0 {
		return
	}
	sort.Strings(lines)
	b.WriteString("\n# --- settings\n")
	for _, l := range lines {
		b.WriteString(l + "\n")
	}
}

// shellQuote quotes s for POSIX sh.
func shellQuote(s string) string {
	return "'" + strings.ReplaceAll(s, "'", `'\''`) + "'"
}
