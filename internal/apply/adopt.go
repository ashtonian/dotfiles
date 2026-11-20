package apply

import (
	"bytes"
	"context"
	"errors"
	"fmt"
	"os"
	"path/filepath"

	"github.com/ashtonian/dotfiles/internal/atomicfile"
	"github.com/ashtonian/dotfiles/internal/plan"
	"github.com/ashtonian/dotfiles/internal/prefs"
)

// ErrNotManaged means a target given to Adopt is neither one of this
// machine's managed copies nor one of its app settings.
var ErrNotManaged = errors.New("not a managed copy or app setting on this machine")

// Adopt makes what is here the repository's version, for each target: a
// managed copy's path, whose content is written into its tracked source, or
// an app setting's <store>:<key>, whose current value replaces its line in
// the prefs file. Both are recorded, so the next apply sees no drift. It is
// how a change made here, by hand or by the app itself, reaches the
// repository. Every target is checked before any tracked file is written.
func Adopt(ctx context.Context, p *plan.Plan, prev *State, targets []string, stores map[string]PrefStore) (*Report, *State, error) {
	copies := make(map[string]plan.Copy, len(p.Copies))
	for _, c := range p.Copies {
		copies[c.Target] = c
	}
	settings := make(map[string]plan.Pref, len(p.Prefs))
	for _, pr := range p.Prefs {
		settings[pr.ID()] = pr
	}

	// Each tracked file to write, built up in memory so two settings adopted
	// from one prefs file both land.
	type source struct {
		before, after []byte
		mode          os.FileMode
	}
	sources := map[string]*source{}
	var order []string
	load := func(path string) (*source, error) {
		if s, ok := sources[path]; ok {
			return s, nil
		}
		info, err := os.Stat(path)
		if err != nil {
			return nil, err
		}
		data, err := os.ReadFile(path)
		if err != nil {
			return nil, err
		}
		s := &source{before: data, after: data, mode: info.Mode().Perm()}
		sources[path] = s
		order = append(order, path)
		return s, nil
	}

	next := prev.clone()
	var actions []Action // one per target whose tracked file changes
	for _, target := range targets {
		if pr, ok := settings[target]; ok {
			store, ok := stores[pr.Store]
			if !ok {
				return nil, nil, fmt.Errorf("adopt %s: no store for %s", target, pr.Store)
			}
			live, present, err := store.Get(ctx, pr.Key)
			if err != nil {
				return nil, nil, fmt.Errorf("adopt %s: %w", target, err)
			}
			if !present {
				return nil, nil, fmt.Errorf("adopt %s: it has no value here, so there is nothing to keep", target)
			}
			src, err := load(pr.Source)
			if err != nil {
				return nil, nil, fmt.Errorf("adopt %s: %w", target, err)
			}
			updated, err := prefs.SetLine(pr.Source, src.after, pr.Key, live)
			if err != nil {
				return nil, nil, fmt.Errorf("adopt %s: %w", target, err)
			}
			if !bytes.Equal(updated, src.after) {
				actions = append(actions, Action{Kind: "adopt", Path: target, Detail: pr.Source})
			}
			src.after = updated
			value, err := prefs.EncodeJSON(live)
			if err != nil {
				return nil, nil, fmt.Errorf("adopt %s: %w", target, err)
			}
			rec := PrefRecord{Value: value, Previous: value, HadPrevious: true}
			if old, had := prev.Prefs[target]; had {
				rec.Previous, rec.HadPrevious = old.Previous, old.HadPrevious
			}
			next.Prefs[target] = rec
			continue
		}

		c, ok := copies[filepath.Clean(target)]
		if !ok {
			return nil, nil, fmt.Errorf("%w: %s", ErrNotManaged, target)
		}
		info, err := os.Lstat(c.Target)
		if err != nil {
			return nil, nil, fmt.Errorf("adopt %s: %w", c.Target, err)
		}
		if !info.Mode().IsRegular() {
			return nil, nil, fmt.Errorf("adopt %s: %w: it is not a regular file", c.Target, ErrNotManaged)
		}
		content, err := os.ReadFile(c.Target)
		if err != nil {
			return nil, nil, fmt.Errorf("adopt %s: %w", c.Target, err)
		}
		src, err := load(c.Source)
		if err != nil {
			return nil, nil, fmt.Errorf("adopt %s: %w", c.Target, err)
		}
		if !bytes.Equal(content, src.after) {
			actions = append(actions, Action{Kind: "adopt", Path: c.Target, Detail: c.Source})
		}
		src.after = content
		next.Copies[c.Target] = CopyRecord{Source: c.Source, SHA256: hash(content)}
	}

	for _, path := range order {
		s := sources[path]
		if bytes.Equal(s.before, s.after) {
			continue
		}
		if err := atomicfile.Write(path, s.after, s.mode); err != nil {
			return &Report{}, nil, err
		}
	}
	return &Report{Actions: actions}, next, nil
}
