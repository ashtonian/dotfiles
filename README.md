# dotfiles

Personal macOS configuration: modular Zsh, Stow-managed files, Homebrew tooling,
signed Git sync, app backups, and local coding-agent services.

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
less install.sh
less Brewfile
~/.dotfiles/install.sh
```

Review the installer and Brewfile first: this is a broad personal app collection,
including paid apps. The installer requests sudo, offers passwordless sudo,
installs shared packages, attempts every Stow package, and loads LaunchAgents.
The sync agent runs immediately at load. Package and Stow failures can be
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
| Homebrew, Stow, Python 3 | Packages, links, and AWS profile helpers |
| Gitleaks | Scanning dotfiles before automatic publication |
| GitHub CLI (gh), authenticated for each destination | Checking GitHub commit verification after a push |
| Mac App Store sign-in | Brewfile mas entries |
| Zinit and downloaded plugins | Interactive shell; first use downloads plugins |
| Codex / Claude Code, authenticated separately | Their respective launchers and workers |
| OpenCode and a configured gateway | Optional coordinator; see its package README |

Claude Code, gitstead, and gateway credentials need separate setup when those
integrations are used. Configure signing and GitHub authentication as described
under [Multi-Machine Setup](#multi-machine-setup) before relying on automatic sync.

## What Gets Installed

| Component | Description |
| ----------- | ------------- |
| **Homebrew** | Package manager + all packages from Brewfile |
| **Stow packages** | Every package in stow/, linked one file at a time; see [package inventory](STRUCTURE.md#stow-packages) |
| **Zinit** | Zsh plugin manager with deferred loading |
| **Mackup** | Installed, but not run by sync; see [Mackup](#mackup-app-config-backup) |
| **LaunchAgents** | Sync every 4 hours, Friday updates, Go build cache trim every 6 hours, eligible Codex/OpenCode/agent dashboard services |

## Architecture

```text
~/.dotfiles/                    # This repo - synced via git
├── stow/                       # Symlinked to ~ (dotfiles)
│   ├── zsh/                    # Shell config
│   ├── git/                    # Git config
│   ├── ssh/                    # SSH config
│   ├── atuin/                  # Shell history
│   └── mackup/                 # Mackup config
├── lib_sh/                     # Shell libraries
├── bin/                        # Scripts
├── launchagents/               # Automation plists
├── Brewfile                    # Curated package list
├── install.sh                  # Bootstrap script
├── config.sh                   # macOS preferences
└── sync.sh                     # Sync automation

~/.sync/                        # Auxiliary repos (synced separately)
├── mackup/                     # Earlier Mackup backups (git repo); sync no longer writes here
├── dracula-iterm/              # iTerm theme
├── colorls/                    # Colorls theme
└── alfred-dracula/             # Alfred theme
```

## Stow vs Mackup: When to Use What

| Use **Stow** for: | Use **Mackup** for: |
| ------------------- | --------------------- |
| Dotfiles (`.zshrc`, `.gitconfig`) | App preferences (plists) |
| Config dirs (`~/.config/zsh/`) | App data (`~/Library/...`) |
| Files you edit directly | Files apps manage |
| Text-based configs | Binary/plist configs |
| Cross-platform files | macOS-specific files |

**Examples:**

- `.zshrc` → Stow (you edit it, want version control)
- `.gitconfig` → Stow (you edit it)
- `com.googlecode.iterm2.plist` → Mackup (iTerm manages it)
- `Alfred.alfredpreferences` → Mackup (Alfred manages it)
- `~/.ssh/config` → Stow (you edit it)
- Terminal.app preferences → Mackup (macOS manages it)

**Rule of thumb:** If you open the file in an editor, use stow. If an app generates/modifies it, use mackup.
Never link an app-managed file under `~/Library` with stow: current macOS apps
refuse to read or save a symlinked preference file.

## Sync System

### What Gets Synced

| Location | Tool | Frequency |
| ---------- | ------ | ----------- |
| `~/.dotfiles` | git, tracked files only | Every 4 hours |
| `~/.sync/*` repos | git, tracked files only | Every 4 hours |
| Missing packages | brew bundle install `--no-upgrade` | Every sync |

Sync publishes edits to files the repository already tracks. A new file is
never published until you commit it yourself. A repository with a Git index
lock, or with a tracked edit newer than `SYNC_QUIET_MINUTES`, is left alone
until a later run, so half-finished work is not committed.

### Manual Sync Commands

```sh
# Full sync (recommended)
~/.dotfiles/sync.sh sync

# Individual operations
~/.dotfiles/sync.sh dotfiles  # Sync only dotfiles repo
~/.dotfiles/sync.sh repos     # Sync only ~/.sync/ repos
~/.dotfiles/sync.sh brewfile  # Install missing packages
~/.dotfiles/sync.sh stow      # Relink stow packages, one link per file
~/.dotfiles/sync.sh all       # Full sync + stow
~/.dotfiles/sync.sh check     # Lock availability without syncing
```

| Variable | Type | Default | Description |
| -------- | ---- | ------- | ----------- |
| `DOTFILES_DIR` | path | `~/.dotfiles` | Repository sync and stow operate on |
| `SYNC_DIR` | path | `~/.sync` | Directory whose Git repositories sync also publishes |
| `SYNC_QUIET_MINUTES` | minutes | `30` | A tracked edit newer than this makes sync skip the repository for this run |
| `XDG_STATE_HOME` | path | `~/.local/state` | `dotfiles/stow-hold/` under it keeps machine-local files that could not be moved home |

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

# OpenCode server only (local setup first, see stow/opencode/README.md)
~/.dotfiles/bin/dotfiles-install-launchagents.sh --opencode-only

# Agent dashboard only (after bin/agent-monitor install, see docs/AGENT-MONITOR.md)
~/.dotfiles/bin/dotfiles-install-launchagents.sh --agent-monitor-only

# Agent telemetry collector only (after bin/otel-agent install + configure, see docs/AGENT-TELEMETRY.md)
~/.dotfiles/bin/dotfiles-install-launchagents.sh --otel-agent-only

# Go build cache trim only (entries unused for 48 h, every 6 h; see docs/OPERATIONS.md)
~/.dotfiles/bin/dotfiles-install-launchagents.sh --go-cache-trim-only

# Uninstall
~/.dotfiles/bin/dotfiles-install-launchagents.sh --uninstall
```

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
pager, locale) are defined once in `~/.config/shell/env.sh` (stow package
`shell`). `~/.zshenv` sources it for every zsh, `~/.bashrc` for bash, and
Claude Code runs it before each Bash tool command (`CLAUDE_ENV_FILE`).

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

Interactive launchers from `stow/zsh/.zshrc`:

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

The `claudefleet` function forwards its arguments to `gitstead fleet open fleet`.
Install and configure [gitstead](https://github.com/ashtonian/gitstead) separately;
fleet definitions, agent profiles, and workspace paths live in the machine-local
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
[stow/opencode/README.md](stow/opencode/README.md).

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

This repo is designed to sync across multiple machines via LaunchAgent (every 4 hours). Each machine installs shared packages and backs up its own app configs without overwriting the other.

### After install on a new machine

1. **GPG signing** — create `~/.gitconfig.local` (see `stow/git/.gitconfig.local.example`):

   ```ini
   [commit]
       gpgsign = true
   [user]
       signingkey = YOUR_GPG_KEY_ID
   [gpg]
       program = /opt/homebrew/bin/gpg
   ```

2. **Machine-specific packages** — create `Brewfile.local` in `~/.dotfiles/` (gitignored):

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

- **Brewfile**: The shared `Brewfile` is curated manually. Sync installs missing packages with `--no-upgrade` and disables Homebrew auto-update for this operation. Weekly updates own upgrades. Use `Brewfile.local` for machine-specific packages.
- **Stow**: `sync.sh stow` links one file at a time (`--no-folding`), so no directory in `$HOME` becomes a link into the repository and a tool writing next to its config never writes into the repository. Gitignored files found inside a package (written there through an old directory link, such as gh's `hosts.yml`) are moved to their place in `$HOME` before the package is relinked. Untracked files that are not ignored are linked, listed in the log, and left for you to commit or remove.
- **Git sync**: Repositories with an unfinished merge, rebase, cherry-pick or bisect are skipped. Sync requires a configured Git identity and signing key, creates signed commits and merges, and verifies signatures locally. Source conflicts abort the merge; backup repositories retain their local-wins merge policy. Detached HEADs and branches without a matching `origin` tracking branch are skipped.
- **Publishing**: Gitleaks scans staged dotfiles and outgoing commits with redacted output; auxiliary repos are not scanned. Missing tools, scan failures, signing failures and merge failures stop publication. GitHub verification is checked after the push and does not undo publication on failure; bad_email requires correcting the signing identity.
- **Locking**: macOS `lockf` holds `logs/sync.flock` open during sync. The file remains after exit, and its presence does not mean the lock is held. Check availability with `sync.sh check`.
- **Failures**: Sync returns a nonzero status when an operation fails and records the failure in `logs/sync.log`.
- **Local overrides**: `.gitconfig.local`, `.zshrc.local`, `.ssh/config.local` are never tracked.

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

### Stow Conflicts

```sh
# Check what would happen
stow --dir="$HOME/.dotfiles/stow" --target="$HOME" --simulate --verbose zsh

# Relink every package after comparing and backing up conflicting files
~/.dotfiles/sync.sh stow
```

Stow does not overwrite conflicting regular files; a package with a conflict is
left exactly as it was, and the log names the file. Editing an existing linked
file does not require restowing. See [failure recovery](docs/OPERATIONS.md#shell-and-stow-troubleshooting).

### Sync Issues

```sh
# Check sync log
tail -50 ~/.dotfiles/logs/sync.log

# Run sync manually with verbose output
~/.dotfiles/sync.sh sync 2>&1
```


## Adding New Dotfiles

### Via Stow (recommended for configs you edit)

```sh
# 1. Create package directory
mkdir -p ~/.dotfiles/stow/myapp

# 2. Move existing config
mv ~/.myapprc ~/.dotfiles/stow/myapp/.myapprc

# 3. Link it, one link per file
~/.dotfiles/sync.sh stow

# 4. Commit it: sync never publishes new files
git -C ~/.dotfiles add stow/myapp && git -C ~/.dotfiles commit -S -m "myapp: add config"
```


## Package and AWS Helpers

The shared package manifest uses maintained `fastfetch` and `tlrc` clients in
place of removed or disabled clients, and uses Rustup for Rust toolchains. On a
fresh machine, initialize Rust with `rustup default stable`. Disabled or removed
casks are excluded from the shared manifest; existing applications are preserved.

The sync wrapper accepts `SYNC_DIR` for the backup root and `MACKUP_CONFIG_FILE`
for an alternate Mackup configuration (default `~/.mackup.cfg`).

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
- [Stow](https://www.gnu.org/software/stow/)
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
use temporary clones. Kernel-lock checks require macOS `lockf`; OpenCode worker
checks require Bun and the plugin dependencies installed by OpenCode.

Tests with missing platform/tool prerequisites are skipped. Run from the
repository root, and use `git diff --check` to check whitespace. Warm
`time zsh -ic exit` measures configuration loading; it does not exercise every
plugin deferred until after the first prompt.

Documentation lint requires Node.js/npm:

```sh
npx --yes markdownlint-cli2@0.23.3 \
  "*.md" "docs/*.md" stow/opencode/README.md \
  stow/opencode/.config/opencode/agents/coordinator.md win10/readme.md
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

OpenCode defaults to all interfaces with HTTP basic auth and no TLS. Configure
its bind address and network protection before enabling access from other
devices; see [OpenCode security](stow/opencode/README.md#security).
