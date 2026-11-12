package apply

import (
	"bytes"
	"errors"
	"fmt"
	"os"
	"path/filepath"

	"github.com/ashtonian/dotfiles/internal/plan"
)

// ErrNotCopy means a path given to Adopt is not one of this machine's managed
// copies.
var ErrNotCopy = errors.New("not a managed copy on this machine")

// Adopt makes the current content of each managed copy at targets the
// repository's version: it writes that content into the copy's tracked source
// and records it, so the next apply sees no drift. It is how a change made
// here, by hand or by the app that rewrites its own settings file, reaches
// the repository. Every target is checked before any source is written.
func Adopt(p *plan.Plan, prev *State, targets []string) (*Report, *State, error) {
	byTarget := make(map[string]plan.Copy, len(p.Copies))
	for _, c := range p.Copies {
		byTarget[c.Target] = c
	}
	type adoption struct {
		copy    plan.Copy
		content []byte
		mode    os.FileMode
		changed bool
	}
	adoptions := make([]adoption, 0, len(targets))
	for _, target := range targets {
		c, ok := byTarget[filepath.Clean(target)]
		if !ok {
			return nil, nil, fmt.Errorf("%w: %s", ErrNotCopy, target)
		}
		info, err := os.Lstat(c.Target)
		if err != nil {
			return nil, nil, fmt.Errorf("adopt %s: %w", c.Target, err)
		}
		if !info.Mode().IsRegular() {
			return nil, nil, fmt.Errorf("adopt %s: %w: it is not a regular file", c.Target, ErrNotCopy)
		}
		content, err := os.ReadFile(c.Target)
		if err != nil {
			return nil, nil, fmt.Errorf("adopt %s: %w", c.Target, err)
		}
		srcInfo, err := os.Stat(c.Source)
		if err != nil {
			return nil, nil, fmt.Errorf("adopt %s: %w", c.Target, err)
		}
		existing, err := os.ReadFile(c.Source)
		if err != nil {
			return nil, nil, fmt.Errorf("adopt %s: %w", c.Target, err)
		}
		adoptions = append(adoptions, adoption{copy: c, content: content, mode: srcInfo.Mode().Perm(),
			changed: !bytes.Equal(existing, content)})
	}

	report := &Report{}
	next := prev.clone()
	for _, a := range adoptions {
		if a.changed {
			if err := writeAtomic(a.copy.Source, a.content, a.mode); err != nil {
				return report, nil, err
			}
			report.Actions = append(report.Actions, Action{Kind: "adopt", Path: a.copy.Target, Detail: a.copy.Source})
		}
		next.Copies[a.copy.Target] = CopyRecord{Source: a.copy.Source, SHA256: hash(a.content)}
	}
	return report, next, nil
}
