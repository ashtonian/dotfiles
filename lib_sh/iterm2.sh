#!/bin/bash
# iTerm2 helper functions and integrations
# Source this file in your .zshrc (via 60-functions.zsh)

# Only run in iTerm2
[[ "$TERM_PROGRAM" != "iTerm.app" ]] && return

#=============================================================================
# TAB/WINDOW TITLE MANAGEMENT
#=============================================================================

# Set iTerm2 tab title
iterm2_set_tab_title() {
    echo -ne "\033]0;${1}\007"
}

# Set iTerm2 window title
iterm2_set_window_title() {
    echo -ne "\033]2;${1}\007"
}

# Set both tab and window title
iterm2_set_title() {
    iterm2_set_tab_title "$1"
    iterm2_set_window_title "$1"
}

# Auto-set title based on current directory and git branch
iterm2_auto_title() {
    local dir="${PWD##*/}"
    local branch=""
    if git rev-parse --git-dir &>/dev/null; then
        branch="$(git branch --show-current 2>/dev/null)"
        [[ -n "$branch" ]] && dir="$dir ($branch)"
    fi
    iterm2_set_tab_title "$dir"
}

#=============================================================================
# BADGE MANAGEMENT (text overlay in terminal)
#=============================================================================

# Set iTerm2 badge (persistent text overlay)
iterm2_set_badge() {
    printf "\e]1337;SetBadgeFormat=%s\a" "$(echo -n "$1" | base64)"
}

# Clear badge
iterm2_clear_badge() {
    printf "\e]1337;SetBadgeFormat=\a"
}

#=============================================================================
# PROFILE SWITCHING
#=============================================================================

# Switch to a named profile
iterm2_profile() {
    echo -ne "\033]1337;SetProfile=${1}\007"
}

#=============================================================================
# NOTIFICATIONS
#=============================================================================

# Send iTerm2 notification (works even when minimized)
iterm2_notify() {
    local message="${1:-Command completed}"
    printf "\e]9;%s\a" "$message"
}

# Notify when long command finishes (add to precmd if desired)
iterm2_notify_on_long_command() {
    local threshold="${1:-30}"  # seconds
    if [[ -n "$_iterm2_cmd_start" ]]; then
        local elapsed=$((SECONDS - _iterm2_cmd_start))
        if (( elapsed > threshold )); then
            iterm2_notify "Command finished (${elapsed}s)"
        fi
        unset _iterm2_cmd_start
    fi
}

# Track command start time
iterm2_track_command() {
    _iterm2_cmd_start=$SECONDS
}

#=============================================================================
# CLAUDE CODE INTEGRATIONS
#=============================================================================

# Start Claude with iTerm2 tab title set to session
claude_iterm() {
    local session_name="${1:-claude}"
    iterm2_set_tab_title "Claude: $session_name"
    iterm2_set_badge "Claude"
    if [[ -n "$1" ]]; then
        claude --session-id "$session_name"
    else
        claude
    fi
    iterm2_clear_badge
    iterm2_auto_title
}

# Resume Claude with visual indicator
claude_resume_iterm() {
    iterm2_set_badge "Claude"
    if [[ -n "$1" ]]; then
        claude --resume "$1"
    else
        claude --resume
    fi
    iterm2_clear_badge
    iterm2_auto_title
}

# Create new pane for Claude (vertical split)
claude_split() {
    local session="${1:-}"
    # Use iTerm2's AppleScript to split
    osascript -e 'tell application "iTerm2"
        tell current session of current window
            split vertically with default profile
        end tell
    end tell' 2>/dev/null

    # The new pane becomes active, start claude there
    if [[ -n "$session" ]]; then
        claude_iterm "$session"
    else
        claude_iterm
    fi
}

# Create new tab for Claude
claude_tab() {
    local session="${1:-}"
    osascript -e 'tell application "iTerm2"
        tell current window
            create tab with default profile
        end tell
    end tell' 2>/dev/null

    if [[ -n "$session" ]]; then
        claude_iterm "$session"
    else
        claude_iterm
    fi
}

#=============================================================================
# ALIASES
#=============================================================================
alias ci='claude_iterm'           # Claude with iTerm2 integration
alias cri='claude_resume_iterm'   # Resume with iTerm2 integration
alias csplit='claude_split'       # Claude in split pane
alias ctab='claude_tab'           # Claude in new tab
alias badge='iterm2_set_badge'    # Quick badge set
alias unbadge='iterm2_clear_badge' # Clear badge
alias notify='iterm2_notify'      # Quick notification

#=============================================================================
# HOOKS (optional - uncomment to enable)
#=============================================================================
# Auto-update title on directory change
# autoload -Uz add-zsh-hook
# add-zsh-hook chpwd iterm2_auto_title

# Track long-running commands and notify
# add-zsh-hook preexec iterm2_track_command
# add-zsh-hook precmd iterm2_notify_on_long_command
