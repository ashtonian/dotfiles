# Dotfiles Structure

This document explains the organization of the dotfiles repository.

## Directory Layout

```
~/.dotfiles/
├── stow/                        # GNU Stow packages
│   ├── zsh/                     # Zsh configuration
│   │   └── .zshrc               # Main zsh config
│   ├── git/                     # Git configuration
│   │   └── .gitconfig           # Git settings
│   ├── ssh/                     # SSH configuration template
│   │   └── .ssh/
│   │       └── config           # SSH config (no keys!)
│   └── atuin/                   # Atuin shell history
│       └── .config/
│           └── atuin/
│               └── config.toml  # Atuin settings
│
├── lib_sh/                      # Shell helper libraries
│   ├── echos.sh                 # Colorized output functions
│   ├── funcs.sh                 # General utility functions
│   ├── requirers.sh             # Package requirement helpers
│   └── claude.sh                # Claude CLI helpers
│
├── bin/                         # Executable scripts
│   └── dotfiles-install-launchagent
│
├── launchagents/                # macOS LaunchAgent definitions
│   └── com.dotfiles.sync.plist  # Auto-sync job (4 hours)
│
├── install.sh                   # Initial machine setup
├── config.sh                    # macOS system preferences
├── sync.sh                      # Git sync automation
├── Brewfile                     # Homebrew packages
├── README.md                    # Main documentation
└── STRUCTURE.md                 # This file
```

## Stow Packages

Each subdirectory in `stow/` is a "package" that mirrors the home directory structure. When you run `stow <package>`, it creates symlinks in your home directory.

### zsh

Contains `.zshrc` with:
- Oh-My-Zsh configuration
- Plugin management
- Path configuration
- History settings
- Custom aliases
- Atuin integration
- Claude CLI helpers

### git

Contains `.gitconfig` with:
- User settings
- Diff/merge tools
- Aliases
- URL shortcuts
- Color settings
- Include for `~/.gitconfig.local` (private settings)

### ssh

Contains SSH config template. Note: **Never put SSH keys in this repo!**

The config includes:
- Default settings for all hosts
- Include directive for `config.local` (machine-specific)

### atuin

Contains Atuin shell history configuration:
- Sync settings
- Search preferences
- Privacy filters

## Shell Libraries

### lib_sh/echos.sh

Colorized output functions for scripts:
- `ok` - Green success message
- `bot` - Bot-style message
- `running` - Yellow action indicator
- `warn` - Warning message
- `error` - Red error message

### lib_sh/funcs.sh

General utility functions:
- `server` - Start local HTTP server
- `mkd` - Make directory and cd into it
- `fs` - File/directory size
- `digs` - Simplified dig output
- `bootstrap_ssh_key` - SSH key generation
- `whodat` / `getem` - Port process management
- Various AWS, brew, and system helpers

### lib_sh/requirers.sh

Package management helpers:
- `require_brew` - Install brew package if missing
- `require_cask` - Install brew cask if missing
- `require_gem` - Install gem if missing
- `require_npm` - Install npm package if missing

### lib_sh/claude.sh

Claude Code CLI helpers for AI-assisted development:

**Session Management:**
- `cworktree` - Create git worktree + Claude session
- `ccontinue` - Continue last session
- `cresume` - Resume session picker

**Documentation:**
- `cdoc` - Generate CLAUDE.md
- `creadme` - Update all READMEs
- `carch` - Architecture documentation

**Code Quality:**
- `creview` - Review branch changes
- `cdebt` - Find technical debt
- `csecurity` - Security audit
- `cdeps` - Dependency audit

**Maintenance:**
- `clint` - Fix linting issues
- `cupdate` - Update dependencies
- `ctests` - Add missing tests
- `cpr` - Prepare pull request

## Scripts

### install.sh

Initial machine setup:
1. Configure sudo
2. Install Xcode CLI tools
3. Install Homebrew
4. Clone dotfiles repo
5. Configure git
6. Install Oh-My-Zsh
7. Run config.sh

### config.sh

macOS system preferences:
- Login window settings
- Finder preferences
- Dock configuration
- Keyboard/trackpad settings
- Security settings
- App-specific settings

### sync.sh

Automated git sync:
- Check connectivity
- Commit local changes
- Pull remote changes (with rebase)
- Push to origin
- Optional: run stow to update symlinks

Usage:
```sh
./sync.sh sync   # Git sync only
./sync.sh stow   # Update symlinks only
./sync.sh all    # Both
```

## LaunchAgents

### com.dotfiles.sync.plist

Runs `sync.sh` every 4 hours (14400 seconds) to:
- Auto-commit local changes
- Pull remote updates
- Push to origin

Install with:
```sh
~/.dotfiles/bin/dotfiles-install-launchagent
```

## Private Configuration

For sensitive settings, create a separate private repo at `~/.dotfiles-private/`:

```
~/.dotfiles-private/
├── stow/
│   ├── ssh/
│   │   └── .ssh/
│   │       └── config.local    # Host-specific SSH config
│   └── git-private/
│       └── .gitconfig.local    # Private git settings
└── install-private.sh
```

This repo should:
- Be private on GitHub
- Never contain actual secrets (use 1Password CLI, etc.)
- Be stowed after the public dotfiles

## Workflow

### Fresh Machine Setup

```sh
# 1. Run install script
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/ashtonian/dotfiles/master/install.sh)"

# 2. Stow packages
cd ~/.dotfiles/stow
stow -v -t ~ zsh git atuin ssh

# 3. Install LaunchAgent
~/.dotfiles/bin/dotfiles-install-launchagent

# 4. Setup Atuin
brew install atuin
atuin login -u <username>
atuin import zsh
```

### Making Changes

```sh
# 1. Edit files in ~/.dotfiles/
vim ~/.dotfiles/stow/zsh/.zshrc

# 2. Re-stow if needed
cd ~/.dotfiles/stow && stow -R -t ~ zsh

# 3. Commit changes (or let auto-sync handle it)
cd ~/.dotfiles
git add -A && git commit -m "Update zshrc"
git push
```

### Adding New Stow Package

```sh
# 1. Create package structure
mkdir -p ~/.dotfiles/stow/newapp/.config/newapp

# 2. Add config file
vim ~/.dotfiles/stow/newapp/.config/newapp/config

# 3. Stow it
cd ~/.dotfiles/stow
stow -v -t ~ newapp
```
