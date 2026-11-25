# Agent MCP servers

## Overview

Claude Code, Codex and OpenCode have a global read-only GitHub MCP for repositories, issues, pull requests and Actions. Claude Code and Codex also load servers per repository. A repository lists the
servers it needs in committed config, `.mcp.json` for Claude Code and
`.codex/config.toml` for Codex, and each entry runs `agent-mcp <server>
[claude|codex]`. The launcher, `features/agents.agent-mcp/home/.local/bin/agent-mcp`, defines
every server's binary, version and flags once, so repositories never carry
paths, hosts or credentials. OpenCode loads GitHub globally through its managed user configuration.

| Where | Claude Code | Codex |
| --- | --- | --- |
| Every session | github (read-only), context7 (remote, user scope) | github (read-only), context7 (remote, `~/.codex/config.toml`) |
| Go applications with a database and a web console | serena, codebase-memory, playwright, postgres; typescript-lsp plugin | serena, codebase-memory, postgres |
| Go libraries and engines | serena, codebase-memory | serena, codebase-memory |
| Infrastructure repositories (Kubernetes, Terraform) | kubernetes, terraform, grafana; pyright-lsp plugin | kubernetes, terraform, grafana |
| The homelab operations session's directory | kubernetes, terraform, grafana (Claude local scope) | — |

Which repositories are which, with their databases and ports, is in each
context's overlay (`docs/AGENT-MCP.md` there); see the README's
[Overlays](../README.md#overlays).

The gopls-lsp plugin stays enabled for every Claude Code session. It starts
gopls only in Go code.

## Config

| Setting | Where | Value | Description |
| --- | --- | --- | --- |
| `AGENT_MCP_HOME` | environment | `~/.claude/mcp` | Install root of the pinned servers (`node/`, `bin/`, launchers). |
| `AGENT_MCP_CONFIG` | environment | `~/.config/agent-mcp` | Holds `serena-claude-code.yml` (feature `agents.agent-mcp`). |
| serena | `agent-mcp` | `serena start-mcp-server --project-from-cwd --add-mode no-memories --enable-web-dashboard false --open-web-dashboard false --enable-gui-log-window false` | Serena 2.1.0 (`uv tool install -p 3.13 serena-agent==2.1.0`), REPL interface. No memories or onboarding, since they would duplicate AGENTS.md and CLAUDE.md. No dashboard, so there is no web server per session. |
| | Claude | `--context ~/.config/agent-mcp/serena-claude-code.yml` | Upstream's claude-code context without its ban on Claude's Read and Edit, so LSP diagnostics after edits keep working. |
| | Codex | `--context codex` | Upstream's Codex context. |
| | each Go repository | `.serena/project.yml` | Languages (`go`, plus `typescript` where the repository has a web console), ignored paths and gopls's build (`ls_specific_settings.go.gopls_settings`): the repository's test build tags, or `GOOS=linux` for a Linux-only engine. Without it Serena writes a per-clone default with no language servers. `.serena/.gitignore` ignores its cache and local files. |
| | `~/.serena/serena_config.yml` | `trusted_project_path_patterns` | The clones of the Go repositories that enable Serena. Serena ignores a project's `ls_specific_settings` unless its root matches. |
| codebase-memory | `agent-mcp` | `~/.local/libexec/codebase-memory-mcp/0.12.1/codebase-memory-mcp`; Codex adds `--tool-profile=analysis` | Code graph. Config (`codebase-memory-mcp config list`): `auto_index=true`, `auto_watch=true`, `ui_enabled=false`. Indexes in `~/.cache/codebase-memory-mcp`, one per clone. A repository's `.cbmignore` excludes its non-code trees. The launcher turns off git's rename detection (`diff.renames=false`) and lazy fetching (`GIT_NO_LAZY_FETCH=1`) for it: the indexer reads history with `git log --name-only`, and with renames on, a partial (`blob:none`) clone fetches each missing blob from the remote. |
| playwright | `agent-mcp` | `@playwright/mcp` 0.0.83, `--browser chromium --headless --isolated --output-dir ~/.cache/playwright-mcp` | Needs Playwright's Chromium 1247 in `$PLAYWRIGHT_BROWSERS_PATH` (`node node_modules/playwright-core/cli.js install chromium` in `~/.claude/mcp/node`). |
| postgres | `agent-mcp` | `@bytebase/dbhub` 1.5.0 and its `pg` 8.23.1 driver; `agent-mcp postgres <harness> <databases>` reads `~/.claude/mcp/dbhub/<databases>.toml` | Read-only SQL against the repository's development databases, each on its own host port; the overlay's docs list each repository's config name, database and port. dbhub lists `pg` only as an optional dependency and, without it, starts but answers every query with `No connector found for DSN`. |
| kubernetes | `agent-mcp` | kubernetes-mcp-server v0.0.67 `--read-only --disable-destructive --disable-multi-cluster`, `~/.kube/mcp-homelab.yaml` | Single context, `admin@talos-homelab`. |
| terraform | `agent-mcp` | terraform-mcp-server v1.3.0 `stdio --toolsets=registry` | Public registry only. |
| pprof | `agent-mcp` | pprof-analyzer-mcp v0.3.1 | Reads profile files. No repository loads it: `compare_profiles` reports CPU time in bytes and `analyze_pprof` has no cumulative view. `go tool pprof` does both. |
| grafana | `agent-mcp` → `~/.claude/mcp/grafana.sh` | mcp-grafana v2.0.2 `-disable-write -disable-admin -usage-stats=disabled` | URL and token from keychain service `claude-mcp-grafana`; the token belongs to Grafana service account `claude-mcp` (Viewer). Claude gets search, datasource, prometheus, loki, alerting, dashboard, folder and pyroscope. Codex gets search, datasource, prometheus, loki and dashboard. |
| github | Claude Code user scope | GitHub’s hosted MCP at `https://api.githubcopilot.com/mcp/` | The header helper reads the active github.com credential from `gh` at connection time and selects the read-only default and Actions toolsets. |
| github | Codex user scope and OpenCode global config | `agent-mcp github` | Runs Homebrew’s official `github-mcp-server` on stdio with the same toolsets and read-only mode. Only the server child receives the credential. |
| context7 | `~/.claude.json` (user), `~/.codex/config.toml` | `https://mcp.context7.com/mcp` | Claude's `headersHelper` (`~/.claude/mcp/context7-headers.sh`) sends an API key from keychain service `claude-mcp-context7`, account `api-key`, when one exists; until then it is anonymous. |
| Approvals | `~/.claude/settings.json` `enabledMcpjsonServers` | the eight server names above | Fleet sessions never stop at a project-server prompt. |
| Codex trust | `~/.codex/config.toml` `[projects."<clone>"]` | `trust_level = "trusted"` per clone | Codex reads a project's `.codex/config.toml` only for a trusted clone path (exact path, not a parent). A new clone asks once in the Codex TUI. |
| LSP plugins | `~/.claude/settings.json` (off) and each repository's `.claude/settings.json` (on) | typescript-lsp, pyright-lsp | Binaries `typescript-language-server` 6.0.2 (fallback TypeScript 6.0.3) and `pyright` 1.1.414 live in `~/.claude/mcp/node`, linked into `~/.local/bin`. |

## External Dependencies

- `~/.claude/mcp` with its pinned installs; the runbook there lists every version and the upgrade steps. The credential helpers in it, `github-headers.sh` and `context7-headers.sh` (`headersHelper` scripts named in `~/.claude.json`) and `grafana.sh`, are links into this feature; the installs stay untracked.
- An active github.com login in `gh` on each workstation. Run `gh auth login --hostname github.com` if needed. The desktop client can access a macOS login keychain that an SSH shell cannot.
- `uv` (Serena), Go and gopls (`~/go/bin`), and mise's default Node, through its shims (Playwright, dbhub, the LSP servers).
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
./sync.sh github-mcp                 # register installed clients in their user configs
claude mcp get github
codex mcp get github
opencode mcp list
python3 -m unittest tests.test_dotfiles.AgentMcp
cd <clone> && claude mcp list                                        # project servers connected?
cd <clone> && ~/.local/libexec/codex-stable/bin/codex mcp list       # needs a trusted clone
cd <clone> && claude -p "/context" --strict-mcp-config --mcp-config '{"mcpServers":{}}'   # baseline context, no API call
```

A full sync registers GitHub with the installed Claude and Codex CLIs after package installation. Registration preserves other servers and reports an existing custom entry named `github`. Open a fresh client session to load the configuration.

To add a server to a repository, add its name to that repository's
`.mcp.json` and `.codex/config.toml`. If it is a new server, add a case to
`agent-mcp`, install it under `~/.claude/mcp`, and add its name to
`enabledMcpjsonServers`.

## Operations

**Context cost**, measured with `/context` on 2026-10-20 in an application repository with about 150k of synced rules, before any message:

| Configuration | In context | Deferred MCP schemas |
| --- | --- | --- |
| No MCP servers | 165.6k | 0 |
| Previous global set (9 servers) | 168.7k | 55.6k |
| That repository's set | 166.6k | 30.2k |

- Claude Code defers MCP tool schemas, so a server costs only its instructions
  until a tool is used. Codex sends every schema on every request. Per request
  that is serena 1.1k, codebase-memory 4.4k (analysis profile), postgres 0.4k,
  kubernetes 4.3k, terraform 2.5k and grafana 7.5k tokens.
- That repository's baseline is 152.7k of memory files, nearly all
  `.claude/rules/*.md`. The other repositories start at 21–38k.

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
  database is down. Start it with the repository's compose file
  (`docker compose up -d --wait postgres`, with the profile and directory it
  needs; the overlay's docs name them).
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
| [features/agents.agent-mcp/home/.local/bin/agent-mcp](../features/agents.agent-mcp/home/.local/bin/agent-mcp) | Launcher: server name → pinned binary and flags |
| [features/agents.agent-mcp/home/.config/agent-mcp/serena-claude-code.yml](../features/agents.agent-mcp/home/.config/agent-mcp/serena-claude-code.yml) | Serena context for Claude Code |
| [features/agents.agent-mcp/home/.claude/mcp/github-headers.sh](../features/agents.agent-mcp/home/.claude/mcp/github-headers.sh) | `headersHelper`: the GitHub server's `Authorization` header from `gh auth token` |
| [features/agents.agent-mcp/home/.claude/mcp/context7-headers.sh](../features/agents.agent-mcp/home/.claude/mcp/context7-headers.sh) | `headersHelper`: Context7's API key from keychain service `claude-mcp-context7`, or no header |
| [features/agents.agent-mcp/home/.claude/mcp/grafana.sh](../features/agents.agent-mcp/home/.claude/mcp/grafana.sh) | Starts `bin/mcp-grafana` beside it with the URL and token from keychain service `claude-mcp-grafana` |
| [tests/test_dotfiles.py](../tests/test_dotfiles.py) | `AgentMcp` tests |
