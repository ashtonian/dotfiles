# Dotfiles structure

The [README](README.md) covers installation and interfaces.
[Operations](docs/OPERATIONS.md) covers configuration, restore, and troubleshooting.
This file maps the checked-in implementation.

## Directory layout

```text
~/.dotfiles/
├── Brewfile                 # Shared packages and editor extensions
├── install.sh               # Bootstrap; default checkout and backup locations
├── config.sh                # Optional system/app preferences
├── sync.sh                  # Packages, backups, signed Git publication
├── bin/                     # Executable entry points
├── launchagents/            # Templates copied to ~/Library/LaunchAgents
├── lib_sh/                  # Libraries sourced by Zsh or config.sh
├── stow/                    # Packages whose contents map into ~
├── tests/test_dotfiles.py   # Regression suite
├── docs/OPERATIONS.md       # Configuration and operations
├── docs/AGENT-MONITOR.md    # Local Claude Code / Codex agent dashboard
├── docs/AGENT-TELEMETRY.md  # Agent OpenTelemetry to the cluster (otel-agent)
├── docs/AGENT-MCP.md        # Per-repository MCP servers through agent-mcp
├── Software.md              # Historical software notes
├── software_list.md         # Historical installed-package snapshot
├── chrome_extensions.md     # Browser inventory instructions
└── win10/                   # Legacy Windows package script

~/.sync/                    # Separate repos, outside the dotfiles repo
├── mackup/<LocalHostName>/  # App backups partitioned by source host
├── dracula-iterm/           # Theme checkout
├── colorls/                 # Theme checkout
└── alfred-dracula/          # Theme checkout
```

The older `.zshrc.omz-backup` is retained as a historical reference. It is not
sourced by the modular Zsh configuration.

## Stow packages

Every immediate directory in stow/ is attempted by `install.sh` and `sync.sh stow`.
Stow's default ignore rules exclude package README files.

| Package | Linked files / purpose |
| --------- | ------------------------ |
| atuin | `.config/atuin/config.toml`; history UI |
| claude | .claude/`CLAUDE.md`; shared Claude instructions |
| colorls | `.config/colorls/dark_colors.yaml`; palette |
| gh | `.config/gh/config.yml`; preferences; authentication stays local |
| git | `.gitconfig`, `.gitconfig.local.example`, `.config/git/ignore` |
| htop | `.config/htop/htoprc` |
| mackup | `.mackup.cfg`; filesystem storage and app exclusions |
| neofetch | `.config/neofetch/config.conf`; legacy config, not used by Fastfetch |
| opencode | `.config/opencode/opencode.jsonc`, coordinator agent, delegate plugin |
| shell | `.config/shell/env.sh` (POSIX environment for every shell and agent), `.bashrc` |
| ssh | .ssh/config; OrbStack include, private local include, shared defaults |
| taskwarrior | `.taskrc` |
| zsh | `.zshenv`, `.zprofile`, `.zshrc`, `.config/zsh/*.zsh` |

Edit linked files in place; restow when adding, removing, or repairing links.
Existing regular files can conflict. See the [Stow commands](README.md#stow-conflicts)
before moving or adopting files.

## Shell loading

| Stage | Behavior |
| ------- | ---------- |
| `env.sh` | Every shell and agent command: PATH (system, Homebrew, toolchains, user bins), Homebrew variables, Go, editor, pager, locale; builtins only |
| `.zshenv` | Every Zsh: sources `env.sh`; bash-like globbing and word splitting for Codex command shells (`AGENT_SHELL`) |
| `.zprofile` | Login shells: re-apply `env.sh` after `/etc/zprofile`'s path_helper reorders PATH; optional OrbStack integration |
| `.zshrc` | Interactive shells: classify real terminal vs zsh `-ic`; source sorted modules, then `~/.zshrc.local`; define CLI launchers and invoke optional greeting |
| `00-init.zsh` | Bootstrap Zinit and annexes, set shell options |
| `20-history.zsh` | Shared history, 50,000-entry limits, duplicate/space handling |
| `30-plugins.zsh` | Theme, highlighting, autosuggestions, completions, compinit; deferred plugins and selected OMZ snippets |
| `40-keybindings.zsh` | Emacs keys, navigation/history keys, then Atuin initialization when installed |
| `50-aliases.zsh` | Convenience aliases; command-replacing and safety aliases gated to real sessions |
| `60-functions.zsh` | Libraries, cached Helm completion, git-extras completion, zoxide, direnv, fnm |
| `70-greeting.zsh` | Define optional greeting; called after local overrides |

Zinit's wait plugins run after the first prompt, so `zsh -ic exit` does not
exercise every deferred plugin. Zoxide initializes synchronously in
`60-functions.zsh`; FZF is deferred. Atuin, when installed, initializes after the
base keybindings and sets `FZF_CTRL_R_COMMAND=''` so FZF keeps its `Ctrl+R` binding.
`SHOW_COWSAY=true` enables the greeting only in a real terminal with cowsay,
fortune, and lolcat installed.

Plugin setup prunes dangling completion links and source-less compiled OMZ
snippet caches. The weekly updater fast-forwards Zinit core, then runs
`zinit update --all --quiet`.

## Shell libraries

| Library | Interfaces |
| --------- | ------------ |
| [echos.sh](lib_sh/echos.sh) | ok, bot, running, warn, error, color variables |
| [funcs.sh](lib_sh/funcs.sh) | `gitnr`, `mkd`, `fs`, `server`, `digs`, `whoisport`, `whodat`, `getem`, SSH/GPG helpers, AWS profiles, software exporters, `install_brewfiles` |
| [requirers.sh](lib_sh/requirers.sh) | Package requirements used by `config.sh` |
| [claude.sh](lib_sh/claude.sh) | Session helpers and prompt wrappers for docs, review, tests, maintenance, and PR preparation |
| [iterm2.sh](lib_sh/iterm2.sh) | Terminal titles, badges, Claude/iTerm helpers |
| [opencode.sh](lib_sh/opencode.sh) | `oc` attaches in $PWD; `ocweb` opens the UI and copies its password |

Exporters write to stdout unless given `-o` FILE:

```sh
vscode_list_md -o /tmp/vscode-extensions.md
brew_list_md --casks -o /tmp/brew-packages.md
mas_list_md -o /tmp/app-store-apps.md
chrome_list_ext_md --browser chrome -o /tmp/chrome-extensions.md
```

`vscode_extensions_list` with no arguments writes `vscode_extensions_list.md` in
the current directory. Browser export reads only the Default profile; pass
`--browser` explicitly (the implementation defaults to Brave). Package exports
include installed dependencies and are snapshots, not installation manifests.
Review output before publishing.

`assume_role ROLE_ARN SESSION_NAME PROFILE_NAME [REGION]` obtains an AWS session
and passes JSON over stdin to `bin/aws-profile`. The default region is us-east-1.
`rename_aws_profile OLD NEW` renames exact sections in the AWS config and
credentials files, rejecting destination collisions. Updates validate input,
lock cooperating writers, replace each file atomically, and set mode 600.
The pair of files is not one atomic filesystem transaction. These operations
respect `AWS_SHARED_CREDENTIALS_FILE` and `AWS_CONFIG_FILE`.

## Executables

| Script | Responsibility |
| -------- | ---------------- |
| [bin/aws-profile](bin/aws-profile) | assume PROFILE REGION reads credential JSON on stdin; rename OLD NEW renames sections |
| [bin/dotfiles-install-launchagents.sh](bin/dotfiles-install-launchagents.sh) | Copy templates, substitute $HOME, load/unload jobs, show status |
| [bin/dotfiles-update.sh](bin/dotfiles-update.sh) | Update Homebrew and Zinit, invoke full sync |
| [bin/stable-exec](bin/stable-exec) | Refresh a verified Homebrew copy under `~/.local/libexec/<tool>-stable`, then execute it |
| [bin/codex-daemon](bin/codex-daemon) | Forward Codex arguments to `stable-exec codex` |
| [bin/opencode-server](bin/opencode-server) | Load local password, then call `stable-exec opencode serve` |
| [bin/agent-monitor](bin/agent-monitor) | Install the pinned agent dashboard and its hooks; `serve` runs it on loopback, `gate` its LAN gate |
| [bin/agent-monitor-gate.mjs](bin/agent-monitor-gate.mjs) | Token-checked LAN relay to the loopback dashboard; refuses hook routes |
| [stow/agent-mcp/.local/bin/agent-mcp](stow/agent-mcp/.local/bin/agent-mcp) | Start an MCP server by name with its pinned binary and flags, per harness (Claude Code, Codex) |
| [bin/otel-agent](bin/otel-agent) | Install the pinned OpenTelemetry Collector; `serve` forwards agent telemetry to the cluster gateway; `status`, `ping` |

## Automation and data boundaries

| Label | Schedule / service | Logs |
| ------- | -------------------- | ------ |
| com.dotfiles.sync | Every 14,400 seconds and at load | `logs/sync.log`, `/tmp/dotfiles-sync.{out,err}` |
| com.dotfiles.update | Friday 09:00 local time | `logs/update.log`, `/tmp/dotfiles-update.{out,err}` |
| com.ashtonian.codex-remote-control | Always on; default Unix socket; soft file limit 65,536 | `~/Library/Logs/CodexHomebrew/remote-control.{stdout,stderr}.log` |
| com.ashtonian.opencode | Always on; HTTP server; default `0.0.0.0:4096` | `~/Library/Logs/opencode/server.{stdout,stderr}.log` |
| com.ashtonian.agent-monitor | While its data link resolves; HTTP `127.0.0.1:4820` | `~/Library/Logs/agent-monitor/server.{stdout,stderr}.log` |
| com.ashtonian.agent-monitor-gate | After `agent-monitor lan enable`; HTTP `0.0.0.0:4821`, token required | `~/Library/Logs/agent-monitor/gate.{stdout,stderr}.log` |
| com.ashtonian.otel-agent | Always on after `otel-agent configure`; OTLP `127.0.0.1:4318`/`4317` | `~/Library/Logs/otel-agent/collector.{stdout,stderr}.log` |

Templates are copied, not linked. Reinstall the affected agent to apply a
template change; restarting a loaded job keeps its loaded plist settings.
Reloading always-on services interrupts attached sessions.

Sync holds `logs/sync.flock` using macOS lockf, installs missing packages with
`--no-upgrade`, and gives Mackup a temporary host-specific config. Git sync is
separate for dotfiles and each immediate Git repo under `SYNC_DIR`. It signs
commits and merges, verifies outgoing signatures, and checks GitHub verification
after publishing. Auxiliary merges use `-X ours`, which prefers local conflicting
hunks rather than discarding all remote changes. Only dotfiles gets secret scans.

Authentication, app backups, worker job state, local overrides, generated plugin
dependencies, and logs belong outside tracked source. See
[Operations](docs/OPERATIONS.md) and the [OpenCode package](stow/opencode/README.md)
for configuration and recovery.
