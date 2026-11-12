// Package resolve decides which features a machine enables and what each
// setting's value is, from feature defaults, profiles in order, and the
// machine manifest.
package resolve

import (
	"errors"
	"fmt"
	"maps"
	"slices"
	"sort"
	"strings"

	"github.com/ashtonian/dotfiles/internal/manifest"
)

// ErrConflict wraps every resolution failure the manifests cause, so callers
// can tell them from programming errors.
var ErrConflict = errors.New("feature resolution failed")

// Decision records whether a feature is enabled and which layer decided it.
type Decision struct {
	Enabled bool
	// Source is "default", "profile:<name>", "machine", "required by <id>",
	// or "unsupported on <os>".
	Source string
	// Explicit is true when a profile or the machine manifest named the
	// feature, as opposed to its default.
	Explicit bool
}

// Value is a resolved setting value and the layer that set it.
type Value struct {
	Value  any
	Source string
}

// Result is the outcome of resolution.
type Result struct {
	Decisions map[string]Decision
	// Order lists enabled features with each one after everything it
	// requires; ties break by id.
	Order []string
	// Settings holds every setting declared by an enabled feature that has a
	// value, keyed by setting name.
	Settings map[string]Value
	// Missing lists required settings without a value, per feature. Apply
	// skips those features and reports them.
	Missing map[string][]string
}

// Resolve applies feature defaults, then each of the machine's profiles in
// order, then the machine's own overrides, for the platform goos.
func Resolve(features map[string]*manifest.Feature, profiles map[string]*manifest.Profile,
	machine *manifest.Machine, goos string) (*Result, error) {
	decisions := make(map[string]Decision, len(features))
	for id, f := range features {
		decisions[id] = Decision{Enabled: f.Default, Source: "default"}
	}

	apply := func(sel manifest.Selection, source string) error {
		for _, id := range sel.Enable {
			if _, ok := features[id]; !ok {
				return fmt.Errorf("%w: %s enables unknown feature %q", ErrConflict, source, id)
			}
			decisions[id] = Decision{Enabled: true, Source: source, Explicit: true}
		}
		for _, id := range sel.Disable {
			if _, ok := features[id]; !ok {
				return fmt.Errorf("%w: %s disables unknown feature %q", ErrConflict, source, id)
			}
			decisions[id] = Decision{Enabled: false, Source: source, Explicit: true}
		}
		return nil
	}
	for _, name := range machine.Profiles {
		p, ok := profiles[name]
		if !ok {
			return nil, fmt.Errorf("%w: machine.toml names unknown profile %q", ErrConflict, name)
		}
		if err := apply(p.Features, "profile:"+name); err != nil {
			return nil, err
		}
	}
	if err := apply(machine.Features, "machine"); err != nil {
		return nil, err
	}

	// A shared profile may enable a feature another OS lacks; it is simply
	// inactive here.
	for id, f := range features {
		if d := decisions[id]; d.Enabled && !f.Supports(goos) {
			decisions[id] = Decision{Enabled: false, Source: "unsupported on " + goos, Explicit: d.Explicit}
		}
	}

	if err := pullRequirements(features, decisions, goos); err != nil {
		return nil, err
	}
	if err := checkConflicts(features, decisions); err != nil {
		return nil, err
	}
	order, err := dependencyOrder(features, decisions)
	if err != nil {
		return nil, err
	}
	settings, missing, err := resolveSettings(features, profiles, machine, order)
	if err != nil {
		return nil, err
	}
	return &Result{Decisions: decisions, Order: order, Settings: settings, Missing: missing}, nil
}

func pullRequirements(features map[string]*manifest.Feature, decisions map[string]Decision, goos string) error {
	queue := enabledIDs(decisions)
	for len(queue) > 0 {
		id := queue[0]
		queue = queue[1:]
		for _, req := range features[id].Requires {
			rf, ok := features[req]
			if !ok {
				return fmt.Errorf("%w: %s requires unknown feature %q", ErrConflict, id, req)
			}
			d := decisions[req]
			switch {
			case d.Enabled:
				continue
			case !rf.Supports(goos):
				return fmt.Errorf("%w: %s requires %s, which does not run on %s", ErrConflict, id, req, goos)
			case d.Explicit:
				return fmt.Errorf("%w: %s requires %s, which %s disables", ErrConflict, id, req, d.Source)
			}
			decisions[req] = Decision{Enabled: true, Source: "required by " + id}
			queue = append(queue, req)
		}
	}
	return nil
}

func checkConflicts(features map[string]*manifest.Feature, decisions map[string]Decision) error {
	for _, id := range enabledIDs(decisions) {
		for _, other := range features[id].Conflicts {
			if decisions[other].Enabled {
				return fmt.Errorf("%w: %s conflicts with %s; disable one of them", ErrConflict, id, other)
			}
		}
	}
	return nil
}

// dependencyOrder sorts enabled features so each comes after what it
// requires, deterministically.
func dependencyOrder(features map[string]*manifest.Feature, decisions map[string]Decision) ([]string, error) {
	enabled := enabledIDs(decisions)
	const (
		unvisited = iota
		visiting
		done
	)
	state := make(map[string]int, len(enabled))
	order := make([]string, 0, len(enabled))
	var visit func(id string, path []string) error
	visit = func(id string, path []string) error {
		switch state[id] {
		case done:
			return nil
		case visiting:
			return fmt.Errorf("%w: requirement cycle: %s", ErrConflict, strings.Join(append(path, id), " -> "))
		}
		state[id] = visiting
		reqs := slices.Clone(features[id].Requires)
		sort.Strings(reqs)
		for _, req := range reqs {
			if err := visit(req, append(path, id)); err != nil {
				return err
			}
		}
		state[id] = done
		order = append(order, id)
		return nil
	}
	for _, id := range enabled {
		if err := visit(id, nil); err != nil {
			return nil, err
		}
	}
	return order, nil
}

func resolveSettings(features map[string]*manifest.Feature, profiles map[string]*manifest.Profile,
	machine *manifest.Machine, order []string) (map[string]Value, map[string][]string, error) {
	type declared struct {
		feature string
		setting manifest.Setting
	}
	all := map[string]declared{}
	for id, f := range features {
		for name, s := range f.Settings {
			all[name] = declared{id, s}
		}
	}

	values := map[string]Value{}
	for _, id := range order {
		for name, s := range features[id].Settings {
			if s.Default != nil {
				values[name] = Value{Value: s.Default, Source: "default"}
			}
		}
	}
	set := func(src map[string]any, source string) error {
		for _, name := range slices.Sorted(maps.Keys(src)) {
			d, ok := all[name]
			if !ok {
				return fmt.Errorf("%w: %s sets unknown setting %q", ErrConflict, source, name)
			}
			if err := manifest.CheckValue(d.setting.Type, src[name]); err != nil {
				return fmt.Errorf("%w: %s: setting %q: %w", ErrConflict, source, name, err)
			}
			if slices.Contains(order, d.feature) {
				values[name] = Value{Value: src[name], Source: source}
			}
		}
		return nil
	}
	for _, name := range machine.Profiles {
		if err := set(profiles[name].Settings, "profile:"+name); err != nil {
			return nil, nil, err
		}
	}
	if err := set(machine.Settings, "machine"); err != nil {
		return nil, nil, err
	}

	missing := map[string][]string{}
	for _, id := range order {
		for name, s := range features[id].Settings {
			if _, ok := values[name]; s.Required && !ok {
				missing[id] = append(missing[id], name)
			}
		}
		sort.Strings(missing[id])
	}
	for id, names := range missing {
		if len(names) == 0 {
			delete(missing, id)
		}
	}
	return values, missing, nil
}

// Runnable returns the enabled features apply can install: Order without any
// feature missing a required setting, or requiring one that is.
func (r *Result) Runnable(features map[string]*manifest.Feature) []string {
	blocked := map[string]bool{}
	for id := range r.Missing {
		blocked[id] = true
	}
	var runnable []string
	for _, id := range r.Order { // requirements come first, so blocking propagates forward
		for _, req := range features[id].Requires {
			if blocked[req] {
				blocked[id] = true
			}
		}
		if !blocked[id] {
			runnable = append(runnable, id)
		}
	}
	return runnable
}

func enabledIDs(decisions map[string]Decision) []string {
	var ids []string
	for id, d := range decisions {
		if d.Enabled {
			ids = append(ids, id)
		}
	}
	sort.Strings(ids)
	return ids
}
