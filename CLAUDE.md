# Synapsidian plugins: project rules

## Layout

One local marketplace (`.claude-plugin/marketplace.json`, `synapsidian`) with four plugins:

- `plugins/synapsidian/`: the core. Vault layout, schema, notes, tasks, meetings, save, find,
  ingest, research, think, evening, review, recap, schedule, hooks.
- `plugins/synapsidian-work/`: the work add-on (`dependencies: ["synapsidian"]`). 1:1s, stand-up, work
  brief (PRs, Jira, email and Slack asks), its own setup.
- `plugins/synapsidian-projects/`: the projects add-on (`dependencies: ["synapsidian"]`; D98-D111,
  D139-D152, D154, `docs/spec.md` §10d).
  - It owns the `project` type and every `project` field: hubs live in
    `Projects/<Project>/<Project>.md` with a kanban board, and project notes are filed under
    that folder.
  - Skills: `setup`, `project` (hubs, a read-only repository scan), `milestone` (stages with
    a target date), `decide` (MADR decisions), `map` (Excalidraw mind maps), `spec`, `change`,
    `debug`, `incident` and `architect` (architecture notes, any language, a Vue profile). Its
    scripts (`scripts/projects.py`, `repos.py`, `maps.py`, `flows.py`, `progress.py`, `architect.py`) never import
    `synapsidianlib`; they read `synapsidian query` JSON on stdin instead.
  - It only ever reads code repositories.
- `plugins/synapsidian-dock/`: the dock add-on (`dependencies: ["synapsidian"]`; D156), a Claude Code mod
  (`hooks/register.ts`): a band above the prompt (`/synapsidian` shows it, ✕ hides it) with a Tasks
  button to a task pane. No skills, no
  schema extension. It meets the core only through `synapsidian brief --json`, `synapsidian note set` and
  `synapsidian commit` (on PATH, or the installed synapsidian's `bin/synapsidian` where the desktop app leaves it
  off), and writes nothing without a key press.

`tests/`, `docs/`, `pyproject.toml` and `uv.lock` sit at the repo root and ship with none of them.
The one exception is a mod's `*.test.ts` (today `plugins/synapsidian-dock/tests/`), which
`claude plugin test` runs only from inside its plugin.

## The core is universal (D88, D90)

`synapsidian` is a portable, user-agnostic Claude Code plugin for running any Obsidian vault as a
second brain. It is not the author's work setup. Someone installing it on another machine, for
a personal vault with no job, no team and no Jira, must get a plugin that fits them.

- **Core works for anyone with no work context.** Nothing in `plugins/synapsidian/` may assume an
  employer, a team, a manager, tickets, pull requests, stand-ups, 1:1s or a code repository.
- **Project features go in `synapsidian-projects`** (D99, D106). The core has no `project` type,
  field, template or Base. Core code that touches projects asks the schema (does a `project`
  type exist?), and core skills follow the Projects section of `references/conventions.md`.
- **Work features go in `synapsidian-work`.** Anything tied to a job lives in `plugins/synapsidian-work/`.
  Its options are its own `userConfig`; an empty or unsubstituted option switches that source
  off silently (D86): never an error, never a prompt, never mentioned in a report.
- **How the two meet (D90)**, and only these ways:
  - Schema: synapsidian-work's `extension/` (types, `extend:` of core fields, templates, bases) is
    installed into the vault by `synapsidian setup extension` at `<vault>/.synapsidian/extensions/<name>/`.
    The core merges whatever is installed there. Core `schema/types.yaml` holds no work types
    or values.
  - Core skills reach the add-on only through `command -v synapsidian-work` and
    `synapsidian-work hook <name>` (a printed reference). Where options are needed, the hook says to
    invoke a synapsidian-work skill, since only synapsidian-work's skills see its `${user_config.*}`.
  - synapsidian-work skills call the core through `synapsidian ...` on PATH and read core references with
    `synapsidian ref <name>`; `${CLAUDE_PLUGIN_ROOT}` in a synapsidian-work skill is synapsidian-work's root.
  - synapsidian-work's scripts never import `synapsidianlib`: a plugin can't import another plugin's code
    (separate cache copies). Copy the few helpers into `worklib/` instead.
- **Nothing user-specific is hardcoded** in anything read at runtime: skills, `references/`,
  `schema/`, `bases/`, `scripts/`, `hooks/`, templates, in either plugin. That means no company
  or product names, ticket prefixes or keys, app or repository names, people's names, meeting
  cadences or times, vault paths, home-directory paths, or Polish strings in what the plugins
  write. Such values come from `userConfig` or `About.md`, or are a neutral default the user
  can change.
- **Examples stay generic.** Example ticket keys, app names and people in skills and
  references use neutral placeholders (`ABC-123`, `web-app`, `Alex`), never the author's real
  ones. Test fixtures may be realistic but must not be read by the plugins at runtime.
- **Portability counts too.** Don't add new macOS-only paths or tools without a fallback or a
  clear error. Obsidian's paths and commands per operating system live in `obsidian_host()` in
  `scripts/setup.py` (D157); add to it rather than hardcoding a path elsewhere.

Before adding or changing a skill, script or reference, ask: would this behave correctly for a
user whose vault is personal only, with synapsidian-work not installed? If not, it belongs in
synapsidian-work or needs an option.

## Versions

Bump `version` in the plugin's `.claude-plugin/plugin.json` for every shipped change (the
installed copy is cached per version). For synapsidian-work, keep `extension/extension.yaml`'s
`version` equal to its plugin version; `/synapsidian-work:setup` re-installs the extension when they
differ.
