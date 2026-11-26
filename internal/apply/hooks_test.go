package apply

import (
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

// script writes an executable script into the repository.
func (m *machine) script(rel, body string) {
	m.t.Helper()
	m.write(rel, "#!/bin/sh\n"+body)
	require.NoError(m.t, os.Chmod(filepath.Join(m.repo, rel), 0o755))
}

// withConvergingHook gives the machine a "tool" feature whose check reports
// drift until $HOME/.tool-ok exists, and whose apply hook creates it, counting
// its runs in $HOME/.tool-runs.
func (m *machine) withConvergingHook(hooks string) {
	m.write("features/tool/feature.toml", "id = \"tool\"\ndefault = true\n[hooks]\napply = \"apply.sh\"\n"+hooks+"[check]\nscript = \"check.sh\"\n")
	m.script("features/tool/check.sh", `if [ -f "$HOME/.tool-ok" ]; then echo '{"state": "ok", "detail": ""}'
else echo '{"state": "drift", "detail": "not converged"}'; fi
`)
	m.script("features/tool/apply.sh", `touch "$HOME/.tool-ok"; echo run >> "$HOME/.tool-runs"
`)
}

func (m *machine) runs(name string) int {
	m.t.Helper()
	data, err := os.ReadFile(m.at(name))
	if os.IsNotExist(err) {
		return 0
	}
	require.NoError(m.t, err)
	return strings.Count(string(data), "run\n")
}

func problemsOf(r *Report, subject string) []string {
	var out []string
	for _, p := range r.Problems {
		if p.Path == subject {
			out = append(out, p.Detail)
		}
	}
	return out
}

func TestAHookRunsOnlyWhileItsCheckReportsDrift(t *testing.T) {
	m := newMachine(t)
	m.withConvergingHook("")

	dry := m.run(true)
	assert.Equal(t, 1, kinds(dry)["hook"], "a dry run reports the hook it would run")
	assert.Zero(t, m.runs(".tool-runs"), "and runs nothing")

	first := m.run(false)
	assert.Empty(t, first.Problems)
	require.Equal(t, 1, kinds(first)["hook"])
	for _, a := range first.Actions {
		if a.Kind == "hook" {
			assert.Equal(t, "tool", a.Path)
			assert.Equal(t, "drift: not converged", a.Detail, "the action says what the check found")
		}
	}
	assert.Equal(t, 1, m.runs(".tool-runs"))

	second := m.run(false)
	assert.Empty(t, second.Actions, "a check that reports ok runs no hook")
	assert.Equal(t, 1, m.runs(".tool-runs"))
}

func TestAHookThatDoesNotConvergeIsAProblem(t *testing.T) {
	m := newMachine(t)
	m.withConvergingHook("")
	m.script("features/tool/apply.sh", "echo run >> \"$HOME/.tool-runs\"\n")

	report := m.run(false)
	assert.Equal(t, []string{"hooks.apply ran, and the check still reports drift: not converged"}, problemsOf(report, "tool"))
	assert.Zero(t, kinds(report)["hook"])
}

func TestASudoHookRunsOnlyFromApplySudo(t *testing.T) {
	m := newMachine(t)
	m.withConvergingHook("sudo = true\n")
	m.script("features/tool/apply.sh", `read -r line; echo "$line" > "$HOME/.tool-stdin"; touch "$HOME/.tool-ok"; echo run >> "$HOME/.tool-runs"
`)

	unattended := m.run(false)
	assert.Equal(t, []string{"drift: not converged; run `dotfiles apply --sudo`"}, problemsOf(unattended, "tool"))
	assert.Zero(t, m.runs(".tool-runs"))

	m.sudo, m.stdin = true, strings.NewReader("password\n")
	report := m.run(false)
	assert.Empty(t, report.Problems)
	assert.Equal(t, 1, m.runs(".tool-runs"))
	stdin, err := os.ReadFile(m.at(".tool-stdin"))
	require.NoError(t, err)
	assert.Equal(t, "password\n", string(stdin), "a sudo hook reads the owner's terminal")
}

func TestABrokenCheckIsAProblem(t *testing.T) {
	tests := []struct {
		name, check, timeout, want string
	}{
		{"output that is not JSON", "echo fine", "", `check.script printed "fine\n", not one JSON object`},
		{"an unknown state", `echo '{"state": "great", "detail": ""}'`, "", `reported state "great"`},
		{"an unknown field", `echo '{"state": "ok", "detail": "", "extra": 1}'`, "", "not one JSON object"},
		{"two objects", `echo '{"state": "ok", "detail": ""} {"state": "ok", "detail": ""}'`, "", "more than one JSON object"},
		{"a failing exit", "exit 3", "", "check.script exited with status 3"},
		{"a check that hangs", "exec sleep 5", "timeout = \"200ms\"\n", "check.script did not finish within 200ms"},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			m := newMachine(t)
			m.write("features/tool/feature.toml", "id = \"tool\"\ndefault = true\n[check]\nscript = \"check.sh\"\n"+tt.timeout)
			m.script("features/tool/check.sh", tt.check+"\n")
			report := m.run(false)
			problems := problemsOf(report, "tool")
			require.Len(t, problems, 1)
			assert.Contains(t, problems[0], tt.want)
		})
	}
}

func TestHooksSeeTheirSettingsAndHome(t *testing.T) {
	m := newMachine(t)
	m.write("features/tool/feature.toml", `id = "tool"
default = true
[check]
script = "check.sh"
[settings."tool.dir"]
type = "path"
default = "~/data"
env = "TOOL_DIR"
`)
	m.script("features/tool/check.sh", `echo "$TOOL_DIR $DOTFILES_FEATURE $DOTFILES_DIR" > "$HOME/.tool-env"; echo '{"state": "ok", "detail": ""}'
`)
	report := m.run(false)
	assert.Empty(t, report.Problems)
	env, err := os.ReadFile(m.at(".tool-env"))
	require.NoError(t, err)
	assert.Equal(t, m.at("data")+" tool "+m.repo+"\n", string(env))
}

// withTeardown gives the machine an "enrolled" feature whose teardown removes
// $HOME/.enrolled and records that it ran in $HOME/.tool-runs.
func (m *machine) withTeardown(hooks string) {
	m.write("features/enrolled/feature.toml", "id = \"enrolled\"\ndefault = true\n[hooks]\nteardown = \"teardown.sh\"\n"+hooks)
	m.script("features/enrolled/teardown.sh", `rm -f "$HOME/.enrolled"; echo run >> "$HOME/.tool-runs"
`)
	require.NoError(m.t, os.WriteFile(m.at(".enrolled"), []byte("token\n"), 0o600))
}

func TestATeardownRunsAfterItsFeatureIsDeleted(t *testing.T) {
	m := newMachine(t)
	m.withTeardown("")
	first := m.run(false)
	assert.Empty(t, first.Problems)
	assert.Contains(t, m.state.Teardowns, "enrolled", "an enabled feature's teardown is recorded")
	assert.Zero(t, m.runs(".tool-runs"), "and does not run")

	require.NoError(t, os.RemoveAll(filepath.Join(m.repo, "features/enrolled")))
	dry := m.run(true)
	assert.Equal(t, 1, kinds(dry)["teardown"])
	assert.FileExists(t, m.at(".enrolled"), "a dry run tears nothing down")

	report := m.run(false)
	assert.Empty(t, report.Problems)
	assert.Equal(t, 1, kinds(report)["teardown"])
	assert.NoFileExists(t, m.at(".enrolled"), "the recorded copy ran")
	assert.NotContains(t, m.state.Teardowns, "enrolled")

	again := m.run(false)
	assert.Empty(t, again.Actions)
	assert.Equal(t, 1, m.runs(".tool-runs"), "a teardown runs once")
}

func TestATeardownThatFailsRunsAgainNextTime(t *testing.T) {
	m := newMachine(t)
	m.withTeardown("")
	m.script("features/enrolled/teardown.sh", "echo run >> \"$HOME/.tool-runs\"; exit 1\n")
	m.run(false)
	m.disable = []string{"enrolled"}

	for range 2 {
		report := m.run(false)
		assert.Equal(t, []string{"turned off, and hooks.teardown exited with status 1; the next apply runs it again"}, problemsOf(report, "enrolled"))
		assert.Contains(t, m.state.Teardowns, "enrolled")
	}
	assert.Equal(t, 2, m.runs(".tool-runs"))
}

func TestASudoTeardownWaitsForApplySudo(t *testing.T) {
	m := newMachine(t)
	m.withTeardown("sudo = true\n")
	m.run(false)
	m.disable = []string{"enrolled"}

	unattended := m.run(false)
	assert.Equal(t, []string{"turned off, and its teardown needs administrator rights; run `dotfiles apply --sudo`"}, problemsOf(unattended, "enrolled"))
	assert.FileExists(t, m.at(".enrolled"))
	assert.Contains(t, m.state.Teardowns, "enrolled")

	m.sudo = true
	report := m.run(false)
	assert.Empty(t, report.Problems)
	assert.NoFileExists(t, m.at(".enrolled"))
	assert.NotContains(t, m.state.Teardowns, "enrolled")
}

func TestAFeatureThatStaysOnKeepsOnlyItsCurrentTeardown(t *testing.T) {
	m := newMachine(t)
	m.withTeardown("")
	m.run(false)
	m.write("features/enrolled/feature.toml", "id = \"enrolled\"\ndefault = true\n")

	report := m.run(false)
	assert.Empty(t, report.Actions, "dropping a teardown from an enabled feature runs nothing")
	assert.NotContains(t, m.state.Teardowns, "enrolled")
	assert.FileExists(t, m.at(".enrolled"))
}
