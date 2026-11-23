---
name: setup
description: Set up or repair the synapsidian vault end to end - check Obsidian, uv and git, create the vault layout, configure Obsidian and its community plugins, register the vault and fill in About.md. Use the first time the plugin is used, when the user asks to set up, install, configure, repair or check the vault ("set up synapsidian", "skonfiguruj vault", "is synapsidian set up correctly"), or when another synapsidian skill reports the vault is missing.
argument-hint: "[check]"
allowed-tools: Bash(synapsidian *) Bash(obsidian *) Bash(command -v synapsidian-work) Bash(command -v synapsidian-projects) Read AskUserQuestion
---

# Set up the synapsidian vault

The `synapsidian` command takes the vault path from the plugin option `vault_path` (set when the plugin was enabled; change it in `/plugin` → synapsidian → configure).

Arguments: $ARGUMENTS (`check` = report only, change nothing)

Talk to the user in their language. Everything below is idempotent: re-running it on a working vault changes nothing and says so.

## 1. Check

```bash
synapsidian setup check
```

Show the user a short checklist from the result (✅ / ❌ per line): Obsidian installed and version ≥ `minimum`, vault folder, git repo, folders, About.md, registered in Obsidian, Obsidian CLI (optional), each plugin in `community_plugins_required` (installed, enabled, `settings_unset` empty), each in `community_plugins_recommended` (installed and enabled, or "optional" when not; never ❌), and the `automation` block (uv where hooks look for it, `jq` or `python3` for the session-end hook, the hook events, how many sessions wait in the queue; list its `problems`). If `$ARGUMENTS` is `check`, stop here and list what `/synapsidian:setup` would fix.

Blocking problems and their fixes, which **the user** runs, not you:

| Problem | Tell the user |
|---|---|
| Obsidian not installed | `obsidian.install` from the result (it fits the user's operating system) |
| `version_ok: false` | Update Obsidian (Settings → General → Check for updates); Bases kanban needs ≥ 1.14 |
| `version_ok: null` | synapsidian can't read the version on this system yet: ask the user to check Settings → General shows at least `minimum` (not blocking) |
| `uv` missing | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| No git identity | Ask for the name and email to sign vault commits with |

## 2. About the user

If `about_exists` is false, ask with AskUserQuestion (one round, free text allowed via "Other"): what the user does (`role`: a job title, "student", "freelance designer", anything) and their usual working or focus hours. Each question needs at least two options: offer plausible ones from what you already know plus "Skip". The timezone is detected automatically. Don't invent answers; leave out what the user skips. Don't ask about an employer, team or manager: the vault may be personal, and the synapsidian-work add-on asks for those itself.

## 3. Apply

```bash
synapsidian setup apply [--about role="..." --about working_hours="..."]
```

This creates the folders, `.gitignore`, `About.md`, `Templates/Daily.md`, a Templater template per note type in `Templates/Generated/` (generated from the schema, the add-ons' types included, D110, D119), the `Bases/*.base` views (task kanban board, due this week, calendars of tasks, meetings and goals, people, inbox, ideas, decisions; projects come with the synapsidian-projects add-on), and Obsidian's config:

| File | What synapsidian sets |
|---|---|
| `.obsidian/core-plugins.json` | Bases, Properties, Daily notes, Backlinks, Outgoing links, File recovery, Canvas, ... on |
| `.obsidian/app.json` | new notes → `Inbox/`, attachments → `Attachments/`, wikilinks, shortest link format, always update links on rename, deleted files → vault `.trash` |
| `.obsidian/daily-notes.json` | folder `Daily`, format `YYYY-MM-DD`, template `Templates/Daily` (same shape as `/synapsidian:daily`) |
| `.obsidian/types.json` | property types from the synapsidian schema (`due`, `date`, `created`, `done_on` as dates, `attendees` as lists, ...) |

A later `apply` rewrites a template in `Templates/Generated/` (and `Templates/Daily.md`) when synapsidian's version changed, and removes one synapsidian no longer ships, but only while the file is as synapsidian wrote it: one the user edited stays and is listed in `kept_user_settings`. Mention those. A vault from before synapsidian 0.29.0 had them in `Templates/Synapsidian/`: `apply` moves them and Templater's folder over (D119). For an edited one left there, say that Templater no longer lists it and offer to move it into `Templates/Generated/` under a new name.

The core **Templates** plugin, pointed at a folder that holds `Templates/Generated/`, pastes synapsidian's templates as raw JavaScript (D118). When `core_templates_off` is true, `apply` turned it off: tell the user in one line why, and that Obsidian needs a reload before it shows (command palette → *Reload app without saving*, or quit and reopen it). When `check` still reports `core_templates_clash`, the folder holds the user's own core templates (`own_templates`). Name them and ask with AskUserQuestion: turn core Templates off, or move their templates to a subfolder (`Templates/Core/`) and point the plugin's folder there. Do the chosen fix only on their answer.

It then makes the vault a git repo (commits signed with the user's git identity) and commits what it created. Settings the user already changed are kept and listed in `kept_user_settings`: mention them; don't override them unless the user asks.

`About.md` has a `## Rules` section for the user's own rules for Claude in this vault, and a `protected` property listing folders or files Claude must ask about before touching. An older `About.md` gets the empty section appended (`updated` lists it). When `About.md` was created or updated, tell the user in one line that both exist and that every session reads them. Don't ask for rules now.

For installed required plugins it also writes synapsidian's settings into their `data.json` (listed in `plugins_configured`); step 5 installs them first.

Person and goal notes made before synapsidian 0.30.0 have no views of their meetings and tasks (`## Meetings and tasks`, `## Linked work`; D133). Find them with `synapsidian query notes --type person` and `--type goal` (a note whose body lacks the heading) and, on the user's yes, add the section to each: `synapsidian note section --type person --section "Meetings and tasks" | synapsidian note fill --file "<rel>" --section "Meetings and tasks"` (and `--type goal --section "Linked work"`). `fill` keeps a section the user already wrote. One commit for all of them.

Tasks from older versions with `ZAD-n` ids become `Tn` (id, file name and every link to the file, one commit of their own). When `task_ids` isn't null, list what was renamed, any `skipped` task with its reason, and the `mentions_left`: plain-text `ZAD-n` synapsidian left alone because it can't tell its own task from another tool's (a Notion card); offer to change the ones the user says are vault tasks.

## 4. Register the vault in Obsidian

Obsidian only opens folders it knows. If `registered_in_obsidian` is false, offer two ways with AskUserQuestion:

1. **Automatic (Recommended):** the user quits Obsidian (`obsidian.quit` from the check result), then you run
   ```bash
   synapsidian setup register
   ```
   It refuses while Obsidian is running (Obsidian would overwrite the change), backs up Obsidian's registry first, and prints `open_with`, the command that opens the vault on this system. This edits Obsidian's own settings file, which is undocumented, so say so and get a clear yes first. Where the system can't tell whether Obsidian runs (`running: null` in the refusal), ask the user to confirm it is closed, and only on their yes run `synapsidian setup register --obsidian-closed`.
2. **Manual:** in Obsidian, *Open folder as vault* → choose the vault folder.

After the automatic way, give the user the exact `open_with` command from the result.

## 5. Community plugins

Read `${CLAUDE_PLUGIN_ROOT}/references/obsidian-plugins.md`. synapsidian requires four community plugins (D91, D110, D115): **Git** (history and undo for the user's own edits), **Excalidraw** (drawings in notes), **Templater** (notes made by hand in Obsidian from the generated templates in `Templates/Generated/`) and **Calendar Bases** (the Calendar views of the task, meeting and goal Bases). An installed add-on can require more: `community_plugins_required` lists each with `required_by` (synapsidian-projects requires **Folder notes**, so a click on a project's folder opens its hub). Kanban boards, tables and properties stay core Obsidian; say so, since many guides tell people to install Dataview, Tasks or Kanban (D114: none is needed).

Once Templater is installed, tell the user in two lines how to make a note (command palette → *Templater: Create new note from template* → `Templates/Generated/...`) and to leave **Trigger Templater on new file creation** off, with the reason from the reference. synapsidian can't read that switch; never ask the user to turn it on.

For each plugin in `community_plugins_required` that isn't installed and enabled, try to do it yourself through the Obsidian CLI. `<vault>` below is the vault's folder name.

1. This needs `obsidian.cli_on_path` and the vault registered in Obsidian (step 4). Without them, go to the task below.
2. `obsidian vault=<vault> plugins:restrict` tells whether Restricted mode is on. If it is, don't turn it off: it is Obsidian's safeguard against third-party code and the user's call. Ask the user to switch it off themselves (Settings → Community plugins → *Turn on community plugins*) and to say when done; if they'd rather not now, go to the task.
3. Ask once with AskUserQuestion before installing (it is third-party code, fetched by Obsidian from its plugin directory), naming the plugins. On yes, for each: `obsidian vault=<vault> plugin:install id=<id> enable`.
4. Run `synapsidian setup apply` again: it writes synapsidian's settings for the newly installed plugins. For each id in `plugins_configured`, run `obsidian vault=<vault> plugin:reload id=<id>`; a plugin that was already running keeps its old settings in memory and would write them back.
5. `synapsidian setup check` must now show each plugin installed, enabled, with `settings_unset` empty. Settings the user had chosen differently show up in `kept_user_settings`: mention them, don't override them.

**When something can't be done here** (no CLI, the vault not registered, Restricted mode left on, an install that failed, or the user said not now), file it as one task so it isn't forgotten. First `synapsidian find --type task "Obsidian plugins synapsidian needs"`; if an open task exists, update its body instead of adding a second one. Otherwise:

```bash
synapsidian note new --type task --title "Install the Obsidian plugins synapsidian needs" \
  --field summary="Install and enable <plugins>, which synapsidian requires; then run /synapsidian:setup to configure them" \
  --field priority=high --field source=manual --body-file - <<'EOF'
<body>
EOF
synapsidian commit --skill setup --message "task: install the Obsidian plugins synapsidian needs" "<rel>"
```

The body, in the user's language, from the reference: why each missing plugin is needed (one line each); the steps (Restricted mode off, Browse, search the plugin, Install, Enable, for each one); then "run `/synapsidian:setup` again and synapsidian applies its settings", followed by the same settings as a manual alternative with where each one is in the plugin's settings tab. Name only what is still missing: an enabled plugin with `settings_unset` needs only the settings part. Tell the user the task's `[[Tn ...]]` link.

**Recommended plugins.** For each plugin in `community_plugins_recommended` that isn't installed and enabled (today **Claudian**: Claude Code in Obsidian's sidebar, so synapsidian's skills run beside the open note), say in one line what it gives and offer it in the same AskUserQuestion as the required ones, as a separate choice. Install it only on a yes, the same way. A no is fine: `ready` never waits for it, and it goes in no task.

Then present the rest of the reference as a short table, as options the user installs if they want: Omnisearch (in-app search), Importer (one-off move from Notion, Evernote and others), the Web Clipper browser extension with its `synapsidian capture` template, and the common plugins that aren't needed here and why (Linter actively conflicts). Don't install these.

## 6. Optional extras

Mention these as optional, one line each, without doing them:
- **Obsidian CLI** (lets synapsidian open notes and rename with link updates): Obsidian → Settings → General → Advanced → *Command line interface* → enable, then *Register* (asks for the admin password).
- **kepano/obsidian-skills** (Obsidian's own skills for Markdown, Bases and Canvas syntax): `/plugin marketplace add kepano/obsidian-skills` then `/plugin install obsidian@obsidian-skills`.

## 7. Verify the session capture

Hooks of a freshly installed plugin load only in a new session, so run this once the user is in one:

```bash
synapsidian setup selftest
```

It feeds a fake SessionEnd to the hook against a throwaway vault (the real queue stays clean), reads the row back through uv, and runs the SessionStart brief on the real vault. Show each check; on a failure, give its `detail` and the fix (usually uv or `jq`/`python3` missing).

## 8. Report

Run `synapsidian setup check` once more and end with the setup report: `${CLAUDE_PLUGIN_ROOT}/references/setup-report.md` gives its three groups (✅ ready, ➕ added in this run, ❗ still needed). Under Still needed, also name each add-on that is on PATH (`command -v synapsidian-work`, `command -v synapsidian-projects`) but has no extension in the check's `extensions`, with its setup skill as the fix. Whether an installed extension is out of date is for the add-on's own setup to say (D90).

When nothing is left under Still needed, suggest next steps after the report: `/synapsidian:daily` to start today's note, `/synapsidian:task add ...`, and `/synapsidian:save` at the end of a working session.

Then ask once whether to schedule the recurring runs (vault health, morning, evening, review) and, on yes, continue with `/synapsidian:schedule`: without the evening run the session queue is never turned into devlogs.
