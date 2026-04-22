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

claudemore() {
  local base="${PWD##*/}"
  local max=0 n
  for f in ~/.claude/sessions/*.json(N); do
    n=$(python3 -c "import json;d=json.load(open('$f'));name=d.get('name','');parts=name.rsplit('-',1);print(parts[1] if len(parts)==2 and parts[0]=='$base' and parts[1].isdigit() else '')" 2>/dev/null)
    [[ -n "$n" && "$n" -gt "$max" ]] && max=$n
  done
  local name="${base}-$((max + 1))"
  echo "Session: ${name}"
  claude --effort max --dangerously-skip-permissions --disallowedTools "Agent" --name "${name}" "$@"
}

claudeclean() {
  local removed=0
  for f in ~/.claude/sessions/*.json(N); do
    local pid="${f:t:r}"
    if ! kill -0 "$pid" 2>/dev/null; then
      rm -f "$f"
      ((removed++))
    fi
  done
  echo "Removed ${removed} dead session(s), $(ls ~/.claude/sessions/*.json(N) 2>/dev/null | wc -l | tr -d ' ') active remaining"
}
