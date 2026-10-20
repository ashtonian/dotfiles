# Agent monitor

## Overview

[Claude Code Agent Monitor](https://github.com/hoangsonww/Claude-Code-Agent-Monitor)
(CCAM, MIT) is a web dashboard for the Claude Code and Codex sessions on this Mac:
live session and agent cards, a Kanban board, tool timelines, transcripts, token
and cost analytics, alerts, and a Run page that starts or resumes `claude` and
`codex` sessions it then supervises. It uses the CLIs' own logins and needs no
API keys.

`bin/agent-monitor` installs a pinned release, wires both CLIs' hooks to it, and
runs it as the `com.ashtonian.agent-monitor` LaunchAgent on `127.0.0.1:4820`.

The dashboard runs here, not in the cluster, because it reads `~/.claude/projects`
and `~/.codex/sessions` directly. A remote copy gets live hook events only. Its
other transfer path re-copies both history trees in full over `scp` on every
pass (about 4 GB here), and its Run page accepts only localhost browsers.

It cannot type into a session that is already running in a terminal. Run
**Resume** starts a second process on that transcript, so use it only for
sessions that have ended. Running sessions stay reachable through Remote
Control: `claudemore`/`claudemax` sessions at claude.ai/code, and the Codex
app-server for `gptmore`/`gptmax`.

## Config

`bin/agent-monitor` reads these from the environment. The LaunchAgent sets none
of them, so the service runs on the defaults.

| Variable | Type | Default | Description |
| ---------- | ------ | --------- | ------------- |
| `AGENT_MONITOR_HOME` | Directory path | `~/.local/share/agent-monitor` | Release checkout (`app/`), settings (`config/.env`) and the data link (`data`). The LaunchAgent template and installer assume the default |
| `AGENT_MONITOR_PORT` | Port | `4820` | Dashboard port. Hooks find a non-default port through `~/.claude/.agent-dashboard.json` while the server runs |
| `FNM_DIR` | Directory path | `~/Library/Application Support/fnm` | Where the pinned Node.js release is installed |
| `CODEX_HOME` | Directory path | `~/.codex` | Codex home for hooks and history |

Pinned in the script; change them there and rerun `install`:

| Constant | Value | Description |
| ---------- | ------- | ------------- |
| `CCAM_VERSION` / `CCAM_COMMIT` | `2.3.0` / `a06db03…` | Upstream release tag and the commit it must resolve to; a moved tag aborts the install |
| `NODE_VERSION` | `24.22.0` | Node.js 24 LTS, the runtime upstream builds and tests against |

`serve` sets the upstream variables `NODE_ENV=production`,
`DASHBOARD_HOST=127.0.0.1`, `DASHBOARD_PORT`, `DASHBOARD_DATA_DIR`
(`<home>/data`), `DASHBOARD_ENV_PATH` (`<home>/config/.env`) and
`DASHBOARD_UPDATE_CHECK=0`. Upstream's update notifier would `git fetch` every
five minutes and compare the pinned tag against its default branch. Other upstream
settings, such as sweep intervals, snapshot retention and alert rules, go in
`config/.env` or the Settings page. Upstream's
[`.env.example`](https://github.com/hoangsonww/Claude-Code-Agent-Monitor/blob/v2.3.0/.env.example)
lists every key.

`install --data-dir DIR` chooses the data directory (default
`/Volumes/E2TB/agent-monitor`, mode 0700). It holds `dashboard.db` and the
transcript snapshots. Snapshots are plain copies of live transcripts, gzipped
once an original is deleted, so expect several GB. Without `--data-dir`, a later
`install` keeps the existing link.

## External dependencies

| Dependency | Used for |
| ------------ | ---------- |
| GitHub (`hoangsonww/Claude-Code-Agent-Monitor`) | Release checkout at install time |
| npm registry | Server and client dependencies at install time |
| `fnm` (Brewfile) | Installs the pinned Node.js |
| `git`, `curl` | Checkout; `status` health check |
| `claude`, `codex` on the LaunchAgent PATH | Run page sessions only |

With the update check off, the server makes no outbound calls beyond features
you configure, such as webhooks, web push and remote sources. Install-time scripts of the
server's dependencies are skipped, including an analytics ping.
`better-sqlite3` is rebuilt explicitly.

## Interfaces

| Interface | Location |
| ----------- | ---------- |
| Web UI | <http://127.0.0.1:4820> |
| Health | `GET /api/health` → `{"status":"ok","version":"2.3.0",…}` |
| REST API and OpenAPI | `/api/*`, interactive docs at `/api/docs` |
| Claude Code hooks | 8 events in `~/.claude/settings.json`: `node <app>/scripts/hook-handler.js <event>` |
| Codex hooks | 6 events in `~/.codex/hooks.json`: `node <app>/scripts/codex-hook-handler.js <event>` |
| Upstream CLI | `node ~/.local/share/agent-monitor/app/bin/ccam.js --help` |

Hooks are fire-and-forget. Each one starts a short Node.js process that posts to
the dashboard with a 2 s timeout and never blocks or fails the agent, even when
the dashboard is down. The installer leaves other hook entries alone. New
sessions pick the hooks up, and Codex sessions report even without hooks
because the dashboard watches its rollout files.

## Build, run and test

```sh
~/.dotfiles/bin/agent-monitor install    # install or update; idempotent
~/.dotfiles/bin/agent-monitor status     # release, data link, service, health, hooks
open http://127.0.0.1:4820

# Service only (after an install)
~/.dotfiles/bin/dotfiles-install-launchagents.sh --agent-monitor-only

# Remove the hooks (the service and data stay)
~/.dotfiles/bin/agent-monitor uninstall-hooks

# Tests (no network)
python3 -B -m unittest tests.test_dotfiles.AgentMonitor -v
```

The first start imports all existing Claude Code and Codex history. Expect
minutes of CPU and disk activity before analytics are complete.

## Operations

Logs: `~/Library/Logs/agent-monitor/server.{stdout,stderr}.log` (not rotated).

```sh
launchctl print "gui/$(id -u)/com.ashtonian.agent-monitor"
launchctl kickstart -k "gui/$(id -u)/com.ashtonian.agent-monitor"   # restart
tail -50 ~/Library/Logs/agent-monitor/server.stderr.log
```

The service runs only while `<home>/data` resolves. With the data volume
unmounted it stays stopped, and launchd starts it again when the volume returns.
Upgrades replace the checkout in place, so restart the service afterwards.

Troubleshooting:

- **Service "running" but health unreachable, logs empty.** macOS is asking
  whether `node` may access a removable volume. Click **Allow**. The prompt
  blocks other apps' privacy checks while it is pending. Then `kickstart -k`.
  The grant belongs to
  `~/Library/Application Support/fnm/node-versions/v24.22.0/installation/bin/node`,
  so a new `NODE_VERSION` asks once more. If you denied it, re-enable it in
  System Settings → Privacy & Security → Files & Folders → node →
  Removable Volumes.
- **Exit status 78 in `launchctl print`.** Node.js or the checkout is missing:
  rerun `install`.
- **`install` aborts: tag resolved to an unexpected commit.** Upstream moved the
  tag. Verify the new commit before updating `CCAM_COMMIT`.
- **`better-sqlite3 does not load`.** The native driver does not match Node.js:
  rerun `install` (it rebuilds the driver).
- **A session is missing.** Check `status` for hooks. Sessions started before
  the hooks were installed appear through history import, not live events.
- **Port in use.** `lsof -nP -iTCP:4820 -sTCP:LISTEN`, then stop the other process
  or set `AGENT_MONITOR_PORT` for `install` and in the installed plist.

There is no metrics endpoint wired to the homelab. Upstream's `/api/metrics`
needs `DASHBOARD_TOKEN`.

## Security

- Listens on loopback only, without a token. Upstream treats the loopback bind
  as the trust boundary. The API returns every transcript and can start
  `claude`/`codex` with your logins, so do not widen `DASHBOARD_HOST` without
  `DASHBOARD_TOKEN` and TLS.
- Upstream rejects requests whose `Host` is not loopback (DNS rebinding) and Run
  requests from non-localhost origins.
- The data directory holds full transcript copies, so it is created with mode 0700.
- The release is pinned to a verified commit. Server dependencies install
  without lifecycle scripts, apart from `better-sqlite3`.

## Code map

| Path | Role |
| ------ | ------ |
| `bin/agent-monitor` | Install/update, `serve` entry point, status, hook removal |
| `launchagents/com.ashtonian.agent-monitor.plist` | Service template: loopback, PATH for Run, waits on the data link |
| `bin/dotfiles-install-launchagents.sh` | `--agent-monitor-only`; included in the full install once installed |
| `tests/test_dotfiles.py` (`AgentMonitor`) | Loopback env, missing-install error, usage error, hook removal |
