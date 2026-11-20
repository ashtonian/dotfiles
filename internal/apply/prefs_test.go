package apply

import (
	"context"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	"github.com/ashtonian/dotfiles/internal/prefs"
)

// memoryStore is one app's settings in memory, with a failure to act out.
type memoryStore struct {
	values map[string]any
	getErr error
	setErr error // one wrapping prefs.ErrNotApplied still saves
	sets   int
}

func (s *memoryStore) Get(_ context.Context, key string) (any, bool, error) {
	if s.getErr != nil {
		return nil, false, s.getErr
	}
	v, ok := s.values[key]
	return v, ok, nil
}

func (s *memoryStore) Set(_ context.Context, key string, value any) error {
	s.sets++
	if s.setErr != nil && !errors.Is(s.setErr, prefs.ErrNotApplied) {
		return s.setErr
	}
	s.values[key] = value
	return s.setErr
}

func (s *memoryStore) Unset(_ context.Context, key string) error {
	delete(s.values, key)
	return nil
}

const muxyPrefs = `# shared Muxy settings
"appearance.dark_theme" = "Dracula"
"terminal.font_families" = ["FiraCode Nerd Font Mono"]
`

// prefsMachine is a machine whose "app" feature owns two Muxy settings, in a
// Muxy that has its own theme and no font list yet.
func prefsMachine(t *testing.T) (*machine, *memoryStore) {
	t.Helper()
	m := newMachine(t)
	m.write("features/app/feature.toml", "id = \"app\"\ndefault = true\n[provides.prefs]\nmuxy = \"muxy.toml\"\n")
	m.write("features/app/muxy.toml", muxyPrefs)
	muxy := &memoryStore{values: map[string]any{"appearance.dark_theme": "Muxy", "appearance.layout": "project_focused"}}
	m.stores = map[string]PrefStore{"muxy": muxy}
	return m, muxy
}

func details(r *Report, kind string) map[string]string {
	d := map[string]string{}
	for _, a := range r.Actions {
		if a.Kind == kind {
			d[a.Path] = a.Detail
		}
	}
	return d
}

func TestPrefsSetOnlyTheirKeysAndStayPut(t *testing.T) {
	m, muxy := prefsMachine(t)

	dry := m.run(true)
	assert.Len(t, details(dry, "pref"), 2)
	assert.Zero(t, muxy.sets, "a dry run sets nothing")

	first := m.run(false)
	assert.Empty(t, first.Problems)
	assert.Equal(t, map[string]string{
		"muxy:appearance.dark_theme":  `"Dracula" (was "Muxy")`,
		"muxy:terminal.font_families": `["FiraCode Nerd Font Mono"] (was no value)`,
	}, details(first, "pref"))
	assert.Equal(t, map[string]any{"appearance.dark_theme": "Dracula", "terminal.font_families": []any{"FiraCode Nerd Font Mono"},
		"appearance.layout": "project_focused"}, muxy.values, "a key no feature owns is left alone")

	again := m.run(false)
	assert.Empty(t, again.Actions)
	assert.Empty(t, again.Problems)
}

func TestPrefsFollowTheRepositoryUntilChangedHere(t *testing.T) {
	m, muxy := prefsMachine(t)
	m.run(false)

	m.write("features/app/muxy.toml", `"appearance.dark_theme" = "Nord"`+"\n"+`"terminal.font_families" = ["FiraCode Nerd Font Mono"]`+"\n")
	moved := m.run(false)
	assert.Equal(t, map[string]string{"muxy:appearance.dark_theme": `"Nord" (was "Dracula")`}, details(moved, "update-pref"))

	muxy.values["appearance.dark_theme"] = "Catppuccin Mocha" // picked in Muxy's theme picker
	m.write("features/app/muxy.toml", muxyPrefs)
	changed := m.run(false)
	require.Len(t, changed.Problems, 1)
	assert.Equal(t, "muxy:appearance.dark_theme", changed.Problems[0].Path)
	assert.Contains(t, changed.Problems[0].Detail, `changed here since dotfiles set it (now "Catppuccin Mocha")`)
	assert.Equal(t, "Catppuccin Mocha", muxy.values["appearance.dark_theme"], "a change made here is never overwritten")
	assert.Len(t, m.run(false).Problems, 1, "it stays a problem until the owner decides")

	report, next, err := Adopt(context.Background(), m.plan(), m.state, []string{"muxy:appearance.dark_theme"}, m.stores)
	require.NoError(t, err)
	assert.Equal(t, 1, kinds(report)["adopt"])
	m.state = next
	source, err := os.ReadFile(filepath.Join(m.repo, "features/app/muxy.toml"))
	require.NoError(t, err)
	assert.Equal(t, "# shared Muxy settings\n\"appearance.dark_theme\" = \"Catppuccin Mocha\"\n\"terminal.font_families\" = [\"FiraCode Nerd Font Mono\"]\n",
		string(source), "adopt rewrites that one line")
	after := m.run(false)
	assert.Empty(t, after.Problems)
	assert.Empty(t, after.Actions)
}

func TestPrefsTeardownPutsBackWhatWasThere(t *testing.T) {
	m, muxy := prefsMachine(t)
	m.run(false)
	m.disable = []string{"app"}

	report := m.run(false)
	assert.Empty(t, report.Problems)
	assert.Equal(t, map[string]string{
		"muxy:appearance.dark_theme":  `"Muxy"`,
		"muxy:terminal.font_families": "no value",
	}, details(report, "restore-pref"))
	assert.Equal(t, map[string]any{"appearance.dark_theme": "Muxy", "appearance.layout": "project_focused"}, muxy.values)
	assert.Empty(t, m.state.Prefs)
	assert.Empty(t, m.run(false).Actions)
}

func TestPrefsTeardownLeavesAChangedSettingAlone(t *testing.T) {
	m, muxy := prefsMachine(t)
	m.run(false)
	muxy.values["appearance.dark_theme"] = "Nord"
	m.disable = []string{"app"}

	report := m.run(false)
	require.Len(t, report.Problems, 1)
	assert.Contains(t, report.Problems[0].Detail, "no longer managed, but changed since dotfiles set it")
	assert.Equal(t, "Nord", muxy.values["appearance.dark_theme"])
	assert.NotContains(t, muxy.values, "terminal.font_families", "the unchanged one is still put back")
}

func TestPrefsAStoreThatFailsIsAProblemForItsSettingsOnly(t *testing.T) {
	m, muxy := prefsMachine(t)
	m.run(false)
	recorded := m.state.Prefs["muxy:appearance.dark_theme"]

	muxy.getErr = fmt.Errorf("%w: Muxy is not installed", prefs.ErrUnavailable)
	m.write("features/app/muxy.toml", `"appearance.dark_theme" = "Nord"`+"\n")
	report := m.run(false)
	require.Len(t, report.Problems, 2, "the owned setting, and the one teardown could not read")
	for _, p := range report.Problems {
		assert.Contains(t, p.Detail, "Muxy is not installed")
	}
	assert.Zero(t, kinds(report)["pref"]+kinds(report)["update-pref"]+kinds(report)["restore-pref"])
	assert.Equal(t, recorded, m.state.Prefs["muxy:appearance.dark_theme"], "what apply set is still known for the next run")
	assert.Contains(t, m.state.Prefs, "muxy:terminal.font_families")
	_, err := os.Lstat(m.at(".config/shell/a.sh"))
	assert.NoError(t, err, "everything else still converges")
}

func TestPrefsAValueTheRunningAppDidNotTakeIsStillRecorded(t *testing.T) {
	m, muxy := prefsMachine(t)
	muxy.setErr = fmt.Errorf("%w: terminal.toml: unknown field", prefs.ErrNotApplied)

	first := m.run(false)
	assert.Len(t, details(first, "pref"), 2)
	require.Len(t, first.Problems, 2)
	assert.Contains(t, first.Problems[0].Detail, "restart the app to load it")

	muxy.setErr = nil
	again := m.run(false)
	assert.Empty(t, again.Actions)
	assert.Empty(t, again.Problems, "it was saved, so the next run has nothing to do")
}

func TestPrefsARefusedValueIsAProblem(t *testing.T) {
	m, muxy := prefsMachine(t)
	muxy.setErr = errors.New("muxy config set: terminal.font_families: invalid type")

	report := m.run(false)
	assert.Empty(t, details(report, "pref"))
	require.Len(t, report.Problems, 2)
	assert.Contains(t, report.Problems[0].Detail, "setting it: muxy config set")
	assert.Empty(t, m.state.Prefs, "nothing was set, so nothing is recorded")
}

func TestAdoptRefusesASettingWithNoValueHere(t *testing.T) {
	m, muxy := prefsMachine(t)
	m.run(false)
	delete(muxy.values, "terminal.font_families")
	_, _, err := Adopt(context.Background(), m.plan(), m.state, []string{"muxy:terminal.font_families"}, m.stores)
	assert.ErrorContains(t, err, "has no value here")
	_, _, err = Adopt(context.Background(), m.plan(), m.state, []string{"muxy:appearance.layout"}, m.stores)
	assert.ErrorIs(t, err, ErrNotManaged, "a key no feature owns")
}
