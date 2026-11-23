<div align="center">

# 🧩 Synapsidian

[![Claude Code](https://img.shields.io/badge/Claude_Code-D97757?logo=anthropic&logoColor=white)](https://claude.com/claude-code)
[![Obsidian](https://img.shields.io/badge/Obsidian-7C3AED?logo=obsidian&logoColor=white)](https://obsidian.md)
[![Plugin Checks](https://github.com/JanSzewczyk/synapsidian/actions/workflows/plugin-checks.yml/badge.svg)](https://github.com/JanSzewczyk/synapsidian/actions/workflows/plugin-checks.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![GitHub stars](https://img.shields.io/github/stars/JanSzewczyk/synapsidian?style=social)](https://github.com/JanSzewczyk/synapsidian/stargazers)

**Claude Code plugins that turn an Obsidian vault into a second brain**

[Plugins](#-plugins) • [Getting Started](#-getting-started) • [Development](#-development) • [Documentation](#-table-of-contents)

</div>

---

## 👋 Hello there!

Claude Code plugins that keep a second brain in an Obsidian vault: daily notes, tasks, meeting and people notes, decisions and knowledge, captured from your Claude sessions and kept current. Every change Claude makes is a git commit in the vault, so you can see and undo it.

One marketplace, four plugins: the core works for any vault, personal or work, and three optional add-ons build on it for work, projects and a task dock. Nothing in the core assumes a job.

Inspired by [eugeniughelbur/obsidian-second-brain](https://github.com/eugeniughelbur/obsidian-second-brain), rebuilt for current Claude Code plugin features: skills with progressive disclosure, a single note schema, scripts for the mechanics and Claude for the judgement. See [docs/spec.md](docs/spec.md) for the design and [docs/decisions.md](docs/decisions.md) for why.

## ✨ Features

### 📓 Capture and notes

- **✍️ [Daily notes, tasks and meetings](plugins/synapsidian/README.md)** — `daily`, `task` and `meeting` skills, with meeting notes importable from Gemini notes
- **📥 [Inbox capture](plugins/synapsidian/README.md)** — a prompt starting with `>>` goes to the vault's Inbox instead of to Claude
- **💾 [Save from conversations](plugins/synapsidian/README.md)** — the `save` and `capture` skills file what a session produced
- **📚 [Ingest sources](plugins/synapsidian/README.md)** — web articles, YouTube videos, PDF, DOCX and PPTX files, Confluence pages, pasted text and images, each kept verbatim in `Sources/`

### 🔎 Knowledge and review

- **🧠 [Research and thinking tools](plugins/synapsidian/README.md)** — `research` writes a cited dossier from the vault first and the web for the gaps; `think` and `find` work on what the vault knows
- **🌅 [Morning brief, evening run, reviews](plugins/synapsidian/README.md)** — `morning`, `evening`, `recap`, `review` and `schedule` keep the vault current
- **🩺 [Vault health](plugins/synapsidian/README.md)** — `health` applies safe mechanical fixes and lists what needs a decision

### 🧩 Add-ons

- **💼 [Work](plugins/synapsidian-work/README.md)** — 1:1 notes, the stand-up note, pull requests, Jira, and asks from email and Slack in the morning brief
- **🗂️ [Projects](plugins/synapsidian-projects/README.md)** — a hub note with a kanban board per project, plus milestones, decisions, specs, changes, bug investigations, postmortems, architecture notes and mind maps
- **🪟 [Dock](plugins/synapsidian-dock/README.md)** — the brief in a band above the prompt, with a Tasks pane whose keys change a task without a Claude turn

### 🔒 Safety

- **↩️ Every change is a git commit in the vault** — see and undo what Claude did
- **🙈 Off-the-record sessions** — keep folders out of the devlog with `session_exclude_paths` or `#off-the-record`; text inside `<private>...</private>` is left out of every digest

---

## 📖 Table of Contents

- [✨ Features](#-features)
- [🧩 Plugins](#-plugins)
- [🎯 Getting Started](#-getting-started)
- [📚 Vault Layout](#-vault-layout)
- [💻 Development](#-development)
- [📁 Repository Structure](#-repository-structure)
- [🤝 Contributing](#-contributing)
- [📜 License](#-license)
- [🙏 Acknowledgments](#-acknowledgments)
- [📧 Contact & Support](#-contact--support)

---

## 🧩 Plugins

Each plugin's README lists its skills, options and hooks.

| Plugin | Skills | What it does |
| --- | :-: | --- |
| [`synapsidian`](plugins/synapsidian/README.md) | 16 | The core, for any vault: from `/synapsidian:setup` and `/synapsidian:task` to `/synapsidian:morning`, `/synapsidian:evening` and `/synapsidian:review`, plus the hooks |
| [`synapsidian-work`](plugins/synapsidian-work/README.md) | 6 | Optional work add-on: setup, the work brief, the stand-up, 1:1 prep and the win log |
| [`synapsidian-projects`](plugins/synapsidian-projects/README.md) | 10 | Optional projects add-on: setup, projects, milestones, decisions, specs, changes, bug investigations, postmortems, architecture notes and mind maps. Code repositories are only ever read |
| [`synapsidian-dock`](plugins/synapsidian-dock/README.md) | 0 | Optional Claude Code mod: the band, its task pane and their keys; `/synapsidian` shows the band. Needs Claude Code 2.1.299 or later and no setup |

---

## 🎯 Getting Started

### 📋 Prerequisites

Before you begin, ensure you have the following installed:

- **macOS** and [Claude Code](https://claude.com/claude-code)
- **[Obsidian](https://obsidian.md)** 1.14 or later (core Bases with kanban); `brew install --cask obsidian`
- **[uv](https://docs.astral.sh/uv/)** — runs the Python scripts; it fetches Python 3.12+ and each script's libraries itself, e.g. trafilatura, markitdown, youtube-transcript-api, pypdfium2, and for `visual` yt-dlp with a bundled ffmpeg
- **Git** for version control
- **synapsidian-work only** — [`gh`](https://cli.github.com) for pull requests, the Atlassian connector for Jira, Gmail and Slack connectors for asks

Four Obsidian community plugins are required and set up by `/synapsidian:setup`: Git (history for your own edits), Excalidraw (drawings), Templater (notes you make by hand, from templates synapsidian generates in `Templates/Generated/`) and Calendar Bases (calendar views of tasks, meetings and goals). synapsidian-projects adds Folder notes (a click on a project's folder opens its hub) and Excalidraw Extras (Mermaid diagrams turned into editable drawings). Every setup ends with a short report: what is ready, what this run added, and what is still needed, with how to add it. Setup also offers Claudian, Claude Code in Obsidian's sidebar, as a recommended extra. Why each, and the optional ones: [plugins/synapsidian/references/obsidian-plugins.md](plugins/synapsidian/references/obsidian-plugins.md). No API keys, no MCP server.

### 📦 Installation

#### 1. Add the marketplace and the core plugin

From a Claude Code session, with the path of your clone of this repository:

```text
/plugin marketplace add <path to this repo>
/plugin install synapsidian@synapsidian
```

Claude Code asks for the vault path (default `~/Synapsidian`; give the folder's exact spelling).

#### 2. Set up the vault

In a new session (hooks of a newly installed plugin load at session start):

```text
/synapsidian:setup
```

It checks Obsidian, uv and git, creates the vault layout, configures Obsidian (core plugins, Bases views, daily notes, a Templater template per note type, property types, the required community plugins), makes the vault a git repo, asks a few questions for `About.md`, and offers to register the vault in Obsidian.

#### 3. Add the add-ons you want

For work, add the add-on (it installs `synapsidian` too if it's missing):

```text
/plugin install synapsidian-work@synapsidian
/synapsidian-work:setup
```

It asks for your GitHub repo, Jira project key, work repository path and stand-up days and time (leave any empty to skip that source), installs its schema extension into the vault (`.synapsidian/extensions/synapsidian-work/`), fills the work fields of `About.md` and schedules the stand-up.

For projects:

```text
/plugin install synapsidian-projects@synapsidian
/synapsidian-projects:setup
```

For the dock (no setup):

```text
/plugin install synapsidian-dock@synapsidian
```

### 🔧 Configuration

Your own rules for Claude in this vault go in the `## Rules` section of `About.md` ("never file notes about my family"). Folders Claude must ask about before touching go in its `protected` property. Every session reads both, and they override synapsidian's defaults.

Sessions you don't want in the devlog: list their folders (or glob patterns) in the option `session_exclude_paths`, or write `#off-the-record` in any message of that session. Text inside `<private>...</private>` is left out of every digest.

### 🔄 Updating

Because the manifests have a `version`, installed plugins are copies in `~/.claude/plugins/cache/`; to ship changes, bump the version and run:

```bash
claude plugin marketplace update synapsidian && claude plugin update synapsidian@synapsidian
```

Do the same for `synapsidian-work@synapsidian`, then restart. For a one-off session without installing:

```bash
claude --plugin-dir plugins/synapsidian --plugin-dir plugins/synapsidian-work
```

---

## 📚 Vault Layout

`Inbox/ Daily/ Tasks/ People/ Meetings/ Decisions/ Notes/ Howtos/ Ideas/ Goals/ Sources/ Research/ Reviews/ Thinking/ Bases/ Templates/ Attachments/ Archive/` plus `About.md`.

synapsidian-projects adds `Projects/<Project>/`, which holds the hub `<Project>.md` and the project's own `Tasks/`, `Decisions/`, `Specs/`, `Changes/`, `Debug/`, `Incidents/`, `Architecture/`, `Research/`, `Workflows/`, `Notes/`, `Thinking/` and `Maps/`.

Note types and their fields are defined once in [plugins/synapsidian/schema/types.yaml](plugins/synapsidian/schema/types.yaml), widened by the extensions installed in the vault's `.synapsidian/extensions/`.

---

## 💻 Development

### 🧪 Checks

```bash
uv sync
uv run pytest
uv run ruff check plugins tests && uv run ruff format --check plugins tests
claude plugin validate plugins/synapsidian --strict && claude plugin validate plugins/synapsidian-work --strict && claude plugin validate plugins/synapsidian-projects --strict && claude plugin validate plugins/synapsidian-dock --strict && claude plugin validate .
(cd plugins/synapsidian-dock && claude plugin test)
```

Pull requests also run [`.github/workflows/plugin-checks.yml`](.github/workflows/plugin-checks.yml): manifests and docs against the plugins on disk, a version bump for every changed plugin (with its `CHANGELOG.md` section), and a skill audit.

### 🛠️ Running scripts directly

```bash
plugins/synapsidian/bin/synapsidian find --vault ~/Synapsidian "export format"
plugins/synapsidian-work/bin/synapsidian-work standup window --days tue,thu --time 12:00
```

---

## 📁 Repository Structure

```text
synapsidian/
├── .claude-plugin/          # marketplace.json: the four plugins
├── .github/workflows/       # plugin-checks.yml
├── docs/                    # spec.md, decisions.md, research/
├── plugins/
│   ├── synapsidian/         # core: skills, hooks, schema, bases, scripts
│   ├── synapsidian-work/    # work add-on
│   ├── synapsidian-projects/ # projects add-on
│   └── synapsidian-dock/    # dock mod
├── tests/                   # pytest suite and a fixture vault
├── CHANGELOG.md
├── CLAUDE.md                # project rules
├── pyproject.toml           # dev environment: tests and lint
└── uv.lock
```

### Key Directories

- **`plugins/<name>/.claude-plugin/plugin.json`** — each plugin's manifest; `skills/<skill>/SKILL.md` holds its skills
- **`docs/`** — the design ([spec.md](docs/spec.md)), why ([decisions.md](docs/decisions.md)) and research notes
- **`tests/`, `pyproject.toml`, `uv.lock`** — the dev environment; like `docs/`, they sit at the repo root and ship with none of the plugins

---

## 🤝 Contributing

Contributions are welcome. Project rules, including what may go in which plugin, are in [CLAUDE.md](CLAUDE.md).

1. Fork the repository and create a branch
2. Make the change following [CLAUDE.md](CLAUDE.md)
3. Update the READMEs that list skills, then run the checks above
4. Open a pull request

Versions are bumped only on request, with `/plugin-release`; CI fails a pull request that changes a plugin without a bump.

---

## 📜 License

MIT, © 2026 Jan Szewczyk. Maintained by [Szum Tech Team](https://github.com/JanSzewczyk).

---

## 🙏 Acknowledgments

Inspired by [eugeniughelbur/obsidian-second-brain](https://github.com/eugeniughelbur/obsidian-second-brain).

---

## 📧 Contact & Support

- 🐛 [Open an issue](https://github.com/JanSzewczyk/synapsidian/issues)
- ⭐ [Star this repository](https://github.com/JanSzewczyk/synapsidian)
- 👨‍💻 Check out the maintainer's [GitHub profile](https://github.com/JanSzewczyk)

---

<div align="center">

**Made with ❤️ by [Jan Szewczyk](https://github.com/JanSzewczyk)**

If these plugins helped you, please consider giving them a ⭐ on GitHub!

[⬆ Back to Top](#-synapsidian)

</div>
