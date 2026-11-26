package apply

import (
	"encoding/json"
	"errors"
	"fmt"
	"maps"
	"os"
	"path/filepath"

	"github.com/ashtonian/dotfiles/internal/atomicfile"
)

// stateVersion is the state file format this build writes. Version 2 added
// prefs and version 3 teardowns; a build refuses a newer file rather than
// save over it without what it does not know.
const stateVersion = 3

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
	// Prefs maps each app setting apply owns, by plan.Pref.ID, to what it set
	// and what it replaced.
	Prefs map[string]PrefRecord `json:"prefs"`
	// Agents maps each LaunchAgent label apply installed to its plist.
	Agents map[string]AgentRecord `json:"agents"`
	// Teardowns maps each enabled feature with a teardown hook to a copy of
	// it, which runs once the feature is no longer enabled, even if it is gone
	// from the repository by then.
	Teardowns map[string]TeardownRecord `json:"teardowns"`
}

// TeardownRecord is a feature's teardown hook as apply last planned it.
type TeardownRecord struct {
	Script         []byte   `json:"script"` // the script's contents
	Sudo           bool     `json:"sudo,omitempty"`
	TimeoutSeconds int64    `json:"timeout_seconds"`
	Env            []string `json:"env,omitempty"`
}

// AgentRecord is an installed LaunchAgent: its plist, the hash apply wrote it
// with, and the launchd.Definition of the plist launchd last loaded, empty
// when unknown (a load failed). The definition differs from the plist's while
// a reload waits for a later apply.
type AgentRecord struct {
	Path   string `json:"path"`
	SHA256 string `json:"sha256"`
	Loaded string `json:"loaded"`
}

// CopyRecord is a managed copy's source and content hash at write time.
type CopyRecord struct {
	Source string `json:"source"`
	SHA256 string `json:"sha256"`
}

// PrefRecord is an app setting apply owns: the value it last set, and the
// value the setting had before apply first set it, which teardown puts back.
type PrefRecord struct {
	// Want is the value apply last set. A plan that wants another means the
	// repository, a profile or the machine manifest moved on. Empty until
	// apply has set it once.
	Want json.RawMessage `json:"want,omitempty"`
	// Value is what the app stored for Want, as apply read it back: Want, or
	// Want as the app rounds it (Muxy keeps a float as 32 bits).
	Value json.RawMessage `json:"value,omitempty"`
	// Previous is meaningful only with HadPrevious; without it the setting had
	// no value, and teardown unsets it.
	Previous    json.RawMessage `json:"previous,omitempty"`
	HadPrevious bool            `json:"had_previous"`
	// Pending is saved, with Previous, before apply changes the setting, and
	// cleared once apply has read back what the app stored. A run that stops
	// in between leaves it set: the setting then holds either Value or what
	// apply was setting, and the next run sets it again instead of calling
	// either one a change made here.
	Pending bool `json:"pending,omitempty"`
}

func newState() *State {
	return &State{
		Version:   stateVersion,
		Links:     map[string]string{},
		Copies:    map[string]CopyRecord{},
		Generated: map[string]string{},
		Stubs:     map[string]bool{},
		Prefs:     map[string]PrefRecord{},
		Agents:    map[string]AgentRecord{},
		Teardowns: map[string]TeardownRecord{},
	}
}

func (s *State) clone() *State {
	c := newState()
	c.overlay(s)
	return c
}

// overlay copies every record of o into s, replacing records of the same
// path, label or setting.
func (s *State) overlay(o *State) {
	maps.Copy(s.Links, o.Links)
	maps.Copy(s.Copies, o.Copies)
	maps.Copy(s.Generated, o.Generated)
	maps.Copy(s.Stubs, o.Stubs)
	maps.Copy(s.Prefs, o.Prefs)
	maps.Copy(s.Agents, o.Agents)
	maps.Copy(s.Teardowns, o.Teardowns)
}

// LoadState reads the state file; a missing file is a machine apply has
// never touched. A version 1 file, from before app settings existed, has no
// prefs, which reads as none set; one before version 3 has no teardowns. A file from a newer build is refused: saving
// over it would drop what this build does not know.
func LoadState(path string) (*State, error) {
	data, err := os.ReadFile(path)
	if errors.Is(err, os.ErrNotExist) {
		return newState(), nil
	}
	if err != nil {
		return nil, fmt.Errorf("read state %s: %w", path, err)
	}
	s := newState()
	s.Version = 0 // the file's own, or none
	if err := json.Unmarshal(data, s); err != nil {
		return nil, fmt.Errorf("parse state %s: %w", path, err)
	}
	if s.Version > stateVersion {
		return nil, fmt.Errorf("state %s has version %d; this dotfiles build reads versions 1 to %d, so a newer dotfiles wrote it: update dotfiles (git pull in the repository) and run that", path, s.Version, stateVersion)
	}
	if s.Version < 1 {
		return nil, fmt.Errorf("state %s has no version; dotfiles did not write it", path)
	}
	s.Version = stateVersion
	if s.Prefs == nil {
		s.Prefs = map[string]PrefRecord{}
	}
	if s.Teardowns == nil {
		s.Teardowns = map[string]TeardownRecord{}
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
	return atomicfile.Write(path, append(data, '\n'), 0o600)
}
