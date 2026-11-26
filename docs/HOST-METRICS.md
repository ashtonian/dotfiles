# Host metrics

## Overview

The `macos.host-metrics` feature sends each Mac's hardware metrics to the
cluster: power, temperatures and fan speed, thermal and memory pressure, CPU,
memory, disk and network use, SSD health and wear, and on a laptop the
battery's health. Two exporters and a textfile writer run as LaunchAgents and
listen on loopback only; the agent telemetry collector
([AGENT-TELEMETRY.md](AGENT-TELEMETRY.md)) scrapes them every minute and
forwards the samples through its own disk queue, with the Mac's token, to the
cluster gateway, which stores them in Mimir.

```text
host-metrics collect (60 s) → textfiles: thermal pressure, battery, SMART ─┐
node_exporter      127.0.0.1:9100  (job mac-node) ←───────────────────────┘ ─┐
macmon serve       127.0.0.1:9101  (job macmon)                              ─┴─ otel-agent prometheus/host (60 s)
                                                                                 → otlp_http/host disk queue → gateway → Mimir
```

Nothing is pulled from the Mac, so a laptop that sleeps or travels opens no
port and needs no firewall rule: it queues what it measures and delivers it
once it reaches the gateway again, up to Mimir's one-week limit. A Mac that
sleeps or is off the LAN shows a gap, never an alert: the cluster's rules alert
on what a Mac reports, never on its absence.

| Source | Job | What |
| --- | --- | --- |
| `node_exporter` | `mac-node` | CPU (`node_cpu_seconds_total`), load, memory (`node_memory_*`), disk I/O (`node_disk_*`), network on `en*` interfaces (`node_network_*_total`), the internal disk's root filesystem, boot time, the textfiles below |
| `macmon serve` | `macmon` | Power by rail in watts (`macmon_{cpu,gpu,ane,ram,gpu_ram,chip,sys,dcs,dc_in}_power_watts`), CPU and GPU temperature (`macmon_{cpu,gpu}_temp_celsius`), fan speed (`macmon_fan_speed_rpm`), memory pressure (`macmon_memory_pressure_level`: 0 normal, 1 warning, 2 critical; `_pressure_percent`), RAM and swap (`macmon_memory_{ram,swap}_{total,used}_bytes`), usage ratios and GPU frequency |
| `host-metrics collect` | `mac-node` | `macos_thermal_pressure_level` (0 nominal, 1 moderate, 2 heavy, 3 trapping, 4 sleeping); the battery's `macos_battery_*`; each physical disk's SMART data as `smartctl_device_*` |

Every series carries `host_name` (`studio`, `mbp`, `mini`, from the Mac's
enrollment), which the gateway promotes from the `host.name` the collector
stamps. `instance` is `127.0.0.1:<port>` on every Mac, so it identifies
nothing; select by `host_name`.

The SMART series are smartctl_exporter 0.15.0's (`metrics.go`, `smartctl.go`):
the same names, labels and help, read with the same `smartctl` arguments and
computed the same way, so queries and rules written for the exporter apply,
and switching to it (below) changes nothing that reads them.

| Metric | Labels besides `device` | Value |
| --- | --- | --- |
| `smartctl_device` | `interface`, `protocol`, `model_family`, `model_name`, `serial_number`, `ata_additional_product_id`, `firmware_version`, `ata_version`, `sata_version`, `form_factor`, `scsi_vendor`, `scsi_product`, `scsi_revision`, `scsi_version` | 1; `model_family`, `ata_additional_product_id` and an empty `model_name` read `unknown`, as upstream |
| `smartctl_device_smartctl_exit_status` | | smartctl's exit status, for every disk, read or not (below) |
| `smartctl_device_capacity_bytes` | | `user_capacity.bytes`, else the NVMe controller's `nvme_total_capacity`, else diskutil's size: smartctl reports no `user_capacity` on macOS, where upstream would export 0 |
| `smartctl_device_nvme_capacity_bytes` | | `nvme_total_capacity` |
| `smartctl_device_capacity_blocks`, `smartctl_device_block_size` | `blocks_type` (`logical`, `physical`) for the block size | When smartctl reports them; it does not on macOS |
| `smartctl_device_power_on_seconds` | | Power-on hours and minutes, in seconds |
| `smartctl_device_temperature` | `temperature_type`: `current`, and the drive's `op_limit_max` and `critical_limit_max` where it states them | °C |
| `smartctl_device_power_cycle_count` | | Power cycles |
| `smartctl_device_smart_status` | | 1 passed, 0 failed |
| `smartctl_device_percentage_used`, `_available_spare`, `_available_spare_threshold`, `_critical_warning`, `_media_errors`, `_num_err_log_entries` | | NVMe SMART / Health Information log fields |
| `smartctl_device_bytes_read`, `smartctl_device_bytes_written` | | NVMe data units × 512,000 bytes; left out while the drive reports 0 |
| `smartctl_devices` | none | Physical disks found |
| `smartctl_version` | `json_format_version`, `smartctl_version`, `svn_revision`, `build_info`, no `device` | 1 |

Where upstream exports a value smartctl did not report as 0, `collect` leaves
it out. Upstream declares `percentage_used`, `available_spare`,
`available_spare_threshold` and `critical_warning` counters although they are
levels; `collect` declares them gauges, because the collector reads a counter
that falls as a reset. PromQL reads either the same. The ATA and SCSI families
(`smartctl_device_attribute`, `_statistics`, `_error_log_count`, the SCSI error
counters and so on) are not produced: every disk on these Macs is NVMe, and a
SATA disk behind a USB bridge gets the device-level series only.

`device` is the BSD name (`disk0`), which can change when a drive is
reconnected: join on `serial_number` to follow a drive.

Every physical disk gets `smartctl_device_smartctl_exit_status`, so a disk that
stops answering shows instead of vanishing. Its bits are smartctl's:

| Bit | Value | Meaning | Data kept |
| --- | --- | --- | --- |
| 0 | 1 | Command line refused, as for a device type smartctl cannot drive | No |
| 1 | 2 | Device did not open or answer, or is in standby (`--nocheck=standby` does not wake it). A read past `host_metrics.smartctl_timeout`, or output that is not JSON, is reported as this bit too | No |
| 2 | 4 | A SMART command failed. Apple's internal SSD always sets it: it has no NVMe error-information log page | Yes |
| 3 to 7 | 8 to 128 | The disk's own findings: SMART says failing, prefail attributes at threshold, past threshold, errors logged, self-test errors | Yes |

A disk with bit 0 or 1 set has only its exit status that run; the others keep
all their series.

The battery series, written only when the Mac has a battery:

| Metric | From `AppleSmartBattery` | Meaning |
| --- | --- | --- |
| `macos_battery_cycle_count` | `CycleCount` | Charge cycles completed |
| `macos_battery_design_cycle_count` | `DesignCycleCount9C` | Cycles the battery is rated for |
| `macos_battery_design_capacity_ampere_hours` | `DesignCapacity` | Capacity as designed |
| `macos_battery_nominal_capacity_ampere_hours` | `NominalChargeCapacity` | Full-charge capacity. System Settings' Battery Health "Maximum Capacity" is this over the design capacity, so health is `nominal / design` |
| `macos_battery_max_capacity_ampere_hours` | `AppleRawMaxCapacity` | The fuel gauge's raw full-charge reading, which moves with temperature and charge history |

macOS 27 keeps the capacities under the entry's `BatteryData`; earlier releases
at its top level. `collect` reads either.

## Config

The feature's settings, set per Mac in `~/.config/dotfiles/machine.toml`
`[settings]` or in a profile; `dotfiles apply` exports them to
`~/.config/dotfiles/generated/env.sh`, which `bin/host-metrics` reads. An
environment variable of the same name wins.

| Setting | Environment | Type | Default | Description |
| --- | --- | --- | --- | --- |
| `host_metrics.node_exporter_port` | `HOST_METRICS_NODE_EXPORTER_PORT` | Port, 1024 to 65535 | `9100` | Where `node_exporter` listens, on 127.0.0.1 only. Change it where something else holds the port; apply restarts the exporter and the collector follows (no collector change). |
| `host_metrics.macmon_port` | `HOST_METRICS_MACMON_PORT` | Port, 1024 to 65535 | `9101` | Where `macmon serve` listens, on 127.0.0.1 only; as above. |
| `host_metrics.smart_interval` | `HOST_METRICS_SMART_INTERVAL` | Seconds, 60 to 86400 | `300` | How often `collect` reads each physical disk's SMART data. Wear and write counters move slowly; a disk in standby is skipped, not woken. |
| `host_metrics.smartctl_timeout` | `HOST_METRICS_SMARTCTL_TIMEOUT` | Seconds, 1 to 300 | `60` | How long one disk's `smartctl` read may take before it is ended and the disk reported as not answering (exit status 2). A read takes well under a second. |
| | `HOST_METRICS_STATE` | Directory path | `~/.local/state/host-metrics` | Targets and textfiles. Tests only: the collector's fragment names the default path. |

Fixed in the code, each for the reason given:

| Value | Where | Setting | Why |
| --- | --- | --- | --- |
| Scrape every 60 s, 20 s timeout | `conf.d/host-metrics.yaml` | `global` | Hardware moves on the scale of minutes; a finer interval multiplies the queue and Mimir's series samples. |
| `collect` every 60 s | `com.ashtonian.host-metrics.plist` | `StartInterval` | Matches the scrape. |
| macmon samples once a minute | `bin/host-metrics macmon` | `--interval 60000` | Power and usage are then averages over the minute the scrape reports, not one second of it. |
| Filesystems: `/` only | `bin/host-metrics node-exporter` | `--collector.filesystem.mount-points-include='^/$'` | See [external volumes](#operations). |
| Network: `en*` interfaces | `bin/host-metrics node-exporter` | `--collector.netdev.device-include='^en[0-9]+$'` | Ethernet and Wi-Fi; tunnels, bridges and Thunderbolt bridges add series no panel reads. |
| No `thermal` collector | `bin/host-metrics node-exporter` | `--no-collector.thermal` | Its 50-odd raw sensor series add nothing macmon's CPU and GPU temperatures and the thermal pressure level do not already give. |
| Series dropped | `conf.d/host-metrics.yaml` | `metric_relabel_configs` | `node_scrape_collector_duration_seconds`, multicast, collision and no-protocol counters; macmon keeps only the families in the table above (`macmon_all_power_watts` duplicates `chip`). |
| `smartctl` arguments | `bin/host-metrics` `smart_device` | `--json --info --health --attributes --capabilities --tolerance=verypermissive --nocheck=standby --format=brief --log=error` | smartctl_exporter 0.15.0's (`readjson.go`), so the JSON, and every value computed from it, match what the exporter would read. |
| Queue: 320 MiB of serialized data | `config.yaml` `otlp_http/host` | `queue_size` | About 290 points a minute at about 84 bytes each queued, 35 MB a day: about 9.5 days at studio's rate, past Mimir's one-week limit with room for more disks. |

About 290 samples a minute per Mac reach Mimir, measured on studio with three
disks: 254 from `node_exporter` and the textfiles (70 network, 53 SMART, 48
CPU, 36 disk I/O, the rest memory, load, filesystem and system info), 24 from
macmon, and 5 scrape series per job. A disk adds 15 to 18 SMART series; a
laptop adds 5 battery series.

## External Dependencies

| Dependency | Version | Source | Used for |
| --- | --- | --- | --- |
| `node_exporter` | 1.13.1 (latest) | Homebrew formula | System metrics and the textfile collector |
| `macmon` | 0.12.1 (latest) | Homebrew formula, Apple silicon only | Power, temperatures, fans, memory pressure |
| `smartmontools` | 7.5 (latest) | Homebrew formula | `smartctl --json` for each disk's SMART data |
| `jq` | 1.7.1 in macOS (`/usr/bin/jq`); Homebrew's 1.8.2 comes first on the jobs' PATH where `brew.base` installed it | base system | Turns smartctl's JSON into samples in one pass per disk; both versions give the same output |
| `otelcol-contrib` | as pinned in `bin/otel-agent` | the `agents.otel-agent` feature | Scrapes the exporters and forwards to the gateway |
| `notifyutil`, `ioreg`, `diskutil`, `plutil`, `lsof`, `sysctl`, `launchctl` | base system | macOS | Thermal pressure, battery, disk list, parsing, port checks, job control |

The cluster side lives in the infrastructure repository, which is private: the
gateway (`k8s/monitoring/otel-gateway`) stores the samples in Mimir, Mimir's
ruler evaluates the Macs' SSD and battery alerts, and the **Macs** Grafana
dashboard (Infrastructure) shows them.

### Why not smartctl_exporter, and when to switch to it

smartctl_exporter 0.15.0 drops Apple's internal SSD, the one disk every Mac
has. It asks smartctl for the error-information log (`--log=error`,
`readjson.go`), which Apple's SSD does not have; smartctl answers with an
error message and exit bit 2, and the exporter discards any reply that carries
an error message (`jsonIsOk`). The report,
[prometheus-community/smartctl_exporter#152](https://github.com/prometheus-community/smartctl_exporter/issues/152),
was closed without a fix;
[#412](https://github.com/prometheus-community/smartctl_exporter/pull/412)
keeps a reply that has a SMART status despite such a message, and is open.

Switch to smartctl_exporter once a release contains #412 or another fix that
keeps Apple's SSD. Before switching, check on one Mac that the release exports
`smartctl_device` for the internal SSD, and run it with
`--web.listen-address=127.0.0.1:<port>` and one `--smartctl.device=/dev/diskN`
per disk: its own scan names macOS disks by IOService path, which would change
the `device` label. Add it to the collector's fragment as a scrape job
relabelled to `job="mac-node"`, which the cluster's rules select, and remove
`collect_smart`. What changes for readers:
`smartctl_device_capacity_bytes` reads 0 on macOS (no `user_capacity`), the
four NVMe levels above become counters, and values smartctl leaves out are
exported as 0. A disk the exporter was not given at start, such as a drive
attached later, is not read until it restarts.

## API / Interfaces

```sh
~/.dotfiles/bin/host-metrics status          # the three jobs, each published target and its sample count, each textfile's age
~/.dotfiles/bin/host-metrics collect         # write the textfiles now (what com.ashtonian.host-metrics runs)
~/.dotfiles/bin/host-metrics check           # the feature's check: {"state": ..., "detail": ...}
~/.dotfiles/bin/host-metrics converge        # the feature's apply hook
~/.dotfiles/bin/host-metrics node-exporter   # com.ashtonian.node-exporter's entry point
~/.dotfiles/bin/host-metrics macmon          # com.ashtonian.macmon's entry point
```

Each exporter's entry point refuses to start while another process listens on
its port, and otherwise publishes `127.0.0.1:<port>` as a Prometheus file
service-discovery list, `~/.local/state/host-metrics/targets/<name>.json`,
before it execs the exporter. The collector's fragment watches those files, so
the port setting is the one place a port is named: the collector scrapes
whatever address the running exporter published, and a list that does not
exist (an exporter not installed, or refused) is no target and no error.

`collect` writes `thermal.prom`, `battery.prom` and `smart.prom` under
`~/.local/state/host-metrics/textfile`, each by a rename, so `node_exporter`
never serves half a file. A reading that fails removes its file rather than
leave a stale value.

Exit statuses: 64 usage; 69 a program is not installed; 75 the port is taken;
78 a setting is invalid, or `macmon` on an Intel Mac; 1 from `collect` when any
reading failed (the others are still written).

`check` reports `drift` when the target directory is missing (the collector
logs an error on every refresh while it is) or when a running exporter listens
on a port its setting no longer names. `converge` creates the directory and
restarts each moved exporter's job (`launchctl kickstart -k`); a job that is not
loaded is not running, so its stale target is removed instead.

The collector reads the feature's fragment,
`~/.config/otel-agent/conf.d/host-metrics.yaml`, after its own `config.yaml`
([AGENT-TELEMETRY.md](AGENT-TELEMETRY.md#config)). It adds the
`prometheus/host` receiver and a `metrics/host` pipeline that sends through
`config.yaml`'s `otlp_http/host` exporter. Without the fragment that exporter is
in no pipeline, so the collector never starts it and creates no queue file for
it.

## Build / Run / Test

The feature is off by default. It sends to one context's cluster, so that
context's overlay profile turns it on, for the Macs that send there:

```toml
# profiles/<overlay>.toml
[features]
enable = ["macos.host-metrics"]
```

It requires `agents.otel-agent`, which it turns on too. `dotfiles apply`
installs the three formulae, links the fragment, creates the target
directory, and installs the LaunchAgents once the programs exist and the Mac
is enrolled with otel-agent (`~/.local/share/otel-agent/host`). `dotfiles
doctor` lists a job that waits. A Mac that is not enrolled sends nothing: its
jobs never install. The overlay must name the feature only once this checkout
has it: a profile that enables an unknown feature fails `dotfiles check`, and
with it every sync.

The running collector reads the fragment at its next restart, which the next
sync's `otel-agent converge` does when it sees the config files changed (the
fragment is part of its fingerprint). To start sending at once:

```sh
dotfiles apply && ~/.dotfiles/sync.sh otel-agent
~/.dotfiles/bin/host-metrics status
~/.dotfiles/bin/otel-agent status   # fragments: host-metrics.yaml; queue otlp_http/host near 0 MiB
```

Within two minutes, Grafana → Infrastructure → Macs shows the Mac, or in
Explore: `up{job=~"mac-node|macmon", host_name="<host>"}`.

Tests:

```sh
python3 -m unittest tests.test_dotfiles.HostMetrics tests.test_dotfiles.OtelAgent
python3 -m unittest tests.test_dotfiles.RealFeatures.test_hardware_metrics_are_an_overlays_choice_and_wait_for_enrollment
```

`HostMetrics` runs `bin/host-metrics` against stand-ins for the exporters and
for `notifyutil`, `ioreg`, `diskutil`, `smartctl`, `lsof` and `launchctl`, and
reads the plists it writes with the real `plutil` and `jq`. The smartctl
stand-in replays JSON captured from three drives (Apple's AP0512Z, a Samsung
9100 PRO and a WD_BLACK SN7100, serial numbers replaced) in
`tests/fixtures/smartctl`, and the tests derive what smartctl_exporter would
export from those files. To add a drive, capture it with the arguments in the
config table and replace `serial_number`. To validate the merged
collector config, run the validation in
[AGENT-TELEMETRY.md](AGENT-TELEMETRY.md#build--run--test) with a second
`--config=features/macos.host-metrics/home/.config/otel-agent/conf.d/host-metrics.yaml`.

## Operations

- **Health:** `host-metrics status`: `com.ashtonian.node-exporter` and
  `com.ashtonian.macmon` running, both targets answering with a sample count,
  `thermal.prom` under 2 minutes old and `smart.prom` under
  `HOST_METRICS_SMART_INTERVAL` plus a minute. `otel-agent status` shows the
  `otlp_http/host` queue near 0 MiB while the gateway is reachable.
- **Logs:** `~/Library/Logs/host-metrics/{node-exporter,macmon,collect}.{log,err}`,
  capped daily by `bin/disk-hygiene` with the other LaunchAgent logs. The
  collector's scrape errors are in otel-agent's log.
- **Cost:** `collect` takes under a second with three disks; it runs at low
  I/O priority and nice 10. Each exporter holds about 20 MB resident.
- **Queue:** up to 320 MiB of serialized data, about 420 MiB on disk in
  `~/.local/state/otel-agent/queue/exporter_otlp_http_host_metrics` when full.
  Compaction returns the space once a backlog drains.
- **External volumes.** `node_exporter` reports only `/`. For every volume its
  filesystem collector reports, it asks the volume for its purgeable space by
  path, which on an external drive needs macOS's removable-volume permission,
  asked once per `node_exporter` build (every `brew upgrade`). An unanswered
  prompt holds every later removable-volume access behind it, sync's included
  (see [OPERATIONS.md](OPERATIONS.md#launchagents)). External drives' SMART
  health still arrives, through `smartctl`, which needs no such permission.

**Failure modes:**

- *A target shows `no target published`, and its job's `.err` log says `port
  <n> is taken by <process>`.* Another program listens on the port. Set another
  in `machine.toml` (`[settings] "host_metrics.node_exporter_port" = 9200`) and
  run `dotfiles apply`. launchd retries the job every minute until then, one log
  line each time.
- *`.err` says `HOST_METRICS_..._PORT='': want a whole number`.* `env.sh` lacks
  the setting: run `dotfiles apply`.
- *`not answering`, job running.* The exporter is starting or hung: `launchctl
  kickstart -k gui/$(id -u)/com.ashtonian.<name>`, then read its `.err` log.
- *A disk has only `smartctl_device_smartctl_exit_status`, and `collect.err`
  says `smartctl read nothing from diskN (exit 2)`.* The disk was in standby
  (`--nocheck=standby` does not wake it) or would not open; the next interval
  tries again. Exit 1 means smartctl cannot drive the device type (a USB
  bridge without SAT pass-through): that drive reports no SMART data on a Mac.
- *`collect.err` says `smartctl did not finish reading diskN within 60s`, or
  `smartctl left no JSON for diskN`.* The disk hung or smartctl failed; it is
  reported with bit 1 set. Run `smartctl --json --info --health /dev/diskN`
  by hand; a drive that hangs there needs reconnecting.
- *`smartctl_device_smartctl_exit_status` is 4 for Apple's SSD.* Normal: the
  missing error-information log page (bit 2). Bits 3 and up are the disk's own
  findings; the cluster's rules alert on the health values themselves.
- *No `battery.prom` on a laptop.* `ioreg -rn AppleSmartBattery -a` lacks
  `BatteryInstalled = true`; desktop Macs have a placeholder entry with it
  false, so the file is absent there by design.
- *`collect.err` says `unexpected thermal pressure reading`.* `notifyutil -g
  com.apple.system.thermalpressurelevel` printed something other than a level;
  `thermal.prom` is absent until it reads again.
- *Nothing in Mimir, `host-metrics status` healthy.* The collector has not read
  the fragment: `otel-agent status` lists `fragments:`; if it is missing, run
  `~/.dotfiles/sync.sh otel-agent`. If the fragment is listed, follow the
  collector's failure modes in [AGENT-TELEMETRY.md](AGENT-TELEMETRY.md#operations).
- *otel-agent's log repeats `Error adding file watch` for the target
  directory.* The feature was turned off by `dotfiles apply` and the collector
  still runs the old config; the next sync restarts it, or run
  `~/.dotfiles/sync.sh otel-agent`. With the feature on, `dotfiles apply`
  creates the directory.
- *An Intel Mac.* Unsupported: `macmon` is Apple silicon only, so Homebrew
  refuses the formula. Turn the feature off there.

Turning the feature off removes the fragment, the LaunchAgents, the targets,
textfiles and logs; the formulae stay (`dotfiles prune --packages` removes
them).

## Security

- Both exporters listen on 127.0.0.1 only, at a port the entry point checks is
  free, so nothing on the LAN can read them and the collector never scrapes
  another program in their place. No new Local Network grant is needed: the
  collector already reaches the gateway.
- What leaves the Mac goes through otel-agent's authenticated, per-host
  connection; this feature adds no credential.
- The data is hardware state: the disks' model, serial and firmware numbers,
  power, temperatures and use, plus `node_uname_info` and `node_os_info`,
  which carry the Mac's host name, DNS domain and macOS build. No file,
  volume, user or process names are collected: only `/` is reported among
  filesystems, and `node_exporter` has no process collector on macOS.
- Every job runs as the user and nothing needs root. `smartctl` asks the
  disks' IOKit SMART interface and reads none of their data; no job is
  expected to need a privacy (TCC) grant, which the first run under launchd on
  each Mac confirms (`log show --last 1h --predicate 'subsystem ==
  "com.apple.TCC"' | grep -i prompting`).

## Code Map

| File | Purpose |
| --- | --- |
| [bin/host-metrics](../bin/host-metrics) | The exporters' entry points, the textfile writer, status, and the feature's check and apply hook |
| [features/macos.host-metrics/feature.toml](../features/macos.host-metrics/feature.toml) | Formulae, the fragment link, the LaunchAgents, settings and hooks |
| [features/macos.host-metrics/home/.config/otel-agent/conf.d/host-metrics.yaml](../features/macos.host-metrics/home/.config/otel-agent/conf.d/host-metrics.yaml) | The collector's scrape jobs and pipeline |
| [features/macos.host-metrics/launchagents/](../features/macos.host-metrics/launchagents/) | `com.ashtonian.node-exporter`, `com.ashtonian.macmon` (services), `com.ashtonian.host-metrics` (every 60 s) |
| [features/macos.host-metrics/hooks/](../features/macos.host-metrics/hooks/) | `check`, `apply` and `teardown` |
| [features/agents.otel-agent/home/.config/otel-agent/config.yaml](../features/agents.otel-agent/home/.config/otel-agent/config.yaml) | `otlp_http/host`, the exporter and queue the fragment sends through |
| [bin/otel-agent](../bin/otel-agent) | Passes each `conf.d` fragment to the collector and restarts it when the set changes |
| [tests/test_dotfiles.py](../tests/test_dotfiles.py) | `HostMetrics`, `OtelAgent`, and the feature through the real engine in `RealFeatures` |
| [tests/fixtures/smartctl/](../tests/fixtures/smartctl/) | smartctl's JSON for three drives, as the `HostMetrics` tests replay it |
