---
name: Synapsidian docs
description: Documentation site for the Synapsidian Claude Code plugins, built on Astro Starlight.
colors:
  clay: "#d97757"
  clay-deep: "#b4532f"
  clay-text-dark: "#e8a68a"
  clay-text-light: "#9a4526"
  clay-low-dark: "#3a1d12"
  clay-low-light: "#fbe8df"
  clay-high-dark: "#f3cbb9"
  clay-high-light: "#5c2614"
  mermaid-wash: "#fbf0ea"
  ink: "#0a0a0a"
  ink-raised: "#171717"
  ink-hairline: "#262626"
  ink-text: "#fafafa"
  ink-text-muted: "#d4d4d4"
  grey-quiet: "#a3a3a3"
  grey-mid: "#737373"
  paper: "#ffffff"
  paper-sidebar: "#fafafa"
  paper-raised: "#f0f0f0"
  paper-hairline: "#e5e5e5"
  paper-text-muted: "#404040"
  note-blue: "#3b82f6"
  note-blue-light: "#2563eb"
  tip-emerald: "#10b981"
  tip-emerald-light: "#059669"
  caution-amber: "#f59e0b"
  caution-amber-light: "#d97706"
  danger-red: "#ef4444"
  danger-red-light: "#dc2626"
typography:
  display:
    fontFamily: "Poppins, Inter Variable, system-ui, sans-serif"
    fontSize: "clamp(2.4rem, 1.4rem + 3.6vw, 3.75rem)"
    fontWeight: 700
    lineHeight: 1.08
    letterSpacing: "-0.03em"
  headline:
    fontFamily: "Poppins, Inter Variable, system-ui, sans-serif"
    fontSize: "clamp(1.5rem, 1.2rem + 1.2vw, 2rem)"
    fontWeight: 600
    letterSpacing: "-0.02em"
  title:
    fontFamily: "Poppins, Inter Variable, system-ui, sans-serif"
    fontSize: "1.05rem"
    fontWeight: 600
    lineHeight: 1.3
  body:
    fontFamily: "Inter Variable, system-ui, sans-serif"
    fontSize: "1rem"
    fontWeight: 400
    lineHeight: 1.7
  label:
    fontFamily: "Inter Variable, system-ui, sans-serif"
    fontSize: "0.8125rem"
    fontWeight: 600
    letterSpacing: "0.04em"
  mono:
    fontFamily: "JetBrains Mono Variable, ui-monospace, monospace"
    fontSize: "0.86rem"
    fontWeight: 400
    lineHeight: 1.5
    fontFeature: "liga 0"
  mono-small:
    fontFamily: "JetBrains Mono Variable, ui-monospace, monospace"
    fontSize: "0.72rem"
    fontWeight: 400
rounded:
  xs: "0.25rem"
  sm: "0.375rem"
  md: "0.5rem"
  lg: "0.625rem"
  pill: "999px"
spacing:
  xs: "0.25rem"
  sm: "0.5rem"
  md: "0.75rem"
  lg: "1rem"
  xl: "1.75rem"
  2xl: "2.5rem"
  3xl: "3.5rem"
  section: "clamp(3.5rem, 8vw, 5.5rem)"
components:
  button-primary:
    backgroundColor: "{colors.clay-deep}"
    textColor: "{colors.paper}"
    rounded: "{rounded.sm}"
  copy-button:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.ink-text-muted}"
    rounded: "{rounded.sm}"
    height: "2rem"
    padding: "0 0.7rem"
  install-box:
    backgroundColor: "{colors.ink-raised}"
    rounded: "{rounded.md}"
    padding: "0.8rem 5.25rem 0.8rem 1rem"
  link-card:
    backgroundColor: "{colors.ink-raised}"
    rounded: "{rounded.md}"
  note-card:
    backgroundColor: "{colors.ink-raised}"
    textColor: "{colors.ink-text-muted}"
    typography: "{typography.mono}"
    rounded: "{rounded.md}"
    padding: "0.75rem 0.9rem 0.8rem"
  explore-row:
    textColor: "{colors.ink-text-muted}"
    rounded: "{rounded.lg}"
    padding: "1rem 3rem 1rem 1.1rem"
  explore-row-primary:
    backgroundColor: "{colors.clay-low-dark}"
    textColor: "{colors.clay-high-dark}"
    rounded: "{rounded.lg}"
    padding: "1rem 3rem 1rem 1.1rem"
  flow-node:
    backgroundColor: "{colors.clay-low-dark}"
    textColor: "{colors.clay-high-dark}"
    rounded: "{rounded.pill}"
    size: "2.25rem"
  path-pill:
    textColor: "{colors.grey-quiet}"
    typography: "{typography.mono-small}"
    rounded: "{rounded.pill}"
    padding: "0.1rem 0.55rem"
  sidebar-current:
    backgroundColor: "{colors.clay-low-dark}"
    textColor: "{colors.clay-high-dark}"
    rounded: "{rounded.md}"
---

# Design System: Synapsidian docs

## Overview

**Creative North Star: "The Readable Log"**

The site reads like the vault it documents: plain text, hairlines, a git history you can scan. Neutral greys carry everything; Claude's clay, the stroke of the brain logo, is the one hue and marks what acts or what is current. Literal things (commands, note paths, commit shas, versions, the folders a skill writes) are set in JetBrains Mono, so the reader can tell evidence from explanation at a glance.

Two themes ship and are equal: near-black ground in dark, white in light. Density is documentation density: a 46rem content column, 1.7 body leading, hairline-bordered surfaces at 0.5rem radius, no shadows on cards. The landing page uses the Starlight splash template with its own hero, a commit trail of one day in an example vault.

**Key Characteristics:**
- One accent hue (clay) on neutral greys; status colors live only in asides and badges.
- Poppins for headings, Inter for reading, JetBrains Mono for anything literal.
- Flat surfaces separated by hairlines; depth only where a note lifts off the commit trail.
- Motion is one authored load sequence plus opt-in section reveals; reduced motion shows the end state.

## Colors

Neutral near-black and white grounds with a single warm clay accent taken from the logo.

### Primary
- **Logo Clay** (clay): the logo stroke, the dark-theme accent (borders on hover, focus outlines, the filled commit dot, the trail's brain mark), and the source of every clay tint.
- **Deep Clay** (clay-deep): `--brand`. The primary button fill in both themes and the light-theme accent; the hovered flow node. Chosen so white text on it clears 4.5:1.
- **Clay Text** (clay-text-dark / clay-text-light): accent-colored text: links in the commit trail, commands in the flow, hovered names, `[[links]]` in note cards.
- **Clay Wash** (clay-low-dark / clay-low-light) with **Clay Ink** (clay-high-dark / clay-high-light): the tinted-chip pair. Current sidebar item, flow nodes, numbered start steps, the primary explore row.
- **Mermaid Wash** (mermaid-wash): node and label fill in Mermaid diagrams (light palette, inverted with a 180deg hue rotation in dark so the clay tint survives).

### Neutral
- **Ink** (ink): dark ground, nav and sidebar; also the light-theme text color.
- **Ink Raised** (ink-raised): dark card, install box and note-card fill.
- **Ink Hairline** (ink-hairline): dark borders, rail, inline-code fill.
- **Ink Text / Ink Text Muted** (ink-text, ink-text-muted): dark headings and secondary prose.
- **Quiet Grey / Mid Grey** (grey-quiet, grey-mid): meta text, shas, timestamps, pills, hollow dots; light-theme rail and hollow dots use grey-quiet to reach about 3:1 on white.
- **Paper, Paper Sidebar, Paper Raised, Paper Hairline, Paper Text Muted**: the light-theme counterparts. Light cards are plain white with a hairline, not a grey fill.

### Status (asides and badges only)
Note blue, tip emerald (mapped into Starlight's purple slot as well as green), caution amber, danger red; each has a dark and a light value plus low/high tints in `custom.css`.

### Named Rules
**The One Clay Rule.** Clay is the only interactive hue. Links, focus, current state, primary action and the newest commit use it; nothing else gets a brand color.

**The Darker Clay Under White Rule.** White text sits on clay-deep, never on Logo Clay (about 3:1).

## Typography

**Display Font:** Poppins 500/600/700 (with Inter Variable, system-ui)
**Body Font:** Inter Variable (with system-ui)
**Label/Mono Font:** JetBrains Mono Variable (with ui-monospace)

**Character:** A geometric, friendly heading face over a neutral reading face, with a monospace that marks literal values.

### Hierarchy
- **Display** (700, clamp(2.4rem → 3.75rem), 1.08, -0.03em): landing hero H1 only, max 19ch, balanced wrap.
- **Headline** (600, clamp(1.5rem → 2rem), -0.02em): landing section H2. Content-page H2 is 600 at Starlight's 3xl step; page H1 is 700, -0.02em.
- **Title** (600, 1.05rem, 1.3): flow step names, plugin names (1.2rem for the core), explore row titles at base size.
- **Body** (400, 1rem, 1.7): Markdown content in a 46rem column; leads and notes in muted grey at sm size, 1.5-1.6 leading, max 38-40rem.
- **Label** (600, 0.8125rem, 0.04em, uppercase): list-group titles in the flow and plugin lists, followed by a hairline to the right edge.
- **Mono** (0.86rem, 1.5): commit messages; mono-small (0.72rem) for shas, times, versions and "writes" pills.

### Named Rules
**The Mono Is Evidence Rule.** Commands, paths, shas, versions and folder names are mono; prose is never mono.

**The No Ligatures Rule.** `code` and `pre` set `font-variant-ligatures: none`, so `>-` and similar stay literal.

## Layout

Starlight's three-pane docs layout with `--sl-content-width: 46rem`. The landing (splash) stacks sections with `clamp(3.5rem, 8vw, 5.5rem)` between them.

- **Hero:** one column below 64rem; from 64rem two columns, copy and a 30rem trail, gap 3.5rem. Below 64rem the copy dissolves into the grid so the trail sits after the actions and the install box follows it.
- **Split sections (Why, Start):** one column, then from 56rem a 17rem left column (heading, sticky under the nav in Why) and a fluid right column.
- **Rows:** flow and plugin lists become one row per item at 44rem (flow: node | 15rem title | note | 8.5rem writes; plugins: 13.5rem name | note | version). Explore links go 1 → 2 (40rem) → 3 (64rem) columns.
- **Narrow:** under 50rem tables scroll inside their own box; under 40rem diagrams scroll in their frame or swap to a narrow variant; under 30rem the "by Szum-Tech" pill hides.

## Elevation & Depth

Flat. Cards, link cards, tables, asides, details and the install box set `box-shadow: none` and separate with a 1px hairline and, in dark, a one-step-lighter fill. The only resting shadow is on note cards in the commit trail, a short soft drop that lifts the written notes off the log. A 4px ground-colored ring around flow nodes cuts the connector line; it reads as a gap, not depth.

### Shadow Vocabulary
- **Note lift, dark** (`box-shadow: 0 14px 28px -22px rgb(0 0 0 / 0.55)`): note cards under the open commit.
- **Note lift, light** (`box-shadow: 0 14px 28px -22px rgb(120 60 30 / 0.35)`): same, clay-tinted on white.
- **Node cut** (`box-shadow: 0 0 0 4px var(--sl-color-black)`): flow nodes over their connector.

### Named Rules
**The Hairline Not Shadow Rule.** A surface is separated by a 1px hairline; a shadow is reserved for something the page shows being written.

## Shapes

Gently rounded rectangles: 0.25rem on inline code, 0.375rem on buttons, 0.5rem on cards, tables, asides, code frames, diagrams, install box and note cards, 0.625rem on full-width link rows. Pills (999px) for badges, versions, "writes" targets and the Szum-Tech label. Circles for flow nodes, numbered steps and commit dots. The commit rail is a 2px line; flow connectors are 2px lines mixed 30% clay into grey.

## Components

### Buttons
- **Shape:** gently rounded (0.375rem), weight 500.
- **Primary:** white on clay-deep, border clay-deep. Hover brightens (`filter: brightness(1.1)`).
- **Secondary / Minimal:** Starlight's own variants on the neutral theme.
- **Copy button:** 2rem tall, ground fill, hairline border, muted xs text; hover turns border clay and text clay; after copying, border green and "Copied" for 1.8s; pressed scales to 0.97.

### Cards / Containers
- **Corner Style:** 0.5rem.
- **Background:** ink-raised in dark, white in light.
- **Shadow Strategy:** none (see Elevation).
- **Border:** hairline; link cards turn the border clay on hover.
- **Tables:** hairline outline, row dividers, header row on the raised grey, row hover at 55% of that grey.

### Chips
- **Path pill:** mono-small, grey text, hairline-shade border, pill radius; on parent hover the border goes 50% clay and text clay. Used for versions and "writes" targets.
- **Tinted chip:** clay wash with clay ink: sidebar current page (0.5rem), numbered steps and flow nodes (circles).

### Navigation
- **Site title:** brain mark at 1.75rem, "Synapsidian" in Poppins 600, -0.02em, then a "by Szum-Tech" pill (hairline, 0.7rem, the name in clay text). The pill hides under 30rem.
- **Sidebar:** Starlight default; current item gets the tinted chip.

### Explore row
Full-width link row (0.625rem radius, shade hairline) with a Poppins title, muted sm description and an arrow that slides 0.25rem right on hover. Hover and focus tint 7% clay and turn the border clay; active 12%. The primary row rests on the clay wash with a 45% clay border.

### Flow and plugin lists
Rows on a 0.625rem radius with a 6-8% clay hover tint, under an uppercase group label. Flow rows carry a numbered node on a clay-tinted connector; hovering fills the node with clay-deep and white text. The core plugin row is outlined at 28% clay on a 7% tint.

### Commit trail (signature)
A `git log` of one example day in mono, newest first: a header with the clay brain mark, a 2px grey rail, hollow grey dots, one filled clay dot on the open `save` commit. Commit lines read `synapsidian(<skill>): <message>` with sha and time in mono-small below. The open commit expands into note cards: clay path label with a grey "new"/"edited" tag, grey frontmatter line, body with clay `[[links]]` underlined at 40%. On load the rail grows from the bottom, dots pop oldest to newest at 0.16s steps, the clay dot pings once, then the notes unclip downward. Under reduced motion the finished state shows.

### Diagrams
Inline SVG diagrams in a hairline 0.5rem frame on the raised fill. Nodes are rounded rects filled 12% of their role color and stroked 60%: grey (plain), clay text (command), amber (human), green (ok), red (bad). Edges 1.75px grey, dashed for optional paths. Mermaid diagrams sit in a transparent hairline frame with the clay-tinted theme.

## Do's and Don'ts

### Do:
- **Do** use clay for every link, focus outline (2px, 2px offset), current state and primary action, and nothing else.
- **Do** put white text only on clay-deep (#b4532f).
- **Do** set commands, paths, shas, versions and written folders in JetBrains Mono with ligatures off.
- **Do** separate surfaces with 1px hairlines and give cards 0.5rem corners and no shadow.
- **Do** ease state changes over 0.15s and entrances with `cubic-bezier(0.16, 1, 0.3, 1)`.
- **Do** keep content visible without scripts: hidden reveal states apply only after the `reveal-ready` flag, and reduced motion shows the end state.
- **Do** define a light-theme override for every grey that must reach 3:1 on white (rail and hollow dots use #a3a3a3).

### Don't:
- **Don't** bring back a blue or indigo accent; blue is reserved for note asides.
- **Don't** put white text on Logo Clay (#d97757).
- **Don't** add drop shadows to cards, tables or link rows.
- **Don't** use the uppercase label style as a kicker above a heading; it only names a list group.
- **Don't** fill light-theme cards with grey; they are white with a hairline.
