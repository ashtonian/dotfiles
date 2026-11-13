package apply

import (
	"context"
	"os"
	"path/filepath"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	"github.com/ashtonian/dotfiles/internal/manifest"
	"github.com/ashtonian/dotfiles/internal/plan"
	"github.com/ashtonian/dotfiles/internal/resolve"
)

// machine is a throwaway repository and home directory.
type machine struct {
	t                     *testing.T
	repo, home, generated string
	goos                  string
	state                 *State
	disable               []string
}

func newMachine(t *testing.T) *machine {
	t.Helper()
	root := t.TempDir()
	m := &machine{t: t, repo: filepath.Join(root, "repo"), home: filepath.Join(root, "home"),
		goos: "linux", state: newState()}
	m.generated = filepath.Join(m.home, ".config", "dotfiles", "generated")
	require.NoError(t, os.MkdirAll(m.home, 0o700))
	m.write("features/shell/feature.toml", `id = "shell"
default = true
[provides]
link = [".config/shell"]
env = "env.sh"
brew = ["zoxide"]
stub = [{ path = ".zshrc", line = "source ~/.config/dotfiles/generated/zshrc.zsh" }]
`)
	m.write("features/shell/env.sh", "export SHELL_FEATURE=1\n")
	m.write("features/shell/home/.config/shell/a.sh", "a\n")
	m.write("features/shell/home/.config/shell/nested/b.sh", "b\n")
	m.write("features/prefs/feature.toml", `id = "prefs"
default = true
[provides]
copy = [".config/app/settings.json"]
link = ["Library/Preferences/com.example.plist"]
`)
	m.write("features/prefs/home/.config/app/settings.json", "{}\n")
	m.write("features/prefs/home/Library/Preferences/com.example.plist", "plist\n")
	return m
}

func (m *machine) write(rel, content string) {
	m.t.Helper()
	path := filepath.Join(m.repo, rel)
	require.NoError(m.t, os.MkdirAll(filepath.Dir(path), 0o755))
	require.NoError(m.t, os.WriteFile(path, []byte(content), 0o644))
}

func (m *machine) plan() *plan.Plan {
	m.t.Helper()
	features, err := manifest.LoadFeatures(m.repo)
	require.NoError(m.t, err)
	res, err := resolve.Resolve(features, nil, &manifest.Machine{Features: manifest.Selection{Disable: m.disable}}, m.goos)
	require.NoError(m.t, err)
	p, err := plan.Build(features, res.Runnable(features), plan.Env{Home: m.home, GeneratedDir: m.generated, GOOS: m.goos})
	require.NoError(m.t, err)
	return p
}

func (m *machine) run(dryRun bool) *Report {
	m.t.Helper()
	report, next, err := Run(context.Background(), m.plan(), m.state, Env{Home: m.home, RepoRoot: m.repo}, dryRun)
	require.NoError(m.t, err)
	if !dryRun {
		m.state = next
	}
	return report
}

func (m *machine) at(rel string) string { return filepath.Join(m.home, rel) }

func kinds(r *Report) map[string]int {
	k := map[string]int{}
	for _, a := range r.Actions {
		k[a.Kind]++
	}
	return k
}

func TestFreshHomeConvergesAndStaysPut(t *testing.T) {
	m := newMachine(t)
	first := m.run(false)
	assert.Empty(t, first.Problems)

	for _, rel := range []string{".config/shell/a.sh", ".config/shell/nested/b.sh"} {
		dest, err := os.Readlink(m.at(rel))
		require.NoError(t, err, rel)
		assert.Equal(t, filepath.Join(m.repo, "features/shell/home", rel), dest)
	}
	// One link per file: the directories are real, so nothing written beside a
	// config lands in the repository.
	for _, dir := range []string{".config", ".config/shell", ".config/shell/nested"} {
		info, err := os.Lstat(m.at(dir))
		require.NoError(t, err)
		assert.True(t, info.IsDir(), dir)
	}
	env, err := os.ReadFile(filepath.Join(m.generated, "env.sh"))
	require.NoError(t, err)
	assert.Contains(t, string(env), "export SHELL_FEATURE=1")
	brewfile, err := os.ReadFile(filepath.Join(m.generated, "Brewfile"))
	require.NoError(t, err)
	assert.Contains(t, string(brewfile), `brew "zoxide" # shell`)
	stub, err := os.ReadFile(m.at(".zshrc"))
	require.NoError(t, err)
	assert.Equal(t, "source ~/.config/dotfiles/generated/zshrc.zsh\n", string(stub))

	second := m.run(false)
	assert.Empty(t, second.Actions, "a second run changes nothing")
	assert.Empty(t, second.Problems)
}

func TestDisablingAFeatureRemovesWhatItInstalled(t *testing.T) {
	m := newMachine(t)
	m.run(false)
	m.disable = []string{"shell"}
	report := m.run(false)
	assert.Equal(t, 2, kinds(report)["unlink"])
	assert.NoFileExists(t, m.at(".config/shell/a.sh"))
	// A stub belongs to the owner once created.
	assert.FileExists(t, m.at(".zshrc"))
}

func TestAFileInTheWayIsLeftAlone(t *testing.T) {
	m := newMachine(t)
	require.NoError(t, os.MkdirAll(m.at(".config/shell"), 0o700))
	require.NoError(t, os.WriteFile(m.at(".config/shell/a.sh"), []byte("mine\n"), 0o644))
	report := m.run(false)
	require.Len(t, report.Problems, 1)
	assert.Equal(t, m.at(".config/shell/a.sh"), report.Problems[0].Path)
	content, err := os.ReadFile(m.at(".config/shell/a.sh"))
	require.NoError(t, err)
	assert.Equal(t, "mine\n", string(content))
}

func TestOldStowLinksAreTakenOver(t *testing.T) {
	m := newMachine(t)
	require.NoError(t, os.MkdirAll(m.at(".config/shell"), 0o700))
	// stow writes relative links into the repository.
	rel, err := filepath.Rel(m.at(".config/shell"), filepath.Join(m.repo, "features/shell/home/.config/shell/a.sh"))
	require.NoError(t, err)
	require.NoError(t, os.Symlink(rel, m.at(".config/shell/a.sh")))
	require.NoError(t, os.Symlink(filepath.Join(m.repo, "features/shell/home/.zshrc-old"), m.at(".zshrc")))

	report := m.run(false)
	assert.Empty(t, report.Problems)
	assert.Equal(t, 1, kinds(report)["relink"])
	dest, err := os.Readlink(m.at(".config/shell/a.sh"))
	require.NoError(t, err)
	assert.Equal(t, filepath.Join(m.repo, "features/shell/home/.config/shell/a.sh"), dest)
	info, err := os.Lstat(m.at(".zshrc"))
	require.NoError(t, err)
	assert.True(t, info.Mode().IsRegular(), "the stub replaces a link to the tracked file")
}

func TestAFoldedDirectoryIsNotWrittenThrough(t *testing.T) {
	m := newMachine(t)
	require.NoError(t, os.MkdirAll(m.at(".config"), 0o700))
	require.NoError(t, os.Symlink(filepath.Join(m.repo, "features/shell/home/.config/shell"), m.at(".config/shell")))
	report := m.run(false)
	var paths []string
	for _, p := range report.Problems {
		paths = append(paths, p.Path)
	}
	assert.Contains(t, paths, m.at(".config/shell/a.sh"))
	entries, err := os.ReadDir(filepath.Join(m.repo, "features/shell/home/.config/shell"))
	require.NoError(t, err)
	assert.Len(t, entries, 2, "nothing was written into the repository")
}

func TestManagedCopies(t *testing.T) {
	m := newMachine(t)
	m.run(false)
	target := m.at(".config/app/settings.json")
	info, err := os.Lstat(target)
	require.NoError(t, err)
	assert.True(t, info.Mode().IsRegular(), "a copy, not a link")

	m.write("features/prefs/home/.config/app/settings.json", "{\"v\": 2}\n")
	assert.Equal(t, 1, kinds(m.run(false))["update-copy"], "an untouched copy follows the repository")

	require.NoError(t, os.WriteFile(target, []byte("edited here\n"), 0o644))
	m.write("features/prefs/home/.config/app/settings.json", "{\"v\": 3}\n")
	report := m.run(false)
	require.Len(t, report.Problems, 1)
	content, err := os.ReadFile(target)
	require.NoError(t, err)
	assert.Equal(t, "edited here\n", string(content), "a local edit is never overwritten")
}

func TestAdoptKeepsALocalEditInTheRepository(t *testing.T) {
	m := newMachine(t)
	m.run(false)
	target := m.at(".config/app/settings.json")
	source := filepath.Join(m.repo, "features/prefs/home/.config/app/settings.json")
	require.NoError(t, os.WriteFile(target, []byte("edited here\n"), 0o644))
	require.Len(t, m.run(false).Problems, 1, "a local edit is drift")

	report, next, err := Adopt(m.plan(), m.state, []string{target})
	require.NoError(t, err)
	assert.Equal(t, 1, kinds(report)["adopt"])
	m.state = next
	content, err := os.ReadFile(source)
	require.NoError(t, err)
	assert.Equal(t, "edited here\n", string(content), "the repository has the local version")

	after := m.run(false)
	assert.Empty(t, after.Problems)
	assert.Empty(t, after.Actions)

	m.write("features/prefs/home/.config/app/settings.json", "{\"v\": 2}\n")
	assert.Equal(t, 1, kinds(m.run(false))["update-copy"], "an adopted copy follows the repository again")
}

func TestAdoptRefusesAnythingButAManagedCopy(t *testing.T) {
	m := newMachine(t)
	m.run(false)
	copied := m.at(".config/app/settings.json")
	require.NoError(t, os.WriteFile(copied, []byte("edited here\n"), 0o644))
	for _, other := range []string{m.at(".config/shell/a.sh"), m.at(".config/app/unmanaged.json")} {
		_, _, err := Adopt(m.plan(), m.state, []string{copied, other})
		assert.ErrorIs(t, err, ErrNotCopy, other)
	}
	content, err := os.ReadFile(filepath.Join(m.repo, "features/prefs/home/.config/app/settings.json"))
	require.NoError(t, err)
	assert.Equal(t, "{}\n", string(content), "no source is written when any target is refused")
}

func TestLibraryFilesAreCopiesOnMacOS(t *testing.T) {
	for goos, wantLink := range map[string]bool{"linux": true, "darwin": false} {
		t.Run(goos, func(t *testing.T) {
			m := newMachine(t)
			m.goos = goos
			m.run(false)
			info, err := os.Lstat(m.at("Library/Preferences/com.example.plist"))
			require.NoError(t, err)
			assert.Equal(t, wantLink, info.Mode()&os.ModeSymlink != 0)
		})
	}
}

func TestAStubWithoutItsLineIsReportedNotEdited(t *testing.T) {
	m := newMachine(t)
	require.NoError(t, os.WriteFile(m.at(".zshrc"), []byte("# hand-written\n"), 0o644))
	report := m.run(false)
	require.Len(t, report.Problems, 1)
	assert.Contains(t, report.Problems[0].Detail, "add this line")
	content, err := os.ReadFile(m.at(".zshrc"))
	require.NoError(t, err)
	assert.Equal(t, "# hand-written\n", string(content))
}

func TestDryRunChangesNothing(t *testing.T) {
	m := newMachine(t)
	report := m.run(true)
	assert.NotEmpty(t, report.Actions)
	entries, err := os.ReadDir(m.home)
	require.NoError(t, err)
	assert.Empty(t, entries)
}
