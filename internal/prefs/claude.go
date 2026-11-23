package prefs

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io/fs"
	"os"
	"path/filepath"

	"github.com/ashtonian/dotfiles/internal/atomicfile"
)

// claudeWriteAttempts bounds how often Set and Unset start over when Claude
// Code rewrites the file between their read and their write.
const claudeWriteAttempts = 3

// Claude reads and writes top-level keys of Claude Code's user settings,
// ~/.claude/settings.json. Claude Code rewrites that file itself (/config,
// /theme, /model, plugin installs), and each machine's copy holds its own
// hooks, permissions and MCP servers, so only the named keys change: every
// other key keeps its value and its place.
type Claude struct {
	path string
}

// NewClaude returns the store for the user settings under home.
func NewClaude(home string) *Claude {
	return &Claude{path: filepath.Join(home, ".claude", "settings.json")}
}

// Get returns key's value, and false when the file or the key is missing.
func (c *Claude) Get(_ context.Context, key string) (any, bool, error) {
	data, err := os.ReadFile(c.path)
	if errors.Is(err, fs.ErrNotExist) {
		return nil, false, nil
	}
	if err != nil {
		return nil, false, fmt.Errorf("reading %s: %w", c.path, err)
	}
	members, err := parseObject(data)
	if err != nil {
		return nil, false, fmt.Errorf("reading %s: %w", c.path, err)
	}
	// JSON.parse, as Claude Code reads it, keeps the last of a repeated key.
	for i := len(members) - 1; i >= 0; i-- {
		if members[i].key == key {
			v, err := DecodeJSON(members[i].value)
			if err != nil {
				return nil, false, fmt.Errorf("reading %s: %s: %w", c.path, key, err)
			}
			return v, true, nil
		}
	}
	return nil, false, nil
}

// Set gives key value, in its place if the file has it, or last.
func (c *Claude) Set(ctx context.Context, key string, value any) error {
	raw, err := EncodeJSON(value)
	if err != nil {
		return fmt.Errorf("setting %s in %s: %w", key, c.path, err)
	}
	return c.update(ctx, key, func(members []member) []member {
		found := false
		for i := range members {
			if members[i].key == key {
				members[i].value = raw
				found = true
			}
		}
		if !found {
			members = append(members, member{key: key, value: raw})
		}
		return members
	})
}

// Unset removes key.
func (c *Claude) Unset(ctx context.Context, key string) error {
	return c.update(ctx, key, func(members []member) []member {
		kept := members[:0]
		for _, m := range members {
			if m.key != key {
				kept = append(kept, m)
			}
		}
		return kept
	})
}

// update rewrites the file with change applied. Claude Code may write the
// file at any moment, so the write goes ahead only while the file still
// holds what change was computed from; that narrows the window in which a
// concurrent write is lost to the rename itself.
func (c *Claude) update(ctx context.Context, key string, change func([]member) []member) error {
	for range claudeWriteAttempts {
		if err := ctx.Err(); err != nil {
			return err
		}
		before, mode, err := c.read()
		if err != nil {
			return err
		}
		members := []member{}
		if before != nil {
			if members, err = parseObject(before); err != nil {
				return fmt.Errorf("reading %s: %w", c.path, err)
			}
		}
		after, err := renderObject(change(members), before == nil || bytes.HasSuffix(before, []byte("\n")))
		if err != nil {
			return fmt.Errorf("setting %s in %s: %w", key, c.path, err)
		}
		if bytes.Equal(before, after) {
			return nil
		}
		now, _, err := c.read()
		if err != nil {
			return err
		}
		if !bytes.Equal(now, before) {
			continue
		}
		if before == nil {
			if err := os.MkdirAll(filepath.Dir(c.path), 0o700); err != nil {
				return fmt.Errorf("creating %s: %w", filepath.Dir(c.path), err)
			}
		}
		target, err := c.target()
		if err != nil {
			return err
		}
		return atomicfile.Write(target, after, mode)
	}
	return fmt.Errorf("setting %s in %s: the file kept changing while it was being written", key, c.path)
}

// target is the file a write replaces: the settings file, or the file it
// links to, so a settings.json kept elsewhere and linked into ~/.claude stays
// linked.
func (c *Claude) target() (string, error) {
	info, err := os.Lstat(c.path)
	if errors.Is(err, fs.ErrNotExist) || (err == nil && info.Mode()&fs.ModeSymlink == 0) {
		return c.path, nil
	}
	if err != nil {
		return "", fmt.Errorf("reading %s: %w", c.path, err)
	}
	resolved, err := filepath.EvalSymlinks(c.path)
	if err != nil {
		return "", fmt.Errorf("%s is a link to a file that cannot be written: %w", c.path, err)
	}
	return resolved, nil
}

// read returns the file's content and mode; nil content means it does not
// exist, and a new file is private to the user.
func (c *Claude) read() ([]byte, fs.FileMode, error) {
	data, err := os.ReadFile(c.path)
	if errors.Is(err, fs.ErrNotExist) {
		return nil, 0o600, nil
	}
	if err != nil {
		return nil, 0, fmt.Errorf("reading %s: %w", c.path, err)
	}
	info, err := os.Stat(c.path)
	if err != nil {
		return nil, 0, fmt.Errorf("reading %s: %w", c.path, err)
	}
	return data, info.Mode().Perm(), nil
}

// member is one top-level key of a JSON object and its value as written.
type member struct {
	key   string
	value json.RawMessage
}

// parseObject lists a JSON object's top-level members in order.
func parseObject(data []byte) ([]member, error) {
	dec := json.NewDecoder(bytes.NewReader(data))
	if tok, err := dec.Token(); err != nil || tok != json.Delim('{') {
		return nil, errors.New("not a JSON object")
	}
	var members []member
	for dec.More() {
		tok, err := dec.Token()
		if err != nil {
			return nil, err
		}
		key, ok := tok.(string)
		if !ok {
			return nil, errors.New("not a JSON object")
		}
		var value json.RawMessage
		if err := dec.Decode(&value); err != nil {
			return nil, fmt.Errorf("%s: %w", key, err)
		}
		members = append(members, member{key: key, value: value})
	}
	if _, err := dec.Token(); err != nil {
		return nil, err
	}
	if _, err := dec.Token(); err == nil {
		return nil, errors.New("more than one JSON value")
	}
	return members, nil
}

// renderObject writes members as Claude Code does: indented by two spaces,
// with the final newline the file had.
func renderObject(members []member, newline bool) ([]byte, error) {
	var compact bytes.Buffer
	compact.WriteByte('{')
	for i, m := range members {
		if i > 0 {
			compact.WriteByte(',')
		}
		key, err := EncodeJSON(m.key)
		if err != nil {
			return nil, err
		}
		compact.Write(key)
		compact.WriteByte(':')
		compact.Write(m.value)
	}
	compact.WriteByte('}')
	var out bytes.Buffer
	if err := json.Indent(&out, compact.Bytes(), "", "  "); err != nil {
		return nil, err
	}
	if newline {
		out.WriteByte('\n')
	}
	return out.Bytes(), nil
}
