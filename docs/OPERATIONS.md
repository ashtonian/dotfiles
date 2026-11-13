# Dotfiles operations

## Configuration

The bootstrap installer fixes its checkout at `~/.dotfiles` and backup root at
`~/.sync`. Runtime overrides below apply only to the listed scripts; they do not
relocate the installer or rewrite LaunchAgent templates.

| Variable | Type | Default | Scope / effect |
| ---------- | ------ | --------- | ---------------- |
| `DOTFILES_DIR` | Directory path | `~/.dotfiles` | Sync, updater, LaunchAgent installer, and the `dotfiles` engine's repository (`--repo`); sync resolves the physical path |
| `SYNC_DIR` | Directory path | `~/.sync` | Sync's auxiliary repos |
| `DOTFILES_BIN` | File path | `~/.local/bin/dotfiles` | The engine binary sync builds from the checkout (when `go.mod`, `go.sum`, `cmd/` or `internal/` is newer than it) and runs as `dotfiles apply`; `install.sh` builds and runs the same path |
| `DOTFILES_PROFILES` | Comma-separated names | unset | `install.sh`: the profiles to write, as `--profiles` does; without either it keeps an existing manifest or asks |
| `SYNC_QUIET_MINUTES` | Minutes | `30` | Sync skips a repository whose newest tracked edit is younger than this, so half-finished work is not committed |
| `SYNC_CONNECTIVITY_URL` | URL | `https://github.com` | Sync's reachability check, a HEAD request before any network step; set it in the installed plist to probe another host |
| `SYNC_CONNECTIVITY_TIMEOUT` | Seconds | `15` | How long that HEAD request may take (connecting is capped at 5 s) before sync logs "No network connectivity" and skips the run |
| `XDG_STATE_HOME` | Directory path | `~/.local/state` | `dotfiles/applied.json` is what `dotfiles apply` installed and `dotfiles/apply.lock` serialises runs |
| `XDG_CONFIG_HOME` | Directory path | `~/.config` | Not followed: the engine, sync and the installer always use `~/.config` (the stubs and the shared git and ssh configs name it), with `~/.config/dotfiles/machine.toml` as this machine's manifest and `~/.config/dotfiles/generated/` for the generated outputs. `zshrc.zsh` loads its modules from its own directory. git reads `$XDG_CONFIG_HOME/git/config`, so `dotfiles doctor` reports a value other than `~/.config` |
| `DOTFILES` | Directory path | `~/.dotfiles` | Zsh's shell-library source directory |
| `XDG_DATA_HOME` | Directory path | `~/.local/share` | Zinit installation and weekly update lookup; mise's tools and shims (`mise/`) |
| `MISE_DATA_DIR` | Directory path | `$XDG_DATA_HOME/mise` | mise's installed tools and `shims/`, which `env.sh` puts on PATH |
| `XDG_CACHE_HOME` | Directory path | `~/.cache` | Cached Helm completion and tool init scripts (`zsh/init-*.zsh`); delete one to force regeneration |
| `HISTFILE` | File path | `~/.zsh_history` | Shared shell history |
| `GOPATH` | Directory path | `~/go` | Go workspace and its bin path |
| `PLAYWRIGHT_BROWSERS_PATH` | Directory path | unset (Playwright's own default); the `studio` profile sets `/Volumes/E2TB/cache/ms-playwright` | Browser builds Playwright downloads. Setting `paths.playwright_browsers` (feature `shell.env`), exported by the generated `env.sh`; a value already in the environment wins |
| `GO_CACHE_TRIM_HOURS` | Whole hours, at least 2 | `24` | `bin/go-cache-trim`: delete Go build cache entries unused this long; set in the installed `com.ashtonian.go-cache-trim` plist |
| `EDITOR` / `VISUAL` | Command | nvim if it is on the composed PATH, else vim / `$EDITOR` | Core editor defaults from `env.sh`, chosen after PATH is composed |
| `PAGER` | Command | less | Core pager default |
| `LANG` | Locale string | en_US.UTF-8 | Existing value is preserved |
| `SHOW_COWSAY` | String | false | Set exactly true in `~/.zshrc.local` to enable the greeting |
| `AWS_SHARED_CREDENTIALS_FILE` | File path | `~/.aws/credentials` | AWS helper credential destination |
| `AWS_CONFIG_FILE` | File path | `~/.aws/config` | AWS helper region/profile config |
| `AGENT_SHELL` | Marker | unset; Codex sets it through `[shell_environment_policy] set` in `/etc/codex/config.toml` (`bin/dotfiles-agents`) | A marked `zsh -lc` hands off in `zlogin.zsh`, after the other entry points ran; a marked plain `zsh -c` in `zshenv.zsh`. Either unsets it and runs the command in Homebrew bash (or `/usr/bin/bash` 4+); with neither, it turns off `NOMATCH`, `BAD_PATTERN`, `EQUALS` and turns on `SH_WORD_SPLIT` instead. `env.sh` unsets it in any other shell, so a zsh a bash command starts stays zsh |
| `CLAUDE_CODE_SHELL` | File path | Homebrew bash, from `bin/dotfiles-agents`'s managed-settings drop-in | Shell Claude Code's Bash tool runs |
| `DOTFILES_ENV_PATH` | PATH value | set by `env.sh` | The PATH `env.sh` last composed. A nested shell whose PATH still ends with it keeps PATH unchanged, so directories a command put first stay first; do not set it by hand |
| `DOTFILES_SYSTEM_ROOT` | Directory path | empty (`/`) | Prefix for every path `bin/dotfiles-agents` writes; for testing and packaging |

The `dotfiles` engine's flags:

| Flag | Type | Default | Scope / effect |
| ---- | ---- | ------- | -------------- |
| `--home` | Directory path | `$HOME` | All commands: the home directory to manage |
| `--repo` | Directory path | `$DOTFILES_DIR`, else `~/.dotfiles` | All commands: the checkout whose `features/` and `profiles/` are read |
| `--machine` | File path | `~/.config/dotfiles/machine.toml` | All commands: this machine's manifest |
| `--profiles` | Comma-separated names | none (required) | `init`: the profiles to write, in order |
| `--force` | Boolean | `false` | `init`: replace an existing manifest |
| `--dry-run` | Boolean | `false` | `apply`: report what would change, change nothing (`doctor` always does this) |
| `--lock-wait` | Duration | `1m` | `apply`, `adopt`: how long to wait for another run's `apply.lock` |
| `--git-timeout` | Duration | `30s` | `apply`, `doctor`: how long `git ls-files` may take; apply needs the tracked-file list so unfolding never moves a tracked file |
| `--json` | Boolean | `false` | `status`: print JSON |

OpenCode's [config tables](../features/agents.opencode/README.md#config) cover its bind
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

Use [the local template](../features/git/gitconfig.local.example), merging settings
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

Git uses gh for `github.com` and `gist.github.com` credentials, so one gh login
covers both. `gh auth setup-git` writes the helpers with `git config --global`,
which lands in `~/.gitconfig`: this machine's own file, read after the shared
`~/.config/git/config`. [The local template](../features/git/gitconfig.local.example)
shows the same helpers for `~/.gitconfig.local` instead. Besides gh's defaults
(`repo`, `read:org`, `gist`, `workflow`), this setup uses `project` for GitHub
Projects, `write:gpg_key` for registering the signing key, and `admin:public_key`
and `admin:ssh_signing_key` for the SSH key upload helper. Log in once with all
of them:

```sh
gh auth login -h github.com --insecure-storage \
  -s project,write:gpg_key,admin:public_key,admin:ssh_signing_key
gh auth setup-git -h github.com
```

`--insecure-storage` keeps the token in `~/.config/gh/hosts.yml` (mode 0600,
outside this repo; the engine installs gh's settings file by file, so
`~/.config/gh` is a real directory) instead of the login keychain, which SSH
sessions can't read while it is locked. To add a scope later, run
`gh auth refresh -h github.com -s <scope>`, which keeps the existing ones.
Running `gh auth login` again issues a token with only the defaults.

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
specific stale job. OpenCode has separate [operations instructions](../features/agents.opencode/README.md#operations),
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

## Moving an existing machine to the feature engine

A machine set up before the engine has stow's links in `$HOME`, some of them
whole directories folded into the repository. The first `dotfiles apply`
converts them; nothing needs removing by hand.

Before the migration reaches the machine:

1. Write its manifest with the profiles from the README's machine table, for
   example on the Mac mini:

   ```sh
   mkdir -p ~/.config/dotfiles
   printf 'profiles = ["base", "dev", "desktop", "server"]\n' > ~/.config/dotfiles/machine.toml
   ```

2. Check `go version` is at least the `go` line in `go.mod`; `brew install go`
   or `brew upgrade go` otherwise. Sync builds the engine with `GOTOOLCHAIN=local`
   and refuses to merge the migration until both are in place, so the machine
   keeps working on the old layout until then.

3. Where fnm provided Node, install mise's default Node now (`brew install mise`,
   then `mise install`): `env.sh` puts mise's shims on PATH instead of fnm's
   Node, so agents and LaunchAgents that run `node` or `npx` need it. The weekly
   update runs `mise install` from then on.

Then, on a machine with the sync LaunchAgent, the next sync merges, builds and
applies in one run. On a machine without it, run the same steps by hand:

```sh
git -C ~/.dotfiles pull --ff-only
~/.dotfiles/sync.sh apply      # builds ~/.local/bin/dotfiles, then dotfiles apply
dotfiles doctor                # exit 0 when nothing is left
```

The first apply prints `unfold` for each folded directory, `move-home` for each
untracked file a tool wrote through one (gh's `hosts.yml`, opencode's
`node_modules`), `relink` and `retire` for stow's file links, and `stub` for the
entry points (`~/.zlogin` is new). Then check what the old links carried:

```sh
git -C ~/.dotfiles status --short --ignored   # nothing left under stow/
git config --show-origin --get user.signingkey  # from ~/.gitconfig.local
ssh -G github.com >/dev/null && echo ssh ok
zsh -lic 'echo shell ok'
```

Reinstall the sync and update agents once
(`~/.dotfiles/bin/dotfiles-install-launchagents.sh --sync-only`, then
`--update-only`): an installed plist is a copy, and plists from before the
rollout run `bash -l`, whose `path_helper` puts Apple's bash 3.2 and git ahead
of Homebrew's. Where Go's caches are on an external volume (`go env GOCACHE`),
the first run asks once whether `bash` may access files on a removable volume;
allow it on the machine's screen (System Settings > Privacy & Security > Files
and Folders lists it afterwards). Until someone answers, the job waits in its
first Go command.

Start with `git -C ~/.dotfiles status` and `logs/sync.log`. Do not delete Git
state files, disable signing, or force-push to clear a failure.

| Symptom | Check and recovery |
| --------- | -------------------- |
| Another sync is running | Run `sync.sh check` and inspect the active process. `logs/sync.flock` normally persists after exit. Removing it does not release a live lock and can allow overlap. If it persists across runs, `lsof ~/.dotfiles/logs/sync.flock` names the holder: a sync in progress is `sync.sh` under launchd; anything else (such as `op daemon`) is a leftover from before sync stopped handing the lock to its steps, so end it and the next run proceeds. |
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
| `No network connectivity (... did not answer within ...s), skipping sync` | The HEAD request to `SYNC_CONNECTIVITY_URL` failed. Check `curl -sfI https://github.com` from a terminal; if it answers only slowly, raise `SYNC_CONNECTIVITY_TIMEOUT` in the installed plist. The next run retries. |
| Sync never finishes; `ps` shows a Go command at 0% CPU under it | macOS is waiting for an answer to "bash would like to access files on a removable volume" because Go's caches are on an external drive. Answer it on the machine's screen, or allow `bash` under System Settings > Privacy & Security > Files and Folders. `log show --last 1h --predicate 'subsystem == "com.apple.TCC"' | grep AUTHREQ_PROMPTING` names the waiting binary. |
| New files are not published | By design: sync stages tracked files only (`git add -u`). Commit new files yourself. |
| `installs machine features and this machine has no .../machine.toml` | Upstream uses the feature engine and this machine has no manifest, so sync neither merges nor pushes (merging would leave the old stow links pointing at moved files). Write `~/.config/dotfiles/machine.toml` with this machine's profiles from the list in the message, such as `profiles = ["base", "dev", "desktop"]`, then run `sync.sh`: the same run merges and applies. |
| `installs machine features and Go is not installed to build its engine` | Sync builds the upstream engine before merging it and found no `go` on its PATH, so it neither merges nor pushes. Install Go (`brew install go`; the LaunchAgent's PATH includes `/opt/homebrew/bin`), then run `sync.sh`. |
| `engine does not build with this machine's Go or cannot plan ...machine.toml` | The lines above it are the build error or `dotfiles check`'s message. A build error usually means Go is older than `go.mod` (sync uses `GOTOOLCHAIN=local`): upgrade Go. A plan error (exit 2) names the profile, feature or setting in `machine.toml` that upstream no longer accepts: fix the manifest. Nothing was merged; rerun `sync.sh`. |
| `Building ~/.local/bin/dotfiles failed` / `Go is not installed` | Sync builds the engine with the installed Go and `GOTOOLCHAIN=local`, so it never downloads a toolchain. Install or upgrade Go to the version in `go.mod` (`brew install go`), then rerun `sync.sh apply`. |
| `dotfiles apply left problems to resolve` | The log above lists them; see [Feature engine troubleshooting](#feature-engine-troubleshooting). Sync carries on with packages and the other repositories. |
| Theme repo cannot push | Installer theme clones point at upstream projects. Use an owned fork as origin before publishing local changes. All immediate Git repos under `SYNC_DIR` participate. |
| Package install fails | Run the check below. Check App Store sign-in and tapped/private package access; sync does not upgrade existing packages. |
| Update stops early | Read `logs/update.log`. Homebrew update, upgrade, cleanup, doctor, `mise install`, Zinit updates, and sync must succeed in sequence; `brew doctor` failures stop later actions. Run one step alone with `dotfiles-update.sh --brew`, `--mise`, `--zinit` or `--sync`. |

```sh
HOMEBREW_NO_AUTO_UPDATE=1 brew bundle check --no-upgrade \
  --file="$HOME/.config/dotfiles/generated/Brewfile"
```

## Feature engine troubleshooting

Run `dotfiles doctor`; it changes nothing and lists each problem with its path.

| Symptom | Check and recovery |
| ------- | ------------------ |
| `a file is in the way` | A real file sits where a link goes. Compare it with the tracked file the message names, keep what you need (in the repository if it should be shared), move the file aside, and run `dotfiles apply`. |
| `edited here since dotfiles last wrote it` | A managed copy was changed locally, by hand or by the app that rewrites it. Keep it with `dotfiles adopt <path>`, which writes it into the tracked file (sync publishes it like any tracked edit), or delete the local file and run `dotfiles apply` to take the repository's version. |
| `not a managed copy on this machine` (exit 64) | `dotfiles adopt` names only files an enabled feature installs as a copy; linked files are edited in place and need no adopt. Flags go before the paths. |
| `move this line before the first Host or Match line` | `~/.ssh/config` existed before the stub and its `Include dotfiles.conf` comes after a `Host` or `Match` line, where it applies only inside that block. Move it above the first one. |
| `left in the retired stow tree and not installed any more` | An untracked file is still under `stow/` and nothing in `$HOME` links to it. It is yours: move it where it belongs (often the same path under `$HOME`), or delete it. `/stow/` is gitignored, so it is never published. |
| `XDG_CONFIG_HOME: it is ..., but dotfiles installs into ~/.config` | git and other tools read their config from `$XDG_CONFIG_HOME`, so they miss the shared files. Unset it (usually in `~/.zshrc.local`) or set it to `~/.config`. |
| `add this line so it loads the shared configuration` | An entry point that existed before the stub. Add the named line; the engine never edits a stub once it exists. |
| `.bashrc: add this line` on Linux | The distribution's `~/.bashrc` from `/etc/skel` existed first. Add the line at the top, above its `case $- in` (or `[ -z "$PS1" ] && return`) guard, which returns early in non-interactive shells. Login bash loads `env.sh` through `~/.bash_profile` either way. |
| `skipped until these settings have values` | A required setting has no value. Set it in a profile or `machine.toml`; secrets are `{ secret = "op://..." }` references. |
| `no machine manifest at ...` (exit 2) | This machine has no `~/.config/dotfiles/machine.toml`. Run `dotfiles init --profiles <names>` with this machine's profiles (see the README's machine table); apply refuses to guess, since no profiles would remove everything they install. |
| `a link to ... is in the way` | A link that points outside the repository sits where a link, copy or stub goes. Check what it points at, remove it if it is stale, and run `dotfiles apply`. |
| `unfold` and `move-home` in the output | Expected once per machine: a directory the old stow layout had linked into the repository becomes a real directory, and the untracked files tools wrote through it (such as gh's `hosts.yml`) move into it. Tracked files are never moved. A leftover `<dir>.dotfiles-unfold-<pid>` directory means a run died mid-unfold: compare it with `<dir>`, move any missing file into `<dir>`, then delete it. |
| Exit status 2 | The manifests are invalid or contradict each other; the message names the file, key or features. |
| `another dotfiles apply holds ...apply.lock` | Another run is in progress (sync, or a manual run). Wait, or raise `--lock-wait`. The lock is released when that process exits; never delete the file by hand. |
| `state ... has version N` | The state file is from a different engine build. Rebuild `dotfiles` from the current checkout. |

## Shell troubleshooting

| Symptom | Check and recovery |
| --------- | -------------------- |
| Shell starts without its config | `~/.zshrc`, `~/.zshenv`, `~/.zprofile` and `~/.zlogin` must be the one-line stubs and `~/.config/zsh/*.zsh` links into `features/shell.zsh/home/`. Run `dotfiles doctor`; if it says a stub is missing its line, add the line it names. |
| Slow first shell | First-run downloads are expected. Use repeated `time zsh -ic exit` for warm config load and `zinit times` in a real terminal for deferred plugins; config-load time is not full first-prompt latency. |
| Plugin load error | Inspect `zinit list` and `zinit times`, then repair/update the named plugin or cache rather than deleting unrelated plugin data. |
| Unexpected history key | Inspect `bindkey '^R'` after deferred plugins load. Atuin should own it when installed; otherwise FZF can own it. |
| Missing Rust toolchain | Run `rustup default stable` after a fresh Rustup install. |
| `gh auth status`: "The token in default is invalid" over SSH | gh found no token. It is usually in the login keychain, which SSH sessions can't read while it is locked (`security show-keychain-info` fails with "User interaction is not allowed"), and git's `osxkeychain` helper reports `failed to store: -25308` for the same reason. Log in once with file storage as shown in [Git identity and signing](#git-identity-and-signing). |
| A `gh` scope disappeared | `gh auth login` issues a new token with only the default scopes. Add scopes with `gh auth refresh -h github.com -s <scope>`, which keeps the existing ones; see [Git identity and signing](#git-identity-and-signing) for the set this setup uses. |

Before publishing, run the [validation commands](../README.md#validation) and
review `git diff`. Update configuration tables when defaults or interfaces change.
