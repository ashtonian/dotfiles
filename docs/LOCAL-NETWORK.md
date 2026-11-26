# Local Network allow-lists

## Overview

macOS Local Network privacy (macOS 15 and later) blocks a program's outgoing
connections to the subnets of the Mac's own interfaces until that program is
granted access in System Settings → Privacy & Security → Local Network. A
blocked connection fails with `EHOSTUNREACH` (errno 65), which Go and most
tools print as `connect: no route to host`; nothing says it was privacy.

Granting tools one at a time does not hold on a Mac that runs command-line
tools from Homebrew:

- **Grants are per executable.** macOS records each grant against the
  program's code signature and path. Homebrew bottles are ad-hoc signed, and
  each version installs to its own Cellar path, so every `brew upgrade` makes
  a new program with no grant. The grant list keeps one dead entry per old
  version.
- **Short-lived tools never get the prompt.** macOS does not show the alert
  when the process that made the connection exits right after it fails
  (FB16131937), so `terraform plan` or a one-shot script never appears in the
  list to switch on.
- **Most terminal hosts are not exempt.** Apple exempts command-line tools run
  from Terminal or over SSH, launchd daemons and root processes (TN3179).
  Other hosts differ; under Muxy on macOS 27.2.1, every process in a session
  (`muxy-server`, the shell, the tool) is its own responsible program, so each
  binary needs its own grant. LaunchAgents are never exempt.

Feature `macos.local-network` uses Apple's address allow-lists instead (TN3179,
macOS 15.5 and later). Every address in a listed network is treated as not
local, for every program on the Mac, so no tool needs a grant to reach it,
whatever it is and however often it is upgraded. There are two lists, by
interface type: `AllowedEthernetLocalNetworkAddresses` for wired interfaces and
`AllowedWiFiLocalNetworkAddresses` for Wi-Fi, in the system domain
`/Library/Preferences/com.apple.network.local-network.plist`. The feature takes
both from settings, writes them with `dotfiles apply --sudo`, and its check
reports `pending` until the Mac has restarted, because Apple requires a restart
for a change to take effect.

Only directly attached subnets are gated. A network the Mac reaches through a
router (another VLAN, a Kubernetes LoadBalancer range advertised to the router)
is not local and never needs listing.

The networks are a site's facts, so the public repository declares the feature
and an overlay profile both enables it and sets the networks.

## Config

| Setting | Environment | Type | Default | Description |
| --- | --- | --- | --- | --- |
| `local_network.ethernet` | `DOTFILES_LOCAL_NETWORK_ETHERNET` | Space-separated CIDR networks | empty | The networks every program may reach over wired interfaces without a grant: `AllowedEthernetLocalNetworkAddresses` |
| `local_network.wifi` | `DOTFILES_LOCAL_NETWORK_WIFI` | Space-separated CIDR networks | empty | The same over Wi-Fi: `AllowedWiFiLocalNetworkAddresses` |
| — | `DOTFILES_SYSTEM_ROOT` | Directory path | empty (`/`) | Prefix for the system domain, so tests never touch this Mac's lists. Shared with `bin/dotfiles-agents` |
| — | `DOTFILES_BOOT_TIME` | Epoch seconds | `kern.boottime` | The last boot, for tests; `check` compares the domain's modification time with it |
| — | `DOTFILES_MACOS_VERSION` | Version string | `sw_vers -productVersion` | The macOS version, for tests |

Each network is an IPv4 network with no host bits set (`192.0.2.0/24`, not
`192.0.2.7/24`) or an IPv6 prefix, with a prefix length of 1 or more. `/0` is
refused: it would exempt every address on every network the Mac ever joins.
An empty setting writes an empty list. The feature owns both keys: `install`
replaces whatever they hold, including values set by hand, and leaves any
other key in the domain alone.

The feature is off by default. An overlay profile turns it on:

```toml
# profiles/<overlay>.toml
[features]
enable = ["macos.local-network"]

[settings]
"local_network.ethernet" = "192.0.2.0/24"
"local_network.wifi" = "198.51.100.0/24"
```

List the subnets the context's Macs attach to directly. A network listed on a
Mac that never joins it does nothing there.

## External Dependencies

| Dependency | Why |
| --- | --- |
| macOS 15.5 or later | The release that reads the allow-lists; `check` reports an error on an earlier one |
| `/usr/libexec/nesessionmanager` | Reads both keys with `CFPreferencesCopyAppValue`, whose search includes the system-wide domain in `/Library/Preferences` (its imports and strings, verified on macOS 27.2.1) |
| `defaults`, `plutil`, `stat`, `sysctl` | Write the lists through cfprefsd; read them, the domain's modification time and the boot time |
| `sudo` | Writing the system domain. `dotfiles apply --sudo` hands the terminal to the hook for the password |

## API / Interfaces

| Command | Does | Exit |
| --- | --- | --- |
| `dotfiles-local-network install` | Writes each list whose contents differ from its setting, through sudo unless the domain's directory is writable; prints `restart this Mac …` to standard error when it wrote anything | 0; 65 a setting holds something that is not a network; 69 not macOS 15.5 or later; 74 a write failed |
| `dotfiles-local-network check` | One line: `ok`, `pending` (written after the last boot), `missing` (a list is empty but its setting is not) or `drift` (a list holds something else) | 0 when `ok`, else 1; 65; 69 |
| `dotfiles-local-network check --json` | The same as the feature's check result: `{"state": "ok\|pending\|missing\|drift\|error", "detail": …}` | 0 |
| `dotfiles-local-network uninstall` | Deletes both keys; prints the restart notice when it deleted anything | 0; 69; 74 |

The feature's hooks call these: the check every apply and doctor, `install`
from `dotfiles apply --sudo`, and `uninstall` as the teardown once the feature
is off. The engine lists a `pending` check as waiting, not as a problem, and
runs no hook for it.

## Build / Run / Test

```sh
python3 -B -m unittest tests.test_dotfiles.LocalNetwork -v
python3 -B -m unittest tests.test_dotfiles.RealFeatures.test_the_local_network_allow_lists_wait_for_apply_sudo_then_for_a_restart -v

dotfiles apply --sudo     # write the lists from the settings
dotfiles doctor           # `waiting macos.local-network: restart this Mac …` until the restart
```

The tests run on macOS only, against a system root of their own
(`DOTFILES_SYSTEM_ROOT`), and use documentation address ranges.

## Operations

**Health.** `dotfiles doctor` says nothing about `macos.local-network` once the
lists match the settings and the Mac has restarted since they were written.
`waiting … restart this Mac` means they are written and not yet in effect.
To see the lists: `plutil -p /Library/Preferences/com.apple.network.local-network.plist`.

**Proving it works.** Pick an address on a listed network and connect to it
with a program that has no grant, such as Homebrew's curl, beside Apple's:

```sh
/usr/bin/curl -sk -o /dev/null -w '%{http_code}\n' --max-time 4 https://<address>:<port>/
"$(brew --prefix curl)/bin/curl" -sk -o /dev/null -w '%{http_code}\n' --max-time 4 https://<address>:<port>/
```

Both print an HTTP status once the lists are in effect. Before, the second
prints `000` and exits 7.

**Bounds.** Two keys holding a handful of networks each; nothing accumulates.

**Failure modes.**

- *A tool reports `no route to host` (errno 65) for a LAN address.* Run
  `route -n get <address>`. A `gateway:` line means the address is routed,
  so privacy is not the cause: look at the network. With only an
  `interface:` line, the address is on a directly attached subnet:
  - `dotfiles doctor` shows `waiting … restart this Mac`: restart.
  - The subnet is not in the setting for that interface's type
    (`networksetup -listallhardwareports` names each interface's type): add
    it to the overlay profile, then `dotfiles apply --sudo` and restart.
  - It is listed and in effect: compare with `/usr/bin/curl`, which reached
    attached subnets without a grant on macOS 27.2.1. If both fail, look at
    the host.
- *`problem macos.local-network: missing: … ; run dotfiles apply --sudo`.* The
  settings name networks the lists do not hold yet (first run, or a changed
  setting). Run `dotfiles apply --sudo`.
- *`hooks.apply ran, and the check still reports drift`.* Something rewrote
  the keys after the hook: a configuration profile, or a script with
  `defaults write`. Find it; the feature owns these keys.
- *`error: macOS … ignores the allow-lists`.* The Mac runs a release before
  15.5. Update macOS, or turn the feature off there.
- *`error: setting local_network.…: … is not a network in CIDR form`.* Fix the
  value in the overlay profile: no host bits, prefix 1 or longer.
- *Turning it off.* Disable the feature, then `dotfiles apply --sudo` runs the
  teardown, which deletes both keys; restart for privacy to cover those
  networks again.

## Security

- Every program on the Mac, apps included, reaches the listed networks
  without asking. Local Network privacy is a consent prompt, not a firewall:
  services on those networks have to protect themselves from granted
  programs either way. Keep the lists to the exact subnets the Mac
  administers.
- The lists apply wherever the Mac is: on a foreign network that happens to
  use a listed range, programs reach its hosts without a prompt too.
  Narrow prefixes keep that unlikely; `/0` is refused outright.
- Only an administrator can change the system domain; the check reads it
  without privileges.
- The networks are site details, so they live in an overlay profile, never in
  this repository.

## Code Map

| File | Purpose |
| --- | --- |
| [features/macos.local-network/feature.toml](../features/macos.local-network/feature.toml) | The feature: its two settings, the sudo hooks and the check |
| [features/macos.local-network/hooks/](../features/macos.local-network/hooks/) | `check`, `install`, `uninstall`: each calls `bin/dotfiles-local-network` |
| [bin/dotfiles-local-network](../bin/dotfiles-local-network) | Validates the settings, compares, writes and deletes both lists, and reports a pending restart |
| [tests/test_dotfiles.py](../tests/test_dotfiles.py) | `LocalNetwork` (the script), `RealFeatures` (the engine running the feature end to end) |
