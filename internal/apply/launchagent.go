package apply

import (
	"errors"
	"fmt"
	"io/fs"
	"os"

	"github.com/ashtonian/dotfiles/internal/atomicfile"
	"github.com/ashtonian/dotfiles/internal/launchd"
	"github.com/ashtonian/dotfiles/internal/plan"
)

// launchAgent installs a planned LaunchAgent's plist and has launchd run it:
// loaded when it is not, reloaded when launchd last loaded another definition
// of the job (a change to comments or layout only rewrites the file). A reload
// that would stop a job in the middle of a run waits for a later apply. A
// plist edited here since apply wrote it is a problem and stays.
func (r *runner) launchAgent(a plan.LaunchAgent) error {
	prev, hadPrev := r.prev.Agents[a.Label]
	keep := func() {
		if hadPrev {
			r.next.Agents[a.Label] = prev
		}
	}
	for _, path := range a.WhenExists {
		_, err := os.Stat(path)
		if errors.Is(err, fs.ErrNotExist) {
			// Left unrecorded, so teardownAgents removes what is installed.
			r.wait(a.Label, "installs once "+path+" exists")
			if !hadPrev {
				r.unrecorded[a.Label] = a.Target
			}
			return nil
		}
		if err != nil {
			r.problem(path, fmt.Sprintf("cannot tell whether it exists, which LaunchAgent %s waits for: %v", a.Label, err))
			keep()
			return nil
		}
	}

	want := hash(a.Content)
	pretend, err := r.prepare(a.Target)
	if err != nil {
		return err
	}
	info, err := os.Lstat(a.Target)
	if pretend {
		info, err = nil, fs.ErrNotExist
	}
	write := ""              // the action that writes the plist, if it needs writing
	loadedDef := prev.Loaded // the definition launchd runs, as far as apply knows
	switch {
	case errors.Is(err, fs.ErrNotExist):
		write = "agent"
	case err != nil:
		return fmt.Errorf("inspect %s: %w", a.Target, err)
	case !info.Mode().IsRegular():
		r.problem(a.Target, "something other than a file is in the way of LaunchAgent "+a.Label)
		keep()
		return nil
	default:
		existing, err := os.ReadFile(a.Target)
		if err != nil {
			return fmt.Errorf("read %s: %w", a.Target, err)
		}
		switch got := hash(existing); {
		case got == want:
		case hadPrev && got != prev.SHA256:
			r.problem(a.Target, "edited here since dotfiles last wrote it, so launchd keeps running this version; make the change in "+
				a.Source+" for every machine, or delete this file to take the template")
			keep()
			return nil
		default:
			// Unchanged since apply wrote it, or written by the retired
			// installer, which apply takes over: the template moved on.
			write = "update-agent"
		}
		if !hadPrev {
			// The retired installer loaded the plist it wrote here. One that
			// does not parse is reloaded from the template.
			loadedDef, _ = launchd.Definition(existing)
		}
	}

	state, err := r.env.Launchd.State(r.ctx, a.Label)
	if err != nil {
		r.problem(a.Target, err.Error())
		keep()
		return nil
	}
	launch, waitReason := "", "" // load or reload, or why a reload waits
	switch {
	case !state.Loaded:
		launch = "load"
	case loadedDef == a.Definition:
	case a.Label == r.env.Job:
		waitReason = "reloads when apply next runs outside this job, which it is running in"
	case state.Running && !a.KeepAlive:
		waitReason = "reloads once its current run ends"
	default:
		launch = "reload"
	}

	if write != "" {
		detail := a.Source
		if waitReason != "" {
			detail += "; it " + waitReason
		}
		r.act(write, a.Target, detail)
		if !r.dryRun {
			if err := r.mkdirParent(a.Target); err != nil {
				return err
			}
			if err := atomicfile.Write(a.Target, a.Content, 0o644); err != nil {
				return err
			}
		}
	}
	if waitReason != "" {
		r.wait(a.Label, waitReason)
	}
	if !r.dryRun {
		// launchd does not create the directories of a job's log files.
		for _, dir := range a.LogDirs {
			if err := os.MkdirAll(dir, 0o700); err != nil {
				return fmt.Errorf("create %s for LaunchAgent %s: %w", dir, a.Label, err)
			}
		}
	}

	record := AgentRecord{Path: a.Target, SHA256: want, Loaded: loadedDef}
	if launch != "" {
		r.act(launch, a.Target, "")
		if !r.dryRun {
			if err := r.relaunch(a, launch == "reload"); err != nil {
				r.problem(a.Target, err.Error())
				record.Loaded = "" // unknown, so the next run loads or reloads it
			} else {
				record.Loaded = a.Definition
			}
		}
	}
	r.next.Agents[a.Label] = record
	return nil
}

func (r *runner) relaunch(a plan.LaunchAgent, unload bool) error {
	if unload {
		if err := r.env.Launchd.Unload(r.ctx, a.Label); err != nil {
			return err
		}
	}
	return r.env.Launchd.Load(r.ctx, a.Target)
}

// teardownAgents unloads and removes the LaunchAgents this run does not keep:
// ones an earlier run installed whose feature is now off or whose condition
// no longer holds, and unrecorded ones the retired installer left at a label
// a feature declares. One edited since apply wrote it stays, loaded, and so
// does one in the middle of a run, until a later apply.
func (r *runner) teardownAgents() error {
	targets := map[string]string{}
	for label, rec := range r.prev.Agents {
		if _, kept := r.next.Agents[label]; !kept {
			targets[label] = rec.Path
		}
	}
	for label, target := range r.unrecorded {
		targets[label] = target
	}
	for _, label := range sortedKeys(targets) {
		if err := r.ctx.Err(); err != nil {
			return err
		}
		path := targets[label]
		rec, recorded := r.prev.Agents[label]
		keep := func() {
			if recorded {
				r.next.Agents[label] = rec
			}
		}
		content, err := os.ReadFile(path)
		exists := err == nil
		switch {
		case err != nil && !errors.Is(err, fs.ErrNotExist):
			return fmt.Errorf("read %s: %w", path, err)
		case !recorded && !exists:
			continue
		case recorded && exists && hash(content) != rec.SHA256:
			r.problem(path, "no longer managed, but edited since dotfiles wrote it, so it was left in place and loaded")
			continue
		}
		if label == r.env.Job {
			r.wait(label, "unloads when apply next runs outside this job, which it is running in")
			keep()
			continue
		}
		state, err := r.env.Launchd.State(r.ctx, label)
		if err != nil {
			r.problem(path, err.Error())
			keep()
			continue
		}
		if state.Running && !keepsAlive(content) {
			r.wait(label, "unloads once its current run ends")
			keep()
			continue
		}
		if state.Loaded {
			r.act("unload", path, "")
			if !r.dryRun {
				if err := r.env.Launchd.Unload(r.ctx, label); err != nil {
					r.problem(path, err.Error())
					keep()
					continue
				}
			}
		}
		if exists {
			r.act("remove-agent", path, "")
			if !r.dryRun {
				if err := os.Remove(path); err != nil {
					return fmt.Errorf("remove %s: %w", path, err)
				}
			}
		}
	}
	return nil
}

// keepsAlive reports whether an installed plist is a service launchd keeps
// running. One it cannot read counts as a job that exits on its own, which
// is only ever unloaded between runs.
func keepsAlive(content []byte) bool {
	job, err := launchd.Read(content)
	return err == nil && job.KeepAlive
}
