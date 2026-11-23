---
name: incident
description: Write a blameless postmortem of an incident in a project in the synapsidian vault (synapsidian-projects add-on) - an incident note in Projects/<Project>/Incidents/ with a summary, a timeline, the impact, the root cause, what went well and action items filed as tasks - drafted, then made final once the user has reviewed it. Use when something broke for users or a team and the user wants it written up or reviewed ("write a postmortem", "napisz postmortem", "incident report for yesterday's outage", "opisz incydent", "finalise the postmortem", "what action items came out of the outage"). The hunt for a bug's cause is /synapsidian-projects:debug; a single follow-up is /synapsidian:task.
argument-hint: "<what happened> [project <name>] [date YYYY-MM-DD] | final <incident note>"
allowed-tools: Bash(synapsidian *) Bash(synapsidian-projects *) Read Grep Glob
---

# Incident

Request: $ARGUMENTS

Run `synapsidian ref conventions` and follow it: notes in English, search before creating, one commit per run. Talk to the user in their language.

`synapsidian note where` must list `synapsidian-projects` under `extensions`; if it doesn't, send the user to `/synapsidian-projects:setup` and stop.

Incident fields: `project` (required) · `status` draft | final · `date`, the day it happened, which also starts the file name. The postmortem is **blameless**: it describes what the system and the process allowed, never who was at fault; people appear by role, not by name, unless the user asks otherwise.

**Never invent facts.** Times, numbers of users affected, causes and quotes come from the user, the conversation, linked debug notes or meeting notes. Unknown is `TBD`, and the draft says so.

## Draft

1. **Project:** use the one named, or the one the conversation is about. Resolve it with `synapsidian find --type project "<name>"`; ask if none fits.
2. **Search first:** `synapsidian find --type incident "<what happened>"` and `synapsidian find --type debug "<symptom>"`. An existing postmortem of the same event gets updated instead; debug notes about it are sources to link.
3. **Create** it as `draft`, with the date it happened (ask if unclear):
   ```bash
   synapsidian note new --type incident --title "<Checkout down after the payment API change>" --field project="<project title>" \
     --field date=YYYY-MM-DD --field summary="<one sentence: what broke, for whom, how long>"
   ```
4. **Write it** with Edit:
   - **Summary:** three or four sentences: what happened, impact, cause, how it ended.
   - **Timeline:** bullets `HH:MM` (with the time zone once) from the first sign to the all-clear: detection, decisions, mitigation, resolution.
   - **Impact:** who and what was affected, for how long, with numbers when known.
   - **Root cause:** the mechanism, and the conditions that let it reach users; link the debug note.
   - **What went well:** what limited the damage or sped up the fix.
   - **Action items:** one bullet per item, each a task (step 5).
5. **Action items as tasks.** Ask which items to file, then create each as `/synapsidian:task` does (`synapsidian note new --type task ... --field project="<project title>"`) and turn its bullet into the task's `[[link]]` with its priority.
6. Add a hub Log line: `- YYYY-MM-DD: postmortem [[<incident>]] drafted`.

## Final

When the user has reviewed the draft and the `TBD`s are settled or accepted: `synapsidian note set --file "<rel>" --field status=final`, and a hub Log line `- YYYY-MM-DD: postmortem [[<incident>]] final, <n> action items`. A final postmortem is not rewritten later; a new fact goes in as a dated line at the end of the section it changes.

## Finish

```bash
synapsidian commit --skill synapsidian-projects-incident --message "<draft|final> postmortem <title>" "<incident rel>" "<hub rel>" "<task rel>" ...
```

Tell the user: the postmortem as a `[[link]]`, its status, the action items with their tasks, and the `TBD`s left.
