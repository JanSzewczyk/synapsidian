---
name: spec
description: Write or update a specification in the synapsidian vault (synapsidian-projects add-on) - a living document of how part of a project should work (purpose, scope, requirements, design, open questions), kept in Projects/<Project>/Specs/ and edited in place, with git as its history. Use when the user wants to specify, describe or pin down how a feature, module, API, process or system should behave, or to update such a description ("write a spec for", "spisz specyfikację", "update the checkout spec", "zaktualizuj specyfikację", "what does the spec say about"). A change to make is /synapsidian-projects:change; a decision between options is /synapsidian-projects:decide.
argument-hint: "<subject> [project <name>] | update <spec> ..."
allowed-tools: Bash(synapsidian *) Bash(synapsidian-projects *) Read Grep Glob
---

# Spec

Request: $ARGUMENTS

Run `synapsidian ref conventions` and follow it: notes in English, search before creating, one commit per run. Talk to the user in their language.

`synapsidian note where` must list `synapsidian-projects` under `extensions`; if it doesn't, send the user to `/synapsidian-projects:setup` and stop.

A spec says how something **should** work now. It is edited in place, and git keeps its history, so it never collects dated "update" paragraphs. Fields: `project` (required) and `status`: `draft` while it is being worked out, `current` once the user agrees it holds, `retired` when the thing is gone or another spec replaced it.

**Never invent requirements.** What the user said, what the project's notes, decisions and code show (read only; a repository is never written to) goes in. Anything else is an open question, or `TBD`.

## New

1. **Project:** use the one named, or the one the conversation is about. Resolve it with `synapsidian find --type project "<name>"`; ask if none fits.
2. **Search first:** `synapsidian find --type spec "<subject>"`, plus one other phrasing. If a spec covers the subject, update it instead.
3. **Create.** Titles must be unique across the vault, so start a generic subject with the project's name (`web-app API`, not `API`):
   ```bash
   synapsidian note new --type spec --title "<subject>" --field project="<project title>" \
     --field summary="<one sentence: what it specifies>"
   ```
4. **Write it** with Edit:
   - **Purpose:** what it is for and who uses it, in two or three sentences.
   - **Scope:** `In:` and `Out:` bullets.
   - **Requirements:** numbered `R1`, `R2`, ... One testable statement each, using "must" or "should". Link the decision a requirement comes from.
   - **Design:** how it works: components, data, flows. Short; link notes and research rather than repeat them.
   - **Open questions:** bullets.
5. Add a hub Log line: `- YYYY-MM-DD: spec [[<spec>]] drafted`.

## Update

Read the spec, then edit it in place:
- Change the requirement or section that changed. Keep `R` numbers stable: a removed requirement keeps its number, struck through with the reason (`~~R4 ...~~ dropped, see [[decision]]`), so links and talk about "R5" stay right.
- When a decision or a change caused the edit, link it next to what changed.
- Move an answered open question into the section it settles.
- Status: `synapsidian note set --file "<rel>" --field status=current` when the user agrees the spec holds, `retired` when it no longer applies. Add a hub Log line for either.

## Finish

```bash
synapsidian commit --skill synapsidian-projects-spec --message "<new|update> spec <title>: <what changed>" "<spec rel>" ["<hub rel>"]
```

Tell the user: the spec as a `[[link]]`, its status, what changed, and the open questions left.
