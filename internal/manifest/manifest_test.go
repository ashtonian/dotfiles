package manifest

import (
	"errors"
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
	features, err := LoadFeatures(Root{Dir: root})
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
		{"values for a setting that is not a string", "a", "id = \"a\"\n[settings.\"a.x\"]\ntype = \"int\"\nvalues = [\"1\"]\n", "only a string setting can"},
		{"the same value twice", "a", "id = \"a\"\n[settings.\"a.x\"]\ntype = \"string\"\nvalues = [\"on\", \"on\"]\n", "must be distinct"},
		{"a default that is not one of the values", "a", "id = \"a\"\n[settings.\"a.x\"]\ntype = \"string\"\ndefault = \"of\"\nvalues = [\"on\", \"off\"]\n", `want one of on, off, got "of"`},
		{"a launch agent that is not a plist", "a", "id = \"a\"\n[[provides.launch_agent]]\nplist = \"agent.xml\"\n", "must be a .plist file"},
		{"a launch agent outside the feature", "a", "id = \"a\"\n[[provides.launch_agent]]\nplist = \"../com.example.a.plist\"\n", "leaves the feature directory"},
		{"a relative when_exists", "a", "id = \"a\"\n[[provides.launch_agent]]\nplist = \"com.example.a.plist\"\nwhen_exists = [\"bin/tool\"]\n", "must be absolute or start with ~/"},
		{"a hold on a path it does not link", "a", "id = \"a\"\n[provides]\nlink = [\".local/bin/a\"]\n[provides.link_unless_exists]\n\".local/bin/b\" = [\"~/.b\"]\n", `link_unless_exists names ".local/bin/b", which is not in link`},
		{"a hold with no paths", "a", "id = \"a\"\n[provides]\nlink = [\".local/bin/a\"]\n[provides.link_unless_exists]\n\".local/bin/a\" = []\n", "list the paths that hold it"},
		{"a relative hold", "a", "id = \"a\"\n[provides]\nlink = [\".local/bin/a\"]\n[provides.link_unless_exists]\n\".local/bin/a\" = [\".local/bin/.a\"]\n", "must be absolute or start with ~/"},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			root := t.TempDir()
			writeFeature(t, root, tt.id, tt.body)
			_, err := LoadFeatures(Root{Dir: root})
			require.ErrorIs(t, err, ErrInvalid)
			assert.Contains(t, err.Error(), tt.want)
		})
	}
}

func TestLoadFeaturesReadsLaunchAgents(t *testing.T) {
	root := t.TempDir()
	writeFeature(t, root, "tool.trim", `
id = "tool.trim"
platforms = ["darwin"]

[[provides.launch_agent]]
plist = "launchagents/com.example.trim.plist"
when_exists = ["/opt/homebrew/bin/go", "~/.config/trim/enabled"]
`)
	features, err := LoadFeatures(Root{Dir: root})
	require.NoError(t, err)
	assert.Equal(t, []LaunchAgent{{Plist: "launchagents/com.example.trim.plist",
		WhenExists: []string{"/opt/homebrew/bin/go", "~/.config/trim/enabled"}}}, features["tool.trim"].Provides.LaunchAgent)
}

func TestLoadFeaturesReadsLinkHolds(t *testing.T) {
	root := t.TempDir()
	writeFeature(t, root, "tool.a", `
id = "tool.a"

[provides]
link = [".local/bin/a", ".local/bin/b"]

[provides.link_unless_exists]
".local/bin/a" = ["~/.local/bin/.a", "/opt/a"]
`)
	features, err := LoadFeatures(Root{Dir: root})
	require.NoError(t, err)
	assert.Equal(t, map[string][]string{".local/bin/a": {"~/.local/bin/.a", "/opt/a"}},
		features["tool.a"].Provides.LinkUnlessExists)
}

func TestLoadFeaturesRejectsALaunchAgentDeclaredTwice(t *testing.T) {
	root := t.TempDir()
	writeFeature(t, root, "a", "id = \"a\"\n[[provides.launch_agent]]\nplist = \"com.example.job.plist\"\n")
	writeFeature(t, root, "b", "id = \"b\"\n[[provides.launch_agent]]\nplist = \"launchagents/com.example.job.plist\"\n")
	_, err := LoadFeatures(Root{Dir: root})
	require.ErrorIs(t, err, ErrInvalid)
	assert.Contains(t, err.Error(), "LaunchAgent com.example.job is declared by both a and b")
}

func TestLoadFeaturesRejectsASettingDeclaredTwice(t *testing.T) {
	root := t.TempDir()
	writeFeature(t, root, "a", "id = \"a\"\n[settings.\"shared.x\"]\ntype = \"string\"\n")
	writeFeature(t, root, "b", "id = \"b\"\n[settings.\"shared.x\"]\ntype = \"string\"\n")
	_, err := LoadFeatures(Root{Dir: root})
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

	require.NoError(t, os.WriteFile(path, MachineFile(nil, []string{"base", "dev"}), 0o644))
	m, err = LoadMachine(path)
	require.NoError(t, err)
	assert.Equal(t, &Machine{Profiles: []string{"base", "dev"}}, m, "MachineFile round-trips")
}

func writeProfile(t *testing.T, root, name, body string) {
	t.Helper()
	dir := filepath.Join(root, "profiles")
	require.NoError(t, os.MkdirAll(dir, 0o755))
	require.NoError(t, os.WriteFile(filepath.Join(dir, name+".toml"), []byte(body), 0o644))
}

func TestLoadFeaturesFromOverlays(t *testing.T) {
	repo, personal := t.TempDir(), t.TempDir()
	writeFeature(t, repo, "git", "id = \"git\"\n")
	writeFeature(t, personal, "personal.git", "id = \"personal.git\"\ndefault = true\n")
	writeFeature(t, personal, "personal", "id = \"personal\"\n")
	writeProfile(t, repo, "base", "")
	writeProfile(t, personal, "personal.studio", "")

	roots := []Root{{Dir: repo}, {Dir: personal, Overlay: "personal"}}
	features, err := LoadFeatures(roots...)
	require.NoError(t, err)
	assert.Equal(t, filepath.Join(personal, "features", "personal.git"), features["personal.git"].Dir)
	assert.Contains(t, features, "personal")
	assert.Contains(t, features, "git")

	profiles, err := LoadProfiles(roots...)
	require.NoError(t, err)
	assert.Contains(t, profiles, "base")
	assert.Contains(t, profiles, "personal.studio")
}

func TestOverlaysKeepToTheirOwnNames(t *testing.T) {
	tests := []struct {
		name  string
		setup func(t *testing.T, repo, overlay string)
		want  string
	}{
		{"an overlay feature without the overlay's name", func(t *testing.T, repo, overlay string) {
			writeFeature(t, overlay, "git.private", "id = \"git.private\"\n")
		}, `feature "git.private" is in overlay client-a, so its name must be "client-a" or start with "client-a."`},
		{"an overlay feature named for another overlay", func(t *testing.T, repo, overlay string) {
			writeFeature(t, overlay, "personal.git", "id = \"personal.git\"\n")
		}, `is in overlay client-a`},
		{"a repository feature in an overlay's namespace", func(t *testing.T, repo, overlay string) {
			writeFeature(t, repo, "client-a.rules", "id = \"client-a.rules\"\n")
		}, `feature "client-a.rules" in the repository starts with the name of overlay client-a`},
		{"an overlay profile without the overlay's name", func(t *testing.T, repo, overlay string) {
			writeProfile(t, overlay, "studio", "")
		}, `profile "studio" is in overlay client-a`},
		{"a repository profile in an overlay's namespace", func(t *testing.T, repo, overlay string) {
			writeProfile(t, repo, "client-a", "")
		}, `profile "client-a" in the repository starts with the name of overlay client-a`},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			repo, overlay := t.TempDir(), t.TempDir()
			tt.setup(t, repo, overlay)
			roots := []Root{{Dir: repo}, {Dir: overlay, Overlay: "client-a"}}
			_, ferr := LoadFeatures(roots...)
			_, perr := LoadProfiles(roots...)
			err := errors.Join(ferr, perr)
			require.ErrorIs(t, err, ErrInvalid)
			assert.Contains(t, err.Error(), tt.want)
		})
	}
}

func TestOverlayRoots(t *testing.T) {
	dir := t.TempDir()
	require.NoError(t, os.Mkdir(filepath.Join(dir, "personal"), 0o755))
	require.NoError(t, os.WriteFile(filepath.Join(dir, "client-b"), nil, 0o644))

	roots, err := OverlayRoots(dir, []string{"personal"})
	require.NoError(t, err)
	assert.Equal(t, []Root{{Dir: filepath.Join(dir, "personal"), Overlay: "personal"}}, roots)

	for _, name := range []string{"client-a", "client-b"} {
		_, err = OverlayRoots(dir, []string{"personal", name})
		require.ErrorIs(t, err, ErrNoOverlay, name)
		assert.Contains(t, err.Error(), filepath.Join(dir, name))
	}
	_, err = OverlayRoots(dir, []string{"../personal"})
	require.ErrorIs(t, err, ErrInvalid, "a name never leaves the overlay directory")
}

func TestLoadMachineOverlays(t *testing.T) {
	path := filepath.Join(t.TempDir(), "machine.toml")
	require.NoError(t, os.WriteFile(path, MachineFile([]string{"personal", "client-a"}, []string{"base"}), 0o644))
	m, err := LoadMachine(path)
	require.NoError(t, err)
	assert.Equal(t, &Machine{Overlays: []string{"personal", "client-a"}, Profiles: []string{"base"}}, m, "MachineFile round-trips")

	for _, body := range []string{"overlays = [\"personal\", \"personal\"]\n", "overlays = [\"a.b\"]\n", "overlays = [\"../x\"]\n"} {
		require.NoError(t, os.WriteFile(path, []byte(body), 0o644))
		_, err = LoadMachine(path)
		assert.ErrorIs(t, err, ErrInvalid, body)
	}
}
