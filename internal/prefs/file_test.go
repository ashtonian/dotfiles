package prefs

import (
	"encoding/json"
	"strings"
	"testing"

	"github.com/BurntSushi/toml"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestParseReadsOneSettingPerLine(t *testing.T) {
	entries, err := Parse("muxy.toml", []byte(`# shared settings

"appearance.dark_theme" = "Dracula"
"terminal.font_families" = ["FiraCode Nerd Font Mono"]  # with a note
font_size = 13.0
`))
	require.NoError(t, err)
	assert.Equal(t, []Entry{
		{Key: "appearance.dark_theme", Value: "Dracula", Line: 3},
		{Key: "terminal.font_families", Value: []any{"FiraCode Nerd Font Mono"}, Line: 4},
		{Key: "font_size", Value: 13.0, Line: 5},
	}, entries)
}

func TestParseRejectsWhatAdoptCouldNotRewrite(t *testing.T) {
	tests := []struct {
		name, file, want string
	}{
		{"table header", "[appearance]\ndark_theme = \"Dracula\"\n", "muxy.toml:1: a table header"},
		{"multi-line value", "fonts = [\n  \"a\",\n]\n", "muxy.toml:1: each setting is one"},
		{"two lines for one key", "\"a.b\" = 1\n'a.b' = 2\n", `muxy.toml:2: "a.b" is already set on line 1`},
		{"a dotted key", "permissions.defaultMode = \"acceptEdits\"\n",
			`muxy.toml:1: permissions.defaultMode is a dotted key, which TOML reads as a table; to name one setting whose key holds a dot, quote it, as "permissions.defaultMode" = ...`},
		{"a partly quoted dotted key", "appearance.\"dark_theme\" = \"Dracula\"\n", "is a dotted key"},
		{"a date", "when = 2026-11-20\n", "muxy.toml:1: when: a time.Time is not a setting value"},
		{"not a number", "ratio = nan\n", "muxy.toml:1: ratio: NaN has no JSON form"},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			_, err := Parse("muxy.toml", []byte(tt.file))
			require.Error(t, err)
			assert.Contains(t, err.Error(), tt.want)
		})
	}
}

func TestSetLineRewritesOnlyThatValue(t *testing.T) {
	before := "# keep me\n\"appearance.dark_theme\" = \"Dracula\"   # the team's theme\n'terminal.font_size'=13.0\n"
	after, err := SetLine("muxy.toml", []byte(before), "", "appearance.dark_theme", "Nord # not a comment")
	require.NoError(t, err)
	assert.Equal(t, "# keep me\n\"appearance.dark_theme\" = \"Nord # not a comment\"   # the team's theme\n'terminal.font_size'=13.0\n",
		string(after), "the key as written and the comment stay")
	after, err = SetLine("muxy.toml", after, "", "terminal.font_size", 14.0)
	require.NoError(t, err)
	assert.Contains(t, string(after), "\n'terminal.font_size' = 14.0\n")
	_, err = Parse("muxy.toml", after)
	require.NoError(t, err)

	_, err = SetLine("muxy.toml", []byte(before), "", "missing", "x")
	assert.ErrorContains(t, err, `muxy.toml does not set "missing"`)
}

func TestSetLineRewritesAManifestsOverride(t *testing.T) {
	before := `profiles = ["base"]

[settings]
"muxy:terminal.font_size" = "not this one"

[prefs] # this Mac's display
"muxy:appearance.dark_theme" = "Nord"
"muxy:terminal.font_size" = 13 # the small screen
`
	after, err := SetLine("machine.toml", []byte(before), "prefs", "muxy:terminal.font_size", 12.5)
	require.NoError(t, err)
	assert.Equal(t, strings.Replace(before, `"muxy:terminal.font_size" = 13 # the small screen`,
		`"muxy:terminal.font_size" = 12.5 # the small screen`, 1), string(after))

	_, err = SetLine("machine.toml", []byte("[prefs]\n\"muxy:a\" = 1\n"), "prefs", "muxy:b", int64(2))
	assert.ErrorContains(t, err, `machine.toml does not set "muxy:b" on a line of its own in [prefs]`)
	_, err = SetLine("machine.toml", []byte("prefs = { \"muxy:a\" = 1 }\n"), "prefs", "muxy:a", int64(2))
	assert.ErrorContains(t, err, "on a line of its own in [prefs]")
}

func TestLinePartsKeepQuotedSigns(t *testing.T) {
	tests := []struct{ line, key, value, comment string }{
		{`a = 1`, `a `, ` 1`, ``},
		{`"x=y" = "#1" # note`, `"x=y" `, ` "#1"`, ` # note`},
		{`k = 'a#b' #c`, `k `, ` 'a#b'`, ` #c`},
		{`k = "say \"#\"" # c`, `k `, ` "say \"#\""`, ` # c`},
		{`k = """a"#"b""" # c`, `k `, ` """a"#"b"""`, ` # c`},
	}
	for _, tt := range tests {
		key, value, comment, ok := lineParts(tt.line)
		assert.True(t, ok, tt.line)
		assert.Equal(t, []string{tt.key, tt.value, tt.comment}, []string{key, value, comment}, tt.line)
	}
}

func TestParseIDNamesAStoresKey(t *testing.T) {
	store, key, err := ParseID("muxy:terminal.options.copy_on_select")
	require.NoError(t, err)
	assert.Equal(t, []string{"muxy", "terminal.options.copy_on_select"}, []string{store, key})
	for _, bad := range []string{"terminal.font_size", "vscode:editor.fontSize", "muxy:"} {
		_, _, err := ParseID(bad)
		assert.Error(t, err, bad)
	}
}

// Every value a store can hand back must survive being written to a prefs
// file and read again, with integers and floats kept apart.
func TestEncodeTOMLRoundTrips(t *testing.T) {
	tests := []struct {
		name  string
		value any
		want  string
	}{
		{"string with escapes", "say \"hi\"\n\ttab\x7f<&>", `"say \"hi\"\n\ttab\u007f<&>"`},
		{"integer", int64(-3), "-3"},
		{"float with no fraction", 13.0, "13.0"},
		{"float", 0.25, "0.25"},
		{"json integer", json.Number("13"), "13"},
		{"json float", json.Number("13.0"), "13.0"},
		{"bool", true, "true"},
		{"array", []any{"a", int64(1)}, `["a", 1]`},
		{"table", map[string]any{"b": false, "a.b": "x"}, `{ "a.b" = "x", b = false }`},
		{"empty table", map[string]any{}, "{}"},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got, err := EncodeTOML(tt.value)
			require.NoError(t, err)
			assert.Equal(t, tt.want, got)
			var back map[string]any
			_, err = toml.Decode("v = "+got, &back)
			require.NoError(t, err)
			assert.True(t, Equal(tt.value, back["v"]), "%#v read back as %#v", tt.value, back["v"])
		})
	}
	_, err := EncodeTOML(nil)
	assert.ErrorContains(t, err, "null has no TOML form")
}

func TestEqualComparesNumbersByValue(t *testing.T) {
	assert.True(t, Equal(int64(13), json.Number("13.0")))
	assert.True(t, Equal([]any{13.0}, []any{json.Number("13")}))
	assert.False(t, Equal("13", int64(13)))
	assert.False(t, Equal(map[string]any{"a": true}, map[string]any{"a": true, "b": false}))
}

func TestCheckSettingKeepsMuxySettingsToOneKey(t *testing.T) {
	assert.NoError(t, CheckSetting("muxy", "appearance.dark_theme", "Dracula"))
	assert.ErrorContains(t, CheckSetting("muxy", "appearance", map[string]any{"dark_theme": "Dracula"}),
		"muxy: appearance is a table")
	assert.NoError(t, CheckSetting("claude", "permissions", map[string]any{"allow": []any{"Read"}}),
		"a Claude Code setting can be an object")
	assert.ErrorContains(t, CheckSetting("claude", "permissions.defaultMode", "acceptEdits"),
		`claude: "permissions.defaultMode" is not a top-level key of settings.json`)
}
