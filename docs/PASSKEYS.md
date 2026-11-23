# Passkeys off (browser.passkeys-off)

## Overview

Websites push passkeys at every sign-in. They show "create a passkey" interstitials, run
automatic passkey upgrades after a password sign-in, and put passkey suggestions in the
username field. Each push can raise more than one prompt: the 1Password extension's own,
then the browser's passkey chooser (iCloud Keychain, the browser profile, a phone's QR code,
a security key), then the macOS passkey sheet. Passwords come from 1Password, so none of
these prompts is wanted.

No single setting turns them all off. Chromium (Brave, Chrome) has no policy for the
passkey chooser, the phone QR code, passkey autofill or automatic upgrades. Firefox has one
pref for the macOS passkey service. Safari has only a setting in the Passwords app. So
feature `browser.passkeys-off` works at each layer:

| Layer | What turns it off | How it is set |
|---|---|---|
| Websites in Brave and Chrome | The **Passkeys Off** extension: sites are told no passkey support exists, so they stop offering; creating a passkey is refused; the background request behind passkey autofill never completes | Managed copy at `~/.local/share/browser-extensions/passkeys-off`, loaded once per browser profile with "Load unpacked" |
| Firefox | `security.webauthn.enable_macos_passkeys = false` (no macOS passkey sheet, iCloud Keychain or phone QR code; USB security keys still work through Firefox's own handler) and `security.webauthn.enable_conditional_mediation = false` (no passkey suggestions in sign-in fields) | `passkeys-off apply` writes them to every profile's `user.js` |
| 1Password extension | "Offer to sign in with passkeys" and "Offer to save passkeys" off | By hand in each browser: 1Password > account menu > **Settings** > **Autofill & save** |
| Safari and apps | "Automatically Create Passkeys" off (stops websites and apps upgrading accounts to passkeys) | By hand: **Passwords** > **Settings** |

What still works: a sign-in the page explicitly asks for. The extension lets a modal
`navigator.credentials.get()` through, because that is how a security-key second factor
works, and refusing it could lock an account out. A site where a passkey is already the
account's sign-in method keeps asking for it. Remove the passkey from that account (and
from 1Password) to stop it.

Why an extension, and why a copy: sites read `PublicKeyCredential`'s capability checks
(`isUserVerifyingPlatformAuthenticatorAvailable`, `isConditionalMediationAvailable`,
`getClientCapabilities`) before offering a passkey. Only a script in the page's own world
(MV3 content script, `world: "MAIN"`, `document_start`, every frame) can answer them first.
Chromium silently skips an unpacked extension's content script when the extension's files
are symlinks (measured in Chrome for Testing 156), so the feature installs real files
(`copy`), not links.

## Config

| Setting | Type | Default | Description |
|---|---|---|---|
| `PASSKEYS_OFF_EXTENSION` | path | `~/.local/share/browser-extensions/passkeys-off` | Where the extension is installed; `check` looks for an unpacked extension loaded from here |
| `PASSKEYS_OFF_FIREFOX` | path | `~/Library/Application Support/Firefox` | Firefox's root; profiles come from its `profiles.ini` (relative and absolute paths) |
| `PASSKEYS_OFF_CHROMIUM` | colon-separated paths | `~/Library/Application Support/BraveSoftware/Brave-Browser:~/Library/Application Support/Google/Chrome` | Chromium user-data folders whose profiles `check` reports; missing folders are skipped |
| Firefox prefs | user.js block | both `false` | `security.webauthn.enable_macos_passkeys`, `security.webauthn.enable_conditional_mediation`; defined in `FIREFOX_PREFS` |

The feature is in the `desktop` profile. It is macOS-only (`platforms = ["darwin"]`).

## External Dependencies

- Brave or Chrome with Developer mode on in the extensions page (for "Load unpacked").
  `content_scripts[].world` needs Chromium 111 or later.
- Firefox, for the prefs. Firefox policies cannot set `security.*` prefs, so `user.js` is the
  only file-based route; Firefox reads it at every start.
- `python3` (stdlib only) for `passkeys-off`; `node` for the extension's test.

## API / Interfaces

```sh
passkeys-off apply [--dry-run]   # write the Firefox prefs to every profile; --dry-run reports only
passkeys-off check               # report every Firefox and Chromium profile, then the by-hand settings
```

Exit status: `0` every profile is set, `1` a Firefox profile lacks the prefs or a Chromium
profile lacks the extension (missing or disabled), `2` usage error.

`apply` owns only the lines between `// BEGIN passkeys-off` and `// END passkeys-off` in
`user.js`. Every other line is kept, the block moves to the end of the file (later prefs
win), and the file is replaced atomically with its mode kept. A block written with other
wording by an earlier version is recognized by its prefix and replaced.

The extension is `manifest.json` plus `passkeys-off.js`. Its behaviour:

| Call | Result |
|---|---|
| `PublicKeyCredential.isUserVerifyingPlatformAuthenticatorAvailable()` | `false` |
| `PublicKeyCredential.isConditionalMediationAvailable()` | `false` |
| `PublicKeyCredential.getClientCapabilities()` | every capability `false` |
| `navigator.credentials.create({publicKey})`, including conditional create (automatic upgrade) | rejected, `NotAllowedError` "Passkeys are turned off in this browser (Passkeys Off)." |
| `navigator.credentials.get({publicKey, mediation: "conditional"})` | stays pending until the page aborts it (as if no passkey were picked), so pages that retry on failure do not loop |
| `navigator.credentials.get({publicKey})` (modal) | passed to the browser unchanged |
| Password and other credential types | passed to the browser unchanged |

## Build / Run / Test

Set up a Mac once (after `dotfiles apply` installs the feature):

1. `passkeys-off apply`, then restart Firefox.
2. In Brave (and Chrome, if used): open `brave://extensions` (`chrome://extensions`), turn on
   **Developer mode**, **Load unpacked**, choose `~/.local/share/browser-extensions/passkeys-off`
   (press <kbd>⌘</kbd><kbd>⇧</kbd><kbd>.</kbd> in the file dialog to show hidden folders).
   Repeat in each browser profile.
3. In each browser's 1Password extension: account menu > **Settings** > **Autofill & save** >
   turn off **Offer to sign in with passkeys** and **Offer to save passkeys**.
4. **Passwords** app > **Settings** > turn off **Automatically Create Passkeys**.
5. `passkeys-off check` should exit 0.

Tests: `python3 -B -m unittest tests.test_dotfiles.PasskeysOff -v`. They run the extension
script under Node against stand-in WebAuthn objects, and `apply`/`check` against temporary
Firefox and Chromium profiles.

## Operations

- **Updates.** Sync updates the managed copy. Chromium re-reads an unpacked extension at
  start, so restart the browser (or press the reload arrow on the extension's card).
- **Health.** `passkeys-off check`; exit 1 names the profile and the fix.

Troubleshooting:

| Symptom | Check | Fix |
|---|---|---|
| A site still offers to create a passkey in Brave | `passkeys-off check` shows the profile `ok`? | If not loaded or disabled, load or enable it. If `ok`, the prompt is 1Password's: turn off its two passkey offers in that browser |
| The prompt is the macOS passkey sheet or a QR code in Brave | Did a page action start it (a "Sign in with a passkey" button, a security-key step)? | Explicit sign-ins pass through by design. Use a password instead, or remove the passkey from that account |
| `check` says "not loaded" right after loading it | Was it loaded from another folder (a repository checkout)? | Remove it and load `~/.local/share/browser-extensions/passkeys-off`; `check` compares real paths |
| Extension loads but changes nothing | Were its files symlinks (loaded from `features/.../passkeys-off` through links)? | Load the managed copy; Chromium skips content scripts from symlinked files |
| Firefox still shows the macOS sheet | `about:config` shows `security.webauthn.enable_macos_passkeys` `false`? | Restart Firefox; if still `true`, run `passkeys-off apply` and check that `user.js` sits in the profile `about:support` names |
| `dotfiles apply` reports "edited here since dotfiles last wrote it" for the extension | The copy was changed locally | `dotfiles adopt <path>` to keep the change, or delete the file and `dotfiles apply` |
| A site breaks (sign-in loops, an error banner about passkeys) | Does it work with the extension turned off for a moment? | Use its password sign-in; there is no per-site allowlist |

## Security

- The extension has no permissions, no background worker and no network access. It
  replaces four page-visible functions and leaves every other credential path alone.
- Turning passkeys off does not weaken accounts that use passwords plus a second factor.
  Security keys keep working as a second factor in every browser.
- `user.js` holds only the two prefs; no credentials are read or written.
- A page can still detect the extension's replacements (for example through
  `Function.prototype.toString`), as with any page-world script.

## Code Map

| Path | Purpose |
|---|---|
| [features/browser.passkeys-off/feature.toml](../features/browser.passkeys-off/feature.toml) | Feature: the extension as a managed copy, `passkeys-off` as a link |
| [features/browser.passkeys-off/home/.local/share/browser-extensions/passkeys-off/manifest.json](../features/browser.passkeys-off/home/.local/share/browser-extensions/passkeys-off/manifest.json) | MV3 manifest: one MAIN-world content script in every frame at `document_start` |
| [features/browser.passkeys-off/home/.local/share/browser-extensions/passkeys-off/passkeys-off.js](../features/browser.passkeys-off/home/.local/share/browser-extensions/passkeys-off/passkeys-off.js) | The capability answers and `create`/`get` handling |
| [features/browser.passkeys-off/home/.local/bin/passkeys-off](../features/browser.passkeys-off/home/.local/bin/passkeys-off) | `apply` (Firefox prefs) and `check` (every browser profile) |
| [tests/test_dotfiles.py](../tests/test_dotfiles.py) (`PasskeysOff`) | Extension behaviour under Node; `apply`/`check` against fixture profiles |
