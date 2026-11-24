---
name: save
description: File what matters from the current conversation into the vault - decisions, tasks, people facts, knowledge, how-tos, ideas and project progress - updating existing notes and adding a devlog line. Use when the user says to save or remember the session ("save this", "zapisz to", "remember this decision"), at the end of substantial work, or with "inbox" to sort Inbox captures.
allowed-tools: Bash(synapsidian *) Read Grep Glob
argument-hint: "[inbox] [focus or hint]"
---

# Save to the vault

The `synapsidian` command finds the vault by itself (plugin option `vault_path`); `synapsidian note where` prints its path. Session: `${CLAUDE_SESSION_ID}`

Arguments: $ARGUMENTS

Read both references before writing anything:
- `${CLAUDE_PLUGIN_ROOT}/references/conventions.md` (how to write)
- `${CLAUDE_PLUGIN_ROOT}/references/extraction.md` (what is worth keeping)

## 1. Collect

- **Conversation mode** (default): go through this conversation and list candidate items by kind (decision, task, person fact, knowledge, how-to, idea, project progress) per `extraction.md`. If the user gave a focus, keep to it.
- **Inbox mode** (`inbox`): the items are the notes in `Inbox/`. Read each one; decide what it becomes (one of the kinds above), or whether it should stay as is because it needs the user. A capture that is essentially a link (a URL body or a `source_url`, with at most a line of comment or a passage the user selected on the page, as the Web Clipper template saves it) is a source: ingest it per `${CLAUDE_PLUGIN_ROOT}/references/ingest.md` (steps 1-5, the comment or selection tells you what the user cared about), then archive the capture as below (D70). When the page can't be fetched (it sits behind a login) and the capture holds text the user selected there, store that text with `synapsidian source add --capture-scope partial` instead.

Drop anything the extraction guide says not to keep. If nothing is left, say so and stop: no commit.

## 2. Place each item

For every item, search before creating (`synapsidian find "<name or topic>"`, at least two phrasings for anything that could already exist; `--type person` for names, and `--type project` when the vault has projects, see conventions). Then:

- **Existing note found:** Edit it in place, in the right section. Update stale statements instead of appending contradictions; when a fact changes, keep the old one with its date in `## History` or `## Log` if it matters.
- **No note:** `synapsidian note new ...` with a specific `summary`, then fill the body.
- **Tasks:** `--field source=save --field source_link="<today's daily note date>"`; skip tasks completed during the conversation.
- **Links:** connect what belongs together (decision ↔ project, task ↔ project, person ↔ meeting). Link only to notes that exist. For each new `note`, `howto`, `decision` or `idea`, `synapsidian find --related "<its title>"` shows the notes most like it; link it from the best unlinked one (`linked: false`) where it fits the text, so it doesn't start as an orphan.

In inbox mode, once an item is filed, archive the capture so nothing is deleted: `synapsidian note archive --file "<Inbox/...>"`, and include both the old and the new path in the commit.

## 3. Devlog

`synapsidian note daily` (creates today's note if needed), read the current `devlog` block (`synapsidian block get ... --name devlog`), and write it back with one new bullet for this session per `extraction.md` (skip in inbox mode unless real work was filed).

## 4. Record and commit

1. Commit all touched files in one commit, and record this session as saved so the evening run doesn't extract it a second time:
   ```bash
   synapsidian commit --skill save \
     --record-session "${CLAUDE_SESSION_ID}" --message "<main items, e.g. decision XLSX-first export, T15>" "<rel>" ...
   ```
   In inbox mode leave out `--record-session`.
2. Report to the user: one line per note touched, `created` or `updated`, as `[[links]]`, then anything you deliberately left out and why (in one line).
