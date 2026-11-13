// Package plan turns the enabled features into the files a machine should
// have: links, managed copies, generated outputs and local stubs.
package plan

import (
	"bytes"
	"errors"
	"fmt"
	"io/fs"
	"os"
	"path/filepath"
	"strings"

	"github.com/ashtonian/dotfiles/internal/manifest"
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

// Stub is a local entry point that must exist and contain Line.
type Stub struct {
	Path, Line, Feature string
}

// Plan is the desired state for one machine.
type Plan struct {
	Links     []Link
	Copies    []Copy
	Generated []File
	Stubs     []Stub
}

// Build plans the enabled features, in dependency order.
func Build(features map[string]*manifest.Feature, order []string, env Env) (*Plan, error) {
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
					p.Links = append(p.Links, Link{Target: target, Source: source, Feature: id})
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
			p.Stubs = append(p.Stubs, Stub{Path: target, Line: s.Line, Feature: id})
		}
	}

	generated, err := generate(features, order, env)
	if err != nil {
		return nil, err
	}
	p.Generated = generated
	return p, nil
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

func underLibrary(rel string) bool {
	first, _, _ := strings.Cut(filepath.ToSlash(rel), "/")
	return first == "Library"
}

// generate renders the outputs shells and tools read, so no shell startup
// parses a manifest. Every output is written even when empty, so stubs and
// includes can load it unconditionally.
func generate(features map[string]*manifest.Feature, order []string, env Env) ([]File, error) {
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
	for _, kind := range []string{"tap", "brew", "cask", "mas", "flatpak"} {
		for _, id := range order {
			pr := features[id].Provides
			switch kind {
			case "tap":
				for _, n := range pr.Tap {
					entry(fmt.Sprintf("tap %q", n), id)
				}
			case "brew":
				for _, n := range pr.Brew {
					entry(fmt.Sprintf("brew %q", n), id)
				}
			case "cask":
				if env.GOOS == "darwin" {
					for _, n := range pr.Cask {
						entry(fmt.Sprintf("cask %q", n), id)
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
		files = append(files, File{Path: filepath.Join(env.GeneratedDir, frag.name), Content: b.Bytes()})
	}
	return files, nil
}
