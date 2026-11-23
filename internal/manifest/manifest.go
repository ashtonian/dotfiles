// Package manifest reads the feature, profile and machine manifests that
// describe what each machine should have. See docs/MACHINE-FEATURES.md.
package manifest

import (
	"errors"
	"fmt"
	"os"
	"path"
	"path/filepath"
	"regexp"
	"slices"
	"sort"
	"strings"

	"github.com/BurntSushi/toml"
)

// Platforms a feature can declare; the values match runtime.GOOS.
var Platforms = []string{"darwin", "linux", "windows"}

// SettingTypes are the value types a feature setting can declare.
var SettingTypes = []string{"bool", "int", "string", "path", "secret"}

var (
	idPattern = regexp.MustCompile(`^[a-z0-9]+(?:[.-][a-z0-9]+)*$`)
	// An overlay's name is the first word of every ID in it, so it has no dot.
	overlayPattern = regexp.MustCompile(`^[a-z0-9]+(?:-[a-z0-9]+)*$`)
	// Package names end up inside generated Ruby (the Brewfile), so only the
	// characters real formula, cask, tap and flatpak names use are allowed.
	packagePattern = regexp.MustCompile(`^[A-Za-z0-9][A-Za-z0-9@._+/-]*$`)
	envPattern     = regexp.MustCompile(`^[A-Z_][A-Z0-9_]*$`)
	settingPattern = regexp.MustCompile(`^[a-z0-9_]+(?:\.[a-z0-9_]+)*$`)
	keywordPattern = regexp.MustCompile(`^[A-Za-z][A-Za-z0-9_-]*$`)

	// ErrInvalid wraps every validation failure, so callers can tell a bad
	// manifest from an I/O error.
	ErrInvalid = errors.New("invalid manifest")
	// ErrNoMachine means this machine has no manifest yet. Without one no
	// profile applies, so apply would remove everything the profiles install;
	// callers refuse to run instead.
	ErrNoMachine = errors.New("no machine manifest")
	// ErrNoOverlay means the machine manifest lists an overlay that is not
	// cloned. Applying without it would remove what its features install.
	ErrNoOverlay = errors.New("overlay not cloned")
)

// Root is a tree of features and profiles: the dotfiles repository, or an
// overlay, which is one context's private checkout (personal work, or one
// client). Each feature ID and profile name belongs to the root its first
// word names: an overlay's all start with the overlay's name, and the
// repository's never start with an overlay's. So every ID says which context
// it comes from, and no root can shadow another's.
type Root struct {
	Dir     string
	Overlay string // the overlay's name; empty for the dotfiles repository
}

// Feature is one toggleable capability: features/<id>/feature.toml plus the
// files beside it.
type Feature struct {
	ID          string             `toml:"id"`
	Description string             `toml:"description"`
	Category    string             `toml:"category"`
	Platforms   []string           `toml:"platforms"`
	Default     bool               `toml:"default"`
	Requires    []string           `toml:"requires"`
	Conflicts   []string           `toml:"conflicts"`
	Provides    Provides           `toml:"provides"`
	Settings    map[string]Setting `toml:"settings"`
	// Retire lists paths under $HOME this feature used to install by another
	// means, such as a stow link. apply removes each one that is still a link
	// into the repository and that no feature installs now.
	Retire []string `toml:"retire"`

	// Dir is the absolute directory holding feature.toml.
	Dir string `toml:"-"`
}

// Provides lists what a feature installs. Paths are relative to the
// feature's directory; Link and Copy paths are relative to its home/ tree.
type Provides struct {
	Tap  []string `toml:"tap"`
	Brew []string `toml:"brew"`
	// BrewLink sets a formula's `link:` option, by formula name.
	BrewLink  map[string]bool `toml:"brew_link"`
	Cask      []string        `toml:"cask"`
	Mas       []MasApp        `toml:"mas"`
	Flatpak   []string        `toml:"flatpak"`
	Vscode    []string        `toml:"vscode"`     // editor extension ids
	Go        []string        `toml:"go"`         // go install packages
	Env       string          `toml:"env"`        // POSIX fragment for every shell and agent
	Zshrc     string          `toml:"zshrc"`      // interactive zsh fragment
	Gitconfig string          `toml:"gitconfig"`  // git config fragment
	SSHConfig string          `toml:"ssh_config"` // ssh config fragment
	Bin       []string        `toml:"bin"`        // scripts linked into ~/.local/bin
	Link      []string        `toml:"link"`       // files under home/, linked one by one
	Copy      []string        `toml:"copy"`       // files under home/, installed as managed copies
	Stub      []Stub          `toml:"stub"`       // local entry points created once, never overwritten
	// LinkUnlessExists holds links back: for an entry of Link, paths
	// (absolute or starting with ~/) whose presence means something else owns
	// the link's place. While any exists, apply neither makes nor replaces the
	// entry's links.
	LinkUnlessExists map[string][]string `toml:"link_unless_exists"`
	// LaunchAgent lists launchd jobs for the user's GUI session. They are
	// installed on macOS only; elsewhere the rest of the feature applies.
	LaunchAgent []LaunchAgent `toml:"launch_agent"`
}

// LaunchAgent is a launchd job that apply installs into ~/Library/LaunchAgents
// and loads. Its plist is a template: every $HOME in it becomes the home
// directory. The template is named <Label>.plist, and so is the installed file.
type LaunchAgent struct {
	Plist string `toml:"plist"` // relative to the feature's directory
	// WhenExists lists paths, absolute or starting with ~/, that must all
	// exist before the agent is installed: the program it runs, or a file a
	// person creates during setup. Until then apply leaves the agent out, and
	// removes it if it had installed it.
	WhenExists []string `toml:"when_exists"`
}

// Label is the launchd label the template's file name declares.
func (a LaunchAgent) Label() string {
	return strings.TrimSuffix(path.Base(a.Plist), ".plist")
}

// MasApp is a Mac App Store app.
type MasApp struct {
	Name string `toml:"name"`
	ID   int64  `toml:"id"`
}

// Stub is a local file that tools may append to, created with one line that
// loads the tracked configuration. The repository never edits it again.
type Stub struct {
	Path string `toml:"path"` // relative to $HOME
	Line string `toml:"line"`
	// Before lists keywords the line must precede in an existing file, such as
	// ssh_config's Host and Match: an Include after the first Host line
	// applies only inside that block.
	Before []string `toml:"before"`
	// KeepExisting leaves an existing file as it is; the line is written only
	// when apply creates the file. For an entry point that needs nothing from
	// the line, such as ~/.gitconfig, which git reads after the shared config.
	KeepExisting bool `toml:"keep_existing"`
}

// Setting declares a typed configuration value. Names are global across
// features, such as "paths.playwright_browsers".
type Setting struct {
	Type     string `toml:"type"`
	Default  any    `toml:"default"`
	Required bool   `toml:"required"`
	Doc      string `toml:"doc"`
	// Env exports the resolved value under this name in the generated env.sh.
	// Secrets cannot be exported.
	Env string `toml:"env"`
	// Values, for a string setting, are the only values it may take, so a
	// typo fails resolve instead of the script that reads the setting.
	Values []string `toml:"values"`
}

// Check validates a value for this setting: its type, then Values.
func (s Setting) Check(v any) error {
	if err := CheckValue(s.Type, v); err != nil {
		return err
	}
	if len(s.Values) > 0 && !slices.Contains(s.Values, v.(string)) {
		return fmt.Errorf("want one of %s, got %q", strings.Join(s.Values, ", "), v)
	}
	return nil
}

// Profile is a named set of feature decisions and setting values.
type Profile struct {
	Name     string         `toml:"-"`
	Features Selection      `toml:"features"`
	Settings map[string]any `toml:"settings"`
}

// Selection turns features on or off.
type Selection struct {
	Enable  []string `toml:"enable"`
	Disable []string `toml:"disable"`
}

// Machine is this machine's untracked manifest: the overlays of the contexts
// it belongs to, its profiles in order, then single-feature and setting
// overrides.
type Machine struct {
	Overlays []string       `toml:"overlays"`
	Profiles []string       `toml:"profiles"`
	Features Selection      `toml:"features"`
	Settings map[string]any `toml:"settings"`
}

// Supports reports whether the feature runs on goos. No platforms means all.
func (f *Feature) Supports(goos string) bool {
	return len(f.Platforms) == 0 || slices.Contains(f.Platforms, goos)
}

// checkOverlayNames rejects an overlay name that is not one lowercase word
// group, or that is listed twice.
func checkOverlayNames(names []string) error {
	seen := map[string]bool{}
	for _, name := range names {
		if !overlayPattern.MatchString(name) {
			return fmt.Errorf("%w: overlay name %q must be lowercase words joined by -", ErrInvalid, name)
		}
		if seen[name] {
			return fmt.Errorf("%w: overlay %s is listed twice", ErrInvalid, name)
		}
		seen[name] = true
	}
	return nil
}

// OverlayRoots returns the roots of the overlays named, each the directory
// of that name under dir. An overlay that is not a directory there is
// ErrNoOverlay.
func OverlayRoots(dir string, names []string) ([]Root, error) {
	if err := checkOverlayNames(names); err != nil {
		return nil, err
	}
	roots := make([]Root, 0, len(names))
	for _, name := range names {
		root := Root{Dir: filepath.Join(dir, name), Overlay: name}
		info, err := os.Stat(root.Dir)
		if errors.Is(err, os.ErrNotExist) || (err == nil && !info.IsDir()) {
			return nil, fmt.Errorf("%w: %s is not at %s; clone its repository there, or remove it from machine.toml", ErrNoOverlay, name, root.Dir)
		}
		if err != nil {
			return nil, fmt.Errorf("overlay %s: %w", name, err)
		}
		roots = append(roots, root)
	}
	return roots, nil
}

// overlayOwners returns the set of the roots' overlay names.
func overlayOwners(roots []Root) (map[string]bool, error) {
	var names []string
	for _, r := range roots {
		if r.Overlay != "" {
			names = append(names, r.Overlay)
		}
	}
	if err := checkOverlayNames(names); err != nil {
		return nil, err
	}
	owners := make(map[string]bool, len(names))
	for _, name := range names {
		owners[name] = true
	}
	return owners, nil
}

// checkOwner reports a feature ID or profile name that is in the wrong root:
// an overlay's must start with the overlay's name, and the repository's must
// not start with any overlay's.
func checkOwner(kind, name string, root Root, overlays map[string]bool) error {
	first, _, _ := strings.Cut(name, ".")
	switch {
	case root.Overlay != "" && first != root.Overlay:
		return fmt.Errorf("%s %q is in overlay %s, so its name must be %q or start with %q", kind, name, root.Overlay, root.Overlay, root.Overlay+".")
	case root.Overlay == "" && overlays[first]:
		return fmt.Errorf("%s %q in the repository starts with the name of overlay %s; rename one of them", kind, name, first)
	}
	return nil
}

// LoadFeatures reads features/*/feature.toml under each root, keyed by ID.
func LoadFeatures(roots ...Root) (map[string]*Feature, error) {
	overlays, err := overlayOwners(roots)
	if err != nil {
		return nil, err
	}
	var paths []string
	rootOf := map[string]Root{}
	for _, root := range roots {
		found, err := filepath.Glob(filepath.Join(root.Dir, "features", "*", "feature.toml"))
		if err != nil {
			return nil, fmt.Errorf("list features in %s: %w", root.Dir, err)
		}
		for _, path := range found {
			rootOf[path] = root
		}
		paths = append(paths, found...)
	}
	features := make(map[string]*Feature, len(paths))
	settingOwner := map[string]string{}
	agentOwner := map[string]string{}
	for _, path := range paths {
		var f Feature
		if err := decodeStrict(path, &f, settingDefault); err != nil {
			return nil, err
		}
		f.Dir = filepath.Dir(path)
		if err := validateFeature(&f, filepath.Base(f.Dir)); err != nil {
			return nil, fmt.Errorf("%w: %s: %w", ErrInvalid, path, err)
		}
		if err := checkOwner("feature", f.ID, rootOf[path], overlays); err != nil {
			return nil, fmt.Errorf("%w: %s: %w", ErrInvalid, path, err)
		}
		for name := range f.Settings {
			if owner, taken := settingOwner[name]; taken {
				return nil, fmt.Errorf("%w: setting %q is declared by both %s and %s", ErrInvalid, name, owner, f.ID)
			}
			settingOwner[name] = f.ID
		}
		for _, a := range f.Provides.LaunchAgent {
			if owner, taken := agentOwner[a.Label()]; taken {
				return nil, fmt.Errorf("%w: LaunchAgent %s is declared by both %s and %s", ErrInvalid, a.Label(), owner, f.ID)
			}
			agentOwner[a.Label()] = f.ID
		}
		features[f.ID] = &f
	}
	return features, nil
}

// LoadProfiles reads profiles/*.toml under each root, keyed by file name.
func LoadProfiles(roots ...Root) (map[string]*Profile, error) {
	overlays, err := overlayOwners(roots)
	if err != nil {
		return nil, err
	}
	profiles := map[string]*Profile{}
	for _, root := range roots {
		paths, err := filepath.Glob(filepath.Join(root.Dir, "profiles", "*.toml"))
		if err != nil {
			return nil, fmt.Errorf("list profiles in %s: %w", root.Dir, err)
		}
		for _, path := range paths {
			var p Profile
			if err := decodeStrict(path, &p, settingValue); err != nil {
				return nil, err
			}
			p.Name = strings.TrimSuffix(filepath.Base(path), ".toml")
			if !idPattern.MatchString(p.Name) {
				return nil, fmt.Errorf("%w: %s: profile name %q must be lowercase words joined by - or .", ErrInvalid, path, p.Name)
			}
			if err := checkOwner("profile", p.Name, root, overlays); err != nil {
				return nil, fmt.Errorf("%w: %s: %w", ErrInvalid, path, err)
			}
			profiles[p.Name] = &p
		}
	}
	return profiles, nil
}

// LoadMachine reads the machine manifest. A missing file is ErrNoMachine.
func LoadMachine(path string) (*Machine, error) {
	var m Machine
	if err := decodeStrict(path, &m, settingValue); err != nil {
		if errors.Is(err, os.ErrNotExist) {
			return nil, fmt.Errorf("%w at %s", ErrNoMachine, path)
		}
		return nil, err
	}
	if err := checkOverlayNames(m.Overlays); err != nil {
		return nil, fmt.Errorf("%s: %w", path, err)
	}
	return &m, nil
}

// MachineFile renders a new machine manifest that lists overlays and
// profiles. Their names are validated before this is called, so they need no
// escaping.
func MachineFile(overlays, profiles []string) []byte {
	var b strings.Builder
	b.WriteString("# This machine's overlays, profiles, feature overrides and setting overrides.\n")
	b.WriteString("# Written by `dotfiles init`; see docs/MACHINE-FEATURES.md.\n")
	if len(overlays) > 0 {
		b.WriteString("overlays = ")
		writeList(&b, overlays)
	}
	b.WriteString("profiles = ")
	writeList(&b, profiles)
	return []byte(b.String())
}

func writeList(b *strings.Builder, items []string) {
	b.WriteString("[")
	for i, item := range items {
		if i > 0 {
			b.WriteString(", ")
		}
		fmt.Fprintf(b, "%q", item)
	}
	b.WriteString("]\n")
}

// Setting values decode into `any`, and the decoder reports the keys inside
// such a value (a secret's { secret = "op://..." }) as undecoded; CheckValue
// validates those values against their declared type instead.
func settingValue(k toml.Key) bool   { return len(k) >= 3 && k[0] == "settings" }
func settingDefault(k toml.Key) bool { return len(k) >= 4 && k[0] == "settings" && k[2] == "default" }

func decodeStrict(path string, v any, freeform func(toml.Key) bool) error {
	md, err := toml.DecodeFile(path, v)
	if err != nil {
		if errors.Is(err, os.ErrNotExist) {
			return err
		}
		return fmt.Errorf("%w: %s: %w", ErrInvalid, path, err)
	}
	var keys []string
	for _, k := range md.Undecoded() {
		if !freeform(k) {
			keys = append(keys, k.String())
		}
	}
	if len(keys) > 0 {
		sort.Strings(keys)
		return fmt.Errorf("%w: %s: unknown keys: %s", ErrInvalid, path, strings.Join(keys, ", "))
	}
	return nil
}

func validateFeature(f *Feature, dirName string) error {
	if !idPattern.MatchString(f.ID) {
		return fmt.Errorf("id %q must be lowercase words joined by - or .", f.ID)
	}
	if f.ID != dirName {
		return fmt.Errorf("id %q must match its directory name %q", f.ID, dirName)
	}
	for _, p := range f.Platforms {
		if !slices.Contains(Platforms, p) {
			return fmt.Errorf("unknown platform %q (want one of %s)", p, strings.Join(Platforms, ", "))
		}
	}
	for _, id := range append(slices.Clone(f.Requires), f.Conflicts...) {
		if !idPattern.MatchString(id) {
			return fmt.Errorf("feature reference %q is not a valid id", id)
		}
	}
	var paths []string
	for _, p := range []string{f.Provides.Env, f.Provides.Zshrc, f.Provides.Gitconfig, f.Provides.SSHConfig} {
		if p != "" {
			paths = append(paths, p)
		}
	}
	paths = append(paths, f.Provides.Bin...)
	for _, p := range paths {
		if err := checkRelative(p); err != nil {
			return err
		}
	}
	for _, p := range append(slices.Clone(f.Provides.Link), f.Provides.Copy...) {
		if err := checkRelative(p); err != nil {
			return err
		}
	}
	for entry, paths := range f.Provides.LinkUnlessExists {
		if !slices.Contains(f.Provides.Link, entry) {
			return fmt.Errorf("link_unless_exists names %q, which is not in link", entry)
		}
		if len(paths) == 0 {
			return fmt.Errorf("link_unless_exists %s: list the paths that hold it", entry)
		}
		for _, w := range paths {
			if !strings.HasPrefix(w, "/") && !strings.HasPrefix(w, "~/") {
				return fmt.Errorf("link_unless_exists %s: %q must be absolute or start with ~/", entry, w)
			}
		}
	}
	for _, s := range f.Provides.Stub {
		if err := checkRelative(s.Path); err != nil {
			return err
		}
		if s.Line == "" || strings.ContainsAny(s.Line, "\n\r") {
			return fmt.Errorf("stub %s needs exactly one line", s.Path)
		}
		for _, k := range s.Before {
			if !keywordPattern.MatchString(k) {
				return fmt.Errorf("stub %s: before keyword %q must be one word", s.Path, k)
			}
		}
	}
	for _, p := range f.Retire {
		if err := checkRelative(p); err != nil {
			return err
		}
	}
	for _, a := range f.Provides.LaunchAgent {
		if err := checkRelative(a.Plist); err != nil {
			return err
		}
		if !strings.HasSuffix(a.Plist, ".plist") {
			return fmt.Errorf("launch_agent %q must be a .plist file named for its Label", a.Plist)
		}
		for _, w := range a.WhenExists {
			if !strings.HasPrefix(w, "/") && !strings.HasPrefix(w, "~/") {
				return fmt.Errorf("launch_agent %s: when_exists %q must be absolute or start with ~/", a.Plist, w)
			}
		}
	}
	for _, list := range [][]string{f.Provides.Tap, f.Provides.Brew, f.Provides.Cask, f.Provides.Flatpak, f.Provides.Vscode, f.Provides.Go} {
		for _, name := range list {
			if !packagePattern.MatchString(name) {
				return fmt.Errorf("package name %q has characters a package name cannot", name)
			}
		}
	}
	for name := range f.Provides.BrewLink {
		if !slices.Contains(f.Provides.Brew, name) {
			return fmt.Errorf("brew_link names %q, which is not in brew", name)
		}
	}
	for _, app := range f.Provides.Mas {
		if app.Name == "" || app.ID <= 0 || strings.ContainsAny(app.Name, "\"\\\n") {
			return fmt.Errorf("mas entries need a plain name and a positive id")
		}
	}
	for name, s := range f.Settings {
		if !settingPattern.MatchString(name) {
			return fmt.Errorf("setting name %q must be dotted lowercase words", name)
		}
		if !slices.Contains(SettingTypes, s.Type) {
			return fmt.Errorf("setting %q has unknown type %q (want one of %s)", name, s.Type, strings.Join(SettingTypes, ", "))
		}
		if len(s.Values) > 0 && s.Type != "string" {
			return fmt.Errorf("setting %q lists values, which only a string setting can", name)
		}
		for i, v := range s.Values {
			if v == "" || slices.Contains(s.Values[:i], v) {
				return fmt.Errorf("setting %q values must be distinct and not empty", name)
			}
		}
		if s.Default != nil {
			if err := s.Check(s.Default); err != nil {
				return fmt.Errorf("setting %q default: %w", name, err)
			}
		}
		if s.Env != "" {
			if !envPattern.MatchString(s.Env) {
				return fmt.Errorf("setting %q exports %q, which is not an environment variable name", name, s.Env)
			}
			if s.Type == "secret" {
				return fmt.Errorf("setting %q is a secret, so it cannot be exported to the environment", name)
			}
		}
	}
	return nil
}

// checkRelative rejects absolute paths and paths that leave their base.
func checkRelative(p string) error {
	if p == "" || filepath.IsAbs(p) || strings.HasPrefix(p, "/") {
		return fmt.Errorf("path %q must be relative", p)
	}
	clean := filepath.Clean(filepath.FromSlash(p))
	if clean == ".." || strings.HasPrefix(clean, ".."+string(filepath.Separator)) {
		return fmt.Errorf("path %q leaves the feature directory", p)
	}
	return nil
}

// CheckValue validates a setting value against its declared type. A secret is
// a table holding only an op:// reference; the value itself never appears in
// a manifest.
func CheckValue(typ string, v any) error {
	switch typ {
	case "bool":
		if _, ok := v.(bool); !ok {
			return fmt.Errorf("want a boolean, got %T", v)
		}
	case "int":
		if _, ok := v.(int64); !ok {
			return fmt.Errorf("want an integer, got %T", v)
		}
	case "string", "path":
		if _, ok := v.(string); !ok {
			return fmt.Errorf("want a string, got %T", v)
		}
	case "secret":
		table, ok := v.(map[string]any)
		ref, isString := table["secret"].(string)
		if !ok || len(table) != 1 || !isString || !strings.HasPrefix(ref, "op://") {
			return errors.New(`want { secret = "op://vault/item/field" }, never a value`)
		}
	default:
		return fmt.Errorf("unknown type %q", typ)
	}
	return nil
}
