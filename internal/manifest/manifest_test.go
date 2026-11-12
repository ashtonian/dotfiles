package manifest

import (
	"os"
	"path/filepath"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func writeFeature(t *testing.T, root, id, body string) {
	t.Helper()
	dir := filepath.Join(root, "features", id)
	require.NoError(t, os.MkdirAll(dir, 0o755))
	require.NoError(t, os.WriteFile(filepath.Join(dir, "feature.toml"), []byte(body), 0o644))
}

func TestLoadFeatures(t *testing.T) {
	root := t.TempDir()
	writeFeature(t, root, "shell.zoxide", `
id = "shell.zoxide"
platforms = ["darwin", "linux"]
default = true
requires = ["shell.core"]

[provides]
brew = ["zoxide"]
link = [".config/zoxide"]
stub = [{ path = ".zshrc", line = "source ~/.config/zsh/zshrc.zsh" }]

[settings."zoxide.cd"]
type = "bool"
default = true
`)
	features, err := LoadFeatures(root)
	require.NoError(t, err)
	f := features["shell.zoxide"]
	require.NotNil(t, f)
	assert.Equal(t, filepath.Join(root, "features", "shell.zoxide"), f.Dir)
	assert.True(t, f.Supports("linux"))
	assert.False(t, f.Supports("windows"))
	assert.Equal(t, []string{"zoxide"}, f.Provides.Brew)
	assert.Equal(t, "bool", f.Settings["zoxide.cd"].Type)
}

func TestLoadFeaturesRejects(t *testing.T) {
	tests := []struct {
		name, id, body, want string
	}{
		{"an unknown key", "a", "id = \"a\"\nsurprise = 1\n", "unknown keys: surprise"},
		{"an id that is not its directory", "a", "id = \"b\"\n", `must match its directory name "a"`},
		{"an unknown platform", "a", "id = \"a\"\nplatforms = [\"plan9\"]\n", `unknown platform "plan9"`},
		{"a path leaving the feature", "a", "id = \"a\"\n[provides]\nlink = [\"../../etc\"]\n", "leaves the feature directory"},
		{"an absolute path", "a", "id = \"a\"\n[provides]\nbin = [\"/usr/bin/x\"]\n", "must be relative"},
		{"a package name with a quote", "a", "id = \"a\"\n[provides]\nbrew = [\"x\\\"; system(1)\"]\n", "characters a package name cannot"},
		{"a stub with two lines", "a", "id = \"a\"\n[provides]\nstub = [{ path = \".zshrc\", line = \"a\\nb\" }]\n", "exactly one line"},
		{"a stub keyword that is not one word", "a", "id = \"a\"\n[provides]\nstub = [{ path = \".ssh/config\", line = \"Include x\", before = [\"Host *\"] }]\n", "must be one word"},
		{"a setting with an unknown type", "a", "id = \"a\"\n[settings.\"a.x\"]\ntype = \"float\"\n", `unknown type "float"`},
		{"a secret default that is a value", "a", "id = \"a\"\n[settings.\"a.x\"]\ntype = \"secret\"\ndefault = \"hunter2\"\n", "never a value"},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			root := t.TempDir()
			writeFeature(t, root, tt.id, tt.body)
			_, err := LoadFeatures(root)
			require.ErrorIs(t, err, ErrInvalid)
			assert.Contains(t, err.Error(), tt.want)
		})
	}
}

func TestLoadFeaturesRejectsASettingDeclaredTwice(t *testing.T) {
	root := t.TempDir()
	writeFeature(t, root, "a", "id = \"a\"\n[settings.\"shared.x\"]\ntype = \"string\"\n")
	writeFeature(t, root, "b", "id = \"b\"\n[settings.\"shared.x\"]\ntype = \"string\"\n")
	_, err := LoadFeatures(root)
	require.ErrorIs(t, err, ErrInvalid)
	assert.Contains(t, err.Error(), `setting "shared.x" is declared by both`)
}

func TestLoadMachine(t *testing.T) {
	_, err := LoadMachine(filepath.Join(t.TempDir(), "machine.toml"))
	assert.ErrorIs(t, err, ErrNoMachine, "a missing manifest is never an empty machine")

	path := filepath.Join(t.TempDir(), "machine.toml")
	require.NoError(t, os.WriteFile(path, []byte(`profiles = ["base", "dev"]
[features]
disable = ["shell.greeting"]
[settings]
"toggl.organization_id" = { secret = "op://dotfiles/toggl/organization_id" }
`), 0o644))
	m, err := LoadMachine(path)
	require.NoError(t, err)
	assert.Equal(t, []string{"base", "dev"}, m.Profiles)
	assert.Equal(t, []string{"shell.greeting"}, m.Features.Disable)
	assert.NoError(t, CheckValue("secret", m.Settings["toggl.organization_id"]))

	require.NoError(t, os.WriteFile(path, MachineFile([]string{"base", "dev"}), 0o644))
	m, err = LoadMachine(path)
	require.NoError(t, err)
	assert.Equal(t, &Machine{Profiles: []string{"base", "dev"}}, m, "MachineFile round-trips")
}
