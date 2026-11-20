package prefs

import (
	"bytes"
	"fmt"
	"os"
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
		var one map[string]any
		if _, err := toml.Decode(line, &one); err != nil || len(one) != 1 {
			return nil, fmt.Errorf("%s:%d: each setting is one `key = value` line", path, n)
		}
		for key, value := range one {
			if first, dup := seen[key]; dup {
				return nil, fmt.Errorf("%s:%d: %q is already set on line %d; to name a dotted setting, quote it, as \"a.b\" = 1", path, n, key, first)
			}
			if err := CheckValue(value); err != nil {
				return nil, fmt.Errorf("%s:%d: %s: %w", path, n, key, err)
			}
			seen[key] = n
			entries = append(entries, Entry{Key: key, Value: value, Line: n})
		}
	}
	return entries, nil
}

// SetLine returns the prefs file data with the line that sets key giving it
// value instead, every other line as it was. path only names the file in
// errors.
func SetLine(path string, data []byte, key string, value any) ([]byte, error) {
	entries, err := Parse(path, data)
	if err != nil {
		return nil, err
	}
	for _, e := range entries {
		if e.Key != key {
			continue
		}
		rendered, err := EncodeTOML(value)
		if err != nil {
			return nil, fmt.Errorf("%s: %s: %w", path, key, err)
		}
		lines := bytes.Split(data, []byte("\n"))
		lines[e.Line-1] = []byte(EncodeKey(key) + " = " + rendered)
		return bytes.Join(lines, []byte("\n")), nil
	}
	return nil, fmt.Errorf("%s does not set %q", path, key)
}

// CheckSetting reports why store cannot take key = value. A Muxy setting is
// one leaf: a table would stand for a whole section of its settings file,
// and an unquoted dotted key reads as one.
func CheckSetting(store, key string, value any) error {
	if key == "" {
		return fmt.Errorf("%s: an empty key", store)
	}
	if _, isTable := value.(map[string]any); isTable && store == "muxy" {
		return fmt.Errorf("muxy: %s is a table; name each setting on its own line, with dotted keys quoted, as \"appearance.dark_theme\" = \"Dracula\"", key)
	}
	return nil
}
