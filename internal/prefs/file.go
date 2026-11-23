package prefs

import (
	"bytes"
	"fmt"
	"os"
	"slices"
	"strings"

	"github.com/BurntSushi/toml"
)

// Entry is one setting a prefs file sets.
type Entry struct {
	Key   string
	Value any
	Line  int // 1-based
}

// ReadFile reads and parses the prefs file at path.
func ReadFile(path string) ([]Entry, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	return Parse(path, data)
}

// Parse reads a prefs file: TOML with one top-level `key = value` per line,
// and blank and comment lines between. Keeping each setting on its own line
// keeps it one reviewable line, and lets adopt rewrite exactly that line.
// path only names the file in errors.
func Parse(path string, data []byte) ([]Entry, error) {
	var entries []Entry
	seen := map[string]int{}
	for i, line := range strings.Split(string(data), "\n") {
		n := i + 1
		trimmed := strings.TrimSpace(line)
		if trimmed == "" || strings.HasPrefix(trimmed, "#") {
			continue
		}
		if strings.HasPrefix(trimmed, "[") {
			return nil, fmt.Errorf("%s:%d: a table header; write a table inline on its key's line, as key = { a = 1 }", path, n)
		}
		key, value, err := parseLine(line)
		if err != nil {
			return nil, fmt.Errorf("%s:%d: %w", path, n, err)
		}
		if first, dup := seen[key]; dup {
			return nil, fmt.Errorf("%s:%d: %q is already set on line %d", path, n, key, first)
		}
		if err := CheckValue(value); err != nil {
			return nil, fmt.Errorf("%s:%d: %s: %w", path, n, key, err)
		}
		seen[key] = n
		entries = append(entries, Entry{Key: key, Value: value, Line: n})
	}
	return entries, nil
}

// parseLine decodes one `key = value` line. A key of more than one part,
// such as permissions.defaultMode, is refused: TOML reads it as a table
// holding the last part, so the line would stand for the whole table, every
// key of it the line does not name included.
func parseLine(line string) (string, any, error) {
	var one map[string]any
	if _, err := toml.Decode(line, &one); err != nil || len(one) != 1 {
		return "", nil, fmt.Errorf("each setting is one `key = value` line")
	}
	keyText, _, _, _ := lineParts(line)
	if parts := keyParts(keyText); len(parts) > 1 {
		return "", nil, fmt.Errorf("%s is a dotted key, which TOML reads as a table; to name one setting whose key holds a dot, quote it, as %s = ...",
			strings.TrimSpace(keyText), encodeString(strings.Join(parts, ".")))
	}
	var key string
	var value any
	for key, value = range one {
	}
	return key, value, nil
}

// SetLine returns data with the line that sets key giving it value instead:
// the key as it was written and any comment after the value are kept, and
// every other line is left as it was. With table empty, data is a prefs file
// and key one of its top-level keys; otherwise data is a manifest and key is
// set on its own line inside its [table], as a [prefs] override is. path
// only names the file in errors.
func SetLine(path string, data []byte, table, key string, value any) ([]byte, error) {
	if table == "" {
		if _, err := Parse(path, data); err != nil {
			return nil, err
		}
	}
	rendered, err := EncodeTOML(value)
	if err != nil {
		return nil, fmt.Errorf("%s: %s: %w", path, key, err)
	}
	lines := bytes.Split(data, []byte("\n"))
	current := ""
	for i, raw := range lines {
		line := string(raw)
		trimmed := strings.TrimSpace(line)
		if trimmed == "" || strings.HasPrefix(trimmed, "#") {
			continue
		}
		if strings.HasPrefix(trimmed, "[") {
			current = tableName(trimmed)
			continue
		}
		if current != table {
			continue
		}
		var one map[string]any
		if _, err := toml.Decode(line, &one); err != nil || len(one) != 1 {
			continue
		}
		if _, ok := one[key]; !ok {
			continue
		}
		keyText, _, comment, _ := lineParts(line)
		if len(keyParts(keyText)) != 1 {
			continue // a dotted key that only begins with key
		}
		lines[i] = []byte(strings.TrimRight(keyText, " \t") + " = " + rendered + comment)
		return bytes.Join(lines, []byte("\n")), nil
	}
	if table == "" {
		return nil, fmt.Errorf("%s does not set %q", path, key)
	}
	return nil, fmt.Errorf("%s does not set %q on a line of its own in [%s]", path, key, table)
}

// tableName returns the name of a [table] header line; an array of tables'
// [[name]] header returns a name no [prefs] table has.
func tableName(header string) string {
	if strings.HasPrefix(header, "[[") {
		return header
	}
	code, _, _, _ := lineParts(header) // the text before a comment
	return strings.TrimSpace(strings.TrimSuffix(strings.TrimPrefix(strings.TrimSpace(code), "["), "]"))
}

// lineParts splits a TOML line at its first '=' and at the '#' of a trailing
// comment, both outside quoted strings: key is the text before the '=', value
// the text after it, comment the comment with the blanks before it. Without
// an '=', key holds the text before any comment and ok is false.
func lineParts(line string) (key, value, comment string, ok bool) {
	eq, hash := -1, -1
	quote := ""
scan:
	for i := 0; i < len(line); i++ {
		rest := line[i:]
		switch {
		case quote == "":
			switch {
			case strings.HasPrefix(rest, `"""`), strings.HasPrefix(rest, `'''`):
				quote = rest[:3]
				i += 2
			case rest[0] == '"' || rest[0] == '\'':
				quote = rest[:1]
			case rest[0] == '=' && eq < 0:
				eq = i
			case rest[0] == '#':
				hash = i
				break scan
			}
		case rest[0] == '\\' && quote[0] == '"':
			i++ // an escape in a basic string, \" included
		case strings.HasPrefix(rest, quote):
			i += len(quote) - 1
			quote = ""
		}
	}
	end := len(line)
	if hash >= 0 {
		end = hash
	}
	if eq < 0 {
		return line[:end], "", line[end:], false
	}
	value = strings.TrimRight(line[eq+1:end], " \t")
	return line[:eq], value, line[eq+1+len(value):], true
}

// keyParts splits a TOML key at the dots outside quotes, dropping the quotes
// and the blanks around each part. A bare key is one part, and so is a quoted
// key holding dots.
func keyParts(key string) []string {
	var parts []string
	var part strings.Builder
	quote := byte(0)
	for i := 0; i < len(key); i++ {
		c := key[i]
		switch {
		case quote == 0 && (c == '"' || c == '\''):
			quote = c
		case quote == 0 && c == '.':
			parts = append(parts, strings.TrimSpace(part.String()))
			part.Reset()
		case quote == 0 && (c == ' ' || c == '\t'):
		case quote == '"' && c == '\\' && i+1 < len(key):
			i++
			part.WriteByte(key[i])
		case c == quote:
			quote = 0
		default:
			part.WriteByte(c)
		}
	}
	return append(parts, strings.TrimSpace(part.String()))
}

// CheckSetting reports why store cannot take key = value. A Muxy setting is
// one leaf: a table would stand for a whole section of its settings file.
// A Claude Code setting is a top-level key of settings.json, so a key that
// holds a dot would be a new key of that name, not one inside an object.
func CheckSetting(store, key string, value any) error {
	if key == "" {
		return fmt.Errorf("%s: an empty key", store)
	}
	switch store {
	case "muxy":
		if _, isTable := value.(map[string]any); isTable {
			return fmt.Errorf("muxy: %s is a table; name each setting on its own line, with dotted keys quoted, as \"appearance.dark_theme\" = \"Dracula\"", key)
		}
	case "claude":
		if strings.Contains(key, ".") {
			return fmt.Errorf("claude: %q is not a top-level key of settings.json; this store sets top-level keys only, so a key inside an object such as permissions is the machine's own", key)
		}
	}
	return nil
}

// ParseID splits a setting's <store>:<key> name, as reports, the state file,
// `dotfiles adopt` and [prefs] overrides write it.
func ParseID(id string) (store, key string, err error) {
	store, key, ok := strings.Cut(id, ":")
	if !ok || !slices.Contains(Stores, store) {
		return "", "", fmt.Errorf("%q does not name an app setting; write <store>:<key> with a store from %v, as \"muxy:terminal.font_size\"", id, Stores)
	}
	if key == "" {
		return "", "", fmt.Errorf("%q names no key", id)
	}
	return store, key, nil
}
