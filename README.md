# Synapsidian

Claude Code marketplace for an Obsidian second brain: the synapsidian plugin manages your vault, synapsidian-projects and synapsidian-work extend it for projects and work.

Claude Code plugins that keep a second brain in an Obsidian vault: daily notes, tasks, meeting and people notes, decisions and knowledge, captured from your Claude sessions and kept current. Every change Claude makes is a git commit in the vault, so you can see and undo it.

Four plugins in one marketplace:

- **`synapsidian`**: the core, for any vault, personal or work. Nothing in it assumes a job.
- **`synapsidian-work`**: an optional work add-on on top of `synapsidian`: 1:1 notes, the stand-up note, pull requests, Jira, asks from email and Slack in the morning brief.
- **`synapsidian-projects`**: an optional projects add-on. Each project gets a hub note with its own kanban board of tasks, and its tasks, decisions, specs, changes, bug investigations, postmortems, architecture notes, research, workflows, notes, thinking and mind maps are filed under `Projects/<Project>/`. Code repositories are only ever read. Install it with `/plugin install synapsidian-projects@synapsidian`, then run `/synapsidian-projects:setup`.
- **`synapsidian-dock`**: an optional Claude Code mod: the brief in a band above the prompt, with a Tasks button to a pane whose keys close, start, move or drop a task without a Claude turn; `/synapsidian` shows the band. Install it with `/plugin install synapsidian-dock@synapsidian`; it needs Claude Code 2.1.299 or later and no setup.

Inspired by [eugeniughelbur/obsidian-second-brain](https://github.com/eugeniughelbur/obsidian-second-brain), rebuilt for current Claude Code plugin features: skills with progressive disclosure, a single note schema, scripts for the mechanics and Claude for the judgement. See [docs/spec.md](docs/spec.md) for the design and [docs/decisions.md](docs/decisions.md) for why.

## Requirements

- macOS, [Claude Code](https://claude.com/claude-code)
- [Obsidian](https://obsidian.md) 1.14 or later (core Bases with kanban); `brew install --cask obsidian`
- [uv](https://docs.astral.sh/uv/) (runs the Python scripts; it fetches Python 3.12+ and each script's libraries itself, e.g. trafilatura, markitdown, youtube-transcript-api, pypdfium2, and for `visual` yt-dlp with a bundled ffmpeg)
- git
- synapsidian-work only: [`gh`](https://cli.github.com) for pull requests, the Atlassian connector for Jira, Gmail and Slack connectors for asks

Four Obsidian community plugins are required and set up by `/synapsidian:setup`: Git (history for your own edits), Excalidraw (drawings), Templater (notes you make by hand, from templates synapsidian generates in `Templates/Generated/`) and Calendar Bases (calendar views of tasks, meetings and goals). synapsidian-projects adds Folder notes (a click on a project's folder opens its hub) and Excalidraw Extras (Mermaid diagrams turned into editable drawings). Every setup ends with a short report: what is ready, what this run added, and what is still needed, with how to add it. Setup also offers Claudian, Claude Code in Obsidian's sidebar, as a recommended extra. Why each, and the optional ones: [plugins/synapsidian/references/obsidian-plugins.md](plugins/synapsidian/references/obsidian-plugins.md). No API keys, no MCP server.

## Install

From a Claude Code session, with the path of your clone of this repository:

```
/plugin marketplace add <path to this repo>
/plugin install synapsidian@synapsidian
```

Claude Code asks for the vault path (default `~/Synapsidian`; give the folder's exact spelling). Then, in a new session (hooks of a newly installed plugin load at session start):

```
/synapsidian:setup
```

It checks Obsidian, uv and git, creates the vault layout, configures Obsidian (core plugins, Bases views, daily notes, a Templater template per note type, property types, the required community plugins), makes the vault a git repo, asks a few questions for `About.md`, and offers to register the vault in Obsidian.

Your own rules for Claude in this vault go in the `## Rules` section of `About.md` ("never file notes about my family"). Folders Claude must ask about before touching go in its `protected` property. Every session reads both, and they override synapsidian's defaults.

Sessions you don't want in the devlog: list their folders (or glob patterns) in the option `session_exclude_paths`, or write `#off-the-record` in any message of that session. Text inside `<private>...</private>` is left out of every digest.

For work, add the add-on (it installs `synapsidian` too if it's missing):

```
/plugin install synapsidian-work@synapsidian
/synapsidian-work:setup
```

It asks for your GitHub repo, Jira project key, work repository path and stand-up days and time (leave any empty to skip that source), installs its schema extension into the vault (`.synapsidian/extensions/synapsidian-work/`), fills the work fields of `About.md` and schedules the stand-up.

Because the manifests have a `version`, installed plugins are copies in `~/.claude/plugins/cache/`; to ship changes, bump the version and run `claude plugin marketplace update synapsidian && claude plugin update synapsidian@synapsidian` (and `synapsidian-work@synapsidian`), then restart. For a one-off session without installing: `claude --plugin-dir plugins/synapsidian --plugin-dir plugins/synapsidian-work`.

## Skills

Each plugin's README lists its skills, options and hooks:

- [plugins/synapsidian/README.md](plugins/synapsidian/README.md): 16 skills, from `/synapsidian:setup` and `/synapsidian:task` to `/synapsidian:morning`, `/synapsidian:evening` and `/synapsidian:review`, plus the hooks
- [plugins/synapsidian-work/README.md](plugins/synapsidian-work/README.md): 6 skills: setup, the work brief, the stand-up, 1:1 prep and the win log
- [plugins/synapsidian-projects/README.md](plugins/synapsidian-projects/README.md): 10 skills: setup, projects, milestones, decisions, specs, changes, bug investigations, postmortems, architecture notes and mind maps
- [plugins/synapsidian-dock/README.md](plugins/synapsidian-dock/README.md): no skills; the band, its task pane and their keys

## Vault layout

`Inbox/ Daily/ Tasks/ People/ Meetings/ Decisions/ Notes/ Howtos/ Ideas/ Goals/ Sources/ Research/ Reviews/ Thinking/ Bases/ Templates/ Attachments/ Archive/` plus `About.md`. synapsidian-projects adds `Projects/<Project>/`, which holds the hub `<Project>.md` and the project's own `Tasks/`, `Decisions/`, `Specs/`, `Changes/`, `Debug/`, `Incidents/`, `Architecture/`, `Research/`, `Workflows/`, `Notes/`, `Thinking/` and `Maps/`. Note types and their fields are defined once in [plugins/synapsidian/schema/types.yaml](plugins/synapsidian/schema/types.yaml), widened by the extensions installed in the vault's `.synapsidian/extensions/`.

## Development

```bash
uv sync
uv run pytest
uv run ruff check plugins tests && uv run ruff format --check plugins tests
claude plugin validate plugins/synapsidian --strict && claude plugin validate plugins/synapsidian-work --strict && claude plugin validate plugins/synapsidian-projects --strict && claude plugin validate plugins/synapsidian-dock --strict && claude plugin validate .
(cd plugins/synapsidian-dock && claude plugin test)
```

Scripts can be run directly: `plugins/synapsidian/bin/synapsidian find --vault ~/Synapsidian "export format"`, `plugins/synapsidian-work/bin/synapsidian-work standup window --days tue,thu --time 12:00`. Project rules, including what may go in which plugin, are in [CLAUDE.md](CLAUDE.md).

## License and author

MIT, © 2026 Jan Szewczyk. Maintained by [Szum Tech Team](https://github.com/JanSzewczyk). Questions and bugs: [open an issue](https://github.com/JanSzewczyk/synapsidian/issues).
