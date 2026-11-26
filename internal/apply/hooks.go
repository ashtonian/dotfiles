package apply

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os"
	"os/exec"
	"slices"
	"strings"
	"time"

	"github.com/ashtonian/dotfiles/internal/plan"
)

// checkOutputLimit bounds what apply reads of a check's standard output; the
// one JSON object a check prints is far smaller.
const checkOutputLimit = 64 << 10

// hookWaitDelay bounds how long apply waits for a hook's output to close
// after the hook exits or is killed, when a child it started holds it open.
const hookWaitDelay = 5 * time.Second

// checkStates are the states a check reports; see manifest.Check.
var checkStates = []string{"ok", "drift", "missing", "error"}

type checkResult struct {
	State  string `json:"state"`
	Detail string `json:"detail"`
}

func (c checkResult) String() string {
	if c.Detail == "" {
		return c.State
	}
	return c.State + ": " + c.Detail
}

// hook records h's teardown hook and runs its check. While the check reports
// anything but ok, the apply hook runs and the check runs again to confirm
// it; a sudo hook outside `apply --sudo` is reported instead. A hook or check
// that fails is a problem for the owner, never the end of the run.
func (r *runner) hook(h plan.Hook) error {
	if h.Teardown != "" {
		script, err := os.ReadFile(h.Teardown)
		if err != nil {
			return fmt.Errorf("apply: reading %s's teardown hook: %w", h.Feature, err)
		}
		r.next.Teardowns[h.Feature] = TeardownRecord{Script: script, Sudo: h.Sudo,
			TimeoutSeconds: int64(h.Timeout / time.Second), Env: h.Env}
	}
	if h.Check == "" {
		return nil
	}
	before, err := r.check(h)
	if err != nil {
		return r.hookFailed(h.Feature, err)
	}
	if before.State == "ok" {
		return nil
	}
	switch {
	case h.Apply == "":
		r.problem(h.Feature, before.String())
	case h.Sudo && !r.env.Sudo:
		r.problem(h.Feature, before.String()+"; run `dotfiles apply --sudo`")
	case r.dryRun:
		r.act("hook", h.Feature, before.String())
	default:
		if err := r.runScript(h.Feature, "hooks.apply", h.Apply, h.Env, h.Timeout, h.Sudo, nil); err != nil {
			return r.hookFailed(h.Feature, err)
		}
		after, err := r.check(h)
		if err != nil {
			return r.hookFailed(h.Feature, err)
		}
		if after.State != "ok" {
			r.problem(h.Feature, "hooks.apply ran, and the check still reports "+after.String())
			return nil
		}
		r.act("hook", h.Feature, before.String())
	}
	return nil
}

// teardownHooks runs the recorded teardown of each feature that is no longer
// enabled. A teardown that fails, or that needs `apply --sudo`, keeps its
// record, so a later run tries again.
func (r *runner) teardownHooks(p *plan.Plan) error {
	for _, id := range sortedKeys(r.prev.Teardowns) {
		if slices.Contains(p.Enabled, id) {
			continue // hook recorded its current teardown, if it still has one
		}
		rec := r.prev.Teardowns[id]
		switch {
		case rec.Sudo && !r.env.Sudo:
			r.next.Teardowns[id] = rec
			r.problem(id, "turned off, and its teardown needs administrator rights; run `dotfiles apply --sudo`")
		case r.dryRun:
			r.act("teardown", id, "hooks.teardown")
		default:
			if err := r.runTeardown(id, rec); err != nil {
				if ctxErr := r.ctx.Err(); ctxErr != nil {
					return ctxErr
				}
				r.next.Teardowns[id] = rec
				r.problem(id, fmt.Sprintf("turned off, and %v; the next apply runs it again", err))
				continue
			}
			r.act("teardown", id, "hooks.teardown")
		}
	}
	return nil
}

// hookFailed reports err as a problem of feature, unless the run itself was
// cancelled, which ends it.
func (r *runner) hookFailed(feature string, err error) error {
	if ctxErr := r.ctx.Err(); ctxErr != nil {
		return ctxErr
	}
	r.problem(feature, err.Error())
	return nil
}

// check runs h's check script and decodes the state it reports.
func (r *runner) check(h plan.Hook) (checkResult, error) {
	out := &cappedBuffer{limit: checkOutputLimit}
	if err := r.runScript(h.Feature, "check.script", h.Check, h.Env, h.CheckTimeout, false, out); err != nil {
		return checkResult{}, err
	}
	if out.overflow {
		return checkResult{}, fmt.Errorf("check.script printed more than %d bytes", checkOutputLimit)
	}
	dec := json.NewDecoder(bytes.NewReader(out.Bytes()))
	dec.DisallowUnknownFields()
	var res checkResult
	if err := dec.Decode(&res); err != nil {
		return checkResult{}, fmt.Errorf("check.script printed %q, not one JSON object with state and detail: %w", out.String(), err)
	}
	if dec.More() {
		return checkResult{}, fmt.Errorf("check.script printed more than one JSON object")
	}
	if !slices.Contains(checkStates, res.State) {
		return checkResult{}, fmt.Errorf("check.script reported state %q (want one of %s)", res.State, strings.Join(checkStates, ", "))
	}
	return res, nil
}

// runTeardown runs rec's script from a private temporary copy: the feature's
// own file may be gone.
func (r *runner) runTeardown(feature string, rec TeardownRecord) error {
	f, err := os.CreateTemp("", "dotfiles-teardown-*")
	if err != nil {
		return fmt.Errorf("hooks.teardown: creating its temporary copy: %w", err)
	}
	path := f.Name()
	defer os.Remove(path)
	_, werr := f.Write(rec.Script)
	cerr := f.Close()
	if err := errors.Join(werr, cerr, os.Chmod(path, 0o700)); err != nil {
		return fmt.Errorf("hooks.teardown: writing its temporary copy: %w", err)
	}
	return r.runScript(feature, "hooks.teardown", path, rec.Env, time.Duration(rec.TimeoutSeconds)*time.Second, rec.Sudo, nil)
}

// runScript runs path in the home directory with the hook environment:
// apply's own, the feature's settings, HOME, DOTFILES_DIR (the repository)
// and DOTFILES_FEATURE. Its output goes to HookOutput, or standard output to
// stdout when given. An interactive script, a sudo hook, reads HookStdin.
func (r *runner) runScript(feature, key, path string, env []string, timeout time.Duration, interactive bool, stdout io.Writer) error {
	ctx, cancel := context.WithTimeout(r.ctx, timeout)
	defer cancel()
	cmd := exec.CommandContext(ctx, path)
	cmd.Dir = r.env.Home
	// Later entries win: the feature's settings over apply's environment.
	cmd.Env = append(os.Environ(), env...)
	cmd.Env = append(cmd.Env, "HOME="+r.env.Home, "DOTFILES_DIR="+r.env.Roots[0].Dir, "DOTFILES_FEATURE="+feature)
	output := r.env.HookOutput
	if output == nil {
		output = io.Discard
	}
	cmd.Stdout, cmd.Stderr = output, output
	if stdout != nil {
		cmd.Stdout = stdout
	}
	if interactive {
		cmd.Stdin = r.env.HookStdin
	}
	cmd.WaitDelay = hookWaitDelay
	err := cmd.Run()
	var exit *exec.ExitError
	switch {
	case err == nil:
		return nil
	case errors.Is(ctx.Err(), context.DeadlineExceeded):
		return fmt.Errorf("%s did not finish within %s", key, timeout)
	case errors.As(err, &exit):
		return fmt.Errorf("%s exited with status %d", key, exit.ExitCode())
	default:
		return fmt.Errorf("%s: %w", key, err)
	}
}

// cappedBuffer keeps the first limit bytes written to it and notes whether
// more came.
type cappedBuffer struct {
	bytes.Buffer
	limit    int
	overflow bool
}

func (b *cappedBuffer) Write(p []byte) (int, error) {
	if room := b.limit - b.Len(); len(p) > room {
		b.overflow = true
		b.Buffer.Write(p[:max(room, 0)])
		return len(p), nil
	}
	return b.Buffer.Write(p)
}
