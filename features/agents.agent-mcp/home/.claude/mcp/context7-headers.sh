#!/bin/bash
# headersHelper for the Context7 remote MCP server: sends the API key from the
# keychain (service claude-mcp-context7, account api-key) when one is stored, so
# no key is written into any config file. Without it Context7 serves anonymous
# requests at a lower rate limit. Store a key from context7.com/dashboard with:
#   security add-generic-password -U -s claude-mcp-context7 -a api-key -w '<key>'
set -euo pipefail
if key=$(/usr/bin/security find-generic-password -s claude-mcp-context7 -a api-key -w 2>/dev/null); then
    printf '{"Authorization":"Bearer %s"}\n' "$key"
else
    printf '{}\n'
fi
