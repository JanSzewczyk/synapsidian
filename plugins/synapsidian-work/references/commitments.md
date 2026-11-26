# Filing commitments from email and Slack (D64, D162)

The rules for filing asks as tasks are the core's: run `synapsidian ref sources` and follow its **Filing asks as tasks** section (create only, what counts, never money, health or credentials, the three-step dedup, the `note new` call, at most 5 tasks **per source** per run). If it reports no reference named `sources`, synapsidian is older than this add-on needs: file nothing and say in one line to update synapsidian.

What this add-on adds:

- **Sources:** `source=email` with the thread's link, `source=slack` with the message's permalink. Email and Slack each have their own cap of 5.
- **Slack counts as answered** when the user replied in the thread or reacted with an emoji.
- **Email on `core-mail`:** the core's `mail` source read mail this run; file nothing from email here.

## Pull requests are never tasks (D96)

Asks to review a pull request, personal or team-wide, are not asks to file. No run creates a task, a checklist line or any other note for a pull request: not for a review waiting on the user, changes requested, failing checks or a conflict. The brief lists them, and that is all. A task note left over from an older version (e.g. "PR actions") is the user's: don't append to it, tick it or link it.
