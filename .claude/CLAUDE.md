# Global Rules

## Commit Attribution

All commits, PR descriptions, and git authorship use the local git user
identity only. **Never** add a Claude / agent signature in any form.

### Forbidden

- `Co-Authored-By: Claude …` lines in commit messages.
- `🤖 Generated with [Claude Code](…)` footers.
- "by Claude" / "via Claude Code" / "agent" attribution anywhere in commit
  bodies, PR descriptions, branch names, or release notes.
- Setting commit `--author` to anything other than the local git user.

### Required

- Author commits as the configured local git user
  (`git config user.name` / `user.email`). Don't override.
- Commit message body covers the WHAT and WHY of the change. No mention
  of how it was produced or by whom.
- PR descriptions follow the same rule — no Claude attribution in summary,
  test plan, or footer.

### Why

Git history reflects the project's authors. Tooling used to produce a commit
doesn't belong in the metadata; it's noise that mechanical readers (release
notes, changelogs, blame) have to strip.

If you spot an attribution line in a commit you're about to amend, remove it.
