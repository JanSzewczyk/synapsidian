---
name: debug
description: Keep the investigation of one bug (synapsidian-projects add-on) - a note in Projects/<Project>/Debug/ with the symptom, reproduction, what was ruled out, the root cause and the fix, closed as fixed or wontfix. Use when the user is chasing a bug and wants it written down, or wants to find what was learned before ("log this bug investigation", "zapisz debugowanie", "the bug is fixed", "did we see this error before"). A postmortem of an outage is /synapsidian-projects:incident.
allowed-tools: Bash(synapsidian *) Bash(synapsidian-projects *) Read Grep Glob
argument-hint: "<the bug> [project <name>] | update|fixed|wontfix <debug note>"
---

# Debug

Request: $ARGUMENTS

Run `synapsidian ref conventions` and follow it: notes in English, search before creating, one commit per run. Talk to the user in their language.

`synapsidian note where` must list `synapsidian-projects` under `extensions`; if it doesn't, send the user to `/synapsidian-projects:setup` and stop.

Debug fields: `project` (required) · `status` investigating | fixed | wontfix. The note is a lab notebook: what was observed and tried stays, even when it led nowhere, since a dead end is what saves the next person an afternoon.

**Never invent facts.** Error messages, commands, versions and causes come from the conversation, the user or the code (read only; a repository is never written to). A cause not yet proven is a hypothesis and says so.

## Open

1. **Project:** use the one named, or the one the conversation is about. Resolve it with `synapsidian find --type project "<name>"`; ask if none fits.
2. **Search first:** `synapsidian find --type debug "<error text or symptom>"`, plus one other phrasing. A note on the same bug gets updated instead; a closed one is reopened with `--field status=investigating` and a dated line under Investigation.
3. **Create** it, titled by the symptom as a user sees it:
   ```bash
   synapsidian note new --type debug --title "<Checkout total ignores the discount>" --field project="<project title>" \
     --field summary="<one sentence: what goes wrong, where>"
   ```
4. **Write it** with Edit:
   - **Symptom:** what happens and what should happen; the exact error in a code block; where and since when.
   - **Repro:** numbered steps, with the environment and version. `TBD` until someone can reproduce it.
   - **Investigation:** dated bullets, one per hypothesis or experiment, each with its result (`ruled out`, `confirmed`, `inconclusive`). Link files as `path:line`, commits by hash.
   - **Root cause** and **Fix** stay empty until known.
5. Add a hub Log line: `- YYYY-MM-DD: investigating [[<debug note>]]`.

## Update, fixed, wontfix

Find the note with `synapsidian find --type debug "<words>"` and read it.

- **Update:** add dated bullets under Investigation; when the cause is proven, write Root cause: the mechanism, not only the line that was wrong.
- **Fixed:** write Fix: what changed and why it addresses the root cause, linking the commit, pull request, change (`[[...]]`) or task. Then `--field status=fixed`, and a hub Log line `- YYYY-MM-DD: [[<debug note>]] fixed: <cause in a few words>`.
- **Wontfix:** say why under Fix (cost, rare, superseded) and any workaround, then `--field status=wontfix` and a hub Log line.
- Follow-up work (a test, a guard, a cleanup) becomes tasks as `/synapsidian:task` makes them, with the project; ask first. If the bug was an outage people felt, suggest `/synapsidian-projects:incident` for the postmortem.

## Finish

```bash
synapsidian commit --skill synapsidian-projects-debug --message "<open|update|fixed|wontfix> debug <title>" "<debug rel>" ["<hub rel>"] ...
```

Include tasks this run created. Tell the user: the note as a `[[link]]`, its status, the root cause (or the leading hypothesis), and what is left to try.
