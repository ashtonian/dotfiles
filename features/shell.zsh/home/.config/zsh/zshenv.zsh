# zshenv.zsh - sourced for EVERY zsh (login, interactive, scripts, cron, tools)
# through the local ~/.zshenv stub (feature shell.zsh). Keep this FAST and
# SILENT (no output, minimal forks): it runs even for `zsh -c '...'`.
# Interactive-only config lives in zshrc.zsh.

# --- Environment shared with bash and agents ----------------------------------
# PATH, Homebrew, Go, editor, pager and locale come from one POSIX file that bash
# (~/.bashrc) and Claude Code's Bash tool (CLAUDE_ENV_FILE) read too.
if [[ -r "$HOME/.config/shell/env.sh" ]]; then
    emulate sh -c '. "$HOME/.config/shell/env.sh"'
fi
typeset -U path   # dedupe later additions, keep first occurrence

# --- Agent shells -------------------------------------------------------------
# Codex runs its model-written commands as `zsh -lc <command>`: it takes the
# shell from the passwd entry and has no setting to change it. Its system
# config (bin/dotfiles-agents) marks those shells with AGENT_SHELL. The
# commands are written for bash, so hand them to a current bash with the
# environment above already exported. The marker is unset first, so a zsh
# that command starts keeps zsh semantics. Without a bash 4+, fall back to
# bash's behaviour for the zsh features that otherwise turn those commands
# into errors: an unmatched glob aborting the command (NOMATCH, BAD_PATTERN),
# `=word` path expansion (EQUALS) and unquoted parameters not splitting.
# Interactive shells never see the marker; Claude Code's Bash tool runs bash
# itself (CLAUDE_CODE_SHELL).
_dotfiles_agent_bash() {
    [[ -n "${AGENT_SHELL:-}" && -n "${ZSH_EXECUTION_STRING:-}" && ! -o interactive ]] || return 0
    unset AGENT_SHELL
    local candidate
    # macOS's /bin/bash is 3.2, so it is not a candidate.
    for candidate in "${HOMEBREW_PREFIX:-/nonexistent}/bin/bash" /usr/bin/bash; do
        # ZSH_ARGZERO is the shell's own $0, the name `zsh -c` was given.
        [[ -x $candidate ]] && exec "$candidate" -c "$ZSH_EXECUTION_STRING" "$ZSH_ARGZERO" "$@"
    done
    setopt NO_NOMATCH NO_BAD_PATTERN NO_EQUALS SH_WORD_SPLIT
}
# A login shell hands off from zlogin.zsh instead, after ~/.zshenv, ~/.zprofile
# and whatever installers appended to them have run. A plain `zsh -c` reads
# only ~/.zshenv, so it hands off here.
if [[ ! -o login ]]; then
    _dotfiles_agent_bash "$@"
    unfunction _dotfiles_agent_bash
fi
