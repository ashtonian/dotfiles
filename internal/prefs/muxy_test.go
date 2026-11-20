package prefs

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"slices"
	"testing"
	"time"

	"github.com/BurntSushi/toml"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

// fakeMuxy installs a stand-in for the app's `muxy` under a throwaway home's
// ~/Applications: a script that runs this test binary as TestFakeMuxy,
// keeping settings in a JSON file. mode picks a failure to act out.
func fakeMuxy(t *testing.T, mode string, settings map[string]any) (home, state string) {
	t.Helper()
	home = t.TempDir()
	state = filepath.Join(home, "muxy-settings.json")
	data, err := json.Marshal(settings)
	require.NoError(t, err)
	require.NoError(t, os.WriteFile(state, data, 0o600))
	self, err := os.Executable()
	require.NoError(t, err)
	cli := filepath.Join(home, "Applications", muxyInBundle)
	require.NoError(t, os.MkdirAll(filepath.Dir(cli), 0o755))
	script := fmt.Sprintf("#!/bin/sh\nexec %q -test.run='^TestFakeMuxy$' -- \"$@\"\n", self)
	require.NoError(t, os.WriteFile(cli, []byte(script), 0o755))
	t.Setenv("FAKE_MUXY_STATE", state)
	t.Setenv("FAKE_MUXY_MODE", mode)
	return home, state
}

// TestFakeMuxy is not a test: fakeMuxy runs the test binary through it to
// answer `muxy config` the way Muxy 2.5 does.
func TestFakeMuxy(t *testing.T) {
	state := os.Getenv("FAKE_MUXY_STATE")
	if state == "" {
		t.Skip("the stand-in for muxy, run by fakeMuxy")
	}
	args := os.Args[slices.Index(os.Args, "--")+1:]
	args = slices.DeleteFunc(slices.Clone(args), func(a string) bool { return a == "--json" || a == "--" })
	fail := func(msg string) {
		fmt.Fprintln(os.Stderr, "muxy: "+msg)
		os.Exit(1)
	}
	var settings map[string]any
	data, err := os.ReadFile(state)
	if err != nil || json.Unmarshal(data, &settings) != nil {
		fail("unreadable settings")
	}
	save := func() {
		data, _ := json.Marshal(settings)
		if os.WriteFile(state, data, 0o600) != nil {
			fail("cannot save")
		}
	}
	mode := os.Getenv("FAKE_MUXY_MODE")
	if mode == "hang" {
		time.Sleep(time.Minute)
	}
	switch {
	case len(args) == 3 && args[0] == "config" && args[1] == "list":
		fail("list takes no arguments")
	case len(args) == 2 && args[0] == "config" && args[1] == "list":
		out, _ := json.Marshal(settings)
		fmt.Println(string(out))
	case len(args) == 4 && args[0] == "config" && args[1] == "set":
		var parsed map[string]any
		if _, err := toml.Decode("v = "+args[3], &parsed); err != nil {
			fail(args[2] + ": not a TOML value")
		}
		if _, isString := parsed["v"].(string); isString && args[2] == "terminal.font_size" {
			fail(args[2] + `: invalid type: string, expected f32`)
		}
		settings[args[2]] = parsed["v"]
		save()
		if mode == "not-applied" {
			fail("saved, but the running app couldn't apply it: terminal.toml: unknown field")
		}
		fmt.Printf("{\"key\":%q,\"applied\":true}\n", args[2])
	case len(args) == 3 && args[0] == "config" && args[1] == "unset":
		delete(settings, args[2])
		save()
		fmt.Printf("{\"key\":%q}\n", args[2])
	default:
		fail(fmt.Sprintf("unknown command %v", args))
	}
	os.Exit(0)
}

func TestMuxyRoundTripsThroughTheAppsTool(t *testing.T) {
	ctx := context.Background()
	home, state := fakeMuxy(t, "", map[string]any{"appearance.dark_theme": "Muxy", "terminal.font_size": 13.0})
	m := NewMuxy(MuxyCommands(home), 10*time.Second)

	v, ok, err := m.Get(ctx, "appearance.dark_theme")
	require.NoError(t, err)
	assert.True(t, ok)
	assert.Equal(t, "Muxy", v)
	_, ok, err = m.Get(ctx, "privacy.usage_ping")
	require.NoError(t, err)
	assert.False(t, ok, "a setting missing from `config list` has no value")

	require.NoError(t, m.Set(ctx, "appearance.dark_theme", "Dracula"))
	require.NoError(t, m.Set(ctx, "terminal.font_families", []any{"FiraCode Nerd Font Mono"}))
	require.NoError(t, m.Set(ctx, "terminal.font_size", 14.0))
	var saved map[string]any
	data, err := os.ReadFile(state)
	require.NoError(t, err)
	require.NoError(t, json.Unmarshal(data, &saved))
	assert.Equal(t, map[string]any{"appearance.dark_theme": "Dracula",
		"terminal.font_families": []any{"FiraCode Nerd Font Mono"}, "terminal.font_size": 14.0}, saved)

	require.NoError(t, m.Unset(ctx, "terminal.font_size"))
	_, ok, err = m.Get(ctx, "terminal.font_size")
	require.NoError(t, err)
	assert.False(t, ok)
}

func TestMuxyReportsWhatTheAppRefused(t *testing.T) {
	ctx := context.Background()
	home, _ := fakeMuxy(t, "", map[string]any{})
	err := NewMuxy(MuxyCommands(home), 10*time.Second).Set(ctx, "terminal.font_size", "big")
	assert.EqualError(t, err, "muxy config set: terminal.font_size: invalid type: string, expected f32")
	assert.False(t, errors.Is(err, ErrNotApplied))
}

func TestMuxyTellsASavedButUnappliedValueApart(t *testing.T) {
	ctx := context.Background()
	home, _ := fakeMuxy(t, "not-applied", map[string]any{})
	err := NewMuxy(MuxyCommands(home), 10*time.Second).Set(ctx, "terminal.font_families", []any{"Menlo"})
	assert.ErrorIs(t, err, ErrNotApplied)
	assert.ErrorContains(t, err, "unknown field")
}

func TestMuxyGivesUpOnAToolThatDoesNotAnswer(t *testing.T) {
	home, _ := fakeMuxy(t, "hang", map[string]any{})
	start := time.Now()
	_, _, err := NewMuxy(MuxyCommands(home), 200*time.Millisecond).Get(context.Background(), "appearance.dark_theme")
	assert.EqualError(t, err, "muxy config list: no answer within 200ms")
	assert.Less(t, time.Since(start), 10*time.Second)
}

func TestMuxyWithoutTheAppIsUnavailable(t *testing.T) {
	home := t.TempDir()
	m := NewMuxy([]string{filepath.Join(home, "Applications", muxyInBundle)}, time.Second)
	_, _, err := m.Get(context.Background(), "appearance.dark_theme")
	assert.ErrorIs(t, err, ErrUnavailable)
	assert.ErrorContains(t, err, "Muxy is not installed")
}

func TestMuxyCommandsPreferAPerUserInstall(t *testing.T) {
	assert.Equal(t, []string{"/Users/me/Applications/" + muxyInBundle, "/Applications/" + muxyInBundle},
		MuxyCommands("/Users/me"))
}
