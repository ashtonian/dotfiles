# Running a Gas City fleet

Use one Gas City city per execution host and one shared Beads board per group that may see the same work. A city owns local sessions, prompts and recovery. The shared board tells operators which issue is ready, who claimed it and which change unblocks the next repo. GitHub owns the issue, PR, CI and release. You supply one checkout per active agent, including reviewers.

## Install on each participating Mac

Add the feature to the existing enable list in `~/.config/dotfiles/machine.toml`:

```toml
[features]
enable = ["agents.gascity"]
```

```sh
dotfiles check
dotfiles apply --dry-run
dotfiles apply
~/.dotfiles/sync.sh brewfile
command gc version
bd version
dolt version
tmux -V
```

The upstream tap supplies Gas City and brings in Beads, Dolt, jq, tmux and flock. Homebrew updates these packages independently. The reference versions for this guide are Gas City **1.5.1**, Beads **1.3.2** and Dolt **2.2.0**. Record actual versions on each host before working against a shared board. Upgrade all board clients together when the schema changes. Sign into the installed Claude and Codex CLIs in each intended OS account. Check `claude auth status` and `codex login status` in the shell that will launch sessions. Provider credentials stay in that account.

## Stage one host

Run this in a shell for the intended trust boundary. Choose a fresh private city directory for each host. The example keeps each city's managed ledger local. The team board is a separate directory and database.

```sh
umask 077
CITY="$HOME/.local/share/cities/workbench-a"
command gc init "$CITY" --no-start --template gastown \
  --providers claude,codex --default-provider claude
```

Edit the existing provider tables in the generated `city.toml` before starting any session. The v1.5.1 built-ins default to unrestricted permissions. Set these explicitly, including for the coordinator and pack agents using those providers:

```toml
[providers.claude]
base = "builtin:claude"
option_defaults = { permission_mode = "auto-edit" }

[providers.codex]
base = "builtin:codex"
option_defaults = { permission_mode = "suggest", model = "gpt-6.2-astra" }
```

Use an implementation identity without branch-protection bypass, and require review on the target branch. Give the reviewer read access. Inspect the resolved configuration with `command gc --city "$CITY" config show`, including pack providers, permission modes, startup hooks, standing sessions and refinery/landing orders. Disable auto-landing and additional worker pools before pointing the city at real repos. Count coordinator, patrol and review sessions against the host budget. Start with a disposable copy and one named worker.

For the first pilot, leave product rigs unregistered so their refinery, witness and polecat templates are never activated. For a city-local worker, place this in `agents/parser-one/agent.toml` under the city. Substitute an absolute path on **that host**. Add a second agent directory for the reviewer with `provider = "codex"` and its own copy. Keep checkout-creation and checkout-reset hooks off the supplied copies.

```toml
scope = "city"
work_dir = "/work/slots/parser-one"
provider = "claude"
nudge = "Read your assigned issue and its acceptance criteria."
```

Gas City v1.5.1 selects the runtime **city-wide**. Keep local tmux on each Mac and operate the other cities over an existing verified SSH connection. For a city whose *every* session should run on one remote host, the city setting is `[session] provider = "ssh:builder-a"`. SSH does not distribute a single city's agents across several Macs. [Upstream runtime and transport](https://github.com/gastownhall/gascity/blob/v1.5.1/docs/guides/configuring-an-agent.md)

## Connect the shared work board

Have the operator provision a dedicated Dolt database, a scoped SQL login and a certificate for the endpoint. Install its CA through your trusted workstation configuration. Initialize once, in an empty private board directory. Supply the password from the account's credential manager to the board commands. Keep board exports out of the city supervisor, global shell startup and other trust contexts.

```sh
BOARD="$HOME/.local/share/work-boards/example"
install -d -m 700 "$BOARD"
# Set BOARD_HOST, BOARD_PORT, BOARD_USER, BOARD_DB and BEADS_DOLT_PASSWORD privately.
export BEADS_DOLT_PASSWORD BEADS_DOLT_SERVER_TLS=1
(cd "$BOARD" && bd init --server --external --server-tls \
  --server-host "$BOARD_HOST" --server-port "$BOARD_PORT" --server-user "$BOARD_USER" \
  --database "$BOARD_DB" --prefix team --skip-hooks --skip-agents)
bd -C "$BOARD" dolt test
```

For subsequent hosts distribute the first board's non-secret `.beads/metadata.json` and `.beads/config.yaml` into the same private directory structure after inspecting them. Supply credentials and TLS on each host. Use `bd -C "$BOARD" show ISSUE_ID` on both hosts to check they see the same scratch issue before dispatch. Run board commands outside a Gas City worker environment that sets `BEADS_DIR` or other store overrides. Never copy runtime data, credential files or a running city's internal store between Macs.

## Start the morning's three queues

Suppose the parser, gateway and shared library each have outstanding GitHub issues. Inspect open PRs first. Have **one intake operator** create a bead per issue URL. Check existing beads (including closed ones) on re-intake. An external reference is a lookup key; the read and create below are separate operations.

```sh
repo=example/parser
gh issue list --repo "$repo" --state open
gh pr list --repo "$repo" --state open
url=$(gh issue view 42 --repo "$repo" --json url --jq .url)
bd -C "$BOARD" list --all --limit 0 --external-ref "$url"
# Only if there is no bead for this issue:
bd -C "$BOARD" create "Parser: reject a truncated record" --type task --external-ref "$url"
bd -C "$BOARD" ready
```

Before assigning a *fresh* slot, compare its exact fetch URL and check its working tree. Gitstead is optional. If it manages this repo, run the lookup on the machine that owns the copy.

```sh
slot=$(gitstead path parser 1)       # or set slot to an existing path
fleet-slot-check "$slot" https://github.com/example/parser.git
bd -C "$BOARD" --actor builder-a-parser-one update "$ISSUE_ID" --claim
```

From the city shell, `command gc --city "$CITY" session new parser-one --no-attach` starts the prepared template after the city is running. Keep the returned session ID for the handoff and subsequent attaches.

A successful preflight prints the checkout's HEAD. It does not reserve the copy. Use a unique actor per slot and one session per copy. After the atomic claim succeeds, start the city with `command gc start "$CITY"` and open its coordinator with `command gc --city "$CITY" session attach mayor`. Record the slot, branch, bead and draft PR on the board. On another host use a different actor and claim a different ready item. Keep a live claim current with `bd -C "$BOARD" --actor builder-a-parser-one heartbeat "$ISSUE_ID"` at intervals shorter than its lease. Stop on loss of ownership. If a claim fails, inspect its owner before launching. For parallel work within one repo, split independent acceptance criteria across beads and assign each its own copy.

A morning target across three four-slot hosts might be three parser implementers, three gateway implementers, four library/framework implementers and two Astra reviews. Those are **twelve task slots**. Subtract any standing agents, manual sessions and unavailable hosts from the budget first. Give smaller hosts bounded edits and send heavy Go race tests or generation to CI. Increase to five or six sessions only where measured memory, disk, review throughput and account limits permit.

## Unblock a downstream consumer

Create one producer bead for the module change and one consumer bead for adoption. If the consumer requires a published tag, give publication its own bead and record that tag before closing it. Set the dependency direction explicitly:

```sh
bd -C "$BOARD" dep add "$RELEASE" --blocked-by "$LIB_CHANGE"
bd -C "$BOARD" dep add "$ADOPTION" --blocked-by "$RELEASE"
bd -C "$BOARD" ready
```

For a consumer with relative Go replacements, keep its pinned sibling copy in the expected layout. Test the base pin, then the candidate producer SHA in a disposable paired workspace. Record both SHAs and the test command. Release the implementation slot while CI or an owner-held tag is pending.

## Have Astra review a Claude draft

Give the reviewer the issue, acceptance criteria, diff, tests and exact head. The reviewer can inspect a fetched diff from its own copy. The operator can fetch evidence without allowing the reviewer to change the branch:

```sh
gh pr view "$PR" --repo "$repo" --json baseRefOid,headRefOid,url
gh pr diff "$PR" --repo "$repo"
gh pr checks "$PR" --repo "$repo"
```

Capture the head **before and after** collecting the diff. If it moved, discard the mismatched evidence and fetch again. Ask Astra to report actionable findings with file, line and impact, or to record a clean review for that SHA. Return findings to the original Claude session; record the reviewed SHA on the board. Re-review the next pushed head and let the repository's merge rules decide when it can land. Human intake, dispatch and handoff are explicit in this setup.

## Resume after sleep or an account limit

Inspect `command gc --city "$CITY" session list`, the bead's owner, the existing branch and the current PR. Reattach to the matching session. A dirty copy with matching ownership belongs to that attempt. Keep an unreachable host's work reserved until the original session and branch are reconciled. On a subscription limit, save progress and park that profile until its reset. Other eligible slots can take independent ready issues.

## Keep a client engagement separate

Use a separate OS account or machine, city directory, board **service and storage**, SQL/GitHub identities and approved provider login for client work. A second checkout or database name on the personal server does not establish that boundary. Transfer only an approved, sanitized upstream report. Keep inventory, private issue numbers, host addresses, prompts and credentials out of this repository.

[Upstream installation](https://github.com/gastownhall/gascity/blob/v1.5.1/docs/getting-started/installation.md) · [Gas Town configuration recipes](https://github.com/gastownhall/gascity/blob/v1.5.1/docs/guides/gastown-config-recipes.md) · [Beads server configuration](https://github.com/gastownhall/beads/blob/v1.3.2/docs/architecture/dolt.md)
