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
	// Tracked reports whether a path relative to RepoRoot is tracked by git.
	// Unfolding moves only untracked files home: moving a tracked one would
	// delete it from the repository on the next sync.
	Tracked func(rel string) bool
	// StowTree is the retired stow tree inside the repository, laid out as
	// <package>/<path under $HOME>. Files still in it after the migration are
	// untracked files a tool wrote, or that an older sync linked one by one;
	// apply moves each one that $HOME still links to home. Empty for none.
	StowTree string
}

// Action is one change apply makes, or would make in a dry run.
type Action struct {
	Kind   string // link, relink, unlink, copy, update-copy, remove-copy, write, remove, stub, unfold, move-home, retire, adopt
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
	// sources holds every planned link and copy source, relative to the
	// repository; unfolding leaves them in place even before they are tracked.
	sources  map[string]bool
	unfolded map[string]bool // folded directories handled this run
}

// Run converges the machine on p. prev is the state the last run saved; the
// returned state is what to save now. With dryRun nothing on disk changes and
// the report lists what would. I/O failures stop the run; conflicts are
// reported as problems and leave the file untouched.
func Run(ctx context.Context, p *plan.Plan, prev *State, env Env, dryRun bool) (*Report, *State, error) {
	if env.Tracked == nil {
		return nil, nil, errors.New("apply: Env.Tracked is required")
	}
	r := &runner{ctx: ctx, env: env, prev: prev, next: newState(), dryRun: dryRun,
		sources: map[string]bool{}, unfolded: map[string]bool{}}
	r.repos = []string{filepath.Clean(env.RepoRoot)}
	if resolved, err := filepath.EvalSymlinks(env.RepoRoot); err == nil && resolved != r.repos[0] {
		r.repos = append(r.repos, resolved)
	}
	for _, l := range p.Links {
		if rel, ok := r.repoRel(l.Source); ok {
			r.sources[rel] = true
		}
	}
	for _, c := range p.Copies {
		if rel, ok := r.repoRel(c.Source); ok {
			r.sources[rel] = true
		}
	}

	steps := []func() error{
		func() error { return eachItem(r, p.Generated, r.generated) },
		func() error { return eachItem(r, p.Links, r.link) },
		func() error { return eachItem(r, p.Copies, r.copy) },
		func() error { return eachItem(r, p.Stubs, r.stub) },
		func() error { return eachItem(r, p.Retire, r.retire) },
		r.rescueStowTree,
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

// repoRel returns path relative to the repository, under either spelling of
// the repository root.
func (r *runner) repoRel(path string) (string, bool) {
	path = filepath.Clean(path)
	for _, repo := range r.repos {
		if strings.HasPrefix(path, repo+string(filepath.Separator)) {
			rel, err := filepath.Rel(repo, path)
			return rel, err == nil
		}
	}
	return "", false
}

// foldedParents returns the directories between $HOME and target that are
// links into the repository: old stow foldings, through which a write would
// land in the repository. The outermost comes first.
func (r *runner) foldedParents(target string) []string {
	home := filepath.Clean(r.env.Home)
	var folded []string
	for dir := filepath.Dir(target); dir != home && strings.HasPrefix(dir, home+string(filepath.Separator)); dir = filepath.Dir(dir) {
		info, err := os.Lstat(dir)
		if err != nil || info.Mode()&fs.ModeSymlink == 0 {
			continue
		}
		if dest, err := os.Readlink(dir); err == nil && r.inRepo(dir, dest) {
			folded = append([]string{dir}, folded...)
		}
	}
	return folded
}

// prepare makes sure nothing between $HOME and target is a folded directory
// link, so writing target cannot write into the repository. It reports
// whether target sits under a directory a dry run only pretended to unfold.
func (r *runner) prepare(target string) (pretend bool, err error) {
	for _, dir := range r.foldedParents(target) {
		if err := r.unfold(dir); err != nil {
			return false, err
		}
	}
	for dir := range r.unfolded {
		if r.dryRun && strings.HasPrefix(target, dir+string(filepath.Separator)) {
			return true, nil
		}
	}
	return false, nil
}

// unfold replaces a folded directory link with a real directory. Untracked
// files under the link's destination were written there by tools, through the
// link; they move to their place under the new directory instead of staying
// in the repository. Tracked files stay: the plan links the ones a feature
// installs.
func (r *runner) unfold(dir string) error {
	if r.unfolded[dir] {
		return nil
	}
	r.unfolded[dir] = true
	dest, err := os.Readlink(dir)
	if err != nil {
		return fmt.Errorf("read link %s: %w", dir, err)
	}
	if !filepath.IsAbs(dest) {
		dest = filepath.Join(filepath.Dir(dir), dest)
	}
	dest = filepath.Clean(dest)
	r.act("unfold", dir, dest)

	var local []string
	err = filepath.WalkDir(dest, func(path string, d fs.DirEntry, err error) error {
		if errors.Is(err, fs.ErrNotExist) && path == dest {
			return fs.SkipAll // a dangling link has nothing behind it
		}
		if err != nil {
			return err
		}
		if d.IsDir() {
			return nil
		}
		if rel, ok := r.repoRel(path); ok && (r.sources[rel] || r.env.Tracked(rel)) {
			return nil
		}
		rel, err := filepath.Rel(dest, path)
		if err != nil {
			return err
		}
		local = append(local, rel)
		return nil
	})
	if err != nil {
		return fmt.Errorf("list %s: %w", dest, err)
	}
	if r.dryRun {
		for _, rel := range local {
			r.act("move-home", filepath.Join(dir, rel), filepath.Join(dest, rel))
		}
		return nil
	}

	if len(local) == 0 {
		// Nothing to keep; the plan creates the directories it needs.
		if err := os.Remove(dir); err != nil {
			return fmt.Errorf("unfold %s: %w", dir, err)
		}
		return nil
	}
	// The files gather in a sibling first, so the link is replaced in one
	// rename. A crash in between leaves them in <dir>.dotfiles-unfold-<pid>.
	staging := fmt.Sprintf("%s.dotfiles-unfold-%d", dir, os.Getpid())
	if err := os.Mkdir(staging, 0o700); err != nil {
		return fmt.Errorf("unfold %s: %w", dir, err)
	}
	for _, rel := range local {
		from, to := filepath.Join(dest, rel), filepath.Join(staging, rel)
		if err := os.MkdirAll(filepath.Dir(to), 0o700); err != nil {
			return fmt.Errorf("unfold %s: %w", dir, err)
		}
		if err := move(from, to); err != nil {
			return fmt.Errorf("unfold %s: move %s: %w", dir, from, err)
		}
		r.act("move-home", filepath.Join(dir, rel), from)
	}
	if err := os.Remove(dir); err != nil {
		return fmt.Errorf("unfold %s: %w", dir, err)
	}
	if err := os.Rename(staging, dir); err != nil {
		return fmt.Errorf("unfold %s: %w", dir, err)
	}
	r.removeEmptyDirs(dest)
	return nil
}

// removeEmptyDirs removes the directories unfolding left empty: those under
// root, root itself, and then its parents up to the repository root. Git does
// not track directories, so an empty one in the repository is clutter.
func (r *runner) removeEmptyDirs(root string) {
	var dirs []string
	_ = filepath.WalkDir(root, func(path string, d fs.DirEntry, err error) error {
		if err == nil && d.IsDir() {
			dirs = append(dirs, path)
		}
		return nil
	})
	for i := len(dirs) - 1; i >= 0; i-- {
		_ = os.Remove(dirs[i]) // fails, as intended, unless the directory is empty
	}
	for dir := filepath.Dir(root); ; dir = filepath.Dir(dir) {
		if _, inside := r.repoRel(dir); !inside || os.Remove(dir) != nil {
			return
		}
	}
}

// move renames from to to, copying across file systems when it must.
func move(from, to string) error {
	if err := os.Rename(from, to); err == nil {
		return nil
	}
	info, err := os.Lstat(from)
	if err != nil {
		return err
	}
	if info.Mode()&fs.ModeSymlink != 0 {
		dest, err := os.Readlink(from)
		if err != nil {
			return err
		}
		if err := os.Symlink(dest, to); err != nil {
			return err
		}
		return os.Remove(from)
	}
	data, err := os.ReadFile(from)
	if err != nil {
		return err
	}
	if err := writeAtomic(to, data, info.Mode().Perm()); err != nil {
		return err
	}
	return os.Remove(from)
}

// retire removes an old install path that is still a link into the repository,
// or, when stow folded a directory above it, unfolds that directory first.
func (r *runner) retire(target string) error {
	pretend, err := r.prepare(target)
	if err != nil || pretend {
		return err
	}
	info, err := os.Lstat(target)
	if err != nil || info.Mode()&fs.ModeSymlink == 0 {
		return nil
	}
	dest, err := os.Readlink(target)
	if err != nil || !r.inRepo(target, dest) {
		return nil
	}
	r.act("retire", target, dest)
	if r.dryRun {
		return nil
	}
	if err := os.Remove(target); err != nil {
		return fmt.Errorf("remove %s: %w", target, err)
	}
	return nil
}

// rescueStowTree moves home each file left in the retired stow tree that
// $HOME links to, directly or through a folded parent directory, and reports
// the rest: nothing installs them any more, and they are the owner's data.
func (r *runner) rescueStowTree() error {
	root := r.env.StowTree
	if root == "" {
		return nil
	}
	if _, err := os.Lstat(root); errors.Is(err, fs.ErrNotExist) {
		return nil
	}
	var files []string
	err := filepath.WalkDir(root, func(path string, d fs.DirEntry, err error) error {
		if err != nil {
			return err
		}
		if !d.IsDir() {
			files = append(files, path)
		}
		return nil
	})
	if err != nil {
		return fmt.Errorf("list %s: %w", root, err)
	}
	for _, file := range files {
		if err := r.ctx.Err(); err != nil {
			return err
		}
		rel, err := filepath.Rel(root, file)
		if err != nil {
			return err
		}
		_, under, found := strings.Cut(filepath.ToSlash(rel), "/")
		if repoRel, ok := r.repoRel(file); !found || (ok && r.env.Tracked(repoRel)) {
			continue // a package's own README, or a file git still tracks
		}
		target := filepath.Join(r.env.Home, filepath.FromSlash(under))
		pretend, err := r.prepare(target)
		if err != nil {
			return err
		}
		if pretend {
			continue // a dry run's unfold already listed it
		}
		if _, err := os.Lstat(file); errors.Is(err, fs.ErrNotExist) {
			continue // unfolding moved it home
		}
		if dest, err := os.Readlink(target); err == nil && sameFile(target, dest, file) {
			r.act("move-home", target, file)
			if !r.dryRun {
				if err := moveOver(file, target); err != nil {
					return err
				}
			}
			continue
		}
		if filepath.Base(file) == ".DS_Store" {
			// Finder's view settings for a directory it showed; nothing to keep.
			r.act("remove", file, "")
			if !r.dryRun {
				if err := os.Remove(file); err != nil {
					return fmt.Errorf("remove %s: %w", file, err)
				}
			}
			continue
		}
		r.problem(file, "left in the retired stow tree and not installed any more; move it where it belongs, or delete it")
	}
	if !r.dryRun {
		r.removeEmptyDirs(root)
		_ = os.Remove(root)
	}
	return nil
}

// sameFile reports whether the link at link, whose destination is dest,
// points at file.
func sameFile(link, dest, file string) bool {
	if !filepath.IsAbs(dest) {
		dest = filepath.Join(filepath.Dir(link), dest)
	}
	return filepath.Clean(dest) == filepath.Clean(file)
}

// moveOver replaces the link at target with file, in one rename once the
// file is beside it.
func moveOver(file, target string) error {
	tmp := fmt.Sprintf("%s.dotfiles-home-%d", target, os.Getpid())
	if err := move(file, tmp); err != nil {
		return fmt.Errorf("move %s home: %w", file, err)
	}
	if err := os.Rename(tmp, target); err != nil {
		return fmt.Errorf("move %s home: %w", file, err)
	}
	return nil
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
	pretend, err := r.prepare(l.Target)
	if err != nil {
		return err
	}
	info, err := os.Lstat(l.Target)
	if pretend {
		info, err = nil, fs.ErrNotExist
	}
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

	pretend, err := r.prepare(c.Target)
	if err != nil {
		return err
	}

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
	if pretend {
		info, err = nil, fs.ErrNotExist
	}
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
	pretend, err := r.prepare(s.Path)
	if err != nil {
		return err
	}
	info, err := os.Lstat(s.Path)
	if pretend {
		info, err = nil, fs.ErrNotExist
	}
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
		if s.KeepExisting {
			break
		}
		content, err := os.ReadFile(s.Path)
		if err != nil {
			return fmt.Errorf("read %s: %w", s.Path, err)
		}
		if detail := stubProblem(content, s); detail != "" {
			r.problem(s.Path, detail)
			return nil
		}
	}
	if r.prev.Stubs[s.Path] {
		r.next.Stubs[s.Path] = true
	}
	return nil
}

// stubProblem says what an existing entry point needs so it loads the shared
// configuration, or "" when it has the stub's line, before any of the
// keywords the stub names.
func stubProblem(content []byte, s plan.Stub) string {
	where := ""
	if len(s.Before) > 0 {
		where = " before the first " + strings.Join(s.Before, " or ") + " line"
	}
	keyword := -1
	for i, line := range strings.Split(string(content), "\n") {
		line = strings.TrimSpace(line)
		if line == s.Line {
			if keyword >= 0 {
				return "move this line" + where + ", or it applies only inside that block: " + s.Line
			}
			return ""
		}
		if keyword < 0 && startsWithKeyword(line, s.Before) {
			keyword = i
		}
	}
	return "add this line" + where + " so it loads the shared configuration: " + s.Line
}

// startsWithKeyword reports whether line's first word is one of keywords,
// ignoring case as ssh_config does.
func startsWithKeyword(line string, keywords []string) bool {
	first, _, _ := strings.Cut(line, " ")
	first, _, _ = strings.Cut(first, "\t")
	for _, k := range keywords {
		if strings.EqualFold(first, k) {
			return true
		}
	}
	return false
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
