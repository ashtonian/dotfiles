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

// muxyInBundle is where the app keeps its command line tool.
const muxyInBundle = "Muxy.app/Contents/MacOS/muxy"

// Muxy reads and writes Muxy's app settings through `muxy config`, which
// validates each change, saves it, and has the running app apply it. It runs
// the copy of the tool inside the app bundle, which always matches the
// installed app; the `muxy` on PATH can be another build, such as the one a
// Muxy client installs on a machine it uses as a remote server.
type Muxy struct {
	commands []string
	timeout  time.Duration
}

// MuxyCommands lists where an installed Muxy keeps its tool, a per-user
// install first: <home>/Applications, then /Applications.
func MuxyCommands(home string) []string {
	return []string{
		filepath.Join(home, "Applications", muxyInBundle),
		filepath.Join("/Applications", muxyInBundle),
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
// ErrNotApplied.
func (m *Muxy) Set(ctx context.Context, key string, value any) error {
	rendered, err := EncodeTOML(value)
	if err != nil {
		return fmt.Errorf("muxy setting %s: %w", key, err)
	}
	_, err = m.run(ctx, "config", "set", "--json", "--", key, rendered)
	if err == nil {
		return nil
	}
	if ctx.Err() != nil {
		return err
	}
	// Muxy reports a value it saved but the running app rejected the same
	// way as one it refused; what it saved tells them apart.
	if live, ok, getErr := m.Get(ctx, key); getErr == nil && ok && Equal(live, value) {
		return fmt.Errorf("%w: %w", ErrNotApplied, err)
	}
	return err
}

// Unset returns key to Muxy's default.
func (m *Muxy) Unset(ctx context.Context, key string) error {
	_, err := m.run(ctx, "config", "unset", "--json", "--", key)
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
