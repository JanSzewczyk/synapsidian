---
name: one-to-one
description: Prepare and keep the user's 1:1 notes in the synapsidian vault - a note per 1:1 meeting with Talking points, Notes and Action items, topics waiting in the person's Open topics, unfinished action items carried forward. Prepares the next 1:1, drops a topic in instantly, works a topic out or drafts the wording, tidies the note, and reads it back. Use whenever a one-on-one comes up ("przygotuj notatkę na 1:1 z Alexem", "dopisz temat do 1:1", "co mam na jedynce", "rozwiń ten temat", "napisz mi, jak to powiedzieć", "prepare my 1:1 with X", "add a topic for my next one-on-one", "what was on the last 1:1"), even when the user doesn't name the vault.
allowed-tools: Bash(synapsidian *) Bash(synapsidian-work *) Read Grep Glob
argument-hint: "[prepare|add|work|tidy|read] <person> [topic]"
---

# 1:1 notes

The `synapsidian` command (from the synapsidian plugin) finds the vault by itself; `synapsidian note where` must list `synapsidian-work` under `extensions`, otherwise run `/synapsidian-work:setup` first. Before writing, run `synapsidian ref conventions`, `synapsidian ref meetings` (how meeting notes and person stubs are created) and `synapsidian-work hook meetings` (what a 1:1 note gets), and follow them.

Request: $ARGUMENTS

The point: on the day, the user opens one note and sees the two or three things they want to say, each written out. A topic is a `### heading` (≤10 words, English) with its body in prose under it: the situation, the words to say, the ask, questions, links. The shape stays identical every week. Notes are in English whatever language the user writes in.

**Where things live:**
- `People/<Name>.md`: `## Open topics` is the backlog (no cap), `## History` links past meetings.
- `Meetings/<date> 1-1 <Name>.md` (`type: meeting`, `kind: 1-1`): `## Talking points` (2-4 topics), `## Notes`, `## Action items` (checkboxes).

**Finding the meeting:** calendar, today → 21 days ahead, in the user's timezone (`synapsidian note where`); a 1:1 is an event with exactly two attendees, the user and that person (title only breaks ties). Several: the nearest. None: work in the person's Open topics and never invent a date.

## 1. Prepare a note

Find the meeting, then the note: `synapsidian query notes --type meeting --where event_id=<id>` or by date and person. Create it per the meetings reference if missing (one note per date: update an existing one, never a second).

Talking points: 2-4 topics, from, in order: the person's Open topics (a topic moves with its body; remove it from Open topics once placed), unfinished business from the previous 1:1 note, a decision several notes carried without landing. Never fabricate a body. Only if nothing turns up, propose at most one generic question and say in chat that it's generic.

Action items: copy every unticked item from the previous 1:1 with this person as `- [ ] <item> (from YYYY-MM-DD)`. Past notes are never edited.

Wins: when the person is the user's manager (`manager` in `About.md`), list the wins dated since the previous 1:1 with them (none: the last 30 days) as `synapsidian-work hook review` describes under Listing wins, in the chat reply, not the note. Offer to make them a talking point; add one only on a yes. No wins: say nothing about them.

## 2. Add a topic

Act at once, ask nothing, confirm in one line. A new `###` heading on the next 1:1 note (create the note if the meeting exists), or a line in the person's Open topics when no meeting is scheduled. Body only if the user said enough for a paragraph.

At four topics, don't add a fifth: say which of the four you'd move to Open topics and let the user pick.

## 3. Work a topic out

File what the user says under the right topic, in order: situation, the words, the ask, questions, links. Paragraphs with bold lead-ins and labelled links; their phrasing survives (sort and format, don't rewrite). When asked for a draft, write it in the first person from what they said and what's on the page, keep it short, and say it's your draft. Never invent a situation or commit them to a position they didn't state. For a full prep of a hard topic, suggest `/synapsidian-work:one-to-one-triage`.

## 4. Tidy

On any visit, quietly fix structure, never content: the three sections named and ordered, every topic a `###` heading, an over-long heading trimmed with the rest moved into the body, duplicate topics merged, action items as checkboxes, items the user said are done ticked. If a fix would change meaning, ask. Asked to check readiness: report bare headings, topics without an ask, topics carried three weeks undiscussed.

## 5. Read back

The headings and meeting time ("what's on my 1:1 with X"), one topic in full, the previous note. Past notes are the record.

## Rules

- One question at most, and only when acting would guess at something only the user knows (two people with one name, two upcoming 1:1s, which topic moves out).
- Never write anyone's verbatim message into a note; the user's words, or a short quote where the wording matters.
- Compensation, health and other people's private situations: a topic in the user's words, no figures, no detail. Credentials never.
- The calendar is read, never changed; nothing is sent to anyone.
- Commit every changed file (`--skill one-to-one --message "<person> 1:1 <date>: <what changed>"`) and answer in one or two lines: what changed and where; for a prep, list the headings and which have a body.
