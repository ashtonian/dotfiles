// Package apply converges a machine on a plan: it makes the planned links,
// managed copies, generated outputs and stubs, and removes what an earlier
// run installed for features that are no longer enabled. It never overwrites
// a file it did not create.
package apply

import (
	"bytes"
	"context"
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"fmt"
	"io/fs"
	"os"
	"path/filepath"
	"sort"
	"strings"

	"github.com/ashtonian/dotfiles/internal/plan"
)

// Env is the machine apply works on.
type Env struct {
	Home     string
	RepoRoot string // links into this tree are apply's own, including stow's old ones
}

// Action is one change apply makes, or would make in a dry run.
type Action struct {
	Kind   string // link, relink, unlink, copy, update-copy, remove-copy, write, remove, stub, adopt
	Path   string
	Detail string
}

// Problem is something apply refused to change; the owner has to decide.
type Problem struct {
	Path   string
	Detail string
}

// Report lists what a run did and what it left alone.
type Report struct {
	Actions  []Action
	Problems []Problem
}

type runner struct {
	ctx    context.Context
	env    Env
	repos  []string // the repository root as given and with symlinks resolved
	prev   *State
	next   *State
	dryRun bool
	report Report
}

// Run converges the machine on p. prev is the state the last run saved; the
// returned state is what to save now. With dryRun nothing on disk changes and
// the report lists what would. I/O failures stop the run; conflicts are
// reported as problems and leave the file untouched.
func Run(ctx context.Context, p *plan.Plan, prev *State, env Env, dryRun bool) (*Report, *State, error) {
	r := &runner{ctx: ctx, env: env, prev: prev, next: newState(), dryRun: dryRun}
	r.repos = []string{filepath.Clean(env.RepoRoot)}
	if resolved, err := filepath.EvalSymlinks(env.RepoRoot); err == nil && resolved != r.repos[0] {
		r.repos = append(r.repos, resolved)
	}

	steps := []func() error{
		func() error { return eachItem(r, p.Generated, r.generated) },
		func() error { return eachItem(r, p.Links, r.link) },
		func() error { return eachItem(r, p.Copies, r.copy) },
		func() error { return eachItem(r, p.Stubs, r.stub) },
		func() error { return r.teardown(p) },
	}
	for _, step := range steps {
		if err := step(); err != nil {
			return &r.report, nil, err
		}
	}
	return &r.report, r.next, nil
}

func eachItem[T any](r *runner, items []T, do func(T) error) error {
	for _, item := range items {
		if err := r.ctx.Err(); err != nil {
			return err
		}
		if err := do(item); err != nil {
			return err
		}
	}
	return nil
}

func (r *runner) act(kind, path, detail string) {
	r.report.Actions = append(r.report.Actions, Action{Kind: kind, Path: path, Detail: detail})
}

func (r *runner) problem(path, detail string) {
	r.report.Problems = append(r.report.Problems, Problem{Path: path, Detail: detail})
}

// inRepo reports whether the symlink at link, whose destination is dest,
// points into the repository.
func (r *runner) inRepo(link, dest string) bool {
	if !filepath.IsAbs(dest) {
		dest = filepath.Join(filepath.Dir(link), dest)
	}
	dest = filepath.Clean(dest)
	for _, repo := range r.repos {
		if dest == repo || strings.HasPrefix(dest, repo+string(filepath.Separator)) {
			return true
		}
	}
	return false
}

// foldedParent returns a directory between $HOME and target that is a link
// into the repository: an old stow folding, through which a write would land
// in the repository.
func (r *runner) foldedParent(target string) string {
	home := filepath.Clean(r.env.Home)
	for dir := filepath.Dir(target); dir != home && strings.HasPrefix(dir, home+string(filepath.Separator)); dir = filepath.Dir(dir) {
		info, err := os.Lstat(dir)
		if err != nil || info.Mode()&fs.ModeSymlink == 0 {
			continue
		}
		if dest, err := os.Readlink(dir); err == nil && r.inRepo(dir, dest) {
			return dir
		}
	}
	return ""
}

func (r *runner) mkdirParent(path string) error {
	if r.dryRun {
		return nil
	}
	if err := os.MkdirAll(filepath.Dir(path), 0o700); err != nil {
		return fmt.Errorf("create %s: %w", filepath.Dir(path), err)
	}
	return nil
}

func (r *runner) generated(f plan.File) error {
	sum := hash(f.Content)
	if existing, err := os.ReadFile(f.Path); err == nil && bytes.Equal(existing, f.Content) {
		r.next.Generated[f.Path] = sum
		return nil
	} else if err != nil && !errors.Is(err, fs.ErrNotExist) {
		return fmt.Errorf("read %s: %w", f.Path, err)
	}
	r.act("write", f.Path, "")
	if !r.dryRun {
		if err := r.mkdirParent(f.Path); err != nil {
			return err
		}
		if err := writeAtomic(f.Path, f.Content, 0o644); err != nil {
			return err
		}
	}
	r.next.Generated[f.Path] = sum
	return nil
}

func (r *runner) link(l plan.Link) error {
	keepPrevious := func() {
		if src, ok := r.prev.Links[l.Target]; ok {
			r.next.Links[l.Target] = src
		}
	}
	if dir := r.foldedParent(l.Target); dir != "" {
		r.problem(l.Target, fmt.Sprintf("%s is a directory link into the repository; run `sync.sh stow` to replace it with a real directory", dir))
		keepPrevious()
		return nil
	}
	info, err := os.Lstat(l.Target)
	switch {
	case errors.Is(err, fs.ErrNotExist):
		r.act("link", l.Target, l.Source)
		if err := r.mkdirParent(l.Target); err != nil {
			return err
		}
		if !r.dryRun {
			if err := os.Symlink(l.Source, l.Target); err != nil {
				return fmt.Errorf("link %s: %w", l.Target, err)
			}
		}
	case err != nil:
		return fmt.Errorf("inspect %s: %w", l.Target, err)
	case info.Mode()&fs.ModeSymlink != 0:
		dest, err := os.Readlink(l.Target)
		if err != nil {
			return fmt.Errorf("read link %s: %w", l.Target, err)
		}
		if dest == l.Source {
			break
		}
		if !r.inRepo(l.Target, dest) {
			r.problem(l.Target, fmt.Sprintf("a link to %s is in the way; remove it to let dotfiles manage this file", dest))
			keepPrevious()
			return nil
		}
		r.act("relink", l.Target, l.Source)
		if !r.dryRun {
			if err := replaceWithSymlink(l.Source, l.Target); err != nil {
				return err
			}
		}
	default:
		r.problem(l.Target, "a file is in the way; compare it with "+l.Source+", keep what you need, and move it aside")
		keepPrevious()
		return nil
	}
	r.next.Links[l.Target] = l.Source
	return nil
}

func (r *runner) copy(c plan.Copy) error {
	content, err := os.ReadFile(c.Source)
	if err != nil {
		return fmt.Errorf("read %s: %w", c.Source, err)
	}
	srcInfo, err := os.Stat(c.Source)
	if err != nil {
		return fmt.Errorf("inspect %s: %w", c.Source, err)
	}
	want := hash(content)
	prev, hadPrev := r.prev.Copies[c.Target]
	record := CopyRecord{Source: c.Source, SHA256: want}

	write := func(kind string) error {
		r.act(kind, c.Target, c.Source)
		if r.dryRun {
			return nil
		}
		if err := r.mkdirParent(c.Target); err != nil {
			return err
		}
		return writeAtomic(c.Target, content, srcInfo.Mode().Perm())
	}

	info, err := os.Lstat(c.Target)
	switch {
	case errors.Is(err, fs.ErrNotExist):
		if err := write("copy"); err != nil {
			return err
		}
	case err != nil:
		return fmt.Errorf("inspect %s: %w", c.Target, err)
	case info.Mode()&fs.ModeSymlink != 0:
		dest, err := os.Readlink(c.Target)
		if err != nil {
			return fmt.Errorf("read link %s: %w", c.Target, err)
		}
		if !r.inRepo(c.Target, dest) {
			r.problem(c.Target, fmt.Sprintf("a link to %s is in the way of a managed copy", dest))
			return nil
		}
		if err := write("copy"); err != nil {
			return err
		}
	case !info.Mode().IsRegular():
		r.problem(c.Target, "something other than a file is in the way of a managed copy")
		return nil
	default:
		existing, err := os.ReadFile(c.Target)
		if err != nil {
			return fmt.Errorf("read %s: %w", c.Target, err)
		}
		switch got := hash(existing); {
		case got == want:
		case hadPrev && got == prev.SHA256:
			// Unchanged since apply wrote it; the repository's version moved on.
			if err := write("update-copy"); err != nil {
				return err
			}
		default:
			r.problem(c.Target, "edited here since dotfiles last wrote it; keep this version with `dotfiles adopt "+c.Target+"`, or delete the file to take the repository's")
			if hadPrev {
				r.next.Copies[c.Target] = prev
			}
			return nil
		}
	}
	r.next.Copies[c.Target] = record
	return nil
}

func (r *runner) stub(s plan.Stub) error {
	line := s.Line + "\n"
	info, err := os.Lstat(s.Path)
	switch {
	case errors.Is(err, fs.ErrNotExist):
		r.act("stub", s.Path, s.Line)
		if !r.dryRun {
			if err := r.mkdirParent(s.Path); err != nil {
				return err
			}
			if err := writeAtomic(s.Path, []byte(line), 0o644); err != nil {
				return err
			}
		}
		r.next.Stubs[s.Path] = true
	case err != nil:
		return fmt.Errorf("inspect %s: %w", s.Path, err)
	case info.Mode()&fs.ModeSymlink != 0:
		dest, err := os.Readlink(s.Path)
		if err != nil {
			return fmt.Errorf("read link %s: %w", s.Path, err)
		}
		if !r.inRepo(s.Path, dest) {
			r.problem(s.Path, fmt.Sprintf("a link to %s is in the way of a local stub", dest))
			return nil
		}
		// The tracked file used to be linked here directly; the stub takes
		// its place, so installers that append write the local file.
		r.act("stub", s.Path, s.Line)
		if !r.dryRun {
			if err := writeAtomic(s.Path, []byte(line), 0o644); err != nil {
				return err
			}
		}
		r.next.Stubs[s.Path] = true
	default:
		content, err := os.ReadFile(s.Path)
		if err != nil {
			return fmt.Errorf("read %s: %w", s.Path, err)
		}
		if !bytes.Contains(content, []byte(s.Line)) {
			r.problem(s.Path, "add this line so it loads the shared configuration: "+s.Line)
			return nil
		}
		if r.prev.Stubs[s.Path] {
			r.next.Stubs[s.Path] = true
		}
	}
	return nil
}

// teardown removes what an earlier run installed for features no longer in
// the plan, when it is still exactly what apply left there.
func (r *runner) teardown(p *plan.Plan) error {
	want := map[string]bool{}
	for _, l := range p.Links {
		want[l.Target] = true
	}
	for _, c := range p.Copies {
		want[c.Target] = true
	}
	for _, f := range p.Generated {
		want[f.Path] = true
	}

	for _, target := range sortedKeys(r.prev.Links) {
		if want[target] {
			continue
		}
		if err := r.ctx.Err(); err != nil {
			return err
		}
		dest, err := os.Readlink(target)
		if err != nil || dest != r.prev.Links[target] {
			continue // gone, or replaced by the owner: no longer apply's
		}
		r.act("unlink", target, dest)
		if !r.dryRun {
			if err := os.Remove(target); err != nil {
				return fmt.Errorf("remove %s: %w", target, err)
			}
		}
	}
	for _, target := range sortedKeys(r.prev.Copies) {
		if want[target] {
			continue
		}
		content, err := os.ReadFile(target)
		if errors.Is(err, fs.ErrNotExist) {
			continue
		} else if err != nil {
			return fmt.Errorf("read %s: %w", target, err)
		}
		if hash(content) != r.prev.Copies[target].SHA256 {
			r.problem(target, "no longer managed, but edited since dotfiles wrote it, so it was left in place")
			continue
		}
		r.act("remove-copy", target, "")
		if !r.dryRun {
			if err := os.Remove(target); err != nil {
				return fmt.Errorf("remove %s: %w", target, err)
			}
		}
	}
	for _, path := range sortedKeys(r.prev.Generated) {
		if want[path] {
			continue
		}
		content, err := os.ReadFile(path)
		if err != nil || hash(content) != r.prev.Generated[path] {
			continue
		}
		r.act("remove", path, "")
		if !r.dryRun {
			if err := os.Remove(path); err != nil {
				return fmt.Errorf("remove %s: %w", path, err)
			}
		}
	}
	return nil
}

func hash(b []byte) string {
	sum := sha256.Sum256(b)
	return hex.EncodeToString(sum[:])
}

func sortedKeys[V any](m map[string]V) []string {
	keys := make([]string, 0, len(m))
	for k := range m {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	return keys
}

// writeAtomic writes data beside path and renames it into place, so a reader
// never sees a partial file and a crash leaves the old one.
func writeAtomic(path string, data []byte, mode fs.FileMode) error {
	tmp, err := os.CreateTemp(filepath.Dir(path), "."+filepath.Base(path)+".dotfiles-*")
	if err != nil {
		return fmt.Errorf("write %s: %w", path, err)
	}
	name := tmp.Name()
	defer os.Remove(name)
	if _, err := tmp.Write(data); err != nil {
		tmp.Close()
		return fmt.Errorf("write %s: %w", path, err)
	}
	if err := tmp.Chmod(mode); err != nil {
		tmp.Close()
		return fmt.Errorf("write %s: %w", path, err)
	}
	if err := tmp.Close(); err != nil {
		return fmt.Errorf("write %s: %w", path, err)
	}
	if err := os.Rename(name, path); err != nil {
		return fmt.Errorf("write %s: %w", path, err)
	}
	return nil
}

// replaceWithSymlink swaps whatever is at target for a link to source in one
// rename.
func replaceWithSymlink(source, target string) error {
	tmp := fmt.Sprintf("%s.dotfiles-link-%d", target, os.Getpid())
	_ = os.Remove(tmp)
	if err := os.Symlink(source, tmp); err != nil {
		return fmt.Errorf("link %s: %w", target, err)
	}
	if err := os.Rename(tmp, target); err != nil {
		_ = os.Remove(tmp)
		return fmt.Errorf("link %s: %w", target, err)
	}
	return nil
}
