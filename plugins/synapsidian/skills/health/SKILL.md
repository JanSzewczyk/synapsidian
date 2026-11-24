---
name: health
description: Vault health run - applies safe mechanical fixes, then lists what needs a decision (broken links, orphans, schema problems, duplicates, credentials, stale Inbox captures) in today's daily note. Runs from a scheduled task; `apply` links the orphans the user picks. Use when the run fires or the user asks to check the vault ("check the vault health", "sprawdź vault").
allowed-tools: Bash(synapsidian *) Read Edit Grep Glob
argument-hint: "[apply]"
---

# Health

The `synapsidian` command finds the vault by itself. Read `${CLAUDE_PLUGIN_ROOT}/references/conventions.md` first. Usually unattended: don't ask questions (except under `apply`).

Arguments: $ARGUMENTS

Without arguments, go through sections 1 to 3. With `apply`, go to section 4 instead.

## 1. Check and fix

```bash
synapsidian health --fix
```

It applies only the safe fixes (tag format, missing `created` from git, link letter case) and lists the files it changed under `fixed`; everything else is a report under `issues`. Don't fix anything else yourself. Overdue and stuck tasks are not this run's business (the morning brief and the review carry them).

Nothing under `fixed` and nothing worth listing under section 2 → reply "Vault is clean." and stop: no note, no commit.

## 2. Write the Vault health block

```bash
synapsidian note daily
synapsidian block set --file "Daily/<today>.md" --name health --section "Vault health" <<'EOF'
...
EOF
```

English, short, every note a `[[link]]`, at most 8 lines. In this order, omitting what is empty:

1. **Fixed:** one line: how many notes got safe fixes, as links (first three, then "and N more").
2. **Needs a decision**, one line per kind, most serious first: `credentials`, `templater_leftovers` (Templater commands left in a note or a source: a template inserted without running it, or code in a copied page; say to fill the values by hand or remove the code), `broken_blocks` (a generated block whose `<!-- @end -->` line is gone: its skill refuses to refresh it until the line is put back), `schema`, `not_utf8` (notes a fix skipped: save them as UTF-8), `broken_links` (the link and the note it is in), `wanted_notes` (a missing note two or more notes already link to: name it with its sources, as a note worth writing, e.g. a `kind: concept` note via `/synapsidian:save`), `duplicate_titles`, `stale_inbox` (a count and the oldest). Show at most three examples per kind, then the count.
3. **Orphans with a proposal:** `[[Orphan]]`, linked from `[[Source]]` (it names it in plain text) or `[[Related]]` (shares a rare tag or project). Judge each proposal first: drop a `mentioned_in` hit where the name is clearly an ordinary word and not the note's subject, and a `related` one that has nothing to do with it. At most three orphans, then "and N more orphans". Orphans with no proposal count in one line, not one each.

Proposals are never applied here: the user accepts them with `/synapsidian:health apply`.

## 3. Commit

```bash
synapsidian commit --skill health --message "health <today>: <n> fixes, <m> for a decision" "Daily/<today>.md" "<rel>" ...
```

The files are the daily note plus every path under `fixed`. Reply with the block as written.

## 4. Apply (the user is present)

Run `synapsidian health` (report only) and show the orphans that have a proposal. Ask which to link, and where. Then for each accepted one:

- `mentioned_in`: in that note, turn the first plain mention of the orphan's title into `[[Title]]`, outside code, generated blocks (`<!-- @generated -->`) and existing links. Don't rewrite the sentence.
- `related`: add `See also: [[Orphan]]` as the last line of that note, or append to its `See also:` line if it has one.

Edit with the Edit tool, then one commit: `synapsidian commit --skill health --message "link <n> orphans" <rel> ...`. Tell the user which notes changed, as `[[links]]`. Never create a note, never touch `Archive/` or `Sources/`.
