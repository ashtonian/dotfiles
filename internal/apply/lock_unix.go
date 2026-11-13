//go:build unix

package apply

import (
	"context"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"syscall"
	"time"
)

// Lock holds an exclusive advisory lock on path until Unlock, so a scheduled
// run and a manual one never apply at the same time. It waits until ctx ends.
func Lock(ctx context.Context, path string) (unlock func() error, err error) {
	if err := os.MkdirAll(filepath.Dir(path), 0o700); err != nil {
		return nil, fmt.Errorf("create lock directory: %w", err)
	}
	f, err := os.OpenFile(path, os.O_CREATE|os.O_RDWR, 0o600)
	if err != nil {
		return nil, fmt.Errorf("open lock %s: %w", path, err)
	}
	for {
		err := syscall.Flock(int(f.Fd()), syscall.LOCK_EX|syscall.LOCK_NB)
		if err == nil {
			return func() error {
				defer f.Close()
				return syscall.Flock(int(f.Fd()), syscall.LOCK_UN)
			}, nil
		}
		if !errors.Is(err, syscall.EWOULDBLOCK) {
			f.Close()
			return nil, fmt.Errorf("lock %s: %w", path, err)
		}
		select {
		case <-ctx.Done():
			f.Close()
			return nil, fmt.Errorf("another dotfiles apply holds %s: %w", path, ctx.Err())
		case <-time.After(200 * time.Millisecond):
		}
	}
}
