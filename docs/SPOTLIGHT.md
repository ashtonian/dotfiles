# Spotlight exclusions

## Overview

Spotlight indexes every visible folder on the Data volume, including ones that
hold no documents: Electron caches and app databases under
`~/Library/Application Support`, the pnpm package store, Go toolchains, TeX Live
under `/usr/local` and the Command Line Tools SDKs. On a development Mac these
make up most of the index (over a million items against tens of thousands of
documents), and mds re-imports them whenever a toolchain or package store
changes.

Feature `macos.spotlight` (profile `base`, macOS only) installs:

- `~/.config/spotlight/exclusions`, the list of folders to keep out of the
  index, with the reason for each;
- `~/.local/bin/spotlight-exclusions`, which adds the listed folders to
  Spotlight's Search Privacy list, the list System Settings → Spotlight →
  Search Privacy shows and edits.

A machine's own folders, such as source checkouts and agent workspaces only
that machine has, go in `~/.config/spotlight/exclusions.local`. That file is
never tracked. The tool reads it after the shared list when it exists, so
`apply` and `check` cover both lists.

The tool makes the same CoreServices calls as that settings pane
(`_MDCopyExclusionList` and `_MDSetExclusion`). mds accepts them from the
logged-in user without root, stores the list in the volume's
`.Spotlight-V100/VolumeConfiguration.plist`, stops indexing the excluded
folders at once and purges their items from the index in the background, with
no rebuild. A query scoped to an excluded folder answers nothing right away,
but wider searches keep returning its items until the purge reaches them: on
the MacBook Pro (macOS 27.2.1), 1.6 million items under `~/workgroups` and
`~/projects` were gone about five minutes after `apply`. Taking a folder off
the list makes mds index it again within seconds.

Spotlight already skips hidden folders (`~/.cache`, `~/.cargo`, `~/.claude`,
...) and `~/Library/Caches`, so the list names only visible folders. Whole
volumes are switched off with `mdutil` instead (see [Operations](#operations)).

`dotfiles apply` installs the list and the tool, then runs the feature's check
(`spotlight-exclusions check --json`) and, while a listed folder that exists is
still indexed, its apply hook (`spotlight-exclusions apply`). So sync excludes a
folder added to either list, or one that appears later (a toolchain installed
since), on its next run, and `dotfiles doctor` reports `would hook
macos.spotlight -> drift: Spotlight indexes <folder>` until then. No sudo is
needed: mds takes the change from the logged-in user. Turning the feature off
leaves the folders excluded; `spotlight-exclusions remove` takes them off.

## Config

| Setting | Where | Default | Description |
| --- | --- | --- | --- |
| Exclusion list | `~/.config/spotlight/exclusions` ([tracked file](../features/macos.spotlight/home/.config/spotlight/exclusions)) | App Support, Logs, pnpm store, `~/sdk`, `~/go`, `/usr/local`, `/Library/Developer` | One absolute or `~` path per line; `#` starts a comment line. Folders absent on a machine are skipped |
| Local exclusion list | `~/.config/spotlight/exclusions.local` (untracked) | none | The machine's own folders, in the same format, read after the shared list. Optional: a missing file adds nothing |
| `SPOTLIGHT_EXCLUSIONS_FILE` | environment | `~/.config/spotlight/exclusions` | Shared list to read instead; the local list is the same path with `.local` appended |
| `SPOTLIGHT_EXCLUSIONS_COUNT_TIMEOUT` | environment | `60` | Seconds the `mdfind` for each listed folder's parent may take under `check --counts` |
| `SPOTLIGHT_EXCLUSIONS_STORE` | environment | unset: Spotlight's own list | A JSON list of paths used in place of Spotlight's exclusion list, read and written by every command; for tests, so a test convergence never changes this Mac's index |

## External Dependencies

| Dependency | Why |
| --- | --- |
| macOS CoreServices `_MDCopyExclusionList`, `_MDSetExclusion` | Read and change the Search Privacy list. Private functions; verified on macOS 27.2.1 |
| Python 3 (`/usr/bin/python3` from the Command Line Tools, which Homebrew requires, or Homebrew's) | Calls the functions through `ctypes`; runs on 3.9 and later |
| `mdfind` | Counts what the index still holds under `check --counts` |

## API / Interfaces

| Command | Does | Exit |
| --- | --- | --- |
| `spotlight-exclusions apply [--dry-run]` | Adds every listed folder that exists and is not excluded yet; `--dry-run` prints them | 0, or 3 if mds refused one |
| `spotlight-exclusions check [--counts]` | One line per listed folder: `excluded`, `MISSING` or `absent`; `--counts` adds how many items the index still holds under it, counted from one query per parent folder | 0, or 1 if a folder is `MISSING` |
| `spotlight-exclusions check --json` | The feature's check result for the engine: `{"state": "ok", ...}`, `drift` naming the first `MISSING` folder and how many more, or `error` with the config or mds error | 0 |
| `spotlight-exclusions list` | Prints Spotlight's whole exclusion list, including folders added in System Settings | 0 |
| `spotlight-exclusions remove PATH...` | Takes folders off the list; any spelling of the folder (symlink, `/System/Volumes/Data/...`) matches its entry | 0, 1 if a path was not excluded, 3 if mds refused |

A config error (relative path, a file where a folder belongs, bad timeout)
exits 2. `apply` only adds: a folder deleted from the list stays excluded until
`remove` takes it off, and exclusions added in System Settings are never
touched.

## Build / Run / Test

```sh
dotfiles apply                        # installs the list and the tool (feature macos.spotlight)
spotlight-exclusions apply --dry-run  # what would be added
spotlight-exclusions apply
spotlight-exclusions check --counts   # every listed folder excluded, 0 items indexed under it
python3 -B -m unittest tests.test_dotfiles.SpotlightExclusions -v
```

The tests cover parsing the list, matching folders to exclusions, and the
`check --json` and `apply` round trip against a `SPOTLIGHT_EXCLUSIONS_STORE`
file; they never change the real list.

## Operations

**Health:** `dotfiles doctor` reports nothing for `macos.spotlight`, and
`spotlight-exclusions check` exits 0. `check --counts` shows 0
under each excluded folder. `mdutil -as` shows which volumes are indexed.

**Measuring the index:** count with a content-type query, which only the index
answers:

```sh
mdfind -onlyin ~/Library -count 'kMDItemContentTypeTree == "public.item"'
```

A `kMDItemFSName` query falls back to a filesystem search and also counts
files the index does not hold, so it overstates what is indexed. A query
scoped to an excluded folder always counts 0, even while the index still holds
its items, so measure an excluded folder from its parent, as `check --counts`
does:

```sh
mdfind -onlyin ~ 'kMDItemContentTypeTree == "public.item"' | grep -c "^$HOME/projects/"
```

To find what fills the index, group a wide query by folder:

```sh
mdfind -onlyin ~ 'kMDItemContentTypeTree == "public.item"' | awk -F/ '{print $4}' | sort | uniq -c | sort -rn | head
```

**Failure modes:**

- *`check` exits 1 after an earlier `apply`*: the folder was added to the list
  later, created after the last `apply`, or removed in System Settings. Run
  `spotlight-exclusions apply`.
- *`mds error N` from `apply` or `remove`*: mds refused the change. Run
  `log show --last 5m --predicate 'process == "mds"'` for the reason; adding
  the folder in System Settings → Spotlight → Search Privacy shows the same
  error in words.
- *`check --counts` still shows items under an excluded folder*: mds is still
  purging it. A million items took about five minutes; check again later. A
  few hundred items inside bundles can stay much longer (Dash docsets under
  `Application Support`, a `.dSYM` in the Go module cache). They no longer
  change, so mds does no work for them, and only a full rebuild removes them:
  `sudo mdutil -E /`, which re-indexes the whole volume, honoring the
  exclusions.
- *`symbol not found` or a crash after a macOS upgrade*: Apple changed the
  private functions. Add the folders by hand in System Settings, and compare
  the settings pane's imports with what the tool binds:
  `dyld_info -imports /System/Library/ExtensionKit/Extensions/SpotlightPreferenceExtension.appex/Contents/MacOS/SpotlightPreferenceExtension | grep _MD`.
- *A whole volume (external disk, disk image) should not be indexed*:
  `sudo mdutil -i off /Volumes/<name>`; exclusions are per folder.
- *An app stops finding something through Spotlight*: run
  `spotlight-exclusions list`, `remove` the folder it lives in, and delete
  its line from whichever list names it (shared or `.local`), so the next
  `apply` does not exclude it again.
- *A source checkout or workspace fills the index* (`check --counts` or the
  measuring query above shows hundreds of thousands of items under it): add
  it to `~/.config/spotlight/exclusions.local` when only this machine has it,
  or to the shared list when every machine has it at the same path. Then run
  `spotlight-exclusions apply`.

## Security

- Runs as the logged-in user: no root, no network, and it writes no files;
  mds stores the list in its own configuration.
- An exclusion hides items from Spotlight search and from apps that query
  Spotlight (`mdfind`, `NSMetadataQuery`). It does not protect the files.
- The private functions are called in-process with the argument types System
  Settings uses: a path string and a flag, returning 0 or an error code.

## Code Map

| File | Purpose |
| --- | --- |
| [features/macos.spotlight/feature.toml](../features/macos.spotlight/feature.toml) | Feature manifest: links the list and the tool; its check and apply hooks |
| [features/macos.spotlight/hooks/](../features/macos.spotlight/hooks/) | `check` and `apply`: run the repository's copy of the tool, so they work before the link exists |
| [features/macos.spotlight/home/.config/spotlight/exclusions](../features/macos.spotlight/home/.config/spotlight/exclusions) | The folders to exclude, with reasons |
| [features/macos.spotlight/home/.local/bin/spotlight-exclusions](../features/macos.spotlight/home/.local/bin/spotlight-exclusions) | `apply`, `check`, `list`, `remove` |
| [tests/test_dotfiles.py](../tests/test_dotfiles.py) | `SpotlightExclusions` tests |
