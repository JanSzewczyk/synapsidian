// A minimal Templater for the tests: runs a generated template the way Templater does
// (`<% %>` output, `<%* %>` JavaScript, `-%>` / `<%-` trimming one newline) against stub
// `tp` and `app` objects. Reads {template, title, answers, choices, notes} as JSON on stdin,
// prints {content, path}: the note text and the path `tp.file.move` was given.
import { readFileSync } from "node:fs";

const input = JSON.parse(readFileSync(0, "utf8"));
const TAG = /<%([-_*]?)([\s\S]*?)([-_]?)%>/g;

function compile(template) {
  const parts = [];
  let last = 0;
  for (const match of template.matchAll(TAG)) {
    parts.push({ text: template.slice(last, match.index) });
    parts.push({ open: match[1], code: match[2], close: match[3] });
    last = match.index + match[0].length;
  }
  parts.push({ text: template.slice(last) });
  for (let i = 0; i < parts.length; i++) {
    const p = parts[i];
    if (p.code === undefined) continue;
    if (p.open === "-" && parts[i - 1]) parts[i - 1].text = parts[i - 1].text.replace(/\n$/, "");
    if (p.close === "-" && parts[i + 1]) parts[i + 1].text = parts[i + 1].text.replace(/^\n/, "");
  }
  return parts
    .map((p) =>
      p.code === undefined
        ? `tR += ${JSON.stringify(p.text)};`
        : p.open === "*"
          ? p.code
          : `tR += String(${p.code});`,
    )
    .join("\n");
}

let moved = null;
const answers = input.answers ?? {};
const choices = input.choices ?? {};
const tp = {
  date: { now: (format) => (format === "HHmm" ? "0930" : "2026-10-28") },
  file: {
    title: input.title ?? "Untitled",
    cursor: () => "",
    move: async (path) => {
      moved = path;
      return path;
    },
  },
  system: {
    prompt: async (label, value) => answers[label] ?? value ?? "",
    suggester: async (_texts, items, _throw, placeholder) => {
      if (!(placeholder in choices)) return items[0];
      if (!items.includes(choices[placeholder])) throw new Error(`${choices[placeholder]} is not offered for ${placeholder}`);
      return choices[placeholder];
    },
  },
};
const notes = input.notes ?? [];
const app = {
  vault: {
    getMarkdownFiles: () => notes.map((n) => ({ path: n.path, basename: n.path.split("/").pop().replace(/\.md$/, "") })),
  },
  metadataCache: { getFileCache: (f) => ({ frontmatter: notes.find((n) => n.path === f.path)?.frontmatter }) },
};

const AsyncFunction = Object.getPrototypeOf(async () => {}).constructor;
const run = new AsyncFunction("tp", "app", `let tR = "";\n${compile(input.template)}\nreturn tR;`);
try {
  const content = await run(tp, app);
  console.log(JSON.stringify({ content, path: moved }));
} catch (error) {
  console.log(JSON.stringify({ error: String(error?.message ?? error) }));
}
