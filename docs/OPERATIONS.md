# Dotfiles operations

## Configuration

The bootstrap installer fixes its checkout at `~/.dotfiles` and backup root at
`~/.sync`. Runtime overrides below apply only to the listed scripts; they do not
relocate the installer or rewrite LaunchAgent templates.

| Variable | Type | Default | Scope / effect |
| ---------- | ------ | --------- | ---------------- |
| `DOTFILES_DIR` | Directory path | `~/.dotfiles` | Sync, updater, and the `dotfiles` engine's repository (`--repo`); sync resolves the physical path |
| `SYNC_DIR` | Directory path | `~/.sync` | Sync's auxiliary repos |
| `DOTFILES_OVERLAY_DIR` | Directory path | `~/.dotfiles-overlays` | The engine's `--overlay-dir`: one overlay checkout per context, at `<dir>/<overlay>`. Sync asks the engine (`dotfiles overlays`) which to sync, so it never needs this itself |
| `DOTFILES_BIN` | File path | `~/.local/bin/dotfiles` | The engine binary sync builds from the checkout (when `go.mod`, `go.sum`, `cmd/` or `internal/` is newer than it) and runs as `dotfiles apply`; `install.sh` and `bin/otel-agent` run the same path |
| `DOTFILES_LAUNCHCTL` | File path | `/bin/launchctl` | The launchctl the engine runs to load and unload LaunchAgents; tests point it at a stand-in |
| `DOTFILES_MUXY_APP` | Directory path | unset: `~/Applications/Muxy.app` if it holds the tool, else `/Applications/Muxy.app` | The Muxy app whose `Contents/MacOS/muxy` the engine runs to read and set Muxy settings; when set, the only one tried |
| `XPC_SERVICE_NAME` | launchd label | set by launchd in a job's processes | The job a `dotfiles apply` runs in. apply never reloads or unloads that job, which would stop the run; a later apply outside it does ([LaunchAgents](#launchagents)) |
| `DOTFILES_PROFILES` | Comma-separated names | unset | `install.sh`: the profiles to write, as `--profiles` does; without either it keeps an existing manifest or asks |
| `SYNC_QUIET_MINUTES` | Minutes | `30` | Sync skips a repository whose newest tracked edit is younger than this, so half-finished work is not committed |
| `SYNC_CONNECTIVITY_URL` | URL | `https://github.com` | Sync's reachability check, a HEAD request before any network step; set it in the `dotfiles.sync` template's `EnvironmentVariables` to probe another host |
| `SYNC_CONNECTIVITY_TIMEOUT` | Seconds | `15` | How long that HEAD request may take (connecting is capped at 5 s) before sync logs "No network connectivity" and skips the run |
| `CLAUDE_CODE_INSTALLER_URL` | URL | `https://claude.ai/install.sh` | Anthropic's native Claude Code installer, which sync downloads and runs on a machine with `agents.claude` when `~/.local/bin/claude` is missing; set it in the `dotfiles.sync` template's `EnvironmentVariables` |
| `CLAUDE_CODE_INSTALL_TIMEOUT` | Seconds | `900` | How long that installer may run before sync stops it, with everything it started, and fails the step; its own downloads have no timeout |
| `UPDATE_LOCK_WAIT` | Whole seconds | `1800` | How long `dotfiles-update.sh` waits for a sync (or another update) in progress to release the sync lock, `logs/sync.flock`, before it fails without updating anything. `0` fails at once. A scheduled sync never waits: one that finds the lock held skips its run |
| `XDG_STATE_HOME` | Directory path | `~/.local/state` | `dotfiles/applied.json` is what `dotfiles apply` installed, LaunchAgents included (`bin/disk-hygiene` reads their log paths from it), plus a copy of each enabled feature's `teardown` hook; `dotfiles/apply.lock` serialises runs; `dotfiles/attention` holds the problems the last apply reported, for the [shell notice](#shell-notice) |
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
| `GO_CACHE_TRIM_MAX_GIB` | GiB above 0, decimals allowed | `400` | `bin/go-cache-trim`: the size cap for each cache; once entries past `GO_CACHE_TRIM_HOURS` are gone, it deletes the least recently used of the rest until the cache fits, never one used in the last two hours; set in the `tool.go-cache-trim` feature's template |
| `GO_EXTRA_BUILD_CACHES` | Colon-separated directory paths | unset (only `go env GOCACHE`); the `studio` profile sets `/Volumes/E2TB2/cache/go/build` | `bin/go-cache-trim`: Go build caches to trim besides `go env GOCACHE`, such as one a checkout's `mise.toml` points `GOCACHE` at. Setting `paths.go_extra_build_caches` (feature `shell.env`), exported by the generated `env.sh`, which the job reads itself because launchd starts it without a shell |
| `DISK_HYGIENE_SCRATCH_DAYS` | Whole days, at least 1 | `7` | `bin/disk-hygiene`: delete a Claude Code session's scratch once nothing in it was used this long; set in the `macos.disk-hygiene` feature's template |
| `DISK_HYGIENE_CACHE_DAYS` | Whole days, at least 1 | `14` | `bin/disk-hygiene`: delete a tool's cache directory, a key of a keyed cache, or a goimports or pnpm cache file once unused this long; set in the template |
| `DISK_HYGIENE_TRANSCRIPT_DAYS` | Whole days, at least 1 | `90` | `bin/disk-hygiene`: delete a Codex session under `CODEX_HOME` (`~/.codex`) through `codex delete` once its transcript has not been written this long, a longer window than the 30 days Claude Code's `cleanupPeriodDays` default keeps its own transcripts; set in the template |
| `DISK_HYGIENE_KEYED` | Space-separated names | setting `disk_hygiene.keyed`, empty unless a profile sets it | Cache directories holding one subdirectory per branch, agent or tool version; `bin/disk-hygiene` prunes these a subdirectory at a time instead of whole. They are repository names, so an overlay's profile sets them; the environment wins over the setting. Empty: none |
| `DISK_HYGIENE_KEEP` | Space-separated names | empty | Cache directories `bin/disk-hygiene` never deletes, for a cache that is expensive to rebuild and used less often than the window |
| `DISK_HYGIENE_CACHE_DRIVE` | Directory path (a drive under `/Volumes`) | setting `disk_hygiene.cache_drive`: unset; the `studio` profile sets `/Volumes/E2TB`, other machines set it in their manifest | `bin/disk-hygiene` moves each cache in `DISK_HYGIENE_RELOCATE` to `<drive>/cache/xdg/<name>` and leaves a link in its usual place, while this drive is mounted. Unset: caches stay where their tools put them; the environment wins over the setting |
| `DISK_HYGIENE_RELOCATE` | Space-separated `<path under HOME>[=<name>]` | `Library/Caches/{go-build,gopls,goimports,golangci-lint,staticcheck,grype,mise}`, `.cache/{uv,puppeteer,zig,codebase-memory-mcp}`, `.npm/_cacache=npm`, `.terraform.d/plugin-cache=terraform-plugin-cache` | The caches `DISK_HYGIENE_CACHE_DRIVE` takes. `<name>` defaults to the path's last part; caches with the same name share one directory, as they should when one tool caches under both `~/Library/Caches` and `XDG_CACHE_HOME`. Only caches that rebuild on their own belong here |
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
| `CLAUDE_CONNECTORS` | `1` or unset | unset | `claudemore`/`claudemax`: `1` keeps the claude.ai connectors (Gmail, Calendar, Drive, Docs) for that launch. Otherwise the launcher sets `ENABLE_CLAUDEAI_MCP_SERVERS=false` |
| `ENABLE_CLAUDEAI_MCP_SERVERS` | `false` or unset | `false` in every session `claudemore`/`claudemax` start without `CLAUDE_CONNECTORS=1` | Claude Code fetches no claude.ai connectors. A running session keeps what it started with |
| `CODEX_CONNECTORS` | `1` or unset | unset | `gptmore`/`gptmax`: `1` keeps the ChatGPT apps (connectors) for that launch. Otherwise the launcher passes `--disable apps`, which the app-server applies to that session |
| `CODEX_HOME` | Directory path | `~/.codex` | Codex's config and state directory. `bin/codex-app-server` and the GPT launchers use its `dotfiles-app-server.sock`; a custom value must match in the service and client environments |
| `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` | `1` | `1` in interactive zsh (feature `agents.claude`'s fragment) | Turns on Claude Code's agent teams for sessions started from a terminal |
| `REPO_GUARD_LIST` | File path | unset: every `~/.config/repo-guard/protected.d/*.txt` | repo-guard's protected repositories, one `owner/name` per line; when set, the only list read. Empty protects nothing. Set it in the environment a session starts with; the hook reads the harness's environment, not a command's. A Codex session on the app-server gets the server's environment, so there it cannot be set per session |
| `DOTFILES_ENV_PATH` | PATH value | set by `env.sh` | The PATH `env.sh` last composed. A nested shell whose PATH still ends with it keeps PATH unchanged, so directories a command put first stay first; do not set it by hand |
| `DOTFILES_SYSTEM_ROOT` | Directory path | empty (`/`) | Prefix for every path `bin/dotfiles-agents` and `bin/dotfiles-local-network` read and write, so the `agents.*.bash` and `macos.local-network` checks and hooks run against it too; for testing and packaging |
| `DOTFILES_LOCAL_NETWORK_ETHERNET` / `DOTFILES_LOCAL_NETWORK_WIFI` | Space-separated CIDR networks | settings `local_network.ethernet` / `local_network.wifi`, empty unless an overlay profile sets them | The networks `bin/dotfiles-local-network` writes as `AllowedEthernetLocalNetworkAddresses` / `AllowedWiFiLocalNetworkAddresses`, which every program reaches without a Local Network grant ([LOCAL-NETWORK.md](LOCAL-NETWORK.md)); the environment wins over the setting |
| `DOTFILES_BOOT_TIME` / `DOTFILES_MACOS_VERSION` | Epoch seconds / version string | `kern.boottime` / `sw_vers -productVersion` | What `bin/dotfiles-local-network` takes as the last boot and the macOS version; for tests |
| `SPOTLIGHT_EXCLUSIONS_STORE` | File path | unset: Spotlight's own list | A JSON list `spotlight-exclusions` (and so the `macos.spotlight` hooks) uses in place of Spotlight's exclusion list; for tests, which must not change this Mac's index |

The `dotfiles` engine's flags:

| Flag | Type | Default | Scope / effect |
| ---- | ---- | ------- | -------------- |
| `--home` | Directory path | `$HOME` | All commands: the home directory to manage |
| `--repo` | Directory path | `$DOTFILES_DIR`, else `~/.dotfiles` | All commands: the checkout whose `features/` and `profiles/` are read |
| `--machine` | File path | `~/.config/dotfiles/machine.toml` | All commands: this machine's manifest |
| `--overlay-dir` | Directory path | `$DOTFILES_OVERLAY_DIR`, else `~/.dotfiles-overlays` | All commands: where the overlays `machine.toml` lists are cloned, each at `<dir>/<overlay>` |
| `--overlays` | Comma-separated names | none | `init`: the overlays this machine belongs to; each must be cloned |
| `--profiles` | Comma-separated names | none (required) | `init`: the profiles to write, in order |
| `--force` | Boolean | `false` | `init`: replace an existing manifest |
| `--dry-run` | Boolean | `false` | `apply`: report what would change, change nothing (`doctor` always does this) |
| `--sudo` | Boolean | `false` | `apply`: also run the hooks of features marked `sudo = true` (the root-owned agent configs), with the terminal as their input so `sudo` can ask for the password. Without it apply reports them as problems. Not with `--dry-run` |
| `--lock-wait` | Duration | `1m` | `apply`, `adopt`: how long to wait for another run's `apply.lock` |
| `--git-timeout` | Duration | `30s` | `apply`, `doctor`, `status`: how long each git call per checkout may take; apply needs each checkout's tracked-file list so unfolding never moves a tracked file |
| `--launchctl-timeout` | Duration | `30s` | `apply`, `doctor`: how long one launchctl call may take; a bootstrap is tried five times, 0.25 s to 1 s apart |
| `--launch-agents` | Boolean | `true` | `apply`: install, load and remove LaunchAgents. `false` leaves them, and their records, as they are; `install.sh` applies so before installing packages |
| `--json` | Boolean | `false` | `status`: print JSON, an object with `roots` (name, directory, commit, uncommitted changes) and `features` |

OpenCode's [config tables](../features/agents.opencode/README.md#config) cover its bind
address, port, gateway files, worker binaries, concurrency, and retention. The
agent telemetry collector's are in [AGENT-TELEMETRY.md](AGENT-TELEMETRY.md#config),
and `muxy-reconcile`'s in [MUXY.md](MUXY.md#config).
LaunchAgents do not read `~/.zshrc.local`. Set a service's variables in its
template's `EnvironmentVariables` (`features/<id>/launchagents/`); the next
`dotfiles apply` writes the plist and reloads the job. apply never overwrites an
installed plist edited by hand: it reports it every run and leaves it loaded.

## Git identity and signing

The shared Git config names the owner and sets `user.useConfigOnly`. The email
is each context's: an overlay's git fragment sets it, so a client's machine
never commits as the personal identity, and without one Git refuses to commit.
Override it intentionally for another user or a work-specific repository. The
installer does not create a signing key or register one with GitHub.

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
| `com.ashtonian.gitstead` | `tool.gitstead` (dev) | Every 15 minutes and at load, through `gate-lock run` ([gitstead sync](#gitstead-sync)) | `/opt/homebrew/bin/gitstead`, `~/.local/bin/gate-lock` |
| `com.ashtonian.go-cache-trim` | `tool.go-cache-trim` (base) | Hourly and at load | `/opt/homebrew/bin/go` |
| `com.ashtonian.gpg-agent` | `tool.gpg-agent` (base) | Service, GUI login only | `/opt/homebrew/bin/gpgconf` |
| `com.ashtonian.muxy-reconcile` | `tool.muxy` (desktop) | At load, when a server list is added or removed, when apply rewrites its generated files (`muxy.reconcile`, `muxy.exclude_servers`), and hourly | `/Applications/Muxy.app`, `/opt/homebrew/bin/python3` |
| `com.ashtonian.codex-remote-control` | `agents.codex` (dev) | Service | `/opt/homebrew/bin/codex` |
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
| `com.ashtonian.gitstead` | Allow `bash` (the gate lock) and `gitstead` to access files on a removable volume, where the Studio and the mini keep their repositories |
| `com.ashtonian.codex-remote-control` | Full Disk Access for `~/.local/libexec/codex-stable/bin/codex` ([Codex service](#codex-service)) |
| `com.ashtonian.opencode` | Full Disk Access for `~/.local/libexec/opencode-stable/bin/opencode` |
| `com.ashtonian.otel-agent` | Allow `otelcol-contrib` to find devices on the local network, once per release |

`com.ashtonian.go-cache-trim` runs `bin/go-cache-trim` every hour over
`go env GOCACHE` and each directory in `GO_EXTRA_BUILD_CACHES`. Go trims its
build cache only of entries unused for five days, and has no size cap. Agent
builds write hundreds of GiB a day, most of it never read again: in a
sample of the shared cache, 83% of the bytes were never reused more than an
hour after they were written. Cache keys also include the toolchain
version, so after a Go upgrade the old toolchain's entries are never used
again. Each run therefore deletes, per cache, the entries unused for
`GO_CACHE_TRIM_HOURS`, then the least recently used of the rest until the
cache is under `GO_CACHE_TRIM_MAX_GIB`. It never deletes an entry used in the
last two hours, and it reads each entry's mtime again as it deletes it, so an
entry a build picked up after the listing stays. A deleted entry costs one
recompile the next time a build needs it.

Each run logs one line per cache to `~/Library/Logs/go-cache-trim/trim.log`:
the entries and GiB deleted, how many were past the age window and how many
went for the cap, and about how much is left. `bin/go-cache-trim --dry-run`
reports what a run would delete. Troubleshooting:

- A line ending `still over the cap, with entries used in the last 2 h`: builds
  used more than the cap within two hours. Raise `GO_CACHE_TRIM_MAX_GIB`, or
  find the package that compiles to such large archives.
- `cache ... absent (volume not mounted?)`: the volume holding that cache is
  not mounted; the next run after it mounts trims it.
- `cache ... empty (no build has used it yet)`: nothing to do; Go writes the
  cache's README on the first build that uses it.
- `... is not a Go build cache` in `trim.err` and exit status 1: a configured
  directory has no Go README. Check `GO_EXTRA_BUILD_CACHES` (`echo
  $GO_EXTRA_BUILD_CACHES` in a shell, or the setting in the machine's
  profiles); the other caches are still trimmed.

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
- goimports index files and pnpm metadata files unused for the same window,
  followed through a link to wherever the cache lives.
- a Codex session whose transcript (`<CODEX_HOME>/sessions/<date>/rollout-*.jsonl`,
  or under `archived_sessions`) nothing wrote for `DISK_HYGIENE_TRANSCRIPT_DAYS`
  (90). Codex keeps every session until someone deletes it, while Claude Code
  deletes its own transcripts after `cleanupPeriodDays` (30). The run calls
  `codex delete --force <id>`, so Codex's index and thread history lose the
  session too, then removes the date directories that emptied. Only the write
  time counts, because listing sessions to resume one reads every transcript.
  Without `codex` on the job's PATH the sessions stay and the run says so; a
  session `codex delete` cannot remove is logged as `could not delete Codex
  session` and fails the run.
- with `DISK_HYGIENE_CACHE_DRIVE` naming a mounted drive, each cache in
  `DISK_HYGIENE_RELOCATE` found as a real directory: it is renamed aside, a
  link to `<drive>/cache/xdg/<name>` takes its place, and the internal copy is
  deleted rather than copied (a cache rebuilds; a copy of one a tool is writing
  can be torn). A cache a running process has open, such as an MCP server's
  index database, is left for a later run (`lsof +D`), which logs `is open in a
  running process`. Go tools ignore `XDG_CACHE_HOME` on macOS, so the link is how
  their caches leave the internal disk. Living under `cache/xdg`, the moved
  caches are pruned like the drive sessions' caches; when that pruning removes
  one whole, the run recreates its directory so the link never dangles. Links
  it did not make stay as they are, and a cache its tool never created is not
  linked. While the drive is not mounted the run says so and moves nothing; the
  links then dangle and the tools fail to open their caches until the drive is
  back (see Troubleshooting).
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

A tool that fails to create or open its cache under `/Volumes/<drive>/cache/xdg`
(gopls, golangci-lint, uv and the rest of `DISK_HYGIENE_RELOCATE`) means the
cache drive is not mounted: `mount | grep /Volumes/<drive>`. Mount it, or, to run
without it, delete that tool's link (`rm ~/Library/Caches/<tool>`) and the tool
starts a cache on the internal disk, which the next run with the drive mounted
moves again. A log line `cache drive ... is not mounted` says the same.

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

The service runs `bin/codex-app-server`, which starts codex `app-server
--remote-control` on `$CODEX_HOME/dotfiles-app-server.sock` (`CODEX_HOME`
defaults to `~/.codex`). Its sessions get the delegation policy from the
managed `SessionStart` hook, like every other Codex session.
`bin/codex-app-server --print-endpoint` prints the endpoint
without starting the server. `gptmore` and `gptmax` use it to attach to the
same socket. Their `-C "$PWD"`
selects the project directory instead of the service's home working directory.
A policy edit reaches the next session or compaction without a restart.

The dedicated socket keeps this launchd-managed service separate from
Codex's managed background daemon. On Codex's default `unix://` endpoint,
explicit feature overrides such as `--disable apps` must match the daemon's
shared settings. On this service's endpoint, the client sends them as thread
settings, preserving the per-launch `CODEX_CONNECTORS` choice.

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

After updating the socket configuration, run `dotfiles apply`, restart the
service once, and open a new shell (or source
`~/.config/dotfiles/generated/zshrc.zsh`). Use `gptmore resume <id>` or
`gptmax resume <id>` to reconnect a saved session to this service.

For Too many open files errors, inspect the loaded job's maxfiles value. The
template sets a soft limit of 65,536. `dotfiles apply` reloads the job when the
template changes; `kickstart -k` alone keeps the previously loaded settings. If sessions repeatedly
drop, inspect the log and `launchctl list` for duplicate jobs before removing a
specific stale job. OpenCode has separate [operations instructions](../features/agents.opencode/README.md#operations),
and so does the [telemetry collector](AGENT-TELEMETRY.md#operations).

### gitstead sync

`com.ashtonian.gitstead` runs `gitstead sync --quiet` every 15 minutes and at
load: it fetches and fast-forwards the repositories gitstead tracks, backs up
uncommitted work, and keeps workspaces and archives in shape (gitstead's
[operations guide](https://github.com/ashtonian/gitstead/blob/master/docs/OPERATIONS.md)).
The job runs it as `gate-lock run gitstead-sync -- gitstead sync --quiet` with
`GATE_LOCK_WAIT=1`, so its fetches, repacks and maintenance queue behind
benchmarks and full gates on the host lock, and launchd starts no second run
while one waits. `GATE_LOCK_COMMAND_TIMEOUT=3600` ends a run that hangs past
gitstead's own per-repository timeouts (exit 124); the next interval starts a
fresh one.

The job is held until both `/opt/homebrew/bin/gitstead` (this feature's cask)
and `~/.local/bin/gate-lock` exist. The gate lock's own installer (`install.sh` in
its repository, which `gate-lock` names when no version is installed) puts the
shim there, once per Mac; a Mac without it shows `waiting com.ashtonian.gitstead`
in `dotfiles doctor` rather than syncing outside the lock.

The label is the one `gitstead install-agent` gives its default schedule, so a
Mac runs one or the other, never both. On a Mac where gitstead installed its own
schedule, remove it before the first apply with this feature, so gitstead's
state stops recording a job it no longer owns. First check that no sync is
running, since uninstalling ends one mid-run:

```sh
pgrep -fl 'gitstead sync'
```

When that prints nothing:

```sh
gitstead install-agent --uninstall
dotfiles apply
launchctl print "gui/$(id -u)/com.ashtonian.gitstead" | grep -E 'state|program|last exit'
```

gitstead reads `~/.config/gitstead/config.yaml`, a managed copy of
`features/tool.gitstead/home/.config/gitstead/config.yaml` with the settings
every Mac shares, and merges in each file in `~/.config/gitstead/config.d/`.
The overlays link those fragments: each holds its own context's repos,
workspaces and fleets, with `machines:` sections keyed by the Mac's
LocalHostName (`scutil --get LocalHostName`) for where that Mac keeps them. A
key set in two files is a config error naming both. `gitstead config` prints
the files it read, the machine section it took and the merged result;
`gitstead --machine <name> plan` previews another Mac.

On a Mac where `~/.config/gitstead/config.yaml` was written by hand, apply
leaves the file alone and reports it as in the way. Move its repos and
workspaces into the overlays' fragments first, then:

```sh
mv ~/.config/gitstead/config.yaml ~/.config/gitstead/config.yaml.before-dotfiles
dotfiles apply
gitstead plan
```

`gitstead plan` should show nothing to clone, move or retire that the old file
did not. A config file that is the wrong one for this Mac makes gitstead mark
repos stale; with the default `cleanup.policy: mark_stale` it deletes nothing.

Output and errors go to `~/.local/share/gitstead/gitstead.log`, gitstead's
usual scheduled-sync log; with `--quiet` it holds only problems. `bin/disk-hygiene`
caps it with the other LaunchAgent logs.

| Symptom | Check | Then |
| ------- | ----- | ---- |
| `dotfiles doctor` lists `waiting com.ashtonian.gitstead` | `ls -l ~/.local/bin/gate-lock /opt/homebrew/bin/gitstead` | Run the gate lock's `./install.sh` from its checkout, or `brew install --cask ashtonian/tap/gitstead`; the next apply loads the job |
| Repos stop moving; no new lines in the log | `gate-lock status` | A `gitstead-sync` waiter behind a long holder is expected; a holder making no progress is the problem: see the gate-lock skill's recovery |
| Log ends in `exit 124` lines | `gitstead doctor`, then `gitstead sync -v` from a terminal | Find the repository that stalls (network, a huge fetch) and fix or exclude it |
| `dotfiles doctor`: `~/.config/gitstead/config.yaml` edited here since dotfiles last wrote it | `diff ~/.dotfiles/features/tool.gitstead/home/.config/gitstead/config.yaml ~/.config/gitstead/config.yaml` | A `gitstead setup` or `clone --save` wrote to it. Never `dotfiles adopt` it: this repository is public. Move a repo or workspace into its overlay's fragment, then remove the file and run `dotfiles apply` to copy the shared one back |
| `gitstead config` fails on a key set in two files | The two paths in the message | Keep the key in one fragment: machine facts (`base_dir`, roots, transport, archives) in the fragment that owns the Mac's layout, a context's repos and workspaces in that context's |
| A run never finishes after a drive reconnects | `log show --last 1h --predicate 'subsystem == "com.apple.TCC"' \| grep -i prompting` | Answer the removable-volume prompt on the Mac's screen ([pending prompts](#launchagents)) |

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

### Muxy remote servers

`com.ashtonian.muxy-reconcile` runs `muxy-reconcile`, which keeps the
`[[servers]]` tables of Muxy's `settings.toml` in step with the lists in
`~/.config/muxy/servers.d/` (each context's overlay links one). While the
setting `muxy.reconcile` is `report`, the default, a run only logs what it would
change (`diff:` lines, then `report: would change ...`) and writes nothing; a Mac
moves to `apply` in its own `machine.toml`, the Mac mini first
([Rollout](MUXY.md#rollout)). A run that finds nothing to change writes nothing
and does not start Muxy. Its exit status: 0 in step, changed or reported, 1 Muxy
refused the file or a command failed, 2 a bad list, `muxy.reconcile` or
`muxy.exclude_servers` value, or the lists directory missing while entries are
managed (nothing written), 3 Muxy saved during the run (the next run retries), 69
Muxy.app missing. It never stops, restarts or upgrades a Muxy
server, and the only command it sends a running app is `muxy config reload`
([what that does](MUXY.md#what-muxys-commands-do-to-a-running-muxy)).

One Mac changes what it gets in files only it has: `muxy.exclude_servers` in
`machine.toml` leaves declared servers out, a local list in
`~/.config/muxy/servers.d/` adds its own (and, with an exclusion, renames one),
and `~/.ssh/config.local` changes how one is reached
([Per-machine changes](MUXY.md#per-machine-changes)).

On a Mac where Muxy's own **Install muxy-server** ran, `~/.local/bin/.muxy`
holds the server copy that a running `muxy-server` may execute from. apply
leaves `~/.local/bin/muxy` alone while it exists (`dotfiles doctor`: `waiting
... left alone while ~/.local/bin/.muxy exists`). Never remove or move either
path while a `muxy-server` runs from it (`ps -axo pid,command | grep
'[m]uxy-server'`): that waits for a planned server restart
([Replacing Muxy's own server copy](MUXY.md#replacing-muxys-own-server-copy)).

```sh
muxy-reconcile --mode report                               # decisions and the diff it would make; writes nothing
tail -30 ~/Library/Logs/muxy-reconcile/muxy-reconcile.log  # one line per decision per run
launchctl print "gui/$(id -u)/com.ashtonian.muxy-reconcile"   # last exit status
ssh -G <alias> | grep -E '^(user|hostname|port) '          # where a listed server leads from this Mac
```

At 2am, a server Muxy shows offline is almost always one of three things:
`~/.ssh/config.local` has its own `Host <alias>` block, which ssh reads first;
known_hosts has no key under the HostName the alias leads to (the log says
`no host key`; Muxy connects with `StrictHostKeyChecking=ask` and `BatchMode=yes`, so
it refuses instead of asking; `ssh <alias> true` once fixes it); or the far
side's `~/.local/bin/muxy` is missing or is Muxy's own copy, not the app's
(held for a planned restart there; see above).
The full table, and what each exit status asks for, is in
[MUXY.md](MUXY.md#operations).

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
| Another sync or update is already running | The sync lock, `logs/sync.flock`, is held by a sync or by the weekly update, which holds it for its whole run so no sync runs while packages upgrade; the scheduled sync skips its run and the next one proceeds. Run `sync.sh check` to test it. `logs/sync.flock` normally persists after exit. Removing it does not release a live lock and can allow overlap. If it persists across runs, `lsof ~/.dotfiles/logs/sync.flock` names the holder: a run in progress is `sync.sh` or `dotfiles-update.sh` under launchd; anything else (such as `op daemon`) is a leftover from before the scripts stopped handing the lock to their steps, so end it and the next run proceeds. |
| `Another sync or update still held .../sync.flock after ...s; nothing was updated` | The update waited `UPDATE_LOCK_WAIT` seconds (30 minutes) for the lock and gave up before any stage ran. `lsof ~/.dotfiles/logs/sync.flock` names the holder; a sync that runs this long is usually stuck on a network or signing step, so check `logs/sync.log`. Rerun with `launchctl kickstart gui/$(id -u)/com.dotfiles.update` once it is free. |
| No network connectivity | Sync checks <https://github.com> with a five-second timeout. Restore connectivity, then retry. |
| Git operation in progress | Finish or deliberately abort the merge, rebase, cherry-pick, revert, or bisect; then rerun sync. |
| Detached HEAD / missing tracking branch | Check out the intended branch and set its same-named origin upstream after fetching. |
| Gitleaks fails | Fix staged content or the outgoing commit. Rotate/revoke an exposed secret; deleting the current file does not remove Git history. |
| Signing fails | Check effective Git config, key availability, GPG/pinentry, and background unlock behavior. Diagnose with a deliberate signed commit interactively; never disable signing. |
| `gpg: signing failed: No pinentry` | The gpg-agent that answered runs outside the GUI login, where pinentry-mac cannot reach the keychain or show a dialog. Check `launchctl print "gui/$(id -u)/com.ashtonian.gpg-agent"`: not found means `dotfiles doctor` shows why apply has not loaded it (gnupg missing, or the `tool.gpg-agent` feature off); running means the supervisor replaces that agent within `GPG_AGENT_SUPERVISOR_SECONDS`, so retry. If nobody is logged in at the Mac's screen, log in there. If pinentry-mac asks on every signature, tick "Save in Keychain" in its dialog ([GPG agent](#gpg-agent)). |
| `has no signing identity ...; receiving only` | The repository's effective Git config lacks `user.name`, `user.email`, `user.signingkey` or a working `gpg.program`. Sync still fast-forwards it, so an overlay that supplies the email arrives and the apply after it installs it; the next run publishes. If the warning persists, check `git -C <repo> config --show-origin --get user.email` and that `machine.toml` lists the overlay that sets it. The `... needs a signing identity` errors name what waits for it: local edits, local commits or a branch that diverged, all left as they are. |
| GitHub reports bad_email | Correct the affected commit to a signing-key email verified on GitHub. Keep a backup ref before any authorized history repair. |
| GitHub verification fails after push | Publication already occurred. Inspect the reason and GitHub status; repair only affected commits within authorized history scope. |
| Merge conflict | Automation aborts the merge. Resolve and sign the integration deliberately. Dotfiles has no conflict preference; auxiliary repos use local-preferred conflicting hunks (`-X ours`). |
| Push rejected | Check permissions and remote changes. Sync tries at most three times with fetch and signed merge; it never force-pushes. |
| Excluded tracked changes remain | Review tracked `*.local`, `.env*` or `*.secret*` paths in any directory. Sync skips merge/push while excluded tracked changes remain. |
| Sync leaves a repository alone | The log says why: a Git index lock (another Git command is running, or one crashed and left `.git/index.lock`; check `ps` before removing it), or a tracked edit newer than `SYNC_QUIET_MINUTES`. The next run picks it up. |
| `No network connectivity (... did not answer within ...s), skipping sync` | The HEAD request to `SYNC_CONNECTIVITY_URL` failed. Check `curl -sfI https://github.com` from a terminal; if it answers only slowly, raise `SYNC_CONNECTIVITY_TIMEOUT` in the `dotfiles.sync` template. The next run retries. |
| Sync never finishes; `ps` shows a Go command at 0% CPU under it | macOS is waiting for an answer to "bash would like to access files on a removable volume" because Go's caches are on an external drive. Answer it on the machine's screen, or allow `bash` under System Settings > Privacy & Security > Files and Folders. `log show --last 1h --predicate 'subsystem == "com.apple.TCC"' \| grep AUTHREQ_PROMPTING` names the binary it is waiting on; after a `brew upgrade bash` it is the new build. A prompt holds every later removable-volume check behind it until someone answers, whichever binary asked, so a sync can stall on another tool's prompt (an agent runtime, `python3`). |
| New files are not published | By design: sync stages tracked files only (`git add -u`). Commit new files yourself. |
| `installs machine features and this machine has no .../machine.toml` | Upstream uses the feature engine and this machine has no manifest, so sync neither merges nor pushes (merging would leave the old stow links pointing at moved files). Write `~/.config/dotfiles/machine.toml` with this machine's profiles from the list in the message, such as `profiles = ["base", "dev", "desktop"]`, then run `sync.sh`: the same run merges and applies. |
| `installs machine features and Go is not installed to build its engine` | Sync builds the upstream engine before merging it and found no `go` on its PATH, so it neither merges nor pushes. Install Go (`brew install go`; the LaunchAgent's PATH includes `/opt/homebrew/bin`), then run `sync.sh`. |
| `engine does not build with this machine's Go or cannot plan ...machine.toml` | The lines above it are the build error or `dotfiles check`'s message. A build error usually means Go is older than `go.mod` (sync uses `GOTOOLCHAIN=local`): upgrade Go. A plan error (exit 2) names the profile, feature or setting in `machine.toml` that upstream no longer accepts, or a feature no overlay defines: fix the manifest, or list the overlay that defines the feature in `machine.toml` (sync brings the listed overlays up to date before this check, so a feature their incoming commits add is already seen). Nothing was merged; rerun `sync.sh`. |
| `Building ~/.local/bin/dotfiles failed` / `Go is not installed` | Sync builds the engine with the installed Go and `GOTOOLCHAIN=local`, so it never downloads a toolchain. Install or upgrade Go to the version in `go.mod` (`brew install go`), then rerun `sync.sh apply`. |
| `dotfiles apply left problems to resolve` | The log above lists them; see [Feature engine troubleshooting](#feature-engine-troubleshooting). Sync carries on with packages and the other repositories. |
| `the telemetry collector did not converge` | The line above it is `otel-agent converge`'s reason: `no host name configured` means the Mac was enrolled before per-host tokens, so run `~/.dotfiles/bin/otel-agent enroll <studio\|mbp\|mini>`; a download or checksum error is retried by the next sync. See [Agent telemetry](AGENT-TELEMETRY.md#operations). Sync carries on with the other steps. |
| `downloading the Claude Code installer ... failed` / `the Claude Code installer failed (exit N)` | Sync could not install Claude Code on a machine with `agents.claude`; the lines above are the installer's output. Check `curl -fsSL https://claude.ai/install.sh -o /dev/null` and the network; the next sync retries, or run `~/.dotfiles/sync.sh claude-code` from a terminal. Sync carries on with the other steps. |
| `the Claude Code installer did not finish within ...s and was stopped` | A download stalled past `CLAUDE_CODE_INSTALL_TIMEOUT`. The next sync retries; on a slow link raise the timeout in the `dotfiles.sync` template. |
| `jq is not installed, so sync cannot tell whether this machine wants Claude Code` | `jq` comes from `brew.base`; install it (`brew install jq`) or let the Brewfile step install it, and the next sync goes on. |
| `claude` is old, or `type -a claude` lists `/opt/homebrew/bin/claude` | That is the Homebrew cask, which dotfiles no longer installs. `brew uninstall --cask claude-code`; the native `~/.local/bin/claude` comes first on PATH and updates itself (`claude doctor`). |
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

## Aerial wallpaper memory leak

Since macOS 14 the default wallpaper is an aerial video, and the screen saver
and lock screen play the same aerial. While it plays,
`WallpaperAerialsExtension` sits at 100%+ CPU and the `VTDecoderXPCService` it
drives grows by gigabytes until the Mac swaps. It plays whenever the screen
saver starts, which on a Mac kept awake (Caffeine, `caffeinate`) can mean hours,
and whenever the lock screen shows, which includes every Screen Sharing
connection. Reproduced on macOS 27.2.1.

`config.sh` runs `bin/disable-aerials`, which replaces each aerial: an aerial
desktop and lock screen get a still picture, an aerial screen saver Floating
Message. A picture, picture folder, colour, dynamic wallpaper or screen saver
someone chose is left as it is. It leaves the screen saver on: on a Mac whose
display never sleeps, the screen saver is what locks the screen. The script
reads every entry in
`~/Library/Application Support/com.apple.wallpaper/Store/Index.plist` (all
spaces and displays, the system default, any per-display or per-space entry);
a slot is an aerial when its provider is `default` (a linked entry with no
choice of its own shows the system default, an aerial since macOS 14) or names
an aerial. When it changed something, it restarts WallpaperAgent and stops the
aerial extension, which ends its decoder. A run that finds no aerial changes
nothing. It refuses an entry layout it does not know and leaves the store
untouched.

| Flag | Type | Default | Effect |
| ---- | ---- | ------- | ------ |
| `--picture` | File path | `/System/Library/Desktop Pictures/Solid Colors/Space Gray.png` | Picture for an aerial desktop and lock screen; must be a still image |
| `--saver` | `.saver` bundle path | `/System/Library/Screen Savers/FloatingMessage.saver` | Screen saver in place of an aerial one |
| `--store` | File path | the logged-in user's store | Store to rewrite; WallpaperAgent is restarted only for the default |
| `--dry-run` | Boolean | `false` | Report the entries that would change, write nothing |

Each write first copies the store to
`$XDG_STATE_HOME/dotfiles/wallpaper/Index-<UTC time>.plist`.

Confirm the leak before blaming it, and check that the fix held:

```sh
top -l 2 -s 15 -o mem -n 8 -stats pid,command,mem,cpu   # leak: VTDecoderXPCService at GiB and growing
pgrep -lf 'VTDecoderXPCService|WallpaperAerialsExtension'
plutil -p ~/Library/Application\ Support/com.apple.wallpaper/Store/Index.plist | grep -E '"(Type|Provider)"'
```

After the fix no entry is `linked` to `default` and no `Provider` names an
aerial; a chosen picture, folder, colour or dynamic wallpaper keeps its own
provider.
WallpaperAgent may start `WallpaperAerialsExtension` again; idle at 0% CPU with
no `VTDecoderXPCService` beside it, it is not playing anything. To free a
running leak without the script, kill both processes: the decoder alone is
restarted by the extension and leaks again within a minute. `kernel_task`
showing a large MEM is compressor accounting, not the leak.

| Symptom | Check and recovery |
| --------- | -------------------- |
| `WallpaperAgent reverted …` | The agent rejected the store, usually because a macOS update changed its layout. Restore the newest backup (below) and pick a still wallpaper and screen saver in System Settings. Then compare the store with `plutil -p` and update the script to match. |
| `unknown entry type …` | The store has a layout the script does not know; nothing was written. Set the wallpaper in System Settings, then teach the script the new `Type`. |
| Leak is back after a macOS update | Updates can reset the wallpaper. Run `~/.dotfiles/bin/disable-aerials`. |
| Undo | `cp ~/.local/state/dotfiles/wallpaper/Index-<time>.plist ~/Library/Application\ Support/com.apple.wallpaper/Store/Index.plist && killall WallpaperAgent` |

Don't start the screen saver to test the change: it locks the screen of
whoever is at the Mac.

## Shell notice

Sync applies unattended, so a problem it hits (a root-owned file to update with
`dotfiles apply --sudo`, a hook that failed) would otherwise sit in
`logs/sync.log`. Every apply that is not a dry run writes its problems to
`~/.local/state/dotfiles/attention` (mode 0600), one `<path>: <detail>` per
line, and removes the file when there are none. The `dotfiles.sync` feature's
zshrc fragment reads it when an interactive shell starts and prints, on
standard error:

```text
dotfiles: 2 problem(s) need you; the first: agents.claude.bash: drift: … run `dotfiles apply --sudo`
dotfiles: see all with: dotfiles doctor
```

It reads one small file and runs nothing, so it adds no measurable startup
time. The notice stops once an apply reports no problems; deleting the file
silences it until the next apply.

## Feature engine troubleshooting

Run `dotfiles doctor`; it changes nothing and lists each problem with its path.

| Symptom | Check and recovery |
| ------- | ------------------ |
| `a file is in the way` | A real file sits where a link goes. Compare it with the tracked file the message names, keep what you need (in the repository if it should be shared), move the file aside, and run `dotfiles apply`. |
| `edited here since dotfiles last wrote it` | A managed copy was changed locally, by hand or by the app that rewrites it. Keep it with `dotfiles adopt <path>`, which writes it into the tracked file (sync publishes it like any tracked edit), or delete the local file and run `dotfiles apply` to take the repository's version. |
| `not a managed copy or app setting on this machine` (exit 64) | `dotfiles adopt` names only files an enabled feature installs as a copy, and app settings an enabled feature owns, as `<store>:<key>` (`muxy:appearance.dark_theme`); linked files are edited in place and need no adopt. Flags go before the targets. |
| `pref muxy:<key> -> <value> (was <other>)` on a machine's first apply | Expected: apply sets each shared key a feature owns, after saving the value it replaced, which disabling the feature puts back. A value set by hand in the app is replaced like any other. `dotfiles doctor` lists what the first apply would change, and `app-setting` lines say where each value comes from. To keep this machine's own value, add it to `machine.toml` before the first apply: `[prefs]` then `"muxy:<key>" = <value>` (see [Per-machine overrides](MACHINE-FEATURES.md#per-machine-overrides)). To make this machine's value the shared one instead, run `dotfiles adopt muxy:<key>` here before the first apply: it rewrites that line of the prefs file, sync publishes it, and the other machines take it. |
| `update-pref muxy:<key> -> <value> (was <other>)` | The planned value moved: the prefs file changed, or a profile's or `machine.toml`'s `[prefs]` override was added, changed or removed (removing one returns to the shared value). Expected; `dotfiles status` shows which layer sets it now. |
| `... -> <value> (was <other>); the app stored <close value>` | The app keeps the value less precisely than written (Muxy keeps a float as 32 bits: `1.3` is stored as `1.2999999523162842`). apply records what the app stored, so later runs see no change. Nothing to do. |
| `waiting muxy:<key>: app not available: ..., so its value from before dotfiles, <value>, waits to be put back` (doctor) | The feature that owned the setting was turned off while the app was not there: uninstalled, or its bundle being replaced by an update. apply keeps the record, the only copy of the earlier value, and puts it back on a later run once the app is there; it is no failure. If the app is gone for good, run `dotfiles forget muxy:<key>`: it drops the record and prints the earlier value (`forget-pref muxy:<key> -> before dotfiles set it, it was <value>`), to set by hand with `muxy config set -- <key> <value>` should the app return. |
| `dotfiles: not an app setting waiting to be put back: ...` from `dotfiles forget` (exit 64) | `forget` names only settings the state holds a record of and no enabled feature owns. For an owned one, disable its feature and let apply put the value back. |
| `note: muxy:<key>: ... [prefs] sets it, but <feature>, which owns it, is off here, so it is ignored` (check), `ignored ...` (doctor) | A `machine.toml` override for a feature turned off on this machine. It changes nothing and fails nothing; delete the line, or enable the feature. |
| `... [prefs] "muxy:<key>": no feature owns this setting` (exit 2) | An override in `machine.toml` or a profile names a setting no feature owns: a typo, or a key removed from the feature's prefs file. Fix or delete the line. |
| `... is a dotted key, which TOML reads as a table` (exit 2) | A prefs file or `[prefs]` line names a key with an unquoted dot, such as `permissions.defaultMode = ...`, which TOML reads as a whole `permissions` table. Quote the key (`"terminal.font_size" = 14.0`). The `claude` store owns only top-level keys of `settings.json`, so a key inside an object is refused even when quoted. |
| `muxy:<key>: changed here since dotfiles set it` (or `claude:<key>`) | The setting was changed in the app (Muxy's settings or theme picker, Claude Code's `/config` or `/theme`) after apply set it, so apply leaves it. Keep it for every machine with `dotfiles adopt muxy:<key>`, which rewrites that line of the feature's prefs file (sync publishes it); keep it for this machine only by adding it to `machine.toml`'s `[prefs]` table first, after which adopt rewrites that line instead; or set it back to the value the message names. |
| `muxy:<key>: reading it: Muxy is not installed` | The engine runs the `muxy` inside `$DOTFILES_MUXY_APP` when it is set, else `~/Applications/Muxy.app` or `/Applications/Muxy.app`, never the one on `PATH` (a Muxy client installs its own build there on machines it connects to). Install the app (`tool.muxy` adds its cask; sync installs it after apply, so the next sync sets the settings), or disable `tool.muxy` on this machine. |
| `muxy:<key>: saved, but the running app did not apply it` | Muxy saved the value (or the unset), but the running app could not reload its settings, usually because it is older than the installed app (an update is waiting for a relaunch). Nothing is lost: the app reads the file when it next starts, and the next apply finds the value saved and reports nothing. Leave it for the next relaunch. Never use **Restart Server** or **Stop Server** for this: they end that server's terminals. Quitting the app keeps terminals only while the server setting **Keep terminals running after quitting** is on, so check it before quitting a Muxy whose terminals must survive, and never use **End All Sessions and Quit**. |
| `muxy:<key>: setting it: ...` | Muxy refused the value; the message is Muxy's own (an unknown key, or the wrong type). Fix the line in `features/<id>/muxy.toml`; `muxy config list` shows every key and its current value. |
| `muxy config list: no answer within 15s` | The Muxy tool hung. Check that the app opens; raise `--app-timeout` only for a machine that is known to be slow. |
| `claude:<key>: reading it: ... not a JSON object` | `~/.claude/settings.json` does not parse. Fix it (`jq . ~/.claude/settings.json` shows where), or let Claude Code rewrite it with `/config`; the engine never writes a file it cannot read. |
| `no longer managed, but changed since dotfiles set it` | A feature that owned an app setting was disabled, or the key was removed from its prefs file, and the setting had changed in the app since apply set it, so apply left it as it is rather than putting back the earlier value. Nothing to do unless you want the old value back. |
| `move this line before the first Host or Match line` | `~/.ssh/config` existed before the stub and its `Include dotfiles.conf` comes after a `Host` or `Match` line, where it applies only inside that block. Move it above the first one. |
| `left in the retired stow tree and not installed any more` | An untracked file is still under `stow/` and nothing in `$HOME` links to it. It is yours: move it where it belongs (often the same path under `$HOME`), or delete it. `/stow/` is gitignored, so it is never published. |
| `XDG_CONFIG_HOME: it is ..., but dotfiles installs into ~/.config` | git and other tools read their config from `$XDG_CONFIG_HOME`, so they miss the shared files. Unset it (usually in `~/.zshrc.local`) or set it to `~/.config`. |
| `add this line so it loads the shared configuration` | An entry point that existed before the stub. Add the named line; the engine never edits a stub once it exists. |
| `.bashrc: add this line` on Linux | The distribution's `~/.bashrc` from `/etc/skel` existed first. Add the line at the top, above its `case $- in` (or `[ -z "$PS1" ] && return`) guard, which returns early in non-interactive shells. Login bash loads `env.sh` through `~/.bash_profile` either way. |
| `skipped until these settings have values` | A required setting has no value. Set it in a profile or `machine.toml`; secrets are `{ secret = "op://..." }` references. |
| `no machine manifest at ...` (exit 2) | This machine has no `~/.config/dotfiles/machine.toml`. Run `dotfiles init --profiles <names>` with this machine's profiles (see the README's machine table); apply refuses to guess, since no profiles would remove everything they install. |
| `Tracked files name what an overlay keeps private` in `logs/sync.log` | A tracked line in dotfiles names something on an overlay's `denylist.txt`; the lines follow the message. Reword it generically or move it into that overlay (a feature, profile setting or `docs/` there), commit, and let the next sync publish. Nothing was committed or pushed. `bin/check-private-names` runs the same check by hand. |
| `overlay not cloned: <name> is not at ...` (exit 2) | `machine.toml` lists an overlay that has no checkout. Clone that context's overlay repository to the path named, or remove the overlay from `overlays` if this machine left the context. Apply stops rather than run without it, which would remove what its features install. Sync logs the same as `lists overlay <name>, which is not cloned`. |
| `... is in overlay <name>, so its name must be ...` or `... in the repository starts with the name of overlay <name>` (exit 2) | A feature or profile is in the wrong checkout. An overlay's feature IDs and profile names start with the overlay's name and a dot (or are the name), and the repository's never do. Rename the directory and its `id`. |
| `a link to ... is in the way` | A link that points outside the repository sits where a link, copy or stub goes. Check what it points at, remove it if it is stale, and run `dotfiles apply`. |
| `unfold` and `move-home` in the output | Expected once per machine: a directory the old stow layout had linked into the repository becomes a real directory, and the untracked files tools wrote through it (such as gh's `hosts.yml`) move into it. Tracked files are never moved. A leftover `<dir>.dotfiles-unfold-<pid>` directory means a run died mid-unfold: compare it with `<dir>`, move any missing file into `<dir>`, then delete it. |
| Exit status 2 | The manifests are invalid or contradict each other; the message names the file, key or features. |
| `another dotfiles apply holds ...apply.lock` | Another run is in progress (sync, or a manual run). Wait, or raise `--lock-wait`. The lock is released when that process exits; never delete the file by hand. |
| `state ... has version N; this dotfiles build reads versions 1 to 3` | A newer engine wrote the state file (version 2 added the app settings' records, version 3 the teardown hooks). This build stops rather than save over it and lose what it does not know. Update the checkout (`git pull`) and rebuild `dotfiles`. Never delete or hand-edit the file to get past it: it holds the values teardown puts back. |
| `state ... has no version; dotfiles did not write it` | Something other than dotfiles wrote `~/.local/state/dotfiles/applied.json`, or it was edited by hand. Restore it from a backup if there is one. Moving it aside makes the next apply treat every installed file as unknown (reported, never overwritten) and forget the app settings' earlier values. |
| ``<feature>: drift: …; run `dotfiles apply --sudo` `` (or `missing:`) | A feature whose hooks need an administrator, such as `agents.claude.bash`, found its state out of date: usually a pull changed a root-owned agent config. Sync never prompts, so run `dotfiles apply --sudo` in a terminal; `sudo` asks for the password. |
| ``<feature>: turned off, and its teardown needs administrator rights; run `dotfiles apply --sudo` `` | The feature was turned off or deleted and its recorded teardown must run as an administrator. Run `dotfiles apply --sudo`. Until then the record stays in `applied.json` and the file it removes stays in place. |
| `<feature>: hooks.apply ran, and the check still reports <state>: <detail>` | The hook exited 0 without fixing what the check reports. Its output is on the apply's standard error (in `logs/sync.log` for sync); run the feature's `hooks/check` and `hooks/apply` by hand with `DOTFILES_DIR` set to the repository to see both sides. |
| `<feature>: check.script printed "…", not one JSON object with state and detail` | The feature's check broke its contract ([MACHINE-FEATURES.md](MACHINE-FEATURES.md#hooks-and-checks)): it must exit 0 and print exactly `{"state": "ok\|drift\|missing\|error", "detail": "…"}`. Fix the script; diagnostics go to standard error. |
| `<feature>: check.script did not finish within 10s` (or `hooks.apply … 5m0s`) | The script hung or waited for input it cannot get. A hook that legitimately takes longer sets `[hooks] timeout` or `[check] timeout` in its `feature.toml`. |
| `<feature>: turned off, and hooks.teardown exited with status N; the next apply runs it again` | The recorded teardown failed; its output is above. The next apply retries it. A teardown that can never succeed (what it removes is already gone some other way) still has to exit 0: fix it in the repository. |
| `<feature>: check.script hooks/check is not an executable file` (exit 2) | The script is missing or lost its executable bit: `chmod +x features/<id>/hooks/check` and commit. |
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

## Agent troubleshooting

| Symptom | Check and recovery |
| ------- | ------------------ |
| `claudemore: command not found` (or `gptmore`) | The launchers live in the generated zshrc fragment of `agents.claude` (`agents.codex` for the GPT ones, macOS only), which the dev profile enables. Run `dotfiles apply` (sync runs it) and open a new shell; `grep -c 'agents.claude' ~/.config/dotfiles/generated/zshrc.zsh` should be 1. |
| A session behaves as if it had no delegation policy (never uses `scout` or `reader`) | Claude Code: `/hooks` must list a managed `SessionStart` hook running `cat ~/.config/agent-delegation/policy.md`; Codex: `/hooks` must list it with source system. If either is missing, `dotfiles doctor` reports `agents.claude.bash` or `agents.codex.bash` with `drift` or `missing`: run `dotfiles apply --sudo`. If the hook is there, the `agents.delegation` link is missing or broken: `dotfiles doctor` names it and `dotfiles apply` restores it. The hook adds nothing when the file is absent. A running session gets the policy at its next compaction, `/clear` or resume. |
| `/agents` lists no `scout` or `reader` | `~/.claude/agents/scout.md` and `reader.md` must link into `features/agents.delegation/home/`. Run `dotfiles doctor`, then `dotfiles apply`; a running session picks new subagent files up only after a restart. |
| Codex's `spawn_agent` offers no `scout` or `reader` role | `~/.codex/agents/scout.toml` and `reader.toml` must link into `features/agents.delegation/home/`. A malformed role file is skipped with a startup warning (`Ignoring malformed agent role definition`); `codex debug prompt-input hi \| grep -o -E '(scout\|reader): \{'` prints one line per role that loaded. |
| A launched session still shows `mcp__claude_ai_*` tools | It was started with `CLAUDE_CONNECTORS=1`, by plain `claude`, or before this launcher. Check with `ps -E -o command= -p <pid> \| tr ' ' '\n' \| grep ENABLE_CLAUDEAI`; restart it with `claudemore`. |
| A `gptmore` session still has ChatGPT app tools | It was started with `CODEX_CONNECTORS=1`, by plain `codex`, or before this launcher. `ps -o command= -p <pid>` of the client shows `--disable apps` when the launcher left them out; restart it with `gptmore`. |
| `Background server has incompatible feature settings` / `This session requires apps to be disabled` | Check the client's `--remote` argument: `gptmore` and `gptmax` use the dedicated endpoint printed by `~/.dotfiles/bin/codex-app-server --print-endpoint`. A client using `unix://` is checking Codex's shared daemon settings. Run `dotfiles apply`, restart the Codex service when its sessions are idle, and open a new shell to load the updated launchers. |
| A command is denied with `Changes to <owner>/<name> need the user's explicit permission` | repo-guard matched a protected repository: the command names it, or runs in or points git at a clone of it. `claude plugin list` shows `repo-guard@skills-dir`; Codex's `/hooks` shows the `PreToolUse` hook from `/etc/codex/config.toml` as managed. The lists are `~/.config/repo-guard/protected.d/*.txt`. If the change is permitted, run it yourself, or start a Claude Code session with `REPO_GUARD_LIST=` (empty). If the repository should not be protected, remove it from its overlay's list. |
| Codex runs a protected write without a denial | Codex's `/hooks` must list the repo-guard hook with source system. If it is missing, `dotfiles doctor` reports `agents.codex.bash` with `/etc/codex/config.toml` missing or changed: run `dotfiles apply --sudo`. If it is listed, `ls -l ~/.local/bin/repo-guard` must resolve into `features/agents.repo-guard/` (without it the hook passes): `dotfiles apply`. A hook that ran past 10 s lets the call through; the session shows it as a failed hook. |
| `PreToolUse:Bash hook error` naming `repo-guard: <list>:<n>: '<line>' is not owner/name` | A protected list has a bad line, so every write-shaped command is blocked. Fix the line in the overlay that owns the list; reads keep working meanwhile. `cannot read the protected list` means a listed file is unreadable or `REPO_GUARD_LIST` names a missing file. |
| `repo-guard: jq is not installed` | Every Bash command is blocked while a protected list exists, because the hook cannot read its input. Install jq (`brew.base` lists it; macOS 15 and later also ship `/usr/bin/jq`). |
| `failed; blocking because onFailure is "block"` or `timed out` for repo-guard, or Codex shows `repo-guard: exited <n>; blocking the command` | The hook crashed (or, in Claude Code, ran past 10 s). Run `features/agents.repo-guard/guard_test.sh`; it prints each failing case. Exit 127 in Codex means `~/.local/bin/repo-guard` is a dangling link: `dotfiles apply`. |
| `dotfiles apply` reports `a file is in the way` for `~/.codex/AGENTS.md` | A hand-written Codex instructions file predates `agents.codex` rendering it. Every rule in it belongs in a source (README: Agent rules): every agent's in `features/agents.rules/home/.claude/CLAUDE.md`, Codex's own in `features/agents.codex/codex-rules.md`, a context's in its overlay's rules file. Move each one there, delete the file and apply. Then `codex debug prompt-input hi \| grep -c 'agents.codex'` prints 1 |
| `dotfiles apply` reports `a file is in the way` for `~/.claude/statusline-p10k.sh` or a `~/.claude/mcp/*.sh` helper | The machine's untracked copy predates the feature. Compare it with the tracked file the message names, move it aside, and apply. |

Before publishing, run the [validation commands](../README.md#validation) and
review `git diff`. Update configuration tables when defaults or interfaces change.
