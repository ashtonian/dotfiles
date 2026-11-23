# shellcheck shell=bash
# start_launch_agent LABEL FEATURE: (re)start a LaunchAgent that dotfiles apply
# owns, right after the setup step it waits for. A loaded agent restarts, so it
# reads what the step changed; one not loaded yet is installed and loaded by
# apply. Fails, saying why, when the agent's feature is off on this Mac.
# Sourced by bin/otel-agent and bin/agent-monitor (zsh, where `status` is
# read-only); needs DOTFILES_DIR.
start_launch_agent() {
    local label=$1 feature=$2 engine=${DOTFILES_BIN:-$HOME/.local/bin/dotfiles} rc=0
    if launchctl print "gui/$UID/$label" >/dev/null 2>&1; then
        launchctl kickstart -k "gui/$UID/$label"
        return
    fi
    if [[ ! -x $engine ]]; then
        echo "$engine is missing; run $DOTFILES_DIR/sync.sh apply" >&2
        return 69
    fi
    # Exit 1 is a problem elsewhere in the machine, which apply printed.
    "$engine" apply --repo "$DOTFILES_DIR" || rc=$?
    if (( rc > 1 )); then
        echo "dotfiles apply failed (exit $rc); run $engine doctor" >&2
        return 70
    fi
    if ! launchctl print "gui/$UID/$label" >/dev/null 2>&1; then
        echo "$label is not loaded: enable the $feature feature for this Mac (docs/MACHINE-FEATURES.md), or see $engine doctor" >&2
        return 78
    fi
}
