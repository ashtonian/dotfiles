package resolve

import (
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	"github.com/ashtonian/dotfiles/internal/manifest"
)

type featureOpt func(*manifest.Feature)

func feature(id string, opts ...featureOpt) *manifest.Feature {
	f := &manifest.Feature{ID: id}
	for _, o := range opts {
		o(f)
	}
	return f
}

func on(f *manifest.Feature)             { f.Default = true }
func requires(ids ...string) featureOpt  { return func(f *manifest.Feature) { f.Requires = ids } }
func conflicts(ids ...string) featureOpt { return func(f *manifest.Feature) { f.Conflicts = ids } }
func platforms(p ...string) featureOpt   { return func(f *manifest.Feature) { f.Platforms = p } }
func setting(name string, s manifest.Setting) featureOpt {
	return func(f *manifest.Feature) {
		if f.Settings == nil {
			f.Settings = map[string]manifest.Setting{}
		}
		f.Settings[name] = s
	}
}

func catalog(fs ...*manifest.Feature) map[string]*manifest.Feature {
	m := map[string]*manifest.Feature{}
	for _, f := range fs {
		m[f.ID] = f
	}
	return m
}

func TestDecisions(t *testing.T) {
	profiles := map[string]*manifest.Profile{
		"dev":  {Name: "dev", Features: manifest.Selection{Enable: []string{"b"}, Disable: []string{"a"}}},
		"work": {Name: "work", Features: manifest.Selection{Enable: []string{"a"}}},
	}
	tests := []struct {
		name    string
		machine manifest.Machine
		want    map[string]Decision
	}{
		{
			name:    "defaults only",
			machine: manifest.Machine{},
			want: map[string]Decision{
				"a": {Enabled: true, Source: "default"},
				"b": {Enabled: false, Source: "default"},
			},
		},
		{
			name:    "a profile overrides defaults",
			machine: manifest.Machine{Profiles: []string{"dev"}},
			want: map[string]Decision{
				"a": {Enabled: false, Source: "profile:dev", Explicit: true},
				"b": {Enabled: true, Source: "profile:dev", Explicit: true},
			},
		},
		{
			name:    "a later profile wins",
			machine: manifest.Machine{Profiles: []string{"dev", "work"}},
			want: map[string]Decision{
				"a": {Enabled: true, Source: "profile:work", Explicit: true},
				"b": {Enabled: true, Source: "profile:dev", Explicit: true},
			},
		},
		{
			name: "the machine has the last word",
			machine: manifest.Machine{Profiles: []string{"dev"},
				Features: manifest.Selection{Disable: []string{"b"}}},
			want: map[string]Decision{
				"a": {Enabled: false, Source: "profile:dev", Explicit: true},
				"b": {Enabled: false, Source: "machine", Explicit: true},
			},
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			res, err := Resolve(catalog(feature("a", on), feature("b")), profiles, &tt.machine, "darwin")
			require.NoError(t, err)
			assert.Equal(t, tt.want, res.Decisions)
		})
	}
}

func TestRequirementsAndPlatforms(t *testing.T) {
	features := catalog(
		feature("core"),
		feature("app", on, requires("core")),
		feature("mac-only", platforms("darwin")),
		feature("needs-mac", requires("mac-only")),
	)
	t.Run("a requirement is pulled in", func(t *testing.T) {
		res, err := Resolve(features, nil, &manifest.Machine{}, "linux")
		require.NoError(t, err)
		assert.Equal(t, Decision{Enabled: true, Source: "required by app"}, res.Decisions["core"])
		assert.Equal(t, []string{"core", "app"}, res.Order)
	})
	t.Run("a shared profile's feature another OS lacks is inactive", func(t *testing.T) {
		m := &manifest.Machine{Features: manifest.Selection{Enable: []string{"mac-only"}}}
		res, err := Resolve(features, nil, m, "linux")
		require.NoError(t, err)
		assert.False(t, res.Decisions["mac-only"].Enabled)
		assert.Equal(t, "unsupported on linux", res.Decisions["mac-only"].Source)
	})

	errorCases := []struct {
		name    string
		machine manifest.Machine
		goos    string
		want    string
	}{
		{"a requirement disabled on purpose", manifest.Machine{Features: manifest.Selection{Disable: []string{"core"}}}, "linux", "app requires core, which machine disables"},
		{"a requirement this OS lacks", manifest.Machine{Features: manifest.Selection{Enable: []string{"needs-mac"}}}, "linux", "needs-mac requires mac-only, which does not run on linux"},
		{"an unknown feature", manifest.Machine{Features: manifest.Selection{Enable: []string{"nope"}}}, "linux", `unknown feature "nope"`},
		{"an unknown profile", manifest.Machine{Profiles: []string{"nope"}}, "linux", `unknown profile "nope"`},
	}
	for _, tt := range errorCases {
		t.Run(tt.name, func(t *testing.T) {
			_, err := Resolve(features, nil, &tt.machine, tt.goos)
			require.ErrorIs(t, err, ErrConflict)
			assert.Contains(t, err.Error(), tt.want)
		})
	}
}

func TestConflictsAndCycles(t *testing.T) {
	_, err := Resolve(catalog(feature("a", on, conflicts("b")), feature("b", on)), nil, &manifest.Machine{}, "linux")
	require.ErrorIs(t, err, ErrConflict)
	assert.Contains(t, err.Error(), "a conflicts with b")

	_, err = Resolve(catalog(feature("a", on, requires("b")), feature("b", requires("a"))), nil, &manifest.Machine{}, "linux")
	require.ErrorIs(t, err, ErrConflict)
	assert.Contains(t, err.Error(), "requirement cycle")
}

func TestSettings(t *testing.T) {
	features := catalog(
		feature("app", on,
			setting("app.path", manifest.Setting{Type: "path", Default: "~/default"}),
			setting("app.token", manifest.Setting{Type: "secret", Required: true}),
		),
		feature("plugin", on, requires("app")),
		feature("off", setting("off.flag", manifest.Setting{Type: "bool"})),
	)
	profiles := map[string]*manifest.Profile{
		"base": {Name: "base", Settings: map[string]any{"app.path": "~/profile", "off.flag": true}},
	}
	secret := map[string]any{"secret": "op://dotfiles/app/token"}

	t.Run("profile then machine, and only for enabled features", func(t *testing.T) {
		m := &manifest.Machine{Profiles: []string{"base"}, Settings: map[string]any{"app.token": secret}}
		res, err := Resolve(features, profiles, m, "linux")
		require.NoError(t, err)
		assert.Equal(t, Value{Value: "~/profile", Source: "profile:base"}, res.Settings["app.path"])
		assert.Equal(t, Value{Value: secret, Source: "machine"}, res.Settings["app.token"])
		assert.NotContains(t, res.Settings, "off.flag")
		assert.Empty(t, res.Missing)
		assert.Equal(t, []string{"app", "plugin"}, res.Runnable(features))
	})
	t.Run("a missing required setting blocks the feature and what needs it", func(t *testing.T) {
		res, err := Resolve(features, profiles, &manifest.Machine{Profiles: []string{"base"}}, "linux")
		require.NoError(t, err)
		assert.Equal(t, map[string][]string{"app": {"app.token"}}, res.Missing)
		assert.Empty(t, res.Runnable(features))
	})

	errorCases := []struct {
		name     string
		settings map[string]any
		want     string
	}{
		{"an unknown setting", map[string]any{"nope": "x"}, `unknown setting "nope"`},
		{"a wrong type", map[string]any{"app.path": int64(3)}, "want a string"},
		{"a secret value instead of a reference", map[string]any{"app.token": "hunter2"}, "never a value"},
	}
	for _, tt := range errorCases {
		t.Run(tt.name, func(t *testing.T) {
			_, err := Resolve(features, profiles, &manifest.Machine{Settings: tt.settings}, "linux")
			require.ErrorIs(t, err, ErrConflict)
			assert.Contains(t, err.Error(), tt.want)
		})
	}
}
