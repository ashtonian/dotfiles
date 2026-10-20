# opencode: a local coordinator for Claude Code and GPT Astra

## Overview

[OpenCode](https://opencode.ai) runs as an always-on server on this Mac, driven
from a terminal (`oc`) and a browser at the same time: both attach to the same
server and see the same sessions live.

Its default agent, **coordinator**, runs on a self-hosted model (Qwen3.6-35B-A3B
behind an OpenAI-compatible gateway on the LAN). It does no coding itself. It
turns a request into briefs and runs them as background jobs on stronger models
through their real CLIs and subscriptions:

| Worker | CLI | Models | Typical use |
| -------- | ----- | -------- | ------------- |
| `claude` | `claude -p` | `opus` (default, `opus[1m]`), `fable` (`fable[1m]`), `sonnet`, `haiku` | Implementation, debugging, infrastructure work, fixing findings |
| `codex` | `codex exec` | `astra` (default, `gpt-6-astra`), `sol` (`gpt-6.1-sol`) | Independent review, audits, verification, second opinions |

Defaults mirror the interactive launchers (`claudemore`, `claudemax`, `gptmax`):
Claude at effort `xhigh`, Codex at `max`. The plugin keeps `max` for a delegated
`sol` job too; the interactive `gptmore` helper separately defaults to `xhigh`.

Jobs are asynchronous. The coordinator starts a job, reports what is running,
and ends its turn. When the worker exits, the `delegate` plugin posts a
`[delegate]` notice into the coordinator's session, which wakes it to read the
result and report or start the next step (for example, Claude implements, Astra
reviews, Claude fixes the confirmed findings in its original session).

The checked-in model and small-model aliases are identical so title/summary
requests use the same backend as the coordinator. Gateway capacity, model
availability, and performance depend on the local deployment; this repository
does not provision the gateway or establish benchmark results.

## Config

Configuration lives in four places: `opencode.jsonc` and the coordinator agent
file in this package (both public), local files under
`~/.local/share/opencode/homelab/`, and environment variables read by the
plugin and the server wrapper.

### opencode.jsonc

| Key | Value | Why |
| ----- | ------- | ----- |
| `enabled_providers` | `["homelab"]` | Enable only the local provider in this config. Delegated worker CLIs contact their own configured providers. |
| `share` | `disabled` | Disable OpenCode's session-sharing feature. |
| `autoupdate` | `false` | Homebrew owns upgrades. |
| `shell` | `/opt/homebrew/bin/bash` | The shell tool runs `bash -c`, matching Claude Code's Bash tool; bash semantics for model-written commands. |
| `default_agent` | `coordinator` | |
| `model`, `small_model` | `homelab/qwen3.6-35b` | Keep coordinator, title, and summary requests on the same alias. |
| `provider.homelab.options.baseURL` | `{file:~/.local/share/opencode/homelab/base-url}` | Gateway URL, kept out of this public repo. |
| `provider.homelab.options.apiKey` | `{file:~/.local/share/opencode/homelab/litellm.key}` | Scoped virtual key. |
| `provider.homelab.models.*` | The one alias the gateway serves | The gateway keeps a single model resident and does not swap; see the model table below. |

| Local alias | Context / output tokens | Capabilities configured |
| ------------- | ------------------------- | ------------------------- |
| `qwen3.6-35b` | 65,536 / 16,384 | Tool calls; coordinator and small-model default |

These are client-side limits, not evidence of the gateway's deployed limits.
Keep them compatible with the server configuration.

### Coordinator agent (`agents/coordinator.md`)

| Field / permission | Setting | Why |
| ------------ | --------- | ----- |
| `mode`, `temperature` | primary, 0.2 | Agent mode and generation temperature. |
| `edit` | deny | The coordinator delegates changes. |
| `bash` | deny, except `git status/log/diff/show/branch` and `ls` | Enough to inspect a repo before writing a brief. |
| `task` | deny | OpenCode subagents would run on the local model; real work goes to workers. |
| `webfetch` | ask | |
| `delegate_write` | ask | Write-access jobs need approval once per directory (`always`) or per job (`once`). |

### Local files (`~/.local/share/opencode/homelab/`, mode 0700)

| File | Contents |
| ------ | ---------- |
| `base-url` | Gateway base URL ending in `/v1` |
| `litellm.key` | LiteLLM virtual key; scope it on the gateway to the configured local alias |
| `server-password` | HTTP basic-auth password for the server (user `opencode`) |

### Environment

| Variable | Type | Default | Read by / effect |
| ---------- | ------ | --------- | ------------------ |
| `BASH_ENV` | File path | `~/.config/shell/env.sh` (LaunchAgent) | Every `bash -c` the shell tool runs sources the shared environment (stow package `shell`); delegated Claude workers inherit it too |
| `OPENCODE_HOSTNAME` | Address string | 0.0.0.0 | Server wrapper bind address |
| `OPENCODE_PORT` | Port number | 4096 | Server wrapper, `oc`, `ocweb` |
| `OPENCODE_SERVER_PASSWORD` | Secret string | Loaded from server-password | Server wrapper replaces any inherited value from the local file |
| `XDG_STATE_HOME` | Directory path | `~/.local/state` | Plugin state parent when `DELEGATE_STATE_DIR` is unset |
| `DELEGATE_STATE_DIR` | Directory path | `$XDG_STATE_HOME/opencode-delegate` | Plugin job store |
| `DELEGATE_CLAUDE_BIN` | Executable path/name | claude on PATH | Claude worker executable |
| `DELEGATE_CODEX_BIN` | Executable path/name | codex on PATH | Codex worker executable |
| `DELEGATE_MAX_RUNNING` | Positive integer | 4 | Concurrent-job cap |
| `DELEGATE_POLL_MS` | Positive integer, milliseconds | 5000 | Completion polling interval |
| `DELEGATE_RESULT_CHARS` | Positive integer, characters | 12000 | Returned final-message limit; full output stays on disk |
| `DELEGATE_RETENTION_DAYS` | Positive integer, days | 14 | Finished jobs pruned at server start |

Settings parse as base-10 integers; nonnumeric or nonpositive results fall back
to their defaults. Set service overrides in the installed LaunchAgent's `EnvironmentVariables`, then reload it;
the daemon does not read `~/.zshrc.local`. Reinstallation replaces local plist
edits. A shell-only `OPENCODE_PORT` override changes where `oc`/`ocweb` connect, not
where an already running server listens.

### Worker invocation

| Access | Claude | Codex |
| -------- | -------- | ------- |
| `read` | `--restricted --tools Read,Glob,Grep --allowedTools Read,Glob,Grep --permission-mode dontAsk --strict-mcp-config --mcp-config '{"mcpServers":{}}'` | `sandbox_mode="read-only"` |
| `write` | `--dangerously-skip-permissions --permission-mode bypassPermissions` (as `claudemore`; subagents allowed) | `sandbox_mode="workspace-write"`, network on |

Claude read jobs expose only file reading and search tools. Restricted mode
ignores user, project and local settings, and the empty strict MCP configuration
prevents inherited servers or shell permissions from granting writes. They cannot
run shell commands or tests. The Claude CLI must support `--restricted` and the
tool-selection flags; unsupported versions fail the job at startup.

Claude workers also run with `ENABLE_CLAUDEAI_MCP_SERVERS=false`, the same policy
as the `wg-*` fleet sessions: unattended agents get no claude.ai connector
content (mail, Drive).

## External Dependencies

| Dependency | Why | Failure effect |
| ------------ | ----- | ---------------- |
| OpenCode (validated with 1.19.x; `brew "anomalyco/tap/opencode"`) | The server, TUI and web UI | Nothing runs |
| LLM gateway (LiteLLM, LAN, internal domain) and its llama.cpp backend | The coordinator's model | The coordinator cannot answer; running jobs are unaffected |
| Claude Code (`~/.local/bin/claude`), signed in to claude.ai | `claude` worker | `claude` jobs fail at start; the error is in the job's `stderr.log` |
| Codex CLI (`cask "codex"`), signed in | `codex` worker | `codex` jobs fail at start |
| `@opencode-ai/plugin` (installed by OpenCode next to its config) | Plugin and tool API | The plugin does not load; no `delegate_*` tools |
| `bin/stable-exec` | Fixed binary path for privacy grants | The service wrapper cannot start without it |

## API / Interfaces

### Shell

| Command | Description |
| --------- | ------------- |
| `oc [attach options]` | Terminal UI on the running server, in `$PWD` |
| `ocweb` | Opens the web UI and copies the password to the clipboard |

The web UI is also reachable from other devices on the LAN or over the VPN at
`http://<this Mac>:4096` (user `opencode`). Remote access requires suitable
network protection; see Security. The service does not configure TLS or a VPN.

### Tools (registered by `plugins/delegate.ts`)

| Tool | Arguments | Behavior |
| ------ | ----------- | ---------- |
| `delegate_start` | `worker`, `title`, `task`, `cwd?`, `access?` (read), `model?`, `effort?` | Starts a detached worker and returns its job id immediately. Write access asks for `delegate_write` approval. |
| `delegate_status` | `job?` | Lists the 15 most recent jobs, or one job's state, worker session and last 8 actions |
| `delegate_result` | `job` | Outcome, exit code, duration, turns and cost (Claude), worker session id, and the final message |
| `delegate_reply` | `job`, `message`, `access?`, `effort?` | Continues a finished job's worker session (`claude --resume`, `codex exec resume`) as a new job |
| `delegate_cancel` | `job` | SIGTERM to the worker's process group, SIGKILL after 10 s |

Job states: `running`, `done`, `failed`, `cancelled`, `lost` (the process vanished
without recording an exit code, e.g. a reboot).

### Completion notices

When a job ends (except by cancellation), the plugin sends this to the session
that started it, as the agent that started it:

```text
[delegate] Job claude-20261014-225524-65fa finished: done. claude/opus, write access, "add retries".
This is an automated notice, not a message from the user.
Call delegate_result with job "claude-20261014-225524-65fa" to read the outcome before reporting it or planning the next step.
```

### Taking over a worker session

`delegate_result` prints the command. Claude sessions can be continued
interactively and steered from claude.ai with Remote Control:

```sh
cd /path/to/project
claude --resume SESSION_ID --remote-control
# Or continue a Codex session:
codex resume THREAD_ID
```

### HTTP

The server is OpenCode's standard API (`/session`, `/session/:id/prompt_async`,
`/permission`, `/event`, ...), all behind basic auth.

## Build / Run / Test

One-time setup on a new machine:

```sh
brew install anomalyco/tap/opencode          # or brew bundle
cd ~/.dotfiles/stow && stow -t ~ opencode    # ~/.config/opencode -> this package

# Local files: base URL, a scoped LiteLLM virtual key, a server password.
umask 077
install -d -m 700 ~/.local/share/opencode/homelab
printf '%s' 'https://<gateway host>/v1' > ~/.local/share/opencode/homelab/base-url
# Create a key scoped to the configured model aliases in the gateway admin UI.
# Copy only that key, then save it without placing it in a shell argument:
(umask 077; pbpaste > ~/.local/share/opencode/homelab/litellm.key)
(umask 077; openssl rand -base64 32 | tr -d '\n=' | tr '+/' '-_' > ~/.local/share/opencode/homelab/server-password)

chmod 600 ~/.local/share/opencode/homelab/{base-url,litellm.key,server-password}
~/.dotfiles/bin/dotfiles-install-launchagents.sh --opencode-only
```

Then grant **Full Disk Access** to `~/.local/libexec/opencode-stable/bin/opencode`
(System Settings → Privacy & Security → Full Disk Access → **+** → Cmd+Shift+G).
Grant access when the server or its workers need protected directories or
external volumes. If a worker stalls at a privacy prompt, check the server's
stable executable and Full Disk Access entry.

Checks:

```sh
opencode models homelab        # verify the configured local model aliases
oc                             # TUI; ask: "call delegate_status"
```

End-to-end: ask the coordinator to start a read-only `claude` job with model
`haiku`, effort `low`, and a `codex` job with effort `low`, each listing the
files in a scratch directory. Completion checks run at the configured polling
interval; notices also depend on successful delivery. Worker latency is
provider-dependent. These checks use live model accounts and can incur usage.
For the local mock-based regression suite, run from the dotfiles repository root:

```sh
python3 -B -m unittest discover -s tests -v
```

The delegated-worker test requires Bun and the plugin dependencies installed by
OpenCode. It uses a fake worker without calling a model provider.

The plugin is TypeScript run by OpenCode's Bun runtime; there is no build step.
After editing it or the config, restart the server (below).

## Operations

| What | How |
| ------ | ----- |
| Process / auth boundary | `launchctl list com.ashtonian.opencode` should have a PID. An unauthenticated request returning `401` checks reachability/auth only; use the health request below to check the server. |
| Server logs | `~/Library/Logs/opencode/server.{stdout,stderr}.log` (startup); `~/.local/share/opencode/log/opencode.log` (runtime, including the plugin's job start, cancel and notice-delivery messages: grep for the job id) |
| Restart (after editing config or plugin, or upgrading) | `launchctl kickstart -k gui/$(id -u)/com.ashtonian.opencode`. Running jobs keep going and are picked up again. |
| Job files | `~/.local/state/opencode-delegate/jobs/<id>/`: `prompt.md`, `events.jsonl`, `stderr.log`, `result.md`, `exit` |
| Live worker output | `tail -f ~/.local/state/opencode-delegate/jobs/<id>/events.jsonl` |
| Usage / metrics | Gateway admin UI for the scoped key; job results expose Claude cost/turns when present. This plugin adds no metrics endpoint. |

Authenticated health check (reads the password into memory; does not put it in
command arguments or print it):

```sh
python3 - <<'PY'
import base64
import json
import os
from pathlib import Path
from urllib.request import Request, urlopen

password = (Path.home() / '.local/share/opencode/homelab/server-password').read_text().strip()
token = base64.b64encode(('opencode:' + password).encode()).decode()
port = os.environ.get('OPENCODE_PORT', '4096')
request = Request(f'http://127.0.0.1:{port}/global/health',
                  headers={'Authorization': 'Basic ' + token})
with urlopen(request, timeout=5) as response:
    print(json.dumps(json.load(response)))
PY
```

Expect `healthy: true` and the running version. This does not check the gateway
or worker authentication. Restarting interrupts active coordinator responses
and attached sessions; detached workers survive and are recovered by the plugin.
Service logs have no rotation configured by these scripts.

### Failure modes and troubleshooting

- **The coordinator does not answer or errors on every message.** Check the
  server log and the gateway's health/model list in its admin UI. Confirm the
  base URL ends in /v1 and the configured model aliases exist. A 401 means the
  gateway key is rejected; rotate or correct it. A timeout requires checking
  gateway/backend availability. Avoid pasting the key into command arguments or
  logs when testing.
- **A job fails at once.** Read `stderr.log` in its job directory. `command not
  found` means `DELEGATE_*_BIN` or the LaunchAgent's `PATH` is wrong. An auth
  error means the CLI's login expired: run `claude` or `codex` interactively once.
- **A job stays `running` with no new events for a long time.** `tail` its
  `events.jsonl`. If a worker is stuck on a path under `/Volumes`, the Full Disk
  Access grant is missing or off: check that the server runs the stable copy
  (`ps -axo command | grep opencode-stable`) and that the grant is on.
- **A job shows `lost`.** The worker died without the wrapper recording an exit
  code (reboot, or a kill outside `delegate_cancel`). The job's session can
  still be continued with `delegate_reply` if a worker session id was recorded.
- **No `[delegate]` notice arrived.** The plugin checks every 5 s. If the job
  directory has `exit` but no `notified`, the server could not deliver it: grep
  `~/.local/share/opencode/log/opencode.log` for the job id. A `notified` file with no notice in
  the session means the owning session was deleted (logged as dropped).
- **`delegate_start` refuses with "jobs are already running".** The cap
  (`DELEGATE_MAX_RUNNING`) is reached. Wait or cancel one.
- **The provider rejects a job.** Preserve the reported error and follow the
  provider's guidance. Retrying does not establish that a task succeeded; inspect
  the job's exit status and final result.

## Security

- **The server is a shell on this Mac.** Anyone who can authenticate can run
  agents with bypassed permissions. It binds to all interfaces so other devices
  on the LAN and VPN can reach the web UI. It uses plain HTTP, so the basic-auth
  password crosses the LAN unencrypted. Keep it off any public network, and set
  `OPENCODE_HOSTNAME=127.0.0.1` in the LaunchAgent if remote access is not needed.
- **Write access is approved per directory.** The `delegate_write` permission
  asks before write-access jobs. Claude read jobs expose only Read/Glob/Grep,
  with inherited settings and MCP tools restricted; Codex read jobs use its
  read-only filesystem sandbox. Read access still permits reading accessible
  private files and is not a confidentiality boundary.
- **Worker environment is inherited with specific removals.** The plugin removes
  `OPENCODE_SERVER_PASSWORD`, `OPENCODE_SERVER_USERNAME`, and CLAUDECODE. Other
  environment variables and the user's CLI authentication remain available.
  CLI sandbox/tool controls do not establish isolation from every inherited
  setting or external integration.
- **Secrets stay out of this repo.** It is public and auto-pushed. The gateway
  URL, key and password live in `~/.local/share/opencode/homelab/` (0700). Job
  directories are 0700 and their files 0600, because briefs and worker output can
  contain sensitive material.
- **Scope the gateway key on the gateway.** Restrict it to the configured model
  aliases and revoke it independently when needed. The public config does not
  enforce server-side key policy.
- **Job ids are validated** before they are used as paths.

## Code Map

| Path | Purpose |
| ------ | --------- |
| `.config/opencode/opencode.jsonc` | Providers, models, default agent |
| `.config/opencode/agents/coordinator.md` | Coordinator prompt and permissions |
| `.config/opencode/plugins/delegate.ts` | Job store, worker commands, completion notices, the five `delegate_*` tools |
| `../../bin/opencode-server` | LaunchAgent entry point: loads the password, runs `opencode serve` from the stable path |
| `../../bin/stable-exec` | Runs a Homebrew CLI from a fixed path so privacy grants survive upgrades |
| `../../launchagents/com.ashtonian.opencode.plist` | The always-on server |
| `../../lib_sh/opencode.sh` | `oc`, `ocweb` |
