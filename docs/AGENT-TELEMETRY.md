# Agent telemetry

## Overview

Claude Code, Codex and OpenCode export OpenTelemetry metrics and log events to a
local collector on each Mac. The collector deletes identities and tool content,
stamps the Mac's source name (`studio`, `mbp` or `mini`) as `host.name`, and
forwards the rest to an OTLP gateway in the cluster with that Mac's own token.
The gateway stores metrics in Mimir and events in Loki for dashboards and
queries.

```text
Claude Code ─┐
Codex       ─┼─ OTLP → otel-agent (127.0.0.1:4318/4317) → disk queue ─ HTTPS + per-host token → cluster gateway → Mimir / Loki
OpenCode    ─┘
```

The export queue lives on disk. A Mac that is off the LAN (the MacBook Pro
travels) or whose gateway is down keeps accepting telemetry, survives restarts
with it queued, and delivers it once the gateway answers again. Loki and Mimir
accept a backlog up to 7 days old. The queues hold about 8 to 9 days of
studio's volume, so the backends' 7-day window, not the disk, is the bound.

The same collector forwards each Mac's hardware metrics, through a queue of
their own, when the `macos.host-metrics` feature adds its pipeline
([HOST-METRICS.md](HOST-METRICS.md)).

What arrives per harness:

| Harness | Configured in | Metrics | Events |
| --- | --- | --- | --- |
| Claude Code | `~/.claude/settings.json` `env` | `claude_code_token_usage`, `_cost_usage`, `_session_count`, `_active_time_total`, with `model`, `type`, `query_source`, `session_id`, `vcs_repository_name` | `api_request`, `tool_result` (tool name, size, duration, success), `mcp_server_connection`, hooks, `user_prompt` (length only) |
| Codex | `~/.codex/config.toml` `[otel]` | `codex_turn_token_usage`, `codex_turn_tool_call`, TTFT, turn duration, MCP discovery timings, with `model`, `originator`, `token_type` | `codex.api_request`, `codex.tool_result`, `codex.sse_event`, `codex.user_prompt` (length only) |
| OpenCode | `features/agents.opencode/home/.config/opencode/opencode.jsonc` `plugin` | `opencode_token_usage`, `_cost_usage`, `_session_*`, `_model_usage` | `api_request`, `tool_result`, `session.*`, `user_prompt` (length only) |

Telemetry starts with new processes. Claude Code sessions pick up the settings
when started; the Codex app-server and the OpenCode server pick them up when
restarted.

### How a pull reaches the collector

The config is a link into the checkout (feature `agents.otel-agent`), so a pull
that moves the pinned collector release changes the config the next start
reads, possibly to one only the new release understands. Two steps keep the
binary and the config together:

1. Every sync runs `otel-agent converge` right after `dotfiles apply`. It
   installs the pinned release if it is missing, removes other releases, and
   restarts the collector (`launchctl kickstart -k`) when the release, the
   config, the set or content of its `conf.d` fragments, or `bin/otel-agent`
   differ from what the running collector started from (`serve` records a
   fingerprint of them in
   `~/.local/state/otel-agent/serving`). A changed LaunchAgent template needs
   no fingerprint: `dotfiles apply` reloads the job itself.
   A Mac that never enrolled is skipped; one enrolled before host names fails
   with `no host name configured` until it is enrolled again (see
   [Build / Run / Test](#build--run--test)).
2. `serve`, the LaunchAgent's entry point, installs a missing pinned release
   before it starts the collector, so a restart that comes before converge
   (a reboot, a crash) starts the new release too.

Each release has its own path (`~/.local/libexec/otelcol/<version>_<platform>/`),
so macOS asks for the Local Network grant once per release on each Mac.

## Config

| Setting | Where | Value | Description |
| --- | --- | --- | --- |
| Gateway URL | `~/.local/share/otel-agent/endpoint` (0600) | `https://otel.<internal domain>` | Written by `otel-agent enroll` or `configure`; kept out of this public repository. |
| Ingest token | `~/.local/share/otel-agent/token` (0600) | 48 characters | This Mac's own token, the gateway's `otel-gateway-token-<host>` Secret. |
| Host name | `~/.local/share/otel-agent/host` (0600) | `studio`, `mbp` or `mini` | The source name enrolled with the token, written to `host.name` on everything forwarded. Lowercase letters, digits and inner hyphens, at most 32. The LaunchAgent keeps the collector alive only while this file exists. |
| `OTEL_AGENT_HOME` | environment | `~/.local/share/otel-agent` | Enrollment directory (endpoint, token, host), mode 0700. |
| `OTEL_AGENT_STATE` | environment | `$XDG_STATE_HOME/otel-agent`, `~/.local/state/otel-agent` | Runtime state: the disk queue (`queue/`, mode 0700) and the `serving` fingerprint. |
| `OTEL_AGENT_LIBEXEC` | environment | `~/.local/libexec/otelcol` | Where the pinned collector is installed, one directory per version and platform. |
| `OTEL_AGENT_CONFIG` | environment | `~/.config/otel-agent/config.yaml` | Collector config (feature `agents.otel-agent`). |
| Config fragments | `conf.d/*.yaml` beside `OTEL_AGENT_CONFIG` | none | Passed to the collector after the config, in name order, as further `--config` files. The collector merges them: maps merge key by key, a list replaces the one before it. A feature adds a receiver and pipeline this way (`macos.host-metrics`); a fragment must not redefine a pipeline or list another fragment uses. |
| `OTEL_AGENT_HOST` | environment | unset | Overrides the enrolled host name for `serve`; validated like it. |
| `OTEL_AGENT_KUBE_CONTEXT` | environment | kubectl's current context | Context `otel-agent enroll` reads the cluster with; `--context` overrides it. |
| Collector | `bin/otel-agent` | `otelcol-contrib` 0.165.0, `darwin_arm64` or `darwin_amd64` by `uname -m`, SHA-256 pinned per platform | The contrib distribution, for the `file_storage` extension. Its version may differ from the gateway's; OTLP is compatible across them. |
| Receivers | `config.yaml` | `127.0.0.1:4318` (HTTP), `127.0.0.1:4317` (gRPC) | Loopback only. |
| Health / self-metrics | `config.yaml` | `127.0.0.1:13134` / `127.0.0.1:8889` | Read by `otel-agent status`. |
| Memory limiter | `config.yaml` | 200 MiB, 50 MiB spike | Refuses data before the Go heap grows past it; clients retry. |
| Batch | `config.yaml` `batch` | 5 s or 8,192 items | One queue entry per batch. |
| Log events queue | `config.yaml` `otlp_http/logs` `sending_queue` | 768 MiB of serialized data (`sizer: bytes`) | About 9 days at studio's rate (~93,000 events a day at ~860 bytes each, ~80 MB a day). |
| Metric points queue | `config.yaml` `otlp_http/metrics` `sending_queue` | 2 GiB of serialized data (`sizer: bytes`) | About 8 days at studio's rate (~520,000 points a day: Claude Code sums at ~480 bytes, Codex histograms at ~840 bytes, ~270 MB a day). |
| Hardware metrics queue | `config.yaml` `otlp_http/host` `sending_queue` | 320 MiB of serialized data (`sizer: bytes`) | About 9.5 days at studio's rate (~420,000 points a day at ~84 bytes, ~35 MB a day). The exporter is in no pipeline, so never started and given no queue file, unless `macos.host-metrics` adds its fragment. |
| Full queue | `config.yaml` | new data dropped, oldest kept | Counted in `otelcol_exporter_enqueue_failed_*`. A batch larger than the room left is dropped whole. |
| Queue files | `config.yaml` `file_storage/queue` | one bbolt file per exporter in `$OTEL_AGENT_STATE/queue`, `max_size` 3 GiB each | A file holds about 1.3 times its queue's bytes: about 1 GiB (logs), 2.7 GiB (metrics) and 420 MiB (hardware) when every queue is full, 4.1 GiB in all. `max_size` is the backstop above the largest queue. |
| Queue durability | `config.yaml` `file_storage/queue` | `fsync: true`, `recreate: true` | Every write is synced, so a power loss keeps what was accepted. A file that fails to open as corrupt is renamed to `<file>.<time>.backup` and replaced; `serve` keeps only the newest backup. |
| Queue compaction | `config.yaml` `file_storage/queue` `compaction` | at start, and online once a file that grew past 100 MiB holds under 10 MiB | Returns a drained backlog's space to the disk. |
| Retry | `config.yaml` `retry_on_failure` | 5 s backing off to 5 min, no time limit | Data waits in the queue until delivered or until a permanent error (see Operations). |
| Redaction | `config.yaml` `resource/redact`, `attributes/redact` | identity and content key patterns | See Security. Must match the gateway's patterns byte for byte. |
| Claude Code | `~/.claude/settings.json` `env` | `CLAUDE_CODE_ENABLE_TELEMETRY=1`, `OTEL_METRICS_EXPORTER=otlp`, `OTEL_LOGS_EXPORTER=otlp`, `OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf`, `OTEL_EXPORTER_OTLP_ENDPOINT=http://127.0.0.1:4318` | Export to the local collector. |
| | | `OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE=cumulative` | Mimir's OTLP endpoint takes cumulative sums. |
| | | `OTEL_METRICS_INCLUDE_ACCOUNT_UUID=false` | No account IDs on metrics (the collector deletes them anyway). |
| | | `OTEL_METRICS_INCLUDE_REPOSITORY=true` | `vcs_repository_name` on metrics and events, the per-project dimension. |
| | | `OTEL_LOG_TOOL_DETAILS=1` | Real MCP server and tool names on counters and events. It also adds Bash commands, file paths and tool input, which the collector deletes before forwarding. |
| Codex | `~/.codex/config.toml` `[otel]` | `exporter` and `metrics_exporter` = `otlp-http` to `127.0.0.1:4318/v1/{logs,metrics}`, `trace_exporter = "none"`, `log_user_prompt = false`, `[otel.tool_result] max_bytes = 0` | Setting `metrics_exporter` also replaces Codex's default export to Statsig. Tool output previews are cut to nothing at the source. |
| OpenCode | `opencode.jsonc` `plugin` | `@devtheops/opencode-plugin-otel@1.5.1` with `endpoint`, `protocol: http/protobuf`, `metricsTemporality: cumulative`, `disabledTraces: [session, llm, tool]` | The 1.x line is the plugin for OpenCode V1. OpenCode installs it on server start. |

The queue sizes come from studio's volume over a week (the collector's own
`otelcol_exporter_sent_*` counters) and from the bytes `otelcol_exporter_queue_size`
reported for representative Claude Code and Codex records queued with
otelcol-contrib 0.165.0.

## External Dependencies

- **Cluster gateway**: `k8s/monitoring/otel-gateway` in the infrastructure
  repository, which is private (OTLP/HTTP behind the LAN ingress, one bearer token per source
  host, Mimir and Loki exporters), plus the **Coding Agents** Grafana dashboard
  (`k8s/monitoring/dashboards/coding-agents.yaml`).
- **Per-host tokens**: Secrets `otel-gateway-token-studio`, `-mbp` and `-mini`
  in namespace `monitoring`, key `token`. `enroll` also reads the internal
  domain from `argocd/render-domains`, key `domain.internal`.
- **Backends' age limits**: both accept a backlog up to 7 days old: Loki's
  `reject_old_samples_max_age` is 168 h (the cluster's Loki config), and
  Mimir's `out_of_order_time_window` is 168 h behind the tenant's newest sample
  (`k8s/monitoring/mimir`). Anything older is refused there, by Loki as too old
  and by Mimir as out of bounds. The queues hold about 8 to 9 days at studio's
  rate, so this window, not the disk, bounds a lossless outage.
- **The collector release**: `otelcol-contrib_<version>_darwin_{arm64,amd64}.tar.gz`
  from [opentelemetry-collector-releases](https://github.com/open-telemetry/opentelemetry-collector-releases),
  verified against the pinned SHA-256.
- **The OpenCode plugin** from npm, MPL-2.0, resolved by OpenCode at server start.
- `kubectl` with access to the cluster, for `enroll` only.
- `curl`, `shasum`, `tar`, `launchctl`, `uname`, `sw_vers`, `du` from the base system.

## API / Interfaces

```sh
otel-agent enroll HOST [--context CTX]   # read HOST's token and the gateway URL with kubectl, then configure
otel-agent configure URL HOST < token    # store URL, host and token (0600), install the collector, (re)start the LaunchAgent
otel-agent install                       # download + verify the pinned collector; install the LaunchAgent once enrolled
otel-agent converge                      # what sync runs after apply: install the pinned release, restart on change
otel-agent check                         # exit 0 when the collector can start, else print why and exit 78
otel-agent serve                         # LaunchAgent entry point
otel-agent status                        # service, collector, host, fragments, queue on disk, health, counters, queue per exporter
otel-agent ping                          # send one test event ({service_name="otel-agent"} in Loki)
~/.dotfiles/sync.sh otel-agent           # the sync step alone
```

`enroll` never prints the token. Exit statuses: 64 usage, 65 bad input or
checksum, 69 a download or the cluster unavailable, 70 a release that does not
run here, 78 not enrolled or not configured.

Any OTLP client on the Mac can send to `http://127.0.0.1:4318` (HTTP) or
`127.0.0.1:4317` (gRPC) without credentials.

## Build / Run / Test

Each Mac needs the `agents.otel-agent` feature, which the `desktop` profile
enables: its `~/.config/dotfiles/machine.toml` lists `desktop`, or enables the
feature, and `dotfiles apply` has linked `~/.config/otel-agent/config.yaml`.

Enroll each Mac once, after the cluster has its `otel-gateway-token-<host>`
Secret. On a Mac with `kubectl` access:

```sh
~/.dotfiles/bin/otel-agent enroll studio
~/.dotfiles/bin/otel-agent enroll mbp
~/.dotfiles/bin/otel-agent enroll mini --context <kube context>   # when the current context is another cluster
```

On a Mac without `kubectl`, pipe its token in from one that has it:

```sh
# from studio, for the mini
kubectl -n monitoring get secret otel-gateway-token-mini -o jsonpath='{.data.token}' | base64 -d \
  | ssh mini ~/.dotfiles/bin/otel-agent configure https://otel.<internal domain> mini
```

Then, at that Mac: allow `otelcol-contrib` when macOS asks about the local
network, and check delivery:

```sh
~/.dotfiles/bin/otel-agent ping && sleep 10 && ~/.dotfiles/bin/otel-agent status
```

Enrolling satisfies the `agents.otel-agent` feature's LaunchAgent, so `configure`
runs `dotfiles apply`, which installs and loads it (a collector already loaded is
restarted on the new token instead). When enrollment ran over ssh and `status`
shows `service: not loaded`, launchd refused a load from outside the GUI login:
the next sync loads it, or run `dotfiles apply` at the Mac.

Tests and config validation:

```sh
python3 -m unittest tests.test_dotfiles.OtelAgent

# validate the config with the pinned binary; dummy values stand in for serve's
OTEL_AGENT_GATEWAY=https://gateway.example OTEL_AGENT_TOKEN=$(printf 'a%.0s' {1..48}) \
OTEL_AGENT_HOST=studio OTEL_AGENT_QUEUE=$(mktemp -d) \
  ~/.local/libexec/otelcol/<version>_<platform>/otelcol-contrib validate \
  --config=features/agents.otel-agent/home/.config/otel-agent/config.yaml
```

To upgrade, set `OTELCOL_VERSION` and both `OTELCOL_SHA256` entries (from each
archive's `.sha256` release asset) in `bin/otel-agent`, check the exporterhelper
and filestorage READMEs of that version for changed keys, and validate the
config with the new binary as above. After the merge, each Mac's next sync
installs the release and restarts the collector on it; each Mac then needs a
new Local Network grant.

An install from before host names (an endpoint and token in
`~/.local/share/otel-agent`, no `host` file) must run
`~/.dotfiles/bin/otel-agent enroll <host>` after its first pull of this
version. Until then every sync reports `no host name configured` and `serve`
refuses to start: the gateway accepts only per-host tokens, so the shared one
the install holds delivers nothing. Enrolling stores the host and its token
and reloads the collector on the new release.

## Operations

- **Health:** `otel-agent status`. `exporter_sent_*` should grow with agent
  activity; `exporter_send_failed_*` and `exporter_enqueue_failed_*` should stay
  at 0, and each exporter's queue near 0 MiB while the gateway is reachable.
- **Queue:** `status` prints the files' size on disk and each exporter's queued
  bytes against its capacity (`otelcol_exporter_queue_size` and
  `otelcol_exporter_queue_capacity`, both in bytes, by `exporter`). The
  queue files are memory-mapped, so a large backlog shows in the process's RSS
  (`otelcol_process_memory_rss`) as file-backed pages the system can reclaim;
  the Go heap (`otelcol_process_runtime_heap_alloc_bytes`) stays small.
- **Logs:** `~/Library/Logs/otel-agent/collector.{stdout,stderr}.log`, capped
  daily by `bin/disk-hygiene`. Each retry while the gateway is unreachable logs
  `Exporting failed. Will retry the request after interval.` at info.
- **Sync:** `~/.dotfiles/logs/sync.log` logs `the telemetry collector did not
  converge` when converge fails; run `~/.dotfiles/bin/otel-agent converge` to
  see why. `com.ashtonian.otel-agent is not loaded` there means apply did not
  load it: the `agents.otel-agent` feature is off here, or apply's own output
  above it names a launchctl problem (`dotfiles doctor`).
- **Dashboard:** Grafana → Applications → Coding Agents. Every minute the local collector scrapes its loopback metrics endpoint and forwards queue size and capacity, accepted and refused OTLP records and points, and export and enqueue failures under the job `coding-agent-collector`. Queue capacity is reported even when agents are idle. A sleeping or disconnected Mac leaves a gap until it can deliver again. The local status command can inspect queues during an outage.

**Failure modes:**

- *`health: unreachable`, `service: loaded, not running`.* `serve` refused to
  start; the stderr log says why. `no host name configured` or `no gateway
  configured`: run `otel-agent enroll HOST`. launchd does not restart a Mac
  that is not enrolled, so the refusal is logged once.
- *The disk queue is full.* `status` shows an exporter's queue at its capacity,
  `exporter_enqueue_failed_*` grows, and the log shows `Exporting failed.
  Rejecting data.` with `sending queue is full`. New data is dropped and the
  oldest kept. Restore the gateway path (LAN, VPN, the gateway's
  `OtelGatewayDown` alert); the queue drains by itself and compaction gives the
  space back. To discard the backlog instead:
  `launchctl bootout gui/$(id -u)/com.ashtonian.otel-agent`, delete
  `~/.local/state/otel-agent/queue/exporter_*`, then `dotfiles apply`, which
  loads it again.
  Enqueue failures while the queue is below capacity mean the disk is full.
- *Log shows `no route to host` or `EHOSTUNREACH`.* macOS Local Network Privacy
  blocks this release's binary, which happens once per release on each Mac.
  Allow `otelcol-contrib` in System Settings → Privacy & Security → Local
  Network, then `launchctl kickstart -k gui/$(id -u)/com.ashtonian.otel-agent`.
  Data queues on disk until then.
- *A `401` after a token rotation.* The log shows `Permanent error` with
  `Unauthenticated` or `401`, `exporter_send_failed_*` grows and the queue
  empties: the exporter does not retry a 401, so every queued batch it sends is
  dropped. Re-run `otel-agent enroll HOST`. A Mac whose token is rotated while
  it is off the LAN drops its backlog on reconnect unless the gateway still
  accepts its old token; re-enroll it before it reconnects when you can.
- *Architecture mismatch.* `install` or `serve` exits 69 with `no
  otelcol-contrib release is pinned for <arch>` on an architecture other than
  arm64 or x86_64, or 70 with `does not run on this Mac` when the downloaded
  build fails `--version` (the message includes the loader's error). A release
  installed from a Rosetta shell on Apple silicon shows as `(darwin_amd64)` in
  `status`; the LaunchAgent's next start runs natively, installs the
  `darwin_arm64` build and removes the other.
- *`checksum mismatch` (exit 65).* The downloaded archive is not the pinned one.
  Do not change the pin to match; check the release page and the network path.
- *Start fails with `downloading ... failed` (exit 69).* The pin moved and the
  Mac was offline when the collector started. launchd retries every 10 s; it
  starts once the download succeeds. Converge installs the release at pull time
  to avoid this.
- *`Exporting failed. Dropping data.` with `interrupted due to shutdown` at a
  restart.* Harmless with the disk queue: the interrupted batch stays queued
  and is sent after the restart.
- *A `.backup` file in the queue directory.* A queue file was corrupt (usually
  a crash during a write) and was replaced; what it held is in the backup and
  is not sent. `serve` keeps only the newest one.
- *A backlog older than 7 days is missing in Grafana.* The Mac's counters show
  it as sent; Loki refused it as too old and Mimir as out of bounds, which the
  gateway's export to them reports. A full queue drops new data and keeps the
  oldest, so an outage longer than about 9 days also loses what arrived after
  the queue filled, and once everything queued is older than 7 days (an outage
  of about 16 days) none of the outage lands.
- *`queue_size` stays high while on the LAN.* The gateway or the LAN is slow.
  Check the gateway's alerts (`OtelGatewayDown`, `OtelGatewayExportFailing`).
- *A harness shows no data.* It must be restarted after its config changed. A
  harness exporting to a port where nothing listens drops its data silently.

## Security

- The receivers listen on loopback only. The gateway URL, token and host name
  live outside this repository in a 0700 directory with 0600 files. No harness
  config holds a credential, and `enroll` passes the token from kubectl to the
  file without printing it.
- Each Mac has its own token, so one can be revoked without touching the others.
- Deleted before anything is queued or leaves the Mac:
  - identities: `user.email`, `user.id`, `user.account_id`, `user.account_uuid`,
    `user.groups`, `organization.id`;
  - content: `prompt`, `prompt_text`, `response`, `tool_input`,
    `tool_parameters`, `arguments`, `output`, `error`, `error.message`,
    `auth.error`, `body`, `body_ref`, `diff`, `hook_definitions`,
    `redacted_settings`.

  Claude Code always attaches the email and account and organization IDs, and
  Codex puts the email, account ID, tool arguments and a tool-output preview on
  its events.
- The disk queue holds only redacted data, in a 0700 directory with 0600 files.
- Prompt and response text is never enabled: Claude's `OTEL_LOG_USER_PROMPTS`
  and `OTEL_LOG_ASSISTANT_RESPONSES`, Codex's `log_user_prompt` and
  `log_agent_responses`, and the OpenCode plugin's `capturePromptInLogs` all
  stay off.
- The gateway deletes the same keys again, so a client that skips this
  collector still cannot store them.
- The collector binary is the upstream release, pinned by SHA-256 per platform
  and checked to run before it is installed.

## Code Map

| File | Purpose |
| --- | --- |
| [bin/otel-agent](../bin/otel-agent) | enroll / configure / install / converge / check / serve / status / ping |
| [features/agents.otel-agent/home/.config/otel-agent/config.yaml](../features/agents.otel-agent/home/.config/otel-agent/config.yaml) | Collector pipelines, redaction and the disk queues, the hardware metrics' included |
| [features/agents.otel-agent/launchagents/com.ashtonian.otel-agent.plist](../features/agents.otel-agent/launchagents/com.ashtonian.otel-agent.plist) | LaunchAgent, kept alive while the Mac is enrolled |
| [features/agents.otel-agent/feature.toml](../features/agents.otel-agent/feature.toml) | `dotfiles apply` installs the LaunchAgent once the enrollment files exist, and removes it when they go |
| [lib_sh/launch-agent.sh](../lib_sh/launch-agent.sh) | `configure` and `install` restart a loaded collector, or run apply to install it |
| [sync.sh](../sync.sh) | `sync_otel_agent` runs `otel-agent converge` after every apply |
| [features/agents.opencode/home/.config/opencode/opencode.jsonc](../features/agents.opencode/home/.config/opencode/opencode.jsonc) | OpenCode's OTel plugin |
| [tests/test_dotfiles.py](../tests/test_dotfiles.py) | `OtelAgent` tests, and the sync step in `Sync` |
