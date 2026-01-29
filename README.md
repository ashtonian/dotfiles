# dotfiles

macOS dotfiles & post install scripts - better defaults, productive OS, awesome tools.

This will initialize a freshly installed macOS instance with applications, CLI tools, shell configuration, and system settings.

## Quick Start

```sh
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/ashtonian/dotfiles/master/install.sh)"
```

## Features

- **GNU Stow** - Symlink-based dotfile management
- **Auto-sync** - Every 4 hours via LaunchAgent
- **Atuin** - Cross-device shell history sync (encrypted)
- **Claude CLI helpers** - AI-assisted development workflows

## Tool Overview

| Tool | Purpose |
|------|---------|
| [mas](https://github.com/mas-cli/mas) | Mac App Store CLI |
| [Homebrew](https://brew.sh/) | Package management |
| [GNU Stow](https://www.gnu.org/software/stow/) | Dotfile symlink management |
| [Atuin](https://atuin.sh/) | Shell history sync |
| [dockutil](https://github.com/kcrawford/dockutil) | Dock management |

## Structure

See [STRUCTURE.md](./STRUCTURE.md) for detailed directory layout.

```
~/.dotfiles/
├── stow/                    # Stow packages (symlinked to ~)
│   ├── zsh/                 # .zshrc
│   ├── git/                 # .gitconfig
│   ├── ssh/                 # SSH config template
│   └── atuin/               # Atuin config
├── lib_sh/                  # Shell helper functions
│   ├── claude.sh            # Claude CLI helpers
│   ├── funcs.sh             # General functions
│   └── echos.sh             # Colorized output
├── bin/                     # Scripts
├── launchagents/            # LaunchAgent plists
├── install.sh               # Initial setup script
├── config.sh                # macOS system configuration
├── sync.sh                  # Auto-sync script
└── Brewfile                 # Homebrew packages
```

## Usage

### Using Stow

After cloning, use stow to create symlinks:

```sh
cd ~/.dotfiles/stow
stow -v -t ~ zsh git atuin
```

To unlink a package:

```sh
stow -D -t ~ zsh
```

### Auto-Sync

Install the LaunchAgent for automatic syncing every 4 hours:

```sh
~/.dotfiles/bin/dotfiles-install-launchagent
```

Manual sync:

```sh
~/.dotfiles/sync.sh sync
```

### Shell History with Atuin

```sh
brew install atuin
atuin register -u <username> -e <email>  # or atuin login
atuin import zsh  # Import existing history
```

## Claude CLI Helpers

Comprehensive helper functions for AI-assisted development. Source `lib_sh/claude.sh` in your shell.

### Session Management

| Command | Description |
|---------|-------------|
| `c` | Start Claude |
| `cc` | Continue last session |
| `cr` | Resume session picker |
| `cw <branch>` | Create worktree + session |
| `co` | Use Opus model |

### Documentation

| Command | Description |
|---------|-------------|
| `cdoc` | Generate CLAUDE.md |
| `creadme` | Update all READMEs |
| `carch` | Architecture docs |
| `cpkgdoc` | Package-level docs |

### Code Quality

| Command | Description |
|---------|-------------|
| `creview [base]` | Review branch changes |
| `cdebt` | Find tech debt |
| `csecurity` | Security audit |
| `cdeps` | Dependency audit |

### Maintenance

| Command | Description |
|---------|-------------|
| `clint` | Fix linting issues |
| `cupdate` | Update dependencies |
| `ctests` | Add missing tests |
| `cpr [base]` | Prepare PR |

See `lib_sh/claude.sh` for the full list of commands.

## Post-Install Manual Steps

1. Sign in to Apple Account, Mail, Contacts, Calendar
2. Configure app syncs: VSCode, Alfred, Brave
3. Sign in to services: Spotify, Slack, Discord, Signal
4. Override Spotlight with Alfred
5. Configure 1Password browser integration

## Global Shortcuts

| App | Shortcut | Action |
|-----|----------|--------|
| 1Password | `Cmd+Shift+P` | Quick access |
| Alfred | `Cmd+Space` | Prompt |
| Alfred | `Cmd+Opt+C` | Clipboard history |
| Todoist | `Ctrl+Cmd+T` | Show/hide |
| Todoist | `Ctrl+Cmd+A` | Quick task |
| MonoSnap | `Cmd+Opt+5` | Capture area |

## Private Configuration

For sensitive configs, create `~/.dotfiles-private/` (private git repo):

```
~/.dotfiles-private/
├── stow/
│   ├── ssh/                 # Host-specific SSH config
│   └── git-private/         # Private git settings
└── install-private.sh
```

The main `.gitconfig` includes `~/.gitconfig.local` if it exists.

## Troubleshooting

### Stow conflicts

If stow reports conflicts, check for existing files:

```sh
ls -la ~/.zshrc  # Check if it's a symlink or real file
```

### LaunchAgent not running

```sh
launchctl list | grep dotfiles
launchctl load ~/Library/LaunchAgents/com.dotfiles.sync.plist
```

### Slow shell startup

Profile startup time:

```sh
time zsh -i -c exit
```

Disable cowsay (already disabled by default):

```sh
# In .zshrc, SHOW_COWSAY is false by default
export SHOW_COWSAY=true  # Only if you want it
```

## Resources

- [awesome-dotfiles](https://github.com/webpro/awesome-dotfiles)
- [dotfiles.github.io](https://dotfiles.github.io/)
- [Mathias Bynens dotfiles](https://github.com/mathiasbynens/dotfiles)
- [awesome-macos-command-line](https://github.com/herrbischoff/awesome-macos-command-line)
