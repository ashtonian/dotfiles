package apply

import (
	"context"
	"os"
	"path/filepath"
	"strings"
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
	tracked               map[string]bool // repository paths git tracks, slash-separated
}

func newMachine(t *testing.T) *machine {
	t.Helper()
	root := t.TempDir()
	m := &machine{t: t, repo: filepath.Join(root, "repo"), home: filepath.Join(root, "home"),
		goos: "linux", state: newState(), tracked: map[string]bool{}}
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
	p, err := plan.Build(features, res.Runnable(features), res.Values(), plan.Env{Home: m.home, GeneratedDir: m.generated, GOOS: m.goos})
	require.NoError(m.t, err)
	return p
}

func (m *machine) run(dryRun bool) *Report {
	m.t.Helper()
	report, next, err := Run(context.Background(), m.plan(), m.state, Env{Home: m.home, RepoRoot: m.repo, StowTree: filepath.Join(m.repo, "stow"),
		Tracked: func(rel string) bool { return m.tracked[filepath.ToSlash(rel)] }}, dryRun)
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

func TestAFoldedDirectoryIsUnfoldedAndToolFilesMoveHome(t *testing.T) {
	for _, dryRun := range []bool{true, false} {
		m := newMachine(t)
		// An old stow package folded ~/.config/shell into the repository, and a
		// tool wrote a machine-local file through it beside a tracked one.
		old := filepath.Join(m.repo, "stow/shell/.config/shell")
		require.NoError(t, os.MkdirAll(filepath.Join(old, "state"), 0o755))
		require.NoError(t, os.WriteFile(filepath.Join(old, "state/hosts.yml"), []byte("token\n"), 0o600))
		m.write("stow/shell/.config/shell/tracked.sh", "tracked\n")
		m.tracked["stow/shell/.config/shell/tracked.sh"] = true
		require.NoError(t, os.MkdirAll(m.at(".config"), 0o700))
		require.NoError(t, os.Symlink(old, m.at(".config/shell")))

		report := m.run(dryRun)
		assert.Empty(t, report.Problems)
		assert.Equal(t, 1, kinds(report)["unfold"])
		assert.Equal(t, 1, kinds(report)["move-home"])
		var shellLinks int
		for _, a := range report.Actions {
			if a.Kind == "link" && filepath.Dir(filepath.Dir(a.Path)) != m.home && strings.HasPrefix(a.Path, m.at(".config/shell")+"/") {
				shellLinks++
			}
		}
		assert.Equal(t, 2, shellLinks, "both tracked files are linked into the new directory")
		if dryRun {
			assert.FileExists(t, filepath.Join(old, "state/hosts.yml"), "a dry run moves nothing")
			continue
		}
		info, err := os.Lstat(m.at(".config/shell"))
		require.NoError(t, err)
		assert.True(t, info.IsDir())
		content, err := os.ReadFile(m.at(".config/shell/state/hosts.yml"))
		require.NoError(t, err)
		assert.Equal(t, "token\n", string(content))
		assert.NoDirExists(t, filepath.Join(old, "state"), "nothing machine-local stays in the repository")
		assert.DirExists(t, old, "the tracked file keeps its directory")
		assert.FileExists(t, filepath.Join(old, "tracked.sh"), "a tracked file never leaves the repository")
		assert.NoFileExists(t, m.at(".config/shell/tracked.sh"), "and no feature installs it")
		assert.Empty(t, m.run(false).Actions)
	}
}

func TestStowLeftoversMoveHome(t *testing.T) {
	for _, dryRun := range []bool{true, false} {
		m := newMachine(t)
		// An older sync linked an untracked package file one by one, and left
		// another one nothing links to.
		left := filepath.Join(m.repo, "stow/tools/.local/bin/othertool")
		orphan := filepath.Join(m.repo, "stow/tools/.orphan")
		finder := filepath.Join(m.repo, "stow/tools/.local/.DS_Store")
		for _, f := range []string{left, orphan, finder} {
			require.NoError(t, os.MkdirAll(filepath.Dir(f), 0o755))
			require.NoError(t, os.WriteFile(f, []byte("mine\n"), 0o755))
		}
		require.NoError(t, os.MkdirAll(m.at(".local/bin"), 0o700))
		require.NoError(t, os.Symlink(left, m.at(".local/bin/othertool")))

		report := m.run(dryRun)
		assert.Equal(t, 1, kinds(report)["move-home"])
		assert.Equal(t, 1, kinds(report)["remove"], "Finder's .DS_Store is removed, not reported")
		require.Len(t, report.Problems, 1)
		assert.Equal(t, orphan, report.Problems[0].Path)
		assert.FileExists(t, orphan, "data nothing installs is reported, never deleted")
		if dryRun {
			assert.FileExists(t, left, "a dry run moves nothing")
			continue
		}
		info, err := os.Lstat(m.at(".local/bin/othertool"))
		require.NoError(t, err)
		assert.True(t, info.Mode().IsRegular(), "the link became the file")
		assert.Equal(t, os.FileMode(0o755), info.Mode().Perm())
		assert.NoFileExists(t, left)
		assert.NoDirExists(t, filepath.Join(m.repo, "stow/tools/.local"), "emptied directories are removed")
	}
}

func TestStubLinePosition(t *testing.T) {
	tests := []struct {
		name, existing, problem string
	}{
		{"before the first host", "IgnoreUnknown UseKeychain\nInclude dotfiles.conf\nHost a\n", ""},
		{"after a host block", "Host a\n  User b\nInclude dotfiles.conf\n", "move this line before the first Host or Match line"},
		{"missing", "match host a\n  User b\n", "add this line before the first Host or Match line"},
		{"only in a comment", "# Include dotfiles.conf\n", "add this line"},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			m := newMachine(t)
			m.write("features/ssh/feature.toml", `id = "ssh"
default = true
[provides]
stub = [{ path = ".ssh/config", line = "Include dotfiles.conf", before = ["Host", "Match"] }]
`)
			require.NoError(t, os.MkdirAll(m.at(".ssh"), 0o700))
			require.NoError(t, os.WriteFile(m.at(".ssh/config"), []byte(tt.existing), 0o600))
			report := m.run(false)
			if tt.problem == "" {
				assert.Empty(t, report.Problems)
				return
			}
			require.Len(t, report.Problems, 1)
			assert.Contains(t, report.Problems[0].Detail, tt.problem)
		})
	}
}

func TestAKeptStubLeavesAnExistingFileAlone(t *testing.T) {
	m := newMachine(t)
	m.write("features/git/feature.toml", `id = "git"
default = true
[provides]
stub = [{ path = ".gitconfig", line = "# machine-local", keep_existing = true }]
`)
	require.NoError(t, os.WriteFile(m.at(".gitconfig"), []byte("[user]\n\tname = Someone\n"), 0o644))
	assert.Empty(t, m.run(false).Problems)
	content, err := os.ReadFile(m.at(".gitconfig"))
	require.NoError(t, err)
	assert.Equal(t, "[user]\n\tname = Someone\n", string(content))

	require.NoError(t, os.Remove(m.at(".gitconfig")))
	m.run(false)
	content, err = os.ReadFile(m.at(".gitconfig"))
	require.NoError(t, err)
	assert.Equal(t, "# machine-local\n", string(content), "a missing one is still created")
}

func TestRetiredLinksAreRemoved(t *testing.T) {
	m := newMachine(t)
	m.write("features/shell/feature.toml", `id = "shell"
default = true
retire = [".gitconfig.local.example", ".mine"]
[provides]
link = [".config/shell"]
`)
	require.NoError(t, os.Symlink(filepath.Join(m.repo, "stow/git/.gitconfig.local.example"), m.at(".gitconfig.local.example")))
	require.NoError(t, os.Symlink("/elsewhere", m.at(".mine")))
	report := m.run(false)
	assert.Equal(t, 1, kinds(report)["retire"])
	_, err := os.Lstat(m.at(".gitconfig.local.example"))
	assert.ErrorIs(t, err, os.ErrNotExist)
	_, err = os.Lstat(m.at(".mine"))
	assert.NoError(t, err, "a link that does not point into the repository is the owner's")
}

func TestARetiredPathUnderAFoldedDirectoryUnfoldsIt(t *testing.T) {
	m := newMachine(t)
	m.write("features/neofetch/feature.toml", `id = "neofetch"
retire = [".config/neofetch/config.conf"]
[provides]
link = [".config/neofetch"]
`)
	m.write("features/neofetch/home/.config/neofetch/config.conf", "layout\n")
	// The feature is off, and its old package folded the directory; the tracked
	// file behind it is already gone, and a tool left a cache file.
	old := filepath.Join(m.repo, "stow/neofetch/.config/neofetch")
	require.NoError(t, os.MkdirAll(old, 0o755))
	require.NoError(t, os.WriteFile(filepath.Join(old, "cache"), []byte("c\n"), 0o600))
	require.NoError(t, os.MkdirAll(m.at(".config"), 0o700))
	require.NoError(t, os.Symlink("../../repo/stow/neofetch/.config/neofetch", m.at(".config/neofetch")))

	report := m.run(false)
	assert.Empty(t, report.Problems)
	assert.Equal(t, 1, kinds(report)["unfold"])
	info, err := os.Lstat(m.at(".config/neofetch"))
	require.NoError(t, err)
	assert.True(t, info.IsDir(), "the folded link is gone")
	assert.FileExists(t, m.at(".config/neofetch/cache"))
	assert.NoFileExists(t, m.at(".config/neofetch/config.conf"), "a disabled feature installs nothing")
	assert.NoDirExists(t, filepath.Join(m.repo, "stow"), "the emptied package tree is gone")
	assert.DirExists(t, m.repo)
}

func TestGeneratedOutputs(t *testing.T) {
	m := newMachine(t)
	m.write("features/tools/feature.toml", `id = "tools"
default = true
[provides]
vscode = ["golang.go"]
go = ["golang.org/x/tools/gopls"]
[settings."paths.cache"]
type = "path"
default = "~/Library/Caches/tool"
env = "TOOL_CACHE"
`)
	m.run(false)
	brewfile, err := os.ReadFile(filepath.Join(m.generated, "Brewfile"))
	require.NoError(t, err)
	assert.Contains(t, string(brewfile), `vscode "golang.go" # tools`)
	assert.Contains(t, string(brewfile), `go "golang.org/x/tools/gopls" # tools`)
	env, err := os.ReadFile(filepath.Join(m.generated, "env.sh"))
	require.NoError(t, err)
	assert.Contains(t, string(env), `[ -n "${TOOL_CACHE:-}" ] || TOOL_CACHE="$HOME"/'Library/Caches/tool'; export TOOL_CACHE # paths.cache`)
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
