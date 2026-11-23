// Package apply converges a machine on a plan: it makes the planned links,
// managed copies, generated outputs, stubs and LaunchAgents, sets the planned
// app settings, and removes what an earlier run installed for features that
// are no longer enabled. It never overwrites a file it did not create, except
// a LaunchAgent plist at a label a feature declares, which the retired
// LaunchAgent installer wrote.
package apply

import (
	"bytes"
	"context"
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"fmt"
	"io/fs"
	"maps"
	"os"
	"path/filepath"
	"sort"
	"strings"

	"github.com/ashtonian/dotfiles/internal/atomicfile"
	"github.com/ashtonian/dotfiles/internal/launchd"
	"github.com/ashtonian/dotfiles/internal/plan"
)

// Root is a checkout the plan installs from: the dotfiles repository or an
// overlay. Links into it are apply's own, including stow's old ones.
type Root struct {
	Dir string
	// Tracked reports whether a path relative to Dir is tracked by git.
	// Unfolding moves only untracked files home: moving a tracked one would
	// delete it from the checkout on the next sync.
	Tracked func(rel string) bool
}

// Env is the machine apply works on.
type Env struct {
	Home  string
	Roots []Root
	// StowTree is the retired stow tree inside the repository, laid out as
	// <package>/<path under $HOME>. Files still in it after the migration are
	// untracked files a tool wrote, or that an older sync linked one by one;
	// apply moves each one that $HOME still links to home. Empty for none.
	StowTree string
	// Prefs holds a store for each name in prefs.Stores.
	Prefs map[string]PrefStore
	// Checkpoint durably saves a state the run has reached, as the state
	// file. apply calls it before it changes an app setting, with the
	// setting's earlier value recorded, so a run that stops before saving
	// its final state still knows what to put back. Required when the plan
	// has app settings and the run is not a dry run.
	Checkpoint func(*State) error
	// Launchd is the user's launchd GUI domain. Required when the plan or the
	// previous state has LaunchAgents.
	Launchd Launchd
	// Job is the label of the launchd job this run executes in
	// ($XPC_SERVICE_NAME), or empty. apply never unloads that job, which
	// would kill the run: it writes the new plist and leaves the reload to a
	// run outside the job.
	Job string
	// LeaveLaunchAgents skips LaunchAgents entirely: none is installed,
	// loaded or removed, and their records carry over. The installer applies
	// this way before it installs packages, so a job that runs at load does
	// not start in the middle of the install.
	LeaveLaunchAgents bool
}

// Launchd loads and unloads jobs in the user's launchd GUI domain.
type Launchd interface {
	State(ctx context.Context, label string) (launchd.State, error)
	// Load bootstraps the plist at path; launchd starts the job if its plist says to.
	Load(ctx context.Context, path string) error
	// Unload boots the job out, stopping it if it runs.
	Unload(ctx context.Context, label string) error
}

// Action is one change apply makes, or would make in a dry run.
type Action struct {
	Kind   string // link, relink, unlink, copy, update-copy, remove-copy, write, remove, stub, unfold, move-home, retire, pref, update-pref, restore-pref, forget-pref (Forget), adopt, agent, update-agent, load, reload, unload, remove-agent
	Path   string
	Detail string
}

// Problem is something apply refused to change; the owner has to decide.
type Problem struct {
	Path   string
	Detail string
}

// Waiting is a change apply leaves for a later run: a LaunchAgent's install
// until a path it needs exists, its reload or removal while that would stop
// the job in the middle of a run, a link held while a path that owns its
// place exists (link_unless_exists), or putting back an app setting while its
// app is not available.
type Waiting struct {
	Subject string // the LaunchAgent's label, the link's path, or the app setting's <store>:<key>
	Reason  string
}

// Report lists what a run did and what it left alone.
type Report struct {
	Actions  []Action
	Problems []Problem
	Waiting  []Waiting
}

// spelling is one way to write a root's directory: as given, or with
// symlinks resolved.
type spelling struct {
	dir  string
	root int // index into Env.Roots
}

// rootPath is a path inside one of the roots.
type rootPath struct {
	root int
	rel  string
}

type runner struct {
	ctx       context.Context
	env       Env
	spellings []spelling
	prev      *State
	next      *State
	dryRun    bool
	report    Report
	// sources holds every planned link and copy source; unfolding leaves them
	// in place even before they are tracked.
	sources  map[rootPath]bool
	unfolded map[string]bool // folded directories handled this run
	// unrecorded maps the labels of LaunchAgents to remove that apply has no
	// record of installing to their plists: the retired installer's.
	unrecorded map[string]string
}

// Run converges the machine on p. prev is the state the last run saved; the
// returned state is what to save now, also when Run fails: then it holds what
// the run did on top of prev. With dryRun nothing on disk changes and the
// report lists what would. I/O failures stop the run; conflicts are reported
// as problems and leave the file untouched.
func Run(ctx context.Context, p *plan.Plan, prev *State, env Env, dryRun bool) (*Report, *State, error) {
	if len(env.Roots) == 0 {
		return nil, nil, errors.New("apply: Env.Roots is required")
	}
	for _, root := range env.Roots {
		if root.Tracked == nil {
			return nil, nil, fmt.Errorf("apply: root %s needs Tracked", root.Dir)
		}
	}
	if env.Launchd == nil && !env.LeaveLaunchAgents && (len(p.LaunchAgents) > 0 || len(p.OffAgents) > 0 || len(prev.Agents) > 0) {
		return nil, nil, errors.New("apply: LaunchAgents need Env.Launchd, and launchd runs only on macOS")
	}
	if env.Checkpoint == nil && !dryRun && len(p.Prefs) > 0 {
		return nil, nil, errors.New("apply: app settings need Env.Checkpoint")
	}
	r := &runner{ctx: ctx, env: env, prev: prev, next: newState(), dryRun: dryRun,
		sources: map[rootPath]bool{}, unfolded: map[string]bool{}, unrecorded: map[string]string{}}
	for label, target := range p.OffAgents {
		if _, recorded := prev.Agents[label]; !recorded {
			r.unrecorded[label] = target
		}
	}
	for i, root := range env.Roots {
		given := filepath.Clean(root.Dir)
		r.spellings = append(r.spellings, spelling{dir: given, root: i})
		if resolved, err := filepath.EvalSymlinks(given); err == nil && resolved != given {
			r.spellings = append(r.spellings, spelling{dir: resolved, root: i})
		}
	}
	for _, l := range p.Links {
		if at, ok := r.locate(l.Source); ok {
			r.sources[at] = true
		}
	}
	for _, c := range p.Copies {
		if at, ok := r.locate(c.Source); ok {
			r.sources[at] = true
		}
	}

	agents, teardownAgents := func() error { return eachItem(r, p.LaunchAgents, r.launchAgent) }, r.teardownAgents
	if env.LeaveLaunchAgents {
		maps.Copy(r.next.Agents, prev.Agents)
		agents, teardownAgents = func() error { return nil }, func() error { return nil }
	}
	steps := []func() error{
		func() error { return eachItem(r, p.Generated, r.generated) },
		func() error { return eachItem(r, p.Links, r.link) },
		func() error { return eachItem(r, p.Copies, r.copy) },
		func() error { return eachItem(r, p.Stubs, r.stub) },
		// After the copies, so a setting can name a file a copy installs,
		// such as a theme.
		func() error { return eachItem(r, p.Prefs, r.pref) },
		func() error { return eachItem(r, p.Retire, r.retire) },
		r.rescueStowTree,
		agents,
		func() error { return r.teardown(p) },
		func() error { return r.teardownPrefs(p) },
		teardownAgents,
	}
	for _, step := range steps {
		if err := step(); err != nil {
			return &r.report, r.partial(), err
		}
	}
	return &r.report, r.next, nil
}

// partial is the state of a run that has not finished: what it recorded so
// far over what the last run saved. A record the run would have dropped is
// still there, and the next run looks at it again.
func (r *runner) partial() *State {
	s := r.prev.clone()
	s.overlay(r.next)
	return s
}

// checkpoint saves partial through Env.Checkpoint.
func (r *runner) checkpoint() error {
	if err := r.env.Checkpoint(r.partial()); err != nil {
		return fmt.Errorf("apply: saving the state before changing an app setting: %w", err)
	}
	return nil
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

func (r *runner) wait(subject, reason string) {
	r.report.Waiting = append(r.report.Waiting, Waiting{Subject: subject, Reason: reason})
}

// inRepo reports whether the symlink at link, whose destination is dest,
// points into one of the roots.
func (r *runner) inRepo(link, dest string) bool {
	if !filepath.IsAbs(dest) {
		dest = filepath.Join(filepath.Dir(link), dest)
	}
	dest = filepath.Clean(dest)
	for _, s := range r.spellings {
		if dest == s.dir || strings.HasPrefix(dest, s.dir+string(filepath.Separator)) {
			return true
		}
	}
	return false
}

// locate returns the root path is inside, under either spelling of the
// root's directory, and path relative to it.
func (r *runner) locate(path string) (rootPath, bool) {
	path = filepath.Clean(path)
	for _, s := range r.spellings {
		if strings.HasPrefix(path, s.dir+string(filepath.Separator)) {
			rel, err := filepath.Rel(s.dir, path)
			return rootPath{root: s.root, rel: rel}, err == nil
		}
	}
	return rootPath{}, false
}

// tracked reports whether git tracks the file at at.
func (r *runner) tracked(at rootPath) bool {
	return r.env.Roots[at.root].Tracked(at.rel)
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
		if at, ok := r.locate(path); ok && (r.sources[at] || r.tracked(at)) {
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
// root, root itself, and then its parents up to the checkout's root. Git does
// not track directories, so an empty one in a checkout is clutter.
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
		if _, inside := r.locate(dir); !inside || os.Remove(dir) != nil {
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
	if err := atomicfile.Write(to, data, info.Mode().Perm()); err != nil {
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
		if at, ok := r.locate(file); !found || (ok && r.tracked(at)) {
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
		if err := atomicfile.Write(f.Path, f.Content, 0o644); err != nil {
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
	// Checked before prepare, which may unfold a parent: a held link changes
	// nothing on disk.
	for _, path := range l.UnlessExists {
		_, err := os.Lstat(path)
		if errors.Is(err, fs.ErrNotExist) {
			continue
		}
		if err != nil {
			r.problem(path, fmt.Sprintf("cannot tell whether it exists, which holds %s back: %v", l.Target, err))
		} else {
			r.wait(l.Target, "left alone while "+path+" exists")
		}
		keepPrevious()
		return nil
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
		return atomicfile.Write(c.Target, content, srcInfo.Mode().Perm())
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
			if err := atomicfile.Write(s.Path, []byte(line), 0o644); err != nil {
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
			if err := atomicfile.Write(s.Path, []byte(line), 0o644); err != nil {
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
