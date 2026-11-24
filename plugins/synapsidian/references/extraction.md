# What to extract from a conversation

Used by `/synapsidian:save`, the evening run and `meeting import` to decide what deserves a place in the vault. When in doubt, leave it out: a vault full of trivia is worse than one missing a detail.

## Worth keeping

| Kind | Keep it when | Goes to |
|---|---|---|
| **Decision** | A choice was made between options, with a reason, that someone may later ask "why did we do it this way?" about. | New `decision` note for anything architectural, cross-team or costly to reverse (with its `project` when the vault has projects, see conventions); otherwise one dated line under `## Key decisions` in the project note, or in the note the decision is about. |
| **Task** | Someone (usually the user) committed to doing something, or the user said "I need to / remind me to". | New `task` note, with the `source` and `source_link` the calling skill names (`/synapsidian:save`: `source: save`, `source_link` to today's daily note). Skip tasks that were finished within the conversation itself. |
| **Person fact** | Something durable about a person: role, team, what they own, what they care about, how the user and they help each other, an open topic to raise with them. | Their `person` note (`## Context`, `## What they care about`, `## How we help each other`, or `## Open topics` for things to raise). The user talked with them → `last_contact` to that date, when later than the one set. The user means to get back to them by a date ("ping Alex next week") → `follow_up` to that date. Create the person note only if they will plausibly come up again. |
| **Knowledge** | How something works (domain rules, system behaviour, an explanation the user will need again). | Existing `note` in `Notes/` on that concept, or a new one (`kind: concept` when it explains one concept). |
| **Goal progress** | A step towards one of the user's goals, or a change to it (target moved, paused, achieved). | A dated line under the goal's `## Progress log`; `progress`, `target` or `status` with `synapsidian note set` when they changed. A new goal only when the user states one. |
| **How-to** | A sequence of steps that worked and will be repeated (setup, deploy, debugging recipe). | `howto` in `Howtos/`, with the exact commands. |
| **Idea** | An idea the user wants to come back to, not acted on yet. | `idea` in `Ideas/`. |
| **Project progress** | A milestone, a blocker, a change of direction on a project. | `## Log` of the project note, dated; without projects in the vault, the `## Log` of the task it moved. |

## Not worth keeping

- Debugging back-and-forth, dead ends that taught nothing, tool chatter.
- Anything already in the code, the commit history or the ticket, unless the *why* is missing there.
- Generic knowledge anyone can look up, unless the user's specific conclusion about it matters.
- Secrets: tokens, passwords, keys, personal data beyond name / role / work email. Never write these.

## Devlog line (`/synapsidian:save`)

The evening run writes its devlog by its own rules. Each save adds one bullet to the `devlog` block of today's daily note: what got done, in plain words, with links ("Fixed rounding in [[Report export]] (ABC-123)"). If the block already has bullets, append; merge bullets about the same piece of work, but there is no limit on how many the day gets.
