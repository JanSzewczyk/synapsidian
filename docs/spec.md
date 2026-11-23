# Synapsidian: specification

Status: **Draft for review** · 2026-10-13 · Owner: Jan Szewczyk

A Claude Code plugin that keeps a second brain in an Obsidian vault at `~/Synapsidian`: it captures what happens in Claude sessions, meetings and sources, keeps it linked and current, and gives it back as context, search and thinking tools. It replaces the Notion setup (devlogs, task board, 1:1 notes, morning brief).

Decisions behind every choice here are in [decisions.md](decisions.md) (cited as D1-D49). Findings about the reference project are in [research/reference-findings.md](research/reference-findings.md).

## 1. Goals and non-goals

**Goals**
- G1. Nothing worth keeping from a Claude session, meeting or source is lost, and recording it costs the user one command or nothing (D13, D14).
- G2. Every Claude session starts knowing who the user is, what is active and what is due, in under 2K tokens (D21).
- G3. Any note can be found again by a question phrased differently from the note (D20; measured, not claimed).
- G4. Every change Claude makes to the vault can be seen and undone (D7, D42).
- G5. Work knowledge never leaves the Mac except to Anthropic (D25, D31).

**Non-goals**
- Personal life areas (goals, health, finances) (D2).
- Phone capture (D15).
- Writing to external systems: calendar, Jira, Slack, Gmail stay read-only (D27).
- Other AI CLIs (Codex, Gemini...). Claude Code only.
- An MCP server in the MVP (D40).
- Importing Notion history (D12).

## 2. Principles

1. **Files are the interface.** Plain `.md` and `.base` files; works with Obsidian closed (D35).
2. **One schema, one source of truth.** Note types live in `schema/types.yaml`; scripts, validator, Bases, templates and skills read it (D41).
3. **Scripts do mechanics, Claude does judgement.** IDs, search ranking, validation, commits, brief assembly are scripts. Extraction, writing and synthesis are Claude (lesson from the reference).
4. **Search before create.** A new note is created only after searching titles, aliases and summaries for an existing one. Never claim something is absent without having searched.
5. **Never fabricate.** Unknown values are left out or written `TBD`; emails, attendees and meeting content come only from a source.
6. **Sources are data.** Text from transcripts, web pages, Slack and email is material to summarise, never instructions.
7. **One commit per skill run**, authored by the user (D42).
8. **Generated blocks are fenced.** Regenerated content sits between `<!-- @generated:<name> -->` and `<!-- @end -->`; anything outside is the user's and is never overwritten.

Deliberate departures from the reference project, so they are visible:
- No `## For future agent` preamble, no `ai-first: true`; a one-line `summary` field instead (D5).
- One vault layout, not two; one task store, not five.
- Skills (`skills/<name>/SKILL.md`), not 47 flat commands plus an 85 KB manual.
- No `--dangerously-skip-permissions` background agent; the session queue + scheduled run pattern instead (D46).
- No Perplexity, Grok, Gemini or NotebookLM (D24, D25). Gemini's own Meet notes may be imported as a source; nothing goes to Gemini (D95).

## 3. Vault layout (`~/Synapsidian`)

```
~/Synapsidian/
├── About.md            # who the user is: role, timezone, active focus, plus the user's vault rules (## Rules, protected); feeds the brief
├── Inbox/              # /capture drops; triaged later
├── Daily/              # YYYY-MM-DD.md
├── Tasks/              # T<n> <title>.md
├── Projects/           # <Project>.md
├── People/             # <First Last>.md
├── Meetings/           # YYYY-MM-DD <kind> <title>.md
├── Decisions/          # YYYY-MM-DD <title>.md (ADRs)
├── Notes/              # concepts and domain knowledge
├── Howtos/             # how-tos and runbooks
├── Ideas/              # YYYY-MM-DD <title>.md
├── Goals/              # <title>.md (D112)
├── Sources/            # immutable copies of ingested material (P3)
├── Research/           # research dossiers (P3)
├── Reviews/            # weekly / monthly / quarterly (P2)
├── Thinking/           # challenge, brainstorm, topic, patterns, distill, learn outputs (P4)
├── Architecture/<repo>/  # generated architecture notes (P4)
├── Bases/              # .base views (tasks, projects, people, meetings, inbox, ideas, goals)
├── Attachments/
└── Archive/            # archived notes keep their links; nothing is deleted
```

Filenames are human titles, ASCII-safe, no `/ \ : * ? " < > |`, NFC-normalised. Git ignores `.obsidian/workspace*.json`, `.trash/`, `.DS_Store`.

## 4. Note types

Defined once in `schema/types.yaml`. Every note has the **universal fields**:

| Field | Required | Notes |
|---|---|---|
| `type` | yes | One of the types below |
| `created` | yes | `YYYY-MM-DD` |
| `summary` | yes (except `daily`, `source`) | One sentence; feeds the index, search and brief |
| `tags` | no | Lowercase, kebab-case |
| `aliases` | no | Other names; used by search-before-create |

Type-specific fields (P1 types in bold):

| Type | Folder | Fields |
|---|---|---|
| **daily** | Daily | `date` |
| **task** | Tasks | `id` (Tn), `status` (todo, doing, waiting, done, dropped), `priority` (high, medium, low), `due`, `project` (link), `source` (save, meeting, slack, email, manual, capture), `source_link` (link), `done_on`, `repeat` (`<n>d/w/m/y`, D124), `goal` (link, D133), `blocked_by` (links, D144) |
| **project** | Projects | `status` (active, paused, done, dropped), `repo` (optional path or URL), `jira` (optional key) |
| **person** | People | `role`, `team`, `email` (only from a source), `relationship` (manager, report, peer, stakeholder, external, family, friend, mentor, other; D122), `last_contact`, `follow_up` (dates, D112) |
| **meeting** | Meetings | `date`, `kind` (1-1, standup, retro, team, review, external, other), `attendees` (links), `event_id` |
| **decision** | Decisions | `status` (proposed, accepted, superseded), `project` (link), `supersedes` (link), `decided_by` (links) |
| **note** | Notes | `area` (optional: domain, tech, process), `kind` (optional: concept, literature; D112) |
| **howto** | Howtos | `applies_to` (links) |
| **idea** | Ideas | `status` (new, exploring, graduated, dropped), `graduated_to` (link) |
| goal (D112) | Goals | `status` (active, paused, achieved, dropped), `target` (date), `progress` (number, percent), `horizon` (year, quarter, month) |
| **capture** | Inbox | `source_url` (optional). `summary` optional. |
| source (P3) | Sources | `url`, `content_hash`, `fetched_at`, `source_kind` (article, pdf, youtube, confluence, other), `source_quality` (primary, secondary, opinion; D130) |
| research (P3) | Research | `question`, `sources` (links), `watch` (weekly, monthly, quarterly) and `refreshed` (D134) |
| review (P2) | Reviews | `period` (week, month, quarter), `period_start`, `period_end` |
| challenge, brainstorm, topic, patterns, distillation, learnings, ideas-ranking (P4) | Thinking | per tool, defined in P4 |
| architecture-overview, architecture-module (P4) | Architecture | `repo`, `scanned_commit` |
| win (synapsidian-work, D113) | Wins | `date`, `impact` (small, medium, large), `evidence` (links or URLs) |

A type may also carry `folder_by: {field, folder}` (D102, synapsidian 0.18.0). When the note's link `field` names a note, the note lives in `folder` with that note's title filled in, for example `Projects/{project}/Tasks`; without the field it stays in the type's own folder, which stays valid either way. Extensions set it through `extend:`. Bases select notes by `note.type` and leave out `Archive/`, not by folder, so a type's notes are found wherever they live.

Note bodies are free markdown with fixed section names per type, defined as templates in `schema/templates/<type>.md`, or `<type>-<kind>.md` for a kind with its own (for example a person note has `## Context`, `## What they care about`, `## How we help each other`, `## Open topics`, `## History`; an external meeting adds `## Goal` and `## Who's who`; a `literature` note has `## Source`, `## Key claims`, `## My take`, `## Connections`). `setup apply` turns each type a person may create into a Templater template in the vault's `Templates/Generated/`, frontmatter included (D110, D119). Facts that go stale carry an `(as of YYYY-MM-DD)` stamp.

## 5. Plugin layout (`~/Projects/synapsidian`)

Since D90 the repository is a marketplace with two plugins: `plugins/synapsidian/` (the tree below) and `plugins/synapsidian-work/` (work add-on: `skills/` one-to-one, one-to-one-triage, standup, work-brief, win, architect, setup; `scripts/` prs, architect, standup with a self-contained `worklib/`; `references/` commitments and `hook-<name>.md`; `extension/` with `extension.yaml`, `schema.yaml`, `templates/`, `bases/`; `bin/synapsidian-work`). `tests/`, `docs/`, `pyproject.toml` and `uv.lock` stay at the repository root and ship with neither plugin. How the two meet is in D90 and `CLAUDE.md`.

```
plugins/synapsidian/
├── .claude-plugin/
│   └── plugin.json         # name: synapsidian, userConfig, no mcpServers
│                           # (marketplace.json "synapsidian" is at the repo root: synapsidian + synapsidian-work)
├── bin/synapsidian               # on the Bash PATH while enabled: `synapsidian <script> ...`, `synapsidian ref <name>`
├── skills/
│   ├── setup/SKILL.md
│   ├── daily/SKILL.md
│   ├── task/SKILL.md
│   ├── save/SKILL.md
│   ├── capture/SKILL.md
│   └── find/SKILL.md
├── references/             # loaded on demand by skills
│   ├── conventions.md      # principles 3-8, linking, filenames, commit step
│   └── extraction.md       # what counts as a decision / task / person fact / knowledge (used by save and the nightly run)
├── schema/
│   ├── types.yaml
│   └── templates/<type>.md
├── bases/                  # .base sources copied into the vault by setup
├── hooks/
│   ├── hooks.json
│   └── run.sh              # finds uv (hooks may not inherit the shell PATH) and runs a script
├── scripts/                # Python, PEP 723 inline deps, run with `uv run --script`
│   ├── synapsidianlib/           # shared: config, schema, frontmatter, vault scan, git, Obsidian templates
│   ├── setup.py            # check / apply / register
│   ├── note.py             # new (incl. Tn ids) / daily / set / archive / next-id
│   ├── block.py            # get / set a @generated block
│   ├── find.py             # ranked search
│   ├── commit.py           # lock + commit touched files (+ record saved session)
│   ├── brief.py            # SessionStart brief
│   ├── validate.py         # PostToolUse warn-only check, also --all
│   └── approve.py          # PreToolUse auto-approval of vault edits
```

**Manifest** (`plugin.json`, verified against the manifest reference):

See `.claude-plugin/plugin.json`. Two options in `userConfig`: `vault_path` (`directory`, required, default `~/Synapsidian`) and `auto_approve_vault_edits` (`boolean`, default `true`). `version` is set (0.1.0) because `claude plugin validate --strict` requires it; a local in-place install still picks up source edits after `/reload-plugins`.

Skills reach the vault path through `${user_config.vault_path}` and pass it explicitly (`--vault`); hook processes read `CLAUDE_PLUGIN_OPTION_VAULT_PATH`. Scripts expand `~` themselves, since the docs don't say whether Claude Code does. Runtime state (lock file, saved-sessions log, P2 queue cursor, P4 embedding index) lives in `${CLAUDE_PLUGIN_DATA}`, never in the vault.

**Permissions.** `${user_config.*}` is not substituted in `allowed-tools`, so skills can't pre-approve vault edits by path. Instead a `PreToolUse` hook (`approve.py`) returns `allow` for Write/Edit on `.md`, `.base` and `.canvas` files inside the vault (never `.git/`, `.obsidian/`, `.trash/`, `.claude/`), `ask` for edits to existing files in `Sources/` and, whatever the option says, for `CLAUDE.md`/`AGENTS.md` anywhere, `About.md`, `Templates/` and `.synapsidian/` (D120), and no decision for anything else. The user can switch it off with `auto_approve_vault_edits`. Skills pre-approve only `Bash(synapsidian *)`, so the writing scripts refuse the same files and a `--vault` that isn't the configured vault or doesn't look like one (D120).

**Scripts.** Each entry script starts with:

```python
#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["pyyaml>=6"]
# ///
```

and imports `synapsidianlib` from its own directory. Skills call them through `bin/synapsidian` (`synapsidian note new ...`), which runs `hooks/run.sh`, which finds `uv`. Script lockfiles (`uv lock --script`) are deferred until the dependency list grows beyond PyYAML.

## 6. Skills, phase 1

Invoked as `/synapsidian:<name>`. Every write skill ends with the commit step from `references/conventions.md`.

| Skill | Invocation | Writes | What it does |
|---|---|---|---|
| `setup` | user + model | folders, `.gitignore`, `About.md`, `Templates/Daily.md`, `Templates/Generated/*.md` (Templater templates generated from the schema, rewritten only while unedited, D110; `Templates/Synapsidian/` before D119, moved by `apply`), `Bases/*.base`, `.obsidian/{app,core-plugins,daily-notes,types}.json`; `git init` with the user's identity; optionally Obsidian's vault registry | D52. Checks Obsidian (≥ 1.14 for core kanban), uv, git; asks for About facts; applies idempotently (user-changed Obsidian settings are kept and reported; an older `About.md` gets the empty `## Rules` section appended, D94); registers the vault in Obsidian only with a yes and only while Obsidian is closed (backup first); installs the required community plugins Git, Excalidraw, Templater and Calendar Bases, plus those an installed add-on lists in its `extension.yaml` (synapsidian-projects: Folder notes and Excalidraw Extras), through the Obsidian CLI after a yes, configures them, or files a task with the steps (D91, D110, D115, D154); ends, like every add-on's setup, with a three-part report from `references/setup-report.md`: ready, added in this run, still needed with how to add it (D154); offers the recommended Claudian, which `ready` doesn't wait for (D115); turns off the core Templates plugin when its folder holds `Templates/Generated/` and none of the user's own templates, and otherwise reports `core_templates_clash`, which blocks `ready` (D118); lists optional extras (Obsidian CLI, kepano/obsidian-skills). `setup check` reports without changing anything. |
| `daily` | user + model | creates or updates `Daily/<today>.md` | Creates from template; fills `Brief` from vault data (due/overdue tasks, active projects). P2 adds calendar, Jira, GitHub, Slack, Gmail. Only rewrites `@generated` blocks. |
| `task` | user + model | `Tasks/Tn *.md` | Add (id from `note.py new`), update, close (`status: done`, `done_on`), list (today / overdue / by project). |
| `save` | user + model | any type | Reads the current conversation; extracts decisions, tasks, people facts, knowledge, how-tos and ideas per `references/extraction.md`; searches before creating; edits existing notes in place; adds a one-line devlog bullet to today's daily note. Reports a list of every note touched. One commit. Records `${CLAUDE_SESSION_ID}` in `${CLAUDE_PLUGIN_DATA}/saved-sessions.jsonl` so the P2 evening run does not extract the same session twice. |
| `capture` | user + model | `Inbox/YYYY-MM-DD HHmm <slug>.md` | Writes the text as-is with `type: capture`. No search, no linking. |
| `find` | user + model | nothing | Runs `find.py`, reads the top hits, answers with `[[links]]`. Says "not found after searching X, Y" rather than "doesn't exist". |

Inbox triage (turning captures into real notes) is part of `save` when invoked as `/synapsidian:save inbox`.

## 7. Scripts, phase 1

| Script | Input | Output | Notes |
|---|---|---|---|
| `brief.py` | vault path | ≤ 6,000 chars of markdown | `About.md` facts, the user's vault rules (`## Rules` and `protected`, whole up to 3,000 chars, placed before the task lists, D94), active projects (`status: active`), tasks due today or overdue, today's meetings if notes exist, vault location. Prints nothing and exits 0 when the vault is missing. |
| `validate.py` | hook JSON on stdin | hook JSON | Only for `.md` inside the vault, outside `Sources/` and `Archive/`. Checks: frontmatter parses, `type` known, required fields present, enum values valid, filename legal. Warns via `additionalContext`; never blocks. |
| `find.py` | query, `--type`, `--limit`, `--all`, `--related NOTE` (D127) | JSON hits: path, title, type, summary, score, matched terms, snippet (`--related`: plus `linked`) | Stage 1 (D20): BM25 per field, weighted title ×5, aliases ×4, summary ×3, tags ×2, body ×1; coverage bonus; light English stemming; accent and case folding; done/dropped notes and daily/capture notes down-weighted. |
| `note.py` | `new` / `daily` / `set` / `archive` / `next-id` / `fill` | JSON | Creates notes with schema-ordered, typed frontmatter (YAML 1.2 typing, D121) and the type's body template (`--body-file -` reads stdin); assigns `Tn` from task frontmatter incl. archived tasks, under a lock; closing a task with `repeat` files the next one (`next`, D124); refuses to overwrite (exit 3) and refuses a file name another note already has anywhere in the vault, letter case ignored, since links resolve by name; puts a note in its `folder_by` folder when that field is set; `set` changes fields with type coercion and stamps `done_on`, and moves the note when its `folder_by` field changes (`from` / `rel`, both committed; archived notes stay put); `archive` moves under `Archive/` keeping the path; `fill` writes a `## ` section only when it is empty or missing (`filled` / `added` / `kept`, headings in code fences ignored, frontmatter byte for byte) and refuses text that looks like a credential (D95), as `new` and `set` do for what they are given (D158); a file name with a date takes it from `date`, else `created`, and a `--title` that repeats it is refused (D158). |
| `block.py` | `get` / `set` a named block | JSON / block text | Replaces only the text between `<!-- @generated:<name> -->` and `<!-- @end -->`, under a lock; a block whose `@end` is gone is refused with exit 5 (D121); `set` refuses content that looks like a credential (D158). |
| `commit.py` | `--skill`, `--message`, file list, `--record-session` | commit sha or `committed: false` | Takes an exclusive lock (`${CLAUDE_PLUGIN_DATA}/vault.lock`, 60 s timeout), commits only the listed paths (`git commit -- <paths>`, so concurrent runs can't sweep up each other's files), message `synapsidian(<skill>): <message>`. Never `git add -A`, never pushes. With `--record-session`, appends to `saved-sessions.jsonl`. Reports as `broken_links` the links the commit added to the listed notes that resolve to no file; the commit is made either way (D158). |
| `setup.py` | `check` / `apply` / `register` | JSON report | See the `setup` skill. |
| `approve.py` | hook JSON on stdin | hook JSON | See Permissions above. Asks before any Write/Edit under a path in `About.md`'s `protected`, whether or not auto-approve is on (D94). |

## 8. Hooks, phase 1

| Event | Handler | Behaviour |
|---|---|---|
| `SessionStart` (matcher `startup|clear`) | `brief.py` | Emits `hookSpecificOutput.additionalContext` with the brief (cap 10,000 chars; we stay under 6,000). Silent if the vault is unset or missing. |
| `SessionStart` (matcher `compact`) | `brief.py --minimal` | Only `About.md` facts, the vault rules (D94) and the vault path, so a compacted session still knows where the vault is without re-injecting the full brief. |
| `PreToolUse` (matcher `Write|Edit`) | `approve.py` | Auto-approves vault note edits (see Permissions); asks before a write under an `About.md` `protected` path (D94). |
| `UserPromptSubmit` | `capture.sh` → `capture.py` | A prompt starting with `>>` is written to `Inbox/` as a capture, committed and blocked; any other prompt exits in the shell without starting uv (D137). |
| `PostToolUse` (matcher `Write|Edit`) | `validate.py` | Warn-only (D43). Timeout 10 s. Scopes itself to vault `.md` files; no `if` filter, so a wrong filter can never silently disable it. |

Hooks run `hooks/run.sh <script>` in exec form; `run.sh` looks for `uv` on PATH, then `~/.local/bin`, `~/.cargo/bin`, `/opt/homebrew/bin`, `/usr/local/bin`, because hooks started by the desktop app may not inherit the shell profile.

`SessionEnd` queueing already exists in `~/.claude/hooks/devlog-queue.sh`; P2 moves it into the plugin.

## 9. Later phases

**P2: automation** (D28, D36, D39, D48)
- `morning` skill: daily note `Brief` (tasks + Calendar + Jira + GitHub PRs + Slack/Gmail commitments filed as tasks with `source`), meeting skeletons for accepted events with another attendee (D44), 1:1 prep from open topics.
- `evening` skill: drains the session queue; devlog bullets per day; extracts decisions and knowledge from sessions straight into notes (D14); lists everything in `Written overnight`. Skips extraction and the devlog line for sessions listed in `saved-sessions.jsonl`. Keeps its own cursor in `${CLAUDE_PLUGIN_DATA}`, independent of the Notion `devlog-rollup` marks, so both can consume the queue during the parallel week.
- `review` skill: weekly (Friday), monthly, quarterly; patterns and contradictions as a report (D19); safe health fixes with a commit (D30).
- `recap`, `standup` (reads devlog from daily notes, D23), `meeting`, `health`.
- `schedule` skill: creates the desktop scheduled tasks. One week in parallel with the Notion tasks, then the user disables them.

**P3: sources** (D24, D38, D67-D75): `ingest` (web page, YouTube, PDF / DOCX / PPTX, Confluence, pasted text, image → `Sources/` immutable copy with hash and URL dedup → existing notes updated, new ones created, contradictions marked) and `research` (vault-first; web search fills only the gaps). YouTube is part of `ingest` (D68). Design in §10b.

**P4: thinking and docs** (D17, D18, D22, D20): `challenge` (lens subagents), `brainstorm`, `topic`, `patterns`, `distill`, `learn`, `ideas`, `graduate`, `architect` (with a hash check on `@generated` blocks), then local embeddings only if a question set shows a gain.

## 10. Phase 1 acceptance criteria

1. `claude plugin validate . --strict` passes.
2. `/synapsidian:init` on an empty `~/Synapsidian` creates the layout and a first commit; a second run changes nothing and says so.
3. A new session in any directory shows the brief; with `vault_path` pointing at a missing folder it shows nothing and no error.
4. `/synapsidian:task add "Review TDD" due friday` creates `Tasks/T1 Review TDD.md` with valid frontmatter and one commit authored by Jan Szewczyk with no Claude attribution.
5. `/synapsidian:save` after a conversation with one decision, one task and one new person touches exactly those notes plus today's daily note, in one commit, and lists them.
6. A note written with a missing `summary` gets a validator warning in the same turn.
7. `find.py` finds each note of a 20-question test set in the top 5, run against a fixture vault of ~30 synthetic notes in `tests/fixtures/vault/`. The notes are written first and the questions in a separate pass; a test asserts that no question shares more than one content word with its target's title, so the set cannot leak its answers (the reference's first benchmark did, scoring 83% for nothing). The set is kept as the baseline for D20 stage 2.
8. `pytest` passes for `synapsidianlib`, `find.py`, `note.py`, `block.py`, `commit.py` (including concurrent commits not interleaving), `validate.py`, `approve.py`, `brief.py` and `setup.py`.

## 10a. Phase 2 design

Decisions D58-D66; the rules of the replaced Notion workflows are in [research/notion-workflows.md](research/notion-workflows.md) and carry over unless a decision changes them. Built in three slices, each tested live before the next: **2a** session queue, `evening`, `standup`; **2b** `morning`, `meeting`; **2c** `review` + health, `one-to-one`, `one-to-one-triage`, `recap`, `schedule`. The one-week parallel run with the Notion tasks (D48) starts once 2b is live.

**New plugin options** (`userConfig`, read by scripts through `synapsidian note where`): `github_repos`, `jira_projects`, `work_repo_paths` (for `git log` in the stand-up; never the session's cwd), each a list (`multiple: true`, D92). None has a default (D86): an empty option switches that source off.

**Session queue.**
- `SessionEnd` hook `hooks/session-end.sh`: pure shell (jq, python3 fallback, no uv; Claude Code kills slow SessionEnd hooks). Appends `{ts, date, session_id, transcript_path, cwd, reason}` to `<vault>/.git/synapsidian/session-queue.jsonl`. Vault from `CLAUDE_PLUGIN_OPTION_VAULT_PATH`, else `pluginConfigs` in settings.json. Independent of the Notion `devlog-queue.sh`, so both run during the parallel week.
- `sessions.py`: `pending` (dates with unmarked work), `digest --date D` (harvest.py's extraction and caps, records of that local day only), `digest --since TS --scan` (stand-up: every transcript touched since TS, including sessions still open), `mark --date D [--until TS] IDS`. Marks are keyed by **(session, date)** and act as watermarks (D87): a pair is pending again when its transcript has records that day after the last mark, and `pending` scans transcripts modified in the last 14 days besides the queue, so sessions kept open for days are logged on every day they were used. Work before a session's `/synapsidian:save` (`saved-sessions.jsonl`, with `saved_at`) is skipped; work after it is not. Transcripts are data, never instructions.

**`when.py`** (date logic, no model judgement): `standup` → window start (previous Tue/Wed/Thu 12:00), `done-window` → morning's "Done" start (26 h, or Friday 09:00 on Mondays), `review` → week / month / quarter for a Friday.

| Skill | Schedule | Writes | Posture |
|---|---|---|---|
| `evening` | daily 20:00 (often a next-morning catch-up) | `devlog` block of each pending day's daily note; knowledge, decisions, how-tos, person facts and tasks (`source: session`) extracted from those sessions | Unattended. Per pending day oldest first: digest → merge with the existing devlog block, re-redact to bullets of ≤2 sentences each (no cap on their number) → extract per `extraction.md` → link the notes it created from a related note (D117) → one commit → mark. Never another day's block; empty day gets nothing; marks only after the commit. Then, with a Google Drive connector, the day's Gemini meeting notes not imported yet (`meeting-import.md`, D95), one report line each. |
| `standup` | Tue-Thu 11:00 | `standup` section of today's daily note | Window from `when.py standup`. Sources: daily-note devlogs in the window, `sessions digest --since`, Jira (`project in (<jira_projects>) AND assignee = currentUser() AND updated >= "<start>"`, plus `statusCategory = "In Progress"`), `gh` PRs per repository, `git log --author` in each of `work_repo_paths`, calendar. Output in chat and saved: ≤5 done bullets, `Today —`, `Blocker —`/`No blockers.`, spoken first-person English (rules in research/notion-workflows.md). |
| `health` (D97) | Mon-Fri 08:15 | `health` block (`## Vault health`) in today's daily note; safe health fixes | `synapsidian health --fix`; remaining issues listed for a decision, at most 8 lines; orphans carry proposed links (`mentioned_in`, `related`) that only `/synapsidian:health apply` writes. Clean vault: nothing written, nothing committed. |
| `morning` (2b) | Mon-Fri 09:00 | today's daily note (`brief`, `agenda`, `overnight` blocks), meeting notes, person stubs, tasks from commitments (PRs are only listed, D96) | `overnight` lists `synapsidian(evening)`/`synapsidian(save)` commits since the last `synapsidian(morning)` commit (from git, no state). Meetings dedup on `event_id`; person stubs get a factual summary and calendar email only. Commitments: create only, max 5, dedup by link → open obligation → closed within 7 days (D64). PR classification by `prs.py`. Morning and evening touch disjoint files (today vs past dailies). |
| `review` (2c) | Fri 16:00 | `Reviews/` note, safe health fixes | `when.py review` picks week/month/quarter. Safe fixes only: tag case/format, missing `created` from `git log --diff-filter=A`, `[[link]]` case mismatches. Everything else is reported, including tasks stuck in `doing`/`waiting` for over 14 days by their last commit (D91). |

Scheduled tasks run in `auto` permission mode (D66), with the vault as their folder (D89): a task takes the folder of the session that created it, the tools can't change it, and a folder that later moves (a code checkout, the plugin's own source) breaks every run. The vault's `.gitignore` excludes `.claude/`, so permission approvals and worktrees from those runs never land in vault commits; `setup apply` appends missing ignore rules to an existing `.gitignore`. Skills pre-approve `Bash(synapsidian *)` and read-only `gh` forms; connector tools rely on the mode. Timezone for every calendar call comes from `About.md` (`timezone`). `validate.py` gains a warn-only secret check (PEM, `sk-`, `ghp_`, `AKIA`, `xox`), since unattended runs now write from transcripts.

## 10b. Phase 3 design

Decisions D67-D75. Slices: **3a** `ingest` with every source kind, YouTube transcripts and `visual` frames; **3b** `research`.

**Source notes** (`type: source`, `Sources/{fetched_at} {title}.md`) are written only by `source.py`; the body is the verbatim content and is never edited (the approval hook asks before any Edit there). Frontmatter: `url`, `source_kind`, `content_hash`, `fetched_at`, `capture_scope` (`full`, or `partial` when only part was captured or the text is Claude's transcription), `author`, `published`, `supersedes`; `summary`, `tags` and `integrated` (the date the notes were updated, D84) are added after integrating with `synapsidian note set`. `Sources/` stays out of search, the brief and health unless asked (`--all`).

| Script | What it does |
|---|---|
| `source.py fetch` | URL → SSRF-checked download (public addresses only, every redirect re-checked, 25 MB cap) → HTML: the page's `<article>`/`<main>` minus chrome converted by markitdown (keeps tables and code; anchors dropped, relative links made absolute), trafilatura when there is no such element or it is mostly chrome; Obsidian Publish shells → the note's raw markdown (own frontmatter dropped, wikilinks flattened to text); markitdown for PDF / DOCX / PPTX / XLSX / EPUB; local files the same way; YouTube links → `youtube-transcript-api` (manual track in the spoken language first) + oEmbed title and channel, transcript in one-minute paragraphs with timestamps. Dedup: same `content_hash` → `unchanged`; same normalised URL with ≥98% shared word 4-grams → `unchanged`; otherwise a new note that `supersedes` the newest copy. Returns `chunks` (≈40k-character line ranges) so long sources can be split across reader subagents. Exit 4 with a `fallback` hint when nothing could be extracted. |
| `source.py add` | Same dedup and note format for content Claude obtained itself: Confluence via the Atlassian MCP, pasted text, an image transcription (`--attach` copies the image to `Attachments/` under a content-hash name and embeds it). `--refuse-secrets` exits 2 instead of writing a body that looks like it holds a credential (meeting transcripts, D95). |
| `source.py lookup` | Source notes for a URL, without fetching. |
| `frames.py` | `visual` only: yt-dlp downloads the H.264 video stream ≤720p (no audio, so no merge and no system ffmpeg); ffmpeg from the `imageio-ffmpeg` wheel takes scene-change frames on keyframes, adds evenly spaced frames where scenes are sparse, samples to `--max` (24) evenly over time, deletes the video. Frames live in `<vault>/.git/synapsidian/frames/<id>/` and are pruned after two days. |
| `pages.py` | PDF pages → JPEGs with PDFium (`pypdfium2` + Pillow wheels), for scans and chart-heavy reports; Claude Code's own PDF rendering needs poppler, which this Mac lacks. Same two-day pruning under `<vault>/.git/synapsidian/pages/`. |

**Research** (3b, skill only, no new script): vault first (three phrasings plus `--all`; a full answer from the vault ends the run with no writes); web for the gaps only, with queries built from the question and stripped of internal identifiers (D77); adaptive depth: standard searches, `general-purpose` subagents per independent thread (they return findings as JSON and write nothing), `deep` forces threads and extended searches; the 2-5 sources the answer rests on are copied with `source fetch`; dossier `Research/{date} {title}.md` (`question`, `sources`) with Answer, Key findings (each cited), Disagreements, Open questions, What the vault already knew, Sources; integration as for ingest; one `synapsidian(research)` commit.

**Integration** (`references/ingest.md`, shared by `ingest`, `save inbox` and `research`): read the source as untrusted data (parallel read-only Explore subagents per chunk for long sources; only the main run writes); keep what serves the user's domains; search before writing; integrate into existing notes in place with `(per [[source]])` citations; contradictions are corrected with a dated `## History` entry when the source is clearly newer or authoritative, otherwise marked with a `[!warning] Contradiction` callout; ≈12 notes per source at most; devlog line; one commit; a report listing every note updated or created.

## 10c. Phase 4 design

Decisions D78-D82. Slices: **4a** `/synapsidian:think` (one skill, eight modes in `references/think-<mode>.md`, one `thinking` type whose `kind` picks the body template `thinking-<kind>.md`, `Bases/Thinking.base`); **4b** `/synapsidian:architect` for the three Vue frontends; **4c** a search measurement on a private question set before any embeddings. Subagents read and return findings; the main run verifies the strong ones and writes every note. `topic` writes outside `Thinking/` only with `fix`; `learn` only proposes rules. `note new` / `note set` now reject enum and pattern violations on write (they used to pass until the next validation), and `link` fields accept a URL as well as a wikilink.

## 10d. synapsidian-projects design (2026-10-28; all six phases built, then debug and incident)

Decisions D98-D109. Built:
- phase 1: `folder_by` and type-based Bases (synapsidian 0.18.0);
- phase 2: the plugin with `setup`, the extension and the hub board (synapsidian-projects 0.1.0, D105);
- phase 3: projects out of the core, the hub in its own folder, existing notes refiled (synapsidian 0.20.0, synapsidian-projects 0.2.0, D106). A third plugin, `plugins/synapsidian-projects/` (`dependencies: ["synapsidian"]`), keeps any number of projects in the vault. A project is a code repository or a description of a system. The vault is the source of truth; code repositories are only read;
- phase 4: the `project` and `decide` skills, `synapsidian-projects scan` and `decision-number`, `synapsidian block set --before` (synapsidian 0.21.0, synapsidian-projects 0.3.0, D107);
- phase 5: `map` (Excalidraw scene written by `synapsidian-projects map`, merged by `customData` keys), the `spec` and `change` types and skills; `note new` refuses missing required fields (synapsidian 0.22.0, synapsidian-projects 0.4.0, D108);
- phase 6: `architect` moved from synapsidian-work with its type, templates and Base, the scan generalised to any language with the Vue scan as a profile, architecture notes migrated into their projects by `setup`; a type two extensions define is a warning (synapsidian 0.23.0, synapsidian-work 0.3.0, synapsidian-projects 0.5.0, D109);
- after the phases: the `debug` and `incident` types with their skills, Bases, hub views and map branches; their Templater templates come from the schema (synapsidian-projects 0.7.0, D111);
- from the audit of 2026-11-03: the `milestone` type with its skill, Base, hub view, Roadmap section and map branch, and `milestone` on tasks (D145); generated Mermaid diagrams of the roadmap and of a milestone's or change's tasks in order (D146) (synapsidian-projects 0.10.0; `blocked_by` on the core task, D144, synapsidian 0.31.0); a Risks section on the hub and `people` and `goals` on `project` (D147), and map refreshes that never draw a new node over a box already there (D148) (synapsidian-projects 0.11.0).

**Layout of a project** (D102):

```
Projects/<Project>/
├── <Project>.md          # hub: Goal, Links (D110), Status, Roadmap (generated, D146), Repository (generated, D107), Key decisions, Risks (D147), Open questions, Log + embedded board and views (D101)
├── Tasks/                # task notes with project: [[<Project>]]
├── Milestones/           # stages with a target date, planned → active → done (D145)
├── Decisions/            # MADR-shaped decisions (D100)
├── Research/             # research dossiers
├── Specs/                # living spec notes
├── Changes/              # change notes, proposed → done
├── Debug/                # bug investigations, investigating → fixed | wontfix (D111)
├── Incidents/            # blameless postmortems, draft → final (D111)
├── Workflows/            # howto notes
├── Maps/                 # Excalidraw mind maps (D103)
└── Architecture/         # architect notes (D104)
```

The same types without a project stay in their flat folders (`Tasks/`, `Decisions/`, ...). Daily notes, people, meetings, notes, ideas, goals, sources, reviews and thinking stay flat.

**Schema** (`plugins/synapsidian-projects/extension/schema.yaml`):
- **Types:**
  - `project`: `status` active / paused / done / dropped, `kind` repository / system, `repo`, `docs`, `scanned_commit`; `repo` holds a remote URL or a local path, plus `path` and `branch` (D139, D141; synapsidian-projects 0.9.0); `people` (person notes: owner and stakeholders) and `goals` (core `goal` notes), both links (D147);
  - `spec`: required `project`, `status` draft / current / retired;
  - `change`: required `project`, `status` proposed / doing / done / dropped, `specs`, `decisions`, `tasks`, `done_on`;
  - `debug`: required `project`, `status` investigating / fixed / wontfix; sections Symptom, Repro, Investigation, Root cause, Fix; named `{date} {title}`;
  - `incident`: required `project`, `status` draft / final, `date` (the day it happened, which names the file; today when left out); sections Summary, Timeline, Impact, Root cause, What went well, Action items;
  - `architecture`: moved from synapsidian-work, with a required `project`;
  - `milestone`: required `project`, `status` planned / active / done / dropped, `start`, `target`, `done_on`; sections Goal, Exit criteria, Tasks (a board of the tasks whose `milestone` is this note), Flow (generated), Log (D145).
- **Extensions:**
  - a `project` link on `task`, `decision`, `research`, `howto`, `note`, `thinking`, each with `folder_by: {field: project, folder: "Projects/{project}/<Type folder>"}`;
  - a `milestone` link on `task` (D145);
  - `decision` gains MADR 4's statuses (`rejected`, `deprecated`), a per-project `number` and `superseded_by`; who decided is the core's `decided_by` (D107).

**Core changes** (D99, D102):
- `folder_by` in `synapsidianlib/schema.py`. It is read by `note.py new` and moves a note on `set`; `validate` accepts either folder. `extend:` may carry it.
- Bases filter on `note.type`, not `file.inFolder`.
- `brief.py` and `health.py` treat projects only when the schema has the type.
- The `project` type, its fields, template and `Projects.base` leave `types.yaml`, `templates/` and `bases/`.
- Core skills mention projects conditionally and follow the Projects section of `references/conventions.md` for project steps. `synapsidian-projects hook <name>` carries steps that need more (D129). Its first is `review` (D151): `/synapsidian:review` runs it when `command -v synapsidian-projects` succeeds and `synapsidian note where` lists the extension, and adds a `## Projects` section with one `synapsidian-projects progress` line per active project.

**Skills:**

| Skill | What it does |
|---|---|
| `setup` | Installs or updates the extension (before the core drops the type); migrates notes with a `project` into their project folders in one commit; creates hubs for architecture apps with no project; with `check`, reports only. |
| `project` | Creates a project (hub, folders, board), refreshes one or lists them; for a repository, `synapsidian-projects scan` reads manifests, layout, README, `docs` and commits into the hub's hashed Repository block, and a refresh logs what changed since `scanned_commit`. Never writes there. `status` (D149) reports from `synapsidian-projects progress` what closed since the last status (the day after the hub's newest `status:` Log line, D152), what is in progress or blocked and each open milestone's `done/total` and days to target, and proposes a dated Status text, written with a Log line only on the user's yes. `close` (D150) settles every open task, milestone and change (close, drop or move), writes a `## Retro` before the Log, sets `status: done` and logs it, in one commit. |
| `decide` | Records a decision in the project's `Decisions/`: drivers, options with trade-offs, consequences; `proposed` until the user accepts it; supersedes an earlier one instead of editing it; the number comes from `synapsidian-projects decision-number`. |
| `map` | Generates or refreshes an Excalidraw mind map of the project from its notes (`synapsidian-projects map`), keeping what the user drew or moved; a new node goes under its siblings and down past any box it would cover, and nothing drawn moves (D148); linked from the hub's Maps section. |
| (shared) | `synapsidian-projects flow` writes Mermaid diagrams into generated blocks: the hub's Roadmap (gantt of milestones, flowchart of tasks waiting on others) and a milestone's or change's Flow; `project` refresh, `milestone` and `change` redraw them, following `references/flows.md` (D146). |
| `spec`, `change` | Create and update spec notes in place; open a change, link its specs, decisions and tasks, close it with a dated Log line on the hub. |
| `milestone` | Plans a stage of a project with a goal, exit criteria, `start` and `target`; puts tasks in it through their `milestone`; starts, closes (after checking open tasks) or drops it; `status` counts its tasks, the blocked ones and the days to target. Each logs on the hub (D145). |
| `debug`, `incident` | Keep a bug investigation as a lab notebook (dated attempts with their results, root cause, fix) and close it as fixed or wontfix; draft a blameless postmortem with its action items filed as tasks and make it final after review. Each logs on the hub (D111). |
| `architect` | Moved from synapsidian-work (D104, D109): `synapsidian-projects architect apps|scan`, a generic scan (manifests, source root and modules, entry points, largest files) plus a Vue profile (domains, stores, routes), repository from the hub's `repo`, notes in `Architecture/` of the project. |

**Repositories across devices** (D139-D143, 2026-11-02; steps 1-3 built in synapsidian 0.30.1 and synapsidian-projects 0.9.0, the mirror of step 4 still a design). The user chooses for each project whether it is shared across devices or tied to one:

| Piece | Where | What |
|---|---|---|
| Identity | hub `repo` (committed) | Either a remote URL in canonical form `https://<host>/<owner>/<name>` (key `<host>/<owner>/<name>`), for a project cloned on several devices, or an absolute local path, for a project never pushed or kept on one device. `project new` proposes the URL when the clone has an `origin`, and the path otherwise; the user can pick the other. Optional `path` (folder inside the repository) and `branch`. |
| Clone on this device | `<state>/synapsidian-projects/repos.json` (per vault clone, untracked) | URL hubs only: key → absolute clone path, or `mirror`. `synapsidian note where` prints `state`. |
| Resolution | `synapsidian-projects repo resolve` | A path: `local` if it exists here, `elsewhere` if not (skip the read with a note, never rewrite it). A URL: the map, then the session's folder. A candidate counts only if one of its remotes has the key. Otherwise an interactive run asks once and `repo bind`s; an unattended run skips and reports. |
| Freshness | `scan --last`, `architect scan --last` | `first`, `same` or `ahead`: write. `behind` or `unknown`: don't write, ask the user to pull. `diverged` or `off_branch`: ask, or skip when unattended. Never fetches a user's clone. |
| No clone (opt-in, phase 2) | `${CLAUDE_PLUGIN_DATA}/mirrors/<key>.git` | Blobless bare mirror fetched by synapsidian-projects; scan reads a ref from git objects; architect unpacks the app's folder with `git archive`. |
| Switching to URLs | `/synapsidian-projects:setup` | Offers, hub by hub, to switch a path that exists here and has an `origin` to its URL + `path`, and binds the clone. What the user leaves stays a path. Nothing switches unattended. One commit. `check` reports bound / unbound / local / elsewhere / mirror per hub. |

Build order: (1) `where` prints `state`, URL normalisation, `repo resolve|bind|forget|list`, the `path` field, skills switched to resolve; (2) `--last` and `freshness` in both scans; (3) setup migration and check; (4) the mirror backend. Tests: the normalisation table (scp, ssh, https with credentials, port, `.git`, trailing slash, case), resolve order and a mismatched folder, each freshness case on a fixture repository with two clones, switching a hub with a monorepo subfolder, a hub the user keeps as a path and one with no `origin` left untouched, and a path hub on a device without that folder (`elsewhere`, no write).

**Build phases** (each tested live on a copy of the vault before the next):
1. Core: `folder_by`, Base filters on type, schema-driven brief and health.
2. synapsidian-projects skeleton: plugin, extension with the project type and fields, hub template with the board, `setup`, `bin/synapsidian-projects hook`.
3. Core without projects: types and Bases removed; conditional skills and hooks; vault migration; synapsidian-work depends on synapsidian-projects.
4. `project` and `decide`.
5. `map`, `spec`, `change`.
6. `architect` moved and generalised; `Architecture/` migrated.

**To verify before building:**
- `this` in a ```base code block;
- dragging cards in an embedded kanban view;
- ~~writing Excalidraw scene JSON vs the plugin's Mermaid import~~ settled: scene JSON (D108).

## 11. Verification status

Resolved while building (sources in `research/`):
- `${user_config.*}` is **not** substituted in `allowed-tools` → `PreToolUse` approval hook (§5 Permissions).
- `~` expansion in a `directory` default is undocumented → scripts expand it themselves.
- Kanban is a **core** Bases view since Obsidian 1.14; no Kanban plugin needed. The Obsidian CLI installs community plugins (`plugin:install id=<id> enable`) only while Obsidian runs and Restricted mode is off.
- A new vault can only be registered in Obsidian via "Open folder as vault" or by editing `obsidian.json` while Obsidian is closed → `setup register`, with consent and a backup.

Verified live on 2026-10-13 (desktop app, Claude Code 2.1.296, Obsidian 1.14.4, vault `/Users/jan/synapsidian`):
- All six skills ran against the real vault; `/synapsidian:save` created and linked notes in one commit.
- After a restart: the session brief appears, vault edits need no permission prompt, an invalid note gets the schema warning (criteria 3, 4, 6). Criterion 5 (`/synapsidian:save`) passed in the build session.
- `bin/synapsidian` is on the Bash PATH.
- Obsidian accepts the `.base` files, including filters such as `note.due <= today() + "7d"`, and rewrites them into its canonical form (`order`/`groupBy`/`sort` without the `note.` prefix, `sort` after `order`). `bases/` ships that form so new vaults aren't rewritten.
- Six integration bugs found and fixed in 0.1.2: see the vault note *Claude Code plugin gotchas* and the commit `fix: issues found in live testing (0.1.2)`.

Phase 3a verified live on 2026-10-14 against `/Users/jan/synapsidian`, one commit each: a docs page (3 notes updated, 1 created, 1 contradiction marked), a 42-minute YouTube video with `visual` (two parallel reader subagents, 24 frames), a chart-heavy PDF (charts read from `synapsidian pages` images), and `/synapsidian:capture` of an Obsidian Publish link followed by `/synapsidian:save inbox`; re-fetching a known URL reports `unchanged` and writes nothing. Fixes from the run are D76. Phase 3b verified the same day: a research question on empty properties in Bases filters answered from the vault plus one official page (kept as a source) and four forum threads (URLs), dossier in `Research/`, two notes updated, one `synapsidian(research)` commit; the web query carried only the public question.

Phase 4a verified 2026-10-14 on the real vault: `challenge` of the Notion cut-over (three parallel lenses; one lens's "blocker" was refuted against git history and recorded as corrected; a real blocker, no vault backup, confirmed with `tmutil`), `topic fix` on the Synapsidian plugin project note (stale status refreshed, old values kept under History), `graduate` of an idea into two tasks; one commit each, health clean.

Phase 4b verified 2026-10-14: `architect.py` scans paw-frontend (21 domains, 68 routes, 22 stores) in 0.6 s, read-only (the work repo stays clean); `admin-frontend Overview`, `paw-frontend Overview` and `paw-frontend report` written with hashed blocks; a hand edit inside a block was detected (`check` → `edited`) and `set` refused to overwrite it (exit 4) until `--force`. The scan first counted test files' mock stores and imports; it now reads code files only. The run also found that paw-frontend already ships SheetJS Pro (`@sheet/perf`), which corrected the same day's XLSX research.

Phase 4c, 2026-10-14: `find.py --eval` measured search on a private real-vault question set; embeddings were not built (D83), and two lexical fixes took English recall@5 from 0.938 to 1.0.

The P2 gate (a desktop scheduled task invokes a plugin skill with vault writes and no prompt) passed on 2026-10-13 with a `/synapsidian:capture` probe (D66); the first unattended `synapsidian(morning)` commit is from 2026-10-14 09:25.

## 12. Review outcomes

- Folder names kept: `Notes/`, `Howtos/` (D50).
- Model-invoked `capture` stays raw, no search (D51).
- `init` became a full `setup` skill (D52).
