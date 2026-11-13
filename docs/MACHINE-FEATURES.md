# Machine Features

Specification for per-machine feature toggles, automatic convergence on pull,
and the local status page. It replaces the flat "every package on every
machine" model with features that each machine enables or disables
independently.

Status: draft on branch `plan/machine-features`. Nothing here is implemented
yet; the [rollout](#rollout) section orders the work.

## Goals

- **Converge on pull.** A machine that pulls the repo reaches the state the repo
  describes without manual steps, except one-time bootstrap actions that need
  root or a human login.
- **Every capability is a feature.** Each one can be enabled or disabled per
  machine, independently, and disabling it removes what it installed (Homebrew
  packages excepted; see [Teardown](#teardown)).
- **One status page per machine.** It shows, for every feature, whether it is
  wanted, why, and whether the machine matches.
- **Nothing machine-local enters the repo.** Tools never write into tracked
  files, and the auto-publisher only commits edits to files already tracked.
- **Agents get bash.** Claude Code, Codex and OpenCode run model-written
  commands in bash with the shared environment: Homebrew bash on macOS and
  Linux, Git Bash on Windows (where Codex only offers PowerShell).
- **macOS, Windows and Linux.** One engine, one feature model, and one
  implementation per OS of each mechanism (see [Platforms](#platforms)).

Non-goals: MDM, and managing other users' accounts.

## Platforms

Features declare the platforms they support (`platforms = ["darwin", "linux",
"windows"]`, all three by default). Each mechanism has one interface in the
engine and one backend per OS:

| Concern | macOS | Linux | Windows |
|---|---|---|---|
| Linking | Per-file symlinks | Per-file symlinks | Per-file symlinks when a test link succeeds at apply time (Developer Mode or the symlink privilege); managed copies otherwise |
| Scheduler | launchd LaunchAgents | systemd user timers with `Persistent=true` and `RandomizedDelaySec`; `loginctl enable-linger` on servers; a user crontab with a lock and catch-up stamp where there is no systemd | Task Scheduler: `Register-ScheduledTask -LogonType Interactive`, `-StartWhenAvailable`, `-MultipleInstances IgnoreNew` |
| Packages | Homebrew formulae, casks and `mas` | Homebrew formulae (Tier 1 needs glibc 2.39 or later), flatpak for desktop apps, apt or dnf only for system prerequisites | WinGet configuration (`winget configure`) |
| Secret store | Login Keychain | Secret Service on desktops; `systemd-creds --user` (systemd 256 or later) on headless hosts, else a 0600 file | Credential Manager, local-machine persistence; values over its 2,560-byte limit go in DPAPI-protected files |
| Login shell entry points | zsh stubs | zsh or bash stubs | PowerShell profile stub at `$PROFILE.CurrentUserAllHosts` (resolved, not hard-coded, since Documents may be redirected), execution policy `RemoteSigned` for the current user |
| Claude Code managed settings | `/Library/Application Support/ClaudeCode/managed-settings.d/` | `/etc/claude-code/managed-settings.d/` | `C:\Program Files\ClaudeCode\managed-settings.d\`. A registry policy under `HKLM\SOFTWARE\Policies\ClaudeCode` outranks the files and hides them unless it sets `managedSourcesBehavior: "merge"`; `doctor` checks |
| Claude Code shell | `CLAUDE_CODE_SHELL`, Homebrew bash | `CLAUDE_CODE_SHELL`, bash | Git Bash through `CLAUDE_CODE_GIT_BASH_PATH`; the PowerShell tool stays available |
| Codex shell | The passwd login shell; the `zshenv.zsh` hand-off (D3) | The passwd login shell; the same hand-off when it is zsh | PowerShell (`pwsh`, then Windows PowerShell); no shell snapshot |
| Codex system config | `/etc/codex/config.toml` | `/etc/codex/config.toml` | `%ProgramData%\OpenAI\Codex\config.toml` (from Codex's source; not in its docs) |
| App settings backup | Mackup catalog | Mackup catalog | D28 |
| State and status page | `~/.local/state/dotfiles/` | `$XDG_STATE_HOME/dotfiles/` | `%LOCALAPPDATA%\dotfiles\` |

Linking rules, on every OS:

- One link per file; a directory is never linked, so a tool that writes a new
  file beside its config never writes into the repo.
- Nothing under `~/Library`, and no file a sandboxed or GUI app reads, is ever
  a symlink. Since macOS 13.4 and 14, apps and `defaults` refuse to read or
  save a symlinked preference file, and granting permissions does not help
  ([Mackup #1924](https://github.com/lra/mackup/issues/1924)). Those files are
  managed copies.
- Managed copies are tracked in a manifest with their content hash. A local
  edit shows as drift, and `dotfiles adopt <path>` copies it back into the
  repo.
- Hard links and junctions are never used: editors that save through a rename,
  and git checkouts, silently break them.

The engine does its own linking on all three OSes, so GNU stow is not used
after the [migration](#rollout).

## Concepts

| Term | Where it lives | Tracked | Purpose |
|---|---|---|---|
| Feature | `features/<id>/feature.toml` plus payload files | yes | The unit of toggling: what to install, link, schedule and check |
| Profile | `profiles/<name>.toml` | yes | A named set of feature decisions and setting values (`base`, `dev`, `desktop`, `server`, `work`, `studio`) |
| Machine manifest | `~/.config/dotfiles/machine.toml` | no | This machine's profiles, feature overrides and setting overrides |
| Setting | declared by a feature, valued by profiles and the machine manifest | values may be either | Typed configuration a feature consumes, such as `paths.playwright_browsers` |
| Secret | The OS secret store (see [Platforms](#platforms)), seeded from 1Password | never | Referenced by name in a feature; the value never appears in a manifest, the environment or a log |
| Generated output | `~/.config/dotfiles/generated/` (`%LOCALAPPDATA%\\dotfiles\\generated\\` on Windows) | no | Files `apply` renders from the enabled features: Brewfile, WinGet configuration, shell fragments, git and ssh includes |
| State | The state directory (see [Platforms](#platforms)) | no | Last run results, the status JSON and HTML page, logs |

### Resolution

A feature is enabled when the last decision in this order says so:

1. The feature's `default`.
2. Each profile listed in `machine.toml`, in order.
3. `machine.toml` `[features]`.

`requires` pulls dependencies in; the status page shows them as "enabled
(required by X)". Disabling a feature that an enabled feature requires is an
error that names both. `conflicts` makes two features mutually exclusive.
Settings resolve the same way: feature default, then profiles in order, then
the machine manifest. A missing required setting fails `apply` for that feature
only and shows on the status page.

### Machine manifest

```toml
# ~/.config/dotfiles/machine.toml
profiles = ["base", "dev", "desktop", "server"]

[features]
enable  = ["tool.toggl-focus", "browser.firefox.bypass-paywalls"]
disable = ["shell.omz.git-auto-fetch", "backup.mackup.macosx"]

[settings]
"paths.playwright_browsers" = "~/Library/Caches/ms-playwright"
```

`dotfiles feature enable|disable <id>` edits this file and runs `apply` for
that feature.

A setting of type `secret` holds an `op://` reference, never a value. The
reference reveals nothing, so it can sit in a tracked profile:

```toml
# profiles/base.toml
[settings]
"toggl.organization_id" = { secret = "op://dotfiles/toggl/organization_id" }
```

## Feature manifest

```toml
# features/shell.zoxide/feature.toml
id          = "shell.zoxide"
description = "zoxide jump commands in interactive terminals"
category    = "shell"
platforms   = ["darwin", "linux", "windows"]
default     = true
requires    = ["shell.core"]
conflicts   = []

[provides]
brew   = ["zoxide"]           # Brewfile entries (macOS, Linux)
winget = ["ajeetdsouza.zoxide"] # WinGet configuration entries (Windows)
zshrc  = "zshrc.zsh"          # interactive zsh fragment, real sessions only
pwsh   = "profile.ps1"        # interactive PowerShell fragment (Windows)
env    = ""                   # POSIX fragment sourced by env.sh (every shell and agent)
bin    = []                   # scripts linked into the user bin directory
link   = []                   # files linked one by one (managed copies where links are not allowed)
copy   = []                   # files always installed as managed copies
schedules = []                # job definitions, rendered per OS scheduler

[settings.cd_override]
type    = "bool"
default = true
doc     = "Replace cd with zoxide's cd in real interactive sessions only"

[hooks]
apply    = ""                 # idempotent converge script, settings passed as env
teardown = ""                 # reverses apply
sudo     = false              # apply needs root; runs only from `dotfiles apply --sudo`

[check]
script  = ""                  # prints one JSON object: {"state": "ok|drift|missing|error", "detail": "..."}
timeout = "2s"
```

Generic checks cover every `provides` type, so most features need no check
script: packages are installed, links point at the repo, managed copies match
their manifest hash, a scheduled job is registered and its last exit was 0, a
fragment is in the generated output.

### Teardown

Disabling a feature reverses each `provides` type: remove its links and
managed copies, unregister its scheduled jobs (`launchctl bootout`,
`systemctl --user disable --now`, `Unregister-ScheduledTask`), drop its
fragments from the generated outputs, and run its `teardown` hook. Packages
are not uninstalled automatically, because another tool or the user may rely
on them. The status page lists installed packages no enabled feature wants,
and `dotfiles prune --packages` removes them on request.

## Generated outputs

`apply` renders everything shells and tools read at runtime, so no shell
startup parses a manifest.

| Output | Consumer | Contents |
|---|---|---|
| `generated/Brewfile` | sync, `brew bundle` (macOS, Linux) | Union of enabled features' `brew`, `cask`, `mas`, `flatpak`, `cargo`, `go` and `vscode` entries, sorted and commented with the feature that wants each |
| `generated/configuration.winget` | sync, `winget configure` (Windows) | Enabled features' `winget` entries as `Microsoft.WinGet.DSC/WinGetPackage` resources |
| `generated/profile.ps1` | the PowerShell profile stub (Windows) | Enabled `pwsh` fragments in feature order |
| `generated/env.sh` | `~/.config/shell/env.sh` | Enabled `env` fragments in feature order; POSIX, builtins only |
| `generated/zshrc.zsh` | `~/.zshrc` stub | Enabled `zshrc` fragments in feature order |
| `generated/gitconfig` | `~/.config/git/config` include | Profile and feature git fragments |
| `generated/ssh_config` | `~/.ssh/config` include | Profile and feature ssh fragments |
| `generated/backup-apps.json` | settings backup (see [Mackup](#mackup)) | Enabled `backup.mackup.*` apps with their paths, credentials removed |

## Entry points

The files tools and installers write to are local one-line stubs created once
by `apply`. Installers that append to them (OrbStack, conda, Claude Code's
installer, `git config --global`) change only the stub.

| Stub | Loads |
|---|---|
| `~/.zshenv` | `~/.config/zsh/zshenv.zsh` |
| `~/.zprofile` | `~/.config/zsh/zprofile.zsh` |
| `~/.zshrc` | `~/.config/zsh/zshrc.zsh`, then `generated/zshrc.zsh` |
| `~/.bashrc`, `~/.bash_profile` | `~/.config/shell/env.sh` |
| `~/.gitconfig` | read by git after `~/.config/git/config`; `git config --global` writes here |
| `~/.ssh/config` | its own lines first (local wins), then `Include` of `generated/ssh_config`, then the shared base |
| `$PROFILE.CurrentUserAllHosts` (Windows) | the tracked PowerShell profile, then `generated/profile.ps1` |

On Windows, `%USERPROFILE%\.gitconfig` and `%USERPROFILE%\.ssh\config` follow
the same rules. `apply` creates `~/.claude`, `~/.local/bin`, `~/.local/share`
and `~/.ssh` before it links anything, and links file by file (see
[Platforms](#platforms)), so no directory in `$HOME` becomes a link into the
repo.

## Automation

One scheduler, `dotfiles run`, called by the OS scheduler (launchd, systemd
user timers or Task Scheduler; see [Platforms](#platforms)). Each step is its own
feature, runs independently, records its result in the state directory, and
never stops the steps after it.

| Feature | Default schedule | Step |
|---|---|---|
| `sync.pull` | every 4 h, at load | Fetch and merge the repo; stop on conflict and notify |
| `sync.apply` | after every pull that changed something | `dotfiles apply` |
| `sync.packages` | after apply, only when a generated package file changed or the last install failed | `brew bundle install --no-upgrade` under `umask 022`; `winget configure` on Windows |
| `sync.publish` | after apply | `git add -u` (tracked files only), gitleaks, signed commit, check the signing key is on GitHub, push. Skips while `index.lock` exists or a changed file is younger than 30 minutes |
| `sync.aux-repos` | after publish | Opt-in list of repos under `~/.sync`; gitleaks before every push |
| `backup.mackup` | after publish | Mackup backup of enabled apps to the private backup repo |
| `update.brew` | weekly, Friday 09:00 | `brew update`, `brew upgrade`; `brew doctor` is logged, never fatal |
| `update.mas` | weekly (macOS) | `mas upgrade` |
| `update.winget` | weekly (Windows) | `winget upgrade --all` |
| `update.flatpak` | weekly (Linux) | `flatpak update --noninteractive` |
| `update.zinit` | weekly | zinit self-update, then `zinit update --all` (plugins and Oh My Zsh snippets) |
| `update.rustup`, `update.cargo` | weekly | `rustup update`; reinstall `cargo` entries whose crates.io version changed |
| `update.mise` | weekly | `mise upgrade` for the global tool versions; on the canary machine, trial the newest mise release and bump the pin (see [Language versions](#language-versions)) |
| `update.uv-tools` | weekly | `uv tool upgrade --all` |
| `status.refresh` | after every run | Re-run checks, write the status JSON and page |

Every scheduled job runs the `dotfiles` binary directly with an explicit
`PATH` (on macOS including `/opt/homebrew/bin` and `/opt/homebrew/sbin`), never
through `bash -l`. Failures post a desktop notification where the OS has one,
and always show on the status page.
Oh My Zsh is used only as zinit snippets; a full `~/.oh-my-zsh` checkout is
reported by `doctor` as unused.

### Verifying it works

`dotfiles doctor --automation` and the status page report, per scheduled
feature: whether its job is registered (`launchctl print gui/<uid>/<label>`,
`systemctl --user show <unit>.timer`, `Get-ScheduledTaskInfo`), its last start
and exit status, whether the last
successful run is within twice its interval, and the step's own last result.
A stale or failing step turns the machine's status red.

## Status page

`dotfiles status` prints a table; `dotfiles status --open` writes
`status.html` in the state directory and opens it. The page is a single
static file with no external assets and no listener; `status.refresh` rewrites
it after every scheduled run. File mode is 0600.

Sections:

1. **Machine.** Hostname, OS and version, profiles, repo commit, last pull,
   apply, publish and update with their results.
2. **Features.** One row per feature: id, category, desired state with the
   source of the decision (`default`, `profile:dev`, `machine`), actual state
   (`ok`, `drift`, `missing`, `error`) with detail, and required-by links.
   Filters for category and for drift only.
3. **Automation.** Each scheduled job: registered, last run, last exit, next run.
4. **Drift.** Homebrew packages no feature wants, wanted packages that are
   missing, link conflicts, managed copies that drifted, stub files that no
   longer load their target.
5. **Manual steps.** Pending sudo actions, logins (gh, Claude, Codex), keys not
   on GitHub, secrets not present. Secrets show presence only, never values.

## Feature catalog

Initial catalog, grouped by category. Each row is one toggle.

| Category | Features |
|---|---|
| shell | `shell.core`, `shell.prompt.dracula`, `shell.plugins.autosuggest`, `shell.plugins.syntax-highlighting`, `shell.plugins.autopair`, `shell.plugins.fzf`, `shell.plugins.you-should-use`, `shell.zoxide`, `shell.atuin`, `shell.direnv`, `shell.mise`, `shell.modern-aliases`, `shell.safety-aliases`, `shell.greeting`, `shell.claude-launchers`, `shell.gitstead` |
| shell.omz | `shell.omz.git`, `shell.omz.git-auto-fetch`, `shell.omz.colored-man-pages`, `shell.omz.extract`, `shell.omz.docker-compose`, `shell.omz.terraform`, `shell.omz.golang`, `shell.omz.node`, `shell.omz.npm`, `shell.omz.ruby`, `shell.omz.rake`, `shell.omz.rsync`, `shell.omz.tmux`, `shell.omz.vscode`, `shell.omz.web-search`, `shell.omz.copyfile`, `shell.omz.encode64`, `shell.omz.iterm2`, `shell.omz.gpg-agent` |
| agents | `agents.claude.bash`, `agents.claude.telemetry`, `agents.claude.mcp`, `agents.codex.bash`, `agents.codex.telemetry`, `agents.opencode`, `agents.agent-monitor`, `agents.agent-mcp`, `agents.otel-agent` |
| sync and update | `sync.pull`, `sync.apply`, `sync.brew-install`, `sync.publish`, `sync.aux-repos`, `update.brew`, `update.mas`, `update.zinit`, `update.rustup`, `update.cargo`, `update.mise`, `update.uv-tools`, `status.refresh` |
| packages | `brew.base`, `brew.dev`, `brew.desktop`, `brew.media`, `brew.mas`, `brew.vscode`, `brew.go-tools`, `brew.cargo-tools`, `winget.base`, `winget.dev`, `winget.desktop`, `flatpak.desktop` |
| backup | `backup.mackup`, `backup.mackup.<app>` for each app in Mackup's catalog, including `backup.mackup.macosx` |
| macOS | `macos.defaults.finder`, `macos.defaults.dock`, `macos.defaults.keyboard`, `macos.defaults.trackpad`, `macos.defaults.screenshots`, `macos.firewall`, `macos.power.server`, `macos.remote-login`, `macos.spotlight` |
| Linux | `linux.linger`, `linux.firewall`, `linux.flatpak` |
| Windows | `windows.powershell-profile`, `windows.developer-mode` (lets the engine use symlinks; needs admin once), `windows.terminal`, `windows.git-bash` |
| browsers | see [Browsers](#browsers) |
| tools | `tool.toggl-focus`, `tool.go-cache-trim`, `tool.aws-profile`, `tool.gpg-signing` |
| security | `security.listeners-loopback` (opencode binds to loopback; the agent-monitor gate is the only LAN listener, opt-in and token-checked) |

## Mackup

Mackup backs up application settings that are not practical to declare,
including macOS's own (`macosx`: `.GlobalPreferences.plist`, symbolic hotkeys,
key bindings, Scripts, Workflows, PDF Services). Declarative system settings
stay in the platform defaults features; Mackup carries what is left.

Mackup supports macOS and GNU/Linux only; upstream tests on macOS 15 and 26
and Ubuntu 22.04, 24.04 and 26.04. `backup.mackup` and every
`backup.mackup.<app>` feature are `darwin` and `linux` features. Windows app
settings are decision D28.

### Rules

> **Mackup runs only in copy mode, only through the engine, and never creates
> a symlink.** `mackup link install`, `mackup link` and `mackup link
> uninstall` are never used. Backup never modifies an original file. Restore
> replaces originals for one named app at a time, after a snapshot, and rolls
> back if anything fails.

### Traps

Verified on 2026-11-11 against Mackup 0.11.2's source (`application.py`,
`utils.py`) and the upstream issue tracker. Each trap has a guard, described
under [Running Mackup safely](#running-mackup-safely).

| Trap | Evidence | Guard |
|---|---|---|
| Before 0.9.0, `mackup backup` was link mode: it moved originals into the store and replaced them with symlinks | Data-loss reports [#1859](https://github.com/lra/mackup/issues/1859), [#1913](https://github.com/lra/mackup/issues/1913), [#1944](https://github.com/lra/mackup/issues/1944); copy mode arrived in [PR #2085](https://github.com/lra/mackup/pull/2085), merged 2025-10-18. Nix 24.11 and 25.05 still ship 0.8.41, and one AUR package ships 0.8.24 | Version gate |
| Link mode breaks macOS preferences: since macOS 13.4 and 14, apps and `defaults` refuse to read or save a symlinked preference file, so settings reset | README warning ([#2035](https://github.com/lra/mackup/issues/2035)); [#1924](https://github.com/lra/mackup/issues/1924), [#1916](https://github.com/lra/mackup/issues/1916); open: [#1564](https://github.com/lra/mackup/issues/1564), [#1890](https://github.com/lra/mackup/issues/1890), [#1858](https://github.com/lra/mackup/issues/1858) (a storage move breaks every link), [#2067](https://github.com/lra/mackup/issues/2067) and [#2117](https://github.com/lra/mackup/issues/2117) (link leftovers break copy mode) | Command allowlist; link-residue check |
| Copy-mode restore deletes the original first | `copy_files_from_mackup_folder` calls `utils.delete` on the home path (`shutil.rmtree` for a directory) and then copies; a `PermissionError` during the copy is printed and skipped, so the original is already gone. 14 stock definitions write into `Library/Containers` or `Library/Group Containers`, and [#2109](https://github.com/lra/mackup/issues/2109) shows macOS refusing access to an Apple preference file | Restore snapshot and rollback; container apps off by default |
| Restore rewrites what it leaves behind | `utils.delete` strips ACLs and immutable flags first; `utils.chmod` forces every file to 0600 and every folder to 0700, so scripts and AppleScript apps stop running ([#1215](https://github.com/lra/mackup/issues/1215), [#2003](https://github.com/lra/mackup/issues/2003)); a symlinked original, such as a dotfiles link, is deleted and replaced with a copy | Mode manifest; symlink pre-flight |
| `mackup backup --force` can delete an original | Backup deletes the store copy before copying. When a parent directory of the path is a link into the store, a link-mode leftover, that "store copy" is the original | Staging; link-residue check |
| Symlinks are followed and their targets copied | [#1979](https://github.com/lra/mackup/issues/1979), [#1741](https://github.com/lra/mackup/issues/1741) (a 350 MB alias target) | Symlink pre-flight |
| A copy error leaves a partial backup | Backup prints `PermissionError` and continues | Partial-backup handling |
| A store inside a backed-up path recurses | [#1766](https://github.com/lra/mackup/issues/1766) | Path check |
| No prune: files deleted from `$HOME` stay in the store | [#2190](https://github.com/lra/mackup/issues/2190) | Staging |

### Running Mackup safely

Decision D30: Mackup's own `backup` and `restore` do the copying, and the
engine wraps every call:

- **Version gate.** Mackup is installed only from Homebrew (macOS and Linux)
  and must report 0.11.2 or later before any call; distribution, Nix and pip
  copies are refused. `doctor` reports any older `mackup` on PATH.
- **Command allowlist.** The engine runs only `mackup --force --config-file
  <generated> backup` and `mackup --force --config-file <generated> restore
  <app>`, always naming the app on restore. The interactive `mackup` wrapper
  refuses `link`, `link install`, `link uninstall` and a restore without an
  app name; `command mackup` remains available on purpose.
- **Link-residue check.** Before every call, the engine refuses to run while
  any symlink under `$HOME` points into a store or staging directory.
- **Path check.** No enabled definition may cover the store, the staging
  directory or the state directory.
- **Symlink pre-flight.** The engine parses each enabled app's definition
  (from the installed Mackup package and `~/.config/mackup/applications/`) and
  leaves out of the run any app whose paths are, or contain, a symlink. That
  covers every dotfiles-managed app, so a restore can never replace a link
  with a copy. Left-out apps are listed on the status page.
- **Credential filter.** For each stock app whose paths include credential
  files, the engine generates an override in
  `~/.config/mackup/applications/<app>.cfg` with those paths removed (custom
  definitions take priority over stock ones in `appsdb.get_config_files`).
  Apps that are nothing but credentials (`pass`, `kubectl`, the 1Password
  plists) are left out. Paths in stock definitions that hold credentials
  include codex `.codex/auth.json`, opencode `auth.json`, the whole `.aws`
  directory, `.kube/config`, `.docker/config.json`, `.npmrc`,
  `.gem/credentials`, composer `auth.json`, gmailctl `credentials.json`,
  context7 `credentials.json`, factory `auth.json`, rclone's config and
  `.password-store`. A path is a credential when it matches `auth`, `token`,
  `credential`, `secret`, `password`, `.netrc`, `.npmrc`, `.pgpass`, `*.pem`,
  `*.key`, `id_*` or `keychain`, or appears in the feature's refusal list.
- **Container apps off by default.** The 14 stock apps whose files sit in
  `Library/Containers` or `Library/Group Containers` start disabled, because
  macOS can refuse the copy partway through. Enabling one is a per-machine
  choice.
- **Staging.** Backup writes into an empty staging directory, so Mackup's
  delete-before-copy only ever deletes inside staging. The engine then
  replaces the machine's directory in the store with it, so deletions show in
  git.
- **Partial-backup handling.** When Mackup reports a copy error for an app, the
  engine keeps that app's previous files in the store instead of swapping in
  the incomplete copy, and marks the run partial on the status page.
- **Mode manifest.** Backup records the mode of every file it covers in
  `manifest.json` beside the backup, because Mackup stores everything as 0600.
  Restore re-applies those modes.
- **Restore snapshot and rollback.** Before `mackup restore <app>`, the engine
  copies the app's current files, with their modes, extended attributes and
  ACLs (`ditto` on macOS, `cp -a` on Linux), into
  `<state>/mackup/snapshots/<timestamp>/<app>/`. After the restore it checks
  that every expected file exists and matches the store's content hash. On any
  error or mismatch it puts the snapshot back. The last ten snapshots are
  kept (`mackup.snapshots_keep`).
- **macOS preferences.** Restore refuses while the app that owns a preference
  domain is running (the plist name is its bundle identifier), and restarts
  `cfprefsd` afterwards so macOS rereads the restored files (D11).
- **Only backup is scheduled.** Restore always runs by hand.

### What gets backed up

- **Every app Mackup supports, wherever its files exist**, minus the
  exclusions above. Each app is a feature, `backup.mackup.<app>`. A profile
  turns off the apps its role does not use (the `work` profile only enables
  apps used for work), and `machine.toml` can turn off any one.
- **Custom definitions** for apps Mackup lacks live in
  `features/backup.mackup/apps/*.cfg`, installed into
  `~/.config/mackup/applications/` as real files.

### Store: per machine, with a shared common set

Decision D27 (recommended): one private repository per context, so a work
machine never holds personal data and a personal machine never holds work
data. Each profile names its context's store (`mackup.store`). Inside it:

```text
mackup-personal/
  common/      apps shared by every machine in the context
  studio/      apps specific to studio
  mini/        apps specific to the Mac mini
```

- **Scope.** Each enabled app has one scope on each machine: `common` or
  `host` (`backup.mackup.<app>.scope`, default `host`). A profile sets the
  shared defaults, such as a terminal or a window manager everyone uses the
  same way, and `machine.toml` overrides one app.
- **One writer for common.** Only the context's `mackup.common_source` machine
  backs up `common/`; every other machine reads it. Machines never write the
  same directory, so backups never conflict. `dotfiles mackup promote <app>`
  copies one app's current files from any machine into `common/` when that
  machine's settings should become the shared ones.
- **Two runs.** Backup runs Mackup once per scope, each with its own generated
  configuration (`[storage] engine = file_system`, `path` = staging,
  `directory` = `common` or `<host>`).
- **Restore source.** A `common` app restores from `common/`; a `host` app
  restores from `<host>/`, or from another machine of the same context with
  `--from <host>`. Restores never cross contexts.
- **Publishing.** After each backup the publisher stages the changed
  directories, runs gitleaks over the staged diff, refuses files larger than
  5 MB and paths that match the credential patterns, confirms the remote is
  private (`gh api repos/<owner>/<repo> --jq .private`), encrypts (D9),
  commits signed and pushes.

## Secrets

A 1Password vault is the source of truth for every secret a feature needs;
each machine's OS secret store is its cache (see [Platforms](#platforms)). The
engine reaches the store through one interface and picks the backend by
testing what works on the machine, not by OS name, so a headless Linux host
without a Secret Service session falls back cleanly.

| Step | Mechanism |
|---|---|
| Declare | A feature setting of type `secret` holds an `op://<vault>/<item>/<field>` reference, never a value |
| Sync | `dotfiles secrets sync` runs `op read` for each reference of the enabled features and writes the value to the store as `dotfiles/<feature>/<field>`. It runs interactively, so 1Password's desktop-app unlock applies (Touch ID on macOS, Windows Hello on Windows, PolKit system authentication on Linux) |
| Use | Features and scheduled jobs read only the store, so a 3 a.m. job never waits on a 1Password prompt |
| Render | Config files that must contain a secret (for example `~/.wakatime.cfg`) are rendered from templates at apply time, mode 0600, outside the repo |
| Report | The status page shows each secret's presence and last sync time, never the value |

Item layout: one 1Password item per service, with fields `url`, `api_key` or
`token`, and `username`/`password` where the service needs them. The vault
name and the headless option are decisions D12 and D13.

Constraints:

- A secret placed in browser policy (Chromium managed storage or Firefox
  `3rdparty`) lives where any local user can read it: `/Library/Managed
  Preferences`, `HKLM`, or `/etc`. That is
  acceptable only for low-value keys scoped to one service; anything else is
  entered by hand or imported from a file.
- Firefox's macOS user defaults domain (`~/Library/Preferences`) is readable
  only by the user; its Windows and Linux policy locations are not.
- Secrets never enter the environment of shells or agents, logs, the status
  page, or the repo.

## Browsers

Requirements:

- One catalog, `features/browser.extensions/catalog.toml`, with each
  extension's Chrome Web Store ID and Firefox add-on GUID. Each extension is a
  feature (`browser.<browser>.ext.<name>`), and each browser is a feature
  (`browser.<browser>.extensions`).
- Install, update and removal are scripted and reversible; disabling a feature
  removes its entries.
- Firefox entries are keyed by add-on GUID, never by listing name, because the
  add-on site carries look-alike listings for several of these extensions.
- Bypass Paywalls Clean is its own feature per browser, off by default, pinned
  to its genuine source with integrity checks.
- The status page compares installed extensions against the catalog.

### Mechanisms

| Browser | Mechanism | Root | Removal |
|---|---|---|---|
| Firefox | `org.mozilla.firefox` user defaults domain: `EnterprisePoliciesEnabled = true` and a generated `ExtensionSettings` dictionary keyed by add-on GUID. Survives app updates and leaves the app signature intact | no | Two phases: rewrite the entry as `blocked` (Firefox uninstalls it at next start), then drop it once no profile's `extensions.json` lists it. Dropping an entry alone only makes the add-on user-removable |
| Chrome, Brave | `/Library/Managed Preferences/com.google.Chrome.plist` and `com.brave.Browser.plist`, owned `root:wheel` 0644, generated whole and installed only when its hash changes, then `killall cfprefsd`. `ExtensionSettings` entries use `normal_installed` with the Web Store update URL | yes | Remove the entry; the browser uninstalls the extension at next start. Delete the file when nothing is left |
| Safari | Host apps through `mas`; enabling has no supported command line outside supervised MDM | `mas install` needs root | Manual; shown on the status page |

The table above is macOS. Windows and Linux take the same policy content in
each OS's own location (checked 2026-11-11 against Chromium, brave-core and
Firefox source):

| Browser | Windows | Linux |
|---|---|---|
| Chrome | `HKLM\SOFTWARE\Policies\Google\Chrome`, written with admin rights only when the generated policy changes | `/etc/opt/chrome/policies/managed/dotfiles.json` (root); the Flathub build reads the host path |
| Brave | `HKLM\SOFTWARE\Policies\BraveSoftware\Brave` (Home editions included) | `/etc/brave/policies/managed/dotfiles.json`; the Flathub build reads it; the Snap build probably cannot (rollout gate) |
| Chromium | not targeted | `/etc/chromium/policies/managed/`; Ubuntu's snap reads `/etc/chromium-browser/policies/` instead; the Flathub build needs a policy extension directory |
| Firefox | `HKLM\SOFTWARE\Policies\Mozilla\Firefox`; `3rdparty` values are REG_SZ JSON | `/etc/firefox/policies/policies.json`, which is then the only policy file read; the Snap reads it too; the Flathub build reads `/var/lib/flatpak/extension/org.mozilla.firefox.systemconfig/<arch>/stable/policies/policies.json` |

Removal works the same way on every OS. Profile and extension records for the
checks live under `%LOCALAPPDATA%` (Chromium family) and `%APPDATA%\Mozilla\Firefox`
on Windows, and under `~/.config/<browser>`, `~/.mozilla/firefox` (or
`$XDG_CONFIG_HOME/mozilla/firefox` on new profiles), `~/snap/<name>/` and
`~/.var/app/<id>/` on Linux.

Rejected mechanisms:

- **User-level `defaults write com.google.Chrome` or `com.brave.Browser`.**
  Chromium reads non-forced values as recommended, and extension policies
  require mandatory ones.
- **External Extensions JSON files.** They prompt for each extension, and once
  the user removes an extension Chromium never offers it again, so a script
  cannot converge.
- **`policies.json` inside `Firefox.app`.** It breaks the code signature and is
  replaced on every update.
- **Configuration profiles.** Since macOS 11, `profiles` cannot install them
  from the command line; each change needs approval in System Settings. This
  is the fallback only if the managed-preferences file does not survive a
  reboot (rollout gate below).

Constraints on unmanaged machines:

- On macOS and on Windows machines that are not AD- or Entra-joined,
  MDM-registered or enrolled in Chrome Enterprise Core, Chromium filters out
  every policy install whose update URL is not the Web Store. Off-store
  extensions can only be allowlisted (`installation_mode = "allowed"`) and then
  installed by hand. Linux applies no filter, so off-store installs work there.
- Chrome removed Manifest V2 support; uBlock Origin Lite replaces uBlock
  Origin there. Brave hosts uBlock Origin, NoScript, uMatrix and AdGuard as MV2
  extensions under its own IDs (uBlock Origin is
  `jcokkipkhhgiakinbnnplhkdbjbgcgpe`), exempted from the MV2 removal by ID
  whatever installed them. Enabling one is a toggle at
  `brave://settings/extensions/v2`, shown as a manual step, unless the rollout
  gate below shows a bare `ExtensionInstallForcelist` entry installs it.
- On macOS and non-enterprise Windows, Chrome checksums its homepage, startup,
  search and extension preferences and resets edits made outside the browser,
  so preference files are never edited directly.

Extension settings:

- Chromium managed storage lives in
  `/Library/Managed Preferences/<bundle>.extensions.<id>.plist`, for example
  the uBlock Origin Lite rulesets.
- Firefox takes `3rdparty.Extensions.<guid>` in the same defaults domain, with
  each value a JSON string (plist booleans arrive as 1 and 0).

Checks:

- **Chromium:** profiles come from `Local State`. Each profile's
  `Secure Preferences` gives every extension's install location and disable
  reasons; `Extensions/<id>/<version>/manifest.json` gives versions. The
  installed policy file is compared with the generated one.
- **Firefox:** profiles come from `profiles.ini`, and each profile's
  `extensions.json` gives `id`, `version`, `active` and `signedState`. The
  defaults domain is compared with the generated dictionary.
- **Safari:** `mas list` and `pluginkit -m -p com.apple.Safari.web-extension`;
  enabled state is reported as manual.

Rollout gates to verify before relying on the design:

- `/Library/Managed Preferences` files persist across a reboot and show as
  Platform / Mandatory at `chrome://policy`.
- Firefox policy installs pick up new host permissions on update without a
  prompt.
- Whether a bare `ExtensionInstallForcelist` entry installs Brave's hosted
  MV2 IDs (expected on every OS, including unmanaged Windows; an explicit
  Brave update URL would be filtered on macOS and Windows).
- Whether Brave's Snap build reads `/etc/brave/policies`.

### Bypass Paywalls Clean

Not on the Chrome Web Store, and removed from the Firefox add-on site after
DMCA notices, though still Mozilla-signed. Publishers file DMCA notices
against it; enabling it is the machine owner's decision. The maintainer
(`magnolia1234`) publishes on GitFlic: code in
`bypass-paywalls-{chrome,firefox}-clean`, builds in `bpc_uploads`, update
manifests in `bpc_updates`. Identity is checked cryptographically, never by
name:

| | Firefox | Chromium |
|---|---|---|
| ID | `magnolia@12.34`, signed by Mozilla's add-on CA (only the owning account can obtain a signature for that ID) | `lkbebcjgcmobigpeffafkodonchffocl`, equal to the CRX3 header ID and the SHA-256 of its public key |
| Update manifest | `bpc_updates` `updates.json` | `bpc_updates` `updates.xml` |
| Scripted install | Yes, silent, through `ExtensionSettings` with an `install_url`; auto-updates, each update signature-checked | No silent install without MDM; policy allowlists the ID, the client downloads and verifies the crx, the user installs it once per profile, then it auto-updates |
| Pin | ID, signer certificate, and SHA-256 of the first download from the catalog | ID derived from the key, and SHA-256 of the first download |

`browser.firefox.bypass-paywalls` is the recommended toggle: it's the only
fully scripted, signature-enforced path, and it keeps an extension with
cookie access on about 950 sites out of the main browser. Its strict mode pins
a local, verified xpi with updates disabled and bumps the version from the
catalog. Residual risks are compromise of the maintainer's account and the
hosting's availability.

### Self-hosted app extensions

Extensions that pair with the self-hosted apps in the home cluster are
features in the same catalog. Each needs a server URL and usually an API key;
both come from the app's 1Password item (see [Secrets](#secrets)). How an
extension's settings get provisioned depends on what it supports, in this
order of preference:

1. Managed storage: Chromium `storage.managed_schema` through
   `<bundle>.extensions.<id>.plist`, or Firefox `3rdparty.Extensions.<guid>`.
2. A settings file the extension imports: rendered to
   `~/.local/state/dotfiles/browser-import/<extension>.json` (mode 0600),
   with a manual import step on the status page.
3. Manual entry: `dotfiles secret copy <feature>.<field>` puts the value on
   the clipboard and clears it after 30 seconds.

None of the evaluated Chrome Web Store packages declares
`storage.managed_schema`, so route 1 is unavailable on Chrome and Brave for
every extension below. On Firefox only New Tab Override reads managed
settings. Many extensions keep their settings in `storage.sync`, so those are
entered once per browser sync account rather than once per machine.

Apps whose API path sits behind SSO forward-auth reject an extension's API
key: the proxy checks for its session, then treats the key as a credential it
does not recognise. Those extensions need the app's API path exempted at the
ingress first, as is already done for several apps.

| App | Extension (Chrome ID / Firefox GUID) | Needs | Route | Verdict |
|---|---|---|---|---|
| wallabag | wallabagger `gbmgphmejlcoihgedabhgjdkcahacjlj` / `{7a7b1d36-d7a4-481b-92c6-9f5427cb9eb1}` | URL, OAuth client id and secret, username, password | 2: "Load from file" `wallabag.json` | Alternative to Readeck (D25) |
| Readeck | Readeck `jnmcpmfimecibicbojhopfkcbmkafhee` / `readeck@readeck.com` | URL; sign-in is OAuth approved in the browser | 3, no secret | Add |
| Karakeep | Karakeep `kgcjekpmcjjogibpjebkhaanilehneje` / `addon@karakeep.app` | URL, API key | 3 | Add |
| Linkwarden | Linkwarden `pnidmkljnhbjfffciajlcpeldoljnidn` / `jordanlinkwarden@gmail.com` | URL, API key | 3 | Alternative to Karakeep |
| LiteLLM | Page Assist `jfgfiigpkhlkbnfnbobbkinehhfdhndo` / `page-assist@nazeem` | OpenAI-compatible base URL, key | 2: data export/import | Add |
| Wakapi | WakaTime `jnbbnacmeggbgdjgaoojpmhdlkkpblgi` / `addons@wakatime.com` | Wakapi's WakaTime-compatible API URL, key | 3 (synced); `~/.wakatime.cfg` rendered for editor plugins | Add |
| RSSHub, FreshRSS | RSSHub Radar `kefjpfngnndepjbopdmoebkipbgkggaa` / `i@diygod.me` | RSSHub URL and access key, FreshRSS URL | 3 | Add |
| Invidious, Piped, Redlib | LibRedirect `7esoorv3@alefvanoon.anonaddy.me` (Firefox only; no current Chrome build) | Instance URLs | 2: settings import | Add on Firefox |
| Memos | Memos Web Clipper `nebaoebnljalfegiidibihhkebeiklbl` / `web-clipper@usememos.com` | URL, access token | 3 | Optional |
| Bookmark sync | floccus `fnaicdffflnofjppbagibeoednhnbjhg` / `floccus@handmadeideas.org` | Backend URL and credentials: Nextcloud Bookmarks, WebDAV, Karakeep or Linkwarden | 2: `floccus.export.json` | Add |
| Homepage | New Tab Override `newtaboverride@agenedia.com` (Firefox) | New-tab URL | 1: Firefox `3rdparty` | Add on Firefox |
| ArchiveBox | ArchiveBox `habonpimjphpdnmcfkaockjnffodikoj` / `archivebox@tjhorner.dev` | URL, API key | 3 | After API-path exemption |
| Tube Archivist | Tube Archivist Companion `jjnkmicfnfojkkgobdfeieblocadmcie` / `{08f0f80f-2b26-4809-9267-287a5bdda2da}` | URL, API token | 3 | After API-path exemption |
| Sonarr, Radarr, Lidarr | Sonarr/Radarr/Lidarr Autosearch `jmmjjcddjldjdjgckdiokhfokccdnekc` / `sonarr-radarr-lidarr-autosearch@robgreen.me` | URL and API key per instance | 2: backup JSON | Optional |
| Seerr | Overseerr Assistant `hopnjiadheaagfhpipecoamoegijhnij` / `RemiRigal@Overseerr-Assistant` | Host, API key | 3 (synced) | Optional |
| SABnzbd | NZB Unity `mpejfoghnejnbfkpbiafklkmlhebkapb` / `{96586e48-b9a2-45dd-b1a1-54fa85a97c91}` | URL, API key | 3 | Optional |
| rTorrent | Remote Torrent Adder `oabphaconndgibllomdcjbfdghcmenci` / `remote-torrent-adder@bogenpirat` | ruTorrent URL, username, password | 2: JSON import | Optional |
| FreshRSS | FreshRSS Checker `fkckemcdpfnblnkndachclpjfmlhofeg` / `freshrss-checker@addons.mozilla.org` | URL, username, API password | 3 | Optional |
| Mealie, Vikunja, Kimai | Mini Mealie, Vikunja Quick Add, Kimai (community, small user bases) | URL, token | 3 | Optional |
| ActivityWatch | aw-watcher-web `nglaklhklhcoonedhgnpgddginnjdadi` / `{ef87d84c-2127-493f-b952-5b4e744245bc}` | Fixed to a local ActivityWatch server | 3 | Only with the local ActivityWatch app |

Skipped: changedetection.io (stale since 2025-03, and behind forward-auth),
Sourcegraph (its listing is live, but it decorates GitHub pages, not Gitea),
Joplin Web Clipper (needs the desktop app), Immich, Paperless-ngx and Home
Assistant (unofficial, stale or trivial), ntfy, Outline and Open WebUI (no
worthwhile extension). Five save-a-page apps run in the cluster (wallabag,
Readeck, Karakeep, Linkwarden, ArchiveBox); choosing one or two avoids five
overlapping extensions (D25).

Settings files for route 2 are rendered with
`op inject -i <template> -o <file> --file-mode 0600`, imported, then deleted.

### Search engine and start page

| Browser | Search engine | Home and new tab | Notes |
|---|---|---|---|
| Firefox | Every OS. `SearchEngines` policy: add the SearXNG engine with its search and suggestion URL templates and make it `Default`. Available in all Firefox releases since 139 | `Homepage` policy for the start page; New Tab Override (managed) for the new-tab page, since the `NewTabPage` policy is on/off only | Scripted through the defaults domain |
| Chrome, Brave | Linux: `DefaultSearchProvider*` policies. macOS and Windows: not scriptable on an unmanaged machine | Linux: `HomepageLocation`, `NewTabPageLocation`, `RestoreOnStartup*`. macOS and Windows: not scriptable | These are sensitive policies that Chromium ignores on macOS and Windows unless the machine is managed; Linux honours them. The initial-preferences file applies only when a profile is first created. On macOS and Windows they are set by hand and listed as a manual step |

### Initial catalog

Chrome Web Store removed every Manifest V2 listing on 2026-08-31, so several
extensions now differ between Chromium browsers and Firefox.

| Extension | Chrome / Brave | Firefox |
|---|---|---|
| uBlock Origin | Chrome: uBlock Origin Lite `ddkjiahejlhfcafbddmgiahcphecmpfh`; Brave: its hosted MV2 build (manual toggle) | `uBlock0@raymondhill.net` |
| Privacy Badger | `pkehgijcmpdhfbdbbnkijodmdjhbjlgp` | `jid1-MnnxcxisBPnSXQ@jetpack` |
| Decentraleyes | `ldpochfccmkkmhdbclfhpagapcfdljkj` | `jid1-BoFifL9Vbdl2zQ@jetpack` |
| ClearURLs | none (removed, no vetted MV3 port) | `{74145f27-f039-47ce-a470-a662b129930a}` |
| PiHole Browser Extension | `ngoafjpapneaopfkpboebcahajopcifi` | `{a4cc20af-d30a-4758-a799-2089ce45f452}` |
| ToS;DR | `hjdoplcnndgiblooccencgcggcoihigg` | none until relisted |
| Dark Reader | `eimadpbcbfnmbkopoojfekhnkhdbieeh` | `addon@darkreader.org` |
| Vimium | `dbepggeogbaibhgnhhndojpepiihcmeb` | `{d7742d87-e61d-4b78-b8a1-b469842139fa}` |
| Just Read | `dgmanlpmmkibanfdgjocnabmcaclkmod` | `{cb2b337b-99d7-4b86-aa04-84a6f5c3e218}` |
| Buster | `mpbjkejclgfgadiemmefgebjfooflfhl` | `{e58d3966-3d76-4cd9-8552-1582fbc800c1}` |
| Don't F*** With Paste | `efaagigdgamehbpimpiagfpoihlkgamh` | `dont-fuck-with-paste@abg1979.github.io` |
| Extensity | `jjmflmamggggndanpgfnpelongoepncg` | none (use about:addons) |
| Old Reddit Redirect | `dneaehbmnbhcippjikoajpoabadpodje` | `{9063c2e9-e07c-4c2c-9646-cfe7ca8d0498}` |
| Reddit Enhancement Suite | `kbmfpngjjgdllneeigpgjifpgocmfgmb` | `jid1-xUfzOsOFlzSOXg@jetpack` |
| Open in IINA | `pdnojahnhpgmdhjdhgphgdcecehkbhfo` | `open_in_iina_firefox@iina.io` |
| RegExp Download Organizer | `oamembonjndgangicfphlckkdmagpjlg` | none (only an untrusted port) |
| WakaTime | `jnbbnacmeggbgdjgaoojpmhdlkkpblgi` | `addons@wakatime.com` |
| Todoist | `jldhpllghnbhlbpcmnajkpdmadaolakh` | `support@todoist.com` |
| Toolkit for YNAB | `lmhdkkhepllpnondndgpgclfjnlofgjl` | `{4F1FB113-D7D8-40AE-A5BA-9300EAEA0F51}` |
| NordVPN | `fjoaledfpmneenckfbpdfhkmimnjocfa` | `nordvpnproxy@nordvpn.com` |
| Notion Web Clipper | `knheggckgoiihginacbkhaalnibhilkk` | none (only look-alike listings) |
| RescueTime | none (the desktop app tracks Chromium browsers) | `rescuetime_firefox@rescuetime.com` |
| Refined GitHub | `hlepfoohegkhhmjieoechaddaejaokhf` | `{a4c4eda4-fb84-4a84-b4a1-f7c1cbf2a1ad}` |
| Material Icons for GitHub | `bggfcpfjbdkhfhfmkjpbhnkhnpjjeomc` | to confirm |
| ZenHub | `ogcgkffhplmphkaahpmffcafajaocjbd` | none |

Optional, off by default: Hacker News UX, View Image, contributors-on-github,
enhanced-github, Octotree.

Not carried over: HTTPS Everywhere (retired; every browser has an HTTPS-only
mode), JSON Viewer (Firefox has one built in), Simple Allow Copy, Smile
Always, friendly-github, GitHub code folding, github-awesome-autocomplete,
hide-files-on-github, octohint and OctoLinker (removed from the store,
archived, or covered natively by GitHub), and Sourcegraph (see self-hosted
app extensions).

Approved (D24). Extension features are off by default, so nothing reaches a
machine unless one of its profiles enables it:

- **`personal` and `work`:** uBlock Origin (Lite on Chrome, Brave's hosted
  build on Brave), Privacy Badger, Decentraleyes, ClearURLs, Dark Reader,
  Vimium, Just Read, Don't F*** With Paste, Extensity, RegExp Download
  Organizer, Refined GitHub, Material Icons for GitHub, contributors-on-github
  and View Image.
- **`personal` only:** Bypass Paywalls Clean, Old Reddit Redirect, Reddit
  Enhancement Suite, Toolkit for YNAB and RescueTime; Enhanced GitHub and
  Octotree, which want a GitHub token to work on private repositories; and the
  self-hosted WakaTime (pointed at Wakapi), LibRedirect, Mini Mealie,
  ArchiveBox and Tube Archivist, which talk to the home cluster.

The split is decision D31. On a machine whose browser already carries
enterprise policy (MDM, Group Policy or Chrome Enterprise Core), the engine
writes no browser policy at all, and the work extensions are listed as manual
installs, so it never fights or overrides the employer's configuration.

## Toggl

`tool.toggl-focus` provides a `toggl-focus` client for the Toggl 2.0 API
(`https://focus.toggl.com/api`, Bearer key): `toggle`, `start [description]`,
`stop`, `status`.

| Setting | Type | Default | Description |
|---|---|---|---|
| `toggl.api_key` | secret | none, required | Toggl 2.0 API key |
| `toggl.organization_id` | secret | none, required | Organization in the timer endpoint paths |
| `toggl.workspace_id` | secret | from `GET /users/me/settings` when unset | Workspace for new entries |

All three are secrets: `op://` references in the base profile, synced into
each machine's secret store by `dotfiles secrets sync`. The client reads them
from the store on each call; they never appear in the environment, a log, the
status page or the repo. Toggl 2.0 allows one active key per user, and creating
a key revokes the previous one, so every machine shares the one key.

## Commit signing

`tool.gpg-signing` keeps each machine's signing key usable and verifiable.
Each machine has its own key; GitHub verifies a commit only when the signing
key is registered on the account and its UID email matches the commit email.

| Check | Result when it fails |
|---|---|
| A secret key matching `user.signingkey` exists and expires in more than 30 days | error |
| The key's UID email equals `git config user.email` | error |
| The key is listed at `https://github.com/<user>.gpg` | error; `sync.publish` refuses to push |
| The account's other public keys and GitHub's web-flow key are in the local keyring | drift; `git log --show-signature` reports `E` (cannot check) for commits signed on other machines and for merges made on GitHub |

`apply` imports the account's published keys and the web-flow key so local
verification works. Registering a new machine's key needs the `admin:gpg_key`
scope (`gh auth refresh -s admin:gpg_key`), then `gh gpg-key add`; the status
page lists it as a manual step until done.

## Agents

| Feature | Mechanism |
|---|---|
| `agents.claude.bash` | A `dotfiles.json` drop-in in the OS's managed-settings directory (see [Platforms](#platforms)) sets `CLAUDE_CODE_SHELL` to bash on macOS and Linux, and `CLAUDE_CODE_GIT_BASH_PATH` on Windows. Installed once with admin rights as a copy of the tracked file, which `apply` keeps in sync |
| `agents.codex.bash` | The system config (`/etc/codex/config.toml`) sets `[features] shell_snapshot = false` and `AGENT_SHELL`; `zshenv.zsh` hands `$ZSH_EXECUTION_STRING` to bash when `AGENT_SHELL` is set, on macOS and on Linux hosts whose login shell is zsh. On Windows, Codex runs PowerShell, and its instructions say so |
| `shell.core` | Interactive-only behaviour (zoxide `cd`, aliases, `AUTO_CD`) loads only in real terminal sessions |
| `shell.core` | `env.sh` applies PATH once per process tree; nested shells keep entries the parent added |

## Language versions

`shell.mise` manages language versions with [mise](https://mise.jdx.dev)
(2026.11.7 when this was written) on macOS, Linux and Windows, replacing fnm
and asdf.

- **Per directory.** mise reads `mise.toml` and `.tool-versions`, plus each
  ecosystem's own files, enabled globally with
  `idiomatic_version_file_enable_tools = ["go", "node", "python"]`: the
  `toolchain` line (or a patch-version `go` line) in `go.mod` and `go.work`
  and `.go-version`; `.nvmrc`, `.node-version` and `package.json`; and
  `.python-version`. A subdirectory uses the nearest file above it.
- **Go.** mise's global `[env]` sets `GOTOOLCHAIN = "local"`, so the
  toolchain mise selected is the one that runs. With Go's default `auto`, the
  `go` command can download and run a newer toolchain than the one mise
  reports.
- **Python.** mise selects the interpreter; uv keeps managing project
  environments (`python.uv_venv_auto` for projects with a `uv.lock`).
- **Interactive shells** use `mise activate zsh` (`mise activate pwsh` on
  Windows), which updates `PATH` at each prompt and directory change.
- **Agents, scheduled jobs and GUI apps** get mise's shim directory on `PATH`
  from `env.sh` (`mise activate --shims`), so each command resolves the
  version for its working directory without a prompt hook. A shim resolves on
  every call; step 3 of the rollout measures the per-command cost.
- **Trust.** A project's `mise.toml` can set environment variables and run
  tasks, so mise applies it only after `mise trust`. Each profile lists its
  own project roots in `trusted_config_paths` (personal and work separately);
  repositories elsewhere stay untrusted, for agents too.
- **Pinned version.** mise ships often (24 releases in the 30 days to
  2026-11-11), so the base profile pins `mise.version`. `apply` installs that
  release from GitHub after checking it against the release's
  `SHASUMS256.txt` and that file's minisign signature, on every OS. Each week,
  `update.mise` on the context's canary machine (`mise.canary`, studio by
  default) installs the newest release, runs `mise doctor` and resolves the
  tool versions of the projects under the trusted roots; when that passes, it
  commits the new pin, and other machines follow on their next pull. A failure
  shows on the status page and the pin stays.
- **Migration.** Node versions installed by fnm are reinstalled through mise;
  `fnm` and `asdf` leave the package lists, and `env.sh` drops `FNM_DIR` and
  the fnm default alias.

## Implementation

A Go command, `cmd/dotfiles`, in this repository: manifest parsing, resolution,
generation, apply and teardown, the scheduler, checks and the status page. Go
gives typed manifests, concurrent checks with timeouts, `html/template` for the
page, table-driven tests, and one static binary per OS and architecture with
no runtime dependencies. Each OS-specific mechanism is an interface with a
backend per OS, selected with build tags.

Bootstrap:

- macOS and Linux: `install.sh` (bash 3.2 compatible) installs the Command
  Line Tools on macOS, then Homebrew and Go, builds `dotfiles` into
  `~/.local/bin`, writes `machine.toml` from `--profiles`, and runs
  `dotfiles apply`.
- Windows: `install.ps1` (Windows PowerShell 5.1 compatible) installs Git for
  Windows and Go with WinGet, builds `dotfiles.exe` into
  `%LOCALAPPDATA%\dotfiles\bin`, writes `machine.toml`, and runs
  `dotfiles apply`.

`apply` rebuilds the binary when its sources change. Shell fragments stay POSIX
sh (env), zsh (interactive) and PowerShell (Windows interactive). Existing
scripts move into the features that own them.

### Testing

- Unit tests for resolution, settings, dependency and conflict errors, and
  generated output, table-driven.
- An integration test that bootstraps into an empty fake `HOME` and runs
  `apply` twice: the second run changes nothing, and nothing untracked links
  into the repo. It runs on macOS, Ubuntu and Windows CI runners; the Windows
  job runs once with symlinks allowed and once without, to cover managed
  copies.
- Agent shell tests with the real Claude Code and Codex command lines.
- `docs/FEATURES.md` is generated from the manifests; CI fails when it is
  stale.

## Decisions

Each entry: the question, why it matters, the options, the recommendation,
and its status. Decided entries record who decided.

### Decided

| ID | Decision | Decided by |
|---|---|---|
| D0.1 | Every capability is a per-machine toggle with fine granularity (each Oh My Zsh plugin, each extension, each scheduled step) | owner |
| D0.2 | Updates and sync run automatically on every machine; a local status page shows feature and automation health | owner |
| D4 | No Tailscale. opencode listens on loopback only (`OPENCODE_HOSTNAME` opts in to another address); the agent-monitor gate stays the opt-in LAN listener for the cluster proxy, token-checked, with its address set by `AGENT_MONITOR_GATE_HOST` | owner |
| D7 | Mackup runs only in copy mode through the engine; link mode is never used, backup never modifies an original, and restore is per app with snapshot and rollback | owner |
| D8 | Mackup's store is a private git repository with one directory per machine | owner |
| D10 | Mackup backs up every app it supports wherever the app's files exist; profiles turn off apps a role does not use, and credential files are removed by generated overrides | owner |
| D17 | Toggl's organization and workspace IDs are secrets, like its key; all three come from 1Password | owner |
| D18 | Targets are macOS, Windows and Linux | owner |
| D20 | mise manages Go, Node, Python and other language versions per directory on all three OSes, replacing fnm and asdf (see [Language versions](#language-versions)) | owner |
| D24 | Extensions approved from the catalog (see [Initial catalog](#initial-catalog)); personal-only ones are enabled by the `personal` profile, never by `work` | owner |
| D25 | No save-a-page extension except ArchiveBox; Readeck, Karakeep, wallabag and Linkwarden are skipped | owner |
| D30 | Mackup's own `backup` and `restore` do the copying, wrapped by the engine's guards (see [Running Mackup safely](#running-mackup-safely)) | owner |
| D0.3 | Browser extensions, including their settings and keys, are scripted; keys come from a 1Password vault | owner |
| D0.4 | Bypass Paywalls Clean is wanted (see D15 for where) | owner |
| D0.5 | Work happens on branch `plan/machine-features` | owner |
| D14 | Chrome and Brave extensions are provisioned through the OS policy location (root on macOS and Linux, admin on Windows); `apply --sudo` runs only when the generated policy changes | owner |
| D16 | Brave uses its hosted MV2 uBlock Origin; enabling it is a manual per-profile toggle listed on the status page | owner |
| D22 | The Mac mini's signing key is registered on GitHub; `tool.gpg-signing` still imports the account's other keys and the web-flow key | done |

### Open

**D1. Which profiles exist?**
Profiles are named feature sets; machines pick several.
Options: role-based (`base`, `dev`, `desktop`, `server`, `work`) plus host
profiles for host facts (`studio`), or host-only profiles.
Recommendation: role-based plus host profiles; host profiles hold only facts
such as volume paths. Status: open.

**D2. Entry points as local stubs, or symlinks into the repo?**
Installers and `git config --global` write into these files; a symlink sends
the write into the public repo.
Options: one-line local stubs created once by `apply`; or symlinks plus
guards. Trade-off: a stub is never updated by the repo, so it must stay one
line.
Recommendation: stubs. Status: open.

**D3. How does Codex get bash?**
Codex always runs the passwd login shell, on Linux as on macOS, and has no
setting to change it; on Windows it only offers PowerShell.
Options: system config (`shell_snapshot = false`, `AGENT_SHELL`) plus a
`.zshenv` hand-off to Homebrew bash; or `chsh` to bash with an interactive
hand-off back to zsh. Trade-off: `chsh` changes `$SHELL` for tmux, ssh and
editors, and breaks logins if Homebrew bash disappears.
Recommendation: system config plus hand-off. Status: open.

**D5. Delete stale inventories?**
`software_list.md`, `Software.md`, `chrome_extensions.md`, `win10/`,
`.zshrc.omz-backup`, the neofetch package and `lib_sh/requirers.sh` duplicate
or contradict current sources.
Recommendation: delete; the generated feature catalog replaces them.
Status: open.

**D6. Language for the feature engine?**
Options: Go (typed manifests, dependency resolution, concurrent checks,
`html/template`, table-driven tests, no runtime dependencies); bash plus
Python's standard library (no build step; macOS's Python 3.9 has no TOML
parser, so manifests would be JSON).
Recommendation: Go. Status: open.

**D9. Encrypt the Mackup store at rest?**
Preference plists can contain license keys and session tokens that gitleaks
does not recognise.
Options: plaintext in a private repo with gitleaks and the credential filter;
or `age` encryption with the key in 1Password, cached in the OS secret store. Trade-off:
encrypted diffs are unreadable in git, and restore needs the key.
Recommendation: encrypt, and treat it as required: the store now covers every
app Mackup supports, and gitleaks cannot vet most of those files.
Status: open.

**D11. How are macOS preference plists restored?**
Mackup copies plist files directly, and `cfprefsd` can hold newer values or
overwrite a copied-in file.
Options: quit the owning app and restart `cfprefsd` after Mackup's restore;
or also re-import each restored plist with `defaults import`.
Recommendation: quit and restart `cfprefsd`; add `defaults import` only for a
domain that restore checks show does not take. Status: open.

**D12. 1Password vault and item layout?**
Proposed: a vault named `dotfiles`, one item per service, fields `url`,
`api_key` or `token`, `username`, `password`. Status: open.

**D13. How do machines without a person present resolve secrets?**
Options:
- Interactive `dotfiles secrets sync` into the OS secret store, with scheduled
  jobs reading only the store. The 1Password desktop-app unlock lasts at most 12
  hours and ends when the app locks, so it suits interactive runs only.
- A 1Password service account. These are available on Individual and Families
  plans, with a limit of 1,000 reads a day per account. The account cannot
  read the built-in Personal or Private vaults, so the secrets live in a
  dedicated vault, and its token is kept in the OS secret store.
- 1Password Connect. The cluster's Connect server has no ingress and is scoped
  to the cluster's vault, so using it from a Mac means exposing it and issuing
  a new token.

Recommendation: the secret-store cache synced interactively; a service account for
machines that need unattended refresh. Status: open.

**D15. Where does Bypass Paywalls Clean run, and how is it pinned?**
Options: Firefox only (silent, signature-checked updates); Chrome and Brave as
well, which is a manual install per profile on macOS and Windows but can be
policy-installed on Linux, where Chromium does not filter off-store installs. Pinning: follow the maintainer's update
manifest, or a strict mode with a verified local file and updates disabled.
Recommendation: Firefox only, following the update manifest with the signer
and ID checked. Status: open.

**D19. Which machines publish?**
`sync.publish` can be off for pull-only machines.
Recommendation: publish from personal machines; pull-only on the work PC.
Status: open.

**D21. The stale remote branch `update_2026`?**
It holds 33 auto-sync commits that never reached `master`. Everything useful
on it is already on `master` except the `erlang@26`, `erlang@27` and `sshpass`
formulae; the rest is duplicated `safe.directory` entries and a committed sync
log. Options: delete; merge.
Recommendation: delete, and add the three formulae to a profile if still
wanted. Status: open.

**D23. Remove the unused `~/.oh-my-zsh` checkout?**
zinit loads Oh My Zsh plugins from its own snippet cache.
Recommendation: remove after confirming; `doctor` reports it until then.
Status: open.

**D26. Exempt API paths from forward-auth for ArchiveBox and Tube Archivist?**
Both extensions are approved (D24), and neither can authenticate while the
API path requires an SSO session. The change lands in the home cluster
repository, not here.
Status: needed before PR 9.

**D27. Mackup store per context?**
Work and personal machines must not exchange app settings.
Options: one private repository per context (personal, work), with `common/`
and one directory per machine inside it; or one shared repository with
`personal/...` and `work/...`. Trade-off: a shared repository gives every machine read access
to the other context's data.
Recommendation: one repository per context. Status: open.

**D28. Windows app settings?**
Mackup does not run on Windows.
Options: declarative features only (settings files the repo owns, such as
Windows Terminal and the PowerShell profile); or the engine implements copy
mode itself from Mackup-format definitions with Windows paths.
Status: open.

**D29. Which OS does each machine run?**
Needed: the OS of each machine (studio, the Mac mini, the work PC, any Linux
hosts), the Linux distributions, and whether Windows machines use WSL.
Status: waiting on the owner.

**D31. Which approved extensions may run on work machines?**
Some approved extensions are personal: they reach the home cluster, carry
personal accounts, or want a token for private repositories.
Recommendation: the split under [Initial catalog](#initial-catalog).
Status: open.

## Rollout

Each step is a pull request with its tests and docs.

1. **Leaks.** `--no-folding` and pre-created directories, `git add -u`
   publishing with the busy-repo check, sync no longer running Mackup (its
   current configuration copies credential files; step 8 replaces it),
   LaunchAgents without `bash -l` plus a `~/.bash_profile`, listeners on
   loopback, the application firewall through `socketfilterfw`, and fixes to
   the installer guard, `stable-exec` and `tf_destroy_apply`.
2. **Agent shells.** The Claude and Codex system configs, the bash hand-off,
   real-session gating, the `cc` rename, and the single PATH application.
3. **Shell UX and startup.** Alias replacements under their own names, one set
   of git aliases, syntax highlighting loaded last, init output cached per
   binary, `compinit -C` with a daily rebuild, unused zinit annexes dropped,
   mise replacing fnm and asdf (D20), and startup re-measured.
4. **Feature engine.** `cmd/dotfiles` with manifests, resolution, generation,
   apply, teardown, stubs, per-file linking and managed copies, and the
   platform interfaces with macOS and Linux backends; the bootstrap test on
   macOS and Ubuntu runners.
5. **Migration.** Split the Brewfile, zsh modules, `config.sh` and LaunchAgents
   into features and profiles; replace stow with the engine's linking; move
   host-only values into host profiles and existing `*.local` files into the
   machine manifest and stubs.
6. **Automation and status.** The scheduler, which replaces `sync.sh sync` and
   `dotfiles-update.sh`, on launchd and systemd user timers, with per-step
   results, notifications, `doctor --automation` and the status page.
7. **Windows.** The symlink test and managed-copy fallback, Task Scheduler,
   WinGet configuration, Credential Manager, the PowerShell profile stub, the
   Claude Code and Codex configs, `install.ps1`, and the Windows CI job.
8. **Settings backup.** The Mackup-catalog copier (D30): per-app features,
   credential removal, refusals, mode manifests, staging, `defaults`
   export and import, per-context stores (D27), scanned and encrypted
   publishing (D9), per-app restore.
9. **Browsers.** The extension catalog and per-browser, per-OS provisioning,
   including Bypass Paywalls Clean.
10. **Toggl and signing.** The `toggl-focus` client and its secrets; the
    `tool.gpg-signing` checks and key import.
11. **Docs.** README restructure, generated feature catalog, removal of stale
    inventories.
