# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Two audiences, weighted equally on the landing page:
- Claude Code users who want what their sessions produce (decisions, tasks, how-tos) kept somewhere they can read later.
- Obsidian users who already keep a vault and want it kept current without doing the filing themselves.

Both arrive from GitHub or a plugin listing, read the landing page, then install from the marketplace or read the docs.

## Product Purpose

Documentation site for Synapsidian: four Claude Code plugins (one marketplace) that run an Obsidian vault as a second brain. The core files what Claude Code sessions produce into plain Markdown notes, keeps the vault current with morning and evening runs, and commits every change it makes. Success: a visitor understands that in seconds, installs the core, and finds the page for any skill or command.

## Positioning

The vault stays plain Markdown with one schema; scripts do the mechanics and Claude does the judgement; every run ends in one git commit named after the skill, so every change can be read and undone. The core assumes no job, team or tickets; work, project and interface features are separate add-ons.

## Operating Context

Claude Code (CLI and desktop app), slash commands such as `/synapsidian:save`, `>>` captures typed into a session, an Obsidian vault on disk with Bases, daily notes, and git history. Scheduled runs: morning brief, evening devlog, Friday review.

## Capabilities and Constraints

- Astro Starlight site in `docs/`, English only, deployed to GitHub Pages under `/synapsidian`, versioned by the core plugin's version.
- Plugins: `synapsidian` (core), `synapsidian-work` and `synapsidian-projects` (extensions that add schema and skills), `synapsidian-dock` (a Claude Code mod: a band above the prompt and a task pane).
- Examples on the site use neutral placeholders (`ABC-123`, `web-app`, `Alex`), never real names or employers.

## Brand Commitments

- Logo: the brain outline drawn by the dock plugin (`SYNAPSIDIAN_MARK` in `plugins/synapsidian-dock/hooks/register.ts`), stroked in Claude's clay `#D97757`.
- Site accent: clay, matching the logo (confirmed 2026-11-25).
- By Szum-Tech.

## Evidence on Hand

Real skill names, CLI commands, note types and vault layout from the plugins. No testimonials, user counts or benchmarks exist; do not invent them. Example session content is illustrative and stays neutral.

## Product Principles

- Show the vault result, not promises: real commands and the notes they write.
- Plain and inspectable: Markdown, links, commits.
- Universal core first; add-ons are optional.
