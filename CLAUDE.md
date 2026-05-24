# CLAUDE.md

Chemigram's agent-operational handbook lives in [AGENTS.md](AGENTS.md). That's the canonical source — edit it there and the change applies project-wide.

This file is a Claude-specific entry point. Claude Code reads `CLAUDE.md` by default in any project; without this pointer, the harness wouldn't find the conventions.

Claude-specific addenda below — anything that's Claude-only and doesn't belong in the cross-tool canonical handbook.

---

## For Claude specifically

- When the user references "/<skill-name>" or a slash command, invoke via the Skill tool. Only use skills listed in the user-invocable skills section — don't guess.
- Prefer `lean-ctx` MCP tools (`ctx_read`, `ctx_shell`, `ctx_search`, `ctx_tree`) over native equivalents per the user's global `~/.claude/CLAUDE.md`. Native Edit/Write stay normal; if Edit requires a prior Read and Read is unavailable, use `ctx_edit`.
- Memory: write to `~/.claude/projects/-Users-markodragoljevic-Projects-chemigram/memory/` per the auto-memory rules in the system prompt. Never duplicate AGENTS.md content there.

Everything else — disciplines, doc system, voice rules, code conventions, workflow conventions including the post-push CI check — is in [AGENTS.md](AGENTS.md).
