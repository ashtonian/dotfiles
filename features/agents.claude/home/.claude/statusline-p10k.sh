#!/usr/bin/env bash
# Claude Code status line mirroring the p10k prompt: os_icon + dir + vcs (left
# elements), with the model where p10k's transient right side would be.
input=$(cat)
cwd=$(printf '%s' "$input" | jq -r '.workspace.current_dir // .cwd // empty')
model=$(printf '%s' "$input" | jq -r '.model.display_name // empty')
[ -n "$cwd" ] || cwd=$PWD
dir=${cwd/#$HOME/\~}
# p10k shortens long paths; keep the last two components beyond that.
IFS=/ read -ra parts <<< "$dir"
n=${#parts[@]}
if [ "$n" -gt 3 ]; then dir="…/${parts[n-2]}/${parts[n-1]}"; fi
vcs=""
ref=$(git -C "$cwd" branch --show-current 2>/dev/null)
if [ -n "$ref" ]; then
  if git -C "$cwd" status --porcelain 2>/dev/null | head -1 | grep -q .; then
    vcs=$(printf ' \033[38;5;178m %s ±\033[0m' "$ref")   # dirty: p10k yellow
  else
    vcs=$(printf ' \033[38;5;76m %s\033[0m' "$ref")      # clean: p10k green
  fi
fi
printf ' \033[38;5;39m%s\033[0m%s \033[2m%s\033[0m' "$dir" "$vcs" "$model"
