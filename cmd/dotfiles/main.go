// Command dotfiles converges this machine on the features its profiles and
// machine manifest enable. See docs/MACHINE-FEATURES.md.
//
// Usage:
//
//	dotfiles init --profiles a,b [--force]  write this machine's manifest
//	dotfiles apply [--dry-run]              install, update and remove what the features say,
//	                                        LaunchAgents included
//	dotfiles doctor                         report drift and conflicts without changing anything,
//	                                        and the LaunchAgents waiting for a later run
//	dotfiles status [--json]                list every feature, whether it is enabled, and why
//	dotfiles check                          validate the manifests and plan this machine, reading nothing under $HOME
//	dotfiles adopt [flags] <target>...      make local edits to managed copies (a path) or app
//	                                        settings (<store>:<key>) the repository's version
//
// Exit status: 0 done; 1 doctor or apply left problems for the owner; 2 the
// manifests are invalid or contradict each other, or the machine has none; 64
// usage, or adopt named something that is not a managed copy or app setting;
// 70 an I/O failure.
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
	"slices"
	"sort"
	"strings"
	"syscall"
	"text/tabwriter"
	"time"

	"github.com/ashtonian/dotfiles/internal/apply"
	"github.com/ashtonian/dotfiles/internal/launchd"
	"github.com/ashtonian/dotfiles/internal/manifest"
	"github.com/ashtonian/dotfiles/internal/plan"
	"github.com/ashtonian/dotfiles/internal/prefs"
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
	overlays                                    string // holds one checkout per overlay, named for it
}

// applyOptions are apply's and doctor's limits and their launchd domain.
type applyOptions struct {
	dryRun               bool
	lockWait, gitTimeout time.Duration
	launchctl            string
	launchctlTimeout     time.Duration
	launchAgents         bool
	stores               map[string]apply.PrefStore
}

// prefStores builds the store for each app in prefs.Stores.
func prefStores(home, muxyApp string, appTimeout time.Duration) map[string]apply.PrefStore {
	return map[string]apply.PrefStore{
		"claude": prefs.NewClaude(home),
		"muxy":   prefs.NewMuxy(prefs.MuxyCommands(home, muxyApp), appTimeout),
	}
}

func run(ctx context.Context, args []string, stdout, stderr io.Writer) int {
	if len(args) == 0 {
		fmt.Fprintln(stderr, "usage: dotfiles init|apply|doctor|status|check|overlays|adopt|forget [flags]")
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
	overlayDir := flags.String("overlay-dir", envOr("DOTFILES_OVERLAY_DIR", filepath.Join(home, ".dotfiles-overlays")), "directory holding one checkout per overlay, named for it")
	machine := flags.String("machine", "", "machine manifest (default <config>/dotfiles/machine.toml)")
	dryRun := flags.Bool("dry-run", false, "apply: report what would change without changing it")
	jsonOut := flags.Bool("json", false, "status: print JSON")
	lockWait := flags.Duration("lock-wait", time.Minute, "apply: how long to wait for another run to finish")
	profiles := flags.String("profiles", "", "init: comma-separated profiles, in order")
	overlays := flags.String("overlays", "", "init: comma-separated overlays this machine belongs to")
	force := flags.Bool("force", false, "init: replace an existing machine manifest")
	gitTimeout := flags.Duration("git-timeout", 30*time.Second, "apply: how long listing the repository's tracked files may take")
	launchctlTimeout := flags.Duration("launchctl-timeout", 30*time.Second, "apply: how long one launchctl call may take")
	launchAgents := flags.Bool("launch-agents", true, "apply: install, load and remove LaunchAgents; false leaves them as they are")
	appTimeout := flags.Duration("app-timeout", 15*time.Second, "apply, doctor, adopt: how long one call to an app's settings command may take")
	if err := flags.Parse(args[1:]); err != nil {
		return exitUsage
	}
	if cmd != "adopt" && cmd != "forget" && flags.NArg() > 0 {
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
		overlays:  *overlayDir,
		machine:   *machine,
		generated: filepath.Join(config, "dotfiles", "generated"),
		state:     filepath.Join(stateHome, "dotfiles", "applied.json"),
		lock:      filepath.Join(stateHome, "dotfiles", "apply.lock"),
	}
	if p.machine == "" {
		p.machine = filepath.Join(config, "dotfiles", "machine.toml")
	}

	stores := prefStores(p.home, os.Getenv("DOTFILES_MUXY_APP"), *appTimeout)
	opts := applyOptions{dryRun: *dryRun, lockWait: *lockWait, gitTimeout: *gitTimeout,
		launchctl: envOr("DOTFILES_LAUNCHCTL", "/bin/launchctl"), launchctlTimeout: *launchctlTimeout, launchAgents: *launchAgents,
		stores: stores}
	switch cmd {
	case "init":
		return cmdInit(p, *overlays, *profiles, *force, stdout, stderr)
	case "apply":
		return cmdApply(ctx, p, opts, false, stdout, stderr)
	case "doctor":
		opts.dryRun = true
		return cmdApply(ctx, p, opts, true, stdout, stderr)
	case "status":
		return cmdStatus(ctx, p, *jsonOut, *gitTimeout, stdout, stderr)
	case "check":
		return cmdCheck(p, stdout, stderr)
	case "overlays":
		return cmdOverlays(p, stdout, stderr)
	case "adopt":
		return cmdAdopt(ctx, p, stores, flags.Args(), *lockWait, stdout, stderr)
	case "forget":
		return cmdForget(ctx, p, flags.Args(), *lockWait, stdout, stderr)
	default:
		fmt.Fprintf(stderr, "dotfiles: unknown command %q; want init, apply, doctor, status, check, overlays, adopt or forget\n", cmd)
		return exitUsage
	}
}

type loaded struct {
	roots    []manifest.Root // the repository first, then the machine's overlays
	features map[string]*manifest.Feature
	result   *resolve.Result
}

// roots returns the repository's root followed by the named overlays'.
func (p paths) roots(overlays []string) ([]manifest.Root, error) {
	extra, err := manifest.OverlayRoots(p.overlays, overlays)
	if err != nil {
		return nil, err
	}
	return append([]manifest.Root{{Dir: p.repo}}, extra...), nil
}

func load(p paths) (*loaded, error) {
	machine, err := manifest.LoadMachine(p.machine)
	if errors.Is(err, manifest.ErrNoMachine) {
		profiles, perr := manifest.LoadProfiles(manifest.Root{Dir: p.repo})
		if perr != nil {
			return nil, perr
		}
		return nil, fmt.Errorf("%w; run `dotfiles init --profiles <names>` with profiles from %v", err, sortedKeys(profiles))
	}
	if err != nil {
		return nil, err
	}
	roots, err := p.roots(machine.Overlays)
	if err != nil {
		return nil, err
	}
	features, err := manifest.LoadFeatures(roots...)
	if err != nil {
		return nil, err
	}
	profiles, err := manifest.LoadProfiles(roots...)
	if err != nil {
		return nil, err
	}
	result, err := resolve.Resolve(features, profiles, machine, runtime.GOOS)
	if err != nil {
		return nil, err
	}
	return &loaded{roots: roots, features: features, result: result}, nil
}

// plan builds the desired state for this machine from what load resolved.
func (l *loaded) plan(p paths) (*plan.Plan, error) {
	return plan.Build(l.features, l.result.Runnable(l.features), l.result.Values(), l.result.PrefLayers,
		plan.Env{Home: p.home, GeneratedDir: p.generated, GOOS: runtime.GOOS})
}

func exitFor(err error, stderr io.Writer) int {
	fmt.Fprintln(stderr, "dotfiles:", err)
	if errors.Is(err, apply.ErrNotManaged) || errors.Is(err, apply.ErrNotForgettable) {
		return exitUsage
	}
	if errors.Is(err, manifest.ErrInvalid) || errors.Is(err, manifest.ErrNoMachine) || errors.Is(err, manifest.ErrNoOverlay) ||
		errors.Is(err, resolve.ErrConflict) || errors.Is(err, plan.ErrPlan) {
		return exitManifest
	}
	return exitIO
}

// cmdApply runs apply, or with dryRun the doctor check: the same plan, with
// nothing changed on disk. The doctor also lists the LaunchAgents waiting for
// a later run.
func cmdApply(ctx context.Context, p paths, opts applyOptions, doctor bool, stdout, stderr io.Writer) int {
	dryRun := opts.dryRun
	l, err := load(p)
	if err != nil {
		return exitFor(err, stderr)
	}
	pl, err := l.plan(p)
	if err != nil {
		return exitFor(err, stderr)
	}

	if !dryRun {
		lockCtx, cancel := context.WithTimeout(ctx, opts.lockWait)
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
	env := apply.Env{Home: p.home, StowTree: filepath.Join(p.repo, retiredStowTree), Prefs: opts.stores,
		Checkpoint: func(s *apply.State) error { return s.Save(p.state) }}
	for _, root := range l.roots {
		tracked, err := trackedFiles(ctx, root.Dir, opts.gitTimeout)
		if err != nil {
			return exitFor(err, stderr)
		}
		env.Roots = append(env.Roots, apply.Root{Dir: root.Dir,
			Tracked: func(rel string) bool { return tracked[filepath.ToSlash(rel)] }})
	}
	env.LeaveLaunchAgents = !opts.launchAgents
	if runtime.GOOS == "darwin" && opts.launchAgents {
		env.Launchd = launchd.New(opts.launchctl, os.Getuid(), opts.launchctlTimeout)
		// launchd names the job a process runs in; a terminal's is no LaunchAgent's label.
		env.Job = os.Getenv("XPC_SERVICE_NAME")
	}
	report, next, err := apply.Run(ctx, pl, prev, env, dryRun)
	// A run that fails partway still returns what it did, which the next
	// run needs: an app setting's earlier value, a link it made.
	if !dryRun && next != nil {
		if saveErr := next.Save(p.state); saveErr != nil {
			return exitFor(errors.Join(err, saveErr), stderr)
		}
	}
	if err != nil {
		return exitFor(err, stderr)
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
	if doctor {
		// Expected states, not problems; apply prints them only as it acts.
		for _, w := range report.Waiting {
			fmt.Fprintf(stdout, "waiting     %s: %s\n", w.Subject, w.Reason)
		}
		for _, pr := range pl.Prefs {
			fmt.Fprintf(stdout, "app-setting %s\n", describePref(pr))
		}
		for _, ig := range pl.IgnoredPrefs {
			fmt.Fprintf(stdout, "ignored     %s\n", describeIgnored(ig))
		}
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

// splitList returns the non-empty, trimmed items of a comma-separated list.
func splitList(list string) []string {
	var items []string
	for _, item := range strings.Split(list, ",") {
		if item = strings.TrimSpace(item); item != "" {
			items = append(items, item)
		}
	}
	return items
}

// cmdInit writes the machine manifest. It checks the overlays are cloned, the
// profiles exist, and the features resolve with them, so a manifest it writes
// always loads.
func cmdInit(p paths, overlayList, list string, force bool, stdout, stderr io.Writer) int {
	names := splitList(list)
	overlays := splitList(overlayList)
	if len(names) == 0 {
		fmt.Fprintln(stderr, "dotfiles init: --profiles is required, such as --profiles base,dev")
		return exitUsage
	}
	if _, err := os.Lstat(p.machine); err == nil && !force {
		fmt.Fprintf(stderr, "dotfiles init: %s exists; edit it, or pass --force to replace it\n", p.machine)
		return exitUsage
	}
	roots, err := p.roots(overlays)
	if err != nil {
		return exitFor(err, stderr)
	}
	features, err := manifest.LoadFeatures(roots...)
	if err != nil {
		return exitFor(err, stderr)
	}
	profiles, err := manifest.LoadProfiles(roots...)
	if err != nil {
		return exitFor(err, stderr)
	}
	if _, err := resolve.Resolve(features, profiles, &manifest.Machine{Overlays: overlays, Profiles: names}, runtime.GOOS); err != nil {
		return exitFor(err, stderr)
	}
	if err := os.MkdirAll(filepath.Dir(p.machine), 0o700); err != nil {
		return exitFor(err, stderr)
	}
	tmp := p.machine + ".tmp"
	if err := os.WriteFile(tmp, manifest.MachineFile(overlays, names), 0o644); err != nil {
		return exitFor(err, stderr)
	}
	if err := os.Rename(tmp, p.machine); err != nil {
		_ = os.Remove(tmp)
		return exitFor(err, stderr)
	}
	fmt.Fprintf(stdout, "wrote %s with overlays %v and profiles %v; run `dotfiles apply`\n", p.machine, overlays, names)
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
	pl, err := l.plan(p)
	if err != nil {
		return exitFor(err, stderr)
	}
	for _, id := range sortedKeys(l.result.Missing) {
		fmt.Fprintf(stdout, "note: %s is skipped until these settings have values: %v\n", id, l.result.Missing[id])
	}
	for _, root := range l.roots[1:] {
		fmt.Fprintf(stdout, "overlay: %s at %s\n", root.Overlay, root.Dir)
	}
	for _, pr := range pl.Prefs {
		fmt.Fprintf(stdout, "app setting: %s\n", describePref(pr))
	}
	for _, ig := range pl.IgnoredPrefs {
		fmt.Fprintf(stdout, "note: %s\n", describeIgnored(ig))
	}
	fmt.Fprintf(stdout, "ok: %d features plan for %s\n", len(l.result.Runnable(l.features)), p.machine)
	return exitOK
}

// cmdOverlays prints the checkout directory of each overlay the machine
// manifest lists, one per line, cloned or not. sync.sh syncs them before
// apply reads them.
func cmdOverlays(p paths, stdout, stderr io.Writer) int {
	machine, err := manifest.LoadMachine(p.machine)
	if err != nil {
		return exitFor(err, stderr)
	}
	for _, name := range machine.Overlays {
		fmt.Fprintln(stdout, filepath.Join(p.overlays, name))
	}
	return exitOK
}

// cmdForget drops the records of app settings waiting to be put back for an
// app that is gone for good, under the same lock as apply, printing each
// earlier value.
func cmdForget(ctx context.Context, p paths, ids []string, lockWait time.Duration, stdout, stderr io.Writer) int {
	if len(ids) == 0 {
		fmt.Fprintln(stderr, "dotfiles forget: name the app settings to forget, such as muxy:appearance.dark_theme")
		return exitUsage
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
	report, next, err := apply.Forget(pl, prev, ids)
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

// cmdAdopt copies local edits of managed copies and app settings into the
// repository, under the same lock as apply, and records them so apply no
// longer reports drift.
func cmdAdopt(ctx context.Context, p paths, stores map[string]apply.PrefStore, targets []string, lockWait time.Duration, stdout, stderr io.Writer) int {
	if len(targets) == 0 {
		fmt.Fprintln(stderr, "dotfiles adopt: name the managed copies or app settings to keep, such as ~/.config/htop/htoprc or muxy:appearance.dark_theme")
		return exitUsage
	}
	resolved := make([]string, len(targets))
	for i, t := range targets {
		if store, _, ok := strings.Cut(t, ":"); ok && slices.Contains(prefs.Stores, store) {
			resolved[i] = t // an app setting, <store>:<key>
			continue
		}
		a, err := filepath.Abs(t)
		if err != nil {
			return exitFor(err, stderr)
		}
		resolved[i] = a
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
	report, next, err := apply.Adopt(ctx, pl, prev, resolved, stores)
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

// cmdStatus prints each root's commit and whether it has uncommitted
// changes, then every feature's decision and the layer that made it.
func cmdStatus(ctx context.Context, p paths, jsonOut bool, gitTimeout time.Duration, stdout, stderr io.Writer) int {
	l, err := load(p)
	if err != nil {
		return exitFor(err, stderr)
	}
	// A plan error is reported after the rest, which still helps find it.
	pl, planErr := l.plan(p)
	type rootRow struct {
		Name   string `json:"name"`
		Dir    string `json:"dir"`
		Commit string `json:"commit,omitempty"`
		Dirty  bool   `json:"dirty"`
		Error  string `json:"error,omitempty"`
	}
	type featureRow struct {
		ID      string `json:"id"`
		Enabled bool   `json:"enabled"`
		Source  string `json:"source"`
	}
	type prefRow struct {
		ID    string `json:"id"`
		Value any    `json:"value"`
		// SetBy is the feature that owns the setting, or "profile:<name>" or
		// "machine" when an override sets it.
		SetBy   string `json:"set_by"`
		Feature string `json:"feature"`
		Shared  any    `json:"shared"` // the feature's own value
	}
	var out struct {
		Roots    []rootRow    `json:"roots"`
		Features []featureRow `json:"features"`
		Prefs    []prefRow    `json:"prefs"`
	}
	for _, root := range l.roots {
		row := rootRow{Name: root.Overlay, Dir: root.Dir}
		if row.Name == "" {
			row.Name = "repository"
		}
		row.Commit, row.Dirty, err = gitState(ctx, root.Dir, gitTimeout)
		if err != nil {
			row.Error = err.Error()
		}
		out.Roots = append(out.Roots, row)
	}
	for _, id := range sortedKeys(l.result.Decisions) {
		d := l.result.Decisions[id]
		out.Features = append(out.Features, featureRow{ID: id, Enabled: d.Enabled, Source: d.Source})
	}
	if planErr == nil {
		for _, pr := range pl.Prefs {
			out.Prefs = append(out.Prefs, prefRow{ID: pr.ID(), Value: pr.Value, SetBy: pr.SetBy(), Feature: pr.Feature, Shared: pr.Shared})
		}
	}
	if jsonOut {
		enc := json.NewEncoder(stdout)
		enc.SetIndent("", "  ")
		if err := enc.Encode(out); err != nil {
			return exitFor(err, stderr)
		}
		if planErr != nil {
			return exitFor(planErr, stderr)
		}
		return exitOK
	}
	w := tabwriter.NewWriter(stdout, 0, 4, 2, ' ', 0)
	fmt.Fprintln(w, "ROOT\tCOMMIT\tUNCOMMITTED\tDIRECTORY")
	for _, r := range out.Roots {
		commit := r.Commit
		if r.Error != "" {
			commit = "unknown: " + r.Error
		}
		fmt.Fprintf(w, "%s\t%s\t%t\t%s\n", r.Name, commit, r.Dirty, r.Dir)
	}
	fmt.Fprintln(w)
	fmt.Fprintln(w, "FEATURE\tENABLED\tDECIDED BY")
	for _, r := range out.Features {
		fmt.Fprintf(w, "%s\t%t\t%s\n", r.ID, r.Enabled, r.Source)
	}
	if len(out.Prefs) > 0 {
		fmt.Fprintln(w)
		fmt.Fprintln(w, "APP SETTING\tVALUE\tSET BY")
		for _, pr := range pl.Prefs {
			setBy := pr.SetBy()
			if pr.Origin != "" {
				setBy += fmt.Sprintf(" (%s shares %s)", pr.Feature, tomlValue(pr.Shared))
			}
			fmt.Fprintf(w, "%s\t%s\t%s\n", pr.ID(), tomlValue(pr.Value), setBy)
		}
	}
	if err := w.Flush(); err != nil {
		return exitFor(err, stderr)
	}
	if planErr != nil {
		return exitFor(planErr, stderr)
	}
	return exitOK
}

// describePref says what value an app setting gets here and where it comes
// from: the feature that owns it, or the profile or machine manifest whose
// [prefs] table overrides the feature's value.
func describePref(pr plan.Pref) string {
	d := fmt.Sprintf("%s = %s, from %s", pr.ID(), tomlValue(pr.Value), pr.SetBy())
	if pr.Origin != "" {
		d += fmt.Sprintf(" (%s shares %s)", pr.Feature, tomlValue(pr.Shared))
	}
	return d
}

// describeIgnored says why a machine manifest override changes nothing here.
func describeIgnored(ig plan.IgnoredPref) string {
	return fmt.Sprintf("%s: %s [prefs] sets it, but %s, which owns it, is off here, so it is ignored", ig.ID, ig.File, ig.Feature)
}

// tomlValue renders a setting value as a prefs file or [prefs] table writes it.
func tomlValue(v any) string {
	s, err := prefs.EncodeTOML(v)
	if err != nil {
		return fmt.Sprint(v)
	}
	return s
}

// gitState returns the checkout's short commit and whether a tracked file has
// uncommitted changes.
func gitState(ctx context.Context, dir string, timeout time.Duration) (commit string, dirty bool, err error) {
	ctx, cancel := context.WithTimeout(ctx, timeout)
	defer cancel()
	git := func(args ...string) (string, error) {
		cmd := exec.CommandContext(ctx, "git", append([]string{"-C", dir}, args...)...)
		var stderr bytes.Buffer
		cmd.Stderr = &stderr
		out, err := cmd.Output()
		if err != nil {
			return "", fmt.Errorf("git %s in %s: %w: %s", args[0], dir, err, strings.TrimSpace(stderr.String()))
		}
		return strings.TrimSpace(string(out)), nil
	}
	if commit, err = git("rev-parse", "--short", "HEAD"); err != nil {
		return "", false, err
	}
	changes, err := git("status", "--porcelain", "--untracked-files=no")
	if err != nil {
		return commit, false, err
	}
	return commit, changes != "", nil
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
