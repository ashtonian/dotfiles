# shellcheck shell=bash
# machine_setting VAR: a setting's value on this machine, as `dotfiles apply`
# generated it into env.sh. Read in a subshell, so the other settings stay out
# of the caller's environment. LaunchAgents do not load env.sh, so a script
# they run reads its settings this way.
machine_setting() {
    local generated="$HOME/.config/dotfiles/generated/env.sh"
    (
        # shellcheck source=/dev/null
        if [[ -r "$generated" ]]; then . "$generated" >/dev/null 2>&1; fi
        printf '%s' "${!1:-}"
    )
}
