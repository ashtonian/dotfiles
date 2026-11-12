// Command dotfiles converges this machine on the features its profiles and
// machine manifest enable. See docs/MACHINE-FEATURES.md.
//
// Usage:
//
//	dotfiles init --profiles a,b [--force]  write this machine's manifest
//	dotfiles apply [--dry-run]              install, update and remove what the features say
//	dotfiles doctor                         report drift and conflicts without changing anything
//	dotfiles status [--json]                list every feature, whether it is enabled, and why
//	dotfiles check                          validate the manifests and plan this machine, reading nothing under $HOME
//	dotfiles adopt [flags] <path>...        make local edits to managed copies the repository's version
//
// Exit status: 0 done; 1 doctor or apply left problems for the owner; 2 the
// manifests are invalid or contradict each other, or the machine has none; 64
// usage, or adopt named a path that is not a managed copy; 70 an I/O failure.
package main

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"io"
	"os"
	"os/exec"
	"os/signal"
	"path/filepath"
	"runtime"
	"sort"
	"strings"
	"syscall"
	"text/tabwriter"
	"time"

	"github.com/ashtonian/dotfiles/internal/apply"
	"github.com/ashtonian/dotfiles/internal/manifest"
	"github.com/ashtonian/dotfiles/internal/plan"
	"github.com/ashtonian/dotfiles/internal/resolve"
)

// retiredStowTree is where the stow packages lived before the features; apply
// moves home what tools left in it (see apply.Env.StowTree).
const retiredStowTree = "stow"

const (
	exitOK       = 0
	exitProblems = 1
	exitManifest = 2
	exitUsage    = 64
	exitIO       = 70
)

func main() {
	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	code := run(ctx, os.Args[1:], os.Stdout, os.Stderr)
	stop()
	os.Exit(code)
}

// paths are the locations one run works with.
type paths struct {
	home, repo, machine, generated, state, lock string
	config                                      string // ~/.config
}

func run(ctx context.Context, args []string, stdout, stderr io.Writer) int {
	if len(args) == 0 {
		fmt.Fprintln(stderr, "usage: dotfiles init|apply|doctor|status|check|adopt [flags]")
		return exitUsage
	}
	cmd := args[0]
	home, err := os.UserHomeDir()
	if err != nil {
		fmt.Fprintln(stderr, "dotfiles: find home directory:", err)
		return exitIO
	}
	flags := flag.NewFlagSet("dotfiles "+cmd, flag.ContinueOnError)
	flags.SetOutput(stderr)
	homeDir := flags.String("home", home, "home directory to manage")
	repo := flags.String("repo", envOr("DOTFILES_DIR", filepath.Join(home, ".dotfiles")), "repository checkout")
	machine := flags.String("machine", "", "machine manifest (default <config>/dotfiles/machine.toml)")
	dryRun := flags.Bool("dry-run", false, "apply: report what would change without changing it")
	jsonOut := flags.Bool("json", false, "status: print JSON")
	lockWait := flags.Duration("lock-wait", time.Minute, "apply: how long to wait for another run to finish")
	profiles := flags.String("profiles", "", "init: comma-separated profiles, in order")
	force := flags.Bool("force", false, "init: replace an existing machine manifest")
	gitTimeout := flags.Duration("git-timeout", 30*time.Second, "apply: how long listing the repository's tracked files may take")
	if err := flags.Parse(args[1:]); err != nil {
		return exitUsage
	}
	if cmd != "adopt" && flags.NArg() > 0 {
		fmt.Fprintf(stderr, "dotfiles %s: unexpected arguments %v\n", cmd, flags.Args())
		return exitUsage
	}

	// Always ~/.config: the stubs and the shared git and ssh configs name it
	// literally, so XDG_CONFIG_HOME pointing elsewhere is reported, not followed.
	config := filepath.Join(*homeDir, ".config")
	stateHome := envOr("XDG_STATE_HOME", filepath.Join(*homeDir, ".local", "state"))
	p := paths{
		config:    config,
		home:      *homeDir,
		repo:      *repo,
		machine:   *machine,
		generated: filepath.Join(config, "dotfiles", "generated"),
		state:     filepath.Join(stateHome, "dotfiles", "applied.json"),
		lock:      filepath.Join(stateHome, "dotfiles", "apply.lock"),
	}
	if p.machine == "" {
		p.machine = filepath.Join(config, "dotfiles", "machine.toml")
	}

	switch cmd {
	case "init":
		return cmdInit(p, *profiles, *force, stdout, stderr)
	case "apply":
		return cmdApply(ctx, p, *dryRun, *lockWait, *gitTimeout, stdout, stderr)
	case "doctor":
		return cmdApply(ctx, p, true, *lockWait, *gitTimeout, stdout, stderr)
	case "status":
		return cmdStatus(p, *jsonOut, stdout, stderr)
	case "check":
		return cmdCheck(p, stdout, stderr)
	case "adopt":
		return cmdAdopt(ctx, p, flags.Args(), *lockWait, stdout, stderr)
	default:
		fmt.Fprintf(stderr, "dotfiles: unknown command %q; want init, apply, doctor, status, check or adopt\n", cmd)
		return exitUsage
	}
}

type loaded struct {
	features map[string]*manifest.Feature
	result   *resolve.Result
}

func load(p paths) (*loaded, error) {
	features, err := manifest.LoadFeatures(p.repo)
	if err != nil {
		return nil, err
	}
	profiles, err := manifest.LoadProfiles(p.repo)
	if err != nil {
		return nil, err
	}
	machine, err := manifest.LoadMachine(p.machine)
	if errors.Is(err, manifest.ErrNoMachine) {
		return nil, fmt.Errorf("%w; run `dotfiles init --profiles <names>` with profiles from %v", err, sortedKeys(profiles))
	}
	if err != nil {
		return nil, err
	}
	result, err := resolve.Resolve(features, profiles, machine, runtime.GOOS)
	if err != nil {
		return nil, err
	}
	return &loaded{features: features, result: result}, nil
}

// plan builds the desired state for this machine from what load resolved.
func (l *loaded) plan(p paths) (*plan.Plan, error) {
	return plan.Build(l.features, l.result.Runnable(l.features), l.result.Values(),
		plan.Env{Home: p.home, GeneratedDir: p.generated, GOOS: runtime.GOOS})
}

func exitFor(err error, stderr io.Writer) int {
	fmt.Fprintln(stderr, "dotfiles:", err)
	if errors.Is(err, apply.ErrNotCopy) {
		return exitUsage
	}
	if errors.Is(err, manifest.ErrInvalid) || errors.Is(err, manifest.ErrNoMachine) ||
		errors.Is(err, resolve.ErrConflict) || errors.Is(err, plan.ErrPlan) {
		return exitManifest
	}
	return exitIO
}

// cmdApply runs apply, or with dryRun the doctor check: the same plan, with
// nothing changed on disk.
func cmdApply(ctx context.Context, p paths, dryRun bool, lockWait, gitTimeout time.Duration, stdout, stderr io.Writer) int {
	l, err := load(p)
	if err != nil {
		return exitFor(err, stderr)
	}
	pl, err := l.plan(p)
	if err != nil {
		return exitFor(err, stderr)
	}

	if !dryRun {
		lockCtx, cancel := context.WithTimeout(ctx, lockWait)
		unlock, err := apply.Lock(lockCtx, p.lock)
		cancel()
		if err != nil {
			return exitFor(err, stderr)
		}
		defer unlock()
	}
	prev, err := apply.LoadState(p.state)
	if err != nil {
		return exitFor(err, stderr)
	}
	tracked, err := trackedFiles(ctx, p.repo, gitTimeout)
	if err != nil {
		return exitFor(err, stderr)
	}
	env := apply.Env{Home: p.home, RepoRoot: p.repo, StowTree: filepath.Join(p.repo, retiredStowTree),
		Tracked: func(rel string) bool { return tracked[filepath.ToSlash(rel)] }}
	report, next, err := apply.Run(ctx, pl, prev, env, dryRun)
	if err != nil {
		return exitFor(err, stderr)
	}
	if !dryRun {
		if err := next.Save(p.state); err != nil {
			return exitFor(err, stderr)
		}
	}

	verb := ""
	if dryRun {
		verb = "would "
	}
	for _, a := range report.Actions {
		fmt.Fprintf(stdout, "%s%-11s %s", verb, a.Kind, a.Path)
		if a.Detail != "" {
			fmt.Fprintf(stdout, " -> %s", a.Detail)
		}
		fmt.Fprintln(stdout)
	}
	problems := len(report.Problems)
	for _, pr := range report.Problems {
		fmt.Fprintf(stdout, "problem     %s: %s\n", pr.Path, pr.Detail)
	}
	for _, id := range sortedKeys(l.result.Missing) {
		problems++
		fmt.Fprintf(stdout, "problem     %s: skipped until these settings have values: %v\n", id, l.result.Missing[id])
	}
	if xdg := os.Getenv("XDG_CONFIG_HOME"); xdg != "" && filepath.Clean(xdg) != p.config {
		problems++
		fmt.Fprintf(stdout, "problem     XDG_CONFIG_HOME: it is %s, but dotfiles installs into %s, so git and zsh miss the shared configuration; unset it or set it to %s\n", xdg, p.config, p.config)
	}
	if dryRun && len(report.Actions) > 0 {
		// For doctor, pending changes are drift.
		problems += len(report.Actions)
	}
	if problems > 0 {
		return exitProblems
	}
	return exitOK
}

// cmdInit writes the machine manifest. It checks the profiles exist and that
// the features resolve with them, so a manifest it writes always loads.
func cmdInit(p paths, list string, force bool, stdout, stderr io.Writer) int {
	var names []string
	for _, n := range strings.Split(list, ",") {
		if n = strings.TrimSpace(n); n != "" {
			names = append(names, n)
		}
	}
	if len(names) == 0 {
		fmt.Fprintln(stderr, "dotfiles init: --profiles is required, such as --profiles base,dev")
		return exitUsage
	}
	if _, err := os.Lstat(p.machine); err == nil && !force {
		fmt.Fprintf(stderr, "dotfiles init: %s exists; edit it, or pass --force to replace it\n", p.machine)
		return exitUsage
	}
	features, err := manifest.LoadFeatures(p.repo)
	if err != nil {
		return exitFor(err, stderr)
	}
	profiles, err := manifest.LoadProfiles(p.repo)
	if err != nil {
		return exitFor(err, stderr)
	}
	if _, err := resolve.Resolve(features, profiles, &manifest.Machine{Profiles: names}, runtime.GOOS); err != nil {
		return exitFor(err, stderr)
	}
	if err := os.MkdirAll(filepath.Dir(p.machine), 0o700); err != nil {
		return exitFor(err, stderr)
	}
	tmp := p.machine + ".tmp"
	if err := os.WriteFile(tmp, manifest.MachineFile(names), 0o644); err != nil {
		return exitFor(err, stderr)
	}
	if err := os.Rename(tmp, p.machine); err != nil {
		_ = os.Remove(tmp)
		return exitFor(err, stderr)
	}
	fmt.Fprintf(stdout, "wrote %s with profiles %v; run `dotfiles apply`\n", p.machine, names)
	return exitOK
}

// cmdCheck loads the manifests and builds this machine's plan without reading
// or changing anything under $HOME. Sync runs an upstream checkout's own
// engine this way before merging it, so a merge never brings a layout this
// machine cannot install.
func cmdCheck(p paths, stdout, stderr io.Writer) int {
	l, err := load(p)
	if err != nil {
		return exitFor(err, stderr)
	}
	if _, err := l.plan(p); err != nil {
		return exitFor(err, stderr)
	}
	for _, id := range sortedKeys(l.result.Missing) {
		fmt.Fprintf(stdout, "note: %s is skipped until these settings have values: %v\n", id, l.result.Missing[id])
	}
	fmt.Fprintf(stdout, "ok: %d features plan for %s\n", len(l.result.Runnable(l.features)), p.machine)
	return exitOK
}

// cmdAdopt copies local edits of managed copies into the repository, under
// the same lock as apply, and records them so apply no longer reports drift.
func cmdAdopt(ctx context.Context, p paths, targets []string, lockWait time.Duration, stdout, stderr io.Writer) int {
	if len(targets) == 0 {
		fmt.Fprintln(stderr, "dotfiles adopt: name the managed copies to keep, such as ~/.config/htop/htoprc")
		return exitUsage
	}
	abs := make([]string, len(targets))
	for i, t := range targets {
		a, err := filepath.Abs(t)
		if err != nil {
			return exitFor(err, stderr)
		}
		abs[i] = a
	}
	l, err := load(p)
	if err != nil {
		return exitFor(err, stderr)
	}
	pl, err := l.plan(p)
	if err != nil {
		return exitFor(err, stderr)
	}
	lockCtx, cancel := context.WithTimeout(ctx, lockWait)
	unlock, err := apply.Lock(lockCtx, p.lock)
	cancel()
	if err != nil {
		return exitFor(err, stderr)
	}
	defer unlock()
	prev, err := apply.LoadState(p.state)
	if err != nil {
		return exitFor(err, stderr)
	}
	report, next, err := apply.Adopt(pl, prev, abs)
	if err != nil {
		return exitFor(err, stderr)
	}
	if err := next.Save(p.state); err != nil {
		return exitFor(err, stderr)
	}
	for _, a := range report.Actions {
		fmt.Fprintf(stdout, "%-11s %s -> %s\n", a.Kind, a.Path, a.Detail)
	}
	return exitOK
}

func cmdStatus(p paths, jsonOut bool, stdout, stderr io.Writer) int {
	l, err := load(p)
	if err != nil {
		return exitFor(err, stderr)
	}
	type row struct {
		ID      string `json:"id"`
		Enabled bool   `json:"enabled"`
		Source  string `json:"source"`
	}
	ids := sortedKeys(l.result.Decisions)
	rows := make([]row, 0, len(ids))
	for _, id := range ids {
		d := l.result.Decisions[id]
		rows = append(rows, row{ID: id, Enabled: d.Enabled, Source: d.Source})
	}
	if jsonOut {
		enc := json.NewEncoder(stdout)
		enc.SetIndent("", "  ")
		if err := enc.Encode(rows); err != nil {
			return exitFor(err, stderr)
		}
		return exitOK
	}
	w := tabwriter.NewWriter(stdout, 0, 4, 2, ' ', 0)
	fmt.Fprintln(w, "FEATURE\tENABLED\tDECIDED BY")
	for _, r := range rows {
		fmt.Fprintf(w, "%s\t%t\t%s\n", r.ID, r.Enabled, r.Source)
	}
	if err := w.Flush(); err != nil {
		return exitFor(err, stderr)
	}
	return exitOK
}

// trackedFiles lists the files git tracks in repo, slash-separated and
// relative to it.
func trackedFiles(ctx context.Context, repo string, timeout time.Duration) (map[string]bool, error) {
	ctx, cancel := context.WithTimeout(ctx, timeout)
	defer cancel()
	cmd := exec.CommandContext(ctx, "git", "-C", repo, "ls-files", "-z")
	var stderr bytes.Buffer
	cmd.Stderr = &stderr
	out, err := cmd.Output()
	if err != nil {
		return nil, fmt.Errorf("list tracked files in %s: %w: %s", repo, err, strings.TrimSpace(stderr.String()))
	}
	tracked := map[string]bool{}
	for _, name := range strings.Split(string(out), "\x00") {
		if name != "" {
			tracked[name] = true
		}
	}
	return tracked, nil
}

func envOr(name, fallback string) string {
	if v := os.Getenv(name); v != "" {
		return v
	}
	return fallback
}

func sortedKeys[V any](m map[string]V) []string {
	keys := make([]string, 0, len(m))
	for k := range m {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	return keys
}
