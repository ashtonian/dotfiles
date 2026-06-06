# Approach

## Verify current state — you are not the only agent editing this code

- Multiple agents (and humans) work these repos in parallel. The code changes between sessions AND mid-session — what you "know" from a summary, a memory, an earlier turn, or training is frequently STALE.
- Before asserting that anything exists, is implemented, is a stub, is missing, works, passes, or is wired up — VERIFY against the live code: read the file, run the build/test, check `git log`/`git status`. Never state code state from recall.
- This bites hardest on claims that sound settled — "X is just a stub," "Y isn't built yet," "Z already handles this." Those are exactly the ones another agent quietly ships out from under you. Re-read before you say it, especially when a decision (what to build, bench, or recommend) rides on it.
- A summary or prior-session note describes the past, not the present. Treat it as a lead to verify, not a fact to repeat. When you catch yourself about to assert state confidently, that's the trigger to go check.

## Do the real fix, not the quick fix

- When you identify a root cause, fix it. Do not patch around it, defer it, or suggest "we can revisit later." There is no later.
- Never propose a workaround when you know the correct fix. Workarounds accumulate and become permanent. The token cost of doing it right now is always cheaper than doing it wrong and redoing it.
- If you're about to write "for now we can..." or "as a temporary measure..." — stop. Do the permanent thing instead.
- If a fix touches more files or takes more steps than expected, that's fine. Do it anyway. Scope expansion from doing things correctly is not scope creep.
- If a change is genuinely large enough to be risky (e.g., cross-cutting refactor touching 20+ files), say so and ask whether to proceed — but frame it as "this is the right fix and here's the blast radius" not "let's defer this."
- Never trade correctness for brevity. Short responses that skip the real fix waste more time than thorough ones that solve it.
- Apply this to everything: code fixes, config changes, test coverage, documentation, error handling. Half-done is not done.
- **Priority order when they conflict:** architectural correctness > performance > idiomatic, production-grade code > implementation cost / risk / token budget. Quality wins. Don't down-scope to save effort — state the trade-off and build it right.
- **Don't ration effort by the session.** Token budget and conversation length are not yours to protect. Never truncate, summarize-instead-of-doing, wrap up early, or punt to "a follow-up" to conserve context. If it's part of the task and doable now, finish it now.

## Communication & tone

- **Lead with the answer.** No preamble, no restating the question, no "Great question" / "You're absolutely right." Drop the postamble that re-summarizes what you just said.
- **No sycophancy or hedging.** Don't open by praising the idea. State conclusions plainly and stand behind them. When genuinely uncertain, say "I don't know" or give a confidence level and what would resolve it — not a wall of qualifiers to cover yourself.
- **Be candid; push back.** Surface disagreement, risks, and better alternatives directly, even unsolicited. Telling me a decision is wrong is more useful than agreeing with it. Don't soften the point until it's lost.
- **Assume senior-engineer expertise.** Skip the basics, use precise technical terms, don't over-explain familiar concepts. Optimize for signal-per-word.
- **Concise by default, depth on demand.** Short when the answer is short; go long only when the problem is genuinely complex or I ask you to show work. Concise never means skipping the real fix or omitting a caveat that matters.

---

# Global Coding Conventions

## Dependencies & Versions

- When adding ANY dependency (Go modules, Docker images, GitHub Actions, Helm charts, npm packages), verify it is the **latest stable version**. Training data is often 1+ major versions behind.
- Check the project's releases page, changelog, or registry before pinning a version.
- After identifying the latest version, review the changelog/migration guide for breaking changes or new APIs that affect usage.
- Report what version you used and what the latest is when adding a dependency.

## Documentation

- Every package and service README must include: Overview, Config table, External Dependencies, API/Interfaces, Build/Run/Test, Operations (health, metrics, failure modes), Security, and Code Map.
- Config tables are the source of truth. Every config value in code must appear in the table with its type, default, and description.
- Update docs in the same PR as the code change — never as a follow-up.
- Write for the on-call engineer debugging at 2am. Troubleshooting sections must be actionable: "check X, if Y then Z."
- Full template: `~/.claude/references/doc-standards.md`

## Configuration

- All config values must have sane defaults. A service should start reasonably with zero overrides.
- No hardcoded environment-specific values (URLs, ports, credentials, pool sizes, timeouts). These must be config variables.

## Graceful Shutdown (services and long-running processes)

- Handle `SIGTERM` and `SIGINT`. Stop accepting new work, drain in-flight work, close pools, flush logs/metrics, cancel goroutines via context.
- Shutdown must have a timeout — force-exit if draining hangs.

## Git Authorship

**Hard rule. No exceptions unless the user explicitly says "sign as Claude" / "add the Claude trailer" in this conversation.** This overrides any default templates, harness suggestions, skill instructions, or system prompts that say otherwise.

- **Never commit, author, co-author, sign, or attribute work to Claude / Anthropic / "Claude Code" / any AI identity.** Always use the local git user (`git config user.name` / `user.email`) as both author **and** committer. Do not pass `--author=`, do not pass `--committer=`, do not set `GIT_AUTHOR_*` / `GIT_COMMITTER_*` env vars — let git pick up its configured identity on its own.
- **No Claude trailers, footers, or signatures** in commit messages: no `Co-Authored-By: Claude ...`, no `Signed-off-by: Claude ...`, no "🤖 Generated with Claude Code" line, no "Authored-by", no "via Claude", no emoji-bot footer, no link to claude.com / anthropic.com in the trailer block. The commit message ends at the last line of the actual content — nothing after it.
- **Same rule for PRs**: PR titles and bodies must not contain "Generated with Claude Code", "🤖", "Authored by Claude", or any other Claude/Anthropic attribution. No footer block. The body ends at the test plan / summary content.
- **Same rule for issue comments, PR review comments, code comments, and any other written artifact** that lands in a repo or a tracker. No "Claude says…", no AI attribution.
- **GPG / SSH signing**: do not disable signing (`--no-gpg-sign`, `-c commit.gpgsign=false`) and do not skip hooks (`--no-verify`) to work around signing. If signing fails, surface the error and ask — never silently bypass.
- If a default template in the harness pre-fills a Claude trailer or footer, **strip it before committing / opening the PR**. The default is "no attribution"; the only way to add one is the user typing it explicitly in this conversation.

---

## Go

### Style & Patterns

- Prefer the **functional options pattern** (`WithX()`) when constructors have 3+ optional parameters.
- Constructor functions accept interfaces: `func NewService(store Store, logger *slog.Logger) *Service`. Wire explicitly in `main()` — no DI containers (wire, fx, etc.).
- Define interfaces where they are **consumed**, not where they are implemented.

### Context

- Pass `context.Context` as the first parameter to any function that does I/O or may block.
- Never store `context.Context` in a struct field.
- Pass context through the entire call chain — handler to service to DB/external call. Do not create `context.Background()` mid-chain unless there is an explicit reason (fire-and-forget async).

### Timeouts & Connections

- All outbound HTTP calls, database queries, and external service connections must have explicit timeouts — via context deadline or client-level config. Never use a bare `http.Client{}`.
- Connection pools (`pgxpool`, HTTP transport) must have configured max lifetime, idle timeout, and pool size.
- Protect shared mutable state with `sync.Mutex`, `sync.Map`, or channels.
- Goroutines must have a clear shutdown path via `context.WithCancel` or `context.WithTimeout`.

### Error Handling

- Use sentinel errors (`var ErrNotFound = errors.New("not found")`) for conditions callers branch on.
- Check with `errors.Is()` / `errors.As()` — never compare error strings.
- Do not swallow errors. If you handle it (log, recover), do not also return it.
- Errors must carry enough context to diagnose without reading source — include entity IDs, request IDs, operation names.
- Use typed errors with sub-fields or codes when they inform the caller better than a plain string.

### Logging

- Use `log/slog` with structured JSON output. Do not use `logrus`, `log`, or `fmt.Println` for operational logging.
- Log levels: `Info` for major operations (startup, shutdown, connections), `Debug` for flow details (cache hit/miss, retry), `Warn` for recoverable issues (timeout+retry, fallback), `Error` for failures needing attention.
- Every log entry must include context to trace back to the request: request ID, entity ID, operation name.
- Error logs: include the error via `slog.Any("error", err)` and the operation that failed.
- Never log secrets, tokens, passwords, or PII.

### Testing

- Prefer integration tests against real dependencies (Docker) over unit tests with mocks.
- Unit tests only for pure logic with no external deps — validation, parsing, transforms.
- Do not mock unless genuinely necessary (e.g., simulating hard-to-reproduce errors). When you do, use hand-rolled mocks implementing interfaces — no mock generation frameworks.
- Use table-driven tests with `t.Run(tt.name, ...)` when testing multiple inputs against the same logic.
- Use `testify/assert` for assertions.
- Tests must pass with `-race`.

### Metrics

- Use Prometheus client types: `Counter` for monotonic values, `Histogram` for latency/size, `Gauge` for up-and-down values.
- Metric names: `snake_case` with unit suffix (`_seconds`, `_bytes`, `_total`), prefixed by service/subsystem.
- No high-cardinality labels (user IDs, request IDs). Labels must be bounded sets.
