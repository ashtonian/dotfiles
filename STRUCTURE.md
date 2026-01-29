# Dotfiles Structure

Complete directory layout and explanation of the zinit-based dotfiles setup.

## Directory Layout

```
~/.dotfiles/
├── stow/                              # GNU Stow packages
│   ├── zsh/                           # Zsh configuration
│   │   ├── .zshrc                     # Entry point (minimal, sources modules)
│   │   └── .config/zsh/               # Modular configuration
│   │       ├── 00-init.zsh            # Zinit bootstrap & core options
│   │       ├── 10-path.zsh            # PATH & environment variables
│   │       ├── 20-history.zsh         # History settings & Atuin
│   │       ├── 30-plugins.zsh         # Zinit plugin definitions (turbo)
│   │       ├── 40-keybindings.zsh     # Key bindings
│   │       ├── 50-aliases.zsh         # Aliases
│   │       └── 60-functions.zsh       # External function sources
│   ├── git/
│   │   └── .gitconfig                 # Git settings (includes .local)
│   ├── ssh/
│   │   └── .ssh/config                # SSH config template
│   └── atuin/
│       └── .config/atuin/config.toml  # Atuin shell history config
│
├── lib_sh/                            # Shell function libraries
│   ├── echos.sh                       # Colorized output (ok, bot, running, etc.)
│   ├── funcs.sh                       # Utility functions (server, mkd, etc.)
│   ├── requirers.sh                   # Package requirement helpers
│   └── claude.sh                      # Claude CLI helper functions
│
├── bin/                               # Executable scripts
│   ├── dotfiles-install-launchagents.sh  # LaunchAgent installer
│   └── dotfiles-update.sh             # Weekly update script
│
├── launchagents/                      # macOS LaunchAgent definitions
│   ├── com.dotfiles.sync.plist        # Dotfiles sync (4 hours)
│   └── com.dotfiles.update.plist      # System updates (Friday 9 AM)
│
├── install.sh                         # Initial machine setup
├── config.sh                          # macOS system preferences
├── sync.sh                            # Git sync automation
├── Brewfile                           # Homebrew packages
├── README.md                          # Main documentation
└── STRUCTURE.md                       # This file
```

## Zsh Configuration Modules

### 00-init.zsh - Zinit Bootstrap

- Auto-installs zinit if missing
- Loads zinit annexes for extended features
- Sets core zsh options (AUTO_CD, CORRECT, etc.)

### 10-path.zsh - Environment

- Homebrew initialization
- Go, Ruby, Python, Java paths
- User bin directories
- Environment variables (EDITOR, LANG, etc.)

### 20-history.zsh - History & Atuin

- History file settings (50k entries)
- History options (dedup, share, ignore space)
- Atuin integration (if installed)

### 30-plugins.zsh - Zinit Plugins

**Immediate load:**
- Dracula theme
- zsh-syntax-highlighting
- zsh-autosuggestions
- zsh-completions

**Turbo mode (async after prompt):**
- zoxide (replaces autojump, much faster)
- fzf (fuzzy finder)
- OMZ libraries (clipboard, completion, git, etc.)
- OMZ plugins (gitfast, docker, terraform, etc.)
- fast-alias-tips (Rust-based)

### 40-keybindings.zsh - Keys

- Emacs mode
- Word navigation (Option+Arrow)
- History search (Ctrl+R/S)
- Autosuggestion accept (Ctrl+F)

### 50-aliases.zsh - Aliases

- Better defaults (cat→bat, ls→colorls, etc.)
- Directory navigation
- Git shortcuts
- Safety aliases (rm -i, etc.)

### 60-functions.zsh - External Sources

- Sources lib_sh/funcs.sh
- Sources lib_sh/claude.sh
- Tool completions (helm, git-extras)
- direnv, fnm initialization

## LaunchAgents

### com.dotfiles.sync.plist

**Purpose:** Keep dotfiles synced across machines

| Setting | Value |
|---------|-------|
| Frequency | Every 4 hours |
| Run at load | Yes |
| Actions | git add, commit, pull, push |
| Logs | ~/.dotfiles/logs/sync.log |

### com.dotfiles.update.plist

**Purpose:** Keep system packages updated

| Setting | Value |
|---------|-------|
| Frequency | Friday 9:00 AM |
| Run at load | No |
| Actions | brew update/upgrade, zinit update |
| Logs | ~/.dotfiles/logs/update.log |

## Shell Function Libraries

### lib_sh/echos.sh

Output helpers:
- `ok` - Green success
- `bot` - Bot message
- `running` - Action indicator
- `warn` / `error` - Warnings and errors

### lib_sh/funcs.sh

Utilities:
- `server [port]` - Start HTTP server
- `mkd <dir>` - Make and cd
- `fs [path]` - File/directory size
- `digs <domain>` - Simplified dig
- `bootstrap_ssh_key` - Generate SSH keys
- `whodat <port>` - Process using port
- `getem <port>` - Kill process on port

### lib_sh/claude.sh

Claude CLI helpers:

**Session:**
- `cworktree <branch>` - Worktree + session (ID = repo-branch)
- `ccontinue` / `cresume` - Continue/resume sessions
- `copus` - Use Opus model

**Documentation:**
- `cdoc` - Generate CLAUDE.md
- `creadme` - Update READMEs
- `carch` - Architecture docs

**Code Quality:**
- `creview` - Review changes
- `cdebt` - Find tech debt
- `csecurity` - Security audit

**Maintenance:**
- `clint` - Fix linting
- `cupdate` - Update deps
- `cpr` - Prepare PR

## Stow Usage

### Link packages

```sh
cd ~/.dotfiles/stow
stow -v -t ~ zsh git atuin ssh
```

This creates:
- `~/.zshrc` → `stow/zsh/.zshrc`
- `~/.config/zsh/` → `stow/zsh/.config/zsh/`
- `~/.gitconfig` → `stow/git/.gitconfig`
- etc.

### Unlink

```sh
stow -D -t ~ zsh
```

### Relink after changes

```sh
stow -R -t ~ zsh
```

## Migration from OMZ

The zinit config loads most OMZ plugins via `zinit snippet OMZP::plugin-name`. Key differences:

| OMZ | Zinit |
|-----|-------|
| `source $ZSH/oh-my-zsh.sh` | Zinit loads plugins individually |
| Plugins load synchronously | Turbo mode loads async |
| autojump | zoxide (faster) |
| ~/.oh-my-zsh/custom/ | ~/.local/share/zinit/ |

## Local Customization

### ~/.zshrc.local

Machine-specific settings (not in git):

```sh
# API keys
export OPENAI_API_KEY="..."

# Local aliases
alias work="cd ~/work/projects"

# Override settings
export EDITOR="code"
```

### ~/.gitconfig.local

Private git settings (included by main .gitconfig):

```ini
[user]
    signingkey = ABC123
[commit]
    gpgsign = true
```

## Workflow

### Fresh machine

```sh
# 1. Run installer
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/ashtonian/dotfiles/master/install.sh)"

# 2. Stow configs
cd ~/.dotfiles/stow && stow -v -t ~ zsh git atuin ssh

# 3. Install LaunchAgents
~/.dotfiles/bin/dotfiles-install-launchagents.sh

# 4. Restart shell
exec zsh
```

### Daily use

- Edit files in `~/.dotfiles/stow/zsh/.config/zsh/`
- Run `stow -R -t ~ zsh` to update symlinks
- Changes auto-commit every 4 hours

### Manual operations

```sh
# Sync now
~/.dotfiles/sync.sh sync

# Update now
~/.dotfiles/bin/dotfiles-update.sh --all

# Check plugin load times
zinit times
```
