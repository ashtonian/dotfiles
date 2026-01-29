# 40-keybindings.zsh - Key bindings

#=============================================================================
# EDITOR MODE
#=============================================================================
bindkey -e  # Emacs mode (use -v for vim mode)

#=============================================================================
# NAVIGATION
#=============================================================================
# Word navigation (Option+Arrow on macOS)
bindkey "^[[1;3C" forward-word      # Option+Right
bindkey "^[[1;3D" backward-word     # Option+Left

# Line navigation
bindkey "^A" beginning-of-line
bindkey "^E" end-of-line

# Delete word
bindkey "^W" backward-kill-word
bindkey "^[d" kill-word             # Option+D

#=============================================================================
# HISTORY SEARCH
#=============================================================================
bindkey "^R" history-incremental-search-backward
bindkey "^S" history-incremental-search-forward

# Up/Down for history prefix search
autoload -Uz up-line-or-beginning-search down-line-or-beginning-search
zle -N up-line-or-beginning-search
zle -N down-line-or-beginning-search
bindkey "^[[A" up-line-or-beginning-search
bindkey "^[[B" down-line-or-beginning-search

#=============================================================================
# EDITING
#=============================================================================
bindkey "^X^_" redo                 # Ctrl+X Ctrl+_
bindkey "^_" undo                   # Ctrl+_

# Accept autosuggestion
bindkey "^F" autosuggest-accept     # Ctrl+F or use Right Arrow
