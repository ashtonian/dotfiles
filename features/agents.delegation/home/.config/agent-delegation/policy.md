# Delegation policy

This session runs on the strongest model in play, with two cheaper subagents for scoped, read-only work. The failure this policy exists to prevent is building on a subagent's wrong claim.

- `scout` (the cheapest model) finds and quotes: paths, symbols, call sites, config keys, log lines. No judgment.
- `reader` (a mid-tier model) answers one bounded question about named files, logs or command output, tagging every claim VERIFIED (cited) or INFERRED.

In Claude Code they are subagent types for the Agent tool; in Codex, `agent_type` roles for `spawn_agent`. This policy is the explicit request to use them.

## What goes where

- Locating: `scout`. Bounded read-and-answer: `reader`. Prefer these over the built-in explorers (Claude Code's Explore, Codex's `explorer`) for that work.
- Do a read or two of a file you already know yourself. When finding something will take more than a couple of searches, or answering means reading large files or long output, hand it to `scout` or `reader`. Every call this session makes re-reads its whole context, and whatever it reads stays there for every later call; a subagent does that work in a small context and returns a short cited report.
- Keep on the session's model (yourself, a fork, or an agent with no role or model override): root cause, design and architecture, review verdicts, performance and profile conclusions, security, anything that writes code, and any answer you would act on without checking it.
- When unsure which side a task falls on, keep it on the session's model.

## Briefing

- Ask the question; do not hand over your hypothesis. "Where is X validated?", not "Confirm X is validated in Y."
- Name the exact files, directories or commands in scope.

## Using results

- Subagent reports are leads, not facts, and that includes a fetch agent's page summary. Before a decision, an edit or a statement to the user depends on a claim, read the cited lines yourself. That is a read of the cited range, not a redo of the task.
- A claim with no citation, or tagged INFERRED or NOT CHECKED, is unverified. Do not present it as established or reason further from it until you have checked it.
- If a report conflicts with something you have seen, or looks too clean, read the source yourself.
- When you relay findings to the user, keep what you verified separate from what a subagent reported.
