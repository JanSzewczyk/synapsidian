"""Writes tests/fixtures/vault: ~30 synthetic notes for the search benchmark (D20; formerly §10.7 of the spec, removed on 2026-11-25).

Run once; the generated files are committed. Notes are written first, the questions in
search_questions.yaml separately, and test_find.py checks the questions don't leak titles.
"""

from pathlib import Path

import yaml

ROOT = Path(__file__).parent / "vault"

NOTES = {
    "About.md": (
        "about",
        {"role": "Senior frontend engineer", "team": "Platform", "timezone": "Europe/Warsaw"},
        "## Who I am\nFrontend engineer working on the pay equity analytics product.\n",
    ),
    "Projects/Pay equity export.md": (
        "project",
        {
            "status": "active",
            "summary": "Let customers download pay gap reports as spreadsheets and slide decks",
            "jira": "PA",
        },
        "## Goal\nCustomers want to take regression results into board meetings without screenshots.\n\n## Key decisions\n- 2026-09-30: ship XLSX before PPTX ([[2026-09-30 Spreadsheet format before slides]])\n",
    ),
    "Projects/Design system migration.md": (
        "project",
        {
            "status": "active",
            "summary": "Move every view from the legacy component kit to the new token-based design system",
        },
        "## Goal\nOne source of colours, spacing and typography; remove the old Sass mixins.\n",
    ),
    "Projects/Onboarding revamp.md": (
        "project",
        {"status": "paused", "summary": "Shorter first-week setup for new customers, paused until Q1"},
        "## Status\nPaused: the team moved to export work.\n",
    ),
    "Decisions/2026-09-30 Spreadsheet format before slides.md": (
        "decision",
        {
            "status": "accepted",
            "summary": "Ship the XLSX download first and the PowerPoint deck later because finance teams asked for raw numbers",
            "project": "[[Pay equity export]]",
        },
        "## Context\nTwo formats requested. Finance users re-run their own pivots.\n\n## Decision\nXLSX first; PPTX after feedback.\n",
    ),
    "Decisions/2026-08-12 Server state in query cache.md": (
        "decision",
        {
            "status": "accepted",
            "summary": "Keep API data in the query library cache instead of Pinia stores to avoid stale duplicates",
        },
        "## Context\nTwo sources of truth drifted after mutations.\n\n## Decision\nPinia only for UI state.\n",
    ),
    "Decisions/2026-07-01 Monorepo package boundaries.md": (
        "decision",
        {
            "status": "superseded",
            "summary": "Shared packages may not import from apps; later replaced by lint-enforced layers",
        },
        "## Decision\nApps depend on packages, never the reverse.\n",
    ),
    "People/Anna Nowak.md": (
        "person",
        {
            "role": "Product manager",
            "team": "Platform",
            "relationship": "peer",
            "summary": "PM who owns the reporting roadmap and prioritises customer export requests",
        },
        "## Context\nOwns reporting and exports.\n\n## Open topics\n- Ask about the PPTX template from marketing.\n",
    ),
    "People/Mikael Berg.md": (
        "person",
        {
            "role": "Engineering manager",
            "team": "Platform",
            "relationship": "manager",
            "summary": "My manager; runs the weekly one-to-one on Tuesdays",
        },
        "## Context\nCares about predictable delivery and test coverage.\n",
    ),
    "People/Tomasz Wiśniewski.md": (
        "person",
        {
            "role": "Backend engineer",
            "relationship": "peer",
            "summary": "Backend engineer behind the Django statistics service and its regression endpoints",
        },
        "## Context\nWrote the regression API. Prefers async review over calls.\n",
    ),
    "Notes/Adjusted pay gap.md": (
        "note",
        {
            "area": "domain",
            "summary": "The gap left after controlling for job level, tenure and location with a regression model",
        },
        "## Overview\nUnadjusted gap compares raw medians. The adjusted figure comes from an OLS regression with controls; what remains is unexplained by those factors.\n",
    ),
    "Notes/EU pay transparency directive.md": (
        "note",
        {
            "area": "domain",
            "summary": "EU law requiring employers to report gender pay differences and justify gaps above five percent",
        },
        "## Overview\nApplies from June 2026 for large employers. Joint pay assessment needed when a category gap exceeds 5% and isn't justified.\n",
    ),
    "Notes/Rounding in statistics service.md": (
        "note",
        {"area": "tech", "summary": "Why percentages are rounded only at display time and never inside calculations"},
        "## Details\nEarly rounding produced totals of 99.9%. Rounding moved to the formatting layer.\n",
    ),
    "Notes/Feature flags.md": (
        "note",
        {"area": "process", "summary": "How unfinished features are hidden from customers until release"},
        "## Overview\nFlags live in the tenant settings service; default off; removed two sprints after launch.\n",
    ),
    "Notes/Vue reactivity pitfalls.md": (
        "note",
        {"area": "tech", "summary": "Mistakes that silently break reactivity in Vue 3, such as destructuring props"},
        "## Details\nDestructuring a reactive object loses tracking; use toRefs. Watching a getter vs a ref.\n",
    ),
    "Howtos/Run the app against staging.md": (
        "howto",
        {"summary": "Point the local frontend at the staging API with real tenant data"},
        "## Steps\n1. Copy `.env.staging.example` to `.env.local`.\n2. `pnpm dev --mode staging`.\n",
    ),
    "Howtos/Regenerate API types.md": (
        "howto",
        {"summary": "Rebuild the TypeScript client after the backend OpenAPI schema changes"},
        "## Steps\n1. `pnpm openapi:pull`\n2. `pnpm openapi:generate`\n3. Fix type errors.\n",
    ),
    "Howtos/Release hotfix.md": (
        "howto",
        {"summary": "Ship an urgent production fix outside the normal sprint train"},
        "## Steps\nBranch from the release tag, cherry-pick, get two approvals, deploy via the hotfix pipeline.\n",
    ),
    "Ideas/2026-10-01 Explain the regression in plain words.md": (
        "idea",
        {
            "status": "new",
            "summary": "Generate a short narrative under each chart so HR readers understand coefficients",
        },
        "## The idea\nAn LLM-written paragraph under each regression chart.\n",
    ),
    "Ideas/2026-09-15 Keyboard shortcuts for filters.md": (
        "idea",
        {"status": "exploring", "summary": "Power users could switch report filters without the mouse"},
        "## The idea\nCommand palette for filters.\n",
    ),
    "Tasks/T1 Review export TDD.md": (
        "task",
        {
            "id": "T1",
            "status": "todo",
            "priority": "high",
            "due": "2026-10-15",
            "project": "[[Pay equity export]]",
            "summary": "Read and comment on the technical design for the spreadsheet download",
        },
        "## Context\nTomasz wrote it; comments due before Thursday.\n",
    ),
    "Tasks/T2 Migrate filter panel.md": (
        "task",
        {
            "id": "T2",
            "status": "doing",
            "priority": "medium",
            "project": "[[Design system migration]]",
            "summary": "Rebuild the report filter sidebar with the new design tokens",
        },
        "## Context\nBiggest remaining legacy component.\n",
    ),
    "Tasks/T3 Ask marketing for deck template.md": (
        "task",
        {
            "id": "T3",
            "status": "waiting",
            "priority": "low",
            "summary": "Get the branded slide template before starting the PowerPoint export",
        },
        "",
    ),
    "Tasks/T4 Fix percent totals.md": (
        "task",
        {
            "id": "T4",
            "status": "done",
            "priority": "high",
            "summary": "Category shares added up to 99.9 because of early rounding",
            "done_on": "2026-10-02",
        },
        "",
    ),
    "Meetings/2026-10-07 1-1 Mikael Berg.md": (
        "meeting",
        {
            "date": "2026-10-07",
            "kind": "1-1",
            "attendees": ["[[Mikael Berg]]"],
            "summary": "Talked about promotion criteria and taking ownership of the export epic",
        },
        "## Notes\nMikael wants me to lead the export epic end to end. Promotion case needs cross-team impact.\n",
    ),
    "Meetings/2026-10-09 review Export demo.md": (
        "meeting",
        {
            "date": "2026-10-09",
            "kind": "review",
            "attendees": ["[[Anna Nowak]]", "[[Tomasz Wiśniewski]]"],
            "summary": "Demo of the first spreadsheet download to product; feedback on column order",
        },
        "## Notes\nAnna wants totals in the first row.\n",
    ),
    "Notes/Testing strategy.md": (
        "note",
        {
            "area": "process",
            "summary": "Which behaviours get unit tests, which get Storybook interaction tests and which get end-to-end coverage",
        },
        "## Overview\nUnit for logic, Storybook play functions for components, Playwright for critical journeys only.\n",
    ),
    "Notes/Tenant isolation.md": (
        "note",
        {
            "area": "tech",
            "summary": "Every API query is scoped by organisation so one customer never sees another's salaries",
        },
        "## Details\nMiddleware adds the organisation filter; tests assert cross-tenant requests return 404.\n",
    ),
    "Howtos/Debug slow report.md": (
        "howto",
        {"summary": "Find out why a report page takes many seconds to render"},
        "## Steps\nRecord a performance profile, check for re-renders of the table, then check API timings.\n",
    ),
    "Notes/Bonus calculation.md": (
        "note",
        {
            "area": "domain",
            "summary": "Variable pay is computed from target percentage times performance multiplier, capped at 150 percent",
        },
        "## Details\nMultiplier ranges 0 to 1.5.\n",
    ),
}

for rel, (type_, fields, body) in NOTES.items():
    meta = {"type": type_, "created": "2026-10-01", **fields}
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "---\n" + yaml.safe_dump(meta, sort_keys=False, allow_unicode=True) + "---\n" + body, encoding="utf-8"
    )
print(len(NOTES), "notes")
