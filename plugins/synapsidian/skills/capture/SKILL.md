---
name: capture
description: Drop a quick thought, link or snippet into the second-brain vault's Inbox exactly as given, with no processing. Use when the user wants to jot something down fast ("capture this", "note this down", "wrzuć do inboxa", "zanotuj szybko") or when an idea comes up mid-task that should not interrupt the work. For filing things properly from a conversation use /synapsidian:save instead.
argument-hint: "<text or URL>"
allowed-tools: Bash(synapsidian *)
---

# Capture to Inbox

The `synapsidian` command finds the vault by itself (plugin option `vault_path`); `synapsidian note where` prints its path.

Text: $ARGUMENTS

Captures are raw by design: no searching, no linking, no rewriting (D51). Sorting happens later in `/synapsidian:save inbox`. The fastest way needs no skill at all: a prompt that starts with `>>` is saved to `Inbox/` by a hook and never reaches the model (D137); mention it when the user captures often.

1. Pick a title of 3-6 words from the text (English). If the text is a URL, pass it as `source_url` too.
2. Create the note with the text exactly as given as its body (keep the user's wording and language):
   ```bash
   synapsidian note new --type capture --title "<title>" [--field source_url="<url>"] --body-file - <<'EOF'
   <the text>
   EOF
   ```
3. Commit it:
   ```bash
   synapsidian commit --skill capture --message "<title>" "<rel from step 2>"
   ```
4. Reply with one line: the note link. Then carry on with whatever the user was doing.
