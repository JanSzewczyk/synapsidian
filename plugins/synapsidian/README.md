# Synapsidian

A second brain in an Obsidian vault, for any vault: personal or work. It covers daily notes and briefs, tasks, meeting and people notes, decisions, knowledge, how-tos and ideas, captured from your Claude Code sessions and kept current. Every change Claude makes is a git commit in the vault, so you can see and undo it. Nothing in it assumes a job: work features come with the `synapsidian-work` add-on, projects with `synapsidian-projects`.

## Requirements

- [Claude Code](https://claude.com/claude-code) on macOS
- [Obsidian](https://obsidian.md) 1.14 or later (core Bases with kanban)
- [uv](https://docs.astral.sh/uv/), which runs the Python scripts and fetches Python 3.12+ and each script's libraries itself
- git

`/synapsidian:setup` installs and configures four Obsidian community plugins: Git, Excalidraw, Templater and Calendar Bases. It also lists whatever an installed add-on requires, and offers Claudian as a recommended extra. Why each one: [references/obsidian-plugins.md](references/obsidian-plugins.md). No API keys, no MCP server.

## Install

```
/plugin install synapsidian@synapsidian
```

Claude Code asks for the vault path. Then, in a new session (hooks of a newly installed plugin load at session start):

```
/synapsidian:setup
```

It checks Obsidian, uv and git, creates the vault layout, configures Obsidian, makes the vault a git repository, asks a few questions for `About.md`, and ends with a report of what is ready, what it added and what is still needed.

## Options

| Option | What it does |
|---|---|
| `vault_path` | Absolute path of the Obsidian vault (default `~/Synapsidian`) |
| `auto_approve_vault_edits` | Note edits inside the vault need no permission prompt; `About.md`, `Templates/`, `CLAUDE.md` and `.claude/` always ask (default on) |
| `session_exclude_paths` | Folders or glob patterns whose Claude sessions never reach the devlog; a single session opts out with `#off-the-record` |

Your own rules for Claude go in the `## Rules` section of `About.md`, and folders Claude must ask about before touching go in its `protected` property. Both override synapsidian's defaults.

## Skills

| Skill | What it does |
|---|---|
| **setup** | `/synapsidian:setup [check]`: set up, repair or check the vault, Obsidian config and the session-capture hooks (`synapsidian setup selftest` drives them end to end) |
| **daily** | `/synapsidian:daily`: create today's note and fill its brief (overdue, due, in progress, the week ahead) |
| **task** | `/synapsidian:task`: add, update, close or list `Tn` tasks; a task with `repeat` (`1w`, `1m`, ...) files its next occurrence when closed; a task with `blocked_by` waits on other tasks, shows as blocked in the brief while one is open, and closing a blocker names the tasks it frees |
| **save** | `/synapsidian:save [inbox]`: file decisions, tasks, people facts, knowledge, how-tos and ideas from the conversation (or the Inbox) into the right notes, plus a devlog line |
| **capture** | `/synapsidian:capture`: drop text into `Inbox/` as is; quicker still, start any prompt with `>>` and a hook saves it there without asking Claude |
| **find** | `/synapsidian:find`: search the vault and answer with `[[links]]`; "what relates to X" lists the notes most like it (`synapsidian find --related`) |
| **ingest** | `/synapsidian:ingest`: take in a web article, YouTube video (`visual` also reads its frames), PDF / DOCX / PPTX, Confluence page, pasted text, image, or a whole folder a batch at a time: verbatim copy in `Sources/`, then existing notes updated, new ones created, contradictions marked once the quote is checked against the copy (`synapsidian source quote-check`) |
| **research** | `/synapsidian:research`: answer a question from the vault first, then the web for the gaps only; dossier in `Research/` with citations, the 2-5 key sources kept in `Sources/`, findings worked into existing notes (`deep` for a broad sweep, the `/synapsidian:research-deep` workflow to cross-check every claim; `watch` a dossier to have it refreshed weekly, monthly or quarterly) |
| **think** | `/synapsidian:think <mode>`: `challenge` (parallel lenses stress-test a decision), `brainstorm`, `topic` (synthesis, contradictions, stale facts, gaps; `fix` applies corrections), `patterns`, `distill`, `learn` (proposed CLAUDE.md rules, never applied), `ideas`, `graduate` (idea into a project or tasks); results in `Thinking/` |
| **morning** | `/synapsidian:morning`: today's brief (needs attention, done, coming up, up to three old `(as of ...)` facts to confirm, one old note from the archive), agenda with meeting skeletons, overnight changes; with synapsidian-work also PRs, Jira and asks (scheduled weekdays 09:00) |
| **meeting** | `/synapsidian:meeting`: meeting note from a calendar event, with people linked; `import` fills it from the call's Gemini notes (Google Drive) and files your next steps as tasks without duplicates |
| **evening** | `/synapsidian:evening`: turn the day's Claude Code sessions into devlog bullets and file what they decided or taught, plus what Claude Code's own memory files picked up (scheduled 20:00) |
| **review** | `/synapsidian:review`: weekly (Fri 16:00), monthly or quarterly review note: done, decisions, open threads, patterns, contradictions, vault health with safe fixes; with synapsidian-projects, a line per active project (what closed, what is in progress or blocked, the next milestone) |
| **health** | `/synapsidian:health`: vault health, weekdays 08:15: safe fixes (tags, `created`, link case) applied; broken links, wanted notes (missing notes several notes link to), orphans with proposed places to link them, schema problems and duplicates listed in today's daily note; `apply` links the orphans you pick |
| **recap** | `/synapsidian:recap`: summary of any period in chat, read only |
| **schedule** | `/synapsidian:schedule`: create or check the scheduled runs (health, morning, evening, review) |

The run times are defaults; `/synapsidian:schedule` sets them and you can move them.

## Hooks

- At session start, a short brief of who you are and what's due.
- Every finished session is queued for the evening run (`<vault>/.git/synapsidian/session-queue.jsonl`).
- A `>>` prompt is captured to the Inbox.
- A schema warning when a note is written with missing or invalid fields.
- Note edits inside the vault are approved automatically (option `auto_approve_vault_edits`), except `About.md`, `Templates/`, `CLAUDE.md` and `.claude/`, which always ask.

Text inside `<private>...</private>` is left out of every digest.

`synapsidian brief --json` prints the session brief's lists as data, for tools that draw them.

## Add-ons

Add-ons install their own schema extension into the vault's `.synapsidian/extensions/<name>/`, and core skills reach them only through `<add-on> hook <name>`. Without an add-on, nothing in synapsidian mentions it.

- `synapsidian-work`: 1:1s, the stand-up, a win log, pull requests, Jira, email and Slack asks.
- `synapsidian-projects`: a hub with a kanban board per project, milestones, decisions, specs, changes, bug investigations, postmortems, architecture notes and mind maps.
- `synapsidian-dock`: a Claude Code mod with the brief in a band above the prompt and a task pane whose keys change a task without a Claude turn. It installs no schema extension; it only calls `synapsidian`.
