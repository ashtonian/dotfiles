#!/bin/bash
# headersHelper for the GitHub remote MCP server: mints the Authorization header from the
# gh CLI keyring at connect time, so no token is written into any config file.
# Claude Code started from the desktop app has no Homebrew on PATH, so its prefixes come first.
set -euo pipefail
gh=$(PATH="${HOMEBREW_PREFIX:-/opt/homebrew}/bin:/home/linuxbrew/.linuxbrew/bin:$PATH" command -v gh) ||
    { echo "gh is not installed; install it with Homebrew" >&2; exit 1; }
token=$("$gh" auth token 2>/dev/null) || { echo "gh auth token failed; run: gh auth login" >&2; exit 1; }
printf '{"Authorization":"Bearer %s"}\n' "$token"
