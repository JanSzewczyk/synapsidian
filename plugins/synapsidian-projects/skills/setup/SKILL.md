---
name: setup
description: Set up, update or check the synapsidian-projects add-on - install its schema extension, move project notes into their project folders, switch Bases to select notes by type and give every project its board and views. Use after installing it, when a projects skill says the extension is missing, or when the user asks to set up or repair it ("set up synapsidian-projects", "skonfiguruj synapsidian-projects", "add boards to my projects").
allowed-tools: Bash(synapsidian *) Bash(synapsidian-projects *) Bash(command -v synapsidian) Bash(obsidian *) Read Glob
argument-hint: "[check]"
---

# Set up synapsidian-projects

Arguments: $ARGUMENTS (`check` = report only)

Talk to the user in their language. Everything here is idempotent. Run `synapsidian ref conventions` and follow it.

## 1. Check

```bash
command -v synapsidian || echo "synapsidian plugin missing"
synapsidian setup check
synapsidian query notes --type project
```

If `synapsidian` is missing, stop: synapsidian-projects depends on the synapsidian plugin (`/plugin install synapsidian@<this marketplace>`), and the user must run `/synapsidian:setup` first. If the vault isn't `ready` for any reason other than a plugin in `community_plugins_required` with `required_by: synapsidian-projects` (step 2b installs those), send the user to `/synapsidian:setup` and stop.

Report as a short checklist (✅ / ❌):
- **Extension:** `extensions` in the check lists `synapsidian-projects` with the `version` of `$(synapsidian-projects extension)/extension.yaml`. Missing or different means step 2 installs it.
- **Plugins:** each plugin listed under `plugins` in `$(synapsidian-projects extension)/extension.yaml` (the add-on's own copy: the check lists only those of the extension already in the vault, which may be older) is installed and enabled in `.obsidian/community-plugins.json` and `.obsidian/plugins/<id>/`. Today: **Folder notes** (D115), so a click on a project's folder opens its hub, and **Excalidraw Extras** (D154), the Excalidraw companion that turns Mermaid (a roadmap or a flow) into an editable drawing.
- **Boards:** each project note (from the query; read it) has a `## Board` and a `## Links` section. List the ones that don't.
- **Repositories on this device** (D139-D143): for each hub with a `repo`, run `synapsidian-projects repo resolve --state "<state>" --repo "<repo>" [--path "<path>"]`, where `<state>` is the `state` from `synapsidian note where`. Show `how` per hub in one line: `local` (a path, here), `elsewhere` (a path from another device), `map` (a URL with its clone here), `missing` (a URL with no clone here yet) or `mismatch`. These are information: none of them makes the add-on not ready.

With `check`, stop here.

## 2. Install the extension

```bash
synapsidian setup extension --from "$(synapsidian-projects extension)"
```

It copies the extension into `<vault>/.synapsidian/extensions/synapsidian-projects/` (tracked in the vault's git, so the vault keeps validating on a device without the add-on), adds the `project` type, the property types and the `Projects` and `By project` Bases, and makes one commit. The same run:
- **files notes into their folders**, in a commit of its own (`refiled` in the result): each hub `Projects/<Project>.md` moves into `Projects/<Project>/<Project>.md`, and each task, decision, research dossier, how-to, note or thinking note with a `project` moves from its type's flat folder to `Projects/<Project>/<Tasks|Decisions|Research|Workflows|Notes|Thinking>/`. Names don't change, so links keep working. A note whose target is taken stays and is listed under `skipped`: tell the user;
- **switches old Bases to type filters**: a Base whose top-level filter picks a type by its folder (`file.inFolder("Tasks")`) picks the type outside `Archive/` instead, since a folder filter would miss nested notes. Only that filter line changes (`updated` in the result).

An unchanged extension makes no commit. Re-run it after every synapsidian-projects update.

If `schema_warnings` in `synapsidian setup check` says synapsidian-work's extension also defines `architecture`, that extension is older than synapsidian-work 0.3.0. The vault still works: synapsidian-projects' definition is used. Tell the user to run `/synapsidian-work:setup` to update it.

## 2b. The add-on's Obsidian plugins

The extension lists the community plugins it needs (`plugins` in its `extension.yaml`), and `synapsidian setup check` now reports them in `community_plugins_required` with `required_by: synapsidian-projects`. Install the ones not installed and enabled exactly as step 5 of `/synapsidian:setup` does (`synapsidian ref obsidian-plugins` explains each): Restricted mode stays the user's call, ask once naming the plugins, then `obsidian vault=<vault> plugin:install id=<id> enable` for each, and `synapsidian setup check` again. When it can't be done here, file or update the one "Install the Obsidian plugins synapsidian needs" task the way that step says.

Folder notes needs no settings: its defaults (a note named like its folder, inside it) are the hub's place. Tell the user in one line that a project's hub no longer shows as a file under its folder; clicking the folder opens it. Excalidraw Extras needs none either; without it Excalidraw asks for it the first time a Mermaid diagram is converted.

Installing isn't required of this step: a plugin left out (no CLI, Restricted mode on, the user said not now) goes under Still needed in the report (step 6), with how to add it.

## 3. Architecture notes into their projects

Architecture notes came from synapsidian-work's architect before synapsidian-work 0.3.0 (D109). They have no `project` and sit in `Architecture/`. Find them:

```bash
synapsidian query notes --type architecture --where "project="
```

None: skip this step. Otherwise, group them by `app`. Each app belongs to one project, by default a project titled like the app:
1. Look for it with `synapsidian find --type project "<app>"`, plus the vault's own rules in `About.md`.
2. Show the user the mapping (app → project, and which hubs are new) and ask once. An unattended run uses the default mapping and reports it.
3. Create a missing hub as a repository project, its summary taken from the app's overview note:
   ```bash
   synapsidian note new --type project --title "<app>" --field kind=repository --field summary="<one sentence>"
   ```
4. Its `repo` is the repository: its URL, or a local path, chosen as `/synapsidian-projects:project` does for a new hub (D139). A note's `path` is the app's folder from the repository root.
   - Another hub may already name the repository of a monorepo that holds several apps: then propose that same `repo`, check that the app's folder exists in this device's clone (Glob), and say it was inferred.
   - Otherwise ask for the clone's path, or leave `repo` empty and report it.
5. Then give each note its project. `note set` moves it into `Projects/<Project>/Architecture/` and prints `from` and `rel`; names don't change, so links keep working:
   ```bash
   synapsidian note set --file "<rel>" --field project="<project title>"
   ```
6. Make one commit with the new hubs and both paths of every moved note:
   ```bash
   synapsidian commit --skill synapsidian-projects-setup --message "architecture notes into <n> projects" "<hub rel>" "<from>" "<rel>" ...
   ```

The old `Architecture/` folder is empty afterwards; tell the user they can delete it. Refresh the notes with `/synapsidian-projects:architect <project>`.

## 4. A board on every project

New project notes get the board, the Links list and the project-notes views from the hub template (also when made by hand in Obsidian from `Templates/Generated/Project.md`, D110). Existing ones get them here, without touching anything the user wrote. For each project note without a `## Board` section:

```bash
synapsidian-projects section Board | synapsidian note fill --file "<project note rel>" --section Board --before Goal
synapsidian-projects section "Project notes" | synapsidian note fill --file "<project note rel>" --section "Project notes" --before Log
```

And for each one without a `## Links` section:

```bash
synapsidian-projects section Links | synapsidian note fill --file "<project note rel>" --section Links --before Status
```

`fill` writes a section only when it is empty or missing (`added` / `filled`); `kept` means the user already has one: leave it.

Hubs made before synapsidian-projects 0.7.0 have a Project notes block without the Debug and Incidents views (D111); `Bases/Debug.base` and `Bases/Incidents.base` list those notes meanwhile. Name such hubs and ask once; on a yes, Edit each block to add the two views exactly as `synapsidian-projects section "Project notes"` prints them, before the Architecture view, and change nothing else in it.

Hubs made before synapsidian-projects 0.10.0 (D145) have no `## Roadmap` section. Add it to each, as above (`fill` writes only a missing or empty section):

```bash
synapsidian-projects section Roadmap | synapsidian note fill --file "<project note rel>" --section Roadmap --before "Key decisions"
```

Hubs made before synapsidian-projects 0.11.0 (D147) have no `## Risks` section. Add it to each the same way:

```bash
synapsidian-projects section Risks | synapsidian note fill --file "<project note rel>" --section Risks --before "Open questions"
```

Their Project notes block also lacks the Milestones view, and their Board doesn't show `milestone` and `blocked_by` on its cards; `Bases/Milestones.base` lists milestones meanwhile. Name such hubs and ask once, together with the Debug and Incidents question when both apply; on a yes, Edit each hub: add the Milestones view as the first view of the Project notes block, and `milestone` and `blocked_by` at the end of the Board view's `order`, exactly as `synapsidian-projects section` prints them, and change nothing else.

Then one commit of the project notes you changed:

```bash
synapsidian commit --skill synapsidian-projects-setup --message "board, links, roadmap, risks and project views on <n> projects" "<rel>" ...
```

## 5. Repositories as URLs, on request

A local path in a hub works on one device only. A URL works on every device the vault syncs to, each finding its own clone. Both are valid (D139), so nothing switches without the user's yes, and an unattended run skips this step.

From the resolves in step 1, take the hubs with `how: local`, a non-null `origin`, and a title not in `keep_path` (`synapsidian-projects repo list --state "<state>"` prints it). None: skip this step. Otherwise show one line per hub, `[[<title>]]`: `<repo>` → `<origin>`, plus `path <path_in_repo>` when that isn't null. Ask once which to switch (all, some, none). Then:
- **Each hub to switch:**
  ```bash
  synapsidian note set --file "<hub rel>" --field repo="<origin>" [--field path="<path_in_repo>"]
  synapsidian-projects repo bind --state "<state>" --repo "<origin>" --clone "<toplevel>"
  ```
  Keep a `path` the hub already has unless `path_in_repo` replaces it. The other device needs nothing now: its first refresh finds its own clone, or asks once.
- **Each hub to keep as a path:** `synapsidian-projects repo keep-path --state "<state>" --title "<title>"`, so this step doesn't ask again on this device.

Also name the hubs with `how: elsewhere` (paths from another device: switch them there) and the absolute `docs` entries (they hold on one device only). Then one commit of the switched hubs:

```bash
synapsidian commit --skill synapsidian-projects-setup --message "repositories as URLs on <n> projects" "<hub rel>" ...
```

## 6. Finish

Run `synapsidian setup check` once more and end with the setup report: `synapsidian ref setup-report` gives its three groups (✅ ready, ➕ added in this run, ❗ still needed). Under Added, name:
- the extension version installed, how many notes were moved into project folders (and any skipped), and the Bases switched to type filters;
- the Obsidian plugins installed;
- the architecture notes moved, and the hubs created for them;
- the projects that got a board, roadmap, risks or views, as `[[links]]`;
- the hubs switched to URLs and the ones kept as paths.

Under Still needed: each plugin from step 2b that isn't installed and enabled, with what it gives and how to add it, and the hubs whose repository has no clone on this device (`how: missing`).

After the report, one line on how filing works now: a project's hub is `Projects/<Project>/<Project>.md`; a task, decision, research dossier, how-to (workflow), note or thinking note created with a `project` goes under that folder (specs, changes, milestones, bug investigations and postmortems always belong to one), and setting `project` later with `synapsidian note set` moves it there. Dragging a card on a project's board changes the task's status.
