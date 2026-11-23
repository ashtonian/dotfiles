# Dotfiles operations

## Configuration

The bootstrap installer fixes its checkout at `~/.dotfiles` and backup root at
`~/.sync`. Runtime overrides below apply only to the listed scripts; they do not
relocate the installer or rewrite LaunchAgent templates.

| Variable | Type | Default | Scope / effect |
| ---------- | ------ | --------- | ---------------- |
| `DOTFILES_DIR` | Directory path | `~/.dotfiles` | Sync, updater, and the `dotfiles` engine's repository (`--repo`); sync resolves the physical path |
| `SYNC_DIR` | Directory path | `~/.sync` | Sync's auxiliary repos |
| `DOTFILES_BIN` | File path | `~/.local/bin/dotfiles` | The engine binary sync builds from the checkout (when `go.mod`, `go.sum`, `cmd/` or `internal/` is newer than it) and runs as `dotfiles apply`; `install.sh`, `bin/otel-agent` and `bin/agent-monitor` run the same path |
| `DOTFILES_LAUNCHCTL` | File path | `/bin/launchctl` | The launchctl the engine runs to load and unload LaunchAgents; tests point it at a stand-in |
| `XPC_SERVICE_NAME` | launchd label | set by launchd in a job's processes | The job a `dotfiles apply` runs in. apply never reloads or unloads that job, which would stop the run; a later apply outside it does ([LaunchAgents](#launchagents)) |
| `DOTFILES_PROFILES` | Comma-separated names | unset | `install.sh`: the profiles to write, as `--profiles` does; without either it keeps an existing manifest or asks |
| `SYNC_QUIET_MINUTES` | Minutes | `30` | Sync skips a repository whose newest tracked edit is younger than this, so half-finished work is not committed |
| `SYNC_CONNECTIVITY_URL` | URL | `https://github.com` | Sync's reachability check, a HEAD request before any network step; set it in the `dotfiles.sync` template's `EnvironmentVariables` to probe another host |
| `SYNC_CONNECTIVITY_TIMEOUT` | Seconds | `15` | How long that HEAD request may take (connecting is capped at 5 s) before sync logs "No network connectivity" and skips the run |
| `XDG_STATE_HOME` | Directory path | `~/.local/state` | `dotfiles/applied.json` is what `dotfiles apply` installed, LaunchAgents included (`bin/disk-hygiene` reads their log paths from it), and `dotfiles/apply.lock` serialises runs |
| `XDG_CONFIG_HOME` | Directory path | `~/.config` | Not followed: the engine, sync and the installer always use `~/.config` (the stubs and the shared git and ssh configs name it), with `~/.config/dotfiles/machine.toml` as this machine's manifest and `~/.config/dotfiles/generated/` for the generated outputs. `zshrc.zsh` loads its modules from its own directory. git reads `$XDG_CONFIG_HOME/git/config`, so `dotfiles doctor` reports a value other than `~/.config` |
| `DOTFILES` | Directory path | `~/.dotfiles` | Zsh's shell-library source directory |
| `XDG_DATA_HOME` | Directory path | `~/.local/share` | Zinit installation and weekly update lookup; mise's tools and shims (`mise/`) |
| `MISE_DATA_DIR` | Directory path | `$XDG_DATA_HOME/mise` | mise's installed tools and `shims/`, which `env.sh` puts on PATH |
| `XDG_CACHE_HOME` | Directory path | `~/.cache`; in a drive session's shells, `DOTFILES_CACHE_HOME` | Cached Helm completion and tool init scripts (`zsh/init-*.zsh`); delete one to force regeneration. Every XDG-aware tool caches here, and `bin/disk-hygiene` deletes a tool's directory once nothing in it was used for `DISK_HYGIENE_CACHE_DAYS` |
| `CLAUDE_CODE_TMPDIR` | Directory path | unset (`/tmp`); `claudemore`/`claudemax` set `<drive>/tmp` for a session whose working directory is on a drive under `/Volumes` | Base of Claude Code's per-session scratch, `claude-<uid>/<project>/<session>`. `bin/disk-hygiene` deletes a session's scratch unused for `DISK_HYGIENE_SCRATCH_DAYS` |
| `DOTFILES_CACHE_HOME` | Directory path | unset; `claudemore`/`claudemax` set `<drive>/cache/xdg` alongside `CLAUDE_CODE_TMPDIR` | `env.sh` exports it as `XDG_CACHE_HOME` in that session's shells, so the commands an agent runs cache on the drive it works on. The `claude` process keeps `~/.cache`: it stages its own updates there. Ignored unless the directory exists |
| `GITSTEAD_CACHE` | Directory path | `$XDG_CACHE_HOME/gitstead` as it was before `DOTFILES_CACHE_HOME` moved it | gitstead's workspace records. `env.sh` pins it when it moves `XDG_CACHE_HOME`, so every shell uses the same records |
| `HISTFILE` | File path | `~/.zsh_history` | Shared shell history |
| `GOPATH` | Directory path | `~/go` | Go workspace and its bin path |
| `GOTOOLCHAIN` | Go toolchain selection | `auto` | Run the Go on PATH (mise's pinned release, or a project's `.go-version`) unless the module's `go.mod`/`go.work` needs a newer one, which the `go` command downloads through `GOPROXY`, checked against `GOSUMDB`; `local` never switches. Setting `go.toolchain` (feature `tool.mise`), exported by the generated `env.sh` for every shell and agent; a value already in the environment wins |
| `DOTFILES_MISE_CANARY` | LocalHostName | empty; the base profile sets `studio` | `dotfiles-update.sh`: the one machine whose weekly run moves the Go pin in `conf.d/dotfiles.toml` to its minor's newest patch and commits it. Setting `mise.canary` (feature `tool.mise`), exported by the generated `env.sh` |
| `PLAYWRIGHT_BROWSERS_PATH` | Directory path | unset (Playwright's own default); the `studio` profile sets `/Volumes/E2TB/cache/ms-playwright` | Browser builds Playwright downloads. Setting `paths.playwright_browsers` (feature `shell.env`), exported by the generated `env.sh`; a value already in the environment wins |
| `GO_CACHE_TRIM_HOURS` | Whole hours, at least 2 | `24` | `bin/go-cache-trim`: delete Go build cache entries unused this long; set in the `tool.go-cache-trim` feature's template |
| `DISK_HYGIENE_SCRATCH_DAYS` | Whole days, at least 1 | `7` | `bin/disk-hygiene`: delete a Claude Code session's scratch once nothing in it was used this long; set in the `macos.disk-hygiene` feature's template |
| `DISK_HYGIENE_CACHE_DAYS` | Whole days, at least 1 | `14` | `bin/disk-hygiene`: delete a tool's cache directory, a key of a keyed cache, or a goimports or pnpm cache file once unused this long; set in the template |
| `DISK_HYGIENE_KEYED` | Space-separated names | `jobcrm estavelle` | Cache directories holding one subdirectory per branch, agent or tool version; `bin/disk-hygiene` prunes these a subdirectory at a time instead of whole. Empty: none |
| `DISK_HYGIENE_KEEP` | Space-separated names | empty | Cache directories `bin/disk-hygiene` never deletes, for a cache that is expensive to rebuild and used less often than the window |
| `DISK_HYGIENE_LOG_MAX_BYTES` | Whole bytes, at least 1 | `1048576` | Each LaunchAgent `dotfiles apply` installed has its stdout and stderr log cut to its newest half once larger than this |
| `DISK_HYGIENE_TMP` | Directory path | `/private/tmp` | Where sessions started without `CLAUDE_CODE_TMPDIR` keep their scratch |
| `DISK_HYGIENE_VOLUMES` | Directory path | `/Volumes` | Its directories are the drives whose `tmp`, `cache/xdg` and `.pnpm-store` `bin/disk-hygiene` prunes |
| `GPG_AGENT_SUPERVISOR_SECONDS` | Whole seconds, at least 1 | `10` | `bin/gpg-agent-supervisor`: how often it checks that the running gpg-agent is the one it started in the GUI login, and replaces it if not; set in the `tool.gpg-agent` feature's template |
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
| `--launchctl-timeout` | Duration | `30s` | `apply`, `doctor`: how long one launchctl call may take; a bootstrap is tried five times, 0.25 s to 1 s apart |
| `--launch-agents` | Boolean | `true` | `apply`: install, load and remove LaunchAgents. `false` leaves them, and their records, as they are; `install.sh` applies so before installing packages |
| `--json` | Boolean | `false` | `status`: print JSON |

OpenCode's [config tables](../features/agents.opencode/README.md#config) cover its bind
address, port, gateway files, worker binaries, concurrency, and retention. The
agent dashboard's are in [AGENT-MONITOR.md](AGENT-MONITOR.md#config), and the agent
telemetry collector's in [AGENT-TELEMETRY.md](AGENT-TELEMETRY.md#config).
LaunchAgents do not read `~/.zshrc.local`. Set a service's variables in its
template's `EnvironmentVariables` (`features/<id>/launchagents/`); the next
`dotfiles apply` writes the plist and reloads the job. apply never overwrites an
installed plist edited by hand: it reports it every run and leaves it loaded.

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
background job, and register its public key with GitHub. On macOS the key's
passphrase comes from pinentry-mac: tick "Save in Keychain" in its dialog once
and it reads the passphrase from the login keychain from then on. pinentry-mac
can do that only for a gpg-agent running in the GUI login, so the
`com.ashtonian.gpg-agent` LaunchAgent keeps one there for SSH sessions, agents
and launchd jobs to sign through ([GPG agent](#gpg-agent)). The commit email must
match an email on the signing key that is verified on the GitHub account.
For deliberate manual commits, use `git commit -S` and `git verify-commit HEAD`.
After a GitHub push, inspect its Verified badge or API status too.

Git uses gh for `github.com` and `gist.github.com` credentials, so one gh login
covers both. The `tool.gh` feature's fragment of the generated git config sets
the helpers (`features/tool.gh/gitconfig`). It comes after `git.keychain`'s
`osxkeychain` and clears it for those two hosts, so no `gh auth setup-git` is
needed. Besides gh's defaults (`repo`, `read:org`, `gist`, `workflow`), this
setup uses `project` for GitHub Projects, `write:gpg_key` for registering the
signing key, and `admin:public_key` and `admin:ssh_signing_key` for the SSH key
upload helper. Log in once with all of them:

```sh
gh auth login -h github.com --insecure-storage \
  -s project,write:gpg_key,admin:public_key,admin:ssh_signing_key
```

`--insecure-storage` keeps the token in `~/.config/gh/hosts.yml` (mode 0600,
outside this repo; the engine installs gh's settings file by file, so
`~/.config/gh` is a real directory) instead of the login keychain, which SSH
sessions can't read while it is locked. To add a scope later, run
`gh auth refresh -h github.com -s <scope>`, which keeps the existing ones.
Running `gh auth login` again issues a token with only the defaults.

## LaunchAgents

`dotfiles apply` installs, loads, reloads and removes this repository's
LaunchAgents. Each is a template in the feature that declares it
(`[[provides.launch_agent]]`, see
[MACHINE-FEATURES.md](MACHINE-FEATURES.md#launchagents)); apply replaces `$HOME`
in it, writes `~/Library/LaunchAgents/<label>.plist`, creates the directories of
its `StandardOutPath` and `StandardErrorPath` under `$HOME` (launchd does not),
and bootstraps it into `gui/<uid>`. Every sync runs apply, so a pulled template
change reaches each Mac within one sync, and a Mac gets every agent its
profiles enable without running an installer.

| Label | Feature (profile) | Runs | Installed once these exist |
| ----- | ----------------- | ---- | -------------------------- |
| `com.dotfiles.sync` | `dotfiles.sync` (base) | Every 4 hours and at load | |
| `com.dotfiles.update` | `dotfiles.update` (base) | Fridays 09:00, or at wake | |
| `com.ashtonian.disk-hygiene` | `macos.disk-hygiene` (base) | Daily 04:15, or at wake | |
| `com.ashtonian.go-cache-trim` | `tool.go-cache-trim` (base) | Hourly and at load | `/opt/homebrew/bin/go` |
| `com.ashtonian.gpg-agent` | `tool.gpg-agent` (base) | Service, GUI login only | `/opt/homebrew/bin/gpgconf` |
| `com.ashtonian.codex-remote-control` | `agents.codex` (dev) | Service | `/opt/homebrew/bin/codex` |
| `com.ashtonian.agent-monitor` | `agents.agent-monitor` (dev) | Service, while the data link resolves | `agent-monitor install`'s release |
| `com.ashtonian.agent-monitor-gate` | `agents.agent-monitor` (dev) | Service | `agent-monitor lan enable`'s token |
| `com.ashtonian.opencode` | `agents.opencode` (desktop) | Service | opencode, and its `server-password` ([setup](../features/agents.opencode/README.md)) |
| `com.ashtonian.otel-agent` | `agents.otel-agent` (desktop) | Service, while enrolled | `otel-agent enroll`'s endpoint, token and host |

On each run, for each agent its features declare:

- **Waiting for a path.** Until every `when_exists` path exists, apply leaves the
  agent out, and unloads and removes one it installed before. `dotfiles doctor`
  lists it: `waiting <label>: installs once <path> exists`.
- **Not loaded.** apply loads it. An agent booted out by hand is loaded again at
  the next apply: to stop one, turn its feature off (below).
- **Template changed.** apply writes the new plist and reloads the job, which
  restarts a service. A change to comments or layout only (no key or value
  changed) rewrites the file without a reload. Two reloads wait for a later apply, and `dotfiles doctor`
  lists both: the job the run executes in (`XPC_SERVICE_NAME`), so a change to
  the sync job's own plist takes effect at the weekly update's sync or at a
  `dotfiles apply` from a terminal; and a scheduled job in the middle of a run,
  which reloads once the run ends. Neither is a problem.
- **Feature off.** apply unloads and removes the agent; a scheduled job in the
  middle of a run finishes first.
- **Edited by hand.** An installed plist that differs from what apply last
  wrote is a problem: apply leaves it in place and loaded, and reports it on
  every run until the change moves into the template or the file is deleted.

The retired `bin/dotfiles-install-launchagents.sh` wrote the same paths. The
first apply on a Mac it set up takes its plists over: one defining the
template's job is recorded as loaded (rewritten if its comments differ), one
that differs in a key or value is rewritten and reloaded, and
one whose feature is off here, or whose `when_exists` path is missing, is
unloaded and removed. `applied.json` keeps, per label, the plist's path, the hash
apply wrote and a fingerprint of the job launchd last loaded, so its size is bounded by the
agents the features declare.

macOS asks once for some of these jobs; answer on the Mac's screen:

| Agent | Prompt or grant |
| ----- | --------------- |
| `com.dotfiles.sync`, `com.dotfiles.update`, `com.ashtonian.disk-hygiene` | Allow `bash` to access files on a removable volume (Go caches on a drive, the drives' `tmp` and `cache/xdg`) |
| `com.ashtonian.codex-remote-control` | Full Disk Access for `~/.local/libexec/codex-stable/bin/codex` ([Codex service](#codex-service)) |
| `com.ashtonian.opencode` | Full Disk Access for `~/.local/libexec/opencode-stable/bin/opencode` |
| `com.ashtonian.agent-monitor` | Allow node to access the data volume; the gate: allow node to accept incoming connections |
| `com.ashtonian.otel-agent` | Allow `otelcol-contrib` to find devices on the local network, once per release |

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

`com.ashtonian.disk-hygiene` runs `bin/disk-hygiene` every day at 04:15, or at
wake when the Mac slept through it. Nothing else removes what agent sessions
and repository scripts leave behind, so each run deletes:

- a Claude Code session's scratch (`<tmp>/claude-<uid>/<project>/<session id>`)
  unused for `DISK_HYGIENE_SCRATCH_DAYS` (7), in `/private/tmp` and in each
  drive's `tmp`. Other entries there, such as Claude Code's bundled skills, stay.
- a tool's cache directory in `~/.cache` and in each drive's `cache/xdg` unused
  for `DISK_HYGIENE_CACHE_DAYS` (14), whole, because one entry can depend on
  another. A keyed cache (`DISK_HYGIENE_KEYED`: one directory per branch, agent
  or tool version) loses only its unused keys. Symlinks and the names in
  `DISK_HYGIENE_KEEP` stay.
- goimports index files and pnpm metadata files unused for the same window.
- packages no project links any more, through `pnpm store prune` on
  `~/Library/pnpm/store` and each drive's `.pnpm-store`, unless a pnpm is
  running. It uses the pnpm on PATH or the newest one corepack has cached, and
  skips the stores when neither runs. The plist's PATH ends with mise's shims,
  which supply pnpm and the node corepack's pnpm needs. A log line `no pnpm on
  PATH or in a corepack cache` means none of them runs outside a project:
  check `cd / && ~/.local/share/mise/shims/pnpm --version`.

Unused means no file was read or written and no directory gained or lost an
entry in the window; the internal disk and the external drives record access
times, so a cache that is only read stays. A directory holding a socket stays,
and so does one the job cannot read all of.

It also cuts the stdout and stderr log of each LaunchAgent `dotfiles apply`
installed (the agents in `applied.json`, at the paths in their installed
plists) to the newest half once over `DISK_HYGIENE_LOG_MAX_BYTES` (1 MiB).
launchd holds those files open for appending, so the cut rewrites the file in
place; moving it aside would leave the agent writing to the moved file.

Each run logs what it removed and a total line to
`~/Library/Logs/disk-hygiene/disk-hygiene.log`; `bin/disk-hygiene --dry-run`
reports what a run would remove. A run that could not remove something exits 1
and logs `could not remove`: usually a file another user owns, or a drive that
dropped mid-run; `launchctl print "gui/$(id -u)/com.ashtonian.disk-hygiene"`
shows the last exit code. If a tool rebuilds a large cache every few weeks,
add its directory name to `DISK_HYGIENE_KEEP` in the template
(`features/macos.disk-hygiene/launchagents/`); the next apply reloads the job.
macOS asks once for bash to read
removable volumes; until that is allowed, the drives' entries are skipped.

A `claudemore` or `claudemax` session started in a directory on a drive under
`/Volumes` (`~/workgroups` resolves to E2TB) keeps its scratch in `<drive>/tmp`
(`CLAUDE_CODE_TMPDIR`) and its commands' caches in `<drive>/cache/xdg`
(`DOTFILES_CACHE_HOME`, which `env.sh` exports as `XDG_CACHE_HOME` in the
session's shells). A session already running keeps what it started with until
it restarts. Tools that ignore `XDG_CACHE_HOME` on macOS, such as Go's
`os.UserCacheDir` users (gopls, goimports, golangci-lint), keep using
`~/Library/Caches`.

Turn an agent off on one Mac by disabling its feature in
`~/.config/dotfiles/machine.toml`, then apply; remove the line to turn it back on
(the sync job's RunAtLoad starts a sync as it loads):

```toml
[features]
disable = ["dotfiles.sync"]
```

Inspect or trigger a loaded job:

```sh
dotfiles doctor                                   # pending changes and waiting agents
launchctl print "gui/$(id -u)/com.dotfiles.sync"
launchctl kickstart "gui/$(id -u)/com.dotfiles.sync"
tail -50 ~/.dotfiles/logs/sync.log
```

Idle scheduled jobs usually have no PID; check their last exit status and log.
`sync.sh check` tests the lock, but also creates runtime directories and may
rotate an oversized sync log. Busy locks and failed connectivity checks return
success; operation errors return nonzero. Other repositories may still sync
when one fails. The sync and update logs (`logs/sync.log`, `logs/update.log`)
rotate above 1 MiB and keep three archives each (`lib_sh/rotate-log.sh`).
LaunchAgent stdout and stderr logs are capped daily by `bin/disk-hygiene`.
There is no metrics endpoint for sync or updates.

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
template sets a soft limit of 65,536. `dotfiles apply` reloads the job when the
template changes; `kickstart -k` alone keeps the previously loaded settings. If sessions repeatedly
drop, inspect the log and `launchctl list` for duplicate jobs before removing a
specific stale job. OpenCode has separate [operations instructions](../features/agents.opencode/README.md#operations),
and so do the [agent dashboard](AGENT-MONITOR.md#operations) and the
[telemetry collector](AGENT-TELEMETRY.md#operations).

### GPG agent

`com.ashtonian.gpg-agent` runs `bin/gpg-agent-supervisor` in the GUI login
whenever gnupg is installed. pinentry-mac reaches the login keychain and shows
its dialog only for a gpg-agent started in that login. One started from an SSH
session can do neither, and every signature through it fails with
`gpg: signing failed: No pinentry`. gpg, git and the zsh gpg-agent plugin
(which queries the agent before every command) start an agent from whichever
shell needs one first, which on a host reached over SSH is usually an SSH
session.

At load, the supervisor replaces the running agent with one it starts, then
every `GPG_AGENT_SUPERVISOR_SECONDS` (10) checks the PID answering on gpg's
socket and replaces any other agent. An agent started elsewhere can therefore
fail signatures for at most that long. Each replacement drops the agent's
cached passphrases; pinentry-mac reads them back from the keychain on the next
signature, or asks on the Mac's screen if the passphrase was never saved.
Reloading the LaunchAgent (apply does when its template changes) replaces the
agent the same way. Stopping the supervisor leaves its agent running.

The LaunchAgent runs only while someone is logged in at the Mac's screen.
After a restart, log in there (unlocking FileVault does) before signing from
an SSH session.

```sh
launchctl print "gui/$(id -u)/com.ashtonian.gpg-agent"   # state = running
tail -20 ~/Library/Logs/gpg-agent/supervisor.log         # starts and replacements
gpg-connect-agent 'getinfo pid' /bye                     # the PID the log last started
```

Replacements logged again and again (`is gone; starting another`, or `was
started outside this login`) mean something keeps stopping the agent: look for
`gpgconf --kill gpg-agent` in scripts and scheduled jobs.
`gpg-agent did not start` means the agent cannot listen on its socket: run
`gpgconf --list-dirs agent-socket` and check that `~/.gnupg` exists with mode
0700.

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
   Node, so agents and LaunchAgents that run `node` or `npx` need it. Sync runs
   `mise install` from then on.

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

The first `dotfiles apply` takes over the sync and update agents' plists and
reloads any that differ from the templates ([LaunchAgents](#launchagents)):
plists from before the rollout run `bash -l`, whose `path_helper` puts Apple's
bash 3.2 and git ahead of Homebrew's. Where Go's caches are on an external volume (`go env GOCACHE`),
the first run asks whether `bash` may access files on a removable volume: the
job runs Homebrew's bash, and macOS holds it responsible for every step. Allow
it on the machine's screen (System Settings > Privacy & Security > Files and
Folders lists it afterwards). Until someone answers, the job waits in its first
Go command. macOS ties the grant to that build of bash, so a `brew upgrade bash`
can ask again.

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
| `gpg: signing failed: No pinentry` | The gpg-agent that answered runs outside the GUI login, where pinentry-mac cannot reach the keychain or show a dialog. Check `launchctl print "gui/$(id -u)/com.ashtonian.gpg-agent"`: not found means `dotfiles doctor` shows why apply has not loaded it (gnupg missing, or the `tool.gpg-agent` feature off); running means the supervisor replaces that agent within `GPG_AGENT_SUPERVISOR_SECONDS`, so retry. If nobody is logged in at the Mac's screen, log in there. If pinentry-mac asks on every signature, tick "Save in Keychain" in its dialog ([GPG agent](#gpg-agent)). |
| GitHub reports bad_email | Correct the affected commit to a signing-key email verified on GitHub. Keep a backup ref before any authorized history repair. |
| GitHub verification fails after push | Publication already occurred. Inspect the reason and GitHub status; repair only affected commits within authorized history scope. |
| Merge conflict | Automation aborts the merge. Resolve and sign the integration deliberately. Dotfiles has no conflict preference; auxiliary repos use local-preferred conflicting hunks (`-X ours`). |
| Push rejected | Check permissions and remote changes. Sync tries at most three times with fetch and signed merge; it never force-pushes. |
| Excluded tracked changes remain | Review tracked `*.local`, `.env*` or `*.secret*` paths in any directory. Sync skips merge/push while excluded tracked changes remain. |
| Sync leaves a repository alone | The log says why: a Git index lock (another Git command is running, or one crashed and left `.git/index.lock`; check `ps` before removing it), or a tracked edit newer than `SYNC_QUIET_MINUTES`. The next run picks it up. |
| `No network connectivity (... did not answer within ...s), skipping sync` | The HEAD request to `SYNC_CONNECTIVITY_URL` failed. Check `curl -sfI https://github.com` from a terminal; if it answers only slowly, raise `SYNC_CONNECTIVITY_TIMEOUT` in the `dotfiles.sync` template. The next run retries. |
| Sync never finishes; `ps` shows a Go command at 0% CPU under it | macOS is waiting for an answer to "bash would like to access files on a removable volume" because Go's caches are on an external drive. Answer it on the machine's screen, or allow `bash` under System Settings > Privacy & Security > Files and Folders. `log show --last 1h --predicate 'subsystem == "com.apple.TCC"' \| grep AUTHREQ_PROMPTING` names the binary it is waiting on; after a `brew upgrade bash` it is the new build. |
| New files are not published | By design: sync stages tracked files only (`git add -u`). Commit new files yourself. |
| `installs machine features and this machine has no .../machine.toml` | Upstream uses the feature engine and this machine has no manifest, so sync neither merges nor pushes (merging would leave the old stow links pointing at moved files). Write `~/.config/dotfiles/machine.toml` with this machine's profiles from the list in the message, such as `profiles = ["base", "dev", "desktop"]`, then run `sync.sh`: the same run merges and applies. |
| `installs machine features and Go is not installed to build its engine` | Sync builds the upstream engine before merging it and found no `go` on its PATH, so it neither merges nor pushes. Install Go (`brew install go`; the LaunchAgent's PATH includes `/opt/homebrew/bin`), then run `sync.sh`. |
| `engine does not build with this machine's Go or cannot plan ...machine.toml` | The lines above it are the build error or `dotfiles check`'s message. A build error usually means Go is older than `go.mod` (sync uses `GOTOOLCHAIN=local`): upgrade Go. A plan error (exit 2) names the profile, feature or setting in `machine.toml` that upstream no longer accepts: fix the manifest. Nothing was merged; rerun `sync.sh`. |
| `Building ~/.local/bin/dotfiles failed` / `Go is not installed` | Sync builds the engine with the installed Go and `GOTOOLCHAIN=local`, so it never downloads a toolchain. Install or upgrade Go to the version in `go.mod` (`brew install go`), then rerun `sync.sh apply`. |
| `dotfiles apply left problems to resolve` | The log above lists them; see [Feature engine troubleshooting](#feature-engine-troubleshooting). Sync carries on with packages and the other repositories. |
| `the telemetry collector did not converge` | The line above it is `otel-agent converge`'s reason: `no host name configured` means the Mac was enrolled before per-host tokens, so run `~/.dotfiles/bin/otel-agent enroll <studio\|mbp\|mini>`; a download or checksum error is retried by the next sync. See [Agent telemetry](AGENT-TELEMETRY.md#operations). Sync carries on with the other steps. |
| Theme repo cannot push | Installer theme clones point at upstream projects. Use an owned fork as origin before publishing local changes. All immediate Git repos under `SYNC_DIR` participate. |
| Package install fails | Run the check below. Check App Store sign-in and tapped/private package access; sync does not upgrade existing packages. |
| `Refusing to load formula ... from untrusted tap` | Homebrew loads third-party tap items only once trusted. The generated Brewfile trusts every `brew` or `cask` a feature names in full (`user/repo/name`); an item listed by its short name cannot be trusted that way, so name it in full in its feature. Trusted entries are in `~/.homebrew/trust.json` (`brew trust --json=v1` lists them). |
| `WARN: Left cask <name>, mas <app> (<id>) for a terminal` | Expected under the LaunchAgent, which has no terminal for sudo to ask a password in: a cask whose install runs a `.pkg`, a keyboard layout or a `sudo` installer step, and every App Store app (mas 7 installs as root), wait instead of failing the run, and sync still exits 0. Run the command the line ends with from a terminal (`brew bundle install --file=...`); later syncs find them installed. A run with passwordless sudo, or from a terminal, installs them itself. |
| `Installing <cask> has failed!` with `sudo is disabled by HOMEBREW_NO_SUDO` | The cask needs root for a step the pkg/installer check above does not see. Install it from a terminal (`brew install --cask <cask>`). |
| `Could not tell which of Brewfile's missing casks need root` | `brew info --json=v2 --cask` failed for a missing cask, usually one renamed or removed upstream; the lines above name it. Fix the feature's entry. Root-needing casks then fail with `HOMEBREW_NO_SUDO` instead of waiting, and sync reports an error until then. |
| `Could not symlink ...` / `is a symlink belonging to <formula>` | Another installed formula owns the same files, usually the one a feature's entry replaced (`tldr` for `tlrc`). `brew uninstall <old formula>`, then `brew link <new formula>`. |
| `mise could not install every tool` | Sync installs what `conf.d/dotfiles.toml` and `~/.config/mise/config.toml` name after the Brewfile. Run `mise -C ~ install` from a terminal for the full error: usually no network, or a pin (such as a Go release) that does not exist. The next sync retries. |
| `go: downloading go1.X.Y` in a build | A module's `go.mod` or `go.work` needs a newer Go than the pin, and `GOTOOLCHAIN=auto` fetched it (once per release, into the module cache). Expected for a module ahead of the fleet; to run it everywhere, raise the pin's minor. With `GOTOOLCHAIN=local` the same module fails with `requires go >= ...`. |
| `go version` is not the pin in a checkout | `mise ls go` names the file that selected it: a `.go-version` or `mise.toml` there pins its own, or the module needs a newer Go (row above). A session started before an update keeps the `GOTOOLCHAIN` it inherited until it restarts. |
| `The Go pin moves on the canary machine only` | Expected everywhere but the canary (`mise.canary`). On the canary, the update log names why a newer patch was left: the checkout is off its tracking branch, `conf.d/dotfiles.toml` has uncommitted edits, or the release would not install or run. Fix that and run `dotfiles-update.sh --go`. |
| `Full update finished; failed stages: ...` | Every stage (Homebrew, the Go pin, Zinit, sync) runs whatever the others did; the run exits 1 when any failed, and `logs/update.log` has each one's `ERROR:` lines. Within Homebrew, update, the formula and cask upgrades, and cleanup each run regardless. Rerun one stage with `dotfiles-update.sh --brew`, `--go`, `--zinit` or `--sync`. |
| `brew upgrade --formula failed for <name>` | When one run of `brew upgrade` fails, each item still outdated is retried alone, so the others upgrade. The item's own output is above the line: `Your Xcode (...) is too outdated` means a formula that builds from source needs a newer Xcode or Command Line Tools (update Xcode from the App Store, or `sudo rm -rf /Library/Developer/CommandLineTools && sudo xcode-select --install`); anything else is the item's own error. |
| `WARN: Left <casks> for a terminal: upgrading them needs root` | Run unattended, upgrades run with `HOMEBREW_NO_SUDO`; an item that fails on it or on a permission error (an app installed root-owned) waits. Run the command the line names from a terminal. Not a failure. |
| `WARN: brew doctor reported problems` | Advisory: `brew doctor` exits 1 for any warning. Read its output above the line and fix what matters by hand (an outdated Xcode, deprecated casks); it never fails the update. |

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
| `waiting <label>: installs once <path> exists` (doctor) | Expected until the agent's setup step runs: install the package, or run the step the [LaunchAgents table](#launchagents) names. The next apply installs and loads it. |
| `waiting <label>: reloads ...` or `unloads ...` (doctor) | Expected: the job is running, so apply left the reload or removal for a later run. If it stays for days, `launchctl print "gui/$(id -u)/<label>"` shows whether a run is stuck. |
| `<label>.plist: edited here since dotfiles last wrote it` | Someone changed the installed plist; launchd keeps running that version. Move the change into the template in `features/<id>/launchagents/` (every Mac gets it), or delete the installed file; the next apply writes the template and reloads the job. |
| `launchctl bootstrap gui/<uid> ...: ... Input/output error` | launchd refused the plist five times. `plutil -lint <plist>` checks it; a job that needs the GUI login (`LimitLoadToSessionType Aqua`, gpg-agent) loads only while someone is logged in at the screen. The next apply retries. |
| `launchctl ...: signal: killed` | launchctl took longer than `--launchctl-timeout`; the next apply retries. Raise the timeout only if `time launchctl print "gui/$(id -u)"` by hand takes longer than it. |

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
