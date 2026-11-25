# dotfiles

Personal macOS configuration: modular Zsh, per-machine features installed by
the `dotfiles` engine, Homebrew tooling, signed Git sync, app backups, and local
coding-agent services.

See [Operations](docs/OPERATIONS.md) for configuration, signing, backup restore,
and failure recovery; [Structure](STRUCTURE.md) maps the implementation. The
[software notes](Software.md), [installed-software snapshot](software_list.md),
and [Windows files](win10/readme.md) are historical references.

## Quick Start

On a fresh Mac, run `xcode-select --install` and finish the Command Line Tools
installation before using Git to clone the repository.

```sh
git clone https://github.com/ashtonian/dotfiles.git ~/.dotfiles
cd ~/.dotfiles
less install.sh profiles/*.toml
~/.dotfiles/install.sh --profiles base,dev,desktop
```

Pick the [profiles](#profiles-and-machines) this machine runs; without
`--profiles` the installer asks. Review the profiles' package features first:
`desktop` is a broad personal app collection, including paid apps. The
installer requests sudo, offers passwordless sudo, installs Go, builds the
`dotfiles` engine, writes `~/.config/dotfiles/machine.toml`, applies the
enabled features, installs their packages, then applies again to load the
features' LaunchAgents, so the sync job (which runs at load) starts after the
packages are in. Apply problems and package failures are
warnings, so inspect the output before relying on the completion message.

The final prompt offers `config.sh`, which applies broad system/app preferences
(among them a still wallpaper and screen saver in place of the leaking aerial; see
[Aerial wallpaper memory leak](docs/OPERATIONS.md#aerial-wallpaper-memory-leak)),
installs packages again, and may restart apps or offer a reboot. Review it before
accepting; it is optional. Open a new terminal after installation.

## First login

- **Dock and Finder.** The optional macOS setup replaces the current user's Dock
  with the configured apps present on this Mac and adds existing folders to
  Finder Favorites (home, projects, Downloads, Desktop, Documents, Applications
  and Utilities). To repeat just one step, run `~/.dotfiles/bin/configure-desktop dock`
  or `~/.dotfiles/bin/configure-desktop sidebar`. In Finder > Settings > Sidebar,
  select Recents, disks and cloud locations as needed. Add any other project or
  cloud folder with Finder > File > Add to Sidebar.
- **Default apps.** With VS Code installed, common text, markup and source files
  open there. With IINA installed, MKV, MP3, MP4, MOV, M4V and FLAC files open
  in IINA. Run `~/.dotfiles/bin/configure-desktop associations` after installing
  either app later. Check an extension with `duti -x mp4`.
- **Browsers.** In Safari > Settings > Extensions, enable the installed extensions
  you use and review their website access. Follow the [passkey setup](docs/PASSKEYS.md)
  for password-manager prompts. In Brave, open Settings > Sync
  and join your existing sync chain using another device.
- **Apps and permissions.** Open Slack to sign in and MeetingBar to select
  calendars. Approve requested access for the features you use in
  System Settings > Privacy & Security. If you use the Dracula theme in Beyond Compare, import the
  [color settings](https://github.com/dracula/beyond-compare-4) in the app.
  Reduce Motion is in System Settings > Accessibility > Display.
- **GitHub and profiles.** The initial HTTPS clone works anonymously. For pushes
  and signing, follow [Git identity and signing](docs/OPERATIONS.md#git-identity-and-signing).
  If your organization supplied a configuration profile, open its `.mobileconfig`
  and review it in System Settings > General > Device Management.
  [Apple’s profile installation guide](https://support.apple.com/guide/mac-help/mh35561/mac)

## External Dependencies

The installer targets macOS and installs Xcode Command Line Tools and Homebrew
when needed. Keep the checkout at `~/.dotfiles`: the installer and service
templates assume that location. Codex/OpenCode background launchers currently
require Apple Silicon Homebrew paths under `/opt/homebrew`; other scripts also
recognize `/usr/local` Homebrew installations.

| Dependency | Required for |
| ------------ | -------------- |
| Git, GnuPG, usable signing key | Repository sync and signed commits |
| Homebrew, Go (version in `go.mod`), Python 3 | Packages, building the `dotfiles` engine, and AWS profile helpers |
| Gitleaks | Scanning dotfiles before automatic publication |
| jq (`/usr/bin/jq` on macOS 15 and later, or the `brew.base` formula) | Sync and the weekly update telling which casks need root, and the update's retries |
| GitHub CLI (gh), authenticated for each destination | Checking GitHub commit verification after a push |
| Mac App Store sign-in | The `brew.mas` feature's App Store apps |
| Zinit and downloaded plugins | Interactive shell; first use downloads plugins |
| Codex / Claude Code, authenticated separately | Their respective launchers and workers |
| Muxy 2.5 or later in `/Applications` or `~/Applications`, or at `DOTFILES_MUXY_APP` (`tool.muxy` installs its cask) | Setting the shared Muxy settings through the `muxy config` inside the app |
| OpenCode and a configured gateway | Optional coordinator; see its package README |

Claude Code, gitstead, and gateway credentials need separate setup when those
integrations are used. Configure signing and GitHub authentication as described
under [Multi-Machine Setup](#multi-machine-setup) before relying on automatic sync.

## What Gets Installed

| Component | Description |
| ----------- | ------------- |
| **Homebrew** | Package manager + the enabled package features' Brewfile entries |
| **Features** | What this machine's profiles enable, linked one file at a time; see [feature inventory](STRUCTURE.md#features) |
| **Zinit** | Zsh plugin manager with deferred loading |
| **Mackup** | Installed, but not run by sync; see [Mackup](#mackup-app-config-backup) |
| **LaunchAgents** | Owned by `dotfiles apply`: sync every 4 hours, Friday updates, daily disk pruning, hourly Go build cache trim, the hourly Muxy server list, gpg-agent, and the Codex, OpenCode, agent dashboard and telemetry services once their setup exists ([list](docs/OPERATIONS.md#launchagents)) |

## Architecture

```text
~/.dotfiles/                    # This repo - synced via git
├── features/<id>/              # One capability each: feature.toml, home/ (files linked into ~), launchagents/
│   ├── shell.env/, shell.zsh/  # Shared environment; zsh modules and entry files
│   ├── git/, ssh/              # Shared git and ssh settings
│   ├── tool.*/, agents.*/      # Tool and coding-agent configs
│   └── brew.*/                 # Package lists, split by role
├── profiles/                   # Named feature sets: base, dev, desktop, server, work, studio
├── cmd/dotfiles/, internal/    # The feature engine (Go)
├── lib_sh/                     # Shell libraries
├── bin/                        # Scripts
├── install.sh                  # Bootstrap script
├── config.sh                   # macOS preferences
└── sync.sh                     # Sync automation

~/.sync/                        # Auxiliary repos (synced separately)
├── mackup/                     # Earlier Mackup backups (git repo); sync no longer writes here
└── colorls/                    # Colorls theme
```

## Features vs Mackup: When to Use What

| Use a **feature** for: | Use **Mackup** for: |
| ------------------- | --------------------- |
| Dotfiles (`.zshrc`, `.gitconfig`) | App preferences (plists) |
| Config dirs (`~/.config/zsh/`) | App data (`~/Library/...`) |
| Files you edit directly | Files apps manage |
| Text-based configs | Binary/plist configs |
| Cross-platform files | macOS-specific files |

**Examples:**

- `~/.config/zsh/*.zsh` → feature `shell.zsh` (you edit it, want version control)
- `~/.config/git/config` → feature `git` (you edit it)
- `~/.ssh/dotfiles.conf` → feature `ssh` (you edit it)
- Terminal.app preferences → Mackup (macOS manages it)

**Rule of thumb:** If you open the file in an editor, make it part of a feature.
If an app generates or modifies it, use Mackup, or a feature's managed `copy`.
The engine never links a file under `~/Library` (current macOS apps refuse to
read or save a symlinked preference file); it installs a managed copy instead.

## Sync System

### What Gets Synced

| Location | Tool | Frequency |
| ---------- | ------ | ----------- |
| `~/.dotfiles` | git, tracked files only | Every 4 hours |
| `~/.sync/*` repos | git, tracked files only | Every 4 hours |
| This machine's features | `dotfiles apply`, right after the dotfiles merge | Every sync, once the checkout has `features/` |
| The agent telemetry collector | `bin/otel-agent converge`, right after apply: installs the pinned release and restarts the collector when it changed | Every sync, on Macs enrolled with `otel-agent enroll` |
| Missing packages | brew bundle install `--no-upgrade` | Every sync; under the LaunchAgent, casks that install as root and App Store apps wait for a terminal, named in a `WARN` line |
| Claude Code | Anthropic's native installer, when `~/.local/bin/claude` is missing; Claude Code then updates itself | Every sync, on machines with `agents.claude` |

Sync publishes edits to files the repository already tracks. A new file is
never published until you commit it yourself. A repository with a Git index
lock, or with a tracked edit newer than `SYNC_QUIET_MINUTES`, is left alone
until a later run, so half-finished work is not committed.

Once the checkout uses the feature engine (it has `features/`), each sync runs
`dotfiles apply` in the same run as the merge, so a pull that moves tracked
files never leaves links to their old paths. Before it merges an upstream that
uses the engine, sync checks that this machine can install it: the machine has
`~/.config/dotfiles/machine.toml` (otherwise it logs the profiles upstream
offers), and the upstream's own engine builds with this machine's Go and plans
that manifest (`dotfiles check`). If any of that fails, sync neither merges nor
pushes, and the checkout stays as it is. Sync then brings this machine's
overlays up to date (see [Overlays](#overlays)) before `dotfiles apply` reads
them.

### Manual Sync Commands

```sh
# Full sync (recommended)
~/.dotfiles/sync.sh sync

# Individual operations
~/.dotfiles/sync.sh dotfiles  # Sync only dotfiles repo
~/.dotfiles/sync.sh overlays  # Sync only the overlays machine.toml lists
~/.dotfiles/sync.sh repos     # Sync only ~/.sync/ repos
~/.dotfiles/sync.sh brewfile  # Install the enabled features' missing packages
~/.dotfiles/sync.sh mise      # Install the tools mise's shared defaults name (the pinned Go, Node LTS)
~/.dotfiles/sync.sh build     # Rebuild ~/.local/bin/dotfiles if its sources changed
~/.dotfiles/sync.sh apply     # Build if needed, then dotfiles apply
~/.dotfiles/sync.sh otel-agent  # Install the pinned telemetry collector; restart it if it changed
~/.dotfiles/sync.sh claude-code  # Install Claude Code natively if agents.claude is on and ~/.local/bin/claude is missing
~/.dotfiles/sync.sh all       # Same as sync
~/.dotfiles/sync.sh check     # Lock availability without syncing
```

| Variable | Type | Default | Description |
| -------- | ---- | ------- | ----------- |
| `DOTFILES_DIR` | path | `~/.dotfiles` | Repository sync and the engine operate on |
| `SYNC_DIR` | path | `~/.sync` | Directory whose Git repositories sync also publishes |
| `SYNC_QUIET_MINUTES` | minutes | `30` | A tracked edit newer than this makes sync skip the repository for this run |
| `DOTFILES_BIN` | path | `~/.local/bin/dotfiles` | The engine binary sync builds and runs |
| `DOTFILES_OVERLAY_DIR` | path | `~/.dotfiles-overlays` | Directory holding one overlay checkout per context, each named for its overlay; the engine reads it, and sync syncs the ones `machine.toml` lists |

Full sync commits and pushes eligible changes. A busy lock or unavailable network
is logged and skipped successfully; other operation failures return nonzero.
Check `logs/sync.log` for the outcome. Runtime overrides are listed in the
[configuration table](docs/OPERATIONS.md#configuration).

### LaunchAgents

Each LaunchAgent is a template in the feature that declares it
(`features/<id>/launchagents/`), and `dotfiles apply`, which every sync runs,
installs, loads, reloads and removes them as the profiles say. An agent whose
program or setup is missing waits for it: the Codex service for the codex cask,
OpenCode for its local setup, the dashboard for `agent-monitor install`, the
telemetry collector for `otel-agent enroll`. The full list, the one-time macOS
prompts, and what apply does when a template changes are in
[OPERATIONS.md](docs/OPERATIONS.md#launchagents).

```sh
dotfiles doctor                                    # pending changes, and agents still waiting
launchctl print "gui/$(id -u)/com.dotfiles.sync"   # one agent's state and last exit
launchctl kickstart "gui/$(id -u)/com.dotfiles.sync"   # run a scheduled job now
```

To turn an agent off on one Mac, disable its feature in
`~/.config/dotfiles/machine.toml` (`[features] disable = ["dotfiles.update"]`)
and run `dotfiles apply`.

The opt-in [Gas City fleet guide](features/agents.gascity/README.md) covers shared issue queues, fixed checkouts, cross-repo dependencies, Claude implementation and Astra review across Macs.

## Feature engine

`cmd/dotfiles` is the engine the [machine features design](docs/MACHINE-FEATURES.md)
describes: every capability is a feature under `features/<id>/`, profiles under
`profiles/` turn groups of them on, and the untracked
`~/.config/dotfiles/machine.toml` lists this machine's profiles and overrides.
Sync builds the binary into `~/.local/bin/dotfiles` and runs `dotfiles apply`
after every merge.

```sh
dotfiles init --profiles base,dev,desktop   # write this machine's manifest (once)
dotfiles init --overlays personal --profiles base,dev,desktop,personal --force   # the same, in an overlay's context
dotfiles status            # each checkout's commit, then every feature, enabled or not, and which layer decided
dotfiles apply --dry-run   # what apply would change
dotfiles apply             # converge this machine
dotfiles doctor            # drift and conflicts, changing nothing; exit 1 if any
dotfiles check             # validate the manifests and plan this machine; reads nothing in $HOME
dotfiles overlays          # the checkout directory of each overlay machine.toml lists
dotfiles adopt ~/.config/htop/htoprc   # make a managed copy's local edits the repository's version
dotfiles adopt muxy:appearance.dark_theme   # the same for an app setting changed in the app
dotfiles forget muxy:appearance.dark_theme  # drop the earlier value of a setting whose app is gone for good
```

`apply` links each tracked file into `$HOME` on its own (never a directory),
writes managed copies for files a tool rewrites (gh, htop and Karabiner
settings, and everything under `~/Library` on macOS), renders the generated
outputs in `~/.config/dotfiles/generated/` (the Brewfile, and the env, zsh, git
and ssh fragments), creates one-line stubs for entry points installers
write to, and installs and loads the features' LaunchAgents on macOS. It records what it installed in `~/.local/state/dotfiles/applied.json`,
so disabling a feature removes exactly what it added. It never overwrites a
file it did not create: a file in the way or a locally edited managed copy is
reported and left alone. `dotfiles adopt <path>` copies a managed copy's local
edits into its tracked file, which sync then publishes like any tracked edit. A
second run with nothing changed does nothing.

App settings that share a file with one machine's own state, such as Muxy's
theme and Claude Code's `theme` in `~/.claude/settings.json`, are owned key by
key: a feature's prefs file lists them, and `apply` sets each one through the
app (`muxy config set` inside `Muxy.app`; an in-place edit of
`settings.json`), leaving every other key to the machine. A setting changed in
the app after apply set it is reported, never overwritten, and
`dotfiles adopt <store>:<key>` keeps it; a `[prefs]` table in a profile or
`machine.toml` gives one machine its own value (see
[Profiles and machines](#profiles-and-machines)); disabling the feature puts
back the value it replaced. See
[App settings](docs/MACHINE-FEATURES.md#app-settings). `--app-timeout`
(default `15s`) bounds each call to an app's settings tool.
Without `machine.toml` it refuses to run, since no profile would apply and it
would remove everything the profiles install.

Old stow links are converted on the first apply: a directory stow had folded
into one link becomes a real directory, the untracked files tools wrote through
that link (such as gh's `hosts.yml`) move to their place in `$HOME`, and links
to paths no feature installs any more are removed. An untracked file still in
the retired `stow/` tree that `$HOME` links to moves home too; one nothing
links to is reported, never deleted, except Finder's `.DS_Store`, which is
removed.

### Profiles and machines

| Profile | Enables |
| ------- | ------- |
| `base` | Shared environment and zsh, git, ssh, gh/atuin/htop/colorls/mise settings, command-line packages, Spotlight exclusions (macOS) |
| `dev` | Development apps, VS Code extensions, Go tools, Claude Code and MCP configs, Claude Code's Dracula theme |
| `desktop` | Desktop and App Store apps for any desk (`brew.apps`, `brew.mas`) and personal ones (`brew.desktop`: games, media, messaging, VPN; `brew.mas.personal`), the RescueTime and WakaTime trackers, OpenCode and the agent telemetry collector (both reach the home cluster), the Mackup config, passkey prompts turned off (`browser.passkeys-off`), the Karabiner mouse mapping (`tool.karabiner`), Muxy with its shared settings (Dracula, FiraCode Nerd Font at 14), its command line tool and the other Macs as its remote servers |
| `server` | Nothing yet; power, remote login and firewall settings arrive with `config.sh`'s migration |
| `work` | Desktop and App Store apps for any desk (`brew.apps`, `brew.mas`, which needs an App Store sign-in); personal features come only from `desktop`, which the work machine does not use |
| `studio` | Host facts only: Playwright's browsers and the agent dashboard's data on the E2TB volume |

| Machine | Profiles | Overlays |
| ------- | -------- | -------- |
| studio | `base, dev, desktop, studio` | `personal` and the clients worked from it |
| Mac mini | `base, dev, desktop, server` | `personal` and the clients worked from it |
| A client's machine | `base, dev, work` | that client's only |

Override one feature, setting or app setting for one machine in `machine.toml`:

```toml
profiles = ["base", "dev", "desktop", "server"]

[features]
disable = ["tool.colorls"]

[settings]
"paths.playwright_browsers" = "~/Library/Caches/ms-playwright"

[prefs]
"muxy:terminal.font_size" = 13.0   # instead of tool.muxy's shared 14.0
```

| Table | Keys | Overrides | Checked |
| --- | --- | --- | --- |
| `[features]` | `enable`, `disable`: feature ids | the feature's `default`, then each profile in order | an unknown id is an error |
| `[settings]` | setting names, such as `"paths.playwright_browsers"` | the declaring feature's default, then each profile's `[settings]` in order | an unknown name or a value of the wrong type is an error |
| `[prefs]` | app settings, `<store>:<key>` as `dotfiles adopt` names them, such as `"muxy:terminal.font_size"` | the owning feature's prefs file, then each profile's `[prefs]` in order | a key no enabled feature owns, or a value the store cannot take, is a plan error |

A profile's `[prefs]` table works the same way for every machine that lists
the profile. Changing or removing an override takes effect on the next apply
(removing one returns the setting to the shared value); disabling the feature
still puts back the value from before dotfiles. `dotfiles check`, `doctor` and
`status` show each app setting's value and where it comes from; see
[Per-machine overrides](docs/MACHINE-FEATURES.md#per-machine-overrides).

### Overlays

This repository is public, so it names no client, private repository or
internal host. Those facts live in overlays: one private repository per
context (personal work, and each client), cloned at
`~/.dotfiles-overlays/<context>` (`DOTFILES_OVERLAY_DIR`). An overlay has this
repository's layout (`features/`, `profiles/`), and the engine loads the ones
`machine.toml` lists after this repository's:

```toml
overlays = ["personal"]
profiles = ["base", "dev", "desktop", "studio", "personal"]
```

- Every feature ID and profile name in an overlay is the overlay's name or
  starts with it and a dot (`personal.claude`, `personal.studio`), and this
  repository's never do. So an ID says which context it comes from, and no
  overlay can replace a feature here or another overlay's.
- An overlay feature with `default = true` is on wherever its overlay is
  listed. An overlay profile can set the settings this repository's features
  declare, which is how a private value (a cache list, a path) reaches a
  public feature.
- A machine lists only the contexts it works in. A client's machine lists that
  client's overlay and nothing else, so it never holds personal facts or
  another client's.
- A listed overlay that is not cloned stops `apply` (exit 2) instead of
  removing what its features installed. Sync pulls and publishes each listed
  overlay, to its own remote, before `apply` reads it.
- Taking an overlay off the list removes what its features installed on the
  next `apply`.
- An overlay's `denylist.txt` lists the names it keeps private, one per line
  (`#` comments). Before sync publishes this repository it fails if a tracked
  line names one, as a whole word in any case, and so does
  `bin/check-private-names` (run it before pushing a branch). The lists stay
  in the overlays, so public CI never sees them.

| Exit status | Meaning |
| ----------- | ------- |
| 0 | Done; for `doctor`, nothing to fix |
| 1 | Problems left for you (a file in the way, an edited copy, an app setting changed in the app, an app that is not installed, a missing setting), or for `doctor`, pending changes |
| 2 | The manifests are invalid or contradict each other (unknown key or feature, a requirement disabled on purpose, a conflict), or a listed overlay is not cloned |
| 64 | Usage |
| 70 | An I/O failure |

## Shell Configuration

### Structure

```text
~/.config/zsh/
├── 00-init.zsh        # Zinit bootstrap
├── 20-history.zsh     # History settings
├── 30-plugins.zsh     # Zinit plugins (turbo mode)
├── 40-keybindings.zsh # Key bindings + Atuin
├── 50-aliases.zsh     # Aliases
├── 60-functions.zsh   # Functions & external sources
└── 70-greeting.zsh    # Optional terminal greeting
```

PATH and the core environment (Homebrew, Go, language toolchains, editor,
pager, locale) are defined once in `~/.config/shell/env.sh` (feature
`shell.env`), followed by the enabled features' generated `env.sh`.
`~/.zshenv` sources it for every zsh, `~/.bash_profile` for login bash and
`~/.bashrc` for interactive bash, which covers
Claude Code's Bash tool. A nested shell keeps the PATH its parent built.

`~/.zshenv`, `~/.zprofile`, `~/.zshrc` and `~/.zlogin` are one-line local stubs
that source `zshenv.zsh`, `zprofile.zsh`, `zshrc.zsh` and `zlogin.zsh` in
`~/.config/zsh/`, so an installer that appends to `~/.zshrc` changes only this
machine. Local zsh modules go beside the shared ones with a number, such as
`~/.config/zsh/80-local.zsh`; `zshrc.zsh` loads only numbered modules.
`~/.gitconfig` is the machine's own file (an existing one is kept): shared
settings are in `~/.config/git/config`, which includes the generated fragments
and then `~/.gitconfig.local`, and `git config --global` writes to
`~/.gitconfig`, which git reads last. `~/.ssh/config` starts with
`Include dotfiles.conf`, which reads `~/.ssh/config.local` first and applies the
shared defaults last (`Match final`), so hosts installers append to
`~/.ssh/config` keep their own settings.

Real sessions differ from tool shells: `ls`, `du`, `ping` and `top` stay the
real commands everywhere (their replacements take different flags); eza
listings are `ll`, `la` and `lt`, ncdu is `dux`, and `reload` starts a fresh
login shell (`exec "$SHELL" -l`). The git aliases (`gs`, `gc` and the rest) are applied again
after the OMZ git plugin loads, so `gc` stays `git commit`.

### Language versions (mise)

[mise](https://mise.jdx.dev) installs Go, Node, Python and other tools and
selects their versions per directory, from each project's own files:
`.go-version`, `.nvmrc`/`.node-version`/`package.json`, `.python-version`, plus
`mise.toml` and `.tool-versions`. Shared defaults are in
`~/.config/mise/conf.d/dotfiles.toml` (feature `tool.mise`), which mise never
writes; `mise use -g` writes the machine-local `~/.config/mise/config.toml`.

```sh
mise install            # install the versions the current directory asks for
mise ls                 # what is selected here, and from which file
mise trust              # let a project's mise.toml set env vars and run tasks
```

- Real sessions activate mise at each prompt. Agents, LaunchAgents and GUI apps
  get mise's shims from `env.sh`, so they run the same versions.
- **Go** is one pinned release (`go = "1.27.4"` in the shared defaults, the
  official build CI's setup-go installs) for every machine, shell, agent and
  checkout. mise does not read `go.mod` or `go.work`: their `go` and
  `toolchain` lines are the oldest Go a module accepts, and with
  `GOTOOLCHAIN=auto` (setting `go.toolchain`, exported by `env.sh`) the `go`
  command runs the pinned release unless a module needs a newer one, which it
  then downloads once through `GOPROXY`, checked against `GOSUMDB`. A project
  that wants an exact Go commits `.go-version` or a `mise.toml`. `go install`
  writes to `~/go/bin` (`go.set_gobin = false`), so its commands outlive a
  pin bump.
- The weekly update on the canary machine (setting `mise.canary`, `studio`)
  moves the Go pin to the newest patch of its minor and publishes it; each
  machine's next sync installs it. A new minor is a deliberate edit to the pin.
- Node outside any project is the LTS release. Sync installs whatever the
  shared defaults name and the machine lacks.
- A project's `mise.toml` takes effect only after `mise trust`; set
  `trusted_config_paths` in `~/.config/mise/config.toml` to trust your own
  project roots, never everything.

### Local Overrides

Create `~/.zshrc.local` for machine-specific config (not synced):

```sh
# ~/.zshrc.local
export EDITOR=vim
alias work="cd ~/work/projects"
# Optional greeting (disabled by default for faster startup)
SHOW_COWSAY=true
```

## AI CLI Helpers

Interactive launchers from the generated zshrc fragment of the dev features
`agents.claude` (`features/agents.claude/zshrc.zsh`) and `agents.codex`
(`features/agents.codex/zshrc.zsh`, macOS only). `~/.zshrc.local` loads after
them, so a local definition replaces one.

Claude Code itself comes from Anthropic's native installer, never Homebrew,
whose cask trails the releases. On a machine with `agents.claude`, sync runs
the installer when `~/.local/bin/claude` is missing (it checks the binary's
SHA-256 against the release manifest), and from then on Claude Code's own
auto-updater keeps it current; `claude doctor` shows the install method, the
update channel and the last update. A `claude` in `/opt/homebrew/bin` is a
leftover cask: `brew uninstall --cask claude-code`.

| Command | Model | Effort | Behavior |
| --------- | ------- | -------- | ---------- |
| `gptmore [args...]` | GPT-6.1 Sol | `xhigh` | Connects to the local remote-control server in the current directory (`-C "$PWD"`; without it the session runs in the server's `~`) and skips Codex approvals and sandboxing. Leaves out the ChatGPT connectors (`--disable apps`) unless the launch sets `CODEX_CONNECTORS=1`. The server gives the session the delegation policy |
| `gptmax [args...]` | GPT-6 Astra | `max` | Same, with Astra |
| `claudemore [args...]` | `opus[1m]` | `xhigh` | Names the session, enables Remote Control, and skips Claude permission checks. Leaves out the claude.ai connectors (`ENABLE_CLAUDEAI_MCP_SERVERS=false`) unless the launch sets `CLAUDE_CONNECTORS=1`, and appends the delegation policy (`--append-system-prompt-file ~/.config/agent-delegation/policy.md`). Started on a drive under `/Volumes`, the session keeps its scratch and its commands' caches on that drive (`CLAUDE_CODE_TMPDIR`, `DOTFILES_CACHE_HOME`; docs/OPERATIONS.md) |
| `claudemax [args...]` | `fable[1m]` | `xhigh` | Same behavior with the Fable alias |

The model and effort defaults are listed above. The launchers forward additional
arguments. Both GPT launchers require the local Codex app
server to be running on its dedicated Unix socket: the
`com.ashtonian.codex-remote-control` LaunchAgent (see LaunchAgents). Claude's model aliases track the
provider's model mapping; the Codex model strings are pinned in these wrappers.
Availability and supported effort levels depend on the authenticated provider.
See the [official OpenAI CLI reference](https://learn.chatgpt.com/docs/cli/reference)
for Codex flags. Use the underlying CLIs directly when bypassing permissions is
not appropriate.

Every session these launchers start bypasses permissions, so connector content
(mail, calendar, Drive, Docs, and for ChatGPT also GitHub) stays out of it by
default. `CLAUDE_CONNECTORS=1 claudemore` brings the claude.ai connectors back
for that one launch, and `CODEX_CONNECTORS=1 gptmore` the ChatGPT apps. Codex
receives `--disable apps` from an attached client as a thread setting, so it
holds for that session only. The server and launchers use
`$CODEX_HOME/dotfiles-app-server.sock` (`CODEX_HOME` defaults to `~/.codex`),
with the endpoint defined by `bin/codex-app-server --print-endpoint`.
Codex reserves its default `unix://` socket for its own managed daemon and
requires explicit feature flags to match that daemon's shared settings.

### Agent rules

Claude Code and Codex follow one set of rules, kept once:

| Source | Owner | Claude Code reads it as | Codex reads it in `~/.codex/AGENTS.md` |
| --- | --- | --- | --- |
| `features/agents.rules/home/.claude/CLAUDE.md`, every agent's rules | `agents.rules` | `~/.claude/CLAUDE.md` | First |
| `features/agents.codex/codex-rules.md`, Codex's own | `agents.codex` | Not at all | Second |
| An overlay's rules file, such as `~/.claude/rules/personal.md` | The overlay's `<context>.claude` | `~/.claude/rules/<context>.md` | After them, in feature order |
| `features/agents.claude/home/.claude/rules/claude-code.md`, Claude Code's own | `agents.claude` | `~/.claude/rules/claude-code.md` | Not at all |

A feature hands its Markdown to Codex with `agent_rules`. `dotfiles apply`
joins the enabled ones in feature order into `generated/AGENTS.md`, each after
an HTML comment naming its feature. `agents.codex` links `~/.codex/AGENTS.md`
there (`link_generated`), because Codex reads that one fixed file and has no
include. So an edit belongs in a source file. The next apply replaces anything
written into `~/.codex/AGENTS.md`, and a hand-written file at that path stays
in place, reported as in the way, until it is removed.

Codex 0.172 includes the whole global file in every session: a 49 KB
`AGENTS.md` came through `codex debug prompt-input` intact. Its
`project_doc_max_bytes` limit applies to a repository's own AGENTS.md files.
On a Mac with the personal and client overlays the rendered file is 43 KB.

### Subagents and the delegation policy

`agents.delegation`, which `agents.claude` and `agents.codex` require, gives
both harnesses the same two read-only subagents and the policy for using them:

| Subagent | Claude Code (`~/.claude/agents/`) | Codex role (`~/.codex/agents/`) | Role |
| -------- | --------------------------------- | ------------------------------- | ---- |
| `scout` | Haiku, `medium`; Read, Glob, Grep, Bash | GPT-6 Luna, `medium` | Finds and quotes files, symbols, call sites, config keys and log lines; never judges |
| `reader` | Sonnet, `xhigh`; Read, Glob, Grep, Bash, WebFetch | GPT-6.2 Sol, `xhigh` | Answers one bounded question about named files or output, tagging each claim VERIFIED (cited) or INFERRED |

Claude Code loads user subagents in every session, a bare `claude` and
`claude -p` included; Codex offers user roles to `spawn_agent` as its
`agent_type` in every session. Each pair shares its description and
instructions word for word, and the suite checks that they still do. A Codex
role can only take capabilities away, not narrow the tool list, so the roles
turn off apps and plugins and rely on their instructions to stay read-only;
the Claude Code subagents' tool lists include Bash, so the same holds there.

`~/.config/agent-delegation/policy.md` says what the session hands them and what
it keeps on its own model, and that their reports are leads to check, not facts.
`claudemore` and `claudemax` append it to the session's system prompt.
A Codex client attached with `--remote` cannot send instructions, so the
app-server behind `gptmore` and `gptmax` (`bin/codex-app-server`) gives the
policy to every session it starts, as developer instructions. It reads the file
at start: restart the service after changing it (OPERATIONS: Codex service).
Subagents never see the policy, and a bare `claude` or `codex` runs without it.
A Claude Code session records its system prompt on its first request, so a
resumed conversation picks up a changed policy only after it compacts.

`claude-subagent-economics [--days N] [--projects DIR]` (default 30 days,
`~/.claude/projects`) prices the recent `scout`, `reader`, Explore and
general-purpose runs from the Claude Code transcripts at Opus rates, and the
break-even size of the main session re-reading what a cheaper subagent cited.
Codex has no counterpart: its transcripts record usage in another shape, and
nothing reads them yet.

`~/.claude/statusline-p10k.sh`, the status line `settings.json` runs, is linked
by `agents.claude`, which also owns the `settings.json` keys every machine
shares ([features/agents.claude/claude.toml](features/agents.claude/claude.toml)):

| Key | Value | Why |
| --- | --- | --- |
| `model` | `opus` | What a plain `claude` starts with; the launchers pass their own |
| `effortLevel` | `xhigh` | The launchers' effort, for a plain `claude` too |
| `autoCompactEnabled`, `autoCompactWindow` | `true`, `400000` | Compact long before the 1M window fills |
| `statusLine` | `bash ~/.claude/statusline-p10k.sh` | The linked status line |
| `skipDangerousModePermissionPrompt` | `true` | The launchers start in bypass mode |
| `agentPushNotifEnabled` | `true` | Push notifications for agent sessions |

Hooks, `env`, permissions, plugins and MCP approvals stay each machine's own:
they name what that machine runs (the agent dashboard, iTerm, telemetry). A
`[prefs]` entry in `machine.toml` gives one machine its own value, as
`"claude:effortLevel" = "high"`.

### Repository guard

`agents.repo-guard` (dev profile) installs repo-guard, one `PreToolUse` hook
script (`~/.local/bin/repo-guard`) that Claude Code and Codex both run before
every shell command. Both name their shell tool `Bash` for hooks, send the same
input and read the same deny decision. The hook denies a commit, a tag, a push
or a GitHub write (`gh pr|issue|release|repo|... <verb>` other than view, list
and the other read verbs; `gh api` with a non-GET method, fields, `--input`, or
a GraphQL mutation) when the command names a protected repository or runs in,
or points git at, a clone of one. Reading, cloning and local builds pass, and so
does anything aimed at other repositories.

| Harness | Registration | When the hook fails |
| ------- | ------------ | ------------------- |
| Claude Code | The plugin `~/.claude/skills/repo-guard/`, linked by the feature: a plugin folder there loads in every session as `repo-guard@skills-dir`, with no install step | `onFailure: "block"` blocks the call on a crash or after 10 s |
| Codex | `[[hooks.PreToolUse]]` in `/etc/codex/config.toml`, written by `bin/dotfiles-agents install` (see [Agent shells](#agent-shells)). Hooks in the system layer are managed: they run without a trust prompt, and a user config cannot turn them off. Without the feature the hook passes | Codex lets a failed hook through, so the registered command turns any exit other than 0 or 2 into a block. A hook still running after 10 s is killed and the call goes ahead |

This repository lists no protected repository. Each context's overlay links its
own list to `~/.config/repo-guard/protected.d/<context>.txt` (see
[Overlays](#overlays)): one `owner/name` per line, `#` comments and blank
lines allowed, names compared in any case. The hook reads every `*.txt` there;
with none, nothing is protected. `REPO_GUARD_LIST` names one file to read
instead, for one session or a test; set to an empty value it protects nothing.

| Path or setting | Effect |
| --------------- | ------ |
| `~/.config/repo-guard/protected.d/*.txt` | The protected repositories, one list per overlay |
| `REPO_GUARD_LIST` | One file read instead of the directory; empty protects nothing |
| `features/agents.repo-guard/guard_test.sh` | The hook's cases against throwaway clones, each sent as Claude Code and as Codex shape their input (`GUARD_BASH=/bin/bash` runs them under bash 3.2) |

The hook blocks the call with exit 2 if it cannot read a list, finds a line
that is not `owner/name`, or has no `jq`. It errs toward denying: it reads the
command's text, not its shell syntax, so `echo git push` in a protected clone
is denied too. It sees the shell tool only. A GitHub MCP server with write
tools would bypass it, so keep that server read-only; the ChatGPT GitHub app
would too, which is one reason `gptmore` and `gptmax` leave the apps out. To
make a change you were given permission for, run the command yourself, or
start that Claude Code session with `REPO_GUARD_LIST=`. A Codex session
attached to the app-server takes its hook environment from the server, so
there the change is yours to run.

The short launchers in `lib_sh/claude.sh` (`c`, `ccont` for `claude --continue`,
`cr`, `cf`, `co` and the rest) exist only in real terminal sessions, as do
zoxide's `cd`, its `z`/`j` aliases and `AUTO_CD`. Agent and tool shells keep the
plain commands, so a model-written `cd build` cannot jump to another tree and
`cc` stays the C compiler.

### Agent shells

Claude Code and Codex run model-written commands in bash, not zsh. Install the
system configs once per machine (they need sudo):

```sh
~/.dotfiles/bin/dotfiles-agents install   # write both files
~/.dotfiles/bin/dotfiles-agents check     # compare them with the repository; exit 1 on drift
```

| File | Effect |
| ---- | ------ |
| `/Library/Application Support/ClaudeCode/managed-settings.d/50-dotfiles.json` (`/etc/claude-code/...` on Linux) | Sets `CLAUDE_CODE_SHELL` to Homebrew bash, and `"attribution": false`, which hides Claude Code's commit trailer, PR line and session link (Claude Code 2.1.281 or later). Managed settings outrank user and project settings, a CLAUDE.md rule cannot override their attribution, and `env` merges per variable |
| `/etc/codex/config.toml` | Codex's system config layer: turns shell snapshots off and sets `AGENT_SHELL` in every command shell. Codex always starts the passwd login shell (`zsh -lc <command>`), and `~/.zshenv` hands a marked command to bash. It also registers repo-guard as a managed `PreToolUse` hook (see [Repository guard](#repository-guard)) |

`dotfiles-agents` never overwrites a file it did not write (exit 73), and
`~/.codex/config.toml` can still override any Codex key for one user (hooks
excepted: a managed hook stays on).

Codex has no local setting for commit and PR attribution (0.171). The signed-in
ChatGPT account's commit attribution setting decides it: when on, every session
is told to end commits with `Co-authored-by: Codex <noreply@openai.com>`, add a
"Generated with Codex" line to pull requests, and ignore earlier instructions
that disable this, so an AGENTS.md rule cannot outrank it; when off, sessions
are told not to add attribution. Keep that account setting off. A session's
rollout file under `~/.codex/sessions/` records the state it ran with as
`"git_attribution":false` or `true`.

### Agent workspaces and fleets (gitstead)

The `claudefleet` function forwards its arguments to `gitstead fleet open fleet`,
and `gitstead cd <query>` jumps to a repository. The `brew.dev-apps` feature
installs [gitstead](https://github.com/ashtonian/gitstead); fleet definitions,
agent profiles, and workspace paths live in the machine-local
`~/.config/gitstead/config.yaml` and are not supplied by this repository. Fleet
sessions run `claudemore` or `claudemax`, which leave the claude.ai connectors
out of every launch, so gitstead's agent profiles need no
`ENABLE_CLAUDEAI_MCP_SERVERS` of their own.

### Coordinator (OpenCode)

An always-on OpenCode server whose default agent runs on a self-hosted model and
delegates work to Claude Code and GPT Astra as background jobs, reporting back as
each finishes. Drive it from the terminal and a browser at once:

| Command | Description |
| --------- | ------------- |
| `oc` | Terminal UI on the running server, in the current directory |
| `ocweb` | Open the web UI (password copied to the clipboard; user `opencode`) |

Setup, configuration, the `delegate_*` tools, operations and security:
[features/agents.opencode/README.md](features/agents.opencode/README.md).

### Agent dashboard

A loopback web dashboard at <http://127.0.0.1:4820> for every Claude Code and
Codex session on this Mac: live cards, Kanban, tool timelines, transcripts, token
and cost analytics, and a Run page that starts sessions with the CLIs' own logins.
`~/.dotfiles/bin/agent-monitor install` sets it up, and `agent-monitor status`
checks it. Setup, configuration, operations and security:
[docs/AGENT-MONITOR.md](docs/AGENT-MONITOR.md).

### Agent MCP servers

Claude Code, Codex and OpenCode get a global read-only GitHub MCP, including Actions jobs and logs.
Repositories list additional MCP servers in committed `.mcp.json` (Claude
Code) and `.codex/config.toml` (Codex) files; every entry runs
`agent-mcp <server>`, which pins each server's binary and flags in one place.
Servers load only where they are used: Serena in the Go repositories, a code
graph in the application repositories, Kubernetes, Terraform and Grafana in the
infrastructure repositories. See
[docs/AGENT-MCP.md](docs/AGENT-MCP.md).

### Agent telemetry

Claude Code, Codex and OpenCode export OpenTelemetry metrics and events to a
local collector (`bin/otel-agent`, LaunchAgent `com.ashtonian.otel-agent`). It
deletes identities and tool content and forwards the rest to the cluster's OTLP
gateway, where the Coding Agents dashboard shows tokens, cost, tools and latency
per harness and repository. Setup and operations:
[docs/AGENT-TELEMETRY.md](docs/AGENT-TELEMETRY.md).

AI-assisted development workflows from `lib_sh/claude.sh`:

| Command | Description |
| --------- | ------------- |
| `cworktree <branch>` | Create worktree + Claude session |
| `cresume` | Resume Claude session |
| `ccontinue` | Continue last session |
| `copus` | Use Claude Opus model |
| `cdoc` | Generate `CLAUDE.md` |
| `creview` | Review branch changes |
| `csecurity` | Security audit |

## Spotlight exclusions

Feature `macos.spotlight` keeps Spotlight out of folders that hold no
documents: app caches and databases under `~/Library/Application Support`,
`~/Library/Logs`, the pnpm store, Go toolchains, `/usr/local` and the Command
Line Tools. `apply` does not run it; after installing the feature, and after
editing the list, run:

```sh
spotlight-exclusions apply    # add the folders in ~/.config/spotlight/exclusions
spotlight-exclusions check    # exit 1 if a folder on the list is not excluded
```

The list, the commands and troubleshooting:
[docs/SPOTLIGHT.md](docs/SPOTLIGHT.md).

## Passkeys off

Feature `browser.passkeys-off` (desktop profile) stops websites, browsers and 1Password from
offering, creating or auto-filling passkeys; passwords and security keys keep working. It
installs the Passkeys Off extension for Brave and Chrome and the `passkeys-off` command. Once
per Mac:

```sh
passkeys-off apply    # Firefox prefs in every profile's user.js; restart Firefox
passkeys-off check    # exit 1 until each browser profile has the extension loaded
```

Loading the extension, the 1Password and Passwords app settings, and troubleshooting:
[docs/PASSKEYS.md](docs/PASSKEYS.md).

## Mouse buttons

Feature `tool.karabiner` (desktop profile) installs Karabiner-Elements with a managed
`~/.config/karabiner/karabiner.json`: the G502 X PLUS's G5 button opens Mission Control,
which G HUB used to do, and every other key and button behaves as it does without
Karabiner. Once per Mac, install it from a terminal (its `.pkg` needs a password), then
approve the driver and Input Monitoring that Karabiner asks for:

```sh
brew install --cask karabiner-elements
```

Checking the button with Karabiner-EventViewer, and troubleshooting:
[docs/KARABINER.md](docs/KARABINER.md).

## Muxy remote servers

Feature `tool.muxy` (desktop profile) makes each Mac's Muxy list the other Macs of
every context it works in as remote servers. Each context's overlay names its Macs:
`Host` aliases in an `ssh_config` fragment, and a list linked to
`~/.config/muxy/servers.d/<context>.toml`. `muxy-reconcile`, run by the LaunchAgent
`com.ashtonian.muxy-reconcile` at load, when a list is added or removed, when apply
rewrites its generated files, and hourly,
rewrites only the `[[servers]]` tables of Muxy's `settings.toml`: it leaves out the Mac
it runs on, keeps the ids of entries that already reach the same Mac (Muxy ties tabs to
them), keeps entries added by hand, and writes only what Muxy's own parser accepts. Until
a Mac's `machine.toml` sets `muxy.reconcile` to `apply`, it only logs what it would change
(the Mac mini moves first; [Rollout](docs/MUXY.md#rollout)).
`~/.local/bin/muxy` runs the app's own `muxy`, which is also what Muxy on the other Macs
starts over SSH. While Muxy's own server copy `~/.local/bin/.muxy` exists, apply leaves
`~/.local/bin/muxy` alone (a running server may execute from it); the copy is retired by
hand at a planned server restart only. Neither apply nor `muxy-reconcile` stops, restarts
or upgrades a Muxy server. One Mac leaves out, adds or renames servers, or changes how one
is reached, in files only it has (`muxy.exclude_servers` in `machine.toml`, a local list,
`~/.ssh/config.local`). Once per Mac:

```sh
dotfiles doctor            # "waiting ~/.local/bin/muxy": Muxy's own server copy is here; leave it
ssh <alias> true           # once per listed Mac: accept its host key
muxy-reconcile --mode report   # what it would change, checked by Muxy; writes nothing
```

The algorithm, configuration, exit statuses and troubleshooting:
[docs/MUXY.md](docs/MUXY.md).

## Multi-Machine Setup

This repo is designed to sync across multiple machines via LaunchAgent (every 4 hours). Each machine converges on the features its profiles enable and installs their missing packages; app settings backup returns with rollout step 8 (see [Mackup](#mackup-app-config-backup)).

A machine set up before the feature engine needs its `machine.toml` and a
current Go before the migration reaches it; see
[Moving an existing machine to the feature engine](docs/OPERATIONS.md#moving-an-existing-machine-to-the-feature-engine).

### After install on a new machine

1. **GPG signing** — create `~/.gitconfig.local` (see `features/git/gitconfig.local.example`):

   ```ini
   [commit]
       gpgsign = true
   [user]
       signingkey = YOUR_GPG_KEY_ID
   [gpg]
       program = /opt/homebrew/bin/gpg
   ```

2. **Machine-specific packages** — create `Brewfile.local` in `~/.dotfiles/` (gitignored; sync installs it after the generated Brewfile):

   ```ruby
   brew "some-package-only-on-this-machine"
   cask "some-app"
   ```

3. **Machine-specific shell config** — create `~/.zshrc.local`

4. **Machine-specific SSH hosts** — create `~/.ssh/config.local`

5. **LaunchAgents**: `dotfiles doctor` lists the ones still waiting for a setup
   step (`otel-agent enroll`, `agent-monitor install`, OpenCode's local files);
   apply loads each once its step has run

6. **Agent shells**: `~/.dotfiles/bin/dotfiles-agents install` (see [Agent shells](#agent-shells))

Also log in to gh with the scopes and storage in
[Git identity and signing](docs/OPERATIONS.md#git-identity-and-signing), and register the signing
public key and its email with GitHub. The shared Git config contains this repo
owner's personal identity; set intentional overrides for another user or work
repository.

### How multi-machine sync works

- **Packages**: The `brew.*` features hold the curated package lists, split by role; `dotfiles apply` writes the enabled ones into `~/.config/dotfiles/generated/Brewfile`. Sync installs missing packages with `--no-upgrade` and disables Homebrew auto-update for this operation. Weekly updates own upgrades. Use `Brewfile.local` for machine-specific packages.
- **Features**: Sync runs `dotfiles apply` right after the merge. Files are linked one at a time, so no directory in `$HOME` is a link into the repository and a tool writing next to its config never writes into the repository.
- **Git sync**: Repositories with an unfinished merge, rebase, cherry-pick or bisect are skipped. Sync creates signed commits and merges and verifies signatures locally. A repository without a complete signing identity (user.name, user.email, user.signingkey and a working gpg.program) is only fast-forwarded: an overlay that supplies the identity still arrives, and the apply after it installs the identity. Its local edits, local commits or a diverged branch then fail the run until the identity is set. Source conflicts abort the merge; backup repositories retain their local-wins merge policy. Detached HEADs and branches without a matching `origin` tracking branch are skipped.
- **Publishing**: Gitleaks scans staged dotfiles and outgoing commits with redacted output; auxiliary repos are not scanned. Missing tools, scan failures, signing failures and merge failures stop publication. GitHub verification is checked after the push and does not undo publication on failure; bad_email requires correcting the signing identity.
- **Locking**: macOS `lockf` holds `logs/sync.flock` open during sync and during the weekly update, so packages never upgrade while a sync runs `brew bundle` or `dotfiles apply` (`lib_sh/sync-lock.sh`). A sync that finds the lock held skips its run; the update waits up to `UPDATE_LOCK_WAIT` seconds (30 minutes) and runs its own sync inside its lock. The file remains after exit, and its presence does not mean the lock is held. Check availability with `sync.sh check`.
- **Failures**: Sync returns a nonzero status when an operation fails and records the failure in `logs/sync.log`.
- **Local overrides**: `machine.toml`, the stubs, `.gitconfig.local`, `.zshrc.local`, `.ssh/config.local`, `Brewfile.local` and `~/.config/spotlight/exclusions.local` are never tracked.

## Mackup: App Config Backup

Sync does not run Mackup. Its configuration here would copy credential files
(`.codex/auth.json`, `.kube/config`, `.npmrc` and others) into the backup
repository, so automatic backups stay off until they return behind the guards
described in [the Mackup design](docs/MACHINE-FEATURES.md#mackup).

Until then:

- Never run `mackup link install`, `mackup link` or `mackup link uninstall`.
  Link mode moves your files into the store and leaves symlinks behind, and
  current macOS apps refuse to read or save symlinked preferences.
- Never run `mackup restore` without naming one app. Restore deletes the
  original before copying, resets every restored file to mode 0600, and
  replaces a dotfiles link with a copy.
- Mackup older than 0.9.0 runs link mode for a plain `mackup backup`; check
  `mackup --version` first.

## Key Bindings

| Key | Action |
| ----- | -------- |
| `Ctrl+R` | History search (Atuin) |
| `Ctrl+F` | Accept autosuggestion |
| `Option+Left/Right` | Word navigation |
| `Ctrl+A/E` | Line start/end |

## Troubleshooting

### Slow Shell Startup

```sh
# Profile startup time
time zsh -i -c exit

# Check plugin load times
zinit times

# Inspect loaded plugins before repairing a specific cache
zinit list
```

### A file is in the way

```sh
dotfiles doctor            # lists each problem with its path
dotfiles apply --dry-run   # what apply would change
```

`apply` never overwrites a file it did not create; it reports it and carries
on with everything else. Compare the file with the tracked one the message
names, keep what you need, move it aside, and run `dotfiles apply`. Editing a
linked file needs no apply. A managed copy edited here (`edited here since
dotfiles last wrote it`) is kept with `dotfiles adopt <path>`, or replaced with
the repository's version by deleting it and running `dotfiles apply`. See
[feature engine troubleshooting](docs/OPERATIONS.md#feature-engine-troubleshooting).

### Sync Issues

```sh
# Check sync log
tail -50 ~/.dotfiles/logs/sync.log

# Run sync manually with verbose output
~/.dotfiles/sync.sh sync 2>&1
```

## Adding New Dotfiles

### As a feature (recommended for configs you edit)

```sh
# 1. Create the feature; home/ mirrors $HOME
mkdir -p ~/.dotfiles/features/tool.myapp/home/.config/myapp
mv ~/.config/myapp/config.toml ~/.dotfiles/features/tool.myapp/home/.config/myapp/
cat > ~/.dotfiles/features/tool.myapp/feature.toml <<'EOF'
id = "tool.myapp"
description = "myapp settings"
category = "tools"

[provides]
link = [".config/myapp"]   # each file under it, linked one by one
EOF

# 2. Enable it in a profile (or one machine's machine.toml), then link it
$EDITOR ~/.dotfiles/profiles/base.toml
dotfiles apply

# 3. Commit it: sync never publishes new files
git -C ~/.dotfiles add features/tool.myapp profiles && git -C ~/.dotfiles commit -S -m "myapp: add config"
```

Use `copy` instead of `link` for a file the tool rewrites, so its edits show as
drift instead of landing in the repository.

## Package and AWS Helpers

The shared package manifest uses maintained `fastfetch` and `tlrc` clients in
place of removed or disabled clients, and uses Rustup for Rust toolchains. On a
fresh machine, initialize Rust with `rustup default stable`. Disabled or removed
casks are excluded from the shared manifest; existing applications are preserved.

`assume_role` and `rename_aws_profile` respect `AWS_SHARED_CREDENTIALS_FILE` and
`AWS_CONFIG_FILE`. Profile updates validate the response first, lock cooperating
writers, and replace files with mode `600`. Credentials are passed over stdin,
never printed or placed in command arguments. Profile renames reject collisions
before changing either file.

`assume_role ROLE_ARN SESSION_NAME PROFILE_NAME [REGION]` writes the returned
session to the named profile; the region defaults to `us-east-1`.
`rename_aws_profile OLD NEW` renames exact profile sections. See
[the helper map](STRUCTURE.md#shell-libraries) for inventory exporters.

## Resources

- [Zinit](https://github.com/zdharma-continuum/zinit)
- [Mackup](https://github.com/lra/mackup)
- [Atuin](https://atuin.sh/)
- [Dracula Theme](https://draculatheme.com/)

## Validation

Run the local regression suite without updating packages, contacting model APIs,
changing real credentials, or committing/pushing repository changes:

```sh
python3 -B -m unittest discover -s tests -v
```

The suite uses temporary files and mock external commands. Git operation guards
use temporary clones. `RealFeatures` builds the engine with the installed Go and
applies the repository's own features to temporary homes. `RepoGuard` runs
`features/agents.repo-guard/guard_test.sh` under the current bash and macOS's
bash 3.2, and both harnesses' registered hook commands; it needs jq. Engine unit tests:
`go test -race ./...`. Kernel-lock checks require macOS `lockf`; the agent
dashboard checks require Node.js; OpenCode worker checks require Bun and the
plugin dependencies OpenCode installs in `~/.config/opencode` (or a directory
holding `node_modules/@opencode-ai/plugin` named by
`DOTFILES_TEST_OPENCODE_DEPS`).

Tests with missing platform/tool prerequisites are skipped. Run from the
repository root, and use `git diff --check` to check whitespace. Warm
`time zsh -ic exit` measures configuration loading; it does not exercise every
plugin deferred until after the first prompt.

Documentation lint requires Node.js/npm:

```sh
npx --yes markdownlint-cli2@0.23.3 \
  "*.md" "docs/*.md" features/agents.opencode/README.md \
  features/agents.opencode/home/.config/opencode/agents/coordinator.md win10/readme.md
```

The [Markdown configuration](.markdownlint.json) permits wide command tables and
keyboard markup, and keeps table spacing consistent.

## Security

This repository is public and auto-pushed. Keep credentials, keys, private host
details, local overrides, and job output outside tracked source. Ignore rules and
secret scans cannot establish that every file is safe to publish. Review new
files and use private remotes for auxiliary backups. See
[sync recovery](docs/OPERATIONS.md#sync-failures) for signing, scans, conflicts, and
post-push verification failures.

OpenCode listens on loopback by default, with HTTP basic auth and no TLS.
`OPENCODE_HOSTNAME` opts in to another address; configure network protection
before enabling access from other devices; see
[OpenCode security](features/agents.opencode/README.md#security).
