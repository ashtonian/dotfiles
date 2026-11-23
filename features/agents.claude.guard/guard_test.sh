#!/usr/bin/env bash
# Runs repo-guard's guard.sh against throwaway clones: two whose origins are on
# protected lists, one whose name merely starts like a protected one, and one
# unrelated. HOME is a scratch directory, so the machine's own lists never
# take part. GUARD_BASH picks the bash that runs the hook (default: bash on
# PATH); CI runs it with /bin/bash too. Exits non-zero on any unexpected result.
set -uo pipefail

guard="$(cd "$(dirname "$0")" && pwd)/home/.claude/skills/repo-guard/scripts/guard.sh"
# Absolute paths: some cases run the hook with a PATH that lacks jq.
guard_bash=$(command -v "${GUARD_BASH:-bash}") || { echo "no ${GUARD_BASH:-bash}" >&2; exit 1; }
jq=$(command -v jq) || { echo "jq is required" >&2; exit 1; }
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
unset REPO_GUARD_LIST

protected=example-owner/protected-repo
second=example-owner/second-repo
clone() { # clone DIR OWNER/NAME
  git init -q "$work/$1" && git -C "$work/$1" remote add origin "git@github.com:$2.git"
}
clone protected "$protected"
clone second "$second"
clone lookalike example-owner/protected-repo-docs
clone other example-owner/other

# Two overlays' lists, as `dotfiles apply` links them; a non-.txt file is not one.
home=$work/home
mkdir -p "$home/.config/repo-guard/protected.d" "$work/empty-home"
printf '# context a\n%s\n\n' "$protected" >"$home/.config/repo-guard/protected.d/a.txt"
printf '  Example-Owner/Second-Repo   # context b, any case\n' >"$home/.config/repo-guard/protected.d/b.txt"
printf '%s\n' example-owner/other >"$home/.config/repo-guard/protected.d/notes.md"
printf '%s\n' "$second" >"$work/only-second.txt"
printf '%s\n' 'not a repository' >"$work/malformed.txt"

# A PATH with git and cat but no jq.
mkdir "$work/nojq"
ln -s "$(command -v git)" "$work/nojq/git"
ln -s "$(command -v cat)" "$work/nojq/cat"

pass=0
fail=0
# check EXPECTED CWD COMMAND: EXPECTED is deny, allow or error (exit 2). The
# caller's HOME, REPO_GUARD_LIST and PATH reach the hook.
check() {
  local input out status got
  # shellcheck disable=SC2016 # $c and $d are jq variables
  input=$("$jq" -n --arg c "$3" --arg d "$2" '{hook_event_name: "PreToolUse", tool_name: "Bash", tool_input: {command: $c}, cwd: $d}')
  out=$("$guard_bash" "$guard" <<<"$input" 2>/dev/null)
  status=$?
  case "$status:$out" in
    0:*'"permissionDecision": "deny"'*) got=deny ;;
    0:) got=allow ;;
    2:) got=error ;;
    *) got="exit $status: $out" ;;
  esac
  if [[ $got == "$1" ]]; then
    pass=$((pass + 1))
  else
    fail=$((fail + 1))
    printf 'FAIL: expected %s, got %s: [%s] %s\n' "$1" "$got" "$2" "$3"
  fi
}

P=$work/protected
O=$work/other
export HOME=$home

for c in 'git push origin main' 'git commit -m x' 'git tag v1.2.3' 'git tag -a v1 -m x' \
  'git -c user.name=x commit -m y' 'git --no-pager push' '/usr/bin/git push' 'git add . && git commit -m z' \
  'gh pr create --fill' 'gh release create v1' 'gh pr merge 3 --squash' 'gh issue comment 4 -b x'; do
  check deny "$P" "$c"
done
for c in 'git tag' 'git tag -l' 'git tag -d v1' 'git log' 'git pull' 'git status' 'docker build -t local/img .' \
  'gh pr view 3' 'gh pr list' 'gh pr checkout 3' 'gh run watch 5'; do
  check allow "$P" "$c"
done
# The hook reads text, not shell syntax, so it errs toward denying.
check deny "$P" 'echo git push'
for c in "cd $P && git commit -m y" 'cd ../protected && git tag v2' 'git -C ../protected push' \
  'git --git-dir=../protected/.git commit -m x' "gh pr create -R $protected" "gh api repos/$protected/issues -f title=x" \
  "gh api -X DELETE repos/$protected/git/refs/heads/x" "gh api --method=PATCH repos/$protected -F private=true" \
  "gh api graphql -f query='mutation { x }' -f repo=$protected" "git push git@github.com:$protected.git main" \
  "gh pr merge 4 -R $second" "gh release upload v1 x.tgz -R EXAMPLE-OWNER/SECOND-REPO" 'cd ../second; git push'; do
  check deny "$O" "$c"
done
for c in 'git push' 'git commit -m x' "gh pr view 3 -R $protected" "gh api repos/$protected/pulls" \
  "gh api repos/$protected/pulls | jq -f filter.jq" \
  "gh api -X GET repos/$protected/issues -f state=open" "gh api graphql -f query='query { x }' -f repo=$protected" \
  "git clone git@github.com:$protected.git /tmp/x" "gh pr create -R example-owner/protected-repo-docs" \
  "gh pr create -R example-owner/other" 'cd ../lookalike && git push'; do
  check allow "$O" "$c"
done

# No protected.d directory: nothing is protected.
HOME=$work/empty-home check allow "$P" 'git push origin main'

# REPO_GUARD_LIST replaces the directory's lists; empty protects nothing.
REPO_GUARD_LIST=$work/only-second.txt check allow "$P" 'git push origin main'
REPO_GUARD_LIST=$work/only-second.txt check deny "$O" "gh pr create -R $second"
REPO_GUARD_LIST='' check allow "$P" 'git push origin main'

# A list that cannot be read or has a bad line blocks write-shaped commands only.
REPO_GUARD_LIST=$work/missing.txt check error "$P" 'git push origin main'
REPO_GUARD_LIST=$work/missing.txt check allow "$P" 'git log'
REPO_GUARD_LIST=$work/malformed.txt check error "$P" 'git commit -m x'
REPO_GUARD_LIST=$work/malformed.txt check allow "$P" 'git status'

# Without jq the hook cannot read its input, so it blocks while a list exists.
PATH=$work/nojq check error "$P" 'git status'
PATH=$work/nojq HOME=$work/empty-home check allow "$P" 'git push origin main'

echo "pass=$pass fail=$fail"
[[ $fail -eq 0 ]]
