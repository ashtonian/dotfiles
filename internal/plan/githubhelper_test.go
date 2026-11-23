package plan

import (
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	"github.com/ashtonian/dotfiles/internal/manifest"
	"github.com/ashtonian/dotfiles/internal/resolve"
)

// TestGitHubCredentialsComeFromGh runs git against the base profile's generated
// git config on macOS, with gh and the keychain helper replaced by recorders.
// GitHub's credentials are read and stored through gh alone: the keychain
// helper is never asked, since an SSH session can't read the locked login
// keychain. Every other host keeps the keychain.
func TestGitHubCredentialsComeFromGh(t *testing.T) {
	gitBin, err := exec.LookPath("git")
	if err != nil {
		t.Skip("git is not installed")
	}
	repo, err := filepath.Abs(filepath.Join("..", ".."))
	require.NoError(t, err)
	features, err := manifest.LoadFeatures(manifest.Root{Dir: repo})
	require.NoError(t, err)
	profiles, err := manifest.LoadProfiles(manifest.Root{Dir: repo})
	require.NoError(t, err)
	result, err := resolve.Resolve(features, profiles, &manifest.Machine{Profiles: []string{"base"}}, "darwin")
	require.NoError(t, err)
	root := t.TempDir()
	p, err := Build(features, result.Runnable(features), result.Values(),
		Env{Home: filepath.Join(root, "home"), GeneratedDir: filepath.Join(root, "gen"), GOOS: "darwin"})
	require.NoError(t, err)
	gitconfig := filepath.Join(root, "gitconfig")
	require.NoError(t, os.WriteFile(gitconfig, []byte(generated(t, p, "gitconfig")), 0o644))

	bin := filepath.Join(root, "bin")
	require.NoError(t, os.MkdirAll(bin, 0o755))
	calls := filepath.Join(root, "calls")
	recorder := func(name, op string) string {
		return "#!/bin/sh\necho \"" + name + " " + op + "\" >> \"$CALLS\"\ncat >/dev/null\n" +
			"if [ \"" + op + "\" = get ]; then printf 'username=" + name + "\\npassword=secret\\n'; fi\n"
	}
	// gh is called as `gh auth git-credential <op>`, the keychain helper as
	// `git-credential-osxkeychain <op>`; each script records the op it got.
	require.NoError(t, os.WriteFile(filepath.Join(bin, "gh"), []byte(recorder("gh", "$3")), 0o755))
	require.NoError(t, os.WriteFile(filepath.Join(bin, "git-credential-osxkeychain"),
		[]byte(recorder("osxkeychain", "$1")), 0o755))

	git := func(stdin string, args ...string) string {
		cmd := exec.Command(gitBin, args...)
		cmd.Env = []string{
			"HOME=" + filepath.Join(root, "home"),
			"PATH=" + bin + ":/usr/bin:/bin",
			"GIT_EXEC_PATH=" + bin,
			"GIT_CONFIG_NOSYSTEM=1",
			"GIT_CONFIG_GLOBAL=" + gitconfig,
			"GIT_TERMINAL_PROMPT=0",
			"CALLS=" + calls,
		}
		cmd.Stdin = strings.NewReader(stdin)
		out, _ := cmd.Output()
		return string(out)
	}
	recorded := func() []string {
		data, err := os.ReadFile(calls)
		if os.IsNotExist(err) {
			return nil
		}
		require.NoError(t, err)
		require.NoError(t, os.Remove(calls))
		return strings.Split(strings.TrimSpace(string(data)), "\n")
	}

	for _, host := range []string{"github.com", "gist.github.com"} {
		filled := git("protocol=https\nhost="+host+"\n\n", "credential", "fill")
		assert.Contains(t, filled, "username=gh", host)
		git("protocol=https\nhost="+host+"\nusername=gh\npassword=secret\n\n", "credential", "approve")
		assert.Equal(t, []string{"gh get", "gh store"}, recorded(), "%s asks gh alone", host)
	}

	filled := git("protocol=https\nhost=example.com\n\n", "credential", "fill")
	assert.Contains(t, filled, "username=osxkeychain")
	assert.Equal(t, []string{"osxkeychain get"}, recorded(), "another host keeps the keychain")
}
