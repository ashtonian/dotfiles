package prefs

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"time"
)

// toolInApp is where a Muxy app bundle keeps its command line tool.
const toolInApp = "Contents/MacOS/muxy"

// Muxy reads and writes Muxy's app settings through `muxy config`, which
// validates each change, saves it, and has the running app apply it. It runs
// the copy of the tool inside the app bundle, which always matches the
// installed app; the `muxy` on PATH can be another build, such as the one a
// Muxy client installs on a machine it uses as a remote server.
type Muxy struct {
	commands []string
	timeout  time.Duration
}

// MuxyCommands lists where an installed Muxy keeps its tool: inside app when
// it is set (DOTFILES_MUXY_APP, which tool.muxy's wrapper also reads), else a
// per-user install first, <home>/Applications, then /Applications.
func MuxyCommands(home, app string) []string {
	if app != "" {
		return []string{filepath.Join(app, toolInApp)}
	}
	return []string{
		filepath.Join(home, "Applications", "Muxy.app", toolInApp),
		filepath.Join("/Applications", "Muxy.app", toolInApp),
	}
}

// NewMuxy returns a store that runs the first of commands that exists, each
// call limited to timeout.
func NewMuxy(commands []string, timeout time.Duration) *Muxy {
	return &Muxy{commands: commands, timeout: timeout}
}

// Get returns key's current value. `muxy config list` lists every setting
// that has a value, so a key missing from it has none.
func (m *Muxy) Get(ctx context.Context, key string) (any, bool, error) {
	out, err := m.run(ctx, "config", "list", "--json")
	if err != nil {
		return nil, false, err
	}
	var all map[string]json.RawMessage
	if err := json.Unmarshal(out, &all); err != nil {
		return nil, false, fmt.Errorf("reading muxy config list: %w", err)
	}
	raw, ok := all[key]
	if !ok {
		return nil, false, nil
	}
	v, err := DecodeJSON(raw)
	if err != nil {
		return nil, false, fmt.Errorf("reading muxy setting %s: %w", key, err)
	}
	return v, true, nil
}

// Set saves key = value. Muxy refuses a value its app could not start with.
// When it saves a value the running app then fails to apply, the error wraps
// ErrNotApplied. Muxy keeps some numbers less precisely than TOML writes them
// (a float setting is 32-bit), so Get can read back a value that differs a
// little from the one set.
func (m *Muxy) Set(ctx context.Context, key string, value any) error {
	rendered, err := EncodeTOML(value)
	if err != nil {
		return fmt.Errorf("muxy setting %s: %w", key, err)
	}
	return m.change(ctx, key, "config", "set", "--json", "--", key, rendered)
}

// Unset returns key to Muxy's default. As with Set, an error wrapping
// ErrNotApplied means the file changed and the running app did not take it.
func (m *Muxy) Unset(ctx context.Context, key string) error {
	return m.change(ctx, key, "config", "unset", "--json", "--", key)
}

// change runs a `muxy config` command that saves key, then has a running app
// apply it. Muxy exits the same way when it refuses the change as when it
// saved the change and the running app failed to apply it; whether key's
// value moved tells them apart.
func (m *Muxy) change(ctx context.Context, key string, args ...string) error {
	before, had, err := m.Get(ctx, key)
	if err != nil {
		return err
	}
	_, err = m.run(ctx, args...)
	if err == nil || ctx.Err() != nil {
		return err
	}
	after, has, getErr := m.Get(ctx, key)
	if getErr == nil && (had != has || !Equal(before, after)) {
		return fmt.Errorf("%w: %w", ErrNotApplied, err)
	}
	return err
}

func (m *Muxy) command() (string, error) {
	for _, c := range m.commands {
		if info, err := os.Stat(c); err == nil && info.Mode().IsRegular() && info.Mode().Perm()&0o111 != 0 {
			return c, nil
		}
	}
	return "", fmt.Errorf("%w: Muxy is not installed; looked for %s", ErrUnavailable, strings.Join(m.commands, " and "))
}

func (m *Muxy) run(ctx context.Context, args ...string) ([]byte, error) {
	name, err := m.command()
	if err != nil {
		return nil, err
	}
	ctx, cancel := context.WithTimeout(ctx, m.timeout)
	defer cancel()
	cmd := exec.CommandContext(ctx, name, args...)
	var stdout, stderr bytes.Buffer
	cmd.Stdout, cmd.Stderr = &stdout, &stderr
	cmd.WaitDelay = time.Second
	if err := cmd.Run(); err != nil {
		operation := "muxy " + strings.Join(args[:2], " ")
		if errors.Is(ctx.Err(), context.DeadlineExceeded) {
			return nil, fmt.Errorf("%s: no answer within %s", operation, m.timeout)
		}
		detail := strings.TrimPrefix(strings.TrimSpace(stderr.String()), "muxy: ")
		if detail == "" {
			detail = err.Error()
		}
		return nil, fmt.Errorf("%s: %s", operation, detail)
	}
	return stdout.Bytes(), nil
}
