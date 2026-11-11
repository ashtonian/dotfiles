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

### Copy mode only

Mackup has two families of commands:

| Commands | What they do | Used here |
|---|---|---|
| `backup`, `restore` | Copy files between `$HOME` and the storage folder | yes |
| `link install`, `link`, `link uninstall` | Move files into the storage folder and leave symlinks in `$HOME` | never |

Link mode breaks modern macOS: apps and `cfprefsd` write preferences
atomically, which replaces the symlink with a regular file, so the stored copy
silently stops updating and settings diverge or are lost. Guards:

- `backup.mackup` invokes Mackup only through `dotfiles mackup`, which passes an
  explicit argument list containing `backup` or `restore <app>` and nothing
  else.
- `shell.core` shadows `mackup` in interactive shells with a function that
  refuses any `link` subcommand; `command mackup` remains available on purpose.
- `doctor` reports an error for any symlink under `$HOME` that points into the
  Mackup storage folder, which is the signature of link mode having run.
- `~/.mackup.cfg` is a generated real file (mode 0600) pointing at the git
  store with the allowlist, so a manual `mackup backup` also uses the safe
  configuration instead of Mackup's Dropbox default.

### Git as the backing store

Mackup's engines are Dropbox, Google Drive, iCloud and `file_system`; there is
no git engine. The store is a `file_system` folder that is a git repository:

- `~/.sync/mackup`, a clone of a private repository, with one directory per
  machine (`<host>/`) so machines never overwrite each other.
- After each backup the publisher stages the machine's directory, runs
  gitleaks over the staged diff, refuses files larger than 5 MB and paths
  matching the credential patterns below, confirms the remote is private
  (`gh api repos/<owner>/<repo> --jq .private`), commits signed and pushes.
- Encrypting the store at rest is decision D9.

### What gets backed up

- **Allowlist only.** `[applications_to_sync]` is generated from enabled
  `backup.mackup.<app>` features. There is no ignore list to keep complete.
- **Credential-bearing apps are refused in code**, even if enabled: codex,
  opencode, kubectl, npm, aws, docker, gh, ssh, gnupg, and any app whose
  definition includes an `auth`, `token`, `credentials`, `.netrc` or `keychain`
  path.
- **Stow-managed apps are refused**, so a restore never replaces a symlink with
  a copy.
- **Custom definitions** for apps Mackup lacks live in
  `features/backup.mackup/apps/*.cfg` and are linked into `~/.mackup/`.

### Preference plists

Preference plists are captured with `defaults export <domain>` and restored
with `defaults import <domain>`, which go through `cfprefsd`. Copying the plist
file directly can capture stale content (the live values sit in the
`cfprefsd` cache) and a copied-in file can be overwritten by the cache. Other
files in an app definition use Mackup's copy.

### Restore

Manual and per app: `dotfiles mackup restore <app> --from <host>` quits the
app, restores, and restarts `cfprefsd`. Restoring across machines is explicit,
because machine directories differ.

The temporary configuration is written under `$HOME` (Mackup refuses configs
elsewhere) and parsed with `allow_no_value`, because Mackup's configuration
uses value-less keys.

## Secrets

A 1Password vault is the source of truth for every secret a feature needs;
the macOS login Keychain is each machine's cache.

| Step | Mechanism |
|---|---|
| Declare | A feature setting of type `secret` holds an `op://<vault>/<item>/<field>` reference, never a value |
| Sync | `dotfiles secrets sync` runs `op read` for each reference of the enabled features and writes the value to the Keychain as `dotfiles/<feature>/<field>`. It runs interactively, so 1Password's desktop-app unlock applies |
| Use | Features and scheduled jobs read only the Keychain (`security find-generic-password`), so a 3 a.m. job never waits on a 1Password prompt |
| Render | Config files that must contain a secret (for example `~/.wakatime.cfg`) are rendered from templates at apply time, mode 0600, outside the repo |
| Report | The status page shows each secret's presence and last sync time, never the value |

Item layout: one 1Password item per service, with fields `url`, `api_key` or
`token`, and `username`/`password` where the service needs them. The vault
name and the headless option are decisions D12 and D13.

Constraints:

- A secret placed in Chromium managed storage lives in a root-owned file under
  `/Library/Managed Preferences` that any local user can read. That is
  acceptable only for low-value keys scoped to one service; anything else is
  entered by hand or imported from a file.
- Firefox's user defaults domain (`~/Library/Preferences`) is readable only by
  the user.
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

Constraints on an unmanaged Mac:

- Chromium filters out every policy install whose update URL is not the Web
  Store, unless the Mac is MDM-enrolled or domain-joined. Off-store extensions
  can only be allowlisted (`installation_mode = "allowed"`) and then installed
  by hand.
- Chrome removed Manifest V2 support; uBlock Origin Lite replaces uBlock
  Origin there. Brave hosts uBlock Origin, NoScript, uMatrix and AdGuard as MV2
  extensions under its own IDs; enabling them is a toggle at
  `brave://settings/extensions/v2`, shown as a manual step.

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
- Whether policy can install Brave's hosted MV2 IDs.

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

The evaluated candidate list is in the following revision of this section.

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

## Decisions

Each entry: the question, why it matters, the options, the recommendation,
and its status. Decided entries record who decided.

### Decided

| ID | Decision | Decided by |
|---|---|---|
| D0.1 | Every capability is a per-machine toggle with fine granularity (each Oh My Zsh plugin, each extension, each scheduled step) | owner |
| D0.2 | Updates and sync run automatically on every machine; a local status page shows feature and automation health | owner |
| D7 | Mackup runs in copy mode only (`backup`, `restore`); link mode is refused | owner |
| D8 | Mackup's store is a private git repository with one directory per machine | owner |
| D0.3 | Browser extensions, including their settings and keys, are scripted; keys come from a 1Password vault | owner |
| D0.4 | Bypass Paywalls Clean is wanted (see D15 for where) | owner |
| D0.5 | Work happens on branch `plan/machine-features` | owner |

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
Codex always runs the passwd login shell and has no setting to change it.
Options: system config (`shell_snapshot = false`, `AGENT_SHELL`) plus a
`.zshenv` hand-off to Homebrew bash; or `chsh` to bash with an interactive
hand-off back to zsh. Trade-off: `chsh` changes `$SHELL` for tmux, ssh and
editors, and breaks logins if Homebrew bash disappears.
Recommendation: system config plus hand-off. Status: open.

**D4. Where do network services listen?**
opencode and the agent-monitor gate serve plain HTTP.
Options: loopback plus the Tailscale address; LAN with TLS in front.
Recommendation: loopback plus Tailscale. Status: open.

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
Options: plaintext in a private repo with gitleaks and the allowlist; or
`age` encryption with the key in 1Password, cached in the Keychain. Trade-off:
encrypted diffs are unreadable in git, and restore needs the key.
Recommendation: encrypt. Status: open.

**D10. Which apps does Mackup back up?**
Proposed: `macosx`, alt-tab, bartender, rectangle, karabiner-elements, iterm2,
istat-menus, hammerspoon. Status: open.

**D11. Plists through `defaults export`/`import`?**
Direct plist copies can be stale or overwritten by `cfprefsd`.
Recommendation: yes, as specified under Mackup. Status: proposed.

**D12. 1Password vault and item layout?**
Proposed: a vault named `dotfiles`, one item per service, fields `url`,
`api_key` or `token`, `username`, `password`. Status: open.

**D13. How do machines without a person present resolve secrets?**
Options: interactive `dotfiles secrets sync` into the Keychain, with scheduled
jobs reading only the Keychain; 1Password Connect (already deployed in the
home cluster) with a token in the Keychain; a 1Password service account, if
the plan includes them.
Recommendation: Keychain cache synced interactively; Connect for machines
that need unattended refresh. Status: open.

**D14. Accept sudo for Chrome and Brave policy changes?**
Extension policies must be mandatory, which on an unmanaged Mac means a
root-owned file; every change to the extension set needs sudo once.
Options: accept; or manage only Firefox automatically and list Chromium
extensions as manual steps. Status: open.

**D15. Where does Bypass Paywalls Clean run, and how is it pinned?**
Options: Firefox only (silent, signature-checked updates); Chrome and Brave as
well (manual install per profile). Pinning: follow the maintainer's update
manifest, or a strict mode with a verified local file and updates disabled.
Recommendation: Firefox only, following the update manifest with the signer
and ID checked. Status: open.

**D16. Ad blocking in Brave?**
Options: Shields only; Brave's hosted uBlock Origin (manual toggle);
uBlock Origin Lite. Status: open.

**D17. Toggl details.**
Needed: the organization ID (no API endpoint returns it) and whether timers
run in Toggl 2.0 (focus.toggl.com) or classic Toggl Track. The key is shared
by every machine through 1Password, because creating a new key revokes the
previous one. Status: waiting on the owner.

**D18. What does the work PC get?**
Needed: its operating system. A `work` profile disables personal features
(Mackup, Bypass Paywalls Clean, personal agents). The engine is macOS-only
today. Status: waiting on the owner.

**D19. Which machines publish?**
`sync.publish` can be off for pull-only machines.
Recommendation: publish from personal machines; pull-only on the work PC.
Status: open.

**D20. Per-directory Node versions?**
`fnm env` runs without `--use-on-cd`, so it costs startup time without
switching versions.
Options: add `--use-on-cd`; or drop the per-shell call and use the default
alias on PATH. Status: open.

**D21. The stale remote branch `update_2026`?**
It holds 33 auto-sync commits that never reached `master`.
Options: delete; merge. Status: open.

**D22. Register this machine's signing key on GitHub.**
Needs `gh auth refresh -s admin:gpg_key` by the owner, then `gh gpg-key add`.
Status: action needed.

**D23. Remove the unused `~/.oh-my-zsh` checkout?**
zinit loads Oh My Zsh plugins from its own snippet cache.
Recommendation: remove after confirming; `doctor` reports it until then.
Status: open.

**D24. Which self-hosted app extensions to add?**
See [Self-hosted app extensions](#self-hosted-app-extensions). Status: open.

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
