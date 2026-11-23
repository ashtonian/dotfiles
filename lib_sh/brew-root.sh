# shellcheck shell=bash
# Homebrew steps that need root, for runs that cannot ask for a password.
#
# A LaunchAgent has no terminal, so sudo cannot prompt there: pkg installers,
# App Store installs (mas 7 runs them as root) and some cask upgrades fail with
# "a terminal is required to read the password". sync.sh and
# dotfiles-update.sh leave those steps for a terminal, name them in a warning,
# and carry on with the rest. Sourced by both; bash 3.2 compatible.

# brew_root_available: sudo can run here, either by asking on the controlling
# terminal (sudo reads a password only from /dev/tty) or without a password.
brew_root_available() {
    if (: </dev/tty) 2>/dev/null; then
        return 0
    fi
    sudo -n true 2>/dev/null
}

# brew_casks_needing_root NAME...: print the NAMEs, as given (a token or
# user/tap/token), whose install runs a step as root: a pkg, a keyboard layout,
# or an installer step marked sudo. These are the artifacts Homebrew's own
# requires_sudo? names; uninstall* and zap steps run only on removal or upgrade.
# Fails when Homebrew cannot describe one of the casks.
brew_casks_needing_root() {
    [[ $# -gt 0 ]] || return 0
    local info
    info=$(HOMEBREW_NO_AUTO_UPDATE=1 brew info --json=v2 --cask "$@") || return
    jq -r '
        [.casks[]
         | select(any(.artifacts[];
             has("pkg") or has("keyboard_layout")
             or any(to_entries[] | select(.key | test("^(uninstall|zap)") | not) | .value | .. | objects;
                    .sudo == true)))
         | .token, .full_token] as $root
        | $ARGS.positional[] | select(IN($root[]))' --args "$@" <<<"$info"
}
