# Dotfiles operations

## Configuration

The bootstrap installer fixes its checkout at `~/.dotfiles` and backup root at
`~/.sync`. Runtime overrides below apply only to the listed scripts; they do not
relocate the installer or rewrite LaunchAgent templates.

| Variable | Type | Default | Scope / effect |
| ---------- | ------ | --------- | ---------------- |
| `DOTFILES_DIR` | Directory path | `~/.dotfiles` | Sync, updater, LaunchAgent installer; sync resolves the physical path |
| `SYNC_DIR` | Directory path | `~/.sync` | Sync's auxiliary repos |
| `SYNC_QUIET_MINUTES` | Minutes | `30` | Sync skips a repository whose newest tracked edit is younger than this, so half-finished work is not committed |
| `XDG_STATE_HOME` | Directory path | `~/.local/state` | `dotfiles/stow-hold/` keeps machine-local files `sync.sh stow` could not move home |
| `DOTFILES` | Directory path | `~/.dotfiles` | Zsh's shell-library source directory |
| `XDG_CONFIG_HOME` | Directory path | `~/.config` | Zsh module directory; Stow still targets the default home layout |
| `XDG_DATA_HOME` | Directory path | `~/.local/share` | Zinit installation and weekly update lookup; mise's tools and shims (`mise/`) |
| `MISE_DATA_DIR` | Directory path | `$XDG_DATA_HOME/mise` | mise's installed tools and `shims/`, which `env.sh` puts on PATH |
| `XDG_CACHE_HOME` | Directory path | `~/.cache` | Cached Helm completion and tool init scripts (`zsh/init-*.zsh`); delete one to force regeneration |
| `HISTFILE` | File path | `~/.zsh_history` | Shared shell history |
| `GOPATH` | Directory path | `~/go` | Go workspace and its bin path |
| `PLAYWRIGHT_BROWSERS_PATH` | Directory path | `/Volumes/E2TB/cache/ms-playwright` | Browser builds Playwright downloads, kept beside the Go and npm caches on E2TB (npm's is `cache=` in `~/.npmrc`) |
| `GO_CACHE_TRIM_HOURS` | Whole hours, at least 2 | `24` | `bin/go-cache-trim`: delete Go build cache entries unused this long; set in the installed `com.ashtonian.go-cache-trim` plist |
| `EDITOR` / `VISUAL` | Command | nvim if installed, else vim / `$EDITOR` | Core editor defaults from `.zshenv` |
| `PAGER` | Command | less | Core pager default |
| `LANG` | Locale string | en_US.UTF-8 | Existing value is preserved |
| `SHOW_COWSAY` | String | false | Set exactly true in `~/.zshrc.local` to enable the greeting |
| `AWS_SHARED_CREDENTIALS_FILE` | File path | `~/.aws/credentials` | AWS helper credential destination |
| `AWS_CONFIG_FILE` | File path | `~/.aws/config` | AWS helper region/profile config |
| `AGENT_SHELL` | Marker | unset; Codex sets it through `[shell_environment_policy] set` in `/etc/codex/config.toml` (`bin/dotfiles-agents`) | `.zshenv` unsets it and runs the `zsh -c` command in Homebrew bash (or `/usr/bin/bash` 4+); with neither, it turns off `NOMATCH`, `BAD_PATTERN`, `EQUALS` and turns on `SH_WORD_SPLIT` instead |
| `CLAUDE_CODE_SHELL` | File path | Homebrew bash, from `bin/dotfiles-agents`'s managed-settings drop-in | Shell Claude Code's Bash tool runs |
| `DOTFILES_ENV_PATH` | PATH value | set by `env.sh` | The PATH `env.sh` last composed. A nested shell whose PATH still ends with it keeps PATH unchanged, so directories a command put first stay first; do not set it by hand |
| `DOTFILES_SYSTEM_ROOT` | Directory path | empty (`/`) | Prefix for every path `bin/dotfiles-agents` writes; for testing and packaging |

OpenCode's [config tables](../stow/opencode/README.md#config) cover its bind
address, port, gateway files, worker binaries, concurrency, and retention. The
agent dashboard's are in [AGENT-MONITOR.md](AGENT-MONITOR.md#config), and the agent
telemetry collector's in [AGENT-TELEMETRY.md](AGENT-TELEMETRY.md#config).
LaunchAgents do not read `~/.zshrc.local`. Set service overrides in an installed
plist's `EnvironmentVariables` and reload it. Reinstallation replaces local plist
edits with the checked-in template.

## Git identity and signing

The shared Git config contains the repository owner's identity. Override it
intentionally for another user or a work-specific repository. The installer
does not create a signing key or register one with GitHub.

Use [the local template](../stow/git/.gitconfig.local.example), merging settings
into an existing `~/.gitconfig.local` rather than overwriting it:

```ini
[user]
    name = Your Name
    email = YOUR_VERIFIED_SIGNING_EMAIL
    signingkey = YOUR_GPG_KEY_ID
[commit]
    gpgsign = true
[gpg]
    program = /opt/homebrew/bin/gpg
```

Use the actual GPG path from `command -v gpg`; Intel Homebrew typically uses
`/usr/local/bin/gpg`. Inspect effective configuration in each synced repo:

```sh
git -C ~/.dotfiles config --show-origin --get-regexp \
  '^(user\.(name|email|signingkey)|gpg\.program|commit\.gpgsign)$'
gpg --list-secret-keys --keyid-format long
gh auth status
```

Authenticate Git transport for the remote, make the signing key usable by the
background job, and register its public key with GitHub. The commit email must
match an email on the signing key that is verified on the GitHub account.
For deliberate manual commits, use `git commit -S` and `git verify-commit HEAD`.
After a GitHub push, inspect its Verified badge or API status too.

Git uses gh for `github.com` and `gist.github.com` credentials through the
helpers in `~/.gitconfig.local`, which the shared config includes last, so one gh
login covers both. Copy them from `stow/git/.gitconfig.local.example` rather than
running `gh auth setup-git`: it writes with `git config --global`, and
`~/.gitconfig` links into this repository, so the helpers would land in the
tracked shared config. Besides gh's defaults (`repo`, `read:org`, `gist`,
`workflow`), this setup uses `project` for GitHub Projects, `write:gpg_key` for
registering the signing key, and `admin:public_key` and `admin:ssh_signing_key`
for the SSH key upload helper. Log in once with all of them:

```sh
gh auth login -h github.com --insecure-storage \
  -s project,write:gpg_key,admin:public_key,admin:ssh_signing_key
```

`--insecure-storage` keeps the token in `~/.config/gh/hosts.yml` (mode 0600,
outside this repo; `sync.sh` stows `gh` file by file) instead of the login
keychain, which SSH sessions can't read while it is locked. To add a scope
later, run `gh auth refresh -h github.com -s <scope>`, which keeps the existing
ones. Running `gh auth login` again issues a token with only the defaults.

## LaunchAgents

Use these options with `~/.dotfiles/bin/dotfiles-install-launchagents.sh`:

| Option | Behavior |
| -------- | ---------- |
| No options | Install/reload all eligible agents; sync starts at load |
| `--sync-only` / `--update-only` / `--go-cache-trim-only` | Install/reload one scheduled job |
| `--codex-only` / `--opencode-only` / `--agent-monitor-only` / `--agent-monitor-gate-only` / `--otel-agent-only` | Install/reload one service if prerequisites exist |
| `--status` | Show installed/loaded/running state and recent logs |
| `--uninstall` | Unload and remove all eight installed agent plists |
| `--help` | Show supported options |

`com.ashtonian.go-cache-trim` runs `bin/go-cache-trim` every hour. Go
trims its build cache only of entries unused for five days. The agent
checkouts share one cache whose working set is about 320 GiB, and cache keys
include the toolchain version: after a Go upgrade the old toolchain's entries
are never used again, so for five days the cache would hold two working sets. Each run logs the entries and GiB it deleted to
`~/Library/Logs/go-cache-trim/trim.log`; `bin/go-cache-trim --dry-run` reports
what a run would delete. A deleted entry costs one recompile the next time a
build needs it.

The job runs at low I/O priority (`LowPriorityIO` in the plist), so its
deletes wait whenever builds keep the volume busy, and a run can then take
hours. Meanwhile `launchctl print "gui/$(id -u)/com.ashtonian.go-cache-trim"`
shows `state = running`, and launchd starts no second run until it exits.
Errors go to `~/Library/Logs/go-cache-trim/trim.err`. A long run is
progressing if `pgrep -f 'go-cache-trim /'` shows a new batch PID every few
minutes. Entries a run could not reach, for example because the volume dropped,
stay until the next run deletes them.

The cache's location and build flags are Go's own settings (`go env -w`, stored
in `$(go env GOENV)`): `GOCACHE`, `GOMODCACHE` and `GOTMPDIR` under
`/Volumes/E2TB/cache/go/`, and `GOFLAGS=-trimpath`. Without `-trimpath`, Go keys
every compiled package by its checkout's absolute directory, so each agent
checkout of the same commit filled the cache with its own copy; with it, they
share one entry. A test that locates files from `runtime.Caller` sees a
module-relative path under `-trimpath`; resolve such files from the working
directory instead. Check with `go env GOFLAGS`; run one build without it with
`GOFLAGS= go build ...`.

Source templates live in launchagents/; installed copies live in
`~/Library/LaunchAgents/`. Pause a scheduled job without deleting its plist:

```sh
launchctl bootout "gui/$(id -u)/com.dotfiles.sync"
```

Resume it when ready (RunAtLoad starts a sync immediately):

```sh
launchctl bootstrap "gui/$(id -u)" \
  "$HOME/Library/LaunchAgents/com.dotfiles.sync.plist"
```

Inspect or trigger a loaded scheduled job:

```sh
~/.dotfiles/bin/dotfiles-install-launchagents.sh --status
launchctl print "gui/$(id -u)/com.dotfiles.sync"
launchctl kickstart "gui/$(id -u)/com.dotfiles.sync"
tail -50 ~/.dotfiles/logs/sync.log
```

Idle scheduled jobs usually have no PID; check their last exit status and log.
`sync.sh check` tests the lock, but also creates runtime directories and may
rotate an oversized sync log. Busy locks and failed connectivity checks return
success; operation errors return nonzero. Other repositories may still sync
when one fails. The sync log rotates above 1 MiB and keeps three archives.
Update and service logs have no rotation configured by these scripts. There
is no metrics endpoint for sync or updates.

### Codex service

The service runs `bin/codex-daemon` app-server `--remote-control` `--listen` unix://.
`gptmore` and `gptmax` attach to that socket. Their `-C "$PWD"` selects the project
directory instead of the service's home working directory.

The stable launcher copies the installed Homebrew release into
`~/.local/libexec/codex-stable/`, verifies its signature, and executes the fixed
path. It refreshes the copy when the service next starts. Grant Full Disk Access
to `~/.local/libexec/codex-stable/bin/codex` in System Settings → Privacy &
Security when protected directories or external volumes require it. Check the
grant again if the binary or its signing identity changes.

```sh
launchctl print "gui/$(id -u)/com.ashtonian.codex-remote-control"
tail -50 ~/Library/Logs/CodexHomebrew/remote-control.stderr.log

# Interrupts sessions served by this process.
launchctl kickstart -k "gui/$(id -u)/com.ashtonian.codex-remote-control"
```

For Too many open files errors, inspect the loaded job's maxfiles value. The
template sets a soft limit of 65,536. Apply plist changes with `--codex-only`;
`kickstart -k` alone keeps the previously loaded settings. If sessions repeatedly
drop, inspect the log and `launchctl list` for duplicate jobs before removing a
specific stale job. OpenCode has separate [operations instructions](../stow/opencode/README.md#operations),
and so do the [agent dashboard](AGENT-MONITOR.md#operations) and the
[telemetry collector](AGENT-TELEMETRY.md#operations).

## App backups

Sync does not run Mackup. The shared `.mackup.cfg` selects every detected app
except an ignore list, which would copy credential files such as
`.codex/auth.json`, `.kube/config` and `.npmrc` into the backup repository.
Automatic backups return behind the guards in
[the Mackup design](MACHINE-FEATURES.md#mackup).

Existing backups in `~/.sync/mackup` stay where they are, and sync still
publishes that repository like any other repository under `SYNC_DIR`.

Do not run Mackup by hand in a way that changes original files:

| Command | Why not |
| ------- | ------- |
| `mackup link install`, `mackup link`, `mackup link uninstall` | Moves files into the store and leaves symlinks behind; current macOS apps refuse to read or save symlinked preferences, so settings reset |
| `mackup restore` without an app name | Restores every app at once; each restore deletes the original before copying, so a copy that fails partway (macOS often refuses access to app containers) loses the original |
| `mackup backup` on Mackup older than 0.9.0 | Older versions run link mode for `backup`; check `mackup --version` |

To restore one app's settings from an existing backup by hand: quit the app,
copy its current files somewhere safe, then run
`mackup --config-file=<config naming the source host> restore <app>`. Restored
files come back as mode 0600, so re-apply the modes of anything executable,
such as scripts under `~/Library/Scripts`.

## Sync failures

Start with `git -C ~/.dotfiles status` and `logs/sync.log`. Do not delete Git
state files, disable signing, or force-push to clear a failure.

| Symptom | Check and recovery |
| --------- | -------------------- |
| Another sync is running | Run `sync.sh check` and inspect the active process. `logs/sync.flock` normally persists after exit. Removing it does not release a live lock and can allow overlap. |
| No network connectivity | Sync checks <https://github.com> with a five-second timeout. Restore connectivity, then retry. |
| Git operation in progress | Finish or deliberately abort the merge, rebase, cherry-pick, revert, or bisect; then rerun sync. |
| Detached HEAD / missing tracking branch | Check out the intended branch and set its same-named origin upstream after fetching. |
| Gitleaks fails | Fix staged content or the outgoing commit. Rotate/revoke an exposed secret; deleting the current file does not remove Git history. |
| Signing fails | Check effective Git config, key availability, GPG/pinentry, and background unlock behavior. Diagnose with a deliberate signed commit interactively; never disable signing. |
| GitHub reports bad_email | Correct the affected commit to a signing-key email verified on GitHub. Keep a backup ref before any authorized history repair. |
| GitHub verification fails after push | Publication already occurred. Inspect the reason and GitHub status; repair only affected commits within authorized history scope. |
| Merge conflict | Automation aborts the merge. Resolve and sign the integration deliberately. Dotfiles has no conflict preference; auxiliary repos use local-preferred conflicting hunks (`-X ours`). |
| Push rejected | Check permissions and remote changes. Sync tries at most three times with fetch and signed merge; it never force-pushes. |
| Excluded tracked changes remain | Review tracked `*.local`, `.env*` or `*.secret*` paths in any directory. Sync skips merge/push while excluded tracked changes remain. |
| Sync leaves a repository alone | The log says why: a Git index lock (another Git command is running, or one crashed and left `.git/index.lock`; check `ps` before removing it), or a tracked edit newer than `SYNC_QUIET_MINUTES`. The next run picks it up. |
| New files are not published | By design: sync stages tracked files only (`git add -u`). Commit new files yourself. |
| Theme repo cannot push | Installer theme clones point at upstream projects. Use an owned fork as origin before publishing local changes. All immediate Git repos under `SYNC_DIR` participate. |
| Package install fails | Run the check below. Check App Store sign-in and tapped/private package access; sync does not upgrade existing packages. |
| Update stops early | Read `logs/update.log`. Homebrew update, upgrade, cleanup, doctor, Zinit updates, and sync must succeed in sequence; `brew doctor` failures stop later actions. |

```sh
HOMEBREW_NO_AUTO_UPDATE=1 brew bundle check --no-upgrade \
  --file="$HOME/.dotfiles/Brewfile"
```

## Shell and Stow troubleshooting

| Symptom | Check and recovery |
| --------- | -------------------- |
| Stow conflict | Preview with explicit `--dir` and `--target` as shown in the README. Compare and back up the conflicting file before moving it aside, then run `sync.sh stow`. A package with a conflict is left exactly as it was. |
| Machine-local file left in `stow-hold` | `sync.sh stow` found a gitignored file inside a package, but a real file already sits at its home location. Compare the two (the log names both), keep the right one at the home path, and delete the held copy under `~/.local/state/dotfiles/stow-hold/`. |
| Untracked files in stow packages | The log lists them after `sync.sh stow`. They are linked but never published. Commit them (`git add` and a signed commit) or delete them. |
| Slow first shell | First-run downloads are expected. Use repeated `time zsh -ic exit` for warm config load and `zinit times` in a real terminal for deferred plugins; config-load time is not full first-prompt latency. |
| Plugin load error | Inspect `zinit list` and `zinit times`, then repair/update the named plugin or cache rather than deleting unrelated plugin data. |
| Unexpected history key | Inspect `bindkey '^R'` after deferred plugins load. Atuin should own it when installed; otherwise FZF can own it. |
| Missing Rust toolchain | Run `rustup default stable` after a fresh Rustup install. |
| `~/.config/gh` is a link into the repository (`readlink ~/.config/gh` prints a path) | An older stow folded the package, so gh wrote its token into `stow/gh/.config/gh/hosts.yml`. Run `~/.dotfiles/sync.sh stow`: it relinks gh file by file and moves `hosts.yml`, which is gitignored, to `~/.config/gh/`. Check `readlink ~/.config/gh` prints nothing and `gh auth status` still succeeds. |
| `gh auth status`: "The token in default is invalid" over SSH | gh found no token. It is usually in the login keychain, which SSH sessions can't read while it is locked (`security show-keychain-info` fails with "User interaction is not allowed"), and git's `osxkeychain` helper reports `failed to store: -25308` for the same reason. Log in once with file storage as shown in [Git identity and signing](#git-identity-and-signing). |
| A `gh` scope disappeared | `gh auth login` issues a new token with only the default scopes. Add scopes with `gh auth refresh -h github.com -s <scope>`, which keeps the existing ones; see [Git identity and signing](#git-identity-and-signing) for the set this setup uses. |

Before publishing, run the [validation commands](../README.md#validation) and
review `git diff`. Update configuration tables when defaults or interfaces change.
