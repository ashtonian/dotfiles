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
