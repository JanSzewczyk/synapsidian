# The setup report

How `/synapsidian:setup` and every add-on's setup end (D154): one short report in the user's language, in three groups, so the user sees at a glance what is in place and what is still theirs to do. Build it from the check you ran last and what this run did; never from memory.

```
✅ Ready
- <what was already in place and still is, one line each>

➕ Added in this run
- <what this run installed, created, moved or configured, one line each, with commits; the About sections and fields filled>

❗ Still needed
- <what is missing, why it is needed (a few words), and how to add it>
```

- **Ready** groups what needs nothing: say "Obsidian 1.15, vault, git, 5 of 5 plugins" rather than one line per green item when nothing in it is news.
- **Added in this run** names each change: an extension version, the Obsidian plugins installed, settings written, notes moved, sections added, the commits. Nothing changed: "nothing, the vault was already set up".
- **Still needed** lists everything the check still shows missing, each with its fix, in the order to do it:
  - a required Obsidian plugin not installed or not enabled: its name, what needs it (`required_by`) and how to add it (Settings → Community plugins → Browse → <name> → Install → Enable, or the CLI line when `obsidian.cli_on_path` is set); with Restricted mode on, turning it off comes first;
  - a required plugin installed but with `settings_unset`: run the setup again once Obsidian has loaded it;
  - an add-on whose extension isn't installed in the vault, or is older than the add-on: its setup skill (`/synapsidian-projects:setup`, `/synapsidian-work:setup`);
  - anything else the check reports as not ready (the vault not registered in Obsidian, no Obsidian CLI where a step needed it).
  Recommended plugins never go here: mention them once under the report as optional. Empty: "nothing, everything synapsidian needs is in place".
- An item the run filed as a task ("Install the Obsidian plugins synapsidian needs") stays under Still needed, with the task's `[[link]]`.
- The setup doesn't have to install anything itself: when a plugin wasn't installed (no CLI, Restricted mode on, the user said not now), saying so here, with the steps, is enough.
