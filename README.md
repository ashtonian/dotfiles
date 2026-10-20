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
| Homebrew, Stow, Mackup, Python 3 | Packages, links, backups, and AWS profile helpers |
| Gitleaks | Scanning dotfiles before automatic publication |
| GitHub CLI (gh), authenticated for each destination | Checking GitHub commit verification after a push |
| Mac App Store sign-in | Brewfile mas entries |
| Zinit and downloaded plugins | Interactive shell; first use downloads plugins |
| Codex / Claude Code, authenticated separately | Their respective launchers and workers |
| OpenCode and a configured gateway | Optional coordinator; see its package README |

Claude Code, gitten, and gateway credentials need separate setup when those
integrations are used. Configure signing and GitHub authentication as described
under [Multi-Machine Setup](#multi-machine-setup) before relying on automatic sync.

## What Gets Installed

| Component | Description |
| ----------- | ------------- |
| **Homebrew** | Package manager + all packages from Brewfile |
| **Stow packages** | All 13 packages in stow/; see [package inventory](STRUCTURE.md#stow-packages) |
| **Zinit** | Zsh plugin manager with deferred loading |
| **Mackup** | App config backup (copy mode, not symlinks) |
| **LaunchAgents** | Sync every 4 hours, Friday updates, eligible Codex/OpenCode/agent dashboard services |

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
├── mackup/                     # App config backups (git repo)
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

## Sync System

### What Gets Synced

| Location | Tool | Frequency |
| ---------- | ------ | ----------- |
| `~/.dotfiles` | git | Every 4 hours |
| `~/.sync/mackup` | git | Every 4 hours |
| Other `~/.sync/*` repos | git | Every 4 hours |
| Missing packages | brew bundle install `--no-upgrade` | Every sync |
| App configs | `mackup backup` | Every sync |

### Manual Sync Commands

```sh
# Full sync (recommended)
~/.dotfiles/sync.sh sync

# Individual operations
~/.dotfiles/sync.sh dotfiles  # Sync only dotfiles repo
~/.dotfiles/sync.sh repos     # Sync only ~/.sync/ repos
~/.dotfiles/sync.sh brewfile  # Install missing packages
~/.dotfiles/sync.sh mackup    # Backup app configs
~/.dotfiles/sync.sh stow      # Relink stow packages
~/.dotfiles/sync.sh all       # Full sync + stow
~/.dotfiles/sync.sh check     # Lock availability without syncing
```

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

### Agent workspaces and fleets (gitten)

The `claudefleet` function forwards its arguments to `gitten fleet open fleet`.
Install and configure [gitten](https://github.com/ashtonian/gitten) separately;
fleet definitions, agent profiles, and workspace paths live in the machine-local
`~/.config/gitten/config.yaml` and are not supplied by this repository. Claude
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

Also run `gh auth login`, authenticate Git transport, and register the signing
public key and its email with GitHub. The shared Git config contains this repo
owner's personal identity; set intentional overrides for another user or work
repository. The installer initializes Mackup without a remote or initial commit.
Follow [private backup setup](docs/OPERATIONS.md#configure-a-private-backup-remote)
before expecting cross-machine app backup publication.

### How multi-machine sync works

- **Brewfile**: The shared `Brewfile` is curated manually. Sync installs missing packages with `--no-upgrade` and disables Homebrew auto-update for this operation. Weekly updates own upgrades. Use `Brewfile.local` for machine-specific packages.
- **Mackup**: Each machine backs up to `~/.sync/mackup/<hostname>/` so configs don't collide.
- **Git sync**: Repositories with an unfinished merge, rebase, cherry-pick or bisect are skipped. Sync requires a configured Git identity and signing key, creates signed commits and merges, and verifies signatures locally. Source conflicts abort the merge; backup repositories retain their local-wins merge policy. Detached HEADs and branches without a matching `origin` tracking branch are skipped.
- **Publishing**: Gitleaks scans staged dotfiles and outgoing commits with redacted output; auxiliary repos are not scanned. Missing tools, scan failures, signing failures and merge failures stop publication. GitHub verification is checked after the push and does not undo publication on failure; bad_email requires correcting the signing identity.
- **Locking**: macOS `lockf` holds `logs/sync.flock` open during sync. The file remains after exit, and its presence does not mean the lock is held. Check availability with `sync.sh check`.
- **Failures**: Sync returns a nonzero status when an operation fails and records the failure in `logs/sync.log`.
- **Local overrides**: `.gitconfig.local`, `.zshrc.local`, `.ssh/config.local` are never tracked.

## Mackup: App Config Backup

Mackup backup and restore copy files. Automated backups are isolated by
`scutil --get LocalHostName` (fallback `hostname -s`). No `mode = copy` setting is
needed; copy operations are the default.

```sh
# Back up into the host directory used by automation
~/.dotfiles/sync.sh mackup

# Inspect supported apps and preview the shared config's manual backup
mackup list
mackup backup --dry-run
```

Plain `mackup backup` and `mackup restore` use the unpartitioned `~/.sync/mackup/`
directory, which differs from automated host backups. Use the
[restore procedure](docs/OPERATIONS.md#restore-app-settings) to select a source
host explicitly.

The config includes all supported, detected apps except its
`[applications_to_ignore]` list. Review backup contents before publishing to a
private remote; app preferences can contain credentials.

### Add More Apps

Edit `~/.mackup.cfg`:

```ini
[applications_to_sync]
# An explicit allowlist replaces the default selection.
# Use app names from mackup list; retain appropriate exclusions.
my-new-app
```

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

# Restow after comparing and backing up conflicting files
stow --dir="$HOME/.dotfiles/stow" --target="$HOME" --restow zsh
```

Restow does not overwrite conflicting regular files. Editing an existing linked
file does not require restowing. See [failure recovery](docs/OPERATIONS.md#shell-and-stow-troubleshooting).

### Sync Issues

```sh
# Check sync log
tail -50 ~/.dotfiles/logs/sync.log

# Run sync manually with verbose output
~/.dotfiles/sync.sh sync 2>&1
```

### Mackup Issues

```sh
# Inspect storage and the app's managed paths
cat ~/.mackup.cfg
mackup show iterm2

# Test backup
mackup backup --dry-run
```

## Adding New Dotfiles

### Via Stow (recommended for configs you edit)

```sh
# 1. Create package directory
mkdir -p ~/.dotfiles/stow/myapp

# 2. Move existing config
mv ~/.myapprc ~/.dotfiles/stow/myapp/.myapprc

# 3. Stow it
cd ~/.dotfiles/stow && stow -v -t ~ myapp
```

### Via Mackup (for app-managed configs)

```sh
# 1. Check if app is supported
mackup list | grep myapp

# 2. Edit app selection/exclusions in the matching config section
vi ~/.mackup.cfg

# 3. Use the normal host-specific backup
~/.dotfiles/sync.sh mackup
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
