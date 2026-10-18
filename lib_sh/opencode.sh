#!/bin/bash
# OpenCode helpers for the local server run by the com.ashtonian.opencode LaunchAgent.
# Sourced by 60-functions.zsh. Setup and operations: ~/.dotfiles/stow/opencode/README.md

_opencode_password_file="$HOME/.local/share/opencode/homelab/server-password"

# oc [opencode attach options] - open the TUI on the running server, in $PWD.
# The terminal and the web UI share the same sessions, live.
oc() {
  if [[ ! -s "$_opencode_password_file" ]]; then
    echo "oc: $_opencode_password_file is missing; see ~/.dotfiles/stow/opencode/README.md" >&2
    return 1
  fi
  OPENCODE_SERVER_PASSWORD="$(<"$_opencode_password_file")" \
    opencode attach "http://127.0.0.1:${OPENCODE_PORT:-4096}" --dir "$PWD" "$@"
}

# ocweb - open the web UI and put its password on the clipboard (user: opencode).
ocweb() {
  if [[ ! -s "$_opencode_password_file" ]]; then
    echo "ocweb: $_opencode_password_file is missing; see ~/.dotfiles/stow/opencode/README.md" >&2
    return 1
  fi
  pbcopy < "$_opencode_password_file"
  open "http://127.0.0.1:${OPENCODE_PORT:-4096}"
  echo "Password copied to the clipboard; user is 'opencode'."
}
