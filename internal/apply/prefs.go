package apply

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"strings"

	"github.com/ashtonian/dotfiles/internal/plan"
	"github.com/ashtonian/dotfiles/internal/prefs"
)

// PrefStore reads and writes one app's settings a key at a time; package
// prefs has the stores.
type PrefStore interface {
	// Get returns key's current value, and false when it has none.
	Get(ctx context.Context, key string) (value any, ok bool, err error)
	// Set gives key value. An error wrapping prefs.ErrNotApplied means the
	// value was saved and the running app did not take it.
	Set(ctx context.Context, key string, value any) error
	// Unset returns key to the app's default.
	Unset(ctx context.Context, key string) error
}

// pref converges one app setting. An app setting always has some value, so
// unlike a managed copy there is no "nothing there yet" to tell apply's own
// work from the owner's: the first run sets it and records the value it
// replaced, for teardown to put back. After that, a value that is no longer
// what apply set was changed here, and is left for the owner; a plan that
// wants another value (the repository, a profile or the machine manifest
// moved on) is set. A store that fails is a problem for this setting only.
func (r *runner) pref(p plan.Pref) error {
	id := p.ID()
	store, ok := r.env.Prefs[p.Store]
	if !ok {
		return fmt.Errorf("apply: no store for %s", id)
	}
	want, err := prefs.EncodeJSON(p.Value)
	if err != nil {
		return fmt.Errorf("apply: %s: %w", id, err)
	}
	prev, hadPrev := r.prev.Prefs[id]
	keepPrevious := func() {
		if hadPrev {
			r.next.Prefs[id] = prev
		} else {
			delete(r.next.Prefs, id)
		}
	}

	live, present, err := store.Get(r.ctx, p.Key)
	if err != nil {
		if ctxErr := r.ctx.Err(); ctxErr != nil {
			return ctxErr
		}
		r.problem(id, "reading it: "+err.Error())
		keepPrevious()
		return nil
	}
	record := PrefRecord{Want: want, Previous: prev.Previous, HadPrevious: prev.HadPrevious}
	if !hadPrev && present {
		if record.Previous, err = prefs.EncodeJSON(live); err != nil {
			return fmt.Errorf("apply: %s: %w", id, err)
		}
		record.HadPrevious = true
	}

	switch {
	case present && prefs.Equal(live, p.Value):
		if record.Value, err = prefs.EncodeJSON(live); err != nil {
			return fmt.Errorf("apply: %s: %w", id, err)
		}
		r.next.Prefs[id] = record
		return nil
	case hadPrev && !prev.Pending && bytes.Equal(prev.Want, want) && present && rawEqual(live, prev.Value):
		// What the app stored for this value, read back when apply set it.
		record.Value = prev.Value
		r.next.Prefs[id] = record
		return nil
	case hadPrev && !prev.Pending && !(present && rawEqual(live, prev.Value)):
		r.problem(id, fmt.Sprintf("changed here since dotfiles set it (now %s); keep it with `dotfiles adopt %s`, or set it back to %s",
			describe(live, present), id, oneLine(prev.Want)))
		keepPrevious()
		return nil
	}

	kind := "pref"
	if hadPrev && len(prev.Want) > 0 {
		kind = "update-pref" // unchanged since apply set it; the plan's value moved on
	}
	detail := fmt.Sprintf("%s (was %s)", want, describe(live, present))
	if r.dryRun {
		r.act(kind, id, detail)
		return nil
	}

	// The earlier value reaches the state file before the app's setting
	// changes, so teardown can put it back even if this run stops here.
	pending := record
	pending.Want, pending.Value, pending.Pending = prev.Want, prev.Value, true
	r.next.Prefs[id] = pending
	if err := r.checkpoint(); err != nil {
		return err
	}
	if err := store.Set(r.ctx, p.Key, p.Value); err != nil {
		if ctxErr := r.ctx.Err(); ctxErr != nil {
			return ctxErr
		}
		if !errors.Is(err, prefs.ErrNotApplied) {
			r.problem(id, "setting it: "+err.Error())
			keepPrevious()
			return nil
		}
		r.problem(id, err.Error()+"; restart the app to load it")
	}
	stored, has, err := store.Get(r.ctx, p.Key)
	if err != nil {
		if ctxErr := r.ctx.Err(); ctxErr != nil {
			return ctxErr
		}
		r.problem(id, "set, but reading back what the app stored failed, so the next run sets it again: "+err.Error())
		r.act(kind, id, detail)
		return nil
	}
	if !has {
		r.problem(id, "set, but the app shows no value for it afterwards, so the next run sets it again")
		r.act(kind, id, detail)
		return nil
	}
	if record.Value, err = prefs.EncodeJSON(stored); err != nil {
		return fmt.Errorf("apply: %s: %w", id, err)
	}
	if !prefs.Equal(stored, p.Value) {
		detail += "; the app stored " + string(record.Value)
	}
	r.act(kind, id, detail)
	r.next.Prefs[id] = record
	return nil
}

// teardownPrefs puts back the value each setting had before apply set it,
// for the settings no enabled feature owns any more, when the setting still
// has the value apply gave it. When the app is no longer installed nothing
// can be put back: the earlier value is reported once, for the owner to set
// by hand should the app return, and the record dropped.
func (r *runner) teardownPrefs(p *plan.Plan) error {
	want := make(map[string]bool, len(p.Prefs))
	for _, pr := range p.Prefs {
		want[pr.ID()] = true
	}
	for _, id := range sortedKeys(r.prev.Prefs) {
		if want[id] {
			continue
		}
		if err := r.ctx.Err(); err != nil {
			return err
		}
		rec := r.prev.Prefs[id]
		name, key, _ := strings.Cut(id, ":")
		earlier := "no value"
		if rec.HadPrevious {
			earlier = oneLine(rec.Previous)
		}
		store, ok := r.env.Prefs[name]
		if !ok {
			r.problem(id, "set by an earlier dotfiles through a store this build does not have, so it was left as it is")
			continue
		}
		live, present, err := store.Get(r.ctx, key)
		if errors.Is(err, prefs.ErrUnavailable) {
			r.act("forget-pref", id, fmt.Sprintf("%s; before dotfiles set it, it was %s", err, earlier))
			continue
		}
		if err != nil {
			if ctxErr := r.ctx.Err(); ctxErr != nil {
				return ctxErr
			}
			r.problem(id, "no longer managed, and reading it to put back its earlier value failed: "+err.Error())
			r.next.Prefs[id] = rec // try again next run
			continue
		}
		if (rec.HadPrevious && present && rawEqual(live, rec.Previous)) || (!rec.HadPrevious && !present) {
			continue // it has its earlier value: never changed, or put back by a run that stopped before saving
		}
		if !rec.Pending && !(present && rawEqual(live, rec.Value)) {
			r.problem(id, "no longer managed, but changed since dotfiles set it, so it was left as it is")
			continue
		}
		if !r.dryRun {
			if err := restore(r.ctx, store, key, rec); err != nil && !errors.Is(err, prefs.ErrNotApplied) {
				if ctxErr := r.ctx.Err(); ctxErr != nil {
					return ctxErr
				}
				r.problem(id, "no longer managed, and putting back its earlier value failed: "+err.Error())
				r.next.Prefs[id] = rec
				continue
			}
		}
		r.act("restore-pref", id, earlier)
	}
	return nil
}

func restore(ctx context.Context, store PrefStore, key string, rec PrefRecord) error {
	if !rec.HadPrevious {
		return store.Unset(ctx, key)
	}
	previous, err := prefs.DecodeJSON(rec.Previous)
	if err != nil {
		return fmt.Errorf("reading the recorded value: %w", err)
	}
	return store.Set(ctx, key, previous)
}

// oneLine renders a value the state recorded on one line: the state file is
// indented, and so is every value read back from it.
func oneLine(recorded json.RawMessage) string {
	var b bytes.Buffer
	if err := json.Compact(&b, recorded); err != nil {
		return string(recorded)
	}
	return b.String()
}

// rawEqual compares a live value with one the state recorded.
func rawEqual(live any, recorded json.RawMessage) bool {
	v, err := prefs.DecodeJSON(recorded)
	return err == nil && prefs.Equal(live, v)
}

func describe(v any, present bool) string {
	if !present {
		return "no value"
	}
	b, err := prefs.EncodeJSON(v)
	if err != nil {
		return fmt.Sprint(v)
	}
	return string(b)
}
