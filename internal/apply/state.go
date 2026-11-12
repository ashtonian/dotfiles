package apply

import (
	"encoding/json"
	"errors"
	"fmt"
	"maps"
	"os"
	"path/filepath"
)

const stateVersion = 1

// State records what apply installed, so a later run can tell its own files
// from the user's and remove exactly what it added when a feature goes away.
type State struct {
	Version int `json:"version"`
	// Links maps each link apply made to the source it points at.
	Links map[string]string `json:"links"`
	// Copies maps each managed copy to its source and the hash it was written with.
	Copies map[string]CopyRecord `json:"copies"`
	// Generated maps each generated output to the hash it was written with.
	Generated map[string]string `json:"generated"`
	// Stubs lists the stubs apply created.
	Stubs map[string]bool `json:"stubs"`
}

// CopyRecord is a managed copy's source and content hash at write time.
type CopyRecord struct {
	Source string `json:"source"`
	SHA256 string `json:"sha256"`
}

func newState() *State {
	return &State{
		Version:   stateVersion,
		Links:     map[string]string{},
		Copies:    map[string]CopyRecord{},
		Generated: map[string]string{},
		Stubs:     map[string]bool{},
	}
}

func (s *State) clone() *State {
	c := newState()
	maps.Copy(c.Links, s.Links)
	maps.Copy(c.Copies, s.Copies)
	maps.Copy(c.Generated, s.Generated)
	maps.Copy(c.Stubs, s.Stubs)
	return c
}

// LoadState reads the state file; a missing file is a machine apply has
// never touched.
func LoadState(path string) (*State, error) {
	data, err := os.ReadFile(path)
	if errors.Is(err, os.ErrNotExist) {
		return newState(), nil
	}
	if err != nil {
		return nil, fmt.Errorf("read state %s: %w", path, err)
	}
	s := newState()
	if err := json.Unmarshal(data, s); err != nil {
		return nil, fmt.Errorf("parse state %s: %w", path, err)
	}
	if s.Version != stateVersion {
		return nil, fmt.Errorf("state %s has version %d; this dotfiles build reads version %d", path, s.Version, stateVersion)
	}
	return s, nil
}

// Save writes the state atomically, private to the user.
func (s *State) Save(path string) error {
	data, err := json.MarshalIndent(s, "", "  ")
	if err != nil {
		return fmt.Errorf("encode state: %w", err)
	}
	if err := os.MkdirAll(filepath.Dir(path), 0o700); err != nil {
		return fmt.Errorf("create state directory: %w", err)
	}
	return writeAtomic(path, append(data, '\n'), 0o600)
}
