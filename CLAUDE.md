# Synapsidian plugins: project rules

## Layout

One local marketplace (`.claude-plugin/marketplace.json`, `synapsidian`) with four plugins:

- `plugins/synapsidian/`: the core. The `synapsidian` CLI (`bin/`, `scripts/`), the schema, Bases and
  templates, hooks (session brief, `>>` capture, session queue, vault-edit approval, validation),
  the `research-deep` workflow, and 16 skills: `capture`, `daily`, `evening`, `find`, `health`,
  `ingest`, `meeting`, `morning`, `recap`, `research`, `review`, `save`, `schedule`, `setup`, `task`,
  `think`.
- `plugins/synapsidian-work/`: the work add-on. Skills `setup`, `work-brief` (PRs, Jira, email and
  Slack asks), `standup`, `one-to-one`, `one-to-one-triage` and `win` (the brag log in `Wins/`);
  1:1, stand-up and retro meeting kinds.
- `plugins/synapsidian-projects/`: the projects add-on (D98-D111, D139-D152, D154).
  - It owns the `project` type: hubs live in
    `Projects/<Project>/<Project>.md` with a kanban board, and project notes are filed under
    that folder.
  - Skills: `setup`, `project` (hubs, a read-only repository scan), `milestone` (stages with
    a target date), `decide` (MADR decisions), `map` (Excalidraw mind maps), `spec`, `change`,
    `debug`, `incident` and `architect` (architecture notes, any language, a Vue profile). Its
    scripts (`scripts/projects.py`, `repos.py`, `maps.py`, `flows.py`, `progress.py`, `architect.py`) never import
    `synapsidianlib`. `decision-number`, `map`, `flow` and `progress` read `synapsidian query` JSON on
    stdin; `scan`, `repo` and `architect` read the repository and the add-on's state folder.
  - It only ever reads code repositories.
- `plugins/synapsidian-dock/`: the dock add-on (D156), a Claude Code mod
  (`hooks/register.ts`): a band above the prompt (`/synapsidian` shows it, ✕ hides it) with a Tasks
  button to a task pane. No skills, no
  schema extension. It meets the core only through `synapsidian brief --json`, `synapsidian note set` and
  `synapsidian commit` (on PATH, or the installed synapsidian's `bin/synapsidian` where the desktop app leaves it
  off), and writes nothing without a key press.

Each add-on lists `dependencies: [{ "name": "synapsidian", "version": "~<core>" }]`, a `~` range on the core.

`tests/`, `docs/`, `references/`, `pyproject.toml` and `uv.lock` sit at the repo root and ship with none of them.
The one exception is a mod's `*.test.ts` (today `plugins/synapsidian-dock/tests/`), which
`claude plugin test` runs only from inside its plugin.
`references/decisions.md` is the decision log; skills, scripts and references cite its numbers (`D90`).
A design not built yet keeps its contract beside it (`references/morning-sources.md`, D162) until it moves into a plugin.

`docs/` is the documentation site (Astro Starlight, English only), deployed to GitHub Pages by
`.github/workflows/docs.yml`:
- Pages live in `docs/src/content/docs/`: one page per skill under `skills/` (core) and
  `extensions/<work|projects>/` (add-ons), the dock (a Claude Code mod) under `mods/dock/`, and one
  page per CLI command under `cli/`. The sidebar is in `docs/astro.config.mjs`. `tests/test_docs_site.py` fails when a skill or command has no page.
- `cd docs && npm run check && npm run build` (the build also fails on a broken internal link).
- Archived releases follow the core version: `versions` in `astro.config.mjs` and a snapshot folder
  (`docs/src/content/docs/0.34/`) written by `starlight-versions` on the first `npm run dev`. The
  changelogs are not versioned, so right after writing a snapshot point its `/synapsidian/<slug>/…/changelog/`
  links back at `/synapsidian/…/changelog/`; after that, edit a snapshot only to follow a changelog
  page that moved.
- The changelog pages (`/changelog/` for the core, `/extensions/<add-on>/changelog/`,
  `/mods/dock/changelog/`) are generated from the root `CHANGELOG.md` by `starlight-changelogs` (`docs/src/content.config.ts`).
- A change to a skill, command, option or schema field also updates its page here.

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
- **How the core and the add-ons meet (D90)**, and only these ways:
  - Schema: an add-on's `extension/` (types, `extend:` of core or add-on types, templates, bases) is
    installed into the vault by `synapsidian setup extension` at `<vault>/.synapsidian/extensions/<name>/`.
    The core merges whatever is installed there. Core `schema/types.yaml` holds no work or project
    types or values. synapsidian-work extends synapsidian-projects' `project` with `jira`; an
    `extend:` of a type nothing defines is skipped (D106).
  - Core skills reach an add-on only through `command -v <add-on>` and `<add-on> hook <name>` (a
    printed reference): `synapsidian-work hook morning|meetings|review|schedule`,
    `synapsidian-projects hook review`. The one direct call is `synapsidian-projects progress` in
    `review`. Where options are needed, the hook says to invoke a synapsidian-work skill, since only
    synapsidian-work's skills see its `${user_config.*}`.
  - Add-on skills call the core through `synapsidian ...` on PATH and read core references with
    `synapsidian ref <name>`; `${CLAUDE_PLUGIN_ROOT}` in an add-on skill is that add-on's root. Each
    add-on's own `bin/` (`synapsidian-work`, `synapsidian-projects`) also prints its `extension`
    directory; `synapsidian-projects section <title>` prints a hub template section.
  - Add-on scripts never import `synapsidianlib`: a plugin can't import another plugin's code
    (separate cache copies). synapsidian-work copies the few helpers into `worklib/`.
- **Nothing user-specific is hardcoded** in anything read at runtime: skills, `references/`,
  `schema/`, `bases/`, `scripts/`, `hooks/`, templates, in any plugin. That means no company
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

Versions are bumped only on request, through `/plugin-release` (see the plugin development section
below). When synapsidian-work's or synapsidian-projects' version changes, keep its
`extension/extension.yaml` `version` equal to the plugin version; the add-on's `setup` skill
re-installs the extension when they differ.

<!-- BEGIN:plugin-dev -->
## Plugin development

Managed by `/plugin-setup`; re-run it to refresh this section instead of editing it here.

### Where things live

- Marketplace: `.claude-plugin/marketplace.json`.
- Plugins: `plugins/<name>/.claude-plugin/plugin.json` for `synapsidian`, `synapsidian-work`,
  `synapsidian-projects` and `synapsidian-dock`.

- Each manifest is `<plugin>/.claude-plugin/plugin.json`. `skills/`, `agents/`, `hooks/` and every
  other component sit at the plugin root, never inside `.claude-plugin/`.
- A new **plugin** is registered in `.claude-plugin/marketplace.json`. A new skill or agent inside
  an existing plugin is not.
- No plugin sets `agents`, so agent files are found by scanning `agents/`. If a manifest ever sets
  `agents`, it must list every agent file, because the array replaces the scan.
- Every manifest opens with `$schema`: `https://www.schemastore.org/claude-code-plugin-manifest.json`
  for a plugin, `https://www.schemastore.org/claude-code-marketplace.json` for the marketplace.

### After a change to a plugin

1. **Update the docs that list capabilities by hand:** the root `README.md`, each
   `plugins/<name>/README.md`, and the plugin layout list at the top of this file.
2. **Run `/marketplace-creator audit`** and fix what it reports before committing. It checks manifests,
   docs and frontmatter against what is on disk.

### Versions

Plugins pin `version`, so users stay on the cached copy until it changes; semver sizes are in
`/plugin-release`.

**Never bump a version on your own.** Editing a skill or an agent is not a request to bump: change
a `version` only when the user asks for it in this conversation, and then through `/plugin-release`,
which proposes the size from the diff and writes nothing until the user agrees. A pull request that
changed a plugin and left its version alone is caught by CI, not by a standing instruction.

### Releasing

Release tags are `<plugin>--v<version>`, created through `/plugin-release`. Every plugin that lists
`dependencies` resolves a version range against these tags, so tag each version a range can point at.

Every version bump adds a `CHANGELOG.md` section, `## [<version> <plugin>] — <date>`;
`/plugin-release` drafts it from git history.

### What runs on its own

Nothing in the background. The steps above happen because this file asks for them; CI, if
`.github/workflows/plugin-checks.yml` exists, fails a pull request with drift or a missing bump.
<!-- END:plugin-dev -->
