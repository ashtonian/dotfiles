# ~/.zshenv - sourced for EVERY zsh (login, interactive, scripts, cron, tools).
# Managed by dotfiles. Keep this FAST and SILENT (no output, minimal forks):
# it runs even for `zsh -c '...'`. Interactive-only config lives in ~/.zshrc.

# --- Environment shared with bash and agents ----------------------------------
# PATH, Homebrew, Go, editor, pager and locale come from one POSIX file that bash
# (~/.bashrc) and Claude Code's Bash tool (CLAUDE_ENV_FILE) read too.
if [[ -r "$HOME/.config/shell/env.sh" ]]; then
    emulate sh -c '. "$HOME/.config/shell/env.sh"'
fi
typeset -U path   # dedupe later additions, keep first occurrence

# --- Agent shells -------------------------------------------------------------
# Codex runs its model-written commands through this zsh: it takes the shell from
# the passwd entry, and ~/.codex/config.toml exports AGENT_SHELL to every command.
# Those commands are written for bash, so give that one shell bash's semantics
# for the zsh behaviours that otherwise turn them into errors: an unmatched glob
# aborting the command (NOMATCH, BAD_PATTERN), `=word` path expansion (EQUALS)
# and unquoted parameters not splitting (SH_WORD_SPLIT). The marker is unset at
# once so zsh scripts that command runs keep normal zsh semantics. Interactive
# shells never see it; Claude Code's Bash tool runs bash (CLAUDE_CODE_SHELL).
if [[ -n "${AGENT_SHELL:-}" && ! -o interactive ]]; then
    setopt NO_NOMATCH NO_BAD_PATTERN NO_EQUALS SH_WORD_SPLIT
    unset AGENT_SHELL
fi
