# 10-path.zsh - PATH and environment configuration

#=============================================================================
# PATH CONFIGURATION
#=============================================================================
# Note: Order matters - later entries take precedence

# Homebrew (must be early for other tools)
if [[ -d "/opt/homebrew/bin" ]]; then
    eval "$(/opt/homebrew/bin/brew shellenv)"
elif [[ -d "/usr/local/bin" ]]; then
    eval "$(/usr/local/bin/brew shellenv)"
fi

# Go
export GOPATH="${GOPATH:-$HOME/go}"
path=("$GOPATH/bin" $path)

# Ruby (prefer homebrew ruby)
if [[ -d "/opt/homebrew/opt/ruby/bin" ]]; then
    path=("/opt/homebrew/opt/ruby/bin" $path)
    path=("$(gem environment gemdir 2>/dev/null)/bin" $path)
elif [[ -d "/usr/local/opt/ruby/bin" ]]; then
    path=("/usr/local/opt/ruby/bin" $path)
    path=("$(gem environment gemdir 2>/dev/null)/bin" $path)
fi

# Python
[[ -d "/usr/local/opt/python/libexec/bin" ]] && path=("/usr/local/opt/python/libexec/bin" $path)

# Java
[[ -d "/usr/local/opt/openjdk/bin" ]] && path=("/usr/local/opt/openjdk/bin" $path)

# User bins
path=("$HOME/bin" "$HOME/.local/bin" $path)

# Deduplicate PATH
typeset -U path

#=============================================================================
# ENVIRONMENT VARIABLES
#=============================================================================
export EDITOR="${EDITOR:-vim}"
export VISUAL="${VISUAL:-$EDITOR}"
export PAGER="${PAGER:-less}"
export LANG="${LANG:-en_US.UTF-8}"
export LC_ALL="${LC_ALL:-en_US.UTF-8}"

# Wakatime
export ZSH_WAKATIME_BIN="${ZSH_WAKATIME_BIN:-/opt/homebrew/bin/wakatime-cli}"
