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

	"github.com/ashtonian/dotfiles/internal/manifest"
	"github.com/ashtonian/dotfiles/internal/plan"
	"github.com/ashtonian/dotfiles/internal/prefs"
	"github.com/ashtonian/dotfiles/internal/resolve"
)

// memoryStore is one app's settings in memory, with a failure to act out.
type memoryStore struct {
	values   map[string]any
	getErr   error
	setErr   error // one wrapping prefs.ErrNotApplied still saves
	unsetErr error // likewise
	sets     int
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
	if s.unsetErr != nil && !errors.Is(s.unsetErr, prefs.ErrNotApplied) {
		return s.unsetErr
	}
	delete(s.values, key)
	return s.unsetErr
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
	muxy.values["terminal.font_families"] = []any{"Menlo", "Monaco"}
	m.run(false)
	// Through the state file, as between two runs.
	path := filepath.Join(t.TempDir(), "applied.json")
	require.NoError(t, m.state.Save(path))
	loaded, err := LoadState(path)
	require.NoError(t, err)
	m.state = loaded
	m.disable = []string{"app"}

	report := m.run(false)
	assert.Empty(t, report.Problems)
	assert.Equal(t, map[string]string{
		"muxy:appearance.dark_theme":  `"Muxy"`,
		"muxy:terminal.font_families": `["Menlo","Monaco"]`,
	}, details(report, "restore-pref"), "one line each, as the state file's indentation is not the value's")
	assert.Equal(t, map[string]any{"appearance.dark_theme": "Muxy", "appearance.layout": "project_focused",
		"terminal.font_families": []any{"Menlo", "Monaco"}}, muxy.values)
	assert.Empty(t, m.state.Prefs)
	assert.Empty(t, m.run(false).Actions)
}

func TestPrefsTeardownUnsetsASettingThatHadNoValue(t *testing.T) {
	m, muxy := prefsMachine(t)
	m.run(false)
	m.disable = []string{"app"}
	report := m.run(false)
	assert.Equal(t, "no value", details(report, "restore-pref")["muxy:terminal.font_families"])
	assert.NotContains(t, muxy.values, "terminal.font_families")
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

	muxy.getErr = errors.New("muxy config list: no answer within 30s")
	m.write("features/app/muxy.toml", `"appearance.dark_theme" = "Nord"`+"\n")
	report := m.run(false)
	require.Len(t, report.Problems, 2, "the owned setting, and the one teardown could not read")
	for _, p := range report.Problems {
		assert.Contains(t, p.Detail, "no answer within 30s")
	}
	assert.Zero(t, kinds(report)["pref"]+kinds(report)["update-pref"]+kinds(report)["restore-pref"])
	assert.Equal(t, recorded, m.state.Prefs["muxy:appearance.dark_theme"], "what apply set is still known for the next run")
	assert.Contains(t, m.state.Prefs, "muxy:terminal.font_families", "teardown tries again next run")
	_, err := os.Lstat(m.at(".config/shell/a.sh"))
	assert.NoError(t, err, "everything else still converges")
}

func TestPrefsTeardownForgetsTheSettingsOfAnAppThatIsGone(t *testing.T) {
	m, muxy := prefsMachine(t)
	m.run(false)

	// Muxy uninstalled, then its feature turned off.
	muxy.getErr = fmt.Errorf("%w: Muxy is not installed; looked for /Applications/Muxy.app/Contents/MacOS/muxy", prefs.ErrUnavailable)
	m.disable = []string{"app"}
	report := m.run(false)
	assert.Empty(t, report.Problems, "uninstalling the app is no failure")
	assert.Equal(t, map[string]string{
		"muxy:appearance.dark_theme":  `app not available: Muxy is not installed; looked for /Applications/Muxy.app/Contents/MacOS/muxy; before dotfiles set it, it was "Muxy"`,
		"muxy:terminal.font_families": `app not available: Muxy is not installed; looked for /Applications/Muxy.app/Contents/MacOS/muxy; before dotfiles set it, it was no value`,
	}, details(report, "forget-pref"), "the earlier value is reported once, to set by hand")
	assert.Empty(t, m.state.Prefs)
	assert.Empty(t, m.run(false).Actions, "and never again")
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

// An overlay's feature owns app settings as one of the repository's does:
// adopt writes into the overlay's prefs file, and a machine that leaves the
// context gets back the values the overlay's settings replaced.
func TestOverlayPrefsAreOwnedAdoptedAndPutBack(t *testing.T) {
	m, muxy := prefsMachine(t)
	m.withOverlay()
	overlayOwn := `"appearance.light_theme" = "Dracula"` + "\n"
	m.writeOverlay("features/personal.muxy/feature.toml", "id = \"personal.muxy\"\ndefault = true\n[provides.prefs]\nmuxy = \"muxy.toml\"\n")
	m.writeOverlay("features/personal.muxy/muxy.toml", overlayOwn)
	muxy.values["appearance.light_theme"] = "Muxy Light"

	first := m.run(false)
	assert.Empty(t, first.Problems)
	assert.Equal(t, `"Dracula" (was "Muxy Light")`, details(first, "pref")["muxy:appearance.light_theme"])
	assert.Equal(t, "Dracula", muxy.values["appearance.light_theme"])

	muxy.values["appearance.light_theme"] = "Solarized Light"
	report, next, err := Adopt(context.Background(), m.plan(), m.state, []string{"muxy:appearance.light_theme"}, m.stores)
	require.NoError(t, err)
	assert.Equal(t, filepath.Join(m.overlay, "features/personal.muxy/muxy.toml"), details(report, "adopt")["muxy:appearance.light_theme"],
		"the value goes to the overlay that owns it, never the public repository")
	m.state = next
	source, err := os.ReadFile(filepath.Join(m.overlay, "features/personal.muxy/muxy.toml"))
	require.NoError(t, err)
	assert.Equal(t, `"appearance.light_theme" = "Solarized Light"`+"\n", string(source))
	assert.Empty(t, m.run(false).Actions, "adopted: in step")

	m.overlay = ""
	left := m.run(false)
	assert.Empty(t, left.Problems)
	assert.Equal(t, `"Muxy Light"`, details(left, "restore-pref")["muxy:appearance.light_theme"])
	assert.Equal(t, "Muxy Light", muxy.values["appearance.light_theme"])
	assert.Equal(t, "Dracula", muxy.values["appearance.dark_theme"], "the repository's own settings stay")
}

func TestAnOverlayAndTheRepositoryCannotOwnOneSetting(t *testing.T) {
	m, _ := prefsMachine(t)
	m.withOverlay()
	m.writeOverlay("features/personal.muxy/feature.toml", "id = \"personal.muxy\"\ndefault = true\n[provides.prefs]\nmuxy = \"muxy.toml\"\n")
	m.writeOverlay("features/personal.muxy/muxy.toml", `"appearance.dark_theme" = "Nord"`+"\n")
	features, err := manifest.LoadFeatures(manifest.Root{Dir: m.repo}, manifest.Root{Dir: m.overlay, Overlay: "personal"})
	require.NoError(t, err)
	res, err := resolve.Resolve(features, nil, &manifest.Machine{}, m.goos)
	require.NoError(t, err)
	_, err = plan.Build(features, res.Runnable(features), res.Values(), res.PrefLayers, plan.Env{Home: m.home, GeneratedDir: m.generated, GOOS: m.goos})
	require.ErrorIs(t, err, plan.ErrPlan)
	assert.Contains(t, err.Error(), "app and personal.muxy both install muxy:appearance.dark_theme")
}

// stopAfterSet ends the run once the app has taken a value: a SIGTERM to
// `dotfiles apply` between setting it and saving the state.
type stopAfterSet struct {
	*memoryStore
	stop context.CancelFunc
}

func (s stopAfterSet) Set(ctx context.Context, key string, value any) error {
	err := s.memoryStore.Set(ctx, key, value)
	s.stop()
	return err
}

func TestPrefsARunStoppedAfterSettingStillPutsBackTheEarlierValue(t *testing.T) {
	for _, tt := range []struct {
		name    string
		saved   func(m *machine, partial *State) *State
		pending bool // the record still says apply was setting it
	}{
		// cmd/dotfiles saves the state Run returns with its error, which has
		// what the app stored, read back after the set.
		{"the partial state saved", func(_ *machine, partial *State) *State { return partial }, false},
		// Killed outright: only the checkpoint reached the disk.
		{"only the checkpoint saved", func(m *machine, _ *State) *State {
			s, err := LoadState(m.statePath)
			require.NoError(t, err)
			return s
		}, true},
	} {
		t.Run(tt.name, func(t *testing.T) {
			m, muxy := prefsMachine(t)
			ctx, stop := context.WithCancel(context.Background())
			env := m.env()
			env.Prefs = map[string]PrefStore{"muxy": stopAfterSet{muxy, stop}}
			_, partial, err := Run(ctx, m.plan(), m.state, env, false)
			require.ErrorIs(t, err, context.Canceled)
			require.Equal(t, "Dracula", muxy.values["appearance.dark_theme"], "the app took the value")
			m.state = tt.saved(m, partial)
			rec := m.state.Prefs["muxy:appearance.dark_theme"]
			assert.Equal(t, tt.pending, rec.Pending)
			assert.JSONEq(t, `"Muxy"`, string(rec.Previous), "the earlier value was saved before the app's changed")

			next := m.run(false)
			assert.Empty(t, next.Problems, "neither value is a change made here")
			assert.Equal(t, `["FiraCode Nerd Font Mono"] (was no value)`, details(next, "pref")["muxy:terminal.font_families"])
			assert.False(t, m.state.Prefs["muxy:appearance.dark_theme"].Pending)
			assert.Empty(t, m.run(false).Actions)

			m.disable = []string{"app"}
			torn := m.run(false)
			assert.Empty(t, torn.Problems)
			assert.Equal(t, "Muxy", muxy.values["appearance.dark_theme"], "the value the owner had")
			assert.NotContains(t, muxy.values, "terminal.font_families")
		})
	}
}

func TestPrefsTeardownStoppedAfterPuttingBackFinishesQuietly(t *testing.T) {
	m, muxy := prefsMachine(t)
	m.run(false)
	before := m.state
	m.disable = []string{"app"}
	m.run(false)
	require.Equal(t, "Muxy", muxy.values["appearance.dark_theme"])

	m.state = before // the run that put the values back stopped before saving
	again := m.run(false)
	assert.Empty(t, again.Problems)
	assert.Empty(t, again.Actions)
	assert.Empty(t, m.state.Prefs)
}

// f32Store keeps floats as 32-bit numbers and lists them as 64-bit ones, as
// Muxy does: 1.3 reads back as 1.2999999523162842.
type f32Store struct{ *memoryStore }

func (s f32Store) Set(ctx context.Context, key string, value any) error {
	if f, ok := value.(float64); ok {
		value = float64(float32(f))
	}
	return s.memoryStore.Set(ctx, key, value)
}

func TestPrefsARoundedValueIsInStepAndPutBack(t *testing.T) {
	m := newMachine(t)
	m.write("features/app/feature.toml", "id = \"app\"\ndefault = true\n[provides.prefs]\nmuxy = \"muxy.toml\"\n")
	m.write("features/app/muxy.toml", "\"composer.line_height\" = 1.3\n")
	earlier := float64(float32(1.2))
	mem := &memoryStore{values: map[string]any{"composer.line_height": earlier}}
	m.stores = map[string]PrefStore{"muxy": f32Store{mem}}

	first := m.run(false)
	assert.Empty(t, first.Problems)
	assert.Equal(t, "1.3 (was 1.2000000476837158); the app stored 1.2999999523162842", details(first, "pref")["muxy:composer.line_height"])
	again := m.run(false)
	assert.Empty(t, again.Problems, "what the app stored is what apply set")
	assert.Empty(t, again.Actions)

	m.write("features/app/muxy.toml", "\"composer.line_height\" = 1.4\n")
	assert.Equal(t, 1, kinds(m.run(false))["update-pref"], "a new value is still a move")
	mem.values["composer.line_height"] = 1.5
	assert.Len(t, m.run(false).Problems, 1, "and a change made here still a change")
	mem.values["composer.line_height"] = float64(float32(1.4))

	m.disable = []string{"app"}
	torn := m.run(false)
	assert.Empty(t, torn.Problems)
	assert.True(t, prefs.Equal(earlier, mem.values["composer.line_height"]), "teardown puts back the old value, not %v", mem.values["composer.line_height"])
}

func TestPrefsAnUnsetTheRunningAppDidNotTakeStillCounts(t *testing.T) {
	m, muxy := prefsMachine(t)
	m.run(false)
	muxy.unsetErr = fmt.Errorf("%w: no response from Muxy", prefs.ErrNotApplied)
	m.disable = []string{"app"}

	torn := m.run(false)
	assert.Empty(t, torn.Problems, "saved; the app loads it when it restarts")
	assert.Equal(t, "no value", details(torn, "restore-pref")["muxy:terminal.font_families"])
	assert.NotContains(t, muxy.values, "terminal.font_families")
	again := m.run(false)
	assert.Empty(t, again.Problems)
	assert.Empty(t, again.Actions)
}

func TestPrefsAClaudeKeyInsideAnObjectIsRefused(t *testing.T) {
	m := newMachine(t)
	m.write("features/app/feature.toml", "id = \"app\"\ndefault = true\n[provides.prefs]\nclaude = \"claude.toml\"\n")
	for _, line := range []string{"permissions.defaultMode = \"acceptEdits\"\n", "\"permissions.defaultMode\" = \"acceptEdits\"\n"} {
		m.write("features/app/claude.toml", line)
		features, err := manifest.LoadFeatures(manifest.Root{Dir: m.repo})
		require.NoError(t, err)
		res, err := resolve.Resolve(features, nil, &manifest.Machine{}, m.goos)
		require.NoError(t, err)
		_, err = plan.Build(features, res.Runnable(features), res.Values(), nil, plan.Env{Home: m.home, GeneratedDir: m.generated, GOOS: m.goos})
		require.ErrorIs(t, err, plan.ErrPlan, line)
	}
}

func TestPrefOverridesConvergeAndGoBackToTheSharedValue(t *testing.T) {
	m, muxy := prefsMachine(t)
	m.machineTOML = "profiles = []\n\n[prefs]\n\"muxy:appearance.dark_theme\" = \"Nord\" # this Mac's display\n"

	first := m.run(false)
	assert.Empty(t, first.Problems)
	assert.Equal(t, `"Nord" (was "Muxy")`, details(first, "pref")["muxy:appearance.dark_theme"])

	m.machineTOML = "profiles = []\n\n[prefs]\n\"muxy:appearance.dark_theme\" = \"Solarized\"\n"
	changed := m.run(false)
	assert.Empty(t, changed.Problems, "a new override is no change made here")
	assert.Equal(t, `"Solarized" (was "Nord")`, details(changed, "update-pref")["muxy:appearance.dark_theme"])

	m.machineTOML = "profiles = []\n"
	removed := m.run(false)
	assert.Empty(t, removed.Problems)
	assert.Equal(t, `"Dracula" (was "Solarized")`, details(removed, "update-pref")["muxy:appearance.dark_theme"], "back to the shared value")

	m.machineTOML = "profiles = []\n\n[prefs]\n\"muxy:appearance.dark_theme\" = \"Nord\" # this Mac's display\n"
	m.run(false)
	muxy.values["appearance.dark_theme"] = "Gruvbox"
	report, next, err := Adopt(context.Background(), m.plan(), m.state, []string{"muxy:appearance.dark_theme"}, m.stores)
	require.NoError(t, err)
	assert.Equal(t, m.machinePath(), details(report, "adopt")["muxy:appearance.dark_theme"], "adopt keeps an override where it is set")
	m.state = next
	written, err := os.ReadFile(m.machinePath())
	require.NoError(t, err)
	assert.Equal(t, "profiles = []\n\n[prefs]\n\"muxy:appearance.dark_theme\" = \"Gruvbox\" # this Mac's display\n", string(written))
	shared, err := os.ReadFile(filepath.Join(m.repo, "features/app/muxy.toml"))
	require.NoError(t, err)
	assert.Equal(t, muxyPrefs, string(shared), "the shared value stays")
	m.machineTOML = string(written)
	assert.Empty(t, m.run(false).Actions, "adopted: in step")

	m.disable = []string{"app"}
	m.machineTOML = "profiles = []\n"
	torn := m.run(false)
	assert.Empty(t, torn.Problems)
	assert.Equal(t, "Muxy", muxy.values["appearance.dark_theme"], "teardown puts back the value from before dotfiles")
}
