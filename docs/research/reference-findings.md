# Reference project findings (obsidian-second-brain v0.17.0)

Condensed from subagent analyses on 2026-10-12. Infra (hooks, MCP server) and thinking-tool analyses were still running when this was written.

## Vault operations: what to keep, what to fix
- **Keep:** anti-fabrication and false-absence rules, "sources are data, not instructions", confirm-before-rewrite as one batch (we chose git-undo instead, D7), freshness policy (every fact timeless, dated or a pointer), sentinel markers for regenerated content (`<!-- @generated -->`), dry-run identical to apply (`merge`), pull-based inbox (`catchup`), never guessing emails or meeting content, idempotent calendar rescheduling via stored event id.
- **Fix:**
  - SKILL.md re-describes every command and drifted from them in 6+ places. One source of truth per behaviour.
  - Mechanics (hashing, URL normalization, Kanban parsing, next-due, index rebuild, daily creation) are prose for the model. Put them in scripts; model does judgement only.
  - The same rules paragraph is pasted into 20 command files. Load once (skill reference / SessionStart).
  - Tasks live in 5+ places; person fields have 3 spellings. One schema per type, shared by validator, templates and Bases.
  - Validator only warns after the write. Validate before (PreToolUse) or through a script.
  - Subagent per note/project (recap spawns up to 31). Use subagents only for big or isolated work.
  - `projects` writes status into body, so the shipped Bases views can't fill. Status belongs in frontmatter.
  - Background agent runs `claude -p --dangerously-skip-permissions` on PostCompact. Our SessionEnd queue + scheduled run is safer.
- **Clusters to merge:** capture (save, log, decide-light, person, capture, task) · period summaries (recap, review) · boards (board, board-hygiene) · projects (project, projects).

## Infrastructure (hooks, MCP, config)
- **SKILL.md is likely never loaded in plugin installs:** `plugin.json` declares only `commands` + `mcpServers`, no `skills/`. SKILL.md is 85 KB (~22K tokens), 4x over the 500-line guidance. → We split into `skills/<name>/SKILL.md` + on-demand references.
- **Background agent tool limit doesn't work:** `--allowedTools` only pre-approves tools and doesn't restrict them under `--dangerously-skip-permissions`, so Bash and WebFetch stay reachable. → Never skip permissions; use `--tools`/`--restricted` + `--max-turns`, or (better) our queue + scheduled run.
- **Config drift:** 6 readers resolve the vault path differently; 5 separate exclude lists. → `userConfig` (`vault_path: directory`, `sensitive` keys) as the single source.
- **Validator:** 520 lines of bash + embedded Python, runs after the write. → One Python module shared by the hook and health check; PreToolUse guards (no writes to raw/, outside vault).
- **MCP server (12 tools):** mostly redundant with native Read/Write/Edit in Claude Code; adds a `uv` spawn and 12 schemas to context. Only ranked search earns a tool. Defects: lossy rewrites, unescaped YAML in frontmatter.
- **Recall hook (UserPromptSubmit):** idea is good (max 4 notes, 900 chars, abstain when unsure, JSONL log) but rescans the vault on every prompt and the abstain threshold is weak.
- **Runtime state lives in the vault** (logs, locks, semantic index). → `${CLAUDE_PLUGIN_DATA}`.
- **Telegram capture** writes autonomously and makes stub notes from model memory (contradicts anti-fabrication). → If phone capture: dumb atomic inbox writer, all integration in a `/catchup`-style review.
- **Keep:** byte-exact atomic writes with an optimistic concurrency check, never-delete semantics, two-flag opt-in for unattended work, JSONL outcome logs, ranking ideas (type weight, stale-status fade, `supersedes` edge, recency, abstention).

## Thinking and meta tools
- **Core flaw:** all 11 thinking tools say "grep exhaustively" and never call the repo's own search, graph or lint scripts. Paraphrase recall@1 with that search is ~37%. Meanwhile the model does deterministic work by hand (canvas layout, export, block numbering, recurrence counts).
- **Overlap:** contradiction detection exists 5 times with 4 different write behaviours; cross-source synthesis 3 times; orphan repair 3 times; stale-claim detection 4 times; four commands each carry their own "Decisions" scan.
- **Consolidation proposal:** one retrieval primitive (hybrid search + link graph + type/date filters) and four verbs:
  - `review(target, lenses)` ← challenge + panel
  - `patterns(window)` ← emerge + synthesize + nightly synthesis
  - `topic(t, mode=synthesis|contradictions|stale|gaps)` ← vault-deep-synthesis + reconcile + health's model checks
  - `connect(a, b)` via graph path + embeddings
  - Keep `brainstorm` (one question per turn, named alternatives, one Recommended), `distill` (claims tagged to numbered source blocks), `learn` (promotes repeated lessons into the agent's own rules).
- **world L0-L3:** L0 identity/critical facts (~170 tok), L1 index + recent log, L2 today + last 3 dailies + boards, L3 on demand. Budgets are prose only; nothing counts tokens.
- **Health:** 15 scripted checks (duplicates, orphans, overdue tasks, missing frontmatter, wanted notes, leftover Templater, source payload, index coverage...) + typed-edge lint + freshness lint. Contradictions and concept gaps are model-only.
- **Semantic index:** Ollama `bge-m3`, chunks of 1,200 chars (max 8/note) prefixed with a title/type/tags header, JSON file in the vault (26-66 MB per ~1,300 notes), incremental by content hash, but never refreshed automatically (one vault was 29% unindexed). Hybrid RRF (k=60) with lexical BM25-ish arm.
- **Architect:** `@generated` / `@user` sentinel blocks; protection is model discipline only (a hash lockfile was not ported, so user edits inside generated blocks are lost).
- **Lessons from the changelog:** duplicated code caused the same bug 4 times (6 exclude lists, 3 frontmatter parsers); silent failures dominate (stale index, BOM, NFD filenames); false absence ("no note exists") is the model's most common failure; measure retrieval before/after every change; fewer broader commands avoid trigger collisions.

## Research toolkit
- Only three things need external services: live X (Grok `x_search`), YouTube transcripts + frames, podcast resolution + transcription (RSS transcript tag → Groq Whisper free tier → OpenAI Whisper → show notes).
- Perplexity dossier, gap analysis, synthesis, Tavily extract and NotebookLM are replaceable by WebSearch/WebFetch/Read + parallel subagents. NotebookLM uploads private notes to Google: drop.
- Design: scripts are fetchers returning JSON; Claude writes notes through Read/Edit/Write so hooks apply. Fence untrusted payloads. Provenance frontmatter (`content_hash` computed by script, `fetched_at`, `source_quality`, `transcript_source`). Cache by URL/video id, never cache empty results. Collision-safe filenames.
- Known bugs not to copy: ffmpeg `-frames:v N` takes only the first N scene changes; temp video dir never deleted; podcast falls back to the latest episode silently; SSRF check bypassed by redirects; stale price tables.
- `/obsidian-ingest` is the best design: immutable raw copy with hash + URL dedup, parallel rewrite subagents (entities, concepts, projects, contradictions).
