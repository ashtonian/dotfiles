# shellcheck shell=bash
# The sync lock: one machine-maintenance run at a time. sync.sh (every 4 hours)
# and bin/dotfiles-update.sh (weekly) each hold it for their whole run. Without
# it, `brew upgrade` runs beside sync's `brew bundle` on the same prefix, and
# beside sync's `dotfiles apply`, which finds a formula's binary unlinked
# mid-upgrade and removes the LaunchAgent that waits for it until the next sync.
#
# The lock is a BSD flock (/usr/bin/lockf) on logs/sync.flock, held on
# descriptor 9 by the script's own shell. The file stays after a run; its
# existence never means the lock is held.

# sync_lock_take LOG_DIR WAIT: hold the sync lock on descriptor 9, waiting up
# to WAIT seconds for another run to release it (0: fail at once). Returns 0
# once held, 75 (EX_TEMPFAIL) when another run still holds it, or lockf's
# other status. On failure descriptor 9 is closed.
#
# A descriptor 9 inherited open on the lock file comes from the run that
# started this process (dotfiles-update.sh runs sync.sh as its last stage), so
# this process is part of that run: it locks the inherited descriptor, which
# flock grants to the open file description already holding the lock, rather
# than opening the file again, which its own run's lock would refuse.
sync_lock_take() {
    local file="$1/sync.flock" wait=$2 status=0
    if ! sync_lock_inherited "$file"; then
        exec 9>>"$file" || return 73
    fi
    /usr/bin/lockf -s -t "$wait" 9 || status=$?
    if [[ $status -ne 0 ]]; then
        exec 9>&-
    fi
    return "$status"
}

# sync_lock_inherited FILE: whether descriptor 9 is open on FILE (same device
# and inode, through fstat; stat of /dev/fd/9 reports devfs's device instead).
sync_lock_inherited() {
    local held file
    held=$(stat -f '%d:%i' 2>/dev/null <&9) || return 1
    file=$(stat -f '%d:%i' "$1" 2>/dev/null) || return 1
    [[ "$held" == "$file" ]]
}

# without_sync_lock CMD...: run CMD in a subshell with descriptor 9 closed,
# while the calling shell keeps holding the lock. A daemon a step starts (op,
# gpg-agent, an ssh control master, a Homebrew service) would otherwise inherit
# the descriptor and keep the lock after the run, and every later run would
# find another one running.
without_sync_lock() {
    ( exec 9>&-; "$@" )
}
