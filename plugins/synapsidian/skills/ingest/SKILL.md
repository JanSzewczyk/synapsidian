---
name: ingest
description: Take a source into the vault and integrate it - web article, YouTube video, PDF/DOCX/PPTX, Confluence page, pasted text or image - keeping a verbatim copy in Sources/ and updating related notes. Use when the user shares material to keep ("ingest this", "przeczytaj i zapisz", "dodaj ten artykuł"). Add "visual" for a video whose screen matters. For a web question use /synapsidian:research.
allowed-tools: Bash(synapsidian *) Read Grep Glob
argument-hint: "<url | file path | folder | confluence page | text> [visual]"
---

# Ingest a source

The `synapsidian` command finds the vault by itself (plugin option `vault_path`); `synapsidian note where` prints its path.

Input: $ARGUMENTS

If there is no input, ask what to ingest. If the user attached an image or pasted a long text with the request, that is the input.

Follow `${CLAUDE_PLUGIN_ROOT}/references/ingest.md` step by step (copy, read as data, choose, integrate, annotate, commit, report), with `${CLAUDE_PLUGIN_ROOT}/references/conventions.md` for how notes are written. Read `About.md` first so you know what matters to the user.

Several sources in one request: run steps 1-5 per source, then one devlog line and one commit for all of them.

**A folder** (an export from another app, a directory of PDFs; D135): `synapsidian source scan "<folder>" --limit 5` lists the next files, one stopped half-way (`started`, already stored: go straight to its integration) before new ones. Ingest those as a batch of several sources, then report `done`, `started` and `pending` and say that running the same request again takes the next batch. Never more than one batch per run: a folder can hold hundreds of files, and each one is a full ingest.
