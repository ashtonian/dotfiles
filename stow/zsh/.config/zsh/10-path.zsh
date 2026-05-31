# 10-path.zsh - Interactive language toolchain paths
# Core PATH + env (Homebrew, Go, user bins, EDITOR/PAGER/LANG) now lives in
# ~/.zshenv so NON-interactive shells (zsh -c, scripts, cron, tools) get it too.
# This file only adds language paths that are interactive niceties.

#=============================================================================
# LANGUAGE PATHS
#=============================================================================
# Ruby (prefer Homebrew ruby) — static paths only, no `gem environment` fork
if [[ -d "/opt/homebrew/opt/ruby/bin" ]]; then
    path=("/opt/homebrew/opt/ruby/bin" $path)
    path+=(/opt/homebrew/lib/ruby/gems/*/bin(N))
elif [[ -d "/usr/local/opt/ruby/bin" ]]; then
    path=("/usr/local/opt/ruby/bin" $path)
    path+=(/usr/local/lib/ruby/gems/*/bin(N))
fi

# Python (Homebrew framework bin)
[[ -d "/opt/homebrew/opt/python/libexec/bin" ]] && path=("/opt/homebrew/opt/python/libexec/bin" $path)
[[ -d "/usr/local/opt/python/libexec/bin" ]] && path=("/usr/local/opt/python/libexec/bin" $path)

# Java (OpenJDK)
[[ -d "/opt/homebrew/opt/openjdk/bin" ]] && path=("/opt/homebrew/opt/openjdk/bin" $path)
[[ -d "/usr/local/opt/openjdk/bin" ]] && path=("/usr/local/opt/openjdk/bin" $path)

# Deduplicate PATH (keep first occurrence)
typeset -U path
