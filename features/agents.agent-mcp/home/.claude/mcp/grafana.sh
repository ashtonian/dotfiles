#!/bin/bash
# Launches mcp-grafana with its URL and service-account token read from the login keychain,
# so neither lives in a config file. Store them once:
#   security add-generic-password -U -s claude-mcp-grafana -a url   -w 'https://grafana.example'
#   security add-generic-password -U -s claude-mcp-grafana -a token -w '<Viewer service-account token>'
set -euo pipefail
kc() { /usr/bin/security find-generic-password -s claude-mcp-grafana -a "$1" -w 2>/dev/null; }
GRAFANA_URL=$(kc url) || { echo "grafana MCP: keychain item claude-mcp-grafana/url missing (see $0)" >&2; exit 1; }
GRAFANA_SERVICE_ACCOUNT_TOKEN=$(kc token) || { echo "grafana MCP: keychain item claude-mcp-grafana/token missing (see $0)" >&2; exit 1; }
export GRAFANA_URL GRAFANA_SERVICE_ACCOUNT_TOKEN
exec "$(dirname "$0")/bin/mcp-grafana" -t stdio -disable-write -disable-admin -usage-stats=disabled "$@"
