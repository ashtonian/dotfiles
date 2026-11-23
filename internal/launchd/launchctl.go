package launchd

import (
	"bytes"
	"context"
	"errors"
	"fmt"
	"os/exec"
	"strconv"
	"strings"
	"time"
)

// notFound is launchctl print's exit status for a label the domain does not have.
const notFound = 113

// loadAttempts bounds Load's retries. A bootstrap right after a bootout of the
// same label can fail while launchd is still tearing the old job down.
const loadAttempts = 5

// State is what launchd reports about a job.
type State struct {
	Loaded  bool
	Running bool // it has a process now
}

// Client registers jobs in one user's launchd GUI domain (gui/<uid>), the
// domain of LaunchAgents in ~/Library/LaunchAgents.
type Client struct {
	launchctl string
	domain    string
	timeout   time.Duration
	retryWait time.Duration
}

// New returns a client that runs the launchctl binary at path for the GUI
// domain of uid, giving each launchctl call at most timeout.
func New(path string, uid int, timeout time.Duration) *Client {
	return &Client{launchctl: path, domain: "gui/" + strconv.Itoa(uid), timeout: timeout, retryWait: 250 * time.Millisecond}
}

// State reports whether the domain has a job with label, and whether it runs.
func (c *Client) State(ctx context.Context, label string) (State, error) {
	out, err := c.run(ctx, "print", c.domain+"/"+label)
	var exit *exec.ExitError
	switch {
	case errors.As(err, &exit) && exit.ExitCode() == notFound:
		return State{}, nil
	case err != nil:
		return State{}, err
	}
	// The job's own state is the one line indented once; deeper ones describe
	// its endpoints and event sources.
	for line := range strings.Lines(string(out)) {
		if value, ok := strings.CutPrefix(line, "\tstate = "); ok {
			return State{Loaded: true, Running: strings.TrimSpace(value) == "running"}, nil
		}
	}
	return State{Loaded: true}, nil
}

// Load bootstraps the plist at path into the domain. launchd starts the job
// when its plist says to (RunAtLoad, KeepAlive).
func (c *Client) Load(ctx context.Context, path string) error {
	var err error
	for attempt := 1; attempt <= loadAttempts; attempt++ {
		if _, err = c.run(ctx, "bootstrap", c.domain, path); err == nil {
			return nil
		}
		if attempt == loadAttempts {
			break
		}
		select {
		case <-ctx.Done():
			return err
		case <-time.After(time.Duration(attempt) * c.retryWait):
		}
	}
	return err
}

// Unload boots the job with label out of the domain, stopping it if it runs.
// A job that is already gone is not an error.
func (c *Client) Unload(ctx context.Context, label string) error {
	_, err := c.run(ctx, "bootout", c.domain+"/"+label)
	if err == nil {
		return nil
	}
	if state, serr := c.State(ctx, label); serr == nil && !state.Loaded {
		return nil
	}
	return err
}

func (c *Client) run(ctx context.Context, args ...string) ([]byte, error) {
	ctx, cancel := context.WithTimeout(ctx, c.timeout)
	defer cancel()
	cmd := exec.CommandContext(ctx, c.launchctl, args...)
	var stderr bytes.Buffer
	cmd.Stderr = &stderr
	out, err := cmd.Output()
	if err != nil {
		return out, fmt.Errorf("launchctl %s: %w: %s", strings.Join(args, " "), err, strings.TrimSpace(stderr.String()))
	}
	return out, nil
}
