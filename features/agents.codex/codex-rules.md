# Codex

The rules above are every agent's; Claude Code reads them as
`~/.claude/CLAUDE.md`. These are Codex's own.

- Delegate as `~/.config/agent-delegation/policy.md` says.
- Claude Code loads a repository's CLAUDE.md and `.claude/rules/*.md` by itself; Codex does not. Before editing code, read the repository's CLAUDE.md beside its AGENTS.md, then every `.claude/rules/*.md` that has no `paths` filter or whose `paths` match the files you will touch, and follow their review checklists. After resuming or compaction, read the ones that apply again before continuing.
- `~/.codex/skills` holds the skills Claude Code loads too. Read the matching skill before that work: `gate-lock` before any build, test, lint or benchmark.
