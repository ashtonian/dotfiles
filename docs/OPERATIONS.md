# Dotfiles operations

## Configuration

The bootstrap installer fixes its checkout at `~/.dotfiles` and backup root at
`~/.sync`. Runtime overrides below apply only to the listed scripts; they do not
relocate the installer or rewrite LaunchAgent templates.

| Variable | Type | Default | Scope / effect |
| ---------- | ------ | --------- | ---------------- |
| `DOTFILES_DIR` | Directory path | `~/.dotfiles` | Sync, updater, LaunchAgent installer; sync resolves the physical path |
| `SYNC_DIR` | Directory path | `~/.sync` | Sync's auxiliary repos and app backups |
| `MACKUP_CONFIG_FILE` | File path | `~/.mackup.cfg` | Base config for the temporary host-specific backup configuration |
| `DOTFILES` | Directory path | `~/.dotfiles` | Zsh's shell-library source directory |
| `XDG_CONFIG_HOME` | Directory path | `~/.config` | Zsh module directory; Stow still targets the default home layout |
| `XDG_DATA_HOME` | Directory path | `~/.local/share` | Zinit installation and weekly update lookup |
| `XDG_CACHE_HOME` | Directory path | `~/.cache` | Cached Helm completion |
| `HISTFILE` | File path | `~/.zsh_history` | Shared shell history |
| `GOPATH` | Directory path | `~/go` | Go workspace and its bin path |
| `EDITOR` / `VISUAL` | Command | nvim if installed, else vim / `$EDITOR` | Core editor defaults from `.zshenv` |
| `PAGER` | Command | less | Core pager default |
| `LANG` | Locale string | en_US.UTF-8 | Existing value is preserved |
| `SHOW_COWSAY` | String | false | Set exactly true in `~/.zshrc.local` to enable the greeting |
| `AWS_SHARED_CREDENTIALS_FILE` | File path | `~/.aws/credentials` | AWS helper credential destination |
| `AWS_CONFIG_FILE` | File path | `~/.aws/config` | AWS helper region/profile config |
| `AGENT_SHELL` | Marker | unset; Codex exports it through `[shell_environment_policy] set` in `~/.codex/config.toml` | In a non-interactive Zsh, `.zshenv` turns off `NOMATCH`, `BAD_PATTERN`, `EQUALS` and turns on `SH_WORD_SPLIT` (bash semantics for model-written commands), then unsets the marker so scripts it runs keep Zsh semantics |

OpenCode's [config tables](../stow/opencode/README.md#config) cover its bind
address, port, gateway files, worker binaries, concurrency, and retention. The
agent dashboard's are in [AGENT-MONITOR.md](AGENT-MONITOR.md#config).
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

## LaunchAgents

Use these options with `~/.dotfiles/bin/dotfiles-install-launchagents.sh`:

| Option | Behavior |
| -------- | ---------- |
| No options | Install/reload all eligible agents; sync starts at load |
| `--sync-only` / `--update-only` | Install/reload one scheduled job |
| `--codex-only` / `--opencode-only` / `--agent-monitor-only` / `--agent-monitor-gate-only` | Install/reload one service if prerequisites exist |
| `--status` | Show installed/loaded/running state and recent logs |
| `--uninstall` | Unload and remove all six installed agent plists |
| `--help` | Show supported options |

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
and so does the [agent dashboard](AGENT-MONITOR.md#operations).

## App backups

Mackup's shared config uses filesystem storage at `~/.sync/mackup`. Sync gives
Mackup a temporary config with the selected `SYNC_DIR` and
`mackup/<LocalHostName>` directory, runs `backup --force`, and deletes the temp
config. The stowed config and original app files remain in place.

All supported, detected apps are included except those listed in
`[applications_to_ignore]`. App preferences can contain tokens even when the
files are not called credentials. Review exclusions and backed-up contents.

### Configure a private backup remote

The installer initializes `~/.sync/mackup` without a commit, invented identity,
or remote. Local backup works before remote sync is configured.

For an existing backup, clone its private repository into `~/.sync/mackup` before
running the installer. For a new backup, create an empty private remote and
complete signing setup first. Then substitute its actual URL below:

```sh
git -C ~/.sync/mackup remote add origin 'PRIVATE_BACKUP_REPOSITORY_URL'
~/.dotfiles/sync.sh mackup
git -C ~/.sync/mackup status --short
```

Review contents and exclusions, then commit any pending changes. A loaded sync
job may already have made a signed local commit; skip the commit step when the
working tree is clean, and verify the existing commit before publishing:

```sh
git -C ~/.sync/mackup add -A
git -C ~/.sync/mackup diff --cached --stat
git -C ~/.sync/mackup commit -S -m 'Start app configuration backups'
git -C ~/.sync/mackup verify-commit HEAD
git -C ~/.sync/mackup push --set-upstream origin HEAD
```

Check GitHub verification after the push. Automatic sync requires a same-named
origin tracking branch. Keep this remote private; only dotfiles gets Gitleaks
scans in `sync.sh`.

### Restore app settings

Plain `mackup restore` reads the shared unpartitioned directory, not the host
directory used by `sync.sh`.

1. Fetch the private backup repo and choose an existing source-host directory.
   Its name does not need to match the destination Mac.
2. Copy the shared config so its exclusions are retained, then edit the copy:

   ```sh
   cp "$HOME/.mackup.cfg" "$HOME/.mackup.restore.cfg"
   vi "$HOME/.mackup.restore.cfg"
   ```

3. Set the storage section to the selected source. Use the actual backup root
   if it differs from `~/.sync`:

   ```ini
   [storage]
   engine = file_system
   path = .sync
   directory = mackup/SOURCE_LOCAL_HOST_NAME
   ```

4. Quit the affected apps and preview the restore:

   ```sh
   mackup --config-file="$HOME/.mackup.restore.cfg" --dry-run restore
   ```

5. Preserve any destination settings needed, then restore interactively:

   ```sh
   mackup --config-file="$HOME/.mackup.restore.cfg" restore
   ```

Edit the matching app-selection section of `.mackup.cfg` to change what is
backed up. `mackup list` lists supported names; `mackup show APP` shows paths.
Adding `[applications_to_sync]` makes an explicit allowlist. A named command
such as `mackup backup APP` overrides app selection/exclusions, so review that
app's paths first. Avoid `mackup link` for this copy-based workflow.

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
| Excluded tracked changes remain | Review tracked *.local, .env*, or *.secret* paths. Sync skips merge/push while excluded tracked changes remain. |
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
| Stow conflict | Preview with explicit `--dir` and `--target` as shown in the README. Compare and back up the conflicting file before moving it aside, then restow. Restow does not overwrite it. |
| Slow first shell | First-run downloads are expected. Use repeated `time zsh -ic exit` for warm config load and `zinit times` in a real terminal for deferred plugins; config-load time is not full first-prompt latency. |
| Plugin load error | Inspect `zinit list` and `zinit times`, then repair/update the named plugin or cache rather than deleting unrelated plugin data. |
| Unexpected history key | Inspect `bindkey '^R'` after deferred plugins load. Atuin should own it when installed; otherwise FZF can own it. |
| Missing Rust toolchain | Run `rustup default stable` after a fresh Rustup install. |

Before publishing, run the [validation commands](../README.md#validation) and
review `git diff`. Update configuration tables when defaults or interfaces change.
