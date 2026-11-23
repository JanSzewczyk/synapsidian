---
name: find
description: Search the user's second-brain vault and answer from it, citing notes as [[links]]. Use when the user asks what they know, decided or planned about something, or refers to past work, people or decisions ("what did we decide about...", "do I have notes on...", "znajdź w notatkach"), and before creating a note, to check it doesn't exist.
allowed-tools: Bash(synapsidian *) Read Grep Glob Agent
argument-hint: "<question or keywords>"
---

# Find in the vault

The `synapsidian` command finds the vault by itself (plugin option `vault_path`); hits carry each note's absolute `path` for Read.

Question: $ARGUMENTS

Run this in an Explore subagent (D131), so the notes it reads stay out of this conversation: spawn it with the Agent tool (`subagent_type: Explore`) and a prompt that holds the question above, with any names or dates it needs, and the steps below, because it does not see the conversation. Relay its answer and `[[links]]`, not the notes' text, and read no notes yourself. If no subagent tool is available, do the steps yourself.

1. Notes are written in English, and the search matches words, not meaning. If the question is in another language, translate it to English keywords first (keep names, ticket keys and product terms as they are). Then run the ranked search:
   ```bash
   synapsidian find "<question>"
   ```
   Add `--type <type>` when the user clearly means one kind of note (task, person, decision, project, meeting, howto, note, idea, goal), and `--all` when they ask about archived or source material.
2. If the top hits don't answer it, search again with **different words**: synonyms, the likely note title, a person's or project's name, a ticket key. Two or three searches is normal. Fall back to `Grep` over the vault for exact strings (ticket keys, error messages, emails).
3. Read the notes that look relevant (Read the file, not just the snippet) and follow `[[links]]` one hop when the answer is spread across notes.
4. Answer in the user's language, short, citing each claim with the note it came from as `[[Note title]]`. Quote the note's own words when precision matters.
5. If nothing relevant turns up, say so and list what you searched for ("searched: 'export format', 'XLSX', 'ABC-123'; 0 matching notes"). Never say a note doesn't exist without having searched.

**What relates to a note** ("what's related to X", "co jeszcze dotyczy X"): `synapsidian find --related "<note title>"` lists the notes most like it, each with `linked` (whether the two already link to each other). Show the unlinked ones first: they are the connections the vault is missing.

This skill does not write to the vault. If the answer reveals that a note is stale or wrong, say so and offer to fix it. When the answer pulled three or more notes together into something none of them says on its own, end with a one-line offer to keep it as a `kind: concept` note through `/synapsidian:save` (the user decides; an answer worth asking twice is worth keeping).
