# Agent MCP servers

## Overview

Claude Code and Codex load MCP servers per repository. A repository lists the
servers it needs in committed config, `.mcp.json` for Claude Code and
`.codex/config.toml` for Codex, and each entry runs `agent-mcp <server>
[claude|codex]`. The launcher, `stow/agent-mcp/.local/bin/agent-mcp`, defines
every server's binary, version and flags once, so repositories never carry
paths, hosts or credentials. OpenCode loads no MCP servers: its local model's
64K context is too small for their tool schemas.

| Where | Claude Code | Codex |
| --- | --- | --- |
| Every session | github (read-only), context7 (remote, user scope) | context7 (remote, `~/.codex/config.toml`) |
| karsto | serena, codebase-memory, playwright, postgres; typescript-lsp plugin | serena, codebase-memory, postgres |
| estavelle | serena, codebase-memory, playwright, postgres; typescript-lsp plugin | serena, codebase-memory, postgres |
| gox | serena, codebase-memory | serena, codebase-memory |
| home-ops, home-ops-private | kubernetes, terraform, grafana; pyright-lsp plugin | kubernetes, terraform, grafana |
| `/Volumes/E2TB/home` (homelab ops session) | kubernetes, terraform, grafana (Claude local scope) | — |

The gopls-lsp plugin stays enabled for every Claude Code session. It starts
gopls only in Go code.

## Config

| Setting | Where | Value | Description |
| --- | --- | --- | --- |
| `AGENT_MCP_HOME` | environment | `~/.claude/mcp` | Install root of the pinned servers (`node/`, `bin/`, launchers). |
| `AGENT_MCP_CONFIG` | environment | `~/.config/agent-mcp` | Holds `serena-claude-code.yml` (stow package `agent-mcp`). |
| serena | `agent-mcp` | `serena start-mcp-server --project-from-cwd --add-mode no-memories --enable-web-dashboard false --open-web-dashboard false --enable-gui-log-window false` | Serena 2.1.0 (`uv tool install -p 3.13 serena-agent==2.1.0`), REPL interface. No memories or onboarding, since they would duplicate AGENTS.md and CLAUDE.md. No dashboard, so there is no web server per session. |
| | Claude | `--context ~/.config/agent-mcp/serena-claude-code.yml` | Upstream's claude-code context without its ban on Claude's Read and Edit, so LSP diagnostics after edits keep working. |
| | Codex | `--context codex` | Upstream's Codex context. |
| | each Go repository | `.serena/project.yml` | Languages (`go`, plus `typescript` in karsto and estavelle), ignored paths and gopls's build (`ls_specific_settings.go.gopls_settings`): karsto and estavelle load their test build tags, gox builds with `GOOS=linux`. Without it Serena writes a per-clone default with no language servers. `.serena/.gitignore` ignores its cache and local files. |
| | `~/.serena/serena_config.yml` | `trusted_project_path_patterns` | The karsto, gox and estavelle clones. Serena ignores a project's `ls_specific_settings` unless its root matches. |
| codebase-memory | `agent-mcp` | `~/.local/libexec/codebase-memory-mcp/0.12.1/codebase-memory-mcp`; Codex adds `--tool-profile=analysis` | Code graph. Config (`codebase-memory-mcp config list`): `auto_index=true`, `auto_watch=true`, `ui_enabled=false`. Indexes in `~/.cache/codebase-memory-mcp`, one per clone. karsto's and gox's `.cbmignore` exclude non-code trees. The launcher turns off git's rename detection (`diff.renames=false`) and lazy fetching (`GIT_NO_LAZY_FETCH=1`) for it: the indexer reads history with `git log --name-only`, and with renames on, a partial clone (gox's are `blob:none`) fetches each missing blob from the remote. |
| playwright | `agent-mcp` | `@playwright/mcp` 0.0.83, `--browser chromium --headless --isolated --output-dir ~/.cache/playwright-mcp` | Needs Playwright's Chromium 1247 in `$PLAYWRIGHT_BROWSERS_PATH` (`node node_modules/playwright-core/cli.js install chromium` in `~/.claude/mcp/node`). |
| postgres | `agent-mcp` | `@bytebase/dbhub` 1.5.0 and its `pg` 8.23.1 driver; `agent-mcp postgres <harness> <databases>` reads `~/.claude/mcp/dbhub/<databases>.toml` | Read-only SQL against the repository's development databases, each on its own host port: karsto's compose PostgreSQL (`karsto`: `karsto_dev`, 5442) and estavelle's console (`estavelle`: `console_dev`, 5452). dbhub lists `pg` only as an optional dependency and, without it, starts but answers every query with `No connector found for DSN`. |
| kubernetes | `agent-mcp` | kubernetes-mcp-server v0.0.67 `--read-only --disable-destructive --disable-multi-cluster`, `~/.kube/mcp-homelab.yaml` | Single context, `admin@talos-homelab`. |
| terraform | `agent-mcp` | terraform-mcp-server v1.3.0 `stdio --toolsets=registry` | Public registry only. |
| pprof | `agent-mcp` | pprof-analyzer-mcp v0.3.1 | Reads profile files. No repository loads it: `compare_profiles` reports CPU time in bytes and `analyze_pprof` has no cumulative view. `go tool pprof` does both. |
| grafana | `agent-mcp` → `~/.claude/mcp/grafana.sh` | mcp-grafana v2.0.2 `-disable-write -disable-admin -usage-stats=disabled` | URL and token from keychain service `claude-mcp-grafana`; the token belongs to Grafana service account `claude-mcp` (Viewer). Claude gets search, datasource, prometheus, loki, alerting, dashboard, folder and pyroscope. Codex gets search, datasource, prometheus, loki and dashboard. |
| context7 | `~/.claude.json` (user), `~/.codex/config.toml` | `https://mcp.context7.com/mcp` | Claude's `headersHelper` (`~/.claude/mcp/context7-headers.sh`) sends an API key from keychain service `claude-mcp-context7`, account `api-key`, when one exists; until then it is anonymous. |
| Approvals | `~/.claude/settings.json` `enabledMcpjsonServers` | the eight server names above | Fleet sessions never stop at a project-server prompt. |
| Codex trust | `~/.codex/config.toml` `[projects."<clone>"]` | `trust_level = "trusted"` per clone | Codex reads a project's `.codex/config.toml` only for a trusted clone path (exact path, not a parent). A new clone asks once in the Codex TUI. |
| LSP plugins | `~/.claude/settings.json` (off) and each repository's `.claude/settings.json` (on) | typescript-lsp, pyright-lsp | Binaries `typescript-language-server` 6.0.2 (fallback TypeScript 6.0.3) and `pyright` 1.1.414 live in `~/.claude/mcp/node`, linked into `~/.local/bin`. |

## External Dependencies

- `~/.claude/mcp` with its pinned installs; the runbook there lists every version and the upgrade steps.
- `uv` (Serena), Go and gopls (`~/go/bin`), and fnm's default Node (Playwright, dbhub, the LSP servers).
- The keychain items `claude-mcp-grafana` (`url`, `token`) and, optionally, `claude-mcp-context7` (`api-key`).
- `~/.local/bin` on `PATH`: `~/.config/shell/env.sh` puts it there for shells, and the Codex and OpenCode LaunchAgents set it in their `PATH`.

## API / Interfaces

```sh
agent-mcp <server> [claude|codex]                    # exec the server on stdio; default harness claude
agent-mcp postgres <claude|codex> <databases>        # dbhub with ~/.claude/mcp/dbhub/<databases>.toml
```

Repository entries:

```json
// .mcp.json
{ "mcpServers": { "serena": { "command": "agent-mcp", "args": ["serena", "claude"] } } }
```

```toml
# .codex/config.toml
[mcp_servers.serena]
command = "agent-mcp"
args = ["serena", "codex"]
startup_timeout_sec = 60
```

Exit codes: 64 for an unknown server or harness, 69 when the server is not
installed (the message names it), 78 when Serena's Claude context file is missing.

## Build / Run / Test

```sh
python3 -m unittest tests.test_dotfiles.AgentMcp
cd <clone> && claude mcp list                                        # project servers connected?
cd <clone> && ~/.local/libexec/codex-stable/bin/codex mcp list       # needs a trusted clone
cd <clone> && claude -p "/context" --strict-mcp-config --mcp-config '{"mcpServers":{}}'   # baseline context, no API call
```

To add a server to a repository, add its name to that repository's
`.mcp.json` and `.codex/config.toml`. If it is a new server, add a case to
`agent-mcp`, install it under `~/.claude/mcp`, and add its name to
`enabledMcpjsonServers`.

## Operations

**Context cost**, measured with `/context` in karsto on 2026-10-20, before any message:

| Configuration | In context | Deferred MCP schemas |
| --- | --- | --- |
| No MCP servers | 165.6k | 0 |
| Previous global set (9 servers) | 168.7k | 55.6k |
| karsto set | 166.6k | 30.2k |

- Claude Code defers MCP tool schemas, so a server costs only its instructions
  until a tool is used. Codex sends every schema on every request. Per request
  that is serena 1.1k, codebase-memory 4.4k (analysis profile), postgres 0.4k,
  kubernetes 4.3k, terraform 2.5k and grafana 7.5k tokens.
- The karsto baseline is 152.7k of memory files, nearly all `.claude/rules/*.md`.
  The other repositories start at 21–38k.

**Failure modes:**

- *`<server>: … is not installed`* in `/mcp`: install it as the runbook in
  `~/.claude/mcp/README.md` describes.
- *Codex shows no project servers*: the clone is not trusted. Open Codex there
  once and accept, or add a `[projects."<path>"]` entry.
- *Serena reports no language server, or a new `.serena/project.yml` appears*:
  the clone predates the committed `.serena/project.yml`. Pull.
- *`go.work.sum` changes in a clone*: gopls (from Serena or the gopls-lsp
  plugin) records missing checksums. Commit or discard it like any other
  toolchain change.
- *postgres answers `SOURCE_UNREACHABLE`*: the repository's development
  database is down. karsto: `docker compose --profile dev up -d --wait postgres`
  in the clone; estavelle: `docker compose up -d --wait postgres` in
  `cloud/console`.
- *postgres answers `No connector found for DSN`*: the `pg` driver is missing
  from `~/.claude/mcp/node`. Run `npm install` there.
- *Grafana fails to connect*: the keychain token is missing or revoked. Create
  a new token for the `claude-mcp` service account (Grafana → Administration →
  Service accounts) and store it with
  `security add-generic-password -U -s claude-mcp-grafana -a token -w '<token>'`.

## Security

- Repository config holds only server names; the launcher and the keychain
  hold everything else.
- kubernetes is read-only with a single context. postgres runs dbhub's
  read-only SQL. grafana is a Viewer with write and admin tools disabled.
  terraform reads only the public registry.
- Serena executes Python in its REPL and codebase-memory reads the repository.
  Both run locally with the agent's own permissions, which already include a
  shell.
- Trusting a clone in Codex lets that repository's `.codex/config.toml` start
  local processes. Trust only your own repositories' clones.
- mcp-grafana's anonymous usage statistics are disabled; codebase-memory
  collects no telemetry.

## Code Map

| File | Purpose |
| --- | --- |
| [stow/agent-mcp/.local/bin/agent-mcp](../stow/agent-mcp/.local/bin/agent-mcp) | Launcher: server name → pinned binary and flags |
| [stow/agent-mcp/.config/agent-mcp/serena-claude-code.yml](../stow/agent-mcp/.config/agent-mcp/serena-claude-code.yml) | Serena context for Claude Code |
| [tests/test_dotfiles.py](../tests/test_dotfiles.py) | `AgentMcp` tests |
