# Filing commitments from email and Slack (D64)

The work brief turns things the user was asked to do into tasks. It may **only create** tasks: never edit, close, re-date or re-prioritise a task the user has, and never touch a task it did not create in this run.

## What counts

- An email thread or Slack message (DM or a mention) addressed to the user that asks them to do something, and that the user has **not** answered or acknowledged (no reply in the thread, no emoji reaction on Slack). Open the thread once to check before using it.
- Not: asks to review a pull request (personal or team-wide; the brief lists PRs, D96), newsletters, notifications, FYIs, things already done, asks to someone else.
- Money, health and credentials are never filed.

## Dedup, in this order

1. Same link: `synapsidian query notes --type task --where source_link=<thread url> --all`.
2. Same obligation among open tasks: `synapsidian query notes --type task --where status!=done --where status!=dropped` and compare by meaning.
3. Same obligation closed in the last 7 days: `--where status=done --where "done_on>=<today-7>"`.

Any match → don't file.

## Creating

At most **5** new tasks per run.

```bash
synapsidian note new --type task --title "<the obligation in the user's own words, imperative>" \
  --field summary="<who asked for what, one sentence>" --field source=<email|slack> \
  --field source_link="<thread url>" [--field due=<YYYY-MM-DD only if a date was stated>]
```

- Title in plain words, never the email subject or pasted message text.
- `due` only when the message states a date (resolve "Friday" against today in the user's timezone); an empty `due` is meaningful.
- `priority` stays at the default unless urgency was stated.
- The task body gets one line under `## Context`: who asked, where, when.

## Pull requests are never tasks (D96)

No run creates a task, a checklist line or any other note for a pull request: not for a review waiting on the user, changes requested, failing checks or a conflict. The brief lists them, and that is all. A task note left over from an older version (e.g. "PR actions") is the user's: don't append to it, tick it or link it.
