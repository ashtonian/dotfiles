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
  commands in Homebrew bash with the shared environment.

Non-goals: Linux or Windows parity (the model allows `linux` and `windows`
profiles later), MDM, and managing other users' accounts.

## Concepts

| Term | Where it lives | Tracked | Purpose |
|---|---|---|---|
| Feature | `features/<id>/feature.toml` plus payload files | yes | The unit of toggling: what to install, link, schedule and check |
| Profile | `profiles/<name>.toml` | yes | A named set of feature decisions and setting values (`base`, `dev`, `desktop`, `server`, `work`, `studio`) |
| Machine manifest | `~/.config/dotfiles/machine.toml` | no | This machine's profiles, feature overrides and setting overrides |
| Setting | declared by a feature, valued by profiles and the machine manifest | values may be either | Typed configuration a feature consumes, such as `paths.playwright_browsers` |
| Secret | macOS Keychain, seeded from 1Password | never | Referenced by name in a feature; the value never appears in a manifest, the environment or a log |
| Generated output | `~/.config/dotfiles/generated/` | no | Files `apply` renders from the enabled features: Brewfile, zsh and env fragments, git and ssh includes |
| State | `~/.local/state/dotfiles/` | no | Last run results, the status JSON and HTML page, logs |

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
"toggl.organization_id" = 1234567
"paths.playwright_browsers" = "~/Library/Caches/ms-playwright"
```

`dotfiles feature enable|disable <id>` edits this file and runs `apply` for
that feature.

## Feature manifest

```toml
# features/shell.zoxide/feature.toml
id          = "shell.zoxide"
description = "zoxide jump commands in interactive terminals"
category    = "shell"
default     = true
requires    = ["shell.core"]
conflicts   = []

[provides]
brew   = ["zoxide"]           # entries merged into the generated Brewfile
zshrc  = "zshrc.zsh"          # interactive fragment, real sessions only
env    = ""                   # POSIX fragment sourced by env.sh (every shell and agent)
bin    = []                   # scripts linked into ~/.local/bin
stow   = []                   # stow packages, linked with --no-folding
launchagents = []             # plist templates in this directory

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
script: Homebrew entries are installed, stow links point at the repo, a
LaunchAgent is loaded and its last exit was 0, a fragment is in the generated
output.

### Teardown

Disabling a feature reverses each `provides` type: `stow -D` its packages,
`launchctl bootout` and remove its agents, drop its fragments from the
generated outputs, remove its `bin` links, and run its `teardown` hook.
Homebrew packages are not uninstalled automatically, because another tool or
the user may rely on them. The status page lists installed packages no enabled
feature wants, and `dotfiles prune --brew` removes them on request.

## Generated outputs

`apply` renders everything shells and tools read at runtime, so no shell
startup parses a manifest.

| Output | Consumer | Contents |
|---|---|---|
| `generated/Brewfile` | sync, `brew bundle` | Union of enabled features' `brew`, `cask`, `mas`, `cargo`, `go` and `vscode` entries, sorted and commented with the feature that wants each |
| `generated/env.sh` | `~/.config/shell/env.sh` | Enabled `env` fragments in feature order; POSIX, builtins only |
| `generated/zshrc.zsh` | `~/.zshrc` stub | Enabled `zshrc` fragments in feature order |
| `generated/gitconfig` | `~/.config/git/config` include | Profile and feature git fragments |
| `generated/ssh_config` | `~/.ssh/config` include | Profile and feature ssh fragments |
| `generated/mackup.cfg` | Mackup | `[applications_to_sync]` from enabled `backup.mackup.*` features |

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

Stow runs with `--no-folding` for every package, and `apply` creates `~/.claude`,
`~/.local/bin`, `~/.local/share` and `~/.ssh` before it stows, so no
directory in `$HOME` becomes a symlink into the repo.

## Automation

One scheduler, `dotfiles run`, called by LaunchAgents. Each step is its own
feature, runs independently, records its result in the state directory, and
never stops the steps after it.

| Feature | Default schedule | Step |
|---|---|---|
| `sync.pull` | every 4 h, at load | Fetch and merge the repo; stop on conflict and notify |
| `sync.apply` | after every pull that changed something | `dotfiles apply` |
| `sync.brew-install` | after apply, only when `generated/Brewfile` changed or the last install failed | `brew bundle install --no-upgrade` under `umask 022` |
| `sync.publish` | after apply | `git add -u` (tracked files only), gitleaks, signed commit, check the signing key is on GitHub, push. Skips while `index.lock` exists or a changed file is younger than 30 minutes |
| `sync.aux-repos` | after publish | Opt-in list of repos under `~/.sync`; gitleaks before every push |
| `backup.mackup` | after publish | Mackup backup of enabled apps to the private backup repo |
| `update.brew` | weekly, Friday 09:00 | `brew update`, `brew upgrade`; `brew doctor` is logged, never fatal |
| `update.mas` | weekly | `mas upgrade` |
| `update.zinit` | weekly | zinit self-update, then `zinit update --all` (plugins and Oh My Zsh snippets) |
| `update.rustup`, `update.cargo` | weekly | `rustup update`; reinstall `cargo` entries whose crates.io version changed |
| `update.node` | weekly | fnm installs the configured Node line and moves the default alias |
| `update.uv-tools` | weekly | `uv tool upgrade --all` |
| `status.refresh` | after every run | Re-run checks, write the status JSON and page |

Every LaunchAgent runs the `dotfiles` binary directly with an explicit `PATH`
that includes `/opt/homebrew/bin` and `/opt/homebrew/sbin`, never through
`bash -l`. Failures post a macOS notification and show on the status page.
Oh My Zsh is used only as zinit snippets; a full `~/.oh-my-zsh` checkout is
reported by `doctor` as unused.

### Verifying it works

`dotfiles doctor --automation` and the status page report, per scheduled
feature: whether the LaunchAgent is loaded (`launchctl print
gui/<uid>/<label>`), its last start and exit status, whether the last
successful run is within twice its interval, and the step's own last result.
A stale or failing step turns the machine's status red.

## Status page

`dotfiles status` prints a table; `dotfiles status --open` writes
`~/.local/state/dotfiles/status.html` and opens it. The page is a single
static file with no external assets and no listener; `status.refresh` rewrites
it after every scheduled run. File mode is 0600.

Sections:

1. **Machine.** Hostname, macOS version, profiles, repo commit, last pull,
   apply, publish and update with their results.
2. **Features.** One row per feature: id, category, desired state with the
   source of the decision (`default`, `profile:dev`, `machine`), actual state
   (`ok`, `drift`, `missing`, `error`) with detail, and required-by links.
   Filters for category and for drift only.
3. **Automation.** Each LaunchAgent: loaded, last run, last exit, next run.
4. **Drift.** Homebrew packages no feature wants, wanted packages that are
   missing, stow conflicts, stub files that no longer load their target.
5. **Manual steps.** Pending sudo actions, logins (gh, Claude, Codex), keys not
   on GitHub, secrets not present. Secrets show presence only, never values.

## Feature catalog

Initial catalog, grouped by category. Each row is one toggle.

| Category | Features |
|---|---|
| shell | `shell.core`, `shell.prompt.dracula`, `shell.plugins.autosuggest`, `shell.plugins.syntax-highlighting`, `shell.plugins.autopair`, `shell.plugins.fzf`, `shell.plugins.you-should-use`, `shell.zoxide`, `shell.atuin`, `shell.direnv`, `shell.fnm`, `shell.modern-aliases`, `shell.safety-aliases`, `shell.greeting`, `shell.claude-launchers`, `shell.gitstead` |
| shell.omz | `shell.omz.git`, `shell.omz.git-auto-fetch`, `shell.omz.colored-man-pages`, `shell.omz.extract`, `shell.omz.docker-compose`, `shell.omz.terraform`, `shell.omz.golang`, `shell.omz.node`, `shell.omz.npm`, `shell.omz.ruby`, `shell.omz.rake`, `shell.omz.rsync`, `shell.omz.tmux`, `shell.omz.vscode`, `shell.omz.web-search`, `shell.omz.copyfile`, `shell.omz.encode64`, `shell.omz.iterm2`, `shell.omz.gpg-agent` |
| agents | `agents.claude.bash`, `agents.claude.telemetry`, `agents.claude.mcp`, `agents.codex.bash`, `agents.codex.telemetry`, `agents.opencode`, `agents.agent-monitor`, `agents.agent-mcp`, `agents.otel-agent` |
| sync and update | `sync.pull`, `sync.apply`, `sync.brew-install`, `sync.publish`, `sync.aux-repos`, `update.brew`, `update.mas`, `update.zinit`, `update.rustup`, `update.cargo`, `update.node`, `update.uv-tools`, `status.refresh` |
| packages | `brew.base`, `brew.dev`, `brew.desktop`, `brew.media`, `brew.mas`, `brew.vscode`, `brew.go-tools`, `brew.cargo-tools` |
| backup | `backup.mackup`, `backup.mackup.<app>` for each allowlisted app, including `backup.mackup.macosx` |
| macOS | `macos.defaults.finder`, `macos.defaults.dock`, `macos.defaults.keyboard`, `macos.defaults.trackpad`, `macos.defaults.screenshots`, `macos.firewall`, `macos.power.server`, `macos.remote-login`, `macos.spotlight` |
| browsers | see [Browsers](#browsers) |
| tools | `tool.toggl-focus`, `tool.go-cache-trim`, `tool.aws-profile`, `tool.gpg-signing` |
| security | `security.listeners-loopback` (opencode, agent-monitor gate bind to loopback or the Tailscale address) |

## Mackup

Mackup backs up app preferences that are not practical to declare, including
macOS's own (`macosx`: `.GlobalPreferences.plist`, symbolic hotkeys, key
bindings, Scripts, Workflows, PDF Services). Declarative system settings stay
in the `macos.defaults.*` features; Mackup carries what is left.

- **Allowlist only.** `generated/mackup.cfg` lists `[applications_to_sync]`
  from enabled `backup.mackup.<app>` features. There is no ignore list to keep
  complete.
- **Credential-bearing apps are refused in code**, even if enabled: codex,
  opencode, kubectl, npm, aws, docker, gh, ssh, gnupg, and any app whose
  definition includes an `auth`, `token`, `credentials` or `.netrc` path.
- **Stow-managed apps are refused**, so a restore never replaces a symlink with
  a copy.
- **Custom definitions** for apps Mackup lacks live in
  `features/backup.mackup/apps/*.cfg` and are linked into `~/.mackup/`.
- **Storage** is `~/.sync/mackup/<host>`. Before every push, gitleaks scans the
  repo and the publisher confirms the remote is private.
- **Restore** is manual and per app: `dotfiles mackup restore <app> --from
  <host>` quits the app, restores, and restarts `cfprefsd` so macOS picks up
  the plist.
- The temporary config is written under `$HOME`, because Mackup rejects a
  config elsewhere, and parsed with `allow_no_value`.

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

The per-browser install mechanism (Chromium external-extension files or
policies, Firefox enterprise policies) is specified in a follow-up revision of
this section.

### Initial catalog

Chrome Web Store removed every Manifest V2 listing on 2026-08-31, so several
extensions now differ between Chromium browsers and Firefox.

| Extension | Chrome / Brave | Firefox |
|---|---|---|
| uBlock Origin | uBlock Origin Lite `ddkjiahejlhfcafbddmgiahcphecmpfh` | `uBlock0@raymondhill.net` |
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
hide-files-on-github, octohint, OctoLinker and Sourcegraph (removed from the
store, archived, or covered natively by GitHub).

## Toggl

`tool.toggl-focus` provides a `toggl-focus` client for the Toggl 2.0 API
(`https://focus.toggl.com/api`, Bearer key): `toggle`, `start [description]`,
`stop`, `status`.

| Setting | Type | Default | Description |
|---|---|---|---|
| `toggl.organization_id` | int | none, required | Organization in the timer endpoint paths |
| `toggl.workspace_id` | int | from `GET /users/me/settings` | Workspace for new entries |
| `toggl.keychain_service` | string | `toggl-focus` | Keychain item holding the key |
| `toggl.onepassword_ref` | string | none | `op://` reference `apply` copies into the Keychain when the item is missing |

Toggl 2.0 allows one active key per user and creating a key revokes the
previous one, so every machine shares one key through 1Password. The client
reads the key from the Keychain per call and never exports it.

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
| `agents.claude.bash` | `/Library/Application Support/ClaudeCode/managed-settings.d/dotfiles.json` sets `CLAUDE_CODE_SHELL` to Homebrew bash. Installed once with sudo as a link to the tracked file |
| `agents.codex.bash` | `/etc/codex/config.toml` (system layer) sets `features.shell_snapshot = false` and `AGENT_SHELL`; `zshenv.zsh` hands `$ZSH_EXECUTION_STRING` to Homebrew bash when `AGENT_SHELL` is set |
| `shell.core` | Interactive-only behaviour (zoxide `cd`, aliases, `AUTO_CD`) loads only in real terminal sessions |
| `shell.core` | `env.sh` applies PATH once per process tree; nested shells keep entries the parent added |

## Implementation

A Go command, `cmd/dotfiles`, in this repository: manifest parsing, resolution,
generation, apply and teardown, the scheduler, checks and the status page. Go
gives typed manifests, concurrent checks with timeouts, `html/template` for the
page, and table-driven tests, with no runtime dependencies on the machine.

Bootstrap order: `install.sh` (bash 3.2 compatible) installs the Command Line
Tools and Homebrew, then Go, builds `dotfiles` into `~/.local/bin`, writes
`machine.toml` from `--profiles`, and runs `dotfiles apply`. `apply` rebuilds
the binary when its sources change.

Shell fragments stay POSIX sh (env) and zsh (interactive). Existing scripts
move into the features that own them.

### Testing

- Unit tests for resolution, settings, dependency and conflict errors, and
  generated output, table-driven.
- An integration test that bootstraps into an empty fake `HOME` and runs
  `apply` twice: the second run changes nothing, and nothing untracked links
  into the repo. It runs on a macOS CI runner.
- Agent shell tests with the real Claude Code and Codex command lines.
- `docs/FEATURES.md` is generated from the manifests; CI fails when it is
  stale.

## Rollout

Each step is a pull request with its tests and docs.

1. **Leaks.** `--no-folding` and pre-created directories, `git add -u`
   publishing with the busy-repo check, LaunchAgents without `bash -l`,
   listeners on loopback, and fixes to the installer guard, `stable-exec` and
   `tf_destroy_apply`.
2. **Agent shells.** The Claude and Codex system configs, the bash hand-off,
   real-session gating, and the single PATH application.
3. **Feature engine.** `cmd/dotfiles` with manifests, resolution, generation,
   apply, teardown, stubs, and the bootstrap test.
4. **Migration.** Split the Brewfile, zsh modules, `config.sh` and LaunchAgents
   into features and profiles; move existing `*.local` files into the machine
   manifest and stubs.
5. **Automation and status.** The scheduler, per-step results, notifications,
   `doctor --automation` and the status page.
6. **Mackup.** Allowlist generation, refusals, custom definitions, scanned
   publishing and per-app restore.
7. **Browsers.** The extension catalog and per-browser provisioning, including
   Bypass Paywalls Clean.
8. **Toggl and signing.** The `toggl-focus` client and its 1Password seeding;
   the `tool.gpg-signing` checks and key import.
9. **Docs.** README restructure, generated feature catalog, removal of stale
   inventories.
