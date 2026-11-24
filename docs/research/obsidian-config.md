# Obsidian facts for setup (verified 2026-10-13, Obsidian 1.14.4)

Sources: obsidian.md/help, the changelog, and the code bundled in the installed 1.14.4 app (marked *bundle*: internal, could change).

## Install and version
- Stable 1.14.4 (2026-10-05). `brew install --cask obsidian` or the DMG from obsidian.md/download.
- `Info.plist` `CFBundleShortVersionString` is the **installer** version. The app version is the highest `~/Library/Application Support/obsidian/obsidian-<x.y.z>.asar`, else the bundled one.

## `.obsidian/` config (safe to write before first open; Obsidian merges and re-saves)
- `core-plugins.json`: object `{ "<id>": true|false }`. Default-on ids include `daily-notes`, `templates`, `bases`, `properties`, `backlink`, `outgoing-link`, `file-recovery`, `canvas`.
- `app.json`: `newFileLocation` (root|current|folder), `newFileFolderPath`, `attachmentFolderPath`, `newLinkFormat` (shortest|relative|absolute), `useMarkdownLinks`, `alwaysUpdateLinks`, `showUnsupportedFiles`, `userIgnoreFilters`, `promptDelete`, `trashOption` (system|local|none). Appearance keys belong in `appearance.json`.
- `daily-notes.json`: `folder`, `format` (Moment), `template`, `autorun`.
- `templates.json`: `folder`, `dateFormat`, `timeFormat`.
- `types.json` (*bundle*, undocumented): `{"types": {"due": "date", ...}}`; types `text`, `multitext`, `number`, `checkbox`, `date`, `datetime`. Documented alternative: CLI `property:set ... type=`.
- `community-plugins.json` only enables; files must exist under `.obsidian/plugins/<id>/`. Restricted mode lives in app storage, not a file. synapsidian requires Git and Excalidraw (D91) and Templater (D110); see `plugins/synapsidian/references/obsidian-plugins.md`.

## Registering a vault
- `obsidian://open?path=` and `open -a Obsidian <dir>` do **not** register an unknown folder.
- Only "Open folder as vault" in the app, or adding an entry to `~/Library/Application Support/obsidian/obsidian.json` (`{"vaults": {"<16 hex>": {"path": "...", "ts": <ms>, "open": true}}}`) **while Obsidian is not running** (it rewrites the file from memory). Undocumented; back up first.

## Bases
- Views: `table`, `cards`, `list`, **`kanban` (core since 1.14)**, `map` (needs Maps plugin).
- View keys: `type`, `name`, `filters`, `order`, `limit`, `summaries`, `groupBy {property, direction}`, `groupOrder`; *bundle*: `sort: [{property, direction}]`, `columnSize`.
- Functions: `today()`, `now()`, `date()`, `file.inFolder()`, `file.hasTag()`, `file.hasLink()`, `list.contains()`, `if()`, `link()`. Date math: `today() + "7d"`.

## CLI (stable, Obsidian ≥ 1.12.7)
- Enable in Settings → General → Advanced → CLI; "Register" symlinks `/usr/local/bin/obsidian` → `/Applications/Obsidian.app/Contents/MacOS/obsidian-cli` (admin password).
- App must be running (first command launches it). `vault=<name>` first selects the vault.
- `open path=`, `search query=`, `rename`, `move` (update links when `alwaysUpdateLinks` is on), `daily`, `property:read|set|remove`, `create`, `base:query`, `plugin:install`.

## kepano/obsidian-skills
- Claude Code marketplace `obsidian-skills`, plugin `obsidian`: skills `obsidian-markdown`, `obsidian-bases`, `json-canvas`, `obsidian-cli`, `defuddle`, `knap`. Optional companion; not a dependency of synapsidian.
