# Muxy remote servers (tool.muxy)

## Overview

Muxy's desktop app lists remote servers in its sidebar, saved as `[[servers]]` tables in
its `settings.toml`, and reaches each one over SSH. Feature `tool.muxy` (desktop profile, macOS) makes every Mac list the other Macs of each
context it belongs to, from lists the contexts' overlays provide, so nobody adds or
updates servers by hand on each Mac. It installs:

| Part | What it does |
| --- | --- |
| `~/.local/bin/muxy` | Runs the `muxy` command line tool inside the installed Muxy app (`~/Applications/Muxy.app`, else `/Applications/Muxy.app`) |
| `~/.local/bin/muxy-reconcile` | Brings `[[servers]]` in step with the server lists in `~/.config/muxy/servers.d/` |
| LaunchAgent `com.ashtonian.muxy-reconcile` | Runs `muxy-reconcile` at load, when a list is added or removed, when `dotfiles apply` rewrites its generated files, and hourly |
| Setting `muxy.exclude_servers` | Declared servers this Mac leaves out ([Per-machine changes](#per-machine-changes)) |
| Homebrew `python` | Python 3.11 or later for `muxy-reconcile` (`tomllib`); macOS's `/usr/bin/python3` is 3.9 |

This repository is public, so it names no hosts. Each context's
[overlay](../README.md#overlays) provides its Macs: an `ssh_config` fragment with one
`Host` alias per Mac, and a server list linked to `~/.config/muxy/servers.d/<context>.toml`
that names those aliases.

### Why the wrapper

Muxy on another Mac logs in over SSH and runs
`sh -c 'export PATH="$PATH:$HOME/.local/bin"; exec muxy --version'`, then `muxy stdio`,
which starts the `muxy-server` beside that `muxy`. Whichever `muxy` it finds decides the
server version every remote client gets. The wrapper makes it the installed app's, so the
command line tool, the app's own server and what remote clients start are always one
version, and updating the app updates all three.

Muxy's own **Install muxy-server** keeps a copy of its server under `~/.local/bin/.muxy/`
(`pair-<version>.<random>/` and a `current` link to it) and links `~/.local/bin/muxy` into
it. A `muxy-server` started from that copy executes from there and holds the terminals of
every Mac connected to it. While `~/.local/bin/.muxy` exists, `dotfiles apply` leaves
`~/.local/bin/muxy` alone, whatever it is: it neither replaces it nor fills its place if it is
missing, and `dotfiles doctor` shows `waiting ~/.local/bin/muxy: left alone while
~/.local/bin/.muxy exists`. Nothing in this feature removes or moves either path. The copy
is retired by hand at a planned server restart ([Replacing Muxy's own server
copy](#replacing-muxys-own-server-copy)). apply checks that the copy exists, not whether a
server runs from it: a server can start from it at any moment, between apply's check and its
change.

### How a run works

1. **Read.** Every `*.toml` in the lists directory, in name order, and Muxy's
   `settings.toml`. A list that does not parse, or a destination declared in two lists,
   stops the run before anything is written: a list that cannot be read would otherwise
   look like servers removed.
2. **Resolve.** For each destination, declared or already in `settings.toml`: `ssh -G`
   gives its user, port, HostName and known_hosts files (so `~/.ssh/config.local` and the
   overlays' `Host` blocks apply exactly as they do for Muxy); `ssh-keygen -F` gives the
   host keys those files hold for it; the system resolver gives the HostName's addresses.
   Nothing connects to any server.
3. **Leave out this Mac.** A declared server is this Mac when its user is this account and
   either known_hosts holds one of this Mac's sshd host keys (`/etc/ssh/ssh_host_*_key.pub`)
   for it, or it is on port 22 at one of this Mac's interface addresses. The host key
   decides even when the name resolves to another interface's address.
4. **Match.** Each declared server takes one existing entry, in three passes: the entry it
   wrote for that destination before (the state file); else an entry with the same
   destination or the same `ssh_command`; else an entry that reaches the same user and port
   on the same machine. Two destinations are the same machine when they share an address or
   a known host key: a Mac with two interfaces has two addresses and one host key. An
   entry Muxy paired (it has a `paired` key) is matched only through the state file.
5. **Decide.** A matched entry keeps its `id`, which Muxy ties each remote project's tabs
   and layout to, and takes the list's `name`, `group` and `ssh` (or `ssh_command`). Its
   other keys, such as `password_login` or `identity_file`, go: the ssh configuration
   decides how to log in. An unmatched declared server gets a new entry with a fresh
   32-hex-digit id. An entry this command wrote whose server is no longer declared, or
   turned out to be this Mac, is removed. Entries it never wrote stay as they are.
6. **Check.** The rewritten file must parse to the original with only `servers` replaced.
   Muxy's own parser (`muxy config list --json` against a scratch profile holding the file
   and a copy of `terminal.toml`) must accept the current file and then the rewritten one,
   and must read back exactly the entries written.
7. **Write.** Holding Muxy's own settings lock (`settings.toml.lock`, the `flock` the app
   takes), and only if `settings.toml` still has the bytes this run read, the file is
   replaced through a temporary file and a rename. Only the `[[servers]]` tables change;
   every other byte is kept. New tables go where Muxy writes them, in key order. Then
   `muxy config reload` has a running app apply it.

A run that finds the servers in step changes no file and never runs Muxy.

### What Muxy's commands do to a running Muxy

From Muxy 2.5.0's own help and messages, checked against a scratch profile:

| Command | Effect on a running app, server and terminals |
| --- | --- |
| `muxy config list` | Reads the profile's files. "Does not start the app or server" |
| `muxy config set` / `unset` | Saves the file only if the app can start with the new value, then asks a running desktop app to read its settings again (`settings.reload` on the profile's `app.sock`). It never starts the app and never contacts `muxy-server`, where terminals run. If the app cannot apply the value, the command says `saved, but the running app couldn't apply it` and exits 1 |
| `muxy config reload` | Sends the same `settings.reload` to the desktop app: "Have the running desktop app read its settings files again. Does not start the app" |

`muxy-reconcile` runs only `config list` (against a scratch copy of the profile) and
`config reload`, and only when it has written `settings.toml`. Neither it nor `dotfiles
apply` stops, restarts or upgrades a server. In Muxy, a server is stopped or restarted
only from **Settings > Servers** (**Stop Server**, **Restart Server**), and both end that
server's terminals. A server update that the app downloads waits until every terminal
session on that server has ended unless someone confirms it. When the app and a running
server are different versions, Muxy says "Restarting the server will end active terminal
sessions" and waits for a person.

Not yet observed on a live app: what an open tab of a server does when `muxy-reconcile`
removes or renames that server's entry. The first live run goes on a Mac whose terminals
can be lost (the Mac mini), never first on a Mac whose sessions must survive.

## Config

### Server lists

`~/.config/muxy/servers.d/<context>.toml`, one per overlay:

```toml
group = "Home"                 # optional: the group Muxy files these servers under

[[server]]
name = "Desk"                  # the name Muxy shows
ssh = "desk"                   # an ssh destination: alias, host or user@host

[[server]]
name = "Build VM"
ssh = "build-vm"               # identifies the machine
ssh_command = "orb ssh build"  # optional: Muxy connects through this command instead
```

| Key | Type | Default | Description |
| --- | --- | --- | --- |
| `group` | string | none (Muxy's ungrouped list) | Group for every server in the file |
| `server[].name` | string | required | Name in Muxy's sidebar |
| `server[].ssh` | string | required | Destination for `ssh -G` and for Muxy. One argument: no spaces, control characters or leading `-`. Unique across all lists |
| `server[].ssh_command` | string | none | Muxy runs this to connect, and `ssh` only identifies the machine for matching. A server reached this way is not checked against known_hosts |

Files whose names start with `.` are skipped. Any other key is an error (exit 2).

### Per-machine changes

The lists are shared by every Mac of a context. One Mac changes what it gets in three
ways, each in a file only that Mac has:

| Change | Where | How |
| --- | --- | --- |
| Leave out a declared server | `~/.config/dotfiles/machine.toml` | `[settings]` `"muxy.exclude_servers" = "personal/laptop"`: space-separated `<list>/<ssh>` names, the list's file name without `.toml` and the server's `ssh`. An entry `muxy-reconcile` wrote for it is removed on the next run; entries added by hand are never touched |
| Add servers | `~/.config/muxy/servers.d/local.toml` (any name not used by an overlay) | A plain file in the list format above. No overlay links it, so it stays on this Mac. A destination may appear in one list only |
| Change a server's name or group | both of the above | Exclude it, then declare it again in the local list with the name and group this Mac shows. Its entry keeps its id, and so its tabs |
| Change how a server is reached | `~/.ssh/config.local` | A `Host <alias>` block there is read before the overlay's aliases, and ssh takes the first value it finds for each option, so its `HostName`, `User`, `Port` or `ProxyJump` win. Muxy and `muxy-reconcile` both go through ssh's configuration |

`muxy.exclude_servers` is a [dotfiles setting](../README.md#profiles-and-machines): a
profile's `[settings]` can set it for every Mac that lists the profile, and `machine.toml`
overrides it. A name that matches no declared server, or one that is not `<list>/<ssh>`,
stops the run with exit 2 before anything is written, so a typo never adds the server it
meant to leave out. launchd does not load the shell environment, so `muxy-reconcile`
reads the value `dotfiles apply` generated into `~/.config/dotfiles/generated/env.sh`,
with the same `lib_sh/machine-setting.sh` the repository's other LaunchAgent scripts use.
The LaunchAgent watches that directory, so a changed setting takes effect at the apply
that writes it. `MUXY_RECONCILE_EXCLUDE` in the environment, when set, wins over the
generated value.

### Environment

`muxy-reconcile` reads these; the LaunchAgent sets only `PATH`. Set others in the
template's `EnvironmentVariables` (`features/tool.muxy/launchagents/`), except the
exclusions, which belong in the `muxy.exclude_servers` setting.

| dotfiles setting | Type | Default | Description |
| --- | --- | --- | --- |
| `muxy.exclude_servers` | string | `""` | Declared servers this Mac leaves out, space-separated `<list>/<ssh>`. Exported as `MUXY_RECONCILE_EXCLUDE` |

| Variable | Type | Default | Description |
| --- | --- | --- | --- |
| `MUXY_DIR` | Directory path | `~/Library/Application Support/Muxy 2` | Muxy's profile, holding `settings.toml`; the same variable Muxy reads |
| `MUXY_RECONCILE_SERVERS_DIR` | Directory path | `$XDG_CONFIG_HOME/muxy/servers.d` (`~/.config/muxy/servers.d`) | Where the server lists are |
| `MUXY_RECONCILE_STATE` | File path | `$XDG_STATE_HOME/muxy-reconcile/managed.json` (`~/.local/state/...`) | The entries this command manages; its run lock is `lock` beside it |
| `MUXY_RECONCILE_LOG` | File path | `~/Library/Logs/muxy-reconcile/muxy-reconcile.log` | One line per decision |
| `MUXY_RECONCILE_LOG_MAX_BYTES` | Whole bytes, at least 1024 | `262144` | Past this size the log becomes `<log>.1`, replacing the previous one |
| `MUXY_RECONCILE_SSH` | File path | `/usr/bin/ssh` | The ssh whose `-G` output is used; tests point it at a stand-in |
| `MUXY_RECONCILE_SELF_ADDRESSES` | Space-separated addresses | this Mac's interface addresses, from `/sbin/ifconfig` | Addresses that mean "this Mac" |
| `MUXY_RECONCILE_HOST_KEYS` | Space-separated files or glob patterns | `/etc/ssh/ssh_host_*_key.pub` | This Mac's sshd public host keys |
| `MUXY_RECONCILE_TIMEOUT` | Whole seconds, at least 1 | `30` | Limit for each `ssh -G`, `ssh-keygen`, name lookup, `muxy` call and setting read |
| `MUXY_RECONCILE_EXCLUDE` | Space-separated `<list>/<ssh>` names | the `muxy.exclude_servers` setting `dotfiles apply` generated (empty) | Declared servers this Mac leaves out ([Per-machine changes](#per-machine-changes)) |
| `DOTFILES_MUXY_APP` | Directory path | unset: `~/Applications/Muxy.app` if it holds the tool, else `/Applications/Muxy.app` | The app bundle whose `Contents/MacOS/muxy` the wrapper runs, and so the one `muxy-reconcile` checks with. The search order is the one `dotfiles apply` uses for Muxy settings |
| `XDG_CONFIG_HOME` / `XDG_STATE_HOME` | Directory path | `~/.config` / `~/.local/state` | Bases of the two defaults above |

Fixed: Muxy's settings lock is waited for 10 s, another `muxy-reconcile` run 60 s.

### LaunchAgent

| Key | Value | Why |
| --- | --- | --- |
| `RunAtLoad` | true | At login and whenever `dotfiles apply` loads or reloads it |
| `WatchPaths` | `~/.config/muxy`, `~/.config/muxy/servers.d`, `~/.config/dotfiles/generated` | A list added or removed (an overlay joined or left), the directory being created, and `dotfiles apply` writing a changed `muxy.exclude_servers` into `env.sh` |
| `StartInterval` | 3600 | An edit inside a linked list changes the overlay's file, not the directory launchd watches; the hourly run picks it up |
| `EnvironmentVariables.PATH` | `/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin` | Homebrew's python3 first |
| `ProcessType`, `LowPriorityIO`, `Nice` | `Background`, true, 10 | It is never urgent |

apply installs it once `/Applications/Muxy.app` and `/opt/homebrew/bin/python3` exist. The
`muxy` cask installs the app there; a Muxy only in `~/Applications` gets the wrapper but not
the LaunchAgent.

### Growth bounds

| Record | Bound |
| --- | --- |
| `muxy-reconcile.log` and `.1` | At most twice `MUXY_RECONCILE_LOG_MAX_BYTES` (512 KiB by default); a run writes one line, plus one per server |
| `launchd.out`, `launchd.err` | One line per run; `bin/disk-hygiene` (base profile) cuts each LaunchAgent log to its newest half past `DISK_HYGIENE_LOG_MAX_BYTES` (1 MiB) |
| `managed.json` | One record per managed server per Muxy profile; profiles whose `settings.toml` is gone are dropped on every save |
| `settings.toml` | One entry per declared server, other Macs only, plus the entries added by hand |

A run costs one `ssh -G` per distinct destination, one `ssh-keygen -F` per destination
and known_hosts file, and one name lookup per HostName (eight at a time); Muxy runs only
when something changes (two `config list` and one `config reload`).

## External Dependencies

- Muxy in `~/Applications/Muxy.app` or `/Applications/Muxy.app` (Homebrew cask `muxy`), with
  `muxy config list --json` and `muxy config reload --json`; tested with 2.5.0. Without it the wrapper exits
  69, `muxy-reconcile` exits 69 when it has something to write, and the LaunchAgent waits.
- Homebrew `python` (3.11 or later).
- OpenSSH's `ssh` and `ssh-keygen` (`/usr/bin`), `/sbin/ifconfig`.
- On each listed Mac: Remote Login on, this Mac's key authorized, and its host key in
  this Mac's known_hosts under the name the alias resolves to (Muxy connects with
  `StrictHostKeyChecking=ask` and `BatchMode=yes`, so an unknown key fails instead of
  being accepted).
- An overlay providing the list and the `Host` aliases.

## API / Interfaces

```sh
muxy [args...]              # the app's muxy; exit 69 if the app is missing
muxy-reconcile              # bring [[servers]] in step; prints one summary line
muxy-reconcile --dry-run    # print each decision and the new [[servers]], checked by Muxy; write nothing
```

Summary lines: `in step: 2 unchanged, 1 this Mac`, `changed: 1 added, 1 adopted, 1 this Mac;
the running app applied it`. The counts: `added`, `adopted` (an entry added by hand now
managed, id kept), `updated`, `removed`, `unchanged`, `not managed` (entries it leaves
alone), `this Mac`, `excluded` (left out by `muxy.exclude_servers`), `unresolved` (no
address and no known host key: not added this run; an existing entry is kept), `no host
key` (Muxy will not connect until one is accepted).

| Exit status | Meaning |
| --- | --- |
| 0 | In step, changed, or Muxy has no `settings.toml` yet (open Muxy once) |
| 1 | Muxy refused the current or the new file, a command failed, or the file was written but the running app did not apply it |
| 2 | A server list, the state file, `muxy.exclude_servers` or a variable is wrong |
| 3 | Muxy saved `settings.toml` during the run, or held its lock, or another run held the run lock: nothing written; the next run retries |
| 69 | Muxy.app is missing and something needed writing |

Files:

| Path | Access |
| --- | --- |
| `$MUXY_DIR/settings.toml` | Read; its `[[servers]]` tables rewritten |
| `$MUXY_DIR/settings.toml.lock` | Muxy's lock, held while writing |
| `$MUXY_DIR/terminal.toml` | Copied into the scratch profile Muxy checks with |
| `~/.config/muxy/servers.d/*.toml` | Read |
| `~/.config/dotfiles/generated/env.sh` | Read, through `lib_sh/machine-setting.sh`, when `MUXY_RECONCILE_EXCLUDE` is not set |
| `~/.local/state/muxy-reconcile/managed.json`, `lock` | Written (mode 0600), run lock |
| `~/Library/Logs/muxy-reconcile/` | Log, and the LaunchAgent's output |

Never read or written: `remote.json` (it holds Muxy's TLS private key), `server.toml`,
`desktop-state.json`, sessions, `~/.local/bin/.muxy`, and the `muxy-server` process.

## Build / Run / Test

Setup, once per Mac, after `dotfiles apply` with the overlay listed in `machine.toml`:

1. `dotfiles doctor`. If it shows `waiting ~/.local/bin/muxy: left alone while
   ~/.local/bin/.muxy exists`, this Mac has Muxy's own server copy. Leave it: the other
   Macs keep reaching this one through it. It is replaced only at a planned server restart
   ([Replacing Muxy's own server copy](#replacing-muxys-own-server-copy)).
2. `ssh <alias> true` once for each alias in the list, accepting the host key, so it is in
   known_hosts under the name Muxy uses.
3. `muxy-reconcile --dry-run`: what it would change, checked by Muxy. Then `muxy-reconcile`,
   or wait for the LaunchAgent. Run it first on a Mac whose open terminals can be lost.

### Replacing Muxy's own server copy

Only at a planned restart of this Mac's server, when every terminal on it may end: those
of this Mac's own Muxy that run on that server, and those of every other Mac connected to
it. Never while a session that must survive runs on it, such as an agent working in a
Muxy terminal.

1. See what runs from the copy:

   ```sh
   ps -axo pid,lstart,command | grep '[m]uxy-server'
   ```

   A path under `~/.local/bin/.muxy/` is a server running from the copy. If one runs and
   its terminals must stay, stop here: nothing changes until the planned restart.
2. Stop that server from Muxy: **Settings > Servers**, this Mac's server, **Stop Server**.
   Run the `ps` again: nothing may run from `~/.local/bin/.muxy/`.
3. Move the copy and its link aside, keeping them until the new server works:

   ```sh
   [ "$(readlink ~/.local/bin/muxy)" = .muxy/current/muxy ] && mv ~/.local/bin/muxy ~/.local/bin/.muxy.retired.link
   mv ~/.local/bin/.muxy ~/.local/bin/.muxy.retired
   ```

4. `dotfiles apply` links the wrapper. The next Mac that connects starts the installed
   app's server. Once it does, delete `~/.local/bin/.muxy.retired` and
   `~/.local/bin/.muxy.retired.link`.

To roll back before deleting them, move both back and stop the new server the same way.

Tests:

```sh
python3 -B -m unittest tests.test_dotfiles.MuxyReconcile -v
python3 -B -m unittest tests.test_dotfiles.RealFeatures -v   # the feature, applied by the engine
```

`MuxyReconcile` runs the command against temporary profiles, with stand-ins for `ssh -G`,
known_hosts and this Mac's addresses and host key, and checks each result with the real
Muxy (tests needing it are skipped without `/Applications/Muxy.app`).

## Operations

- **Health.** `muxy-reconcile --dry-run` ends `in step: ...`. The log has one `run` line per
  run and the decisions after it. `launchctl print "gui/$(id -u)/com.ashtonian.muxy-reconcile"`
  shows the last exit status.
- **Changing the list.** Edit the overlay's list; sync publishes it and the other Macs pick
  it up within an hour of their next sync. `launchctl kickstart
  "gui/$(id -u)/com.ashtonian.muxy-reconcile"` runs it now.
- **Removing a server.** Take it out of the list. Deleting a managed entry in Muxy brings it
  back at the next run; renaming it is undone. To change it on one Mac only, see
  [Per-machine changes](#per-machine-changes).
- **Keeping one Mac's own servers.** Entries added in Muxy that match no declared server
  are never touched.

What Muxy runs, by hand, from the Mac that shows a server offline (its options are
Muxy's own):

```sh
ssh -o BatchMode=yes -o StrictHostKeyChecking=ask -o IdentitiesOnly=yes <alias> \
  'sh -c '\''export PATH="$PATH:$HOME/.local/bin"; command -v muxy; exec muxy --version'\'''
```

Troubleshooting:

| Symptom | Check | Fix |
| --- | --- | --- |
| A server shows offline in Muxy | `ssh -G <alias> \| grep -E '^(user\|hostname\|port\|hostkeyalias) '`: is it the Mac you expect? A `Host <alias>` in `~/.ssh/config.local` is read first and wins over the overlay's | Remove or rename the `config.local` block |
| Offline, and the log says `no host key` for it | known_hosts has no key under that HostName; Muxy's `StrictHostKeyChecking=ask` with `BatchMode=yes` refuses instead of asking | `ssh <alias> true` once and accept the key |
| Offline, `ssh <alias> true` works | The command above prints `~/.local/bin/muxy` and the app's version | `muxy: not found`: tool.muxy is not applied there, or apply is holding `~/.local/bin/muxy` for Muxy's own server copy there (`dotfiles doctor` there; [Replacing Muxy's own server copy](#replacing-muxys-own-server-copy), at a planned restart only). Another path or version: that `muxy` comes first on the far side's PATH; take it off that PATH, or update Muxy there. Never remove a `muxy` that a running `muxy-server` there executes from (`ps`) |
| `waiting ~/.local/bin/muxy: left alone while ~/.local/bin/.muxy exists` | Expected on a Mac with Muxy's own server copy | Nothing now; [Replacing Muxy's own server copy](#replacing-muxys-own-server-copy) at a planned server restart |
| A server should not be listed on this Mac | `muxy-reconcile --dry-run` | Add `<list>/<ssh>` to `muxy.exclude_servers` in `machine.toml` ([Per-machine changes](#per-machine-changes)), then `dotfiles apply` |
| Exit 2 `muxy.exclude_servers names <list>/<ssh>, which no list ... declares` | `ls ~/.config/muxy/servers.d`, and the `ssh` of the server in that list | Fix the name: `<list>` is the file name without `.toml`, `<ssh>` the server's `ssh` value, not its name. Nothing was written |
| Exit 1 `reading the dotfiles setting MUXY_RECONCILE_EXCLUDE` | `bash -c 'source ~/.dotfiles/lib_sh/machine-setting.sh; machine_setting MUXY_RECONCILE_EXCLUDE'` | The checkout `muxy-reconcile` is linked from lacks `lib_sh/machine-setting.sh`, or `generated/env.sh` fails: run `dotfiles apply` |
| A Mac lists itself | The log line for it says `added`, not `this Mac` | Its alias leads to an address not on this Mac and a host key known_hosts does not hold here: `ssh <alias> true` from this Mac stores it |
| Another Mac is missing, log says `this Mac` | `ssh -G <alias>`'s user and HostName; `ssh-keygen -F <hostname>` | Two Macs sharing a host key (a cloned disk) look like one; `sudo ssh-keygen -A` after deleting `/etc/ssh/ssh_host_*` on one of them gives it its own |
| An entry added by hand turned into a managed one | The log's `adopted:` line | It reached the same machine as a declared server, so it took the list's name and settings and kept its id (and tabs). Expected |
| Exit 1 `Muxy refuses the current ...` | `muxy config list` names the line | Fix the file in Muxy (**Settings > Backup & Restore**) or by hand; nothing is written until Muxy accepts it |
| Exit 1 `Muxy refuses the new servers` | The message names the key | The list has a value Muxy rejects (such as a name too long); fix the list |
| Exit 1 `lists its servers in a form ...` | `[[servers]]` written inline or as an array | Edit and save any server in Muxy so it rewrites the file |
| Exit 1 `wrote ..., but the running Muxy did not apply it` | `muxy config reload` | Nothing is lost: the file is right and the app reads it when it next starts. Leave it until the app is relaunched anyway (an update). Never use **Restart Server** or **Stop Server** for this: they end that server's terminals. Quitting the app keeps terminals only when the server setting **Keep terminals running after quitting** is on; check it before quitting, and never use **End All Sessions and Quit** |
| Exit 2 naming a list | The file and key it names | Fix the overlay's list |
| Exit 2 `not a muxy-reconcile state file` | `managed.json` | Delete it; entries are matched again by destination and machine |
| Exit 3 | Muxy saved during the run | Nothing to do; the next run retries |
| Exit 69 | `ls -d ~/Applications/Muxy.app /Applications/Muxy.app` | `brew install --cask muxy` |
| `needs Python 3.11 or later` | `which python3` in the job's PATH | `brew install python` |

## Security

- Lists hold aliases and names, never credentials. Logins go through the ssh
  configuration and agent; managed entries drop `password_login` and `identity_file`.
- A run connects to nothing: `ssh -G` only prints configuration, `ssh-keygen -F` only reads
  known_hosts, and name lookups use the system resolver.
- A destination is one `ssh -G` argument after `--` and may not start with `-`, so a list
  cannot pass ssh options.
- `remote.json`, which holds Muxy's TLS private key, is never opened, copied or logged.
- The state file is mode 0600. The log holds server names, aliases and entry ids.
- Host names and addresses stay in the overlays; this repository holds none.

## Code Map

| Path | Purpose |
| --- | --- |
| [features/tool.muxy/feature.toml](../features/tool.muxy/feature.toml) | The feature: the two links and the hold on `~/.local/bin/muxy`, Homebrew `python`, the LaunchAgent and when it installs, `muxy.exclude_servers` |
| [lib_sh/machine-setting.sh](../lib_sh/machine-setting.sh) | Reads `muxy.exclude_servers` as `dotfiles apply` generated it |
| [features/tool.muxy/home/.local/bin/muxy](../features/tool.muxy/home/.local/bin/muxy) | The wrapper |
| [features/tool.muxy/home/.local/bin/muxy-reconcile](../features/tool.muxy/home/.local/bin/muxy-reconcile) | The reconciler: list and settings parsing, resolution, matching, Muxy checks, the write |
| [features/tool.muxy/launchagents/com.ashtonian.muxy-reconcile.plist](../features/tool.muxy/launchagents/com.ashtonian.muxy-reconcile.plist) | The LaunchAgent template |
| [tests/test_dotfiles.py](../tests/test_dotfiles.py) (`MuxyReconcile`, `RealFeatures`) | Behaviour against Muxy's own parser; the feature applied by the engine |
