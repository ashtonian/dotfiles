# Claude Code

These rules are Claude Code's own. `~/.claude/CLAUDE.md` holds the rules every
agent follows, and Codex reads the same file as the start of its
`~/.codex/AGENTS.md`.

## Searching in the Bash tool

- `grep` there is a shell function that runs Claude Code's built-in ugrep with `--ignore-files -I`: it silently skips gitignored and binary files. Searching ignored, vendored or generated paths (`node_modules`, build output, `.gitignore`d configs) needs `command grep`.
