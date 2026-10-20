# ~/.config/shell/env.sh - the environment every shell and agent gets.
#
# POSIX sh, sourced by ~/.zshenv (every zsh, including Codex's command shells),
# by ~/.bashrc, and by Claude Code before each Bash tool command
# (CLAUDE_ENV_FILE in ~/.claude/settings.json). It runs that often, so it must
# stay idempotent, silent and fork-free: builtins only, no `brew shellenv`, no
# `fnm env`. Interactive-only setup (prompt, completions, fnm's per-directory
# Node switching, zoxide, direnv) stays in the zsh modules.

# _env_front DIR: put DIR first in PATH (moving it if present) when it exists.
_env_front() {
    [ -d "$1" ] || return 0
    _env_p=":$PATH:"
    while :; do
        case "$_env_p" in
            *":$1:"*) _env_p="${_env_p%%:"$1":*}:${_env_p#*:"$1":}" ;;
            *) break ;;
        esac
    done
    _env_p="${_env_p#:}"
    _env_p="${_env_p%:}"
    PATH="$1${_env_p:+:$_env_p}"
}

# _env_back DIR: append DIR to PATH when it exists and is not already there.
_env_back() {
    [ -d "$1" ] || return 0
    case ":$PATH:" in
        *":$1:"*) ;;
        *) PATH="${PATH:+$PATH:}$1" ;;
    esac
}

_env_main() {
# System directories, as /usr/libexec/path_helper would add them for a login shell.
for _env_f in /etc/paths /etc/paths.d/*; do
    [ -f "$_env_f" ] || continue
    while IFS= read -r _env_d || [ -n "$_env_d" ]; do
        [ -n "$_env_d" ] && _env_back "$_env_d"
    done < "$_env_f"
done

# Homebrew: what `brew shellenv` exports, without running brew.
if [ -x /opt/homebrew/bin/brew ]; then
    HOMEBREW_PREFIX=/opt/homebrew
elif [ -x /usr/local/bin/brew ]; then
    HOMEBREW_PREFIX=/usr/local
fi
if [ -n "${HOMEBREW_PREFIX:-}" ]; then
    export HOMEBREW_PREFIX
    export HOMEBREW_CELLAR="$HOMEBREW_PREFIX/Cellar"
    if [ "$HOMEBREW_PREFIX" = /usr/local ]; then
        export HOMEBREW_REPOSITORY=/usr/local/Homebrew
    else
        export HOMEBREW_REPOSITORY="$HOMEBREW_PREFIX"
    fi
    case ":${INFOPATH:-}:" in
        *":$HOMEBREW_PREFIX/share/info:"*) ;;
        *) export INFOPATH="$HOMEBREW_PREFIX/share/info:${INFOPATH:-}" ;;
    esac
fi

export GOPATH="${GOPATH:-$HOME/go}"
export FNM_DIR="${FNM_DIR:-$HOME/Library/Application Support/fnm}"

# Highest priority last. Language toolchains outrank Homebrew's generic copies,
# and the user's own bins outrank everything.
if [ -n "${HOMEBREW_PREFIX:-}" ]; then
    _env_front "$HOMEBREW_PREFIX/sbin"
    _env_front "$HOMEBREW_PREFIX/bin"
    _env_front "$HOMEBREW_PREFIX/opt/ruby/bin"
    _env_front "$HOMEBREW_PREFIX/opt/python/libexec/bin" # unversioned python, pip
    _env_front "$HOMEBREW_PREFIX/opt/openjdk/bin"
    _env_front "$HOMEBREW_PREFIX/opt/rustup/bin"         # keg-only rustup proxies
    for _env_d in "$HOMEBREW_PREFIX"/lib/ruby/gems/*/bin; do
        _env_back "$_env_d"
    done
fi
# fnm's default Node; interactive zsh puts its per-directory version in front.
_env_front "$FNM_DIR/aliases/default/bin"
_env_front "$GOPATH/bin"
_env_front "$HOME/.local/bin"
_env_front "$HOME/bin"
_env_back "$HOME/.orbstack/bin"
_env_back "$HOME/.local/share/zinit/polaris/bin"
export PATH

if [ -z "${EDITOR:-}" ]; then
    if command -v nvim >/dev/null 2>&1; then EDITOR=nvim; else EDITOR=vim; fi
    export EDITOR
fi
export VISUAL="${VISUAL:-$EDITOR}"
export PAGER="${PAGER:-less}"      # plain less; bat as PAGER mangles man pages
export LANG="${LANG:-en_US.UTF-8}" # LANG only; never force LC_ALL
export DOTFILES="${DOTFILES:-$HOME/.dotfiles}"
# zoxide's init-position check always warns (its plugin loads mid-.zshrc), and
# the warning prints in every non-interactive zsh.
export _ZO_DOCTOR=0
}

# Claude Code also prepends this file to commands in sessions still running zsh,
# where an unmatched glob would abort the command; sh emulation passes it through.
if [ -n "${ZSH_VERSION:-}" ]; then
    emulate sh -c _env_main
else
    _env_main
fi
unset _env_p _env_f _env_d
unset -f _env_main _env_front _env_back
