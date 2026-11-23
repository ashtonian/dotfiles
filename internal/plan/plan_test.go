package plan

import (
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	"github.com/ashtonian/dotfiles/internal/launchd"
	"github.com/ashtonian/dotfiles/internal/manifest"
)

// feature writes files under a throwaway features/<id>/ directory and returns
// the feature with its Dir set, as manifest.LoadFeatures would.
func feature(t *testing.T, root string, f manifest.Feature, files map[string]string) *manifest.Feature {
	t.Helper()
	f.Dir = filepath.Join(root, "features", f.ID)
	for rel, content := range files {
		path := filepath.Join(f.Dir, rel)
		require.NoError(t, os.MkdirAll(filepath.Dir(path), 0o755))
		require.NoError(t, os.WriteFile(path, []byte(content), 0o644))
	}
	require.NoError(t, os.MkdirAll(f.Dir, 0o755))
	return &f
}

func generated(t *testing.T, p *Plan, name string) string {
	t.Helper()
	for _, f := range p.Generated {
		if filepath.Base(f.Path) == name {
			return string(f.Content)
		}
	}
	t.Fatalf("no generated %s", name)
	return ""
}

func TestBrewfileFollowsThePlatform(t *testing.T) {
	root := t.TempDir()
	pkgs := feature(t, root, manifest.Feature{ID: "pkgs", Provides: manifest.Provides{
		Tap:  []string{"owner/tap"},
		Brew: []string{"git", "zoxide", "owner/tap/tool", "owner/tap/linked"}, BrewLink: map[string]bool{"zoxide": false, "owner/tap/linked": false},
		Cask: []string{"iterm2", "owner/tap/app"}, Mas: []manifest.MasApp{{Name: "Things", ID: 904280696}},
		Flatpak: []string{"org.example.App"}, Vscode: []string{"golang.go"}, Go: []string{"golang.org/x/tools/gopls@latest"},
	}}, nil)
	again := feature(t, root, manifest.Feature{ID: "again", Provides: manifest.Provides{Brew: []string{"git"}}}, nil)
	features := map[string]*manifest.Feature{"pkgs": pkgs, "again": again}

	tests := []struct {
		goos          string
		want, without []string
	}{
		{"darwin", []string{`cask "iterm2" # pkgs`, `cask "owner/tap/app", trusted: true # pkgs`,
			`mas "Things", id: 904280696 # pkgs`}, []string{"flatpak"}},
		{"linux", []string{`flatpak "org.example.App" # pkgs`}, []string{"cask ", "mas "}},
	}
	for _, tt := range tests {
		t.Run(tt.goos, func(t *testing.T) {
			p, err := Build(features, []string{"pkgs", "again"}, nil, Env{Home: filepath.Join(root, "home"), GeneratedDir: filepath.Join(root, "gen"), GOOS: tt.goos})
			require.NoError(t, err)
			brewfile := generated(t, p, "Brewfile")
			for _, line := range append([]string{`tap "owner/tap" # pkgs`, `brew "git" # pkgs`, `brew "zoxide", link: false # pkgs`,
				`brew "owner/tap/tool", trusted: true # pkgs`, `brew "owner/tap/linked", link: false, trusted: true # pkgs`,
				`vscode "golang.go" # pkgs`, `go "golang.org/x/tools/gopls@latest" # pkgs`}, tt.want...) {
				assert.Contains(t, brewfile, line+"\n")
			}
			assert.NotContains(t, brewfile, `tap "owner/tap", trusted`, "trust covers the named items, never the whole tap")
			for _, absent := range tt.without {
				assert.NotContains(t, brewfile, absent)
			}
			assert.Equal(t, 1, strings.Count(brewfile, `brew "git"`), "a package two features list is installed once")
		})
	}
}

func TestTwoFeaturesCannotInstallOneFile(t *testing.T) {
	root := t.TempDir()
	files := map[string]string{"home/.config/tool/config": "x\n"}
	a := feature(t, root, manifest.Feature{ID: "a", Provides: manifest.Provides{Link: []string{".config/tool"}}}, files)
	b := feature(t, root, manifest.Feature{ID: "b", Provides: manifest.Provides{Copy: []string{".config/tool/config"}}}, files)
	_, err := Build(map[string]*manifest.Feature{"a": a, "b": b}, []string{"a", "b"}, nil,
		Env{Home: filepath.Join(root, "home"), GeneratedDir: filepath.Join(root, "gen"), GOOS: "linux"})
	require.ErrorIs(t, err, ErrPlan)
	assert.Contains(t, err.Error(), "a and b both install")
}

func TestPrefsArePlannedPerKey(t *testing.T) {
	root := t.TempDir()
	env := Env{Home: filepath.Join(root, "home"), GeneratedDir: filepath.Join(root, "gen"), GOOS: "darwin"}
	theme := feature(t, root, manifest.Feature{ID: "theme", Provides: manifest.Provides{Prefs: map[string]string{
		"muxy": "muxy.toml", "claude": "claude.toml"}}}, map[string]string{
		"muxy.toml":   "\"appearance.dark_theme\" = \"Dracula\"\n",
		"claude.toml": "theme = \"custom:dracula\"\n",
	})
	p, err := Build(map[string]*manifest.Feature{"theme": theme}, []string{"theme"}, nil, env)
	require.NoError(t, err)
	assert.Equal(t, []Pref{
		{Store: "claude", Key: "theme", Value: "custom:dracula", Feature: "theme", Source: filepath.Join(theme.Dir, "claude.toml")},
		{Store: "muxy", Key: "appearance.dark_theme", Value: "Dracula", Feature: "theme", Source: filepath.Join(theme.Dir, "muxy.toml")},
	}, p.Prefs)

	tests := []struct {
		name  string
		files map[string]string // the second feature's prefs files
		want  string
	}{
		{"two features owning one key", map[string]string{"muxy.toml": "\"appearance.dark_theme\" = \"Nord\"\n"},
			"theme and other both install muxy:appearance.dark_theme"},
		{"a whole Muxy section", map[string]string{"muxy.toml": "appearance = { dark_theme = \"Nord\" }\n"},
			"muxy: appearance is a table"},
		{"a line adopt could not rewrite", map[string]string{"muxy.toml": "[appearance]\n"}, "a table header"},
		{"a missing file", map[string]string{}, "no such file"},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			other := feature(t, t.TempDir(), manifest.Feature{ID: "other", Provides: manifest.Provides{Prefs: map[string]string{"muxy": "muxy.toml"}}}, tt.files)
			_, err := Build(map[string]*manifest.Feature{"theme": theme, "other": other}, []string{"theme", "other"}, nil, env)
			require.ErrorIs(t, err, ErrPlan)
			assert.Contains(t, err.Error(), tt.want)
		})
	}
}

func TestRetireSkipsPathsAFeatureInstalls(t *testing.T) {
	root := t.TempDir()
	home := filepath.Join(root, "home")
	now := feature(t, root, manifest.Feature{ID: "now", Provides: manifest.Provides{Link: []string{".toolrc"}}},
		map[string]string{"home/.toolrc": "x\n"})
	old := feature(t, root, manifest.Feature{ID: "old", Retire: []string{".toolrc", ".gone"}}, nil)
	p, err := Build(map[string]*manifest.Feature{"now": now, "old": old}, []string{"now"}, nil,
		Env{Home: home, GeneratedDir: filepath.Join(root, "gen"), GOOS: "linux"})
	require.NoError(t, err)
	assert.Equal(t, []string{filepath.Join(home, ".gone")}, p.Retire,
		"a disabled feature's retired paths are still retired, except one an enabled feature installs")
}

func TestSettingExports(t *testing.T) {
	root := t.TempDir()
	f := feature(t, root, manifest.Feature{ID: "env", Settings: map[string]manifest.Setting{
		"paths.cache": {Type: "path", Env: "TOOL_CACHE"},
		"tool.label":  {Type: "string", Env: "TOOL_LABEL"},
		"tool.jobs":   {Type: "int", Env: "TOOL_JOBS"},
		"tool.quiet":  {Type: "bool"},
	}}, nil)
	values := map[string]any{"paths.cache": "~/Library/Caches/it's", "tool.label": "a'b $HOME", "tool.jobs": int64(4), "tool.quiet": true}
	p, err := Build(map[string]*manifest.Feature{"env": f}, []string{"env"}, values,
		Env{Home: filepath.Join(root, "home"), GeneratedDir: filepath.Join(root, "gen"), GOOS: "darwin"})
	require.NoError(t, err)
	env := generated(t, p, "env.sh")
	assert.Contains(t, env, `[ -n "${TOOL_CACHE:-}" ] || TOOL_CACHE="$HOME"/'Library/Caches/it'\''s'; export TOOL_CACHE # paths.cache`)
	assert.Contains(t, env, `[ -n "${TOOL_LABEL:-}" ] || TOOL_LABEL='a'\''b $HOME'; export TOOL_LABEL # tool.label`)
	assert.Contains(t, env, `[ -n "${TOOL_JOBS:-}" ] || TOOL_JOBS='4'; export TOOL_JOBS # tool.jobs`)
	assert.NotContains(t, env, "tool.quiet", "a setting without an env name is not exported")
}

const agentTemplate = `<?xml version="1.0" encoding="UTF-8"?>
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.example.trim</string>
    <key>ProgramArguments</key>
    <array><string>$HOME/.dotfiles/bin/trim</string></array>
    <key>StandardOutPath</key>
    <string>$HOME/Library/Logs/trim/trim.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/trim.err</string>
</dict>
</plist>
`

func TestLaunchAgentsRenderForTheHome(t *testing.T) {
	root := t.TempDir()
	home := filepath.Join(root, "home")
	trim := feature(t, root, manifest.Feature{ID: "trim", Platforms: []string{"darwin"}, Provides: manifest.Provides{
		LaunchAgent: []manifest.LaunchAgent{{Plist: "launchagents/com.example.trim.plist",
			WhenExists: []string{"/opt/homebrew/bin/go", "~/.config/trim/on"}}},
	}}, map[string]string{"launchagents/com.example.trim.plist": agentTemplate})

	p, err := Build(map[string]*manifest.Feature{"trim": trim}, []string{"trim"}, nil, Env{Home: home, GeneratedDir: filepath.Join(home, "gen"), GOOS: "darwin"})
	require.NoError(t, err)
	require.Len(t, p.LaunchAgents, 1)
	a := p.LaunchAgents[0]
	assert.Equal(t, "com.example.trim", a.Label)
	assert.Equal(t, filepath.Join(home, "Library/LaunchAgents/com.example.trim.plist"), a.Target)
	assert.Equal(t, filepath.Join(trim.Dir, "launchagents/com.example.trim.plist"), a.Source)
	assert.Contains(t, string(a.Content), "<string>"+home+"/.dotfiles/bin/trim</string>")
	assert.NotContains(t, string(a.Content), "$HOME")
	assert.Equal(t, []string{"/opt/homebrew/bin/go", filepath.Join(home, ".config/trim/on")}, a.WhenExists)
	assert.Equal(t, []string{filepath.Join(home, "Library/Logs/trim")}, a.LogDirs, "only log directories under home are created")
	assert.False(t, a.KeepAlive)
	def, err := launchd.Definition(a.Content)
	require.NoError(t, err)
	assert.Equal(t, def, a.Definition)
}

func TestLaunchAgentsOfFeaturesOffHereAreListedForRemoval(t *testing.T) {
	root := t.TempDir()
	home := filepath.Join(root, "home")
	features := map[string]*manifest.Feature{}
	for _, id := range []string{"on", "off"} {
		label := "com.example." + id
		features[id] = feature(t, root, manifest.Feature{ID: id, Provides: manifest.Provides{
			LaunchAgent: []manifest.LaunchAgent{{Plist: label + ".plist"}},
		}}, map[string]string{label + ".plist": strings.ReplaceAll(agentTemplate, "com.example.trim", label)})
	}

	p, err := Build(features, []string{"on"}, nil, Env{Home: home, GOOS: "darwin"})
	require.NoError(t, err)
	require.Len(t, p.LaunchAgents, 1)
	assert.Equal(t, "com.example.on", p.LaunchAgents[0].Label)
	assert.Equal(t, map[string]string{"com.example.off": filepath.Join(home, "Library/LaunchAgents/com.example.off.plist")}, p.OffAgents)

	p, err = Build(features, []string{"on"}, nil, Env{Home: home, GOOS: "linux"})
	require.NoError(t, err)
	assert.Empty(t, p.LaunchAgents, "launchd is macOS's")
	assert.Empty(t, p.OffAgents)
}

func TestLaunchAgentsRefuseATemplateNamedForAnotherLabel(t *testing.T) {
	root := t.TempDir()
	tests := map[string]string{
		"another label": strings.Replace(agentTemplate, "com.example.trim</string>", "com.example.other</string>", 1),
		"not a plist":   "Label = com.example.trim\n",
	}
	for name, template := range tests {
		t.Run(name, func(t *testing.T) {
			f := feature(t, root, manifest.Feature{ID: "trim", Platforms: []string{"darwin"}, Provides: manifest.Provides{
				LaunchAgent: []manifest.LaunchAgent{{Plist: "com.example.trim.plist"}},
			}}, map[string]string{"com.example.trim.plist": template})
			_, err := Build(map[string]*manifest.Feature{"trim": f}, []string{"trim"}, nil, Env{Home: filepath.Join(root, "home"), GOOS: "darwin"})
			require.ErrorIs(t, err, ErrPlan)
		})
	}
}

func TestTwoFeaturesCannotInstallOneLaunchAgent(t *testing.T) {
	root := t.TempDir()
	features := map[string]*manifest.Feature{}
	for _, id := range []string{"one", "two"} {
		features[id] = feature(t, root, manifest.Feature{ID: id, Platforms: []string{"darwin"}, Provides: manifest.Provides{
			LaunchAgent: []manifest.LaunchAgent{{Plist: "com.example.trim.plist"}},
		}}, map[string]string{"com.example.trim.plist": agentTemplate})
	}
	_, err := Build(features, []string{"one", "two"}, nil, Env{Home: filepath.Join(root, "home"), GOOS: "darwin"})
	require.ErrorIs(t, err, ErrPlan)
	assert.Contains(t, err.Error(), "both install")
}
