package plan

import (
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

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
		Tap: []string{"owner/tap"}, Brew: []string{"git", "zoxide"},
		Cask: []string{"iterm2"}, Mas: []manifest.MasApp{{Name: "Things", ID: 904280696}},
		Flatpak: []string{"org.example.App"},
	}}, nil)
	again := feature(t, root, manifest.Feature{ID: "again", Provides: manifest.Provides{Brew: []string{"git"}}}, nil)
	features := map[string]*manifest.Feature{"pkgs": pkgs, "again": again}

	tests := []struct {
		goos          string
		want, without []string
	}{
		{"darwin", []string{`cask "iterm2" # pkgs`, `mas "Things", id: 904280696 # pkgs`}, []string{"flatpak"}},
		{"linux", []string{`flatpak "org.example.App" # pkgs`}, []string{"cask ", "mas "}},
	}
	for _, tt := range tests {
		t.Run(tt.goos, func(t *testing.T) {
			p, err := Build(features, []string{"pkgs", "again"}, Env{Home: filepath.Join(root, "home"), GeneratedDir: filepath.Join(root, "gen"), GOOS: tt.goos})
			require.NoError(t, err)
			brewfile := generated(t, p, "Brewfile")
			for _, line := range append([]string{`tap "owner/tap" # pkgs`, `brew "zoxide" # pkgs`}, tt.want...) {
				assert.Contains(t, brewfile, line+"\n")
			}
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
	_, err := Build(map[string]*manifest.Feature{"a": a, "b": b}, []string{"a", "b"},
		Env{Home: filepath.Join(root, "home"), GeneratedDir: filepath.Join(root, "gen"), GOOS: "linux"})
	require.ErrorIs(t, err, ErrPlan)
	assert.Contains(t, err.Error(), "a and b both install")
}
