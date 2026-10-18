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
|--------|-----|--------|-------------|
| `claude` | `claude -p` | `opus` (default, `opus[1m]`), `fable` (`fable[1m]`), `sonnet`, `haiku` | Implementation, debugging, infrastructure work, fixing findings |
| `codex` | `codex exec` | `astra` (default, `gpt-6-astra`), `sol` (`gpt-6.1-sol`) | Independent review, audits, verification, second opinions |

Defaults mirror the interactive launchers (`claudemore`, `claudemax`, `gptmax`):
Claude at effort `xhigh`, Astra at `max`.

Jobs are asynchronous. The coordinator starts a job, reports what is running,
and ends its turn. When the worker exits, the `delegate` plugin posts a
`[delegate]` notice into the coordinator's session, which wakes it to read the
result and report or start the next step (for example, Claude implements, Astra
reviews, Claude fixes the confirmed findings in its original session).

### Why this model

The coordinator only routes work, writes briefs and reports results, so the
criteria are reliable tool calling over many turns, instruction following, and
speed, not raw coding strength. Qwen3.6-35B-A3B is the strongest documented
tool-calling model that fits the 32 GB card (MCP-Atlas 62.8, TAU3 67.2,
Apache 2.0). It decodes at ~110 tok/s there and is already the gateway's
resident default. The GPU holds one model at a time, so any other model forces
a ~20 GB reload for every app that shares it. Open models comparable to Opus or
Astra (GLM-5.3, Kimi K3, DeepSeek V4.1, Qwen3.8-Max) need hundreds of GB of fast
memory. That is why the heavy work goes to the real Claude and Astra.

## Config

Configuration lives in four places: `opencode.jsonc` and the coordinator agent
file in this package (both public), local files under
`~/.local/share/opencode/homelab/`, and environment variables read by the
plugin and the server wrapper.

### opencode.jsonc

| Key | Value | Why |
|-----|-------|-----|
| `enabled_providers` | `["homelab"]` | Only the local gateway. OpenCode's hosted providers stay unloaded, so no session can send code to a third party by picking one of their models. |
| `share` | `disabled` | Sessions are never uploaded to opencode.ai. |
| `autoupdate` | `false` | Homebrew owns upgrades. |
| `default_agent` | `coordinator` | |
| `model`, `small_model` | `homelab/qwen3.6-35b` | Same model for titles and summaries; a different one would force a GPU swap. |
| `provider.homelab.options.baseURL` | `{file:~/.local/share/opencode/homelab/base-url}` | Gateway URL, kept out of this public repo. |
| `provider.homelab.options.apiKey` | `{file:~/.local/share/opencode/homelab/litellm.key}` | Scoped virtual key. |
| `provider.homelab.models.*.limit` | 64K context (32K for `qwen3.8-27b`) | Matches each model's server-side `-c`. |

### Coordinator agent (`agents/coordinator.md`)

| Permission | Setting | Why |
|------------|---------|-----|
| `edit` | deny | The coordinator delegates; it never edits. |
| `bash` | deny, except `git status/log/diff/show/branch` and `ls` | Enough to inspect a repo before writing a brief. |
| `task` | deny | OpenCode subagents would run on the local model; real work goes to workers. |
| `webfetch` | ask | |
| `delegate_write` | ask | Write-access jobs need approval once per directory (`always`) or per job (`once`). |

### Local files (`~/.local/share/opencode/homelab/`, mode 0700)

| File | Contents |
|------|----------|
| `base-url` | Gateway base URL ending in `/v1` |
| `litellm.key` | LiteLLM virtual key `opencode-mac-studio`, scoped to `qwen3.6-35b`, `qwen3.6-35b-thinking`, `qwen3-coder-30b`, `qwen3.8-27b` |
| `server-password` | HTTP basic-auth password for the server (user `opencode`) |

### Environment

| Variable | Default | Read by | Description |
|----------|---------|---------|-------------|
| `OPENCODE_HOSTNAME` | `0.0.0.0` | `bin/opencode-server` | Server bind address |
| `OPENCODE_PORT` | `4096` | `bin/opencode-server`, `oc`, `ocweb` | Server port |
| `DELEGATE_STATE_DIR` | `$XDG_STATE_HOME/opencode-delegate` (`~/.local/state/opencode-delegate`) | plugin | Job store |
| `DELEGATE_CLAUDE_BIN` | `claude` (on `PATH`) | plugin | Claude Code executable |
| `DELEGATE_CODEX_BIN` | `codex` (on `PATH`) | plugin | Codex executable |
| `DELEGATE_MAX_RUNNING` | `4` | plugin | Concurrent running jobs; `delegate_start` refuses beyond it |
| `DELEGATE_POLL_MS` | `5000` | plugin | How often finished jobs are detected |
| `DELEGATE_RESULT_CHARS` | `12000` | plugin | Final-message characters returned to the coordinator; the full text stays on disk |
| `DELEGATE_RETENTION_DAYS` | `14` | plugin | Finished jobs older than this are deleted at server start |

### Worker invocation

| Access | Claude | Codex |
|--------|--------|-------|
| `read` | `--restricted --tools Read,Glob,Grep --allowedTools Read,Glob,Grep --permission-mode dontAsk --strict-mcp-config --mcp-config '{"mcpServers":{}}'` | `sandbox_mode="read-only"` |
| `write` | `--dangerously-skip-permissions --permission-mode bypassPermissions --disallowedTools Agent` (as `claudemore`) | `sandbox_mode="workspace-write"`, network on |

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
|------------|-----|----------------|
| OpenCode 1.19.x (`brew "anomalyco/tap/opencode"`) | The server, TUI and web UI | Nothing runs |
| LLM gateway (LiteLLM, LAN, internal domain) and its llama.cpp backend | The coordinator's model | The coordinator cannot answer; running jobs are unaffected |
| Claude Code (`~/.local/bin/claude`), signed in to claude.ai | `claude` worker | `claude` jobs fail at start; the error is in the job's `stderr.log` |
| Codex CLI (`cask "codex"`), signed in | `codex` worker | `codex` jobs fail at start |
| `@opencode-ai/plugin` (installed by OpenCode next to its config, pinned to the OpenCode version) | Plugin and tool API | The plugin does not load; no `delegate_*` tools |
| `bin/stable-exec` | Fixed binary path for privacy grants | Full Disk Access is lost on every upgrade |

## API / Interfaces

### Shell

| Command | Description |
|---------|-------------|
| `oc [attach options]` | Terminal UI on the running server, in `$PWD` |
| `ocweb` | Opens the web UI and copies the password to the clipboard |

The web UI is also reachable from other devices on the LAN or over the VPN at
`http://<this Mac>:4096` (user `opencode`).

### Tools (registered by `plugins/delegate.ts`)

| Tool | Arguments | Behavior |
|------|-----------|----------|
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

```
[delegate] Job claude-20261014-225524-65fa finished: done. claude/opus, write access, "add retries".
This is an automated notice, not a message from the user.
Call delegate_result with job "claude-20261014-225524-65fa" to read the outcome before reporting it or planning the next step.
```

### Taking over a worker session

`delegate_result` prints the command. Claude sessions can be continued
interactively and steered from claude.ai with Remote Control:

```sh
cd <cwd> && claude --resume <session-id> --remote-control
cd <cwd> && codex resume <thread-id>
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
install -d -m 700 ~/.local/share/opencode/homelab
printf '%s' 'https://<gateway host>/v1' > ~/.local/share/opencode/homelab/base-url
# create a virtual key in the LiteLLM admin UI (or POST /key/generate), save it:
(umask 077; pbpaste > ~/.local/share/opencode/homelab/litellm.key)
(umask 077; openssl rand -base64 32 | tr -d '\n=' | tr '+/' '-_' > ~/.local/share/opencode/homelab/server-password)

~/.dotfiles/bin/dotfiles-install-launchagents.sh --opencode-only
```

Then grant **Full Disk Access** to `~/.local/libexec/opencode-stable/bin/opencode`
(System Settings → Privacy & Security → Full Disk Access → **+** → Cmd+Shift+G).
The workers it starts inherit its privacy grants, and projects live on an
external volume; without the grant, the first job there raises a "removable
volume" prompt that stalls until answered.

Checks:

```sh
opencode models homelab        # lists exactly the four homelab models
oc                             # TUI; ask: "call delegate_status"
```

End-to-end: ask the coordinator to start a read-only `claude` job with model
`haiku`, effort `low`, and a `codex` job with effort `low`, each listing the
files in a scratch directory. Both `[delegate]` notices should arrive within a
minute and the coordinator should report both results.

The plugin is TypeScript run by OpenCode's Bun runtime; there is no build step.
After editing it or the config, restart the server (below).

## Operations

| What | How |
|------|-----|
| Health | `launchctl list com.ashtonian.opencode` (PID present); `curl -s -o /dev/null -w '%{http_code}' localhost:4096/` returns `401` |
| Server logs | `~/Library/Logs/opencode/server.{stdout,stderr}.log` (startup); `~/.local/share/opencode/log/opencode.log` (runtime, including the plugin's job start, cancel and notice-delivery messages: grep for the job id) |
| Restart (after editing config or plugin, or upgrading) | `launchctl kickstart -k gui/$(id -u)/com.ashtonian.opencode`. Running jobs keep going and are picked up again. |
| Job files | `~/.local/state/opencode-delegate/jobs/<id>/`: `prompt.md`, `events.jsonl`, `stderr.log`, `result.md`, `exit` |
| Live worker output | `tail -f ~/.local/state/opencode-delegate/jobs/<id>/events.jsonl` |
| Gateway usage | LiteLLM admin UI → keys → `opencode-mac-studio` |

### Failure modes and troubleshooting

- **The coordinator does not answer or errors on every message.** Check the
  gateway: `curl -s -H "Authorization: Bearer $(<~/.local/share/opencode/homelab/litellm.key)" "$(<~/.local/share/opencode/homelab/base-url)/models"`.
  A 401 means the key was revoked: mint a new one. A timeout means the gateway
  or its GPU backend is down. A first reply that is slow by 10 to 30 s is the
  backend loading the model after another app swapped it out.
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
- **Astra jobs end with a safety-filter termination.** OpenAI's filter stops
  some code-review sessions. Rephrase the brief without words like
  "adversarial" or "attack", and have the worker write findings to a notes file
  as it goes.

## Security

- **The server is a shell on this Mac.** Anyone who can authenticate can run
  agents with bypassed permissions. It binds to all interfaces so other devices
  on the LAN and VPN can reach the web UI. It uses plain HTTP, so the basic-auth
  password crosses the LAN unencrypted. Keep it off any public network, and set
  `OPENCODE_HOSTNAME=127.0.0.1` in the LaunchAgent if remote access is not needed.
- **Write access is approved per directory.** The `delegate_write` permission
  asks before any job that may change files; read jobs cannot edit (Claude's edit
  tools are blocked; Codex runs in a read-only sandbox).
- **Workers do not get the server's credentials.** `OPENCODE_SERVER_PASSWORD` is
  removed from their environment.
- **Secrets stay out of this repo.** It is public and auto-pushed. The gateway
  URL, key and password live in `~/.local/share/opencode/homelab/` (0700). Job
  directories are 0700 and their files 0600, because briefs and worker output can
  contain sensitive material.
- **The gateway key is scoped.** It can reach four models and nothing else, and
  it is revocable on its own in the LiteLLM admin UI.
- **Job ids are validated** before they are used as paths.

## Code Map

| Path | Purpose |
|------|---------|
| `.config/opencode/opencode.jsonc` | Providers, models, default agent |
| `.config/opencode/agents/coordinator.md` | Coordinator prompt and permissions |
| `.config/opencode/plugins/delegate.ts` | Job store, worker commands, completion notices, the five `delegate_*` tools |
| `../../bin/opencode-server` | LaunchAgent entry point: loads the password, runs `opencode serve` from the stable path |
| `../../bin/stable-exec` | Runs a Homebrew CLI from a fixed path so privacy grants survive upgrades |
| `../../launchagents/com.ashtonian.opencode.plist` | The always-on server |
| `../../lib_sh/opencode.sh` | `oc`, `ocweb` |
