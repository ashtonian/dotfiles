// Package prefs owns app settings one key at a time.
//
// Some apps keep settings every machine should share in the same file as
// state that belongs to one machine: Muxy's settings.toml holds the theme and
// shortcuts beside the recent projects and the remote servers it pairs with,
// and Claude Code's settings.json holds the theme beside each machine's own
// hooks, permissions and MCP servers. Both apps also rewrite those files. A
// whole-file link or copy would either clobber the machine's state or report
// drift on every change the app makes, so a feature names the keys it owns in
// a prefs file instead, and apply sets each one through the app's own
// interface (a Store), leaving every other key alone.
package prefs

import (
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"maps"
	"math"
	"reflect"
	"regexp"
	"slices"
	"strconv"
	"strings"
)

// Stores names the apps a feature can own settings in, as the keys of its
// `[provides.prefs]` table.
var Stores = []string{"claude", "muxy"}

var (
	// ErrUnavailable means the app a store talks to is not installed here.
	ErrUnavailable = errors.New("app not available")
	// ErrNotApplied means a value was saved but the running app did not take
	// it; it does once the app restarts.
	ErrNotApplied = errors.New("saved, but the running app did not apply it")
)

// Equal reports whether a and b are the same setting value. Numbers compare
// by value, so 13 and 13.0 are equal, as the apps read them.
func Equal(a, b any) bool {
	return reflect.DeepEqual(normalize(a), normalize(b))
}

func normalize(v any) any {
	switch x := v.(type) {
	case json.Number:
		if f, err := x.Float64(); err == nil {
			return f
		}
		return x.String()
	case int64:
		return float64(x)
	case []any:
		out := make([]any, len(x))
		for i, e := range x {
			out[i] = normalize(e)
		}
		return out
	case map[string]any:
		out := make(map[string]any, len(x))
		for k, e := range x {
			out[k] = normalize(e)
		}
		return out
	default:
		return v
	}
}

// CheckValue reports why v cannot be a setting value. Values come from TOML,
// and the stores speak JSON, so TOML's dates and times, and floats that are
// not numbers, have no place.
func CheckValue(v any) error {
	switch x := v.(type) {
	case string, bool, int64, json.Number:
		return nil
	case float64:
		if math.IsNaN(x) || math.IsInf(x, 0) {
			return fmt.Errorf("%v has no JSON form", x)
		}
		return nil
	case []any:
		for _, e := range x {
			if err := CheckValue(e); err != nil {
				return err
			}
		}
		return nil
	case map[string]any:
		for _, e := range x {
			if err := CheckValue(e); err != nil {
				return err
			}
		}
		return nil
	default:
		return fmt.Errorf("a %T is not a setting value; use a string, number, boolean, array or inline table", v)
	}
}

// DecodeJSON decodes one JSON value, keeping each number as written, so a
// float an app stores as 13.0 stays a float when it is adopted.
func DecodeJSON(data []byte) (any, error) {
	dec := json.NewDecoder(bytes.NewReader(data))
	dec.UseNumber()
	var v any
	if err := dec.Decode(&v); err != nil {
		return nil, err
	}
	if _, err := dec.Token(); !errors.Is(err, io.EOF) {
		return nil, errors.New("more than one JSON value")
	}
	return v, nil
}

// EncodeJSON renders v as compact JSON, leaving <, > and & as they are, as
// the apps write them.
func EncodeJSON(v any) ([]byte, error) {
	var b bytes.Buffer
	enc := json.NewEncoder(&b)
	enc.SetEscapeHTML(false)
	if err := enc.Encode(v); err != nil {
		return nil, err
	}
	return bytes.TrimSuffix(b.Bytes(), []byte("\n")), nil
}

var bareKey = regexp.MustCompile(`^[A-Za-z0-9_-]+$`)

// EncodeKey renders key for the left side of a TOML line: bare when TOML
// allows it, quoted otherwise, as every dotted settings key is.
func EncodeKey(key string) string {
	if bareKey.MatchString(key) {
		return key
	}
	return encodeString(key)
}

// EncodeTOML renders v as a TOML inline value, the form a prefs file line and
// `muxy config set` take.
func EncodeTOML(v any) (string, error) {
	switch x := v.(type) {
	case string:
		return encodeString(x), nil
	case bool:
		return strconv.FormatBool(x), nil
	case int64:
		return strconv.FormatInt(x, 10), nil
	case json.Number:
		// A JSON number is a TOML number spelled the same way, and keeps
		// whether it was an integer or a float.
		return x.String(), nil
	case float64:
		if err := CheckValue(x); err != nil {
			return "", err
		}
		s := strconv.FormatFloat(x, 'g', -1, 64)
		if !strings.ContainsAny(s, ".e") {
			s += ".0" // TOML reads 13 as an integer
		}
		return s, nil
	case []any:
		parts := make([]string, len(x))
		for i, e := range x {
			p, err := EncodeTOML(e)
			if err != nil {
				return "", err
			}
			parts[i] = p
		}
		return "[" + strings.Join(parts, ", ") + "]", nil
	case map[string]any:
		if len(x) == 0 {
			return "{}", nil
		}
		keys := slices.Sorted(maps.Keys(x))
		parts := make([]string, len(keys))
		for i, k := range keys {
			p, err := EncodeTOML(x[k])
			if err != nil {
				return "", err
			}
			parts[i] = EncodeKey(k) + " = " + p
		}
		return "{ " + strings.Join(parts, ", ") + " }", nil
	case nil:
		return "", errors.New("null has no TOML form")
	default:
		return "", fmt.Errorf("a %T has no TOML form", v)
	}
}

// encodeString quotes s as a TOML basic string. JSON's escapes are TOML's,
// except that TOML also wants DEL escaped.
func encodeString(s string) string {
	quoted, err := EncodeJSON(s)
	if err != nil {
		// A Go string always encodes; invalid UTF-8 becomes U+FFFD.
		panic(err)
	}
	return strings.ReplaceAll(string(quoted), "\x7f", `\u007f`)
}
