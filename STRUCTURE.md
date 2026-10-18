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
│   │       ├── 60-functions.zsh       # External function sources
│   │       └── 70-greeting.zsh        # Optional greeting (disabled by default)
│   ├── git/
│   │   └── .gitconfig                 # Git settings (includes .local)
│   ├── ssh/
│   │   └── .ssh/config                # SSH config template
│   ├── atuin/
│   │   └── .config/atuin/config.toml  # Atuin shell history config
│   └── opencode/                      # OpenCode coordinator (see its README.md)
│       └── .config/opencode/          # config, coordinator agent, delegate plugin
│
├── lib_sh/                            # Shell function libraries
│   ├── echos.sh                       # Colorized output (ok, bot, running, etc.)
│   ├── funcs.sh                       # Utility functions (server, mkd, etc.)
│   ├── requirers.sh                   # Package requirement helpers
│   ├── claude.sh                      # Claude CLI helper functions
│   └── opencode.sh                    # oc / ocweb: attach to the OpenCode server
│
├── bin/                               # Executable scripts
│   ├── aws-profile                    # Secure AWS profile updates and renames
│   ├── stable-exec                    # Runs a Homebrew CLI from a fixed path (privacy grants)
│   ├── codex-daemon                   # stable-exec codex (the Codex agent)
│   ├── opencode-server                # The OpenCode agent's entry point
│   ├── dotfiles-install-launchagents.sh  # LaunchAgent installer
│   └── dotfiles-update.sh             # Weekly update script
│
├── launchagents/                      # macOS LaunchAgent definitions
│   ├── com.ashtonian.codex-remote-control.plist  # Codex app-server (always on)
│   ├── com.ashtonian.opencode.plist   # OpenCode server (always on)
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
- Atuin history options; initialization occurs after keybindings in 40-keybindings.zsh

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
- History search (Ctrl+R/S), with Atuin owning Ctrl+R and Up when installed; deferred FZF leaves Ctrl+R unchanged
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

### com.ashtonian.codex-remote-control.plist

**Purpose:** The local Codex app-server with remote control, on its default Unix
socket — the server `gptmore` / `gptmax` connect to. Installed only when codex is
(`cask "codex"` in the Brewfile).

| Setting | Value |
|---------|-------|
| Frequency | Always on (KeepAlive, restarted by launchd) |
| Run at load | Yes |
| Program | `bin/codex-daemon app-server --remote-control --listen unix://` |
| Open files (soft) | 65536 (`SoftResourceLimits.NumberOfFiles`; launchd default is 256) |
| Logs | ~/Library/Logs/CodexHomebrew/remote-control.{stdout,stderr}.log |

**Why the launcher.** A LaunchAgent does not inherit the terminal's Full Disk
Access, and macOS keys a command-line tool's privacy grants to the executable's
path. Homebrew installs each codex release under a new versioned path, so a daemon
run from there lost its grant on every upgrade; its first touch of an external
volume (E2TB) then raised a "Removable Volumes" prompt, and an unanswered prompt
stalls other apps' access checks behind it (OrbStack waited nine hours on one).
`bin/codex-daemon` runs `bin/stable-exec codex`, which APFS-clones the current
release into `~/.local/libexec/codex-stable/` when it changed and execs it from
there. Every release is signed by the same OpenAI Developer ID, so one grant keeps
matching.

**One-time setup, per machine** (privacy settings cannot be scripted): System
Settings → Privacy & Security → Full Disk Access → **+** → Cmd+Shift+G →
`~/.local/libexec/codex-stable/bin/codex`, toggled on. The installer creates that
path first.

**Troubleshooting.** Codex sessions stall on a path under `/Volumes`, or a dialog
asks for codex to access a removable volume: check that the agent runs the stable
copy (`ps -axo command | grep codex-stable`) and that its Full Disk Access entry is
on. A codex upgrade takes effect the next time the daemon starts
(`launchctl kickstart -k gui/$(id -u)/com.ashtonian.codex-remote-control`), which
ends the sessions it is serving.

Commands fail with `Too many open files (os error 24)` or `dup of fd N failed`, or
skills fail to load: the daemon hit its fd limit. One app-server hosts every chat,
and each chat runs its own `node_repl` MCP server, so ~15 chats hold ~240 fds at
idle. Check the loaded limit with `launchctl print
gui/$(id -u)/com.ashtonian.codex-remote-control | grep maxfiles` and current usage
with `lsof -p <pid> | wc -l`. A plist change takes effect only after a reload
(`dotfiles-install-launchagents.sh --codex-only`); `kickstart -k` alone keeps the
old limits.

The daemon restarts every ~15 s and gptmore sessions keep dropping: check
`launchctl list | grep codex` for a stray job besides `codex-remote-control`. A
job created with `launchctl submit` is KeepAlive, so a one-shot reload helper
submitted that way reruns forever. Remove it with `launchctl remove <label>`, then
confirm `com.ashtonian.codex-remote-control` is still loaded.

### com.ashtonian.opencode.plist

**Purpose:** The OpenCode server: web UI and API for the coordinator agent, which
`oc` and browsers attach to. Installed only when opencode is installed
(`brew "anomalyco/tap/opencode"`) and its local files exist.

| Setting | Value |
|---------|-------|
| Frequency | Always on (KeepAlive, restarted by launchd) |
| Run at load | Yes |
| Program | `bin/opencode-server` → `bin/stable-exec opencode serve --hostname 0.0.0.0 --port 4096` |
| Logs | ~/Library/Logs/opencode/server.{stdout,stderr}.log |

It runs from `~/.local/libexec/opencode-stable/` for the same reason as the Codex
agent, and needs the same one-time Full Disk Access grant, on
`~/.local/libexec/opencode-stable/bin/opencode`. Everything else, including
troubleshooting: [stow/opencode/README.md](stow/opencode/README.md).

## Sync safety

`sync.sh` uses macOS `lockf` on `logs/sync.flock`. A process exit releases the
kernel lock; the empty file may remain. `sync.sh check` reports availability
without syncing. Git identity and signing settings come from the repository's
effective Git configuration. Commits and merges use explicit signing and local
verification; GitHub publication also checks GitHub verification status.

Mackup reads `MACKUP_CONFIG_FILE` (default `~/.mackup.cfg`) and receives a temporary
configuration through `--config-file`, leaving the
stowed `~/.mackup.cfg` link intact. Its backup path honors `SYNC_DIR`.

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

### lib_sh/opencode.sh

- `oc` - Terminal UI on the local OpenCode server, in `$PWD`
- `ocweb` - Open the web UI and copy its password

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

Machine-specific git settings (included by main .gitconfig). See `stow/git/.gitconfig.local.example`:

```ini
[commit]
    gpgsign = true
[user]
    signingkey = YOUR_GPG_KEY_ID
[gpg]
    program = /opt/homebrew/bin/gpg
```

### Brewfile.local

Machine-specific Homebrew packages (gitignored). The shared `Brewfile` is curated manually and installed on all machines. Use `Brewfile.local` for packages only needed on one machine.

### Multi-Machine Sync Architecture

- **Brewfile**: `sync.sh` installs from the shared Brewfile — it never overwrites it. `Brewfile.local` handles per-machine packages.
- **Mackup**: `sync.sh` backs up to `~/.sync/mackup/<hostname>/` so each machine has isolated app config backups.
- **Git push**: Uses signed merges and up to three push attempts. Gitleaks scans outgoing dotfiles, local signatures are verified, and GitHub commit verification is checked with `gh`. Unfinished Git operations and failures stop publication.
- **Local overrides**: `.gitconfig.local`, `.zshrc.local`, `.ssh/config.local` are never tracked in git.

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
- Changes auto-commit every 4 hours with signed commits, a secret scan and Git operation guards

### Manual operations

```sh
# Sync now
~/.dotfiles/sync.sh sync

# Update now
~/.dotfiles/bin/dotfiles-update.sh --all

# Check plugin load times
zinit times
```
