package prefs

import (
	"context"
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

// A settings file as Claude Code writes it: two-space indent, a final
// newline, and keys that belong to this machine alone.
const claudeSettings = `{
  "env": {
    "CLAUDE_CODE_SHELL": "/opt/homebrew/bin/bash"
  },
  "hooks": {
    "Stop": [
      {
        "matcher": "*",
        "hooks": []
      }
    ]
  },
  "theme": "dark-ansi",
  "effortLevel": "high",
  "note": "a <tag> & more"
}
`

func claudeHome(t *testing.T, content string) (*Claude, string) {
	t.Helper()
	home := t.TempDir()
	path := filepath.Join(home, ".claude", "settings.json")
	if content != "" {
		require.NoError(t, os.MkdirAll(filepath.Dir(path), 0o700))
		require.NoError(t, os.WriteFile(path, []byte(content), 0o644))
	}
	return NewClaude(home), path
}

func TestClaudeSetChangesOnlyTheKey(t *testing.T) {
	ctx := context.Background()
	c, path := claudeHome(t, claudeSettings)

	v, ok, err := c.Get(ctx, "theme")
	require.NoError(t, err)
	assert.True(t, ok)
	assert.Equal(t, "dark-ansi", v)

	require.NoError(t, c.Set(ctx, "theme", "custom:dracula"))
	got, err := os.ReadFile(path)
	require.NoError(t, err)
	want := strings.Replace(claudeSettings, `"theme": "dark-ansi"`, `"theme": "custom:dracula"`, 1)
	assert.Equal(t, want, string(got), "every other key keeps its value, its place and its formatting")
	info, err := os.Stat(path)
	require.NoError(t, err)
	assert.Equal(t, os.FileMode(0o644), info.Mode().Perm(), "the file keeps its mode")

	require.NoError(t, c.Set(ctx, "statusLine", map[string]any{"type": "command"}))
	v, ok, err = c.Get(ctx, "statusLine")
	require.NoError(t, err)
	assert.True(t, ok)
	assert.Equal(t, map[string]any{"type": "command"}, v)

	require.NoError(t, c.Unset(ctx, "statusLine"))
	got, err = os.ReadFile(path)
	require.NoError(t, err)
	assert.Equal(t, want, string(got), "unsetting the added key restores the file")
}

func TestClaudeCreatesAMissingFilePrivately(t *testing.T) {
	ctx := context.Background()
	c, path := claudeHome(t, "")
	_, ok, err := c.Get(ctx, "theme")
	require.NoError(t, err)
	assert.False(t, ok, "a missing file has no settings")

	require.NoError(t, c.Set(ctx, "theme", "custom:dracula"))
	got, err := os.ReadFile(path)
	require.NoError(t, err)
	assert.Equal(t, "{\n  \"theme\": \"custom:dracula\"\n}\n", string(got))
	info, err := os.Stat(path)
	require.NoError(t, err)
	assert.Equal(t, os.FileMode(0o600), info.Mode().Perm())
}

func TestClaudeKeepsNumbersAsWritten(t *testing.T) {
	ctx := context.Background()
	c, _ := claudeHome(t, "{\"autoCompactWindow\": 400000, \"ratio\": 1.50}")
	v, _, err := c.Get(ctx, "ratio")
	require.NoError(t, err)
	assert.Equal(t, json.Number("1.50"), v)
	require.NoError(t, c.Set(ctx, "theme", "dark"))
	v, _, err = c.Get(ctx, "autoCompactWindow")
	require.NoError(t, err)
	assert.Equal(t, json.Number("400000"), v)
}

func TestClaudeRefusesAFileThatIsNotAnObject(t *testing.T) {
	ctx := context.Background()
	c, path := claudeHome(t, "[1, 2]\n")
	_, _, err := c.Get(ctx, "theme")
	assert.ErrorContains(t, err, "not a JSON object")
	assert.ErrorContains(t, c.Set(ctx, "theme", "dark"), "not a JSON object")
	got, err := os.ReadFile(path)
	require.NoError(t, err)
	assert.Equal(t, "[1, 2]\n", string(got), "a file it cannot read is left alone")
}
