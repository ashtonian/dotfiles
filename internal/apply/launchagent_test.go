package apply

import (
	"context"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	"github.com/ashtonian/dotfiles/internal/launchd"
)

// fakeLaunchd is a GUI domain in memory: the plist each loaded label was
// bootstrapped from, and which labels have a process.
type fakeLaunchd struct {
	loaded   map[string]string
	running  map[string]bool
	calls    []string
	loadErr  error
	stateErr error
}

func newFakeLaunchd() *fakeLaunchd {
	return &fakeLaunchd{loaded: map[string]string{}, running: map[string]bool{}}
}

func (f *fakeLaunchd) State(_ context.Context, label string) (launchd.State, error) {
	if f.stateErr != nil {
		return launchd.State{}, f.stateErr
	}
	_, loaded := f.loaded[label]
	return launchd.State{Loaded: loaded, Running: loaded && f.running[label]}, nil
}

func (f *fakeLaunchd) Load(_ context.Context, path string) error {
	label := strings.TrimSuffix(filepath.Base(path), ".plist")
	f.calls = append(f.calls, "load "+label)
	if f.loadErr != nil {
		return f.loadErr
	}
	content, err := os.ReadFile(path)
	if err != nil {
		return err
	}
	f.loaded[label] = string(content)
	return nil
}

func (f *fakeLaunchd) Unload(_ context.Context, label string) error {
	f.calls = append(f.calls, "unload "+label)
	delete(f.loaded, label)
	return nil
}

func (f *fakeLaunchd) takeCalls() []string {
	calls := f.calls
	f.calls = nil
	return calls
}

// agentPlist is a LaunchAgent template; body adds keys to its dictionary.
func agentPlist(label, body string) string {
	return fmt.Sprintf(`<?xml version="1.0" encoding="UTF-8"?>
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>%s</string>
    <key>ProgramArguments</key>
    <array><string>$HOME/.dotfiles/bin/job</string></array>
    <key>StandardOutPath</key>
    <string>$HOME/Library/Logs/%s/out.log</string>
%s</dict>
</plist>
`, label, label, body)
}

const keepAlive = "    <key>KeepAlive</key>\n    <true/>\n"

// newAgentMachine is a macOS machine with a feature "jobs" that installs
// com.example.trim, a job that runs and exits, and com.example.server, a
// service launchd keeps alive.
func newAgentMachine(t *testing.T) *machine {
	t.Helper()
	m := newMachine(t)
	m.goos = "darwin"
	m.launchd = newFakeLaunchd()
	m.write("features/jobs/feature.toml", `id = "jobs"
default = true
[[provides.launch_agent]]
plist = "launchagents/com.example.trim.plist"
[[provides.launch_agent]]
plist = "launchagents/com.example.server.plist"
`)
	m.write("features/jobs/launchagents/com.example.trim.plist", agentPlist("com.example.trim", ""))
	m.write("features/jobs/launchagents/com.example.server.plist", agentPlist("com.example.server", keepAlive))
	return m
}

// agentKinds counts a report's LaunchAgent actions; the machine's other
// features act on a first run too.
func agentKinds(r *Report) map[string]int {
	k := map[string]int{}
	for _, a := range r.Actions {
		if strings.Contains(a.Path, "/Library/LaunchAgents/") {
			k[a.Kind]++
		}
	}
	return k
}

func (m *machine) agent(label string) string {
	return m.at("Library/LaunchAgents/" + label + ".plist")
}

func (m *machine) installed(label string) string {
	m.t.Helper()
	content, err := os.ReadFile(m.agent(label))
	require.NoError(m.t, err)
	return string(content)
}

func TestLaunchAgentsAreInstalledLoadedAndLeftRunning(t *testing.T) {
	m := newAgentMachine(t)
	first := m.run(false)
	assert.Empty(t, first.Problems)
	assert.Equal(t, map[string]int{"agent": 2, "load": 2}, agentKinds(first))
	assert.ElementsMatch(t, []string{"load com.example.trim", "load com.example.server"}, m.launchd.takeCalls())

	content := m.installed("com.example.trim")
	assert.Contains(t, content, "<string>"+m.home+"/.dotfiles/bin/job</string>", "$HOME is the home directory")
	assert.Equal(t, content, m.launchd.loaded["com.example.trim"], "launchd loaded the installed plist")
	assert.DirExists(t, m.at("Library/Logs/com.example.trim"), "launchd does not create log directories")
	def, err := launchd.Definition([]byte(content))
	require.NoError(t, err)
	assert.Equal(t, def, m.state.Agents["com.example.trim"].Loaded)

	second := m.run(false)
	assert.Empty(t, second.Actions, "a second run changes nothing")
	assert.Empty(t, m.launchd.takeCalls())
}

func TestAChangedTemplateReloadsTheAgent(t *testing.T) {
	m := newAgentMachine(t)
	m.run(false)
	m.launchd.takeCalls()

	m.write("features/jobs/launchagents/com.example.trim.plist", agentPlist("com.example.trim", "    <key>Nice</key>\n    <integer>10</integer>\n"))
	report := m.run(false)
	assert.Equal(t, map[string]int{"update-agent": 1, "reload": 1}, kinds(report))
	assert.Equal(t, []string{"unload com.example.trim", "load com.example.trim"}, m.launchd.takeCalls())
	assert.Contains(t, m.launchd.loaded["com.example.trim"], "<key>Nice</key>")
}

func TestACommentOnlyChangeRewritesThePlistWithoutAReload(t *testing.T) {
	m := newAgentMachine(t)
	m.run(false)
	m.launchd.takeCalls()

	m.write("features/jobs/launchagents/com.example.server.plist",
		strings.Replace(agentPlist("com.example.server", keepAlive), "<dict>", "<!-- what it does -->\n<dict>", 1))
	report := m.run(false)
	assert.Equal(t, map[string]int{"update-agent": 1}, kinds(report))
	assert.Empty(t, m.launchd.takeCalls(), "a reload would restart the service for nothing")
	assert.Contains(t, m.installed("com.example.server"), "what it does")
	assert.Empty(t, m.run(false).Actions)
}

func TestAJobUnloadedByHandIsLoadedAgain(t *testing.T) {
	m := newAgentMachine(t)
	m.run(false)
	delete(m.launchd.loaded, "com.example.trim")
	report := m.run(false)
	assert.Equal(t, map[string]int{"load": 1}, kinds(report), "disabling it is the machine manifest's job")
}

func TestAReloadWaitsUntilItWouldNotCutARunShort(t *testing.T) {
	changed := func(m *machine) {
		m.write("features/jobs/launchagents/com.example.trim.plist", agentPlist("com.example.trim", "    <key>Nice</key>\n    <integer>10</integer>\n"))
		m.write("features/jobs/launchagents/com.example.server.plist", agentPlist("com.example.server", keepAlive+"    <key>Nice</key>\n    <integer>10</integer>\n"))
	}

	t.Run("the job apply runs in", func(t *testing.T) {
		m := newAgentMachine(t)
		m.run(false)
		m.launchd.takeCalls()
		changed(m)
		m.job = "com.example.trim"
		m.launchd.running["com.example.trim"] = true
		report := m.run(false)
		assert.Equal(t, []string{"unload com.example.server", "load com.example.server"}, m.launchd.takeCalls())
		assert.Contains(t, m.installed("com.example.trim"), "<key>Nice</key>", "the new plist is written")
		assert.Contains(t, report.Waiting, Waiting{Label: "com.example.trim", Reason: "reloads when apply next runs outside this job, which it is running in"})

		m.job = ""
		m.launchd.running["com.example.trim"] = false
		report = m.run(false)
		assert.Equal(t, map[string]int{"reload": 1}, kinds(report), "the next run outside the job reloads it")
		assert.Contains(t, m.launchd.loaded["com.example.trim"], "<key>Nice</key>")
	})

	t.Run("a job in the middle of a run", func(t *testing.T) {
		m := newAgentMachine(t)
		m.run(false)
		m.launchd.takeCalls()
		changed(m)
		m.launchd.running["com.example.trim"] = true
		m.launchd.running["com.example.server"] = true
		report := m.run(false)
		assert.Equal(t, []string{"unload com.example.server", "load com.example.server"}, m.launchd.takeCalls(),
			"a running service restarts on its new plist; a running job finishes first")
		assert.Contains(t, report.Waiting, Waiting{Label: "com.example.trim", Reason: "reloads once its current run ends"})

		m.launchd.running["com.example.trim"] = false
		report = m.run(false)
		assert.Equal(t, map[string]int{"reload": 1}, kinds(report))
		assert.Empty(t, report.Waiting)
	})
}

func TestAnAgentWaitsForWhatItNeeds(t *testing.T) {
	m := newAgentMachine(t)
	m.write("features/jobs/feature.toml", `id = "jobs"
default = true
[[provides.launch_agent]]
plist = "launchagents/com.example.trim.plist"
when_exists = ["~/.config/trim/enabled"]
`)
	report := m.run(false)
	assert.Empty(t, agentKinds(report))
	assert.Equal(t, []Waiting{{Label: "com.example.trim", Reason: "installs once " + m.at(".config/trim/enabled") + " exists"}}, report.Waiting)
	assert.NoFileExists(t, m.agent("com.example.trim"))

	require.NoError(t, os.MkdirAll(m.at(".config/trim"), 0o700))
	require.NoError(t, os.WriteFile(m.at(".config/trim/enabled"), nil, 0o600))
	report = m.run(false)
	assert.Equal(t, map[string]int{"agent": 1, "load": 1}, kinds(report))

	require.NoError(t, os.Remove(m.at(".config/trim/enabled")))
	report = m.run(false)
	assert.Equal(t, map[string]int{"unload": 1, "remove-agent": 1}, kinds(report), "an agent whose condition goes away goes too")
	assert.NoFileExists(t, m.agent("com.example.trim"))
	assert.NotContains(t, m.launchd.loaded, "com.example.trim")
	assert.NotContains(t, m.state.Agents, "com.example.trim")
}

func TestDisablingAFeatureUnloadsAndRemovesItsAgents(t *testing.T) {
	m := newAgentMachine(t)
	m.run(false)
	m.launchd.takeCalls()

	m.disable = []string{"jobs"}
	m.launchd.running["com.example.trim"] = true
	report := m.run(false)
	assert.Equal(t, []string{"unload com.example.server"}, m.launchd.takeCalls(), "a job in the middle of a run is unloaded later")
	assert.Contains(t, report.Waiting, Waiting{Label: "com.example.trim", Reason: "unloads once its current run ends"})
	assert.FileExists(t, m.agent("com.example.trim"))
	assert.NoFileExists(t, m.agent("com.example.server"))

	m.launchd.running["com.example.trim"] = false
	report = m.run(false)
	assert.Equal(t, map[string]int{"unload": 1, "remove-agent": 1}, kinds(report))
	assert.NoFileExists(t, m.agent("com.example.trim"))
	assert.Empty(t, m.state.Agents)
}

func TestTheRetiredInstallersAgentsAreTakenOver(t *testing.T) {
	m := newAgentMachine(t)
	m.write("features/off/feature.toml", "id = \"off\"\n[[provides.launch_agent]]\nplist = \"com.example.off.plist\"\n")
	m.write("features/off/com.example.off.plist", agentPlist("com.example.off", ""))
	render := func(label, body string) string {
		return strings.ReplaceAll(agentPlist(label, body), "$HOME", m.home)
	}
	install := func(label, content string) {
		require.NoError(t, os.MkdirAll(filepath.Dir(m.agent(label)), 0o755))
		require.NoError(t, os.WriteFile(m.agent(label), []byte(content), 0o644))
		m.launchd.loaded[label] = content
	}
	install("com.example.trim", "<!-- the old header -->\n"+render("com.example.trim", "")) // the template's job, older comments
	install("com.example.server", render("com.example.server", ""))
	install("com.example.off", render("com.example.off", ""))

	report := m.run(false)
	assert.Empty(t, report.Problems)
	assert.Equal(t, []string{"unload com.example.server", "load com.example.server", "unload com.example.off"}, m.launchd.takeCalls(),
		"a copy defining the template's job stays loaded, a stale one reloads, and a disabled feature's goes")
	assert.Equal(t, map[string]int{"update-agent": 2, "reload": 1, "unload": 1, "remove-agent": 1}, agentKinds(report))
	assert.NotContains(t, m.installed("com.example.trim"), "the old header")
	assert.NoFileExists(t, m.agent("com.example.off"))
	assert.Contains(t, m.state.Agents, "com.example.trim")
	assert.Contains(t, m.installed("com.example.server"), "<key>KeepAlive</key>")
}

func TestAnEditedAgentIsLeftAlone(t *testing.T) {
	m := newAgentMachine(t)
	m.run(false)
	m.launchd.takeCalls()
	edited := strings.Replace(m.installed("com.example.trim"), "</dict>", "<key>Nice</key><integer>5</integer></dict>", 1)
	require.NoError(t, os.WriteFile(m.agent("com.example.trim"), []byte(edited), 0o644))

	m.write("features/jobs/launchagents/com.example.trim.plist", agentPlist("com.example.trim", "    <key>Nice</key>\n    <integer>10</integer>\n"))
	report := m.run(false)
	require.Len(t, report.Problems, 1)
	assert.Contains(t, report.Problems[0].Detail, "edited here since dotfiles last wrote it")
	assert.Equal(t, edited, m.installed("com.example.trim"))
	assert.Empty(t, m.launchd.takeCalls())

	m.disable = []string{"jobs"}
	report = m.run(false)
	assert.Equal(t, edited, m.installed("com.example.trim"), "nor removed once its feature is off")
	assert.Contains(t, m.launchd.loaded, "com.example.trim")
}

func TestALaunchdFailureIsAProblemAndTheNextRunRetries(t *testing.T) {
	m := newAgentMachine(t)
	m.launchd.loadErr = errors.New("launchctl bootstrap gui/501 x: exit status 5: Input/output error")
	report := m.run(false)
	assert.Len(t, report.Problems, 2)
	assert.FileExists(t, m.agent("com.example.trim"), "the plist is in place for launchd at the next login")

	m.launchd.loadErr = nil
	report = m.run(false)
	assert.Equal(t, map[string]int{"load": 2}, kinds(report))

	m.launchd.stateErr = errors.New("launchctl print: signal: killed")
	m.write("features/jobs/launchagents/com.example.trim.plist", agentPlist("com.example.trim", "    <key>Nice</key>\n    <integer>10</integer>\n"))
	report = m.run(false)
	assert.Len(t, report.Problems, 2)
	assert.Contains(t, m.state.Agents, "com.example.trim", "the record stays until launchd answers")
}

func TestDryRunTouchesNeitherAgentsNorLaunchd(t *testing.T) {
	m := newAgentMachine(t)
	report := m.run(true)
	assert.Equal(t, map[string]int{"agent": 2, "load": 2}, agentKinds(report))
	assert.NoFileExists(t, m.agent("com.example.trim"))
	assert.NoDirExists(t, m.at("Library/Logs/com.example.trim"))
	assert.Empty(t, m.launchd.takeCalls())
}

func TestLaunchAgentsAreForMacOSOnly(t *testing.T) {
	m := newAgentMachine(t)
	m.goos = "linux"
	m.launchd = nil
	report := m.run(false)
	assert.Empty(t, report.Problems)
	assert.NoFileExists(t, m.agent("com.example.trim"))
}

func TestLeavingLaunchAgentsKeepsTheirRecords(t *testing.T) {
	m := newAgentMachine(t)
	m.run(false)
	m.launchd.takeCalls()
	before := m.state.Agents

	m.disable = []string{"jobs"}
	report, next, err := Run(context.Background(), m.plan(), m.state, Env{Home: m.home, RepoRoot: m.repo,
		Tracked: func(string) bool { return false }, LeaveLaunchAgents: true}, false)
	require.NoError(t, err)
	assert.Empty(t, agentKinds(report))
	assert.Equal(t, before, next.Agents)
	assert.FileExists(t, m.agent("com.example.trim"))
}
