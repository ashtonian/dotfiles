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

The SMART series use smartctl_exporter's names and labels, so queries and
rules written for it apply: `smartctl_device` (info: `device`, `interface`,
`protocol`, `model_name`, `serial_number`, `firmware_version`),
`smartctl_device_smartctl_exit_status`, `_smart_status` (1 passed, 0 failed),
`_temperature{temperature_type="current"}`, `_power_on_seconds`,
`_power_cycle_count`, `_capacity_bytes`, and for NVMe `_critical_warning`,
`_available_spare`, `_available_spare_threshold`, `_percentage_used`,
`_media_errors`, `_num_err_log_entries`, `_bytes_written`, `_bytes_read`.
`device` is the BSD name (`disk0`), which can change when a drive is
reconnected: join on `serial_number` to follow a drive.

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
| Queue: 320 MiB of serialized data | `config.yaml` `otlp_http/host` | `queue_size` | About 280 points a minute at about 84 bytes each queued, 34 MB a day: about 10 days at studio's rate, past Mimir's one-week limit with room for more disks. |

About 280 samples a minute per Mac reach Mimir, measured on studio with three
disks: 246 from `node_exporter` and the textfiles (70 network, 48 CPU, 45
SMART, 36 disk I/O, the rest memory, load, filesystem and system info), 24
from macmon, and 5 scrape series per job. Each disk adds 15 SMART series; a
laptop adds 5 battery series.

## External Dependencies

| Dependency | Version | Source | Used for |
| --- | --- | --- | --- |
| `node_exporter` | 1.13.1 (latest) | Homebrew formula | System metrics and the textfile collector |
| `macmon` | 0.12.1 (latest) | Homebrew formula, Apple silicon only | Power, temperatures, fans, memory pressure |
| `smartmontools` | 7.5 (latest) | Homebrew formula | `smartctl --json` for each disk's SMART data |
| `otelcol-contrib` | as pinned in `bin/otel-agent` | the `agents.otel-agent` feature | Scrapes the exporters and forwards to the gateway |
| `notifyutil`, `ioreg`, `diskutil`, `plutil`, `lsof`, `sysctl`, `launchctl` | base system | macOS | Thermal pressure, battery, disk list, parsing, port checks, job control |

The cluster side lives in the infrastructure repository, which is private: the
gateway (`k8s/monitoring/otel-gateway`) stores the samples in Mimir, Mimir's
ruler evaluates the Macs' SSD and battery alerts, and the **Macs** Grafana
dashboard (Infrastructure) shows them.

smartctl_exporter is not used. Its 0.15.0 release reads every device with
`smartctl --json`, and treats any smartctl error bit as a failed read: Apple's
internal SSD has no NVMe error-information log page, which smartctl reports
with exit status 4, so the exporter drops the one disk that matters most
(prometheus-community/smartctl_exporter#152, closed; #412 proposes a fix).
`collect` reads the same JSON, keeps a device whose only error is that one
(bit 2), and writes the exporter's names.

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

The `desktop` profile enables the feature, and it requires `agents.otel-agent`.
`dotfiles apply` installs the three formulae, links the fragment, creates the
target directory, and installs the LaunchAgents once the programs exist and
the Mac is enrolled with otel-agent (`~/.local/share/otel-agent/host`).
`dotfiles doctor` lists a job that waits.

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
python3 -m unittest tests.test_dotfiles.RealFeatures.test_a_desktop_mac_sends_hardware_metrics_once_enrolled_and_cleans_up_when_off
```

`HostMetrics` runs `bin/host-metrics` against stand-ins for the exporters and
for `notifyutil`, `ioreg`, `diskutil`, `smartctl`, `lsof` and `launchctl`, and
reads the plists it writes with the real `plutil`. To validate the merged
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
- *`smart.prom` lacks a disk, and `collect.err` says `smartctl read nothing from
  diskN (exit 2)`.* The disk was in standby (`--nocheck=standby` does not wake
  it) or would not open; the next interval tries again. Exit 1 means smartctl
  does not know the device type (a USB bridge without SAT pass-through): that
  drive reports no SMART data on a Mac.
- *`smartctl_device_smartctl_exit_status` is 4 for Apple's SSD.* Normal: the
  missing error-information log page. Bits 3 and up are the disk's own
  findings (3 failing, 4 prefail attributes, 6 errors logged, 7 self-test
  errors); the cluster's rules alert on the health values themselves.
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
| [tests/test_dotfiles.py](../tests/test_dotfiles.py) | `HostMetrics`, `OtelAgent`, and the desktop feature in `RealFeatures` |
