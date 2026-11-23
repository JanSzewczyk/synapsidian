# Obsidian plugins for a synapsidian vault (as of 2026-10, Obsidian 1.14)

Everything synapsidian reads and writes is core Obsidian: Bases (tables and kanban boards), Properties, Daily notes, Backlinks. `setup` enables those. On top of that, synapsidian requires four community plugins (D91, D110, D115), an add-on may require more (synapsidian-projects: Folder notes and Excalidraw Extras), and setup offers one recommended plugin, Claudian.

Community plugins are installed in Obsidian: Settings → Community plugins → turn off Restricted mode → Browse → install → enable. With the Obsidian CLI enabled (Settings → General → Advanced → Command line interface), `obsidian plugin:install id=<id> enable` does the same while Obsidian runs; Restricted mode must be off first, and turning it off is the user's decision (`obsidian plugins:restrict` shows whether it is on).

## Required

`synapsidian setup check` lists them under `community_plugins_required` and isn't `ready` until each is installed, enabled and configured. Once a plugin is installed, `synapsidian setup apply` writes synapsidian's settings into its `data.json`, keeping any value the user already chose; Obsidian then needs `obsidian plugin:reload id=<id>` (or a restart) to read them.

| Plugin | Why synapsidian needs it | Settings synapsidian applies (where to find them by hand) |
|---|---|---|
| **Git** (`obsidian-git`, by Vinzent03) | synapsidian commits only what Claude changes. Your own edits in Obsidian stay uncommitted until something commits them; this plugin does that on a timer, so *your* changes get history and undo too. The timer commits every changed file, so now and then it takes a file in the middle of a synapsidian run; `synapsidian commit` then reports it as `swept` and the run says which commit holds its change. Desktop only. | Settings → Git: **Auto commit-and-sync interval (minutes)** `30`; **Disable push** on (the vault has no remote, D31); **Commit message on auto commit-and-sync** and **Commit message on manual commit** `vault: manual edits {{date}}` (the default "vault backup" suggests a backup that doesn't exist). |
| **Excalidraw** (`obsidian-excalidraw-plugin`, by zsviczian) | Sketches and diagrams inside notes: architecture sketches, meeting whiteboards, idea maps. A drawing is a `.excalidraw.md` file that synapsidian never treats as a note (no schema check, no health report). | Settings → Excalidraw: **Excalidraw folder** `Attachments` (synapsidian's scanners skip it, and embedded drawings land there too); **Compress Excalidraw JSON in Markdown** off, so drawings stay plain text: readable git diffs, and their text is searchable. |
| **Templater** (`templater-obsidian`, by SilentVoid13) | Notes you make yourself in Obsidian come out the way synapsidian writes them. `setup apply` generates a template per note type from the schema into `Templates/Generated/` (Task, Person, Meeting and each meeting kind, Decision, Note, How-to, Idea, Capture; with the add-ons also 1:1, stand-up, Project, Spec, Change). Each one asks for the title, the summary and the choices the type needs, numbers task ids (and a project's decisions), fills the frontmatter, adds the type's sections, and moves the note to its folder under the name synapsidian would give it. | Settings → Templater: **Template folder location** `Templates/Generated`; **Template hotkeys**: one entry per generated template, so the command palette has *Templater: Create Task*, *Templater: Create Meeting - External* and so on (bind keys to them if you like); **Folders to exclude** on file creation: every folder synapsidian writes to. Leave **Trigger Templater on new file creation** off (see below). |
| **Calendar Bases** (`calendar-bases`, by edrickleong) | A **Calendar** view for Bases, beside the core table and kanban: `Tasks.base` by `due`, `Meetings.base` by `date`, `Goals.base` by `target`. Dragging a note to another day changes that date in its frontmatter, the way dragging a card on a board changes its `status`, so the calendar is a view of the notes, not a copy. Version 0.2.x (last release April 2026); synapsidian drops the requirement once Bases gets a core calendar view, as it got kanban. | None: each view's options (start date, week start) live in the `.base` file. A vault set up before synapsidian 0.28.0 keeps its Bases (`apply` never overwrites one), so add the view yourself: open the Base → view menu → *Add view* → Calendar → Start date `due` (or `date`, `target`). |
| **Folder notes** (`folder-notes`, by LostPaul), **with synapsidian-projects** | Required by the synapsidian-projects add-on, not by synapsidian itself: its extension lists it, and `setup check` shows it with `required_by: synapsidian-projects`. A click on `Projects/<Project>` opens the project's hub, `Projects/<Project>/<Project>.md`, which the plugin then hides from the file list. | None: its defaults (a note named like its folder, inside it; nothing created automatically) are where hubs already live. |
| **Excalidraw Extras** (`excalidraw-extras`, by zsviczian), **with synapsidian-projects** | Required by the synapsidian-projects add-on (D154). Excalidraw's companion for its heavy and high-privilege parts: the Mermaid-to-Excalidraw converter, which turns a project's roadmap or flow into an editable drawing, plus LaTeX and PDF export. It does nothing on its own; without it Excalidraw asks for it the first time one of those features is used. | None. |

An add-on lists the plugins it needs under `plugins` in its `extension.yaml`, `{<id>: {name, settings: {<key>: [synapsidian value, plugin default]}}}`; `setup check` and `apply` treat them like synapsidian's own.

## Recommended

Setup offers these and installs one only on a yes; `ready` never waits for them.

| Plugin | Why it helps here | How to set it up |
|---|---|---|
| **Claudian** (`realclaudian`, by YishenTu) | Claude Code in Obsidian's sidebar, with the vault as its working directory: `/synapsidian:save`, `/synapsidian:task` or `/synapsidian:find` run beside the note you have open, without switching to a terminal. It runs on the Claude Agent SDK with your own Claude login, reads skills from your user and vault scopes, and sends no telemetry. Desktop only. | Install, open its sidebar view, sign in if it asks. Check once that the `/synapsidian:` skills are listed; if they aren't, run synapsidian from the terminal as before. |

### Making notes from the templates

Command palette → **Templater: Create new note from template** → pick one from `Templates/Generated/` (or run its own *Create* command). Answer the prompts; Esc cancels, and leaves an empty `Untitled` note in `Inbox/` to delete. The note lands where `synapsidian note new` would put it: a task as `Tasks/T<n> <title>.md`, or under `Projects/<Project>/Tasks/` when you pick a project; a project hub as `Projects/<Project>/<Project>.md` with its board. When the projects add-on is installed, its project skill can then read a code repository into the hub.

The templates belong to synapsidian, which is what the folder's name says: `setup apply` rewrites one when synapsidian's version changes, unless you edited it, in which case it stays and `apply` reports it under `kept_user_settings`. Before synapsidian 0.29.0 the folder was `Templates/Synapsidian/`; `apply` moves an older vault over and points Templater at the new folder (D119). A template you had edited there stays where it is and is reported, since Templater no longer lists that folder. For a variant of your own, copy a template into `Templates/` and change the copy. The daily note template stays `Templates/Daily.md`, filled by the core Daily notes plugin.

### Keep "Trigger Templater on new file creation" off

With it on, Templater runs the `<% %>` code in **every** new Markdown file that appears while Obsidian is open, including notes Claude writes and the verbatim copies of web pages in `Sources/`. A page that happens to contain Templater syntax would run as JavaScript in Obsidian. synapsidian never needs the trigger: the templates are used through *Create new note from template*. Since Templater 2.21 the switch is stored per device in Obsidian, not in `data.json`, so synapsidian can neither turn it on nor see it. As a second guard, synapsidian adds every folder it writes to under **Folders to exclude**, and `/synapsidian:health` reports a note that still holds Templater commands (`templater_leftovers`).

The core **Templates** plugin isn't needed any more (Daily notes fills `{{date}}` itself) and synapsidian no longer turns it on. Pointed at a folder that holds `Templates/Generated/` (synapsidian set it to `Templates` before 0.24.0), its *Insert template* lists synapsidian's templates and pastes one without running it, so the note shows JavaScript. `setup apply` turns it off when that folder holds nothing but synapsidian's templates (D118). If you keep core templates of your own there, `setup check` reports `core_templates_clash`: turn the plugin off, or move your templates to a subfolder such as `Templates/Core/` and set that as its folder.

Plugin code (`main.js`, `styles.css`) is git-ignored: Excalidraw alone is 5 MB a release. Each plugin's `manifest.json` and `data.json` stay tracked, so settings have history. An ignore rule doesn't untrack what git already tracks: in a vault that committed plugin code before, `git rm -r --cached -q .obsidian/plugins/*/main.js .obsidian/plugins/*/styles.css` and a commit stop it (the files stay on disk).

## Worth adding (optional)

| Plugin | Why it helps here | How to set it up |
|---|---|---|
| **Omnisearch** (`omnisearch`, by scambier) | Better in-app search than the core one: typo-tolerant, ranks by relevance, can search PDF text. Handy when you look something up yourself in Obsidian. synapsidian's `find` doesn't use it. | Install and use its command (`Omnisearch: Vault search`); defaults are fine. |
| **Importer** (`obsidian-importer`, by Obsidian) | One-off move into the vault from Notion, Evernote, Apple Notes, OneNote, Google Keep, Bear, Logseq, Roam, Airtable, CSV or HTML. Its Notion (API) mode keeps pages and turns Notion databases into Bases ([help](https://obsidian.md/help/import/notion)). | Install, run *Importer: Open importer*, import into a folder of its own (e.g. `Inbox/Import`), then let `/synapsidian:save inbox` or `/synapsidian:ingest` file what matters. Imported notes don't carry synapsidian's frontmatter until they are filed. Disable it afterwards. |

## Browser: Obsidian Web Clipper (optional)

Obsidian's official browser extension for Chromium browsers (Chrome, Brave, Arc), Edge, Firefox and Safari; the install links are on [obsidian.md/help/web-clipper](https://obsidian.md/help/web-clipper). With one template it turns "this page is worth keeping" into a single click: the page lands in `Inbox/` as a synapsidian capture, and `/synapsidian:save inbox` ingests it later (verbatim copy in `Sources/`, integration into your notes, D70). The clip carries only the link and what you selected: synapsidian fetches the page itself, so URL dedup, the content hash and the change check keep working.

In the extension: Settings (cog) → **New template**, then:

| Setting | Value |
|---|---|
| Name | `synapsidian capture` |
| Behavior | Create a new note |
| Note name | `{{date\|date:"YYYY-MM-DD HHmm"}} {{title\|safe_name}}` (the same shape synapsidian gives captures) |
| Note location | `Inbox` |
| Vault | the vault's name exactly as Obsidian shows it |
| Properties | `type` = `capture`; `created` = `{{date\|date:"YYYY-MM-DD"}}`; `source_url` = `{{url}}` |
| Note content | `{{selection}}` |
| Triggers | none needed: with no matching trigger the first template in the list is used, so drag this one to the top |

Use it like this: optionally select the passage that made the page worth keeping (it tells the ingest what you cared about), open the extension, check the title, and save the clip to Obsidian. Don't use templates that save the whole page into the vault: synapsidian keeps its own verbatim copy, and a second one would bypass dedup. For a page behind a login, select the text you need before clipping; `/synapsidian:save inbox` stores that selection as a partial source when it can't fetch the page. Confluence pages are ingested through the Atlassian connector, so a link is enough.

## Not needed, and why

| Plugin | Instead |
|---|---|
| Kanban | Bases has a core kanban view (Obsidian 1.14): `Bases/Tasks.base` and `Ideas.base` → Board, and with synapsidian-projects `Projects.base` plus a board in every project note. Dragging a card to another column changes the note's `status`, so the board is a view of the notes, not a second copy of them that drifts. |
| Dataview | Bases views over frontmatter; synapsidian writes exactly the properties they read. Dataview has had no release since April 2025 (its author moved on to Datacore), and its inline `key:: value` fields sit outside the schema, so `synapsidian validate` can't check them. If you keep it installed, leave **Enable JavaScript Queries** off: a `dataviewjs` block in a copied web page in `Sources/` would run as code (D114). |
| QuickAdd | Templater's *Create* command per template already gives each note type a command and a hotkey. |
| Tasks | Tasks are notes with `status`/`due`/`priority` properties (Tn), shown on the Bases boards and in the brief, not checkboxes. The `- [ ]` action items in meeting notes point to their Tn note; the Tasks plugin would turn them into a second task list whose done dates never reach the note (D114). |
| Linter | It reformats frontmatter and headings on save, which fights the format synapsidian writes. Avoid it in this vault. |
| Calendar | Harmless if you like a month view of daily notes, but nothing in synapsidian uses it. |
