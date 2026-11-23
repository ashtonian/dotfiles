# Muxy remote servers (tool.muxy)

## Overview

Muxy's desktop app lists remote servers in its sidebar, saved as `[[servers]]` tables in
its `settings.toml`, and reaches each one over SSH. Feature `tool.muxy` (desktop profile, macOS) makes every Mac list the other Macs of each
context it belongs to, from lists the contexts' overlays provide, so nobody adds or
updates servers by hand on each Mac. It installs:

| Part | What it does |
| --- | --- |
| `~/.local/bin/muxy` | Runs the `muxy` command line tool inside `/Applications/Muxy.app` |
| `~/.local/bin/muxy-reconcile` | Brings `[[servers]]` in step with the server lists in `~/.config/muxy/servers.d/` |
| LaunchAgent `com.ashtonian.muxy-reconcile` | Runs `muxy-reconcile` at load, when a list is added or removed, and hourly |
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
version, and updating the app updates all three. A `~/.local/bin/muxy` left by Muxy's own
**Install muxy-server** (a link into `~/.local/bin/.muxy/`) is a file in the way; remove it
once ([Setup](#build--run--test)).

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

### Environment

`muxy-reconcile` reads these; the LaunchAgent sets only `PATH`. Set others in the
template's `EnvironmentVariables` (`features/tool.muxy/launchagents/`).

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
| `MUXY_RECONCILE_TIMEOUT` | Whole seconds, at least 1 | `30` | Limit for each `ssh -G`, `ssh-keygen`, name lookup and `muxy` call |
| `DOTFILES_MUXY_APP` | Directory path | `/Applications/Muxy.app` | The app bundle whose `Contents/MacOS/muxy` the wrapper runs, and so the one `muxy-reconcile` checks with |
| `XDG_CONFIG_HOME` / `XDG_STATE_HOME` | Directory path | `~/.config` / `~/.local/state` | Bases of the two defaults above |

Fixed: Muxy's settings lock is waited for 10 s, another `muxy-reconcile` run 60 s.

### LaunchAgent

| Key | Value | Why |
| --- | --- | --- |
| `RunAtLoad` | true | At login and whenever `dotfiles apply` loads or reloads it |
| `WatchPaths` | `~/.config/muxy`, `~/.config/muxy/servers.d` | A list added or removed (an overlay joined or left), and the directory being created |
| `StartInterval` | 3600 | An edit inside a linked list changes the overlay's file, not the directory launchd watches; the hourly run picks it up |
| `EnvironmentVariables.PATH` | `/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin` | Homebrew's python3 first |
| `ProcessType`, `LowPriorityIO`, `Nice` | `Background`, true, 10 | It is never urgent |

apply installs it once `/Applications/Muxy.app` and `/opt/homebrew/bin/python3` exist.

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

- Muxy in `/Applications/Muxy.app` (Homebrew cask `muxy`), with
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
alone), `this Mac`, `unresolved` (no address and no known host key: not added this run;
an existing entry is kept), `no host key` (Muxy will not connect until one is accepted).

| Exit status | Meaning |
| --- | --- |
| 0 | In step, changed, or Muxy has no `settings.toml` yet (open Muxy once) |
| 1 | Muxy refused the current or the new file, a command failed, or the file was written but the running app did not apply it |
| 2 | A server list, the state file or a variable is wrong |
| 3 | Muxy saved `settings.toml` during the run, or held its lock, or another run held the run lock: nothing written; the next run retries |
| 69 | Muxy.app is missing and something needed writing |

Files:

| Path | Access |
| --- | --- |
| `$MUXY_DIR/settings.toml` | Read; its `[[servers]]` tables rewritten |
| `$MUXY_DIR/settings.toml.lock` | Muxy's lock, held while writing |
| `$MUXY_DIR/terminal.toml` | Copied into the scratch profile Muxy checks with |
| `~/.config/muxy/servers.d/*.toml` | Read |
| `~/.local/state/muxy-reconcile/managed.json`, `lock` | Written (mode 0600), run lock |
| `~/Library/Logs/muxy-reconcile/` | Log, and the LaunchAgent's output |

Never read or written: `remote.json` (it holds Muxy's TLS private key), `server.toml`,
`desktop-state.json`, sessions, and the `muxy-server` process.

## Build / Run / Test

Setup, once per Mac, after `dotfiles apply` with the overlay listed in `machine.toml`:

1. If `~/.local/bin/muxy` is in the way (apply reports it), it came from Muxy's
   **Install muxy-server**: `rm ~/.local/bin/muxy; rm -rf ~/.local/bin/.muxy`, then
   `dotfiles apply`.
2. `ssh <alias> true` once for each alias in the list, accepting the host key, so it is in
   known_hosts under the name Muxy uses.
3. `muxy-reconcile --dry-run`: what it would change, checked by Muxy. Then `muxy-reconcile`,
   or wait for the LaunchAgent.

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
  back at the next run; renaming it is undone.
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
| Offline, `ssh <alias> true` works | The command above prints `~/.local/bin/muxy` and the app's version | `muxy: not found`: tool.muxy is not applied there, or `~/.local/bin/muxy` is in the way there (Setup step 1). Another path or version: that `muxy` comes first on the far side's PATH; remove it, or update Muxy there |
| A Mac lists itself | The log line for it says `added`, not `this Mac` | Its alias leads to an address not on this Mac and a host key known_hosts does not hold here: `ssh <alias> true` from this Mac stores it |
| Another Mac is missing, log says `this Mac` | `ssh -G <alias>`'s user and HostName; `ssh-keygen -F <hostname>` | Two Macs sharing a host key (a cloned disk) look like one; `sudo ssh-keygen -A` after deleting `/etc/ssh/ssh_host_*` on one of them gives it its own |
| An entry added by hand turned into a managed one | The log's `adopted:` line | It reached the same machine as a declared server, so it took the list's name and settings and kept its id (and tabs). Expected |
| Exit 1 `Muxy refuses the current ...` | `muxy config list` names the line | Fix the file in Muxy (**Settings > Backup & Restore**) or by hand; nothing is written until Muxy accepts it |
| Exit 1 `Muxy refuses the new servers` | The message names the key | The list has a value Muxy rejects (such as a name too long); fix the list |
| Exit 1 `lists its servers in a form ...` | `[[servers]]` written inline or as an array | Edit and save any server in Muxy so it rewrites the file |
| Exit 1 `wrote ..., but the running Muxy did not apply it` | `muxy config reload` | Restart Muxy; the file is already right |
| Exit 2 naming a list | The file and key it names | Fix the overlay's list |
| Exit 2 `not a muxy-reconcile state file` | `managed.json` | Delete it; entries are matched again by destination and machine |
| Exit 3 | Muxy saved during the run | Nothing to do; the next run retries |
| Exit 69 | `ls /Applications/Muxy.app` | `brew install --cask muxy` |
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
| [features/tool.muxy/feature.toml](../features/tool.muxy/feature.toml) | The feature: the two links, Homebrew `python`, the LaunchAgent and when it installs |
| [features/tool.muxy/home/.local/bin/muxy](../features/tool.muxy/home/.local/bin/muxy) | The wrapper |
| [features/tool.muxy/home/.local/bin/muxy-reconcile](../features/tool.muxy/home/.local/bin/muxy-reconcile) | The reconciler: list and settings parsing, resolution, matching, Muxy checks, the write |
| [features/tool.muxy/launchagents/com.ashtonian.muxy-reconcile.plist](../features/tool.muxy/launchagents/com.ashtonian.muxy-reconcile.plist) | The LaunchAgent template |
| [tests/test_dotfiles.py](../tests/test_dotfiles.py) (`MuxyReconcile`, `RealFeatures`) | Behaviour against Muxy's own parser; the feature applied by the engine |
