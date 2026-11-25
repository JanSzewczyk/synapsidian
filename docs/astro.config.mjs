// @ts-check
import { defineConfig } from "astro/config";
import starlight from "@astrojs/starlight";
import mermaid from "astro-mermaid";
import starlightChangelogs, { makeChangelogsSidebarLinks } from "starlight-changelogs";
import starlightLinksValidator from "starlight-links-validator";
import starlightVersions from "starlight-versions";

const repo = "https://github.com/JanSzewczyk/synapsidian";

// Archived releases, named after the core plugin's version (see the comment at `plugins` below).
/** @type {{ slug: string; label?: string }[]} */
const versions = [{ slug: "0.34", label: "v0.34" }];

export default defineConfig({
  site: "https://janszewczyk.github.io",
  base: "/synapsidian",
  integrations: [
    mermaid({
      theme: "base",
      autoTheme: false,
      mermaidConfig: {
        themeVariables: {
          fontFamily: "Inter Variable, system-ui, sans-serif",
          primaryColor: "#fbf0ea",
          primaryTextColor: "#0a0a0a",
          primaryBorderColor: "#e8a68a",
          secondaryColor: "#fbe8df",
          tertiaryColor: "#f5f5f5",
          lineColor: "#737373",
          textColor: "#737373",
          noteBkgColor: "#fbe8df",
          noteTextColor: "#0a0a0a",
          edgeLabelBackground: "#fbf0ea",
          stateBkg: "#fbf0ea",
          labelBackground: "#fbf0ea",
        },
      },
    }),
    starlight({
      title: "Synapsidian",
      description: "Claude Code plugins that keep a second brain in an Obsidian vault, with every change a git commit.",
      logo: { src: "./src/assets/logo.svg", alt: "Synapsidian" },
      favicon: "/favicon.svg",
      social: [{ icon: "github", label: "GitHub", href: repo }],
      editLink: { baseUrl: `${repo}/edit/main/docs/` },
      lastUpdated: true,
      plugins: [
        // `current` is the docs on main; each archived release is a folder src/content/docs/<slug>/,
        // named after the core plugin's version. To archive the next release, add { slug: "0.35" }
        // to `versions` and start the dev server once, then point the snapshot's changelog links back at the
        // unversioned /changelog/ pages (changelogs are not versioned). After that, edit a snapshot only to follow a changelog page that moved.
        // Pages under /changelog/, /extensions/<add-on>/changelog/ and /mods/dock/changelog/ come from the repository's
        // CHANGELOG.md (see src/content.config.ts).
        starlightChangelogs(),
        ...(versions.length ? [starlightVersions({ current: { label: "Latest" }, versions })] : []),
        starlightLinksValidator({
          errorOnLocalLinks: true,
          // The changelog pages are routes starlight-changelogs adds, not docs entries the validator sees.
          exclude: ["/synapsidian/changelog/**", "/synapsidian/extensions/*/changelog/**", "/synapsidian/mods/*/changelog/**"],
        }),
      ],
      components: { SiteTitle: "./src/components/SiteTitle.astro", Footer: "./src/components/Footer.astro", Hero: "./src/components/Hero.astro" },
      customCss: ["./src/styles/custom.css", "./src/styles/flow.css", "./src/styles/landing.css"],
      sidebar: [
        { label: "Getting started", items: ["getting-started/introduction", "getting-started/installation", "getting-started/quick-start"] },
        {
          label: "Concepts",
          items: [
            "concepts/vault-layout",
            "concepts/notes-and-schema",
            "concepts/generated-blocks",
            "concepts/git-history",
            "concepts/session-hooks",
            "concepts/daily-loop",
            "concepts/privacy",
            "concepts/extensions",
          ],
        },
        { label: "Skills", items: [{ autogenerate: { directory: "skills" } }] },
        { label: "CLI", collapsed: true, items: [{ autogenerate: { directory: "cli" } }] },
        {
          label: "Configuration",
          items: ["configuration/options", "configuration/about", "configuration/obsidian-plugins", "configuration/scheduled-runs"],
        },
        {
          label: "Extensions",
          items: [
            "extensions/overview",
            {
              label: "synapsidian-work",
              collapsed: true,
              items: [
                { autogenerate: { directory: "extensions/work" } },
                ...makeChangelogsSidebarLinks([{ type: "all", base: "extensions/work/changelog", label: "Changelog" }]),
              ],
            },
            {
              label: "synapsidian-projects",
              collapsed: true,
              items: [
                { autogenerate: { directory: "extensions/projects" } },
                ...makeChangelogsSidebarLinks([{ type: "all", base: "extensions/projects/changelog", label: "Changelog" }]),
              ],
            },
          ],
        },
        {
          label: "Claude Code mods",
          items: [
            "mods/overview",
            {
              label: "synapsidian-dock",
              collapsed: true,
              items: [
                { autogenerate: { directory: "mods/dock" } },
                ...makeChangelogsSidebarLinks([{ type: "all", base: "mods/dock/changelog", label: "Changelog" }]),
              ],
            },
          ],
        },
        {
          label: "Reference",
          items: [
            "reference/file-structure",
            "reference/schema",
            "reference/bases",
            "reference/design-decisions",
            "reference/contributing",
            "reference/troubleshooting",
          ],
        },
        ...makeChangelogsSidebarLinks([{ type: "all", base: "changelog", label: "Changelog" }]),
      ],
    }),
  ],
});
