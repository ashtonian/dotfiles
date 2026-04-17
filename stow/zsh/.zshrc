# ~/.zshrc - Main Zsh configuration
# Managed by dotfiles: https://github.com/ashtonian/dotfiles
#
# This file sources modular config from ~/.config/zsh/
# Edit individual modules for specific functionality.

#=============================================================================
# CONFIGURATION DIRECTORY
#=============================================================================
ZSH_CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/zsh"

#=============================================================================
# LOAD MODULES (in order)
#=============================================================================
# 00 - Zinit initialization
# 10 - PATH and environment
# 20 - History settings
# 30 - Plugins (zinit turbo mode)
# 40 - Keybindings
# 50 - Aliases
# 60 - Functions and completions

for config_file in "$ZSH_CONFIG_DIR"/*.zsh(N); do
    source "$config_file"
done

#=============================================================================
# LOCAL OVERRIDES (not in git)
#=============================================================================
[[ -f "$HOME/.zshrc.local" ]] && source "$HOME/.zshrc.local"

# Enable Claude Code agent teams
export CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1

alias claudemore='claude --effort max --dangerously-skip-permissions --disallowedTools "Agent"'
