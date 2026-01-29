# dotfiles

macOS dotfiles - fast shell, automated updates, AI-assisted workflows.

## Quick Start

```sh
# Install (fresh machine)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/ashtonian/dotfiles/master/install.sh)"

# Stow configurations
cd ~/.dotfiles/stow
stow -v -t ~ zsh git atuin ssh

# Install LaunchAgents (auto-sync & updates)
~/.dotfiles/bin/dotfiles-install-launchagents.sh
```

## Features

| Feature | Description |
|---------|-------------|
| **Zinit** | Blazing fast plugin manager with async loading (~0.3s startup) |
| **Dracula theme** | Clean prompt with git status indicators |
| **Auto-sync** | Dotfiles sync every 4 hours |
| **Weekly updates** | Brew + plugins update Fridays 9 AM |
| **Atuin** | Cross-device shell history (encrypted) |
| **Claude helpers** | AI-assisted development workflows |
| **Modular config** | Organized `~/.config/zsh/*.zsh` files |

## Shell Startup Time

| Before (OMZ) | After (Zinit) |
|--------------|---------------|
| ~2.0s | ~0.3s |

## Structure

```
~/.dotfiles/
├── stow/                        # Stow packages (symlinked to ~)
│   ├── zsh/
│   │   ├── .zshrc               # Entry point (sources modules)
│   │   └── .config/zsh/         # Modular config
│   │       ├── 00-init.zsh      # Zinit bootstrap
│   │       ├── 10-path.zsh      # PATH & environment
│   │       ├── 20-history.zsh   # History + Atuin
│   │       ├── 30-plugins.zsh   # Zinit plugins (turbo)
│   │       ├── 40-keybindings.zsh
│   │       ├── 50-aliases.zsh
│   │       └── 60-functions.zsh # External sources
│   ├── git/                     # .gitconfig
│   ├── ssh/                     # SSH config template
│   └── atuin/                   # Atuin config
├── lib_sh/                      # Shell function libraries
│   ├── claude.sh                # Claude CLI helpers
│   ├── funcs.sh                 # Utility functions
│   └── echos.sh                 # Colorized output
├── bin/                         # Scripts
│   ├── dotfiles-install-launchagents.sh
│   └── dotfiles-update.sh
├── launchagents/                # LaunchAgent plists
│   ├── com.dotfiles.sync.plist  # 4-hour sync
│   └── com.dotfiles.update.plist # Weekly updates
├── install.sh                   # Initial setup
├── config.sh                    # macOS preferences
└── sync.sh                      # Git sync script
```

## Usage

### Stow Packages

```sh
cd ~/.dotfiles/stow

# Link all
stow -v -t ~ zsh git atuin ssh

# Unlink
stow -D -t ~ zsh

# Relink (after changes)
stow -R -t ~ zsh
```

### LaunchAgents

```sh
# Install all agents
~/.dotfiles/bin/dotfiles-install-launchagents.sh

# Check status
~/.dotfiles/bin/dotfiles-install-launchagents.sh --status

# Manual triggers
launchctl start com.dotfiles.sync
launchctl start com.dotfiles.update

# Run directly
~/.dotfiles/sync.sh sync
~/.dotfiles/bin/dotfiles-update.sh --all

# Uninstall
~/.dotfiles/bin/dotfiles-install-launchagents.sh --uninstall
```

### Plugin Management (Zinit)

```sh
# Update all plugins
zinit update --all

# List loaded plugins
zinit list

# Clean unused plugins
zinit delete --clean
```

## Claude CLI Helpers

AI-assisted development workflows. See `lib_sh/claude.sh`.

| Command | Description |
|---------|-------------|
| `c` | Start Claude |
| `cc` | Continue last session |
| `cw <branch>` | Create worktree + Claude session (session ID = repo-branch) |
| `cdoc` | Generate CLAUDE.md |
| `creview` | Review branch changes |
| `csecurity` | Security audit |
| `cpr` | Prepare pull request |

## Automatic Updates

| Agent | Frequency | What it does |
|-------|-----------|--------------|
| `com.dotfiles.sync` | Every 4 hours | Git commit/pull/push dotfiles |
| `com.dotfiles.update` | Friday 9 AM | `brew upgrade`, `zinit update` |

Logs: `~/.dotfiles/logs/`

## Key Bindings

| Key | Action |
|-----|--------|
| `Ctrl+R` | History search (or Atuin) |
| `Ctrl+F` | Accept autosuggestion |
| `Option+Left/Right` | Word navigation |
| `Ctrl+A/E` | Line start/end |

## Customization

### Local overrides (not in git)

Create `~/.zshrc.local` for machine-specific config:

```sh
# ~/.zshrc.local
export SOME_API_KEY="..."
alias work="cd ~/work/projects"
```

### Private configs

Create `~/.dotfiles-private/` (private git repo) for sensitive settings.

## Troubleshooting

### Rebuild fast-alias-tips

```sh
# Requires Rust
brew install rust
cd ~/.local/share/zinit/plugins/zdharma-continuum---null
cargo build --release
```

### Slow startup

Profile with:

```sh
time zsh -i -c exit
zinit times  # Shows plugin load times
```

### Reset zinit

```sh
rm -rf ~/.local/share/zinit
# Restart shell - zinit will reinstall
```

## Resources

- [zinit documentation](https://github.com/zdharma-continuum/zinit)
- [Dracula theme](https://draculatheme.com/zsh)
- [Atuin](https://atuin.sh/)
