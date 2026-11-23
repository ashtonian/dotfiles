# Claude Code launchers (feature agents.claude). `dotfiles apply` copies this
# fragment into ~/.config/dotfiles/generated/zshrc.zsh, which zshrc.zsh sources
# before ~/.zshrc.local, so a local definition replaces one here.

# Enable Claude Code agent teams
export CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1

# _claude_drive_env VOLUMES: set reply to the environment that keeps a session
# working under VOLUMES/<drive> on that drive: its scratch (CLAUDE_CODE_TMPDIR)
# and its commands' caches (DOTFILES_CACHE_HOME, which env.sh turns into
# XDG_CACHE_HOME in the session's shells), where bin/disk-hygiene prunes them.
# ${PWD:A} resolves links such as ~/workgroups to the drive they live on.
_claude_drive_env() {
  reply=()
  local here=${PWD:A} drive
  [[ $here == "$1"/?* ]] || return 0
  drive=${here#"$1"/}
  drive=$1/${drive%%/*}
  command mkdir -p "$drive/tmp" "$drive/cache/xdg" 2>/dev/null || return 0
  reply=(CLAUDE_CODE_TMPDIR="$drive/tmp" DOTFILES_CACHE_HOME="$drive/cache/xdg")
}

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

  # Every session started here runs with permissions bypassed, so claude.ai
  # connector content (mail, Drive, Docs) stays out unless this launch opts in.
  local -a session_env=()
  [[ ${CLAUDE_CONNECTORS:-0} == 1 ]] || session_env+=(ENABLE_CLAUDEAI_MCP_SERVERS=false)
  local -a reply
  _claude_drive_env /Volumes
  session_env+=("${reply[@]}")

  # The claudemix delegation policy, linked by agents.claude. A resumed session
  # keeps the system prompt it recorded until its next compaction.
  local policy=$HOME/.claude/claudemix/policy.md
  local -a policy_args=()
  if [[ -r $policy ]]; then
    policy_args=(--append-system-prompt-file "$policy")
  else
    print -u2 "claude: $policy is missing; starting without the delegation policy"
  fi

  echo "Session: ${name}"
  env "${session_env[@]}" claude --model "$model" --effort xhigh \
    --dangerously-skip-permissions --permission-mode bypassPermissions \
    --name "$name" --remote-control "$name" "${policy_args[@]}" "$@"
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
