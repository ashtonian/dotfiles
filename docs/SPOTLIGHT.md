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

The tool makes the same CoreServices calls as that settings pane
(`_MDCopyExclusionList` and `_MDSetExclusion`). mds accepts them from the
logged-in user without root, stores the list in the volume's
`.Spotlight-V100/VolumeConfiguration.plist`, and stops serving and indexing
the excluded folders at once: their items drop out of search results within
seconds, no rebuild needed. Taking a folder off the list makes mds index it
again within seconds.

Spotlight already skips hidden folders (`~/.cache`, `~/.cargo`, `~/.claude`,
...) and `~/Library/Caches`, so the list names only visible folders. Whole
volumes are switched off with `mdutil` instead (see [Operations](#operations)).

`dotfiles apply` installs the tool but does not run it, because the engine has
no feature hooks (rollout steps 6 and 7 add `[hooks]` and `[check]`). Run
`spotlight-exclusions apply` after installing the feature and after editing
the list.

## Config

| Setting | Where | Default | Description |
| --- | --- | --- | --- |
| Exclusion list | `~/.config/spotlight/exclusions` ([tracked file](../features/macos.spotlight/home/.config/spotlight/exclusions)) | App Support, Logs, pnpm store, `~/sdk`, `~/go`, `/usr/local`, `/Library/Developer` | One absolute or `~` path per line; `#` starts a comment line. Folders absent on a machine are skipped |
| `SPOTLIGHT_EXCLUSIONS_FILE` | environment | `~/.config/spotlight/exclusions` | List to read instead |
| `SPOTLIGHT_EXCLUSIONS_COUNT_TIMEOUT` | environment | `60` | Seconds each `mdfind` may take under `check --counts` |

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
| `spotlight-exclusions check [--counts]` | One line per listed folder: `excluded`, `MISSING` or `absent`; `--counts` adds how many items the index still holds under it (slow on large trees) | 0, or 1 if a folder is `MISSING` |
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

The tests cover parsing the list and matching folders to exclusions; they never
change the real list.

## Operations

**Health:** `spotlight-exclusions check` exits 0. `check --counts` shows 0
under each excluded folder. `mdutil -as` shows which volumes are indexed.

**Measuring the index:** count with a content-type query, which only the index
answers:

```sh
mdfind -onlyin ~/Library -count 'kMDItemContentTypeTree == "public.item"'
```

A `kMDItemFSName` query falls back to a filesystem search and also counts
files the index does not hold, so it overstates what is indexed.

**Failure modes:**

- *`check` exits 1 after an earlier `apply`*: the folder was added to the list
  later, created after the last `apply`, or removed in System Settings. Run
  `spotlight-exclusions apply`.
- *`mds error N` from `apply` or `remove`*: mds refused the change. Run
  `log show --last 5m --predicate 'process == "mds"'` for the reason; adding
  the folder in System Settings → Spotlight → Search Privacy shows the same
  error in words.
- *`check --counts` still shows items under an excluded folder*: mds is
  catching up, which normally takes seconds; check again in a minute.
- *`symbol not found` or a crash after a macOS upgrade*: Apple changed the
  private functions. Add the folders by hand in System Settings, and compare
  the settings pane's imports with what the tool binds:
  `dyld_info -imports /System/Library/ExtensionKit/Extensions/SpotlightPreferenceExtension.appex/Contents/MacOS/SpotlightPreferenceExtension | grep _MD`.
- *A whole volume (external disk, disk image) should not be indexed*:
  `sudo mdutil -i off /Volumes/<name>`; exclusions are per folder.
- *An app stops finding something through Spotlight*: run
  `spotlight-exclusions list`, `remove` the folder it lives in, and delete
  its line from the exclusion list so the next `apply` does not exclude it
  again.

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
| [features/macos.spotlight/feature.toml](../features/macos.spotlight/feature.toml) | Feature manifest: links the list and the tool |
| [features/macos.spotlight/home/.config/spotlight/exclusions](../features/macos.spotlight/home/.config/spotlight/exclusions) | The folders to exclude, with reasons |
| [features/macos.spotlight/home/.local/bin/spotlight-exclusions](../features/macos.spotlight/home/.local/bin/spotlight-exclusions) | `apply`, `check`, `list`, `remove` |
| [tests/test_dotfiles.py](../tests/test_dotfiles.py) | `SpotlightExclusions` tests |
