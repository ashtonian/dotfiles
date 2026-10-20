# Agent telemetry

## Overview

Claude Code, Codex and OpenCode export OpenTelemetry metrics and log events to a
local collector on this Mac. The collector deletes identities and tool content,
then forwards the rest to an OTLP gateway in the cluster, which stores metrics
in Mimir and events in Loki for dashboards and queries.

```
Claude Code ─┐
Codex       ─┼─ OTLP → otel-agent (127.0.0.1:4318/4317) ─ HTTPS + bearer token → cluster gateway → Mimir / Loki
OpenCode    ─┘
```

What arrives per harness:

| Harness | Configured in | Metrics | Events |
| --- | --- | --- | --- |
| Claude Code | `~/.claude/settings.json` `env` | `claude_code_token_usage`, `_cost_usage`, `_session_count`, `_active_time_total`, with `model`, `type`, `query_source`, `session_id`, `vcs_repository_name` | `api_request`, `tool_result` (tool name, size, duration, success), `mcp_server_connection`, hooks, `user_prompt` (length only) |
| Codex | `~/.codex/config.toml` `[otel]` | `codex_turn_token_usage`, `codex_turn_tool_call`, TTFT, turn duration, MCP discovery timings, with `model`, `originator`, `token_type` | `codex.api_request`, `codex.tool_result`, `codex.sse_event`, `codex.user_prompt` (length only) |
| OpenCode | `stow/opencode/.config/opencode/opencode.jsonc` `plugin` | `opencode_token_usage`, `_cost_usage`, `_session_*`, `_model_usage` | `api_request`, `tool_result`, `session.*`, `user_prompt` (length only) |

Telemetry starts with new processes. Claude Code sessions pick up the settings
when started; the Codex app-server and the OpenCode server pick them up when
restarted.

## Config

| Setting | Where | Value | Description |
| --- | --- | --- | --- |
| Gateway URL | `~/.local/share/otel-agent/endpoint` (0600) | `https://otel.<internal domain>` | Written by `otel-agent configure`; kept out of this public repository. |
| Ingest token | `~/.local/share/otel-agent/token` (0600) | 48 characters | The gateway's `otel-gateway-token-workstation` Secret. |
| `OTEL_AGENT_HOME` | environment | `~/.local/share/otel-agent` | State directory (endpoint, token). |
| `OTEL_AGENT_LIBEXEC` | environment | `~/.local/libexec/otelcol` | Where the pinned collector is installed, one directory per version. |
| `OTEL_AGENT_CONFIG` | environment | `~/.config/otel-agent/config.yaml` | Collector config (stow package `otel-agent`). |
| `OTEL_AGENT_HOST` | environment | `scutil --get LocalHostName` | Written to `host.name` on everything forwarded. |
| Collector | `bin/otel-agent` | `otelcol` core 0.163.1, darwin_arm64, SHA-256 pinned | The core distribution has the OTLP receiver and exporter and the attributes, resource, batch and memory-limiter processors. |
| Receivers | `config.yaml` | `127.0.0.1:4318` (HTTP), `127.0.0.1:4317` (gRPC) | Loopback only. |
| Health / self-metrics | `config.yaml` | `127.0.0.1:13134` / `127.0.0.1:8889` | Read by `otel-agent status`. |
| Memory limiter | `config.yaml` | 200 MiB, 50 MiB spike | Refuses data before the process grows past it; clients retry. |
| Export queue | `config.yaml` | 2,000 batches in memory, retry up to 1 h | Covers gateway outages and LAN stalls while the collector runs; lost if it restarts mid-outage. |
| Redaction | `config.yaml` `resource/redact`, `attributes/redact` | identity and content key patterns | See Security. Must match the gateway's patterns. |
| Claude Code | `~/.claude/settings.json` `env` | `CLAUDE_CODE_ENABLE_TELEMETRY=1`, `OTEL_METRICS_EXPORTER=otlp`, `OTEL_LOGS_EXPORTER=otlp`, `OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf`, `OTEL_EXPORTER_OTLP_ENDPOINT=http://127.0.0.1:4318` | Export to the local collector. |
| | | `OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE=cumulative` | Mimir's OTLP endpoint takes cumulative sums. |
| | | `OTEL_METRICS_INCLUDE_ACCOUNT_UUID=false` | No account IDs on metrics (the collector deletes them anyway). |
| | | `OTEL_METRICS_INCLUDE_REPOSITORY=true` | `vcs_repository_name` on metrics and events, the per-project dimension. |
| | | `OTEL_LOG_TOOL_DETAILS=1` | Real MCP server and tool names on counters and events. It also adds Bash commands, file paths and tool input, which the collector deletes before forwarding. |
| Codex | `~/.codex/config.toml` `[otel]` | `exporter` and `metrics_exporter` = `otlp-http` to `127.0.0.1:4318/v1/{logs,metrics}`, `trace_exporter = "none"`, `log_user_prompt = false`, `[otel.tool_result] max_bytes = 0` | Setting `metrics_exporter` also replaces Codex's default export to Statsig. Tool output previews are cut to nothing at the source. |
| OpenCode | `opencode.jsonc` `plugin` | `@devtheops/opencode-plugin-otel@1.5.1` with `endpoint`, `protocol: http/protobuf`, `metricsTemporality: cumulative`, `disabledTraces: [session, llm, tool]` | The 1.x line is the plugin for OpenCode V1. OpenCode installs it on server start. |

## External Dependencies

- **Cluster gateway**: `k8s/monitoring/otel-gateway` in the public home-ops
  repository (OTLP/HTTP behind the LAN ingress, bearer tokens, Mimir and Loki
  exporters), plus the **Coding Agents** Grafana dashboard
  (`k8s/monitoring/dashboards/coding-agents.yaml`).
- **The collector release**: `otelcol_<version>_darwin_arm64.tar.gz` from
  [opentelemetry-collector-releases](https://github.com/open-telemetry/opentelemetry-collector-releases),
  verified against the pinned SHA-256.
- **The OpenCode plugin** from npm, MPL-2.0, resolved by OpenCode at server start.
- `curl`, `shasum`, `tar`, `launchctl`, `scutil` from the base system.

## API / Interfaces

```sh
otel-agent install                 # download + verify the pinned collector; install the LaunchAgent once configured
otel-agent configure URL < token   # store gateway URL and token (0600), (re)start the LaunchAgent
otel-agent serve                   # LaunchAgent entry point
otel-agent status                  # service, health, accepted/sent/failed counters
otel-agent ping                    # send one test event ({service_name="otel-agent"} in Loki)
```

Any OTLP client on this Mac can send to `http://127.0.0.1:4318` (HTTP) or
`127.0.0.1:4317` (gRPC) without credentials.

## Build / Run / Test

```sh
# First install
~/.dotfiles/bin/otel-agent install
kubectl --context admin@talos-homelab -n monitoring get secret otel-gateway-token-workstation \
  -o jsonpath='{.data.token}' | base64 -d | ~/.dotfiles/bin/otel-agent configure https://otel.<internal domain>
~/.dotfiles/bin/otel-agent ping && sleep 10 && ~/.dotfiles/bin/otel-agent status

# Tests
python3 -m unittest tests.test_dotfiles.OtelAgent
```

To upgrade, change `OTELCOL_VERSION` and `OTELCOL_SHA256` (from the release's
`.sha256` asset) in `bin/otel-agent`, run `otel-agent install`, then reinstall
the agent (`dotfiles-install-launchagents.sh --otel-agent-only`). The new binary
gets its own Local Network prompt.

## Operations

- **Health:** `otel-agent status`. `exporter_sent_*` should grow with agent
  activity; `exporter_send_failed_*` and `queue_size` should stay at 0.
- **Logs:** `~/Library/Logs/otel-agent/collector.{stdout,stderr}.log`.
- **Dashboard:** Grafana → Applications → Coding Agents.

**Failure modes:**

- *`health: unreachable`.* The LaunchAgent is not running. Check the stderr log;
  `serve` exits 78 when the collector is missing or no gateway is configured.
- *`exporter_send_failed` grows, log shows `401`.* The token no longer matches
  the gateway's Secret. Re-run the `configure` command above.
- *Log shows `no route to host` or `EHOSTUNREACH`.* macOS Local Network Privacy
  blocks the binary. Allow `otelcol` in System Settings → Privacy & Security →
  Local Network, then `launchctl kickstart -k gui/$(id -u)/com.ashtonian.otel-agent`.
- *`queue_size` stays high.* The gateway or the LAN is slow. Check the
  gateway's alerts (`OtelGatewayDown`, `OtelGatewayExportFailing`).
- *A harness shows no data.* It must be restarted after its config changed. A
  harness exporting to a port where nothing listens drops its data silently.

## Security

- The receivers listen on loopback only. The gateway URL and token live outside
  this repository in a 0700 directory with 0600 files. No harness config holds a
  credential.
- Deleted before anything leaves the Mac:
  - identities: `user.email`, `user.id`, `user.account_id`, `user.account_uuid`,
    `user.groups`, `organization.id`;
  - content: `prompt`, `prompt_text`, `response`, `tool_input`,
    `tool_parameters`, `arguments`, `output`, `error`, `error.message`,
    `auth.error`, `body`, `body_ref`, `diff`, `hook_definitions`,
    `redacted_settings`.

  Claude Code always attaches the email and account and organization IDs, and
  Codex puts the email, account ID, tool arguments and a tool-output preview on
  its events.
- Prompt and response text is never enabled: Claude's `OTEL_LOG_USER_PROMPTS`
  and `OTEL_LOG_ASSISTANT_RESPONSES`, Codex's `log_user_prompt` and
  `log_agent_responses`, and the OpenCode plugin's `capturePromptInLogs` all
  stay off.
- The gateway deletes the same keys again, so a client that skips this
  collector still cannot store them.
- The collector binary is the upstream release, pinned by SHA-256.

## Code Map

| File | Purpose |
| --- | --- |
| [bin/otel-agent](../bin/otel-agent) | install / configure / serve / status / ping |
| [stow/otel-agent/.config/otel-agent/config.yaml](../stow/otel-agent/.config/otel-agent/config.yaml) | Collector pipelines and redaction |
| [launchagents/com.ashtonian.otel-agent.plist](../launchagents/com.ashtonian.otel-agent.plist) | Always-on LaunchAgent |
| [bin/dotfiles-install-launchagents.sh](../bin/dotfiles-install-launchagents.sh) | `--otel-agent-only` installs it |
| [stow/opencode/.config/opencode/opencode.jsonc](../stow/opencode/.config/opencode/opencode.jsonc) | OpenCode's OTel plugin |
| [tests/test_dotfiles.py](../tests/test_dotfiles.py) | `OtelAgent` tests |
