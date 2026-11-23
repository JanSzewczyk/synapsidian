# think: topic

Everything the vault knows about one topic, in one place: what holds, what conflicts, what is stale, what is missing.

1. **Gather.** `synapsidian find` the topic in at least three phrasings, with `--all` once (sources and archive included), and Grep for its key terms and `[[links]]`. Read every relevant note; follow links one hop. Keep a list of the notes read.
2. **Synthesis**: the current understanding in a few paragraphs, each claim cited `[[note]]`. Newer and more authoritative notes win; say so where it matters.
3. **Contradictions**: pairs of notes (or a note and a source) that disagree, quoted briefly, with which is more likely right and why.
4. **Stale**: facts stamped `(as of ...)` older than ~3 months, statuses that git or newer notes contradict, tasks or projects that look abandoned.
5. **Gaps**: questions the vault can't answer that the topic obviously raises. Suggest `/synapsidian:research` for the ones worth it.
6. Write a `thinking` note with `kind=topic`, `about` = the main notes.
7. **Fixes only with `fix`** (D19, D80). Without it, list the proposed corrections in the note and in chat and stop. With `fix`, apply them per `ingest.md` step 4: correct in place with a dated `## History` line, or mark an unresolved contradiction with a callout; never delete. List every note changed.
