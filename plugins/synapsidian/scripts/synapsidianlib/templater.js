// synapsidian: the runtime every generated Templater template starts with (D110).
// `spec` comes before it: the type, its file name and folder rules, and one entry per field.
// It asks for what the schema can't fill, numbers ids, then moves the new note to where
// `synapsidian note new` would have put it. Keep the naming rules equal to synapsidianlib/schema.py.
const today = tp.date.now("YYYY-MM-DD");
const clean = (text) =>
  String(text ?? "")
    .normalize("NFC")
    .replace(/[\\/:*?"<>|#^[\]]/g, " ")
    .replace(/\s+/g, " ")
    .replace(/^[ .]+|[ .]+$/g, "");
const target = (link) => {
  const match = /^\[\[([^\]|#]+)/.exec(String(link ?? "").trim());
  return clean((match ? match[1] : String(link ?? "")).split("/").pop());
};
const notesOf = (type, archived) =>
  app.vault
    .getMarkdownFiles()
    .filter((f) => !f.path.startsWith("Templates/") && (archived || !f.path.startsWith("Archive/")))
    .map((f) => ({ name: f.basename, fm: app.metadataCache.getFileCache(f)?.frontmatter ?? {} }))
    .filter((n) => n.fm.type === type);
const ask = async (label, value = "") => {
  const answer = String((await tp.system.prompt(label, value, true)) ?? "").trim();
  if (!answer) throw new Error(`${spec.label}: ${label} is required`);
  return answer;
};
const pick = (label, options, optional) => {
  const items = optional ? ["", ...options] : options;
  return tp.system.suggester(items.map((o) => o || "(none)"), items, true, label);
};
const yaml = (value, kind) => {
  if (value === "" || value === null || value === undefined) return "";
  if (kind === "date" || kind === "number") return String(value);
  const plain = /^[A-Za-z][\w.-]*$/.test(value) && !/^(true|false|yes|no|null|on|off|y|n)$/i.test(value);
  return kind !== "link" && plain ? value : JSON.stringify(value);
};

const title = await ask("Title", /^Untitled( \d+)?$/.test(tp.file.title) ? "" : tp.file.title);
const raw = { ...spec.literals };
const v = {};
for (const [name, value] of Object.entries(spec.literals)) {
  v[name] = yaml(value, typeof value === "number" ? "number" : "text");
}
for (const f of spec.fields) {
  let value = "";
  switch (f.how) {
    case "today":
      value = today;
      break;
    case "date":
      value = await ask(`${f.name} (YYYY-MM-DD)`, today);
      if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) throw new Error(`${spec.label}: ${f.name} must be YYYY-MM-DD`);
      break;
    case "text":
      value = await ask(f.label ?? f.name);
      break;
    case "number":
      value = Number(await ask(f.name));
      if (Number.isNaN(value)) throw new Error(`${spec.label}: ${f.name} must be a number`);
      break;
    case "choice":
      value = await pick(f.name, f.options, f.optional);
      break;
    case "note":
      value = await pick(f.name, notesOf(f.type, false).map((n) => n.name).sort(), f.optional);
      break;
    case "link":
      value = await ask(f.name);
      break;
    default:
      continue; // literals and empty fields are written as they are; sequences come next
  }
  raw[f.name] = value;
  const isLink = f.how === "note" || f.how === "link";
  v[f.name] = yaml(isLink && value ? `[[${value}]]` : value, isLink ? "link" : f.kind);
}
for (const f of spec.fields.filter((f) => f.how === "sequence")) {
  if (f.per && !raw[f.per]) {
    v[f.name] = "";
    continue;
  }
  const escape = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const pattern = new RegExp(`^(?:${[f.prefix, ...f.legacy].map(escape).join("|")})([1-9][0-9]*)$`);
  let top = 0;
  for (const n of notesOf(spec.type, true)) {
    if (f.per && target(n.fm[f.per]).toLowerCase() !== clean(raw[f.per]).toLowerCase()) continue;
    const value = n.fm[f.name];
    const number = f.prefix
      ? Number(pattern.exec(String(value ?? ""))?.[1] ?? 0)
      : Number.isInteger(value)
        ? value
        : 0;
    top = Math.max(top, number);
  }
  raw[f.name] = f.prefix ? `${f.prefix}${top + 1}` : top + 1;
  v[f.name] = yaml(raw[f.name], f.kind);
}

const values = { ...raw, title: clean(title), date: raw.date || today, time: tp.date.now("HHmm") };
const name = clean(spec.filename.replace(/\{(\w+)\}/g, (_, key) => values[key] ?? ""));
const by = spec.folder_by && raw[spec.folder_by.field];
const folder = by
  ? spec.folder_by.folder.replace(`{${spec.folder_by.field}}`, clean(by))
  : spec.folder.replace("{title}", name);
await tp.file.move(folder ? `${folder}/${name}` : name);
