---
name: map
description: Draw or refresh a project's mind map in the synapsidian vault (synapsidian-projects add-on) - an Excalidraw drawing in Projects/<Project>/Maps/ with the project hub in the middle and branches for its open milestones, open tasks, decisions, specs, open changes, bugs under investigation, draft postmortems, architecture overviews, open questions, research, workflows, notes and thinking, each node a link to its note coloured by its status. A refresh adds what is new and drops what closed, and keeps everything the user moved, restyled or drew themselves. Use when the user wants to see a project at a glance or asks for its map ("draw a map of the project", "mapa myśli projektu", "refresh the project map", "odśwież mapę", "mind map for web-app").
argument-hint: "<project> [all | <n> per branch]"
allowed-tools: Bash(synapsidian *) Bash(synapsidian-projects *) Read Grep Glob
---

# Project map

Request: $ARGUMENTS

Run `synapsidian ref conventions` and follow it: one commit per run. Talk to the user in their language.

`synapsidian note where` must list `synapsidian-projects` under `extensions`; if it doesn't, send the user to `/synapsidian-projects:setup` and stop.

## 1. Project

Resolve the project named in the request, or the one the conversation is about: `synapsidian find --type project "<name>"`. Ask if none fits.

## 2. Draw or refresh

```bash
synapsidian query notes --limit 100000 | synapsidian-projects map --project "<project title>" [--max-leaves <n>]
```

A branch shows 10 notes by default and ends in a `+N more` link to the hub's list of the rest. When the user asks for more, or for all (`--max-leaves 0`), pass it; the next refresh uses the default again unless they ask again.

It writes `Projects/<Project>/Maps/<Project> map.excalidraw.md` (`rel`) and reports which nodes it `added`, `updated` and `removed`. Note text is coloured by status: blue under way, orange waiting, grey not settled yet (a proposed decision or change, a draft spec), red an open bug. On a refresh, it keeps the drawing's elements in place:
- generated nodes the user moved, resized or recoloured stay where and as they are;
- a renamed note or a reworded open question keeps its node;
- new nodes go under their siblings, and further down past any box they would cover, the user's own included;
- nodes of notes that left the map are removed (closed tasks, superseded decisions, retired specs, archived notes);
- anything the user drew themselves is never touched.

Exit 2 with "compressed" means the Excalidraw plugin saves compressed drawings. Tell the user to switch off *Compress Excalidraw JSON* in its settings (`/synapsidian:setup` does it too), save the drawing once and run this again.

If the map is open in Obsidian with unsaved changes, the plugin may write its own version over the refresh. Ask the user to close it first, or run the refresh again after they save.

## 3. Link it from the hub

The first time (`created: true`), list the map in a `## Maps` section of the hub, before Project notes:

```bash
synapsidian note fill --file "<hub rel>" --section Maps --before "Project notes" <<'EOF'
- <link from the result>
EOF
```

`kept` means the hub already has a Maps section. Then, if the link isn't in it yet, add it as a bullet with Edit.

## 4. Commit and report

```bash
synapsidian commit --skill synapsidian-projects-map --message "<new|refresh> map of <project>: +<added> -<removed>" "<map rel>" ["<hub rel>"]
```

Tell the user: the map as a link (they open it in Obsidian), what was added and removed, and that they can move nodes and draw on it freely. A refresh keeps their changes.
