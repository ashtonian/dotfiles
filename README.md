# dotfiles

Personal macOS configuration: modular Zsh, per-machine features installed by
the `dotfiles` engine, Homebrew tooling, signed Git sync, app backups, and local
coding-agent services.

See [Operations](docs/OPERATIONS.md) for configuration, signing, backup restore,
and failure recovery; [Structure](STRUCTURE.md) maps the implementation. The
[software notes](Software.md), [installed-software snapshot](software_list.md),
and [Windows files](win10/readme.md) are historical references.

## Quick Start

On a fresh Mac, run `xcode-select --install` and finish the Command Line Tools
installation before using Git to clone the repository.

```sh
git clone https://github.com/ashtonian/dotfiles.git ~/.dotfiles
cd ~/.dotfiles
less install.sh profiles/*.toml
~/.dotfiles/install.sh --profiles base,dev,desktop
```

Pick the [profiles](#profiles-and-machines) this machine runs; without
`--profiles` the installer asks. Review the profiles' package features first:
`desktop` is a broad personal app collection, including paid apps. The
installer requests sudo, offers passwordless sudo, installs Go, builds the
`dotfiles` engine, writes `~/.config/dotfiles/machine.toml`, applies the
enabled features, installs their packages, and loads LaunchAgents. The sync
agent runs immediately at load. Apply problems and package failures are
warnings, so inspect the output before relying on the completion message.

The final prompt offers `config.sh`, which applies broad system/app preferences,
installs packages again, and may restart apps or offer a reboot. Review it before
accepting; it is optional. Open a new terminal after installation.

## External Dependencies

The installer targets macOS and installs Xcode Command Line Tools and Homebrew
when needed. Keep the checkout at `~/.dotfiles`: the installer and service
templates assume that location. Codex/OpenCode background launchers currently
require Apple Silicon Homebrew paths under `/opt/homebrew`; other scripts also
recognize `/usr/local` Homebrew installations.

| Dependency | Required for |
| ------------ | -------------- |
| Git, GnuPG, usable signing key | Repository sync and signed commits |
| Homebrew, Go (version in `go.mod`), Python 3 | Packages, building the `dotfiles` engine, and AWS profile helpers |
| Gitleaks | Scanning dotfiles before automatic publication |
| GitHub CLI (gh), authenticated for each destination | Checking GitHub commit verification after a push |
| Mac App Store sign-in | The `brew.mas` feature's App Store apps |
| Zinit and downloaded plugins | Interactive shell; first use downloads plugins |
| Codex / Claude Code, authenticated separately | Their respective launchers and workers |
| OpenCode and a configured gateway | Optional coordinator; see its package README |

Claude Code, gitstead, and gateway credentials need separate setup when those
integrations are used. Configure signing and GitHub authentication as described
under [Multi-Machine Setup](#multi-machine-setup) before relying on automatic sync.

## What Gets Installed

| Component | Description |
| ----------- | ------------- |
| **Homebrew** | Package manager + the enabled package features' Brewfile entries |
| **Features** | What this machine's profiles enable, linked one file at a time; see [feature inventory](STRUCTURE.md#features) |
| **Zinit** | Zsh plugin manager with deferred loading |
| **Mackup** | Installed, but not run by sync; see [Mackup](#mackup-app-config-backup) |
| **LaunchAgents** | Sync every 4 hours, Friday updates, Go build cache trim every hour, eligible Codex/OpenCode/agent dashboard services |

## Architecture

```text
~/.dotfiles/                    # This repo - synced via git
├── features/<id>/              # One capability each: feature.toml, home/ (files linked into ~)
│   ├── shell.env/, shell.zsh/  # Shared environment; zsh modules and entry files
│   ├── git/, ssh/              # Shared git and ssh settings
│   ├── tool.*/, agents.*/      # Tool and coding-agent configs
│   └── brew.*/                 # Package lists, split by role
├── profiles/                   # Named feature sets: base, dev, desktop, server, work, studio
├── cmd/dotfiles/, internal/    # The feature engine (Go)
├── lib_sh/                     # Shell libraries
├── bin/                        # Scripts
├── launchagents/               # Automation plists
├── install.sh                  # Bootstrap script
├── config.sh                   # macOS preferences
└── sync.sh                     # Sync automation

~/.sync/                        # Auxiliary repos (synced separately)
├── mackup/                     # Earlier Mackup backups (git repo); sync no longer writes here
├── dracula-iterm/              # iTerm theme
├── colorls/                    # Colorls theme
└── alfred-dracula/             # Alfred theme
```

## Features vs Mackup: When to Use What

| Use a **feature** for: | Use **Mackup** for: |
| ------------------- | --------------------- |
| Dotfiles (`.zshrc`, `.gitconfig`) | App preferences (plists) |
| Config dirs (`~/.config/zsh/`) | App data (`~/Library/...`) |
| Files you edit directly | Files apps manage |
| Text-based configs | Binary/plist configs |
| Cross-platform files | macOS-specific files |

**Examples:**

- `~/.config/zsh/*.zsh` → feature `shell.zsh` (you edit it, want version control)
- `~/.config/git/config` → feature `git` (you edit it)
- `com.googlecode.iterm2.plist` → Mackup (iTerm manages it)
- `Alfred.alfredpreferences` → Mackup (Alfred manages it)
- `~/.ssh/dotfiles.conf` → feature `ssh` (you edit it)
- Terminal.app preferences → Mackup (macOS manages it)

**Rule of thumb:** If you open the file in an editor, make it part of a feature.
If an app generates or modifies it, use Mackup, or a feature's managed `copy`.
The engine never links a file under `~/Library` (current macOS apps refuse to
read or save a symlinked preference file); it installs a managed copy instead.

## Sync System

### What Gets Synced

| Location | Tool | Frequency |
| ---------- | ------ | ----------- |
| `~/.dotfiles` | git, tracked files only | Every 4 hours |
| `~/.sync/*` repos | git, tracked files only | Every 4 hours |
| This machine's features | `dotfiles apply`, right after the dotfiles merge | Every sync, once the checkout has `features/` |
| Missing packages | brew bundle install `--no-upgrade` | Every sync |

Sync publishes edits to files the repository already tracks. A new file is
never published until you commit it yourself. A repository with a Git index
lock, or with a tracked edit newer than `SYNC_QUIET_MINUTES`, is left alone
until a later run, so half-finished work is not committed.

Once the checkout uses the feature engine (it has `features/`), each sync runs
`dotfiles apply` in the same run as the merge, so a pull that moves tracked
files never leaves links to their old paths. Before it merges an upstream that
uses the engine, sync checks that this machine can install it: the machine has
`~/.config/dotfiles/machine.toml` (otherwise it logs the profiles upstream
offers), and the upstream's own engine builds with this machine's Go and plans
that manifest (`dotfiles check`). If any of that fails, sync neither merges nor
pushes, and the checkout stays as it is.

### Manual Sync Commands

```sh
# Full sync (recommended)
~/.dotfiles/sync.sh sync

# Individual operations
~/.dotfiles/sync.sh dotfiles  # Sync only dotfiles repo
~/.dotfiles/sync.sh repos     # Sync only ~/.sync/ repos
~/.dotfiles/sync.sh brewfile  # Install the enabled features' missing packages
~/.dotfiles/sync.sh build     # Rebuild ~/.local/bin/dotfiles if its sources changed
~/.dotfiles/sync.sh apply     # Build if needed, then dotfiles apply
~/.dotfiles/sync.sh all       # Same as sync
~/.dotfiles/sync.sh check     # Lock availability without syncing
```

| Variable | Type | Default | Description |
| -------- | ---- | ------- | ----------- |
| `DOTFILES_DIR` | path | `~/.dotfiles` | Repository sync and the engine operate on |
| `SYNC_DIR` | path | `~/.sync` | Directory whose Git repositories sync also publishes |
| `SYNC_QUIET_MINUTES` | minutes | `30` | A tracked edit newer than this makes sync skip the repository for this run |
| `DOTFILES_BIN` | path | `~/.local/bin/dotfiles` | The engine binary sync builds and runs |

Full sync commits and pushes eligible changes. A busy lock or unavailable network
is logged and skipped successfully; other operation failures return nonzero.
Check `logs/sync.log` for the outcome. Runtime overrides are listed in the
[configuration table](docs/OPERATIONS.md#configuration).

### LaunchAgents

```sh
# Install
~/.dotfiles/bin/dotfiles-install-launchagents.sh

# Status
~/.dotfiles/bin/dotfiles-install-launchagents.sh --status

# Manual trigger
launchctl start com.dotfiles.sync

# Codex app-server only (privacy setup: docs/OPERATIONS.md)
~/.dotfiles/bin/dotfiles-install-launchagents.sh --codex-only

# OpenCode server only (local setup first, see features/agents.opencode/README.md)
~/.dotfiles/bin/dotfiles-install-launchagents.sh --opencode-only

# Agent dashboard only (after bin/agent-monitor install, see docs/AGENT-MONITOR.md)
~/.dotfiles/bin/dotfiles-install-launchagents.sh --agent-monitor-only

# Agent telemetry collector only (after bin/otel-agent install + configure, see docs/AGENT-TELEMETRY.md)
~/.dotfiles/bin/dotfiles-install-launchagents.sh --otel-agent-only

# Go build cache trim only (entries unused for 24 h, every hour; see docs/OPERATIONS.md)
~/.dotfiles/bin/dotfiles-install-launchagents.sh --go-cache-trim-only

# Uninstall
~/.dotfiles/bin/dotfiles-install-launchagents.sh --uninstall
```

## Feature engine

`cmd/dotfiles` is the engine the [machine features design](docs/MACHINE-FEATURES.md)
describes: every capability is a feature under `features/<id>/`, profiles under
`profiles/` turn groups of them on, and the untracked
`~/.config/dotfiles/machine.toml` lists this machine's profiles and overrides.
Sync builds the binary into `~/.local/bin/dotfiles` and runs `dotfiles apply`
after every merge.

```sh
dotfiles init --profiles base,dev,desktop   # write this machine's manifest (once)
dotfiles status            # every feature, enabled or not, and which layer decided
dotfiles apply --dry-run   # what apply would change
dotfiles apply             # converge this machine
dotfiles doctor            # drift and conflicts, changing nothing; exit 1 if any
dotfiles check             # validate the manifests and plan this machine; reads nothing in $HOME
dotfiles adopt ~/.config/htop/htoprc   # make a managed copy's local edits the repository's version
```

`apply` links each tracked file into `$HOME` on its own (never a directory),
writes managed copies for files a tool rewrites (gh, htop and Taskwarrior
settings, and everything under `~/Library` on macOS), renders the generated
outputs in `~/.config/dotfiles/generated/` (the Brewfile, and the env, zsh, git
and ssh fragments), and creates one-line stubs for entry points installers
write to. It records what it installed in `~/.local/state/dotfiles/applied.json`,
so disabling a feature removes exactly what it added. It never overwrites a
file it did not create: a file in the way or a locally edited managed copy is
reported and left alone. `dotfiles adopt <path>` copies a managed copy's local
edits into its tracked file, which sync then publishes like any tracked edit. A
second run with nothing changed does nothing.
Without `machine.toml` it refuses to run, since no profile would apply and it
would remove everything the profiles install.

Old stow links are converted on the first apply: a directory stow had folded
into one link becomes a real directory, the untracked files tools wrote through
that link (such as gh's `hosts.yml`) move to their place in `$HOME`, and links
to paths no feature installs any more are removed. An untracked file still in
the retired `stow/` tree that `$HOME` links to moves home too; one nothing
links to is reported, never deleted, except Finder's `.DS_Store`, which is
removed.

### Profiles and machines

| Profile | Enables |
| ------- | ------- |
| `base` | Shared environment and zsh, git, ssh, gh/atuin/htop/colorls/mise settings, command-line packages |
| `dev` | Development apps, VS Code extensions, Go tools, Claude Code and MCP configs |
| `desktop` | Desktop and App Store apps for any desk (`brew.apps`, `brew.mas`) and personal ones (`brew.desktop`: games, personal finance, media, messaging, VPN; `brew.mas.personal`), the RescueTime and WakaTime trackers, OpenCode and the agent telemetry collector (both reach the home cluster), the Mackup config, neofetch and Taskwarrior settings |
| `server` | Nothing yet; power, remote login and firewall settings arrive with `config.sh`'s migration |
| `work` | Desktop and App Store apps for any desk (`brew.apps`, `brew.mas`, which needs an App Store sign-in); personal features come only from `desktop`, which the work machine does not use |
| `studio` | Host facts only: Playwright's browsers and the agent dashboard's data on the E2TB volume |

| Machine | Profiles |
| ------- | -------- |
| studio | `base, dev, desktop, studio` |
| Mac mini | `base, dev, desktop, server` |
| Work machine | `base, dev, work` |

Override one feature or setting for one machine in `machine.toml`:

```toml
profiles = ["base", "dev", "desktop", "server"]

[features]
disable = ["tool.taskwarrior"]

[settings]
"paths.playwright_browsers" = "~/Library/Caches/ms-playwright"
```

| Exit status | Meaning |
| ----------- | ------- |
| 0 | Done; for `doctor`, nothing to fix |
| 1 | Problems left for you (a file in the way, an edited copy, a missing setting), or for `doctor`, pending changes |
| 2 | The manifests are invalid or contradict each other (unknown key or feature, a requirement disabled on purpose, a conflict) |
| 64 | Usage |
| 70 | An I/O failure |

## Shell Configuration

### Structure

```text
~/.config/zsh/
├── 00-init.zsh        # Zinit bootstrap
├── 20-history.zsh     # History settings
├── 30-plugins.zsh     # Zinit plugins (turbo mode)
├── 40-keybindings.zsh # Key bindings + Atuin
├── 50-aliases.zsh     # Aliases
├── 60-functions.zsh   # Functions & external sources
└── 70-greeting.zsh    # Optional terminal greeting
```

PATH and the core environment (Homebrew, Go, language toolchains, editor,
pager, locale) are defined once in `~/.config/shell/env.sh` (feature
`shell.env`), followed by the enabled features' generated `env.sh`.
`~/.zshenv` sources it for every zsh, `~/.bash_profile` for login bash and
`~/.bashrc` for interactive bash, which covers
Claude Code's Bash tool. A nested shell keeps the PATH its parent built.

`~/.zshenv`, `~/.zprofile`, `~/.zshrc` and `~/.zlogin` are one-line local stubs
that source `zshenv.zsh`, `zprofile.zsh`, `zshrc.zsh` and `zlogin.zsh` in
`~/.config/zsh/`, so an installer that appends to `~/.zshrc` changes only this
machine. Local zsh modules go beside the shared ones with a number, such as
`~/.config/zsh/80-local.zsh`; `zshrc.zsh` loads only numbered modules.
`~/.gitconfig` is the machine's own file (an existing one is kept): shared
settings are in `~/.config/git/config`, which includes the generated fragments
and then `~/.gitconfig.local`, and `git config --global` writes to
`~/.gitconfig`, which git reads last. `~/.ssh/config` starts with
`Include dotfiles.conf`, which reads `~/.ssh/config.local` first and applies the
shared defaults last (`Match final`), so hosts installers append to
`~/.ssh/config` keep their own settings.

Real sessions differ from tool shells: `ls`, `du`, `ping` and `top` stay the
real commands everywhere (their replacements take different flags); eza
listings are `ll`, `la` and `lt`, ncdu is `dux`, and `reload` starts a fresh
shell (`exec zsh`). The git aliases (`gs`, `gc` and the rest) are applied again
after the OMZ git plugin loads, so `gc` stays `git commit`.

### Language versions (mise)

[mise](https://mise.jdx.dev) selects Go, Node, Python and other tool versions per
directory, from each project's own files: `toolchain` (or a patch-version `go`)
lines in `go.mod`/`go.work` and `.go-version`, `.nvmrc`/`.node-version`/`package.json`,
`.python-version`, plus `mise.toml` and `.tool-versions`. Shared defaults are in
`~/.config/mise/conf.d/dotfiles.toml` (feature `tool.mise`), which mise never
writes; `mise use -g` writes the machine-local `~/.config/mise/config.toml`.

```sh
mise install            # install the versions the current directory asks for
mise ls                 # what is selected here, and from which file
mise trust              # let a project's mise.toml set env vars and run tasks
```

- Real sessions activate mise at each prompt. Agents, LaunchAgents and GUI apps
  get mise's shims from `env.sh`, so they run the same versions.
- `GOTOOLCHAIN=local` keeps Go from downloading a different toolchain than the
  one mise selected. In a project whose `go.mod` names a Go you do not have
  yet, run `mise install`.
- Node outside any project is the LTS release (`mise install` once per machine).
- A project's `mise.toml` takes effect only after `mise trust`; set
  `trusted_config_paths` in `~/.config/mise/config.toml` to trust your own
  project roots, never everything.

### Local Overrides

Create `~/.zshrc.local` for machine-specific config (not synced):

```sh
# ~/.zshrc.local
export EDITOR=vim
alias work="cd ~/work/projects"
# Optional greeting (disabled by default for faster startup)
SHOW_COWSAY=true
```

## AI CLI Helpers

Interactive launchers from `~/.config/zsh/zshrc.zsh` (feature `shell.zsh`):

| Command | Model | Effort | Behavior |
| --------- | ------- | -------- | ---------- |
| `gptmore [args...]` | GPT-6.1 Sol | `xhigh` | Connects to the local remote-control server in the current directory (`-C "$PWD"`; without it the session runs in the server's `~`) and skips Codex approvals and sandboxing |
| `gptmax [args...]` | GPT-6 Astra | `max` | Same, with Astra |
| `claudemore [args...]` | `opus[1m]` | `xhigh` | Names the session, enables Remote Control, and skips Claude permission checks |
| `claudemax [args...]` | `fable[1m]` | `xhigh` | Same behavior with the Fable alias |

The model and effort defaults are listed above. The launchers forward additional
arguments. Both GPT launchers require the local Codex app
server to be running on its default Unix socket: the
`com.ashtonian.codex-remote-control` LaunchAgent (see LaunchAgents). Claude's model aliases track the
provider's model mapping; the Codex model strings are pinned in these wrappers.
Availability and supported effort levels depend on the authenticated provider.
See the [official OpenAI CLI reference](https://learn.chatgpt.com/docs/cli/reference)
for Codex flags. Use the underlying CLIs directly when bypassing permissions is
not appropriate.

The short launchers in `lib_sh/claude.sh` (`c`, `ccont` for `claude --continue`,
`cr`, `cf`, `co` and the rest) exist only in real terminal sessions, as do
zoxide's `cd`, its `z`/`j` aliases and `AUTO_CD`. Agent and tool shells keep the
plain commands, so a model-written `cd build` cannot jump to another tree and
`cc` stays the C compiler.

### Agent shells

Claude Code and Codex run model-written commands in bash, not zsh. Install the
system configs once per machine (they need sudo):

```sh
~/.dotfiles/bin/dotfiles-agents install   # write both files
~/.dotfiles/bin/dotfiles-agents check     # compare them with the repository; exit 1 on drift
```

| File | Effect |
| ---- | ------ |
| `/Library/Application Support/ClaudeCode/managed-settings.d/50-dotfiles.json` (`/etc/claude-code/...` on Linux) | Sets `CLAUDE_CODE_SHELL` to Homebrew bash. Managed settings outrank user settings and merge `env` per variable |
| `/etc/codex/config.toml` | Codex's system config layer: turns shell snapshots off and sets `AGENT_SHELL` in every command shell. Codex always starts the passwd login shell (`zsh -lc <command>`), and `~/.zshenv` hands a marked command to bash |

`dotfiles-agents` never overwrites a file it did not write (exit 73), and
`~/.codex/config.toml` can still override any Codex key for one user.

### Agent workspaces and fleets (gitstead)

The `claudefleet` function forwards its arguments to `gitstead fleet open fleet`,
and `gitstead cd <query>` jumps to a repository. The `brew.dev-apps` feature
installs [gitstead](https://github.com/ashtonian/gitstead); fleet definitions,
agent profiles, and workspace paths live in the machine-local
`~/.config/gitstead/config.yaml` and are not supplied by this repository. Claude
launchers disable claude.ai connectors in `wg-*` tmux sessions.

### Coordinator (OpenCode)

An always-on OpenCode server whose default agent runs on a self-hosted model and
delegates work to Claude Code and GPT Astra as background jobs, reporting back as
each finishes. Drive it from the terminal and a browser at once:

| Command | Description |
| --------- | ------------- |
| `oc` | Terminal UI on the running server, in the current directory |
| `ocweb` | Open the web UI (password copied to the clipboard; user `opencode`) |

Setup, configuration, the `delegate_*` tools, operations and security:
[features/agents.opencode/README.md](features/agents.opencode/README.md).

### Agent dashboard

A loopback web dashboard at <http://127.0.0.1:4820> for every Claude Code and
Codex session on this Mac: live cards, Kanban, tool timelines, transcripts, token
and cost analytics, and a Run page that starts sessions with the CLIs' own logins.
`~/.dotfiles/bin/agent-monitor install` sets it up, and `agent-monitor status`
checks it. Setup, configuration, operations and security:
[docs/AGENT-MONITOR.md](docs/AGENT-MONITOR.md).

### Agent MCP servers

Repositories list the MCP servers they need in committed `.mcp.json` (Claude
Code) and `.codex/config.toml` (Codex) files; every entry runs
`agent-mcp <server>`, which pins each server's binary and flags in one place.
Servers load only where they are used: Serena in the Go repositories, the code
graph in karsto, Kubernetes, Terraform and Grafana in home-ops. See
[docs/AGENT-MCP.md](docs/AGENT-MCP.md).

### Agent telemetry

Claude Code, Codex and OpenCode export OpenTelemetry metrics and events to a
local collector (`bin/otel-agent`, LaunchAgent `com.ashtonian.otel-agent`). It
deletes identities and tool content and forwards the rest to the cluster's OTLP
gateway, where the Coding Agents dashboard shows tokens, cost, tools and latency
per harness and repository. Setup and operations:
[docs/AGENT-TELEMETRY.md](docs/AGENT-TELEMETRY.md).

AI-assisted development workflows from `lib_sh/claude.sh`:

| Command | Description |
| --------- | ------------- |
| `cworktree <branch>` | Create worktree + Claude session |
| `cresume` | Resume Claude session |
| `ccontinue` | Continue last session |
| `copus` | Use Claude Opus model |
| `cdoc` | Generate `CLAUDE.md` |
| `creview` | Review branch changes |
| `csecurity` | Security audit |

## Multi-Machine Setup

This repo is designed to sync across multiple machines via LaunchAgent (every 4 hours). Each machine converges on the features its profiles enable and installs their missing packages; app settings backup returns with rollout step 8 (see [Mackup](#mackup-app-config-backup)).

A machine set up before the feature engine needs its `machine.toml` and a
current Go before the migration reaches it; see
[Moving an existing machine to the feature engine](docs/OPERATIONS.md#moving-an-existing-machine-to-the-feature-engine).

### After install on a new machine

1. **GPG signing** — create `~/.gitconfig.local` (see `features/git/gitconfig.local.example`):

   ```ini
   [commit]
       gpgsign = true
   [user]
       signingkey = YOUR_GPG_KEY_ID
   [gpg]
       program = /opt/homebrew/bin/gpg
   ```

2. **Machine-specific packages** — create `Brewfile.local` in `~/.dotfiles/` (gitignored; sync installs it after the generated Brewfile):

   ```ruby
   brew "some-package-only-on-this-machine"
   cask "some-app"
   ```

3. **Machine-specific shell config** — create `~/.zshrc.local`

4. **Machine-specific SSH hosts** — create `~/.ssh/config.local`

5. **Install LaunchAgents**: `~/.dotfiles/bin/dotfiles-install-launchagents.sh`

6. **Agent shells**: `~/.dotfiles/bin/dotfiles-agents install` (see [Agent shells](#agent-shells))

Also log in to gh with the scopes and storage in
[Git identity and signing](docs/OPERATIONS.md#git-identity-and-signing), and register the signing
public key and its email with GitHub. The shared Git config contains this repo
owner's personal identity; set intentional overrides for another user or work
repository.

### How multi-machine sync works

- **Packages**: The `brew.*` features hold the curated package lists, split by role; `dotfiles apply` writes the enabled ones into `~/.config/dotfiles/generated/Brewfile`. Sync installs missing packages with `--no-upgrade` and disables Homebrew auto-update for this operation. Weekly updates own upgrades. Use `Brewfile.local` for machine-specific packages.
- **Features**: Sync runs `dotfiles apply` right after the merge. Files are linked one at a time, so no directory in `$HOME` is a link into the repository and a tool writing next to its config never writes into the repository.
- **Git sync**: Repositories with an unfinished merge, rebase, cherry-pick or bisect are skipped. Sync requires a configured Git identity and signing key, creates signed commits and merges, and verifies signatures locally. Source conflicts abort the merge; backup repositories retain their local-wins merge policy. Detached HEADs and branches without a matching `origin` tracking branch are skipped.
- **Publishing**: Gitleaks scans staged dotfiles and outgoing commits with redacted output; auxiliary repos are not scanned. Missing tools, scan failures, signing failures and merge failures stop publication. GitHub verification is checked after the push and does not undo publication on failure; bad_email requires correcting the signing identity.
- **Locking**: macOS `lockf` holds `logs/sync.flock` open during sync. The file remains after exit, and its presence does not mean the lock is held. Check availability with `sync.sh check`.
- **Failures**: Sync returns a nonzero status when an operation fails and records the failure in `logs/sync.log`.
- **Local overrides**: `machine.toml`, the stubs, `.gitconfig.local`, `.zshrc.local`, `.ssh/config.local` and `Brewfile.local` are never tracked.

## Mackup: App Config Backup

Sync does not run Mackup. Its configuration here would copy credential files
(`.codex/auth.json`, `.kube/config`, `.npmrc` and others) into the backup
repository, so automatic backups stay off until they return behind the guards
described in [the Mackup design](docs/MACHINE-FEATURES.md#mackup).

Until then:

- Never run `mackup link install`, `mackup link` or `mackup link uninstall`.
  Link mode moves your files into the store and leaves symlinks behind, and
  current macOS apps refuse to read or save symlinked preferences.
- Never run `mackup restore` without naming one app. Restore deletes the
  original before copying, resets every restored file to mode 0600, and
  replaces a dotfiles link with a copy.
- Mackup older than 0.9.0 runs link mode for a plain `mackup backup`; check
  `mackup --version` first.

## Key Bindings

| Key | Action |
| ----- | -------- |
| `Ctrl+R` | History search (Atuin) |
| `Ctrl+F` | Accept autosuggestion |
| `Option+Left/Right` | Word navigation |
| `Ctrl+A/E` | Line start/end |

## Troubleshooting

### Slow Shell Startup

```sh
# Profile startup time
time zsh -i -c exit

# Check plugin load times
zinit times

# Inspect loaded plugins before repairing a specific cache
zinit list
```

### A file is in the way

```sh
dotfiles doctor            # lists each problem with its path
dotfiles apply --dry-run   # what apply would change
```

`apply` never overwrites a file it did not create; it reports it and carries
on with everything else. Compare the file with the tracked one the message
names, keep what you need, move it aside, and run `dotfiles apply`. Editing a
linked file needs no apply. A managed copy edited here (`edited here since
dotfiles last wrote it`) is kept with `dotfiles adopt <path>`, or replaced with
the repository's version by deleting it and running `dotfiles apply`. See
[feature engine troubleshooting](docs/OPERATIONS.md#feature-engine-troubleshooting).

### Sync Issues

```sh
# Check sync log
tail -50 ~/.dotfiles/logs/sync.log

# Run sync manually with verbose output
~/.dotfiles/sync.sh sync 2>&1
```

## Adding New Dotfiles

### As a feature (recommended for configs you edit)

```sh
# 1. Create the feature; home/ mirrors $HOME
mkdir -p ~/.dotfiles/features/tool.myapp/home/.config/myapp
mv ~/.config/myapp/config.toml ~/.dotfiles/features/tool.myapp/home/.config/myapp/
cat > ~/.dotfiles/features/tool.myapp/feature.toml <<'EOF'
id = "tool.myapp"
description = "myapp settings"
category = "tools"

[provides]
link = [".config/myapp"]   # each file under it, linked one by one
EOF

# 2. Enable it in a profile (or one machine's machine.toml), then link it
$EDITOR ~/.dotfiles/profiles/base.toml
dotfiles apply

# 3. Commit it: sync never publishes new files
git -C ~/.dotfiles add features/tool.myapp profiles && git -C ~/.dotfiles commit -S -m "myapp: add config"
```

Use `copy` instead of `link` for a file the tool rewrites, so its edits show as
drift instead of landing in the repository.

## Package and AWS Helpers

The shared package manifest uses maintained `fastfetch` and `tlrc` clients in
place of removed or disabled clients, and uses Rustup for Rust toolchains. On a
fresh machine, initialize Rust with `rustup default stable`. Disabled or removed
casks are excluded from the shared manifest; existing applications are preserved.

`assume_role` and `rename_aws_profile` respect `AWS_SHARED_CREDENTIALS_FILE` and
`AWS_CONFIG_FILE`. Profile updates validate the response first, lock cooperating
writers, and replace files with mode `600`. Credentials are passed over stdin,
never printed or placed in command arguments. Profile renames reject collisions
before changing either file.

`assume_role ROLE_ARN SESSION_NAME PROFILE_NAME [REGION]` writes the returned
session to the named profile; the region defaults to `us-east-1`.
`rename_aws_profile OLD NEW` renames exact profile sections. See
[the helper map](STRUCTURE.md#shell-libraries) for inventory exporters.

## Resources

- [Zinit](https://github.com/zdharma-continuum/zinit)
- [Mackup](https://github.com/lra/mackup)
- [Atuin](https://atuin.sh/)
- [Dracula Theme](https://draculatheme.com/)

## Validation

Run the local regression suite without updating packages, contacting model APIs,
changing real credentials, or committing/pushing repository changes:

```sh
python3 -B -m unittest discover -s tests -v
```

The suite uses temporary files and mock external commands. Git operation guards
use temporary clones. `RealFeatures` builds the engine with the installed Go and
applies the repository's own features to temporary homes. Engine unit tests:
`go test -race ./...`. Kernel-lock checks require macOS `lockf`; the agent
dashboard checks require Node.js; OpenCode worker checks require Bun and the
plugin dependencies OpenCode installs in `~/.config/opencode` (or a directory
holding `node_modules/@opencode-ai/plugin` named by
`DOTFILES_TEST_OPENCODE_DEPS`).

Tests with missing platform/tool prerequisites are skipped. Run from the
repository root, and use `git diff --check` to check whitespace. Warm
`time zsh -ic exit` measures configuration loading; it does not exercise every
plugin deferred until after the first prompt.

Documentation lint requires Node.js/npm:

```sh
npx --yes markdownlint-cli2@0.23.3 \
  "*.md" "docs/*.md" features/agents.opencode/README.md \
  features/agents.opencode/home/.config/opencode/agents/coordinator.md win10/readme.md
```

The [Markdown configuration](.markdownlint.json) permits wide command tables and
keyboard markup, and keeps table spacing consistent.

## Security

This repository is public and auto-pushed. Keep credentials, keys, private host
details, local overrides, and job output outside tracked source. Ignore rules and
secret scans cannot establish that every file is safe to publish. Review new
files and use private remotes for auxiliary backups. See
[sync recovery](docs/OPERATIONS.md#sync-failures) for signing, scans, conflicts, and
post-push verification failures.

OpenCode listens on loopback by default, with HTTP basic auth and no TLS.
`OPENCODE_HOSTNAME` opts in to another address; configure network protection
before enabling access from other devices; see
[OpenCode security](features/agents.opencode/README.md#security).
