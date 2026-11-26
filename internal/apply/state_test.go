package apply

import (
	"encoding/json"
	"os"
	"path/filepath"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestStateFromAnOlderBuildIsReadAndSavedAsThisOnes(t *testing.T) {
	path := filepath.Join(t.TempDir(), "applied.json")
	require.NoError(t, os.WriteFile(path, []byte(`{"version": 1, "links": {"/h/.zshrc": "/r/zshrc"}}`), 0o600))

	s, err := LoadState(path)
	require.NoError(t, err)
	assert.Equal(t, "/r/zshrc", s.Links["/h/.zshrc"])
	assert.Empty(t, s.Prefs, "a version 1 file set no app settings")
	assert.NotNil(t, s.Teardowns, "nor recorded a teardown")
	require.NoError(t, s.Save(path))

	var saved struct{ Version int }
	data, err := os.ReadFile(path)
	require.NoError(t, err)
	require.NoError(t, json.Unmarshal(data, &saved))
	assert.Equal(t, stateVersion, saved.Version)
}

func TestStateFromANewerBuildIsRefused(t *testing.T) {
	path := filepath.Join(t.TempDir(), "applied.json")
	newer := []byte(`{"version": 4, "links": {}, "later": {"x": 1}}`)
	require.NoError(t, os.WriteFile(path, newer, 0o600))

	_, err := LoadState(path)
	assert.ErrorContains(t, err, "a newer dotfiles wrote it")
	data, err := os.ReadFile(path)
	require.NoError(t, err)
	assert.Equal(t, newer, data, "left for the build that wrote it")

	require.NoError(t, os.WriteFile(path, []byte(`{"links": {}}`), 0o600))
	_, err = LoadState(path)
	assert.ErrorContains(t, err, "has no version")
}
