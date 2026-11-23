# Dotfiles structure

The [README](README.md) covers installation and interfaces.
[Operations](docs/OPERATIONS.md) covers configuration, restore, and troubleshooting.
This file maps the checked-in implementation.

## Directory layout

```text
~/.dotfiles/
├── install.sh               # Bootstrap: Go, engine build, machine manifest, apply, packages, LaunchAgents
├── config.sh                # Optional system/app preferences
├── sync.sh                  # Signed Git publication, engine build and apply, packages
├── go.mod                   # The feature engine's Go module
├── cmd/dotfiles/            # Engine command: init, apply, doctor, status, check, adopt
├── internal/manifest/       # Feature, profile and machine manifests from the repository and overlays; strict parsing and validation
├── internal/resolve/        # Defaults, profiles, machine overrides; requirements, conflicts, platforms, settings
├── internal/plan/           # Links, managed copies, generated outputs, stubs, LaunchAgents and app settings to install
├── internal/apply/          # Converge on a plan; unfold old stow links, retire, adopt, LaunchAgents, app settings, state, teardown, locking
├── internal/launchd/        # LaunchAgent plist reading; launchctl print, bootstrap and bootout in gui/<uid>
├── internal/prefs/          # App settings owned key by key: prefs files, and the Muxy and Claude Code stores
├── internal/atomicfile/     # Write beside, then rename into place
├── features/<id>/           # feature.toml, home/ (mirrors $HOME), fragments such as gitconfig, launchagents/, prefs files
├── profiles/                # Named feature sets: base, dev, desktop, server, work, studio
├── .github/workflows/ci.yml # Engine tests on macOS and Ubuntu; shell suite on macOS
├── bin/                     # Executable entry points
├── lib_sh/                  # Libraries sourced by Zsh or config.sh
├── tests/test_dotfiles.py   # Regression suite
├── docs/OPERATIONS.md       # Configuration and operations
├── docs/AGENT-MONITOR.md    # Local Claude Code / Codex agent dashboard
├── docs/AGENT-TELEMETRY.md  # Agent OpenTelemetry to the cluster (otel-agent)
├── docs/AGENT-MCP.md        # Per-repository MCP servers through agent-mcp
├── docs/SPOTLIGHT.md        # Spotlight privacy exclusions (macos.spotlight)
├── docs/PASSKEYS.md         # Passkey prompts off (browser.passkeys-off)
├── docs/KARABINER.md       # Mouse buttons through Karabiner-Elements (tool.karabiner)
├── docs/MUXY.md            # The other Macs as Muxy remote servers (tool.muxy)
├── Software.md              # Historical software notes
├── software_list.md         # Historical installed-package snapshot
├── chrome_extensions.md     # Browser inventory instructions
└── win10/                   # Legacy Windows package script

~/.sync/                    # Separate repos, outside the dotfiles repo
├── mackup/<LocalHostName>/  # Earlier app backups; sync no longer runs Mackup (rollout step 8)
└── colorls/                 # Theme checkout
```

The older `.zshrc.omz-backup` is retained as a historical reference. It is not
sourced by the modular Zsh configuration.

## Features

Each directory under `features/` is one feature; `home/` mirrors `$HOME`, and
`apply` links every file under a `link` entry on its own. `retire` lists where
the old stow package linked a file, so `apply` removes the link on a machine
where the feature is off. A `launch_agent` is a plist template under the
feature's `launchagents/`, installed into `~/Library/LaunchAgents` and loaded.

| Feature | Profiles | Platforms | Installs |
| ------- | -------- | --------- | -------- |
| `agents.agent-mcp` | dev | darwin, linux | `~/.config/agent-mcp`, `~/.local/bin/agent-mcp` |
| `agents.agent-monitor` | dev | darwin | LaunchAgents `com.ashtonian.agent-monitor` (after `agent-monitor install`), `com.ashtonian.agent-monitor-gate` (after `agent-monitor lan enable`) |
| `agents.claude` | dev | all | `~/.claude/CLAUDE.md` |
| `agents.claude.theme` | dev | all | copies `~/.claude/themes/dracula.json`; Claude Code setting `theme` |
| `agents.codex` | dev | darwin | LaunchAgent `com.ashtonian.codex-remote-control` (with the codex cask) |
| `agents.opencode` | desktop | all | `~/.config/opencode`; on macOS LaunchAgent `com.ashtonian.opencode` (after its local setup) |
| `agents.otel-agent` | desktop | darwin | `~/.config/otel-agent`; LaunchAgent `com.ashtonian.otel-agent` (after `otel-agent enroll`) |
| `backup.mackup.config` | desktop | darwin, linux | `~/.mackup.cfg` |
| `browser.passkeys-off` | desktop | darwin | `~/.local/share/browser-extensions/passkeys-off` (copy), `~/.local/bin/passkeys-off` |
| `brew.activity-trackers` | desktop | darwin | Brewfile: 1 brew, 1 cask, 2 vscode |
| `brew.apps` | desktop, work | darwin | Brewfile: 26 cask |
| `brew.base` | base | darwin, linux | Brewfile: 6 tap, 97 brew |
| `brew.desktop` | desktop | darwin | Brewfile: 1 tap, 1 brew, 7 cask (personal) |
| `brew.dev-apps` | dev | darwin | Brewfile: 12 cask |
| `brew.go-tools` | dev | darwin, linux | Brewfile: 13 go |
| `brew.macos` | base | darwin | Brewfile: 2 brew |
| `brew.mas` | desktop, work | darwin | Brewfile: 1 brew, 8 mas |
| `brew.mas.personal` | desktop | darwin | Brewfile: 3 mas |
| `brew.vscode` | dev | darwin | Brewfile: 52 vscode |
| `dotfiles.sync` | base | darwin | LaunchAgent `com.dotfiles.sync` |
| `dotfiles.update` | base | darwin | LaunchAgent `com.dotfiles.update` |
| `git` | base | darwin, linux | `~/.config/git`; stubs `~/.gitconfig` (an existing one is kept) |
| `git.keychain` | base | darwin | gitconfig fragment |
| `macos.disk-hygiene` | base | darwin | LaunchAgent `com.ashtonian.disk-hygiene` |
| `macos.spotlight` | base | darwin | `~/.config/spotlight`, `~/.local/bin/spotlight-exclusions` |
| `shell.env` | base | darwin, linux | `~/.config/shell`; stubs `~/.bashrc`, `~/.bash_profile` |
| `shell.zsh` | base | darwin, linux | `~/.config/zsh`; stubs `~/.zshenv`, `~/.zprofile`, `~/.zshrc`, `~/.zlogin` |
| `ssh` | base | darwin, linux | `~/.ssh/dotfiles.conf`; stubs `~/.ssh/config` (its Include before any `Host` or `Match`) |
| `tool.atuin` | base | all | `~/.config/atuin` |
| `tool.colorls` | base | darwin, linux | `~/.config/colorls` |
| `tool.gh` | base | all | copies `~/.config/gh/config.yml`; gitconfig fragment: gh as the credential helper for `github.com` and `gist.github.com` |
| `tool.go-cache-trim` | base | darwin | LaunchAgent `com.ashtonian.go-cache-trim` (with Homebrew's go) |
| `tool.gpg-agent` | base | darwin | LaunchAgent `com.ashtonian.gpg-agent` (with Homebrew's gnupg) |
| `tool.htop` | base | darwin, linux | copies `~/.config/htop/htoprc` |
| `tool.karabiner` | desktop | darwin | copies `~/.config/karabiner/karabiner.json`; Brewfile: 1 cask |
| `tool.mise` | base | all | `~/.config/mise/conf.d/dotfiles.toml` (the pinned Go and default Node); settings `go.toolchain` (`GOTOOLCHAIN`) and `mise.canary` |
| `tool.muxy` | desktop | darwin | `~/.local/bin/muxy` (held while `~/.local/bin/.muxy` exists), `~/.local/bin/muxy-reconcile`; LaunchAgent `com.ashtonian.muxy-reconcile` (with Muxy.app and Homebrew's python3); settings `muxy.reconcile` (`report` until a Mac sets `apply`) and `muxy.exclude_servers`; 8 Muxy settings ([muxy.toml](features/tool.muxy/muxy.toml)): Dracula dark and light themes, FiraCode Nerd Font in the terminal and composer, terminal font size 14, copy on select, agent sessions shown, tips hidden; Brewfile: 2 cask (Muxy, FiraCode Nerd Font), 1 brew |

Edit linked files in place. A feature's prefs file (`[provides.prefs]`) lists
the app settings it owns, one `key = value` line each; apply sets each one
through the app and leaves the rest of the app's settings to the machine. Add,
remove or move files, then run `dotfiles apply`; a file in the way is reported, never overwritten. See
[A file is in the way](README.md#a-file-is-in-the-way).

## Shell loading

| Stage | Behavior |
| ------- | ---------- |
| `env.sh` | Every shell and agent command: Homebrew variables, Go, pager, locale; PATH (system, Homebrew, toolchains, user bins), keeping in front what a parent added since; then the editor and the generated `env.sh` (feature fragments and exported settings); builtins only |
| `zshenv.zsh` | Every Zsh, through the `~/.zshenv` stub: sources `env.sh`; a marked Codex `zsh -c` (`AGENT_SHELL`) runs in bash 4+, or with bash-like globbing and word splitting |
| `zprofile.zsh` | Login shells, through `~/.zprofile`: re-apply `env.sh` after `/etc/zprofile`'s path_helper reorders PATH; OrbStack integration where installed |
| `zlogin.zsh` | Login shells, through `~/.zlogin`: a marked Codex `zsh -lc` hands off to bash here, after the other entry points and the lines installers appended to them |
| `zshrc.zsh` | Interactive shells, through `~/.zshrc`: classify real terminal vs zsh `-ic`; source the numbered modules, the generated `zshrc.zsh` fragments, then `~/.zshrc.local`; define CLI launchers and invoke optional greeting |
| `00-init.zsh` | Bootstrap Zinit, define `_dotfiles_cached_eval` (tool init scripts cached per binary release), set shell options |
| `20-history.zsh` | Shared history, 50,000-entry limits, duplicate/space handling |
| `30-plugins.zsh` | Theme, completions, compinit (one dump per zsh version under `$XDG_CACHE_HOME/zsh`; full security check once a day, `-C` otherwise); deferred autosuggestions, plugins and selected OMZ snippets; syntax highlighting last |
| `40-keybindings.zsh` | Emacs keys, navigation/history keys, then cached Atuin initialization when installed |
| `50-aliases.zsh` | Convenience aliases; command-replacing and safety aliases gated to real sessions; eza listings as `ll`/`la`/`lt`; git aliases re-applied after the OMZ git plugin |
| `60-functions.zsh` | Libraries, cached Helm completion, git-extras completion, cached zoxide (real sessions), direnv, mise activation (real sessions, uncached: it embeds the PATH) and gitstead |
| `70-greeting.zsh` | Define optional greeting; called after local overrides |

Zinit's wait plugins run after the first prompt, so `zsh -ic exit` does not
exercise every deferred plugin, and it is not a real session, so it skips zoxide,
mise activation and the command-replacing aliases. Zoxide initializes
synchronously in `60-functions.zsh` in real sessions; FZF, autosuggestions and
syntax highlighting are deferred. Atuin, when installed, initializes after the
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
| [rotate-log.sh](lib_sh/rotate-log.sh) | `rotate_log`: move an outgrown log aside and keep its newest archives (`sync.sh`, `dotfiles-update.sh`) |
| [launch-agent.sh](lib_sh/launch-agent.sh) | `start_launch_agent`: restart a loaded LaunchAgent, or have `dotfiles apply` install it once its setup step ran (`bin/otel-agent`, `bin/agent-monitor`) |
| [brew-root.sh](lib_sh/brew-root.sh) | `brew_root_available`, `brew_casks_needing_root`: which Homebrew steps a run without a terminal must leave for one (`sync.sh`, `dotfiles-update.sh`) |
| [machine-setting.sh](lib_sh/machine-setting.sh) | `machine_setting`: a setting's value as `dotfiles apply` generated it into `env.sh`, for scripts LaunchAgents run (`bin/disk-hygiene`, `dotfiles-update.sh`) |
| [private-names.sh](lib_sh/private-names.sh) | `private_names_found`: tracked lines that name something on an overlay's `denylist.txt` (`sync.sh`, `bin/check-private-names`) |
| [sync-lock.sh](lib_sh/sync-lock.sh) | `sync_lock_take`, `without_sync_lock`: the `logs/sync.flock` lock that makes sync and update runs exclusive, and runs a step without its descriptor (`sync.sh`, `dotfiles-update.sh`) |

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
| [bin/dotfiles-update.sh](bin/dotfiles-update.sh) | Weekly stages that each run and report on their own: Homebrew (update, upgrades retried item by item after a failed run, cleanup, advisory doctor), the Go pin on the canary, Zinit, full sync; all under the sync lock |
| [bin/dotfiles-agents](bin/dotfiles-agents) | Install or check the Claude Code managed-settings drop-in and Codex system config that run agent commands in bash |
| [bin/stable-exec](bin/stable-exec) | Refresh a verified Homebrew copy under `~/.local/libexec/<tool>-stable`, then execute it |
| [bin/codex-daemon](bin/codex-daemon) | Forward Codex arguments to `stable-exec codex` |
| [bin/opencode-server](bin/opencode-server) | Load local password, then call `stable-exec opencode serve` |
| [bin/agent-monitor](bin/agent-monitor) | Install the pinned agent dashboard and its hooks; `serve` runs it on loopback, `gate` its LAN gate |
| [bin/agent-monitor-gate.mjs](bin/agent-monitor-gate.mjs) | Token-checked LAN relay to the loopback dashboard; refuses hook routes |
| [features/agents.agent-mcp/home/.local/bin/agent-mcp](features/agents.agent-mcp/home/.local/bin/agent-mcp) | Start an MCP server by name with its pinned binary and flags, per harness (Claude Code, Codex) |
| [bin/otel-agent](bin/otel-agent) | Enroll this Mac with its own gateway token and install the pinned OpenTelemetry Collector (contrib); `serve` forwards agent telemetry to the cluster gateway through a disk queue; `converge` (run by sync), `status`, `ping` |
| [bin/go-cache-trim](bin/go-cache-trim) | Delete Go build cache entries unused for `GO_CACHE_TRIM_HOURS` (24); `--dry-run` reports only |
| [bin/disk-hygiene](bin/disk-hygiene) | Delete agent scratch unused for `DISK_HYGIENE_SCRATCH_DAYS` (7) and caches unused for `DISK_HYGIENE_CACHE_DAYS` (14), prune pnpm stores, cap LaunchAgent logs; `--dry-run` reports only |
| [bin/check-private-names](bin/check-private-names) | Fail when a tracked line names something an overlay keeps private (its `denylist.txt`); sync runs the same check before publishing |
| [features/macos.spotlight/home/.local/bin/spotlight-exclusions](features/macos.spotlight/home/.local/bin/spotlight-exclusions) | Add the folders in `~/.config/spotlight/exclusions` to Spotlight's Search Privacy list; `check` reports drift, `list`, `remove` |
| [features/browser.passkeys-off/home/.local/bin/passkeys-off](features/browser.passkeys-off/home/.local/bin/passkeys-off) | Write the Firefox passkey prefs into every profile's `user.js`; `check` reports each Firefox and Chromium profile and the by-hand 1Password and Passwords settings |
| [features/tool.muxy/home/.local/bin/muxy](features/tool.muxy/home/.local/bin/muxy) | Run the `muxy` inside the installed Muxy app (`DOTFILES_MUXY_APP`, else `~/Applications`, else `/Applications`); what Muxy on another Mac starts over SSH |
| [features/tool.muxy/home/.local/bin/muxy-reconcile](features/tool.muxy/home/.local/bin/muxy-reconcile) | Bring Muxy's `[[servers]]` in step with `~/.config/muxy/servers.d/*.toml`, leaving out this Mac; logs the change and writes nothing while `muxy.reconcile` is `report` (`--mode` for one run) |
| [bin/gpg-agent-supervisor](bin/gpg-agent-supervisor) | Start gpg-agent in the GUI login and replace any agent started elsewhere every `GPG_AGENT_SUPERVISOR_SECONDS` (10) |
| [bin/disable-aerials](bin/disable-aerials) | Rewrite the wallpaper store to a still desktop picture and the Floating Message screen saver, then restart WallpaperAgent; `--dry-run` reports only. `config.sh` runs it |

## Automation and data boundaries

| Label | Schedule / service | Logs |
| ------- | -------------------- | ------ |
| com.dotfiles.sync | Every 14,400 seconds and at load; runs `sync.sh` directly, not through a login shell, so the plist's PATH stands and Homebrew's bash is the job's one macOS privacy identity | `logs/sync.log`, `/tmp/dotfiles-sync.{out,err}` |
| com.dotfiles.update | Friday 09:00 local time; runs `dotfiles-update.sh` directly, as the sync agent does | `logs/update.log`, `/tmp/dotfiles-update.{out,err}` |
| com.ashtonian.codex-remote-control | Always on; default Unix socket; soft file limit 65,536 | `~/Library/Logs/CodexHomebrew/remote-control.{stdout,stderr}.log` |
| com.ashtonian.opencode | Always on; HTTP server; default `127.0.0.1:4096` | `~/Library/Logs/opencode/server.{stdout,stderr}.log` |
| com.ashtonian.agent-monitor | While its data link resolves; HTTP `127.0.0.1:4820` | `~/Library/Logs/agent-monitor/server.{stdout,stderr}.log` |
| com.ashtonian.agent-monitor-gate | After `agent-monitor lan enable`; HTTP `$AGENT_MONITOR_GATE_HOST:4821` (default `0.0.0.0`), token required | `~/Library/Logs/agent-monitor/gate.{stdout,stderr}.log` |
| com.ashtonian.otel-agent | Always on while enrolled (`otel-agent enroll`); OTLP `127.0.0.1:4318`/`4317` | `~/Library/Logs/otel-agent/collector.{stdout,stderr}.log` |
| com.ashtonian.go-cache-trim | Every hour and at load, when go is installed | `~/Library/Logs/go-cache-trim/trim.{log,err}` |
| com.ashtonian.disk-hygiene | Daily at 04:15, or at wake after a missed run | `~/Library/Logs/disk-hygiene/disk-hygiene.{log,err}` |
| com.ashtonian.gpg-agent | Always on in the GUI login, when gnupg is installed | `~/Library/Logs/gpg-agent/supervisor.log` |
| com.ashtonian.muxy-reconcile | At load, when `~/.config/muxy/servers.d` gains or loses a list, when apply rewrites `~/.config/dotfiles/generated`, and hourly, once Muxy.app and Homebrew's python3 exist | `~/Library/Logs/muxy-reconcile/muxy-reconcile.log`, `launchd.{out,err}` |

Templates are rendered copies, not links. `dotfiles apply` (every sync) writes a
changed template and reloads the job, except the job it runs in and a scheduled
job mid-run, which a later apply reloads; restarting a loaded job by hand keeps
its loaded plist settings. Reloading always-on services interrupts attached
sessions.

Sync holds `logs/sync.flock` using macOS lockf (the weekly update holds it for
its whole run too, so the two never overlap), syncs the overlays `machine.toml`
lists (the engine names their checkouts) and runs `dotfiles apply` right after
the dotfiles merge (refusing to merge an engine layout this machine cannot
install: no `machine.toml`, no Go, or an upstream engine that does not build here
or cannot plan the manifest), then installs the generated Brewfile's missing packages with
`--no-upgrade`. It does not run Mackup. Git sync is
separate for dotfiles, each listed overlay, and each immediate Git repo under `SYNC_DIR`. It signs
commits and merges, verifies outgoing signatures, and checks GitHub verification
after publishing. Auxiliary merges use `-X ours`, which prefers local conflicting
hunks rather than discarding all remote changes. Only dotfiles gets secret scans.

Authentication, app backups, worker job state, local overrides, generated plugin
dependencies, and logs belong outside tracked source. See
[Operations](docs/OPERATIONS.md) and the [OpenCode feature](features/agents.opencode/README.md)
for configuration and recovery.
