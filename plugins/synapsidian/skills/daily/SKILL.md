---
name: daily
description: Create or refresh today's daily note in the second-brain vault, filling its brief with what is due, overdue, in progress and active. Use when the user asks for today's note itself ("open today's note", "daily note", "notatka dzienna"); a morning brief or "what's on today" is /synapsidian:morning. Also when another synapsidian skill needs today's daily note to exist.
argument-hint: "[YYYY-MM-DD]"
allowed-tools: Bash(synapsidian *) Read Grep Glob
---

# Daily note

The `synapsidian` command finds the vault by itself (plugin option `vault_path`); `synapsidian note where` prints its path.
Conventions: `${CLAUDE_PLUGIN_ROOT}/references/conventions.md`

Date: $ARGUMENTS (empty means today)

1. Make sure the note exists (idempotent; it never overwrites):
   ```bash
   synapsidian note daily [--date YYYY-MM-DD]
   ```
2. Get the facts for the brief:
   ```bash
   synapsidian brief --plain [--today YYYY-MM-DD]
   ```
3. Read the block first: `synapsidian block get --file "Daily/<date>.md" --name brief`. If it has a `**Done**` or a `**Needs attention**` line, the morning run wrote it, with the calendar and any add-on sources this skill doesn't read: leave it as it is, show it to the user, say that `/synapsidian:morning` is what refreshes it, and go to step 4. Otherwise write the `brief` block from those facts: overdue and due-today tasks first (as `[[links]]` with priority), then in-progress tasks, then the week ahead, then active projects only if something about them needs attention. At most ~12 bullets; no "About the user" section. Pipe it in:
   ```bash
   synapsidian block set --file "Daily/<date>.md" --name brief <<'EOF'
   - ...
   EOF
   ```
4. If meeting notes exist for the date (`Meetings/<date> ...`), list them in the `agenda` block the same way, one `[[link]]` per line, in time order when known.
5. Never touch `## Notes` (the user's own section) or other blocks.
6. Commit the daily note (`--skill daily --message "brief <date>"`) and show the user the brief in a few lines with the note link.

This brief is built from the vault only; the calendar and any add-on sources come with the `morning` skill.
