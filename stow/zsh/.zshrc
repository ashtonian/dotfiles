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

for config_file in "$ZSH_CONFIG_DIR"/*.zsh(N); do
    source "$config_file"
done

#=============================================================================
# LOCAL OVERRIDES (not in git)
#=============================================================================
[[ -f "$HOME/.zshrc.local" ]] && source "$HOME/.zshrc.local"

# Enable Claude Code agent teams
export CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1

_claude_named_session() {
  local model="$1"
  shift
  local base="${PWD##*/}"
  local host="${HOST%%.*}"
  local prefix="${base}@${host}"
  local sessdir="$HOME/.claude/sessions"
  local resvdir="$sessdir/.claudemore-resv"
  local lockfile="$sessdir/.claudemore.lock"
  mkdir -p "$resvdir" 2>/dev/null
  : >>"$lockfile" 2>/dev/null

  # Allocate a unique "${prefix}-N" session name. Concurrent launches (a fleet of
  # panes started together) otherwise race: each scans the session files for the
  # current max suffix before any has written its own, so several land on the same
  # N. Serialise the scan+pick under an flock, and record the chosen name as a
  # reservation marker that sibling invocations also count -- that covers the
  # window between picking the name and claude writing its <pid>.json. Markers are
  # reaped after an hour (by then the json covers the name) and on session exit.
  local name="" lockfd max
  zmodload -i zsh/system 2>/dev/null
  if zsystem flock -t 10 -f lockfd "$lockfile" 2>/dev/null; then
    find "$resvdir" -type f -mmin +60 -delete 2>/dev/null
    max=$(python3 -c '
import sys, os, json, glob
prefix, sessdir, resvdir = sys.argv[1:4]
mx = 0
names = []
for f in glob.glob(os.path.join(sessdir, "*.json")):
    try: names.append(json.load(open(f)).get("name", ""))
    except Exception: pass
try: names += os.listdir(resvdir)
except Exception: pass
for nm in names:
    if nm and nm.startswith(prefix + "-"):
        s = nm[len(prefix) + 1:]
        if s.isdigit(): mx = max(mx, int(s))
print(mx)
' "$prefix" "$sessdir" "$resvdir" 2>/dev/null)
    max="${max//[^0-9]/}"
    [[ -n "$max" ]] || max=0
    name="${prefix}-$((max + 1))"
    command touch "$resvdir/$name" 2>/dev/null
    zsystem flock -u $lockfd 2>/dev/null
  else
    # Lock unavailable after the timeout; fall back to a collision-proof,
    # non-numeric suffix so we neither clash nor poison the counter.
    name="${prefix}-x$$-$RANDOM"
  fi

  # Fleet agents (gitten / relaunch-fleet tmux sessions, all named wg-*) run with
  # permissions bypassed; keep claude.ai connector content (mail, Drive) out of them.
  local -a fleet_env=()
  if [[ -n $TMUX && "$(tmux display-message -p '#S' 2>/dev/null)" == wg-* ]]; then
    fleet_env=(ENABLE_CLAUDEAI_MCP_SERVERS=false)
  fi

  echo "Session: ${name}"
  env "${fleet_env[@]}" claude --model "$model" --effort xhigh --dangerously-skip-permissions --permission-mode bypassPermissions --name "${name}" --remote-control "${name}" "$@"
  local rc=$?
  command rm -f "$resvdir/$name" 2>/dev/null
  return $rc
}

claudemore() {
  _claude_named_session 'opus[1m]' "$@"
}

claudemax() {
  _claude_named_session 'fable[1m]' "$@"
}

# A --remote session runs in the app-server's directory (~) unless -C names one.
gptmore() {
  codex --remote unix:// -C "$PWD" --model gpt-6.1-sol -c model_reasoning_effort=xhigh --yolo "$@"
}

gptmax() {
  codex --remote unix:// -C "$PWD" --model gpt-6-astra -c model_reasoning_effort=max --yolo "$@"
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

# Open the gitten fleet `fleet` (gox, estavelle, karsto): one tab per workspace,
# one split per agent, claudemore in each, as tmux -CC panes inside iTerm.
# gitten flags pass through: `claudefleet --agent astra`, `--launcher iterm`,
# `--launcher muxy`, `--fresh`. One workspace: `gitten ws open gox`.
claudefleet() {
  gitten fleet open fleet "$@"
}
[ -f ~/.corio-bench-secrets ] && source ~/.corio-bench-secrets

(( $+functions[dotfiles_greeting] )) && dotfiles_greeting
