# dotfiles

macOS dotfiles - fast shell, automated sync, AI-assisted workflows.

## Quick Start

```sh
# One-line install (fresh machine)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/ashtonian/dotfiles/master/install.sh)"
```

Or manually:

```sh
git clone https://github.com/ashtonian/dotfiles.git ~/.dotfiles
~/.dotfiles/install.sh
```

## What Gets Installed

| Component | Description |
|-----------|-------------|
| **Homebrew** | Package manager + all packages from Brewfile |
| **Stow packages** | Symlinked dotfiles (zsh, git, ssh, atuin, mackup) |
| **Zinit** | Fast zsh plugin manager (~0.3s startup vs ~2s with OMZ) |
| **Mackup** | App config backup (copy mode, not symlinks) |
| **LaunchAgents** | Auto-sync every 4 hours, weekly updates, the local Codex app-server |

## Architecture

```
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
|-------------------|---------------------|
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
|----------|------|-----------|
| `~/.dotfiles` | git | Every 4 hours |
| `~/.sync/mackup` | git | Every 4 hours |
| Other `~/.sync/*` repos | git | Every 4 hours |
| Missing packages | brew bundle install --no-upgrade | Every sync |
| App configs | mackup backup | Every sync |

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
```

### LaunchAgents

```sh
# Install
~/.dotfiles/bin/dotfiles-install-launchagents.sh

# Status
~/.dotfiles/bin/dotfiles-install-launchagents.sh --status

# Manual trigger
launchctl start com.dotfiles.sync

# Codex app-server only (then grant Full Disk Access once, see STRUCTURE.md)
~/.dotfiles/bin/dotfiles-install-launchagents.sh --codex-only

# OpenCode server only (local setup first, see stow/opencode/README.md)
~/.dotfiles/bin/dotfiles-install-launchagents.sh --opencode-only

# Uninstall
~/.dotfiles/bin/dotfiles-install-launchagents.sh --uninstall
```

## Shell Configuration

### Structure

```
~/.config/zsh/
├── 00-init.zsh        # Zinit bootstrap
├── 10-path.zsh        # PATH & environment
├── 20-history.zsh     # History settings
├── 30-plugins.zsh     # Zinit plugins (turbo mode)
├── 40-keybindings.zsh # Key bindings + Atuin
├── 50-aliases.zsh     # Aliases
├── 60-functions.zsh   # Functions & external sources
└── 70-greeting.zsh    # Optional terminal greeting
```

### Local Overrides

Create `~/.zshrc.local` for machine-specific config (not synced):

```sh
# ~/.zshrc.local
export WORK_API_KEY="..."
alias work="cd ~/work/projects"
# Optional greeting (disabled by default for faster startup)
SHOW_COWSAY=true
```

## AI CLI Helpers

Interactive launchers from `stow/zsh/.zshrc`:

| Command | Model | Effort | Behavior |
|---------|-------|--------|----------|
| `gptmore [args...]` | GPT-6.1 Sol | `xhigh` | Connects to the local remote-control server in the current directory (`-C "$PWD"`; without it the session runs in the server's `~`) and skips Codex approvals and sandboxing |
| `gptmax [args...]` | GPT-6 Astra | `max` (below `ultra`) | Same, with Astra |
| `claudemore [args...]` | Latest Opus via `opus[1m]` | `xhigh` (below `max`) | Names the session automatically and skips Claude permission checks |
| `claudemax [args...]` | Latest Fable via `fable[1m]` | `xhigh` (below `max`) | Names the session automatically and skips Claude permission checks |

The model and effort defaults are listed above. The launchers forward additional
arguments. Both GPT launchers require the local Codex app
server to be running on its default Unix socket: the
`com.ashtonian.codex-remote-control` LaunchAgent (see LaunchAgents). Claude's model aliases track the
latest model in each family for your provider; the Codex models are pinned to the
current choices. See the [Codex model guide](https://learn.chatgpt.com/docs/models)
and [Claude model configuration](https://code.claude.com/docs/en/model-config) for
provider-specific model availability.

### Agent workspaces and fleets (gitten)

[gitten](https://github.com/ashtonian/gitten) (formerly git-mgr) keeps the
workgroups as workspaces: `gox`, `estavelle` and `karsto` under `~/workgroups`,
four agents each, plus `home` and `projects`, shared folders four agents work in. Its config, `~/.config/gitten/config.yaml`, is machine-local
(`gitten setup` edits it in place) and defines one agent profile per launcher
above plus the local coordinator:

| Profile | Runs | Model |
|---------|------|-------|
| `claude` (default) | `claudemore` | Opus |
| `fable` | `claudemax` | Fable |
| `astra` | `gptmax` | GPT-6 Astra |
| `sol` | `gptmore` | GPT-6.1 Sol |
| `local` | `oc` | OpenCode coordinator on the local model |

| Command | Opens |
|---------|-------|
| `gitten fleet open all --agent astra` | Astra in every agent of all five workspaces (20), as Muxy sessions |
| `gitten fleet open all --agent local` | The coordinator in the same 20 places, as Muxy sessions |
| `claudefleet` | Fleet `fleet` (all three workspaces), claude, tmux `wg-fleet` as native iTerm panes |
| `claudefleet --agent astra --launcher iterm` | The same with Astra, as plain iTerm splits |
| `gitten ws open gox --agent astra --launcher iterm` | One workspace's four agents with Astra, in a new iTerm window |
| `gitten ws open karsto --agent local --launcher muxy` | One workspace's agents with the coordinator, as Muxy sessions (Existing Terminals) |
| `gitten ws run gox agent-2 --profile astra` | One agent, in the current terminal |
| `gitten ws status gox` / `gitten top` | Agents' states and copies / live view of everything |
| `gitten fleet stop fleet` | Ends every agent in the fleet |

Add `--fresh` to start sessions afresh and `--print` to see what a launcher would
do without doing it. A replica runs one profile at a time, so the `astra` and
`local` launches are alternatives, not layers
([gitten#6](https://github.com/ashtonian/gitten/issues/6)). The iTerm launcher needs macOS's Automation permission for
the terminal gitten runs in, which macOS asks for once.

### Coordinator (OpenCode)

An always-on OpenCode server whose default agent runs on a self-hosted model and
delegates work to Claude Code and GPT Astra as background jobs, reporting back as
each finishes. Drive it from the terminal and a browser at once:

| Command | Description |
|---------|-------------|
| `oc` | Terminal UI on the running server, in the current directory |
| `ocweb` | Open the web UI (password copied to the clipboard; user `opencode`) |

Setup, configuration, the `delegate_*` tools, operations and security:
[stow/opencode/README.md](stow/opencode/README.md).

AI-assisted development workflows from `lib_sh/claude.sh`:

| Command | Description |
|---------|-------------|
| `cworktree <branch>` | Create worktree + Claude session |
| `cresume` | Resume Claude session |
| `ccontinue` | Continue last session |
| `copus` | Use Claude Opus model |
| `cdoc` | Generate CLAUDE.md |
| `creview` | Review branch changes |
| `csecurity` | Security audit |

## Multi-Machine Setup

This repo is designed to sync across multiple machines via LaunchAgent (every 4 hours). Each machine installs shared packages and backs up its own app configs without overwriting the other.

### After install on a new machine:

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

### How multi-machine sync works

- **Brewfile**: The shared `Brewfile` is curated manually. Sync installs missing packages with `--no-upgrade` and disables Homebrew auto-update for this operation. Weekly updates own upgrades. Use `Brewfile.local` for machine-specific packages.
- **Mackup**: Each machine backs up to `~/.sync/mackup/<hostname>/` so configs don't collide.
- **Git sync**: Repositories with an unfinished merge, rebase, cherry-pick or bisect are skipped. Sync requires a configured Git identity and signing key, creates signed commits and merges, and verifies signatures locally. Source conflicts abort the merge; backup repositories retain their local-wins merge policy. Detached HEADs and branches without a matching `origin` tracking branch are skipped.
- **Publishing**: Gitleaks scans staged dotfiles and outgoing commits with redacted output. Missing tools, scan failures, signing failures and merge failures stop publication. GitHub pushes are checked with `gh` for verified signatures; `bad_email` requires correcting the signing identity.
- **Locking**: macOS `lockf` holds `logs/sync.flock` open during sync. The file remains after exit, and its presence does not mean the lock is held. Check availability with `sync.sh check`.
- **Failures**: Sync returns a nonzero status when an operation fails and records the failure in `logs/sync.log`.
- **Local overrides**: `.gitconfig.local`, `.zshrc.local`, `.ssh/config.local` are never tracked.

## Mackup: App Config Backup

Mackup uses **copy mode** (not symlinks) - required for macOS Sonoma+. Backups are isolated per hostname to prevent multi-machine overwrites.

```sh
# Automated backup goes to ~/.sync/mackup/$(hostname -s)/
# Manual commands use ~/.sync/mackup/ by default:
mackup backup

# Restore on new machine
mackup restore

# List supported apps
mackup list

# Show what would be backed up
mackup backup --dry-run
```

### Currently Backed Up

- bartender, bettertouchtool, beyond-compare
- contexts, dash, fork, hazel
- istat-menus, iterm2, keyboard-maestro
- quicklook, rectangle, sublime-text
- terminal, textexpander, tower, transmit

### Add More Apps

Edit `~/.mackup.cfg`:

```ini
[applications_to_sync]
# Add app names from: mackup list
my-new-app
```

## Key Bindings

| Key | Action |
|-----|--------|
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

# Reset zinit (will reinstall on next shell)
rm -rf ~/.local/share/zinit
```

### Stow Conflicts

```sh
# Check what would happen
stow -n -v -t ~ zsh

# Force restow (overwrites)
stow -R -t ~ zsh
```

### Sync Issues

```sh
# Check sync log
tail -50 ~/.dotfiles/logs/sync.log

# Run sync manually with verbose output
~/.dotfiles/sync.sh sync 2>&1
```

### Mackup Issues

```sh
# Verify copy mode is enabled
cat ~/.mackup.cfg | grep mode

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

# 2. Add to config
echo "myapp" >> ~/.mackup.cfg

# 3. Backup
mackup backup
```

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
