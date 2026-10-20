# ~/.zshenv - sourced for EVERY zsh (login, interactive, scripts, cron, tools).
# Managed by dotfiles. Keep this FAST and SILENT (no output, minimal forks):
# it runs even for `zsh -c '...'`. Interactive-only config lives in ~/.zshrc.

# --- Homebrew (arch-aware): needed by non-interactive scripts/cron too --------
# Guard avoids re-running the subprocess in inherited child shells.
if [[ -z "${HOMEBREW_PREFIX:-}" ]]; then
    if [[ -x /opt/homebrew/bin/brew ]]; then
        eval "$(/opt/homebrew/bin/brew shellenv)"
    elif [[ -x /usr/local/bin/brew ]]; then
        eval "$(/usr/local/bin/brew shellenv)"
    fi
fi

# --- Go -----------------------------------------------------------------------
export GOPATH="${GOPATH:-$HOME/go}"

# --- PATH: user bins + go bin (Homebrew paths added by shellenv above) --------
typeset -U path   # dedupe, keep first occurrence
path=("$HOME/bin" "$HOME/.local/bin" "$GOPATH/bin" $path)

# --- Core environment (safe in every shell) -----------------------------------
# Prefer nvim if installed, else vim (command -v is a builtin -- no fork).
if [[ -z "${EDITOR:-}" ]]; then
    if command -v nvim &>/dev/null; then export EDITOR=nvim; else export EDITOR=vim; fi
fi
export VISUAL="${VISUAL:-$EDITOR}"
export PAGER="${PAGER:-less}"          # plain less; bat-as-PAGER mangles man pages
export LANG="${LANG:-en_US.UTF-8}"     # set LANG only; never force LC_ALL

# --- zoxide -------------------------------------------------------------------
# Silence zoxide's init-position "doctor": oh-my-zsh loads the zoxide plugin in the
# MIDDLE of ~/.zshrc (plugins init before any post-plugin config), so its "init at
# the very end of the rc file" check always warns even though zoxide works fine --
# and that warning prints on EVERY non-interactive tool shell. Set here (sourced
# before ~/.zshrc) so it is exported before the plugin's init runs.
export _ZO_DOCTOR=0

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
