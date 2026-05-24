# AGENTS.md

Chemigram's agent-operational handbook lives in [CLAUDE.md](CLAUDE.md).

This file is a pointer for cross-tool compatibility — agentic harnesses (OpenAI Codex, Cursor, and others) look for `AGENTS.md` by default; the canonical content is `CLAUDE.md`. Both files describe the same conventions, so don't fork — edit `CLAUDE.md` and the changes apply project-wide.

Specifically `CLAUDE.md` covers:

- The three foundational disciplines (agent-is-only-writer; darktable-does-photography; BYOA).
- Doc system (PRDs, RFCs, ADRs, references) and how to add each artifact.
- Voice, naming, and code conventions.
- Workflow conventions — including the **post-push CI verification** rule.
- Things that are easy to get wrong + when in doubt.

Start there.
