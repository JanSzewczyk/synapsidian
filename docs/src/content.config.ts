import { defineCollection } from "astro:content";
import { docsLoader } from "@astrojs/starlight/loaders";
import { docsSchema } from "@astrojs/starlight/schema";
import { changelogsLoader } from "starlight-changelogs/loader";
import { docsVersionsLoader } from "starlight-versions/loader";

// CHANGELOG.md headings are `## [0.34.0 synapsidian] — 2026-11-24`, one file for all four plugins.
// Each feed keeps its own plugin's entries and drops the rest. tests/test_docs_site.py checks every
// heading matches this pattern.
const HEADING = /^\[(\S+) (synapsidian(?:-work|-projects|-dock)?)\]\s*—\s*(\d{4}-\d{2}-\d{2})$/;

function entryTitle(plugin: string) {
  return ({ title }: { title: string }) => {
    const m = title.match(HEADING);
    return m && m[2] === plugin ? `${m[1]} · ${m[3]}` : undefined;
  };
}

const feed = (plugin: string, base: string, title: string) => ({
  provider: "keep-a-changelog" as const,
  base,
  title,
  changelog: "../CHANGELOG.md",
  process: entryTitle(plugin),
});

export const collections = {
  docs: defineCollection({ loader: docsLoader(), schema: docsSchema() }),
  changelogs: defineCollection({
    loader: changelogsLoader([
      feed("synapsidian", "changelog", "synapsidian changelog"),
      feed("synapsidian-work", "extensions/work/changelog", "synapsidian-work changelog"),
      feed("synapsidian-projects", "extensions/projects/changelog", "synapsidian-projects changelog"),
      feed("synapsidian-dock", "mods/dock/changelog", "synapsidian-dock changelog"),
    ]),
  }),
  versions: defineCollection({ loader: docsVersionsLoader() }),
};
