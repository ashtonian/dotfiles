//go:build windows

package apply

import (
	"context"
	"errors"
)

// Lock is part of the Windows backend (rollout step 7). Until then apply
// refuses to run on Windows rather than run unlocked.
func Lock(ctx context.Context, path string) (func() error, error) {
	return nil, errors.New("dotfiles apply does not support Windows yet")
}
