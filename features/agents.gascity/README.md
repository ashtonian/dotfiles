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

## Approve one issue or a chunk

Give the planner read access. Have it post a **standalone plan comment** on the issue with the scope, exclusions, affected repos and lanes, immutable source revisions, dependency/release gates, acceptance tests and decisions you are being asked to make. Use one comment for an entire small issue. On a large RFC, use one comment per independently reviewable chunk. A sign-off on chunk 1 leaves chunk 2 awaiting approval. Include downstream SHAs or version constraints when they affect the decision.

The operator selects the plan comment and the trusted owner's numeric GitHub ID. The ID comes from private dispatcher configuration. The number after `#issuecomment-` in the plan's URL is its comment ID. Run:

```sh
repo=example/parser
issue=42
plan=123456
fleet-plan show "$repo" "$issue" "$plan"
```

Review the quoted plan printed by the tool. To approve, paste its final command line as **a new comment of your own on the issue**. To request changes, reply with the feedback and leave approval pending. To put previously approved work on hold, post `/fleet hold 123456` in its own comment. The planner revises the plan and the owner approves its new digest.

Before assigning implementation, the intake operator runs:

```sh
fleet-plan check "$repo" "$issue" "$plan" --owner-id "$FLEET_OWNER_ID" &&
  fleet-slot-check "$slot" "$EXPECTED_ORIGIN" &&
  bd -C "$BOARD" --actor "$ACTOR" update "$IMPLEMENTATION" --claim
```

The check reads all issue-comment pages. It requires an open issue and the latest owner decision for this plan to be an unedited approval matching its current content. It returns the approval URL for the bead. Recheck immediately before launch, at scope changes and before accepting a handoff. A failed check parks the work; a running process needs an explicit pause. Preserve the original plan ID on the bead. A replacement comment requires explicitly rebinding that chunk.

Keep the approval account's write credential outside worker sessions. A bot or CLI posting with the owner's own GitHub credential appears as that owner. With a shared GitHub identity, use manual dispatch from an operator-only session until worker write credentials are separated. The CLI verifies evidence; permission to start sessions and edit the trusted owner ID belongs to the dispatcher. A plain board edit cannot attest to human approval.

For your morning inbox, apply a shared triage label such as `needs-plan-approval` to the source issue and save a GitHub search for open issues with that label in eligible repos. Put the plan permalink and requested decision at the top of each issue. After your decision, the dispatcher records the approval URL and removes the inbox label. Keep a second view for scope changes and reviews that need a human choice. Labels organize the inbox; only the verified owner decision releases work.

## Feed the work board

Use one intake writer per board. Link each source with a stable key and keep its revision separately. Import a second time by updating the existing bead. Reconcile closed items as well as open items. A partial page scan or API failure must leave the cursor unchanged; overlap scans on retry and periodically reconcile the full set. A newly discovered source starts in triage.

| Input | Stable key | What the operator imports |
| --- | --- | --- |
| RFC or lane in Git | Repo and durable RFC/lane ID | Link to the path at a commit. Keep accepted scope, status and ownership rules. An historical plan is evidence. |
| GitHub issue | Repository and issue number | Owner, lane, dependencies, acceptance criteria and existing PR. Reuse the issue's bead when several documents point to it. |
| Draft or open PR | Repository and PR number | Original implementation owner, base and head SHAs, linked issues, CI and overall review state. Each changed head needs a fresh review decision. |
| Review finding | PR and GitHub review-thread ID | Resolution state, outdated state, path and URL. An outdated unresolved thread still needs triage. Route feedback to the original worker. |

For repeatable intake, use the paginated endpoints. The issue endpoint includes PRs, so filter them out before creating issue records. Inspect every open PR, even when the linked issue is already assigned:

```sh
gh api --paginate "repos/$repo/issues?state=open&per_page=100" \
  --jq '.[] | select(has("pull_request") | not) | [.number, .html_url, .updated_at] | @tsv'
gh api --paginate "repos/$repo/pulls?state=open&per_page=100" \
  --jq '.[] | [.number, .base.sha, .head.sha, .html_url] | @tsv'
```

Read the repo's current RFC index or assignments file at a known commit, then follow its links to the current issue. For actual review threads, fetch their GraphQL IDs and resolution state (the PR's overall review decision is a separate input):

```sh
gh api graphql --paginate -F o="${repo%/*}" -F r="${repo#*/}" -F n="$PR_NUMBER" -f query='
query($o:String!, $r:String!, $n:Int!, $endCursor:String) {
  repository(owner:$o, name:$r) { pullRequest(number:$n) {
    headRefOid reviewThreads(first:100, after:$endCursor) {
      nodes { id isResolved isOutdated path } pageInfo { hasNextPage endCursor }
    }
  } }
}' --jq '.data.repository.pullRequest'
```

A useful issue expands into plan, owner approval, implementation and exact-head review beads. Link implementation to the approval bead with `bd dep add "$IMPLEMENTATION" --blocked-by "$APPROVAL"`. The dispatcher closes that blocker after verifying the human decision and records its URL. A reviewer can start from an already open PR. Persist the same PR number and issue owner across pushes. This pilot uses an operator to reconcile these records; the commands above only read GitHub.

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
fleet-plan check "$repo" "$issue" "$plan" --owner-id "$FLEET_OWNER_ID" &&
  fleet-slot-check "$slot" https://github.com/example/parser.git &&
  bd -C "$BOARD" --actor builder-a-parser-one update "$ISSUE_ID" --claim
```

A successful preflight prints the checkout's HEAD. The board claim reserves the issue. Use a unique actor per slot and one session per copy. After the claim succeeds, run these in the city shell:

```sh
command gc start "$CITY"
command gc --city "$CITY" session new parser-one --no-attach
command gc --city "$CITY" session list
```

Give the returned session the claimed issue, branch and acceptance criteria. Attach with `command gc --city "$CITY" session attach "$SESSION_ID"`. Record the slot, session ID, branch, bead and draft PR on the board. To speak to the city coordinator, attach to `mayor`.

On another host use a different actor and claim a different ready item. Keep a live claim current with `bd -C "$BOARD" --actor builder-a-parser-one heartbeat "$ISSUE_ID"` at intervals shorter than its lease. Stop on loss of ownership. If a claim fails, inspect its owner before launching. For parallel work within one repo, split independent acceptance criteria across beads and assign each its own copy.

Across three four-slot hosts, reserve one Astra reviewer per host. The other nine slots can give nine different project queues one implementer each. An idle reviewer stays available for review. Idle implementation capacity can take a second, independent chunk of a busy project after project coverage is satisfied. Subtract any standing agents, manual sessions and unavailable hosts from the budget first. Give smaller hosts bounded edits and send heavy Go race tests or generation to CI. Increase to five or six sessions only where measured memory, disk, review throughput and account limits permit.

## Choose a host and control local load

A bead is claimed in the shared database; a Gas City session starts on one host. One dispatcher selects the host before claiming. Keep a small private inventory of each slot's role, permitted repos and account, supplied copies, active attempt and last-seen time. Snapshot local city sessions, manual sessions, disk headroom and the host build queue. Exclude unreachable hosts, reserved review slots, incompatible copies or identities, and hosts with stale observations.

First serve ready projects with no active implementer. For a particular job, prefer its existing branch/session for follow-up, then its home host if it fits. For overflow pick the eligible host with the most free implementation capacity relative to its limit. Break ties by the oldest waiting work and rotate hosts on equal fit. A free terminal on a memory-pressured machine cannot accept a heavy build. For example, if the laptop is full and the workstation has a free worker and the right checkout, claim as the workstation slot and start there. If both are idle, leave the job on the home host.

Serialize assignments per slot and inspect the local session immediately before starting. An issue claim reserves an issue; independent claims for different issues can still target the same slot. Use a single dispatcher for this pilot. If launch fails after claiming, record the attempt and check for a surviving session before releasing the claim. A future automatic dispatcher needs a durable slot reservation as well as the issue claim.

Keep two budgets on each Mac: live sessions and admitted build/test work. Leave a reviewer seat available and count manual and support agents in the session budget. Route focused checks through existing repo wrappers, heavy validation to the host's build gate or CI, and benchmark runs to the reserved runner. On a laptop also consider sleep and loss of LAN connectivity. Re-evaluate pending jobs when a slot, build gate or subscription window opens; preserve in-flight work on its existing branch.

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
