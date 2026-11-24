# Meeting notes from the calendar

Shared by `morning` (today's skeletons) and `meeting` (one event on demand).

**Add-ons:** if `command -v synapsidian-work` succeeds, run `synapsidian-work hook meetings` once and apply what it prints as well: it adds meeting kinds (checked before the ones below) and what a note of those kinds gets. Without it, use only this file.

## Which events get a note

- Accepted by the user (or organised by them), with **at least one other attendee**. Skip declined, tentative-unanswered, focus/OOO/blocked time, all-day events and events with only the user.
- Calendar calls always pass the user's timezone from `synapsidian note where` (`timezone`); the connector's default is not the user's zone.

## Dedup

Before creating, look the event up: `synapsidian query notes --type meeting --where event_id=<calendar event id> --all`. If a note exists, leave it alone (a re-run or catch-up must never create a second note or overwrite the user's notes).

## Kind

The first that fits, after any add-on kinds:

- `external`: any attendee outside the user's email domain.
- `review`: title says review / demo / retro / planning.
- `team` otherwise.

Each kind has its own sections on top of `## Agenda`, `## Notes`, `## Decisions` and `## Action items`: `team` adds `## Updates`, `review` adds `## Feedback`, `external` opens with `## Goal` and `## Who's who`. Leave the extra sections to the user; fill only what this reference says.

## Creating the note

Resolve or create the attendees' person notes first (see People below), so `attendees` can link them.

```bash
synapsidian note new --type meeting --title "<short title in the user's words, or the event title cleaned up>" \
  --field date=<YYYY-MM-DD> --field kind=<kind> --field event_id=<id> \
  --field attendees="<Person A>,<Person B>" --field summary="<event title> on <date>"
```

- `attendees` lists the other people by their person-note titles (see below), not the user.
- `## Agenda` gets the event description (cleaned, links kept) and the time and meeting link; never invent agenda items. If the description is empty, leave the section empty.
- Link the meeting from the person notes: add `- [[<meeting note>]]` under their `## History`.

## People

For each other attendee: `synapsidian find --type person "<name>"` and also check by email (`synapsidian query notes --type person --where email=<email>`). If no note exists, create a stub only from what the calendar states:

```bash
synapsidian note new --type person --title "<display name from the calendar>" \
  --field email=<calendar email> --field summary="Attendee of <meeting title> on <date>"
```

Leave `role`, `team` and `relationship` empty. If the calendar gives only an email and no name, don't create a person note: list the email in the meeting note's Agenda line instead. Never guess names, roles or emails.
