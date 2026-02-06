# 40-keybindings.zsh - Key bindings

#=============================================================================
# EDITOR MODE
#=============================================================================
bindkey -e  # Emacs mode (use -v for vim mode)

#=============================================================================
# NAVIGATION
#=============================================================================
# Word navigation (Option+Arrow on macOS)
# Works with both "Option sends Esc+" and default modes
bindkey "^[[1;3C" forward-word      # Option+Right (default mode)
bindkey "^[[1;3D" backward-word     # Option+Left (default mode)
bindkey "^[f" forward-word          # Option+F (Esc+ mode)
bindkey "^[b" backward-word         # Option+B (Esc+ mode)

# Line navigation
bindkey "^A" beginning-of-line
bindkey "^E" end-of-line
bindkey "^[[H" beginning-of-line    # Home key
bindkey "^[[F" end-of-line          # End key

# Delete word
bindkey "^W" backward-kill-word
bindkey "^[d" kill-word             # Option+D (Esc+ mode)
bindkey "^[[3;3~" kill-word         # Option+Delete

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

# Clear screen but keep scrollback
bindkey "^L" clear-screen

#=============================================================================
# iTERM2-SPECIFIC
#=============================================================================
# These work when iTerm2 shell integration is loaded
if [[ "$TERM_PROGRAM" == "iTerm.app" ]]; then
    # Cmd+K clears scrollback (handled by iTerm2, but we add shell hook)
    # Option+Enter to insert newline without executing
    bindkey "^[^M" self-insert-unmeta
fi
