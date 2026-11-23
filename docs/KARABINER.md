# Mouse buttons (tool.karabiner)

## Overview

The only custom mapping Logitech G HUB held was the G502 X PLUS's G5 side button opening
Mission Control. G HUB is no longer in the Brewfile; feature `tool.karabiner` installs
Karabiner-Elements and a `karabiner.json` that makes that one button do the same, and
otherwise leaves input as macOS delivers it without Karabiner.

`~/.config/karabiner/karabiner.json` holds one profile:

| Part | What it does | Why |
|---|---|---|
| `devices`: the G502 X PLUS on its cable (vendor 1133, product 49310) and its LIGHTSPEED receiver (1133, 50503), each `"ignore": false` | Karabiner modifies these two pointing devices | Karabiner leaves every pointing device alone by default. Listing the two keeps trackpads and other mice untouched, unlike the profile-wide `ignore_pointing_device_events_by_default` |
| Rule "G502 X PLUS: G5 (button 5) opens Mission Control" | `pointing_button` `button5` from those two devices, with any modifiers, sends `mission_control` | The G HUB mapping |
| Rule "Non-Apple keyboards keep standard F1-F12, as without Karabiner" | F1 to F12 from any keyboard that is not Apple's (vendor 1452 or 76, or built in) send F1 to F12 | Karabiner modifies every keyboard (16.3.0 has no setting to leave keyboards alone). While **Use F1, F2, etc. keys as standard function keys** is off, it turns F1 to F12 into the media keys on all of them. Without Karabiner a non-Apple keyboard, such as the UHK, sends plain F-keys. Karabiner applies its function-key step after the rules and skips keys a rule changed, so this rule keeps them plain. Apple keyboards keep the media-key row |
| `virtual_hid_keyboard.keyboard_type_v2` = `ansi` | Layout of Karabiner's virtual keyboard | macOS records type 40 (ANSI) for every keyboard on the Studio; set so Karabiner does not ask on first start |

G5 sending `button5` is inferred, not measured. G HUB assigns G4 its built-in "mouse button 4"
card, which leaves G5 as button 5 (forward). The setup below confirms it with
Karabiner-EventViewer.

Why a managed copy of `karabiner.json` and not a rule file in
`~/.config/karabiner/assets/complex_modifications/`: an asset does nothing until someone turns
the rule on in **Settings > Complex Modifications** and the mouse on in **Settings >
Devices**, by hand, on each Mac, and both choices are then saved to `karabiner.json` anyway.
The copy installs the whole configuration. Karabiner saves `karabiner.json` by writing
`karabiner.json.tmp` and renaming it over the original, which would replace a link with a
plain file at the first save, so the feature installs a copy (`copy`), not a link. A change
made in Karabiner's settings then shows as drift.

## Config

All of it is `karabiner.json`; the feature has no settings. Keys the file sets:

| Key | Type | Value | Description |
|---|---|---|---|
| `profiles[0].name` / `selected` | string / bool | `Default profile` / `true` | The one profile |
| `profiles[0].devices[].identifiers` | object | `vendor_id`, `product_id`, `is_pointing_device: true` | Must equal what Karabiner reports for the device (**Settings > Devices**, or EventViewer's **Devices** tab) |
| `profiles[0].devices[].ignore` | bool | `false` | Modify the device |
| `profiles[0].complex_modifications.rules` | array | the two rules above | `device_if` / `device_unless` conditions name the devices by vendor and product id |
| `profiles[0].virtual_hid_keyboard.keyboard_type_v2` | string | `ansi` | `ansi`, `iso` or `jis` |

Every other key takes Karabiner's default. The feature is in the `desktop` profile, macOS
only (`platforms = ["darwin"]`).

## External Dependencies

- Karabiner-Elements 16.3.0 or later (cask `karabiner-elements`). Its installer is a `.pkg`,
  so it needs a password once; it updates itself afterwards (the cask is `auto_updates`, so
  `brew upgrade` leaves it alone).
- Its DriverKit virtual keyboard and mouse: a driver extension macOS asks to approve, and
  Input Monitoring for Karabiner's background services.
- Logitech G HUB not running. While it runs it handles the G buttons itself and competes for
  the mouse.

## API / Interfaces

- `~/.config/karabiner/karabiner.json`: the managed copy. Karabiner reloads it when it changes,
  so `dotfiles apply` takes effect without a restart.
- `karabiner_cli` (on PATH from the cask), for example `karabiner_cli --show-current-profile-name`.
- Karabiner-EventViewer (in `/Applications`): shows each input event, with the device it came
  from in the **Devices** tab.

## Build / Run / Test

Once per Mac, after `dotfiles apply`:

1. `brew install --cask karabiner-elements` in a terminal. The background sync cannot enter a
   password for the `.pkg`; later syncs find it installed.
2. Open Karabiner-Elements and follow its setup windows: approve its driver extension in
   **System Settings > General > Login Items & Extensions**, and allow the Karabiner services
   they name in **Privacy & Security > Input Monitoring**.
3. On the Mac with the G502: quit and uninstall G HUB (`brew uninstall --cask
   logitech-g-hub`), then unplug and replug the mouse's cable and receiver.
4. Press G5: Mission Control opens. If it does not, open Karabiner-EventViewer and press G5. It
   shows the button the mouse sends (for example `{"pointing_button":"button4"}`); put that
   name in the rule in
   [karabiner.json](../features/tool.karabiner/home/.config/karabiner/karabiner.json) and run
   `dotfiles apply`.
5. With EventViewer open, F1 on a non-Apple keyboard shows `{"key_code":"f1"}`; F1 on an
   Apple keyboard still changes the display brightness.

Tests: `python3 -B -m unittest tests.test_dotfiles.Karabiner -v`. They check that the
configuration parses, that the mouse rule names only devices Karabiner is told to modify,
and that the F-key rule passes F1 to F12 through unchanged.

## Operations

- **Updates.** Sync updates the managed copy and Karabiner reloads it. Karabiner updates
  itself.
- **Health.** The Karabiner menu bar icon; **Settings > Log** shows errors, including a
  `karabiner.json` it could not load. Karabiner keeps earlier versions of the file in
  `~/.config/karabiner/automatic_backups/` each time it saves.

Troubleshooting:

| Symptom | Check | Fix |
|---|---|---|
| G5 does nothing | EventViewer shows nothing for G5 | G HUB still running, or the mouse not modified: **Settings > Devices** should show the G502 X PLUS with **Modify events** on. If the product id there differs (another receiver), add it to `devices` and to the rule's `device_if` |
| G5 goes back or forward in a browser | EventViewer shows a button other than `button5` | Put that button in the rule (step 4) |
| Sync log: `Installing karabiner-elements has failed!` with `sudo: a password is required` | The `.pkg` needs root | Step 1, once |
| `dotfiles apply` reports `edited here since dotfiles last wrote it` for `karabiner.json` | A change was made in Karabiner's settings | `dotfiles adopt ~/.config/karabiner/karabiner.json` to keep it, or delete the file and `dotfiles apply` |
| `dotfiles apply` reports `karabiner.json` in the way | Karabiner wrote one before dotfiles did | Compare, move it aside, `dotfiles apply` ([A file is in the way](../README.md#a-file-is-in-the-way)) |
| F-keys on an external keyboard became media keys | Does EventViewer's **Devices** tab show vendor 1452 or 76 for it? | It reports itself as Apple's; add a rule for its product id, or press fn with the key |

## Security

- Karabiner's input services see every keystroke and pointer event (that is what Input
  Monitoring grants), and its driver posts input. It is open source (Unlicense, pqrs-org),
  signed and notarized.
- `karabiner.json` holds no credentials.

## Code Map

| Path | Purpose |
|---|---|
| [features/tool.karabiner/feature.toml](../features/tool.karabiner/feature.toml) | Feature: the cask, and `karabiner.json` as a managed copy |
| [features/tool.karabiner/home/.config/karabiner/karabiner.json](../features/tool.karabiner/home/.config/karabiner/karabiner.json) | The profile: devices, the two rules, keyboard type |
| [features/backup.mackup.config/home/.mackup.cfg](../features/backup.mackup.config/home/.mackup.cfg) | Keeps a manual Mackup run away from `~/.config/karabiner` |
| [tests/test_dotfiles.py](../tests/test_dotfiles.py) (`Karabiner`) | Configuration consistency |
