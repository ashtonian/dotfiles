package apply

import (
	"errors"
	"fmt"

	"github.com/ashtonian/dotfiles/internal/plan"
)

// ErrNotForgettable means a target given to Forget is not an app setting
// whose earlier value the state holds for teardown, or one an enabled feature
// still owns.
var ErrNotForgettable = errors.New("not an app setting waiting to be put back")

// Forget drops the records of app settings that no enabled feature owns and
// whose earlier values wait to be put back, for an app that is gone for good.
// Each action names the earlier value, to set by hand should the app return.
// It changes nothing but the state it returns.
func Forget(p *plan.Plan, prev *State, ids []string) (*Report, *State, error) {
	owned := make(map[string]string, len(p.Prefs))
	for _, pr := range p.Prefs {
		owned[pr.ID()] = pr.Feature
	}
	next := prev.clone()
	report := &Report{}
	for _, id := range ids {
		if feature, ok := owned[id]; ok {
			return nil, nil, fmt.Errorf("%w: %s: %s, enabled here, owns it; disable the feature first, and apply puts back its earlier value",
				ErrNotForgettable, id, feature)
		}
		rec, ok := prev.Prefs[id]
		if !ok {
			return nil, nil, fmt.Errorf("%w: %s: the state holds no record of it", ErrNotForgettable, id)
		}
		earlier := "no value"
		if rec.HadPrevious {
			earlier = oneLine(rec.Previous)
		}
		delete(next.Prefs, id)
		report.Actions = append(report.Actions, Action{Kind: "forget-pref", Path: id,
			Detail: "before dotfiles set it, it was " + earlier})
	}
	return report, next, nil
}
