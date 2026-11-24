# synapsidian-work: meeting kinds (added to synapsidian's meetings reference)

Only when `synapsidian note where` lists `synapsidian-work` under `extensions`: these kinds come from its extension, and the vault refuses them without it. Otherwise use synapsidian's own kinds and mention `/synapsidian-work:setup` once in the report.

Check these kinds before synapsidian's own (`external`, `review`, `team`):

- `1-1`: exactly two attendees, the user and one other person.
- `standup`: the title says stand-up or daily.
- `retro`: the title says retro or retrospective. synapsidian's `review` also matches "retro", so this check must come first.

A `1-1` note gets the 1:1 template (`## Talking points`, `## Notes`, `## Action items`):

- **Talking points:** from the person note's `## Open topics`, at most 4, each as a `### heading` with its body moved along. Say how many more wait there. Remove a topic from Open topics once you place it. This is the skeleton: `/synapsidian-work:one-to-one` tops it up to 2-4 topics from the previous 1:1's unfinished business and from decisions that never landed.
- **Action items:** copy every **unticked** item from the previous 1:1 with that person as `- [ ] <item> (from YYYY-MM-DD)`. Never edit the previous note.
- To prepare a topic in depth, the user has `/synapsidian-work:one-to-one` and `/synapsidian-work:one-to-one-triage`.

A `standup` note gets `## Agenda`, `## Blockers`, `## Notes` and `## Action items`, and stays empty below its agenda: the stand-up text goes in the daily note (`/synapsidian-work:standup`). Blockers is for the user to note one someone raised.

A `retro` note gets `## Agenda`, `## Went well`, `## Didn't go well`, `## Ideas`, `## Notes`, `## Decisions` and `## Action items`. Fill only the Agenda, as for any meeting; the three retro sections are the user's, from the board or the discussion, never guessed from the event.
