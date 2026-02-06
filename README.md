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
| **LaunchAgents** | Auto-sync every 4 hours, weekly updates |

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
├── Brewfile                    # Package list (auto-updated)
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
| Brewfile | brew bundle dump | Every sync |
| App configs | mackup backup | Every sync |

### Manual Sync Commands

```sh
# Full sync (recommended)
~/.dotfiles/sync.sh sync

# Individual operations
~/.dotfiles/sync.sh dotfiles  # Sync only dotfiles repo
~/.dotfiles/sync.sh repos     # Sync only ~/.sync/ repos
~/.dotfiles/sync.sh brewfile  # Dump Brewfile
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

# Uninstall
~/.dotfiles/bin/dotfiles-install-launchagents.sh --uninstall
```

## Shell Configuration

### Structure

```
~/.config/zsh/
├── 00-init.zsh        # Zinit bootstrap
├── 10-path.zsh        # PATH & environment
├── 20-history.zsh     # History + Atuin
├── 30-plugins.zsh     # Zinit plugins (turbo mode)
├── 40-keybindings.zsh # Key bindings
├── 50-aliases.zsh     # Aliases
└── 60-functions.zsh   # Functions & external sources
```

### Local Overrides

Create `~/.zshrc.local` for machine-specific config (not synced):

```sh
# ~/.zshrc.local
export WORK_API_KEY="..."
alias work="cd ~/work/projects"
```

## Claude CLI Helpers

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

## Mackup: App Config Backup

Mackup uses **copy mode** (not symlinks) - required for macOS Sonoma+.

```sh
# Backup app configs to ~/.sync/mackup
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
