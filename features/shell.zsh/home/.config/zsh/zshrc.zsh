# zshrc.zsh - Main Zsh configuration (feature shell.zsh)
# The local ~/.zshrc stub sources this file; installers that append to
# ~/.zshrc change only the stub. It sources the numbered modules beside it,
# then the generated fragments of the enabled features.

#=============================================================================
# CONFIGURATION DIRECTORY
#=============================================================================
# This file's own directory: dotfiles links the modules into ~/.config/zsh
# whatever XDG_CONFIG_HOME says.
ZSH_CONFIG_DIR=${${(%):-%x}:h}

#=============================================================================
# REAL-SESSION DETECTION
#=============================================================================
# Distinguish a real interactive session from tool/agent shells invoked as
# `zsh -i -c '...'` (which set ZSH_EXECUTION_STRING). Interactive-only noise
# (greeting) and command-replacing/safety aliases are gated on this so tool
# shells get clean, predictable behavior. See 50-aliases.zsh / 70-greeting.zsh.
if [[ -o interactive && -z "${ZSH_EXECUTION_STRING:-}" ]]; then
    ZSH_REAL_SESSION=1
else
    ZSH_REAL_SESSION=0
fi

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

# Numbered modules only: zshenv.zsh, zprofile.zsh, zlogin.zsh and this file live
# here too. A local module needs a number as well, such as 80-local.zsh.
for config_file in "$ZSH_CONFIG_DIR"/[0-9][0-9]-*.zsh(N); do
    source "$config_file"
done

# Interactive fragments of the enabled features (dotfiles apply).
_dotfiles_generated_zshrc="$HOME/.config/dotfiles/generated/zshrc.zsh"
[[ -r "$_dotfiles_generated_zshrc" ]] && source "$_dotfiles_generated_zshrc"
unset _dotfiles_generated_zshrc

#=============================================================================
# LOCAL OVERRIDES (not in git)
#=============================================================================
[[ -f "$HOME/.zshrc.local" ]] && source "$HOME/.zshrc.local"

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

# Open the gitstead fleet `fleet` (its workspaces come from the overlays'
# gitstead config): one tab per workspace, one split per agent, claudemore in
# each, as tmux -CC panes inside iTerm. gitstead flags pass through:
# `claudefleet --agent astra`, `--launcher iterm`, `--launcher muxy`, `--fresh`.
# One workspace: `gitstead ws open <workspace>`.
claudefleet() {
  gitstead fleet open fleet "$@"
}

(( $+functions[dotfiles_greeting] )) && dotfiles_greeting
