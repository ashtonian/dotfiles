#!/usr/bin/env bash
# repo-guard: a Claude Code PreToolUse hook for the Bash tool. It denies a
# command that would change a protected repository (a commit, a tag, a push or
# a GitHub write) when the command names the repository or runs in, or points
# git at, a clone of it. Reading, cloning and local builds pass.
#
# Protected repositories are listed one owner/name per line; blank lines and
# # comments are skipped:
#   REPO_GUARD_LIST set   that file alone (empty: nothing is protected)
#   otherwise             every ~/.config/repo-guard/protected.d/*.txt, which
#                         the context overlays link, one file each
# With no list, nothing is protected.
#
# Output: a deny decision as JSON on stdout, exit 0. Exit 2 blocks the call and
# shows stderr to Claude: a list is unreadable or has a line that is not
# owner/name, the hook input is not JSON, or jq is missing.
# Runs under macOS's bash 3.2 as well as current bash.
set -uo pipefail
shopt -s nocasematch # GitHub owner and repository names ignore case
unset GIT_DIR GIT_WORK_TREE

die() {
  printf 'repo-guard: %s\n' "$*" >&2
  exit 2
}

lists=()
if [[ -n ${REPO_GUARD_LIST+set} ]]; then
  [[ -z $REPO_GUARD_LIST ]] || lists=("$REPO_GUARD_LIST")
else
  for list in "$HOME/.config/repo-guard/protected.d"/*.txt; do
    [[ -e $list ]] && lists+=("$list")
  done
fi
((${#lists[@]})) || exit 0

command -v jq >/dev/null || die "jq is not installed; it reads the hook input (Homebrew: brew install jq)"
input=$(cat)
cwd=$(jq -r '.cwd // empty' <<<"$input") || die "the hook input is not JSON"
command=$(jq -r '.tool_input.command // empty' <<<"$input") || die "the hook input is not JSON"
[[ -n $command ]] || exit 0
[[ -n $cwd ]] || cwd=$PWD

# Not a command word when preceded by a name character: `legit`, `.gh`.
start='(^|[^[:alnum:]_.-])'

# git commit, push, and creating a tag, after any global options.
git_options='([[:space:]]+(-[Cc][[:space:]]+[^[:space:]]+|--(git-dir|work-tree|namespace)[[:space:]]+[^[:space:]]+|-[^[:space:]]+))*'
git_tag_create='tag[[:space:]]+([^-[:space:]]|-[afsmuF]|--(annotate|sign|local-user|force|message|file))'
git_write_re="${start}git${git_options}[[:space:]]+(commit|push|${git_tag_create})"

# gh commands that act on a repository: every verb but these may write.
gh_read_verbs=' view list ls status diff checks checkout clone search browse download watch '
gh_nouns=' pr issue release repo label workflow run secret variable cache ruleset project discussion '
gh_re="${start}gh[[:space:]]+([^[:space:]]+)([[:space:]]+([^[:space:]]+))?"
newline=$'\n'

# gh_api_writes SEGMENT: the arguments after `gh api`, up to the next ; & | or
# newline, describe a request that may change something.
gh_api_writes() {
  local args=" $1 "
  if [[ $args =~ [[:space:]]graphql[[:space:]] ]]; then
    [[ $args == *mutation* ]]
    return
  fi
  if [[ $args =~ [[:space:]](-X|--method)(=|[[:space:]]*)([A-Za-z]+) ]]; then
    [[ ${BASH_REMATCH[3]} != GET && ${BASH_REMATCH[3]} != HEAD ]]
    return
  fi
  # Fields or a body turn gh's default GET into a POST.
  [[ $args =~ [[:space:]](-f|-F|--field|--raw-field|--input)([=[:space:]]) ]]
}

writes() {
  [[ $command =~ $git_write_re ]] && return 0
  local rest=$command noun verb segment
  while [[ $rest =~ $gh_re ]]; do
    noun=${BASH_REMATCH[2]}
    verb=${BASH_REMATCH[4]}
    rest=${rest#*"${BASH_REMATCH[0]}"}
    if [[ $noun == api ]]; then
      segment="$verb ${rest%%[;&|"${newline}"]*}"
      gh_api_writes "$segment" && return 0
    elif [[ $gh_nouns == *" $noun "* && $gh_read_verbs != *" $verb "* ]]; then
      return 0
    fi
  done
  return 1
}
writes || exit 0

# Every list is read in full first, so a bad line fails the same way whichever
# list holds it.
repos=()
for list in "${lists[@]}"; do
  [[ -r $list ]] || die "cannot read the protected list $list"
  n=0
  while IFS= read -r line || [[ -n $line ]]; do
    n=$((n + 1))
    repo=${line%%#*}
    repo=${repo//[[:space:]]/}
    [[ -n $repo ]] || continue
    [[ $repo =~ ^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$ ]] || die "$list:$n: '$line' is not owner/name"
    repos+=("$repo")
  done <"$list"
done
((${#repos[@]})) || exit 0

# resolve DIR BASE: DIR as an absolute path, read relative to BASE.
resolve() {
  local dir=$1
  dir=${dir//\"/}
  dir=${dir//\'/}
  dir=${dir/#\~/$HOME}
  dir=${dir/#\$\{HOME\}/$HOME}
  dir=${dir/#\$HOME/$HOME}
  [[ $dir == /* ]] || dir="$2/$dir"
  printf '%s\n' "$dir"
}

# Where the command may act: the session's directory, each `cd` or `pushd`
# target in order (a relative one from the directory before it), and each
# `-C`, `--git-dir` or `--work-tree` it hands git.
dirs=("$cwd")
dir_re="${start}(cd|pushd)[[:space:]]+([^[:space:];&|)]+)|[[:space:]]-C[[:space:]]+([^[:space:];&|)]+)|--(git-dir|work-tree)[=[:space:]]+([^[:space:];&|)]+)"
base=$cwd
rest=$command
while [[ $rest =~ $dir_re ]]; do
  rest=${rest#*"${BASH_REMATCH[0]}"}
  if [[ -n ${BASH_REMATCH[3]} ]]; then
    base=$(resolve "${BASH_REMATCH[3]}" "$base")
    dirs+=("$base")
  elif [[ -n ${BASH_REMATCH[4]} ]]; then
    dirs+=("$(resolve "${BASH_REMATCH[4]}" "$base")")
  else
    dirs+=("$(resolve "${BASH_REMATCH[6]}" "$base")")
  fi
done

remotes=""
for dir in "${dirs[@]}"; do
  [[ -d $dir ]] || continue
  remotes+="$(git -C "$dir" remote -v 2>/dev/null)"$'\n'
done

deny() {
  jq -n --arg repo "$1" '{hookSpecificOutput: {
    hookEventName: "PreToolUse",
    permissionDecision: "deny",
    permissionDecisionReason: ("Changes to " + $repo + " need the user'"'"'s explicit permission for that change. Reading, scratch clones and local builds are fine; write findings where you were asked to work.")
  }}'
  exit 0
}

for repo in "${repos[@]}"; do
  # The whole name, as in owner/name, github.com:owner/name.git or repos/owner/name/pulls.
  repo_re="${start}${repo//./[.]}([.]git)?(\$|[^[:alnum:]_.-])"
  [[ $command =~ $repo_re ]] && deny "$repo"
  [[ $remotes =~ $repo_re ]] && deny "$repo"
done
exit 0
