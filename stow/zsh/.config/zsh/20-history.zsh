# 20-history.zsh - Shell history configuration

#=============================================================================
# HISTORY SETTINGS
#=============================================================================
HISTFILE="${HISTFILE:-$HOME/.zsh_history}"
HISTSIZE=50000
SAVEHIST=50000

setopt EXTENDED_HISTORY          # Write timestamp to history
setopt INC_APPEND_HISTORY        # Write immediately, not on exit
setopt SHARE_HISTORY             # Share history between sessions
setopt HIST_EXPIRE_DUPS_FIRST    # Expire duplicates first
setopt HIST_IGNORE_DUPS          # Don't record immediate duplicates
setopt HIST_IGNORE_ALL_DUPS      # Delete old duplicate entries
setopt HIST_FIND_NO_DUPS         # Don't display duplicates when searching
setopt HIST_IGNORE_SPACE         # Ignore commands starting with space
setopt HIST_SAVE_NO_DUPS         # Don't write duplicates to file
setopt HIST_REDUCE_BLANKS        # Remove extra blanks
setopt HIST_VERIFY               # Show before executing history expansion

#=============================================================================
# ATUIN (Cross-device history sync)
# Install: brew install atuin && atuin login -u <username>
#=============================================================================
if command -v atuin &>/dev/null; then
    eval "$(atuin init zsh)"
fi
