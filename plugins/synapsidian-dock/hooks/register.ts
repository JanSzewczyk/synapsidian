/**
 * The synapsidian dock (D156): a /synapsidian pane and a band above the prompt showing what the session
 * brief shows, kept current without a Claude turn, with keys that change a task in place.
 *
 * It meets the core only through the `synapsidian` command on PATH (D90): it reads `synapsidian brief --json`
 * and writes with `synapsidian note set` and `synapsidian commit`, so the vault path, the schema checks and
 * the one-commit-per-change rule stay the core's own. Nothing here writes to the vault unless the
 * user presses a key.
 */

const PANE = 'synapsidian-dock'
/** The date rolls over and other sessions change tasks. */
const REFRESH_MS = 5 * 60_000
/** Sessions reuse one another's fresh state instead of each starting uv. */
const SHARED_MS = 60_000
const WRITE_TOOLS = ['Write', 'Edit', 'MultiEdit', 'NotebookEdit']
const SYNAPSIDIAN_BASH = /\bsynapsidian\s+(note|commit)\b|\b(note|commit)\.py\b/

/** Theme keys the dock paints with, so it follows the person's Claude theme. */
const Tone = {
  ACCENT: 'claude',
  ALERT: 'error',
  OK: 'success',
  PAUSED: 'warning',
  QUIET: 'inactive',
  /**
   * Behind the open task's card and a hovered row on the desktop: a translucent neutral, since the
   * desktop paints only the named theme keys and none of them is a surface (2.1.323 drew nothing
   * for `userMessageBackground`); over the theme's own background it reads on light and dark alike.
   */
  RAISED: '#8080801f',
  /** No paint at all, for a hover that should change nothing. */
  CLEAR: '#00000000',
} as const

/** What a badge says by its colour. */
export const Badge = {
  OK: 'ok',
  ALERT: 'alert',
  PAUSED: 'paused',
  ACCENT: 'accent',
  QUIET: 'quiet',
} as const
export type Badge = (typeof Badge)[keyof typeof Badge]

/**
 * A badge's colours, drawn as an image on the desktop: a Box there rounds its fill only along a
 * border, which pads it to more than a caption's height (2.1.323). An image cannot read theme keys, so each colour is the
 * Claude theme's own for light and for dark, picked by the system's scheme; the fill is the same
 * hue, faint.
 */
const BADGE_PAINT: Record<Badge, { light: string; dark: string }> = {
  [Badge.OK]: { light: '#2e7d32', dark: '#74c473' },
  [Badge.ALERT]: { light: '#c62828', dark: '#ef7a6a' },
  [Badge.PAUSED]: { light: '#a86400', dark: '#e3a03d' },
  [Badge.ACCENT]: { light: '#c96442', dark: '#d97757' },
  [Badge.QUIET]: { light: '#5f5d57', dark: '#b4b2aa' },
}
/** A thin upright line between groups of controls, as an image, since a Box border can't draw one side alone. */
const DIVIDER = '<svg xmlns="http://www.w3.org/2000/svg" width="9" height="18"><rect x="4" y="1" width="1" height="16" fill="#808080" fill-opacity=".45"/></svg>'

/** The badge image's type, as the desktop's own: 11px medium. */
const BADGE_FONT = "500 11px -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif"
const BADGE_HEIGHT = 18

/** One badge: its words, its colour, and the state mark that leads a status badge. */
export type BadgeSpec = { label: string; tone: Badge; mark?: string }

/**
 * The band's synapsidian mark, drawn as an image on the desktop surfaces. An image cannot read theme
 * keys, so the stroke is Claude's clay, which holds on light and dark backgrounds alike.
 */
const SYNAPSIDIAN_MARK =
  '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><g fill="none" stroke="#D97757" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">' +
  '<path d="M12 5.6A2.7 2.7 0 0 0 7.4 4.9 2.7 2.7 0 0 0 4.3 8.6 2.8 2.8 0 0 0 3.6 13.4 2.7 2.7 0 0 0 6.2 17.6 2.7 2.7 0 0 0 10.4 19 2.2 2.2 0 0 0 12 18.2 2.2 2.2 0 0 0 13.6 19 2.7 2.7 0 0 0 17.8 17.6 2.7 2.7 0 0 0 20.4 13.4 2.8 2.8 0 0 0 19.7 8.6 2.7 2.7 0 0 0 16.6 4.9 2.7 2.7 0 0 0 12 5.6Z"/>' +
  '<path d="M12 5.6V18.2M7.6 8.2C8.8 8 9.6 8.9 9.4 10M5.8 11.6C7.4 11.2 8.6 12 8.6 13.4M8 16C9.2 15.6 10 16.2 10 17.1M16.4 8.2C15.2 8 14.4 8.9 14.6 10M18.2 11.6C16.6 11.2 15.4 12 15.4 13.4M16 16C14.8 15.6 14 16.2 14 17.1"/>' +
  '</g></svg>'
/** As tall as a native button, so the mark does not make the band taller. */
const SYNAPSIDIAN_MARK_PX = 26

/** The status a task can be set to; the values are the schema's own. */
export const Status = {
  TODO: 'todo',
  DOING: 'doing',
  WAITING: 'waiting',
  DONE: 'done',
  DROPPED: 'dropped',
} as const
export type Status = (typeof Status)[keyof typeof Status]

const STATUS_LABEL: Record<Status, string> = {
  [Status.TODO]: 'To do',
  [Status.DOING]: 'In progress',
  [Status.WAITING]: 'Waiting',
  [Status.DONE]: 'Done',
  [Status.DROPPED]: 'Dropped',
}

/** What a one-press status button says: the move it makes, not the state it lands in. */
const STATUS_ACTION: Record<Status, { label: string; hotkey: string }> = {
  [Status.TODO]: { label: 'Back to to-do', hotkey: 't' },
  [Status.DOING]: { label: 'Start', hotkey: 's' },
  [Status.WAITING]: { label: 'Waiting', hotkey: 'w' },
  [Status.DONE]: { label: 'Done', hotkey: 'd' },
  [Status.DROPPED]: { label: 'Drop', hotkey: 'x' },
}

/** When a task falls due: the end of a span from today, or no date at all. */
export const Due = {
  KEEP: 'keep',
  TODAY: 'today',
  WEEK: 'week',
  MONTH: 'month',
  YEAR: 'year',
  NONE: 'none',
} as const
export type Due = (typeof Due)[keyof typeof Due]

/** What Claude is asked to do with a task; each puts a draft in the prompt box. */
export const Ask = {
  ABOUT: 'about',
  DO: 'do',
} as const
export type Ask = (typeof Ask)[keyof typeof Ask]

/** A change `act` makes in the vault: a new status or a new due date. */
export type Change = { status: Status } | { due: Exclude<Due, typeof Due.KEEP> }

/** A task's state as its mark shows it: `blocked` wins over the status while a blocker is open. */
export const State = {
  TODO: 'todo',
  DOING: 'doing',
  WAITING: 'waiting',
  BLOCKED: 'blocked',
} as const
export type State = (typeof State)[keyof typeof State]

/**
 * One glyph family for every state, which the terminal draws alone and a desktop status badge
 * draws before the state's name, so colour is never alone.
 */
const STATE_MARK: Record<State, { glyph: string; color: string; label: string; badge: Badge }> = {
  [State.TODO]: { glyph: '○', color: Tone.QUIET, label: 'To do', badge: Badge.QUIET },
  [State.DOING]: { glyph: '●', color: Tone.OK, label: 'In progress', badge: Badge.OK },
  [State.WAITING]: { glyph: '◑', color: Tone.PAUSED, label: 'Waiting', badge: Badge.PAUSED },
  [State.BLOCKED]: { glyph: '⊘', color: Tone.ALERT, label: 'Blocked', badge: Badge.ALERT },
}

const PRIORITY_RANK: Record<string, number> = { high: 0, medium: 1, low: 2 }

export const Tab = {
  TODAY: 'today',
  PROJECTS: 'projects',
  WRITES: 'writes',
} as const
export type Tab = (typeof Tab)[keyof typeof Tab]

const TAB_LABEL: Record<Tab, { label: string; hotkey: string }> = {
  [Tab.TODAY]: { label: 'Today', hotkey: '1' },
  [Tab.PROJECTS]: { label: 'Projects', hotkey: '2' },
  [Tab.WRITES]: { label: 'Writes', hotkey: '3' },
}

const WEEKDAYS = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']

type Task = {
  id: string
  title: string
  rel: string
  status: string
  priority: string | null
  due: string | null
  days: number | null
  blocked_by: Array<string>
  project: string | null
  repeat: string | null
  /** The note's one-line `summary` (synapsidian 0.32.3+); absent from older synapsidians. */
  summary?: string | null
}

type Dock = {
  ok: boolean
  error?: string
  vault: string
  today: string
  daily: string | null
  meetings: Array<{ title: string; rel: string }>
  sections: Array<{ key: string; title: string; tasks: Array<Task> }>
  open: Array<Task>
  projects: Array<string>
  inbox: number
}

type Write = { rel: string; what: string; at: string }

/**
 * One fact the band shows: in the terminal `strong` at full strength and `rest` dim unless the
 * fact is an alert; on the desktop the shorter `badge`.
 */
export type BandFact = { strong: string; rest: string; isAlert: boolean; badge: BadgeSpec }

/** Whether the band shows: shown at start unless the option turns it off, ✕ hides it, /synapsidian shows it again. */
let showBand = true
/** The surface session.start named; null in claude -p and the Agent SDK. */
let startSurface: string | null = null
let dock: Dock | null = null
/** When the shown state was read from the vault, for the age next to Refresh. */
let dockAt: number | null = null
let tab: Tab = Tab.TODAY
/** The vault-relative path of the task whose details are open; null when every row is closed. */
let selected: string | null = null
/** What the pane says while a key's change runs; null when idle. */
let busy: string | null = null
let writes: Array<Write> = []
let pending: { cancel(): void } | null = null
/**
 * How to start `synapsidian`: the bare name while PATH has it, else its script found on disk. The
 * desktop app starts a mod's processes without the plugins' `bin/` folders on PATH, which the
 * Bash tool and the terminal app do get.
 */
let synapsidianArgv: Array<string> = ['synapsidian']

function isMissing(text: string): boolean {
  return /ENOENT|not found|no such file/i.test(text)
}

/** `bin/synapsidian` of each installed synapsidian plugin, newest first, from Claude Code's install record. */
export function installedSynapsidians(installedJson: string): Array<string> {
  try {
    const record = JSON.parse(installedJson)
    const entries = Object.entries(record?.plugins ?? {})
      .filter(([id]) => id.startsWith('synapsidian@'))
      .flatMap(([, installs]) => (Array.isArray(installs) ? installs : []))
      .filter((install) => typeof install?.installPath === 'string')
      .sort((a, b) => String(b.lastUpdated ?? '').localeCompare(String(a.lastUpdated ?? '')))
    return entries.map((install) => install.installPath.replace(/\/$/, '') + '/bin/synapsidian')
  } catch {
    return []
  }
}

/** Find `bin/synapsidian` without PATH: Claude Code's install record, then a `synapsidian` folder beside this plugin. */
async function findSynapsidian($): Promise<string | null> {
  const candidates: Array<string> = []
  const home = await $.env.get('HOME')
  const configDir = (await $.env.get('CLAUDE_CONFIG_DIR')) || (home ? home + '/.claude' : '')
  if (configDir) {
    try {
      candidates.push(...installedSynapsidians(String(await $.fs.read(configDir + '/plugins/installed_plugins.json'))))
    } catch {
      // No install record: only the folder beside this plugin is left to try.
    }
  }
  const root = String($.plugin.root).replace(/\/$/, '')
  candidates.push(root.slice(0, root.lastIndexOf('/')) + '/synapsidian/bin/synapsidian')
  for (const candidate of candidates) {
    if (await $.fs.exists(candidate)) return candidate
  }
  return null
}

/**
 * What to show for a run that printed no JSON: the last non-empty line of stderr, else of stdout.
 * A Python traceback ends with the exception and its message, so that line says why (D161).
 */
export function failureLine(stderr: string, stdout: string): string {
  const last = (text: string) =>
    String(text ?? '')
      .split('\n')
      .map((line) => line.trim())
      .filter(Boolean)
      .pop() ?? ''
  return (last(stderr) || last(stdout)).slice(0, 300)
}

/** Run `synapsidian <command> ...` and return its JSON answer (the last line printed). */
async function runSynapsidian($, command: string, args: Array<string>): Promise<any> {
  try {
    let r
    try {
      r = await $.process.run([...synapsidianArgv, command, ...args])
    } catch (error) {
      if (synapsidianArgv.length !== 1 || !isMissing(errorText(error))) throw error
      const found = await findSynapsidian($)
      if (found === null) throw error
      synapsidianArgv = ['/bin/sh', found]
      r = await $.process.run([...synapsidianArgv, command, ...args])
    }
    const line = r.stdout.trim().split('\n').pop() ?? ''
    try {
      const answer = JSON.parse(line)
      if (typeof answer?.ok !== 'boolean') return { ok: false, error: 'synapsidian ' + command + ' answered in another shape; update synapsidian to 0.32.0 or later' }
      return answer
    } catch {
      return { ok: false, error: failureLine(r.stderr, r.stdout) || 'no answer from synapsidian ' + command }
    }
  } catch (error) {
    const text = errorText(error)
    if (isMissing(text)) {
      return { ok: false, error: 'synapsidian was found neither on PATH nor among the installed plugins (is it installed?): ' + text }
    }
    return { ok: false, error: 'synapsidian ' + command + ' did not finish: ' + text }
  }
}

async function refresh($, force: boolean): Promise<void> {
  const now = await $.clock.now()
  if (!force) {
    const cached = await $.store.get('dock')
    if (cached && typeof cached.at === 'number' && now - cached.at < SHARED_MS && cached.state?.ok) {
      dock = cached.state
      dockAt = cached.at
      $.ui.invalidate('ui.render')
      return
    }
  }
  const state = await runSynapsidian($, 'brief', ['--json'])
  dock = state
  if (state?.ok) {
    dockAt = now
    await $.store.set('dock', { at: now, state })
  }
  $.ui.invalidate('ui.render')
}

/** Refresh once a burst of vault writes has settled. */
function refreshSoon($): void {
  pending?.cancel()
  pending = $.clock.after(1500, () => refresh($, true))
}

async function clockTime($): Promise<string> {
  return new Date(await $.clock.now()).toTimeString().slice(0, 5)
}

export function addDays(iso: string, days: number): string {
  const [y, m, d] = iso.split('-').map(Number)
  return new Date(Date.UTC(y, m - 1, d + days)).toISOString().slice(0, 10)
}

function utcDate(iso: string): Date {
  const [y, m, d] = iso.split('-').map(Number)
  return new Date(Date.UTC(y, m - 1, d))
}

/** `Tuesday, 17 November`, the pane's heading. */
export function longDate(iso: string): string {
  const date = utcDate(iso)
  return WEEKDAYS[date.getUTCDay()] + ', ' + date.getUTCDate() + ' ' + MONTHS[date.getUTCMonth()]
}

/** `17 Nov`, with the year only when it is not this year's. */
export function shortDate(iso: string, today: string): string {
  const date = utcDate(iso)
  const day = date.getUTCDate() + ' ' + MONTHS[date.getUTCMonth()].slice(0, 3)
  return iso.slice(0, 4) === today.slice(0, 4) ? day : day + ' ' + iso.slice(0, 4)
}

function dayCount(n: number): string {
  return n === 1 ? '1 day' : n + ' days'
}

/**
 * The due date as a row says it, in the words a person would: `9d late`, `today`, `tomorrow`,
 * a weekday within the week, else the date; a task with no date says `high` when it is.
 */
/** Days from today to a dated task's due date, negative when late; `brief` gives it, else the dates do. */
function daysUntil(t: Task & { due: string }, today: string): number {
  return t.days ?? Math.round((utcDate(t.due).getTime() - utcDate(today).getTime()) / 86_400_000)
}

export function dueLabel(t: Task, today: string): string {
  if (t.due === null) return t.priority === 'high' ? 'high' : ''
  const days = daysUntil(t as Task & { due: string }, today)
  if (days < 0) return -days + 'd late'
  if (days === 0) return 'today'
  if (days === 1) return 'tomorrow'
  if (days < 7) return WEEKDAYS[utcDate(t.due).getUTCDay()].slice(0, 3)
  return shortDate(t.due, today)
}

/** How old the shown state is, next to Refresh. */
export function ageLabel(at: number | null, now: number): string {
  if (at === null) return ''
  const minutes = Math.floor((now - at) / 60_000)
  if (minutes < 1) return 'just now'
  if (minutes < 60) return minutes + ' min ago'
  return Math.floor(minutes / 60) + ' h ago'
}

function shortId(task: Task): string {
  return task.id || task.title
}

/** The title without its leading id, which the row draws apart from it. */
export function bareTitle(t: Task): string {
  return t.id && t.title.startsWith(t.id + ' ') ? t.title.slice(t.id.length + 1) : t.title
}

/**
 * The last day of the span a due option names, counted from `today`: today itself, this week's
 * Sunday (ISO weeks end on Sunday), the month's or the year's last day; null for no due date.
 */
export function dueDate(due: Exclude<Due, typeof Due.KEEP>, today: string): string | null {
  const [y, m, d] = today.split('-').map(Number)
  switch (due) {
    case Due.TODAY:
      return today
    case Due.WEEK:
      return addDays(today, (7 - new Date(Date.UTC(y, m - 1, d)).getUTCDay()) % 7)
    case Due.MONTH:
      return new Date(Date.UTC(y, m, 0)).toISOString().slice(0, 10)
    case Due.YEAR:
      return y + '-12-31'
    case Due.NONE:
      return null
  }
}

const STATUS_SUBJECT: Record<Status, string> = {
  [Status.TODO]: 'move {id} back to to-do',
  [Status.DOING]: 'start {id}',
  [Status.WAITING]: 'park {id} as waiting',
  [Status.DONE]: 'close {id}',
  [Status.DROPPED]: 'drop {id}',
}

/** The fields `synapsidian note set` gets for a change, and the commit subject for it. */
export function change(what: Change, task: Task, today: string): { fields: Array<string>; subject: string } {
  const id = shortId(task)
  if ('status' in what) return { fields: ['status=' + what.status], subject: STATUS_SUBJECT[what.status].replace('{id}', id) }
  const date = dueDate(what.due, today)
  return date === null
    ? { fields: ['due='], subject: 'clear the due date of ' + id }
    : { fields: ['due=' + date], subject: 'move ' + id + ' to ' + date }
}

async function act($, task: Task, what: Change): Promise<void> {
  if (busy !== null || dock === null) return
  const { fields, subject } = change(what, task, dock.today)
  busy = subject
  $.ui.invalidate('ui.render')
  try {
    const set = await runSynapsidian($, 'note', ['set', '--file', task.rel, ...fields.flatMap((f) => ['--field', f])])
    if (!set?.ok) {
      $.ui.toast(shortId(task) + ' unchanged: ' + (set?.error ?? 'synapsidian note set failed'), { timeoutMs: 8000 })
      return
    }
    const files = [set.rel, set.from, set.next?.rel].filter(Boolean)
    const commit = await runSynapsidian($, 'commit', ['--skill', 'task', '--message', subject + ' (dock)', ...files])
    const next = set.next ? ' · next ' + set.next.id + ' due ' + set.next.due : ''
    if (commit?.ok) $.ui.toast(subject + next)
    else $.ui.toast(subject + ', not committed: ' + (commit?.error ?? 'synapsidian commit failed'), { timeoutMs: 8000 })
    writes = [{ rel: set.rel, what: subject, at: await clockTime($) }, ...writes].slice(0, 30)
    await refresh($, true)
  } finally {
    busy = null
    $.ui.invalidate('ui.render')
  }
}

export function obsidianUrl(vault: string, rel: string): string {
  const name = vault.split('/').filter(Boolean).pop() ?? ''
  return 'obsidian://open?vault=' + encodeURIComponent(name) + '&file=' + encodeURIComponent(rel.replace(/\.md$/, ''))
}

async function openInObsidian($, rel: string): Promise<void> {
  if (dock === null) return
  const url = obsidianUrl(dock.vault, rel)
  for (const opener of ['open', 'xdg-open']) {
    try {
      const r = await $.process.run([opener, url])
      if (r.exitCode === 0) return
    } catch {
      // Not on this system: try the next opener.
    }
  }
  $.ui.toast('Could not open Obsidian; the note is ' + rel)
}

/** The draft each Claude action puts in the prompt box; Enter sends it, so nothing runs unasked. */
export function claudeDraft(ask: Ask, task: Task): string {
  const ref = '[[' + task.title + ']] (' + task.rel + ')'
  return ask === Ask.DO
    ? 'Work on the task ' + ref + ': read the note, then do what it asks and log the progress in it.'
    : 'Tell me about the task ' + ref + ': what it is, where it stands and what is left.'
}

async function askClaude($, task: Task, ask: Ask): Promise<void> {
  await $.prompt.fill({ text: claudeDraft(ask, task) })
  $.ui.toast('Draft in the prompt box; Enter sends it')
}

function sectionTasks(d: Dock, key: string): Array<Task> {
  return d.sections.find((s) => s.key === key)?.tasks ?? []
}

/** What the band says, most urgent first: overdue, due today, in progress, the Inbox. */
export function bandFacts(d: Dock | null): Array<BandFact> {
  if (d === null || !d.ok) return []
  const facts: Array<BandFact> = []
  const overdue = sectionTasks(d, 'overdue')
  if (overdue.length === 1) {
    const late = -(overdue[0].days ?? 0)
    facts.push({
      strong: shortId(overdue[0]),
      rest: ' ' + dayCount(late) + ' overdue',
      isAlert: true,
      badge: { label: shortId(overdue[0]) + ' · ' + late + 'd late', tone: Badge.ALERT },
    })
  } else if (overdue.length > 1) {
    facts.push({ strong: String(overdue.length), rest: ' overdue', isAlert: true, badge: { label: overdue.length + ' overdue', tone: Badge.ALERT } })
  }
  const dueToday = sectionTasks(d, 'today')
  if (dueToday.length) {
    facts.push({ strong: String(dueToday.length), rest: ' due today', isAlert: false, badge: { label: dueToday.length + ' today', tone: Badge.PAUSED } })
  }
  const doing = d.open.length ? d.open.filter((t) => t.status === Status.DOING) : sectionTasks(d, 'doing')
  if (doing.length) {
    const strong = doing.length === 1 ? shortId(doing[0]) : String(doing.length)
    const mark = STATE_MARK[State.DOING].glyph
    facts.push({ strong, rest: ' in progress', isAlert: false, badge: { label: strong + ' in progress', tone: Badge.OK, mark } })
  }
  if (d.inbox) facts.push({ strong: String(d.inbox), rest: ' in Inbox', isAlert: false, badge: { label: 'Inbox ' + d.inbox, tone: Badge.QUIET } })
  return facts
}

async function canDraw($): Promise<boolean> {
  if (startSurface !== null) return true
  try {
    const surfaces = await $.session.surfaces()
    return Array.isArray(surfaces) && surfaces.length > 0
  } catch {
    return false
  }
}

/** Open the dock's pane; false where nothing can draw it (claude -p). */
async function openPane($): Promise<boolean> {
  if (dock === null) await refresh($, false)
  try {
    return (await $.ui.open({ id: PANE, title: 'Synapsidian', focus: true, closeOnEscape: true }))?.isPlaced === true
  } catch {
    return false
  }
}

export function taskLabel(t: Task): string {
  const bits: Array<string> = []
  if (t.due) bits.push(t.days !== null && t.days < 0 ? 'due ' + t.due + ', ' + -t.days + 'd overdue' : 'due ' + t.due)
  if (t.status === Status.DOING || t.status === Status.WAITING) bits.push(t.status)
  if (t.priority === 'high') bits.push('high')
  if (t.blocked_by.length) bits.push('blocked by ' + t.blocked_by.join(', '))
  if (t.repeat) bits.push('every ' + t.repeat)
  return t.title + (bits.length ? ' (' + bits.join(', ') + ')' : '')
}

/** The brief as text, for where nothing draws (claude -p) or the pane can't be placed. */
export function summaryText(d: Dock | null): string {
  if (d === null) return 'The synapsidian dock has no data yet; try /synapsidian refresh.'
  if (!d.ok) return 'The synapsidian dock could not read the vault: ' + (d.error ?? 'unknown error')
  const lines = ['Synapsidian, ' + d.today + ':']
  for (const s of d.sections) {
    if (!s.tasks.length) continue
    lines.push(s.title + ':')
    for (const t of s.tasks.slice(0, 8)) lines.push('- ' + taskLabel(t))
  }
  if (d.inbox) lines.push('Inbox: ' + d.inbox)
  return lines.length > 1 ? lines.join('\n') : 'Synapsidian, ' + d.today + ': nothing due, overdue or in progress.'
}

export function stateOf(t: Task): State {
  if (t.blocked_by.length) return State.BLOCKED
  if (t.status === State.DOING) return State.DOING
  if (t.status === State.WAITING) return State.WAITING
  return State.TODO
}

function statusOf(t: Task): Status {
  return Object.values(Status).includes(t.status as Status) ? (t.status as Status) : Status.TODO
}

/** Highest priority first, then the earliest due date, then the task id. */
export function byPriority(tasks: Array<Task>): Array<Task> {
  function rank(t: Task): number {
    return PRIORITY_RANK[t.priority ?? ''] ?? 3
  }
  return [...tasks].sort(
    (a, b) =>
      rank(a) - rank(b) ||
      (a.due ?? '9999').localeCompare(b.due ?? '9999') ||
      a.id.localeCompare(b.id, undefined, { numeric: true }),
  )
}

/** The two status moves a task most likely needs next, the likeliest first. */
export function nextStatuses(t: Task): [Status, Status] {
  switch (statusOf(t)) {
    case Status.DOING:
      return [Status.DONE, Status.WAITING]
    case Status.WAITING:
      return [Status.DOING, Status.DONE]
    case Status.DONE:
    case Status.DROPPED:
      return [Status.TODO, Status.DOING]
    default:
      return [Status.DOING, Status.DONE]
  }
}

/** The facts the details show under the summary, as label and value pairs. */
export function facts(t: Task, today: string): Array<[string, string]> {
  const pairs: Array<[string, string]> = [
    ['Status', t.blocked_by.length ? 'Blocked by ' + t.blocked_by.join(', ') : STATUS_LABEL[statusOf(t)]],
  ]
  if (t.priority) pairs.push(['Priority', t.priority[0].toUpperCase() + t.priority.slice(1)])
  if (t.due) {
    const late = t.days !== null && t.days < 0 ? ', ' + dayCount(-t.days) + ' late' : ''
    pairs.push(['Due', shortDate(t.due, today) + late])
  }
  if (t.project) pairs.push(['Project', t.project])
  if (t.repeat) pairs.push(['Repeats', 'every ' + t.repeat])
  return pairs
}

/** A task's state as a badge: its mark and name; a closed task in the Projects tab says its status. */
export function statusBadge(t: Task): BadgeSpec {
  const status = statusOf(t)
  if (status === Status.DONE || status === Status.DROPPED) return { label: STATUS_LABEL[status], tone: Badge.QUIET }
  const state = STATE_MARK[stateOf(t)]
  return { label: state.label, tone: state.badge, mark: state.glyph }
}

/**
 * When a row's task is due: a red badge when late, an amber one for today; a later date is plain
 * text (`tone` null), so the colour stays for what needs attention. Null for no date.
 */
export function dueBadge(t: Task, today: string): { label: string; tone: Badge | null } | null {
  if (t.due === null) return null
  const label = dueLabel(t, today)
  const days = daysUntil(t, today)
  if (days < 0) return { label, tone: Badge.ALERT }
  if (days === 0) return { label: 'Today', tone: Badge.PAUSED }
  return { label: label[0].toUpperCase() + label.slice(1), tone: null }
}

/** High priority as a badge in Claude's accent; a row says nothing for medium and low. */
export function priorityBadge(t: Task): BadgeSpec | null {
  return t.priority === 'high' ? { label: 'High', tone: Badge.ACCENT } : null
}

/** The open task's facts as badges: state, due date, priority, project, repeat. */
export function factBadges(t: Task, today: string): Array<BadgeSpec> {
  const badges: Array<BadgeSpec> = []
  const state = statusBadge(t)
  // A pill can't wrap, so a blocker is named by its id alone.
  const blockers = t.blocked_by.map((b) => b.split(' ')[0])
  badges.push(blockers.length ? { ...state, label: cutLabel('Blocked by ' + blockers.join(', ')) } : state)
  if (t.due) {
    const isLate = t.days !== null && t.days < 0
    const when = 'Due ' + shortDate(t.due, today) + (isLate ? ' · ' + -(t.days ?? 0) + 'd late' : '')
    badges.push({ label: when, tone: isLate ? Badge.ALERT : t.days === 0 ? Badge.PAUSED : Badge.QUIET })
  }
  if (t.priority) badges.push(priorityBadge(t) ?? { label: t.priority[0].toUpperCase() + t.priority.slice(1), tone: Badge.QUIET })
  if (t.project) badges.push({ label: cutLabel(t.project), tone: Badge.QUIET })
  if (t.repeat) badges.push({ label: cutLabel('Every ' + t.repeat), tone: Badge.QUIET })
  return badges
}

/** The longest text a badge holds: a pill can't wrap, so a longer one is cut with an ellipsis. */
const BADGE_MAX = 32

function cutLabel(label: string): string {
  return label.length > BADGE_MAX ? label.slice(0, BADGE_MAX - 1) + '…' : label
}

type Option = { value: string; label: string }

/** Every status, the task's own drawn as the current value. */
export function statusOptions(): Array<Option> {
  return Object.values(Status).map((value) => ({ value, label: STATUS_LABEL[value] }))
}

/** The current due date as the drawn value, then each span's last day, then no date. */
export function dueOptions(t: Task, today: string): Array<Option> {
  const spans: Array<[Exclude<Due, typeof Due.KEEP | typeof Due.NONE>, string]> = [
    [Due.TODAY, 'Today'],
    [Due.WEEK, 'This week'],
    [Due.MONTH, 'This month'],
    [Due.YEAR, 'This year'],
  ]
  return [
    { value: Due.KEEP, label: t.due ? shortDate(t.due, today) : 'No date' },
    ...spans.map(([value, label]) => ({ value, label: label + ' (' + shortDate(dueDate(value, today) ?? today, today) + ')' })),
    ...(t.due ? [{ value: Due.NONE, label: 'No date' }] : []),
  ]
}

/** The tasks a tab lists, in drawing order, under their headings. */
function groups(d: Dock, shown: Tab): Array<{ key: string; heading: string; tasks: Array<Task> }> {
  if (shown === Tab.TODAY) {
    return d.sections.filter((s) => s.tasks.length).map((s) => ({ key: s.key, heading: s.title, tasks: byPriority(s.tasks) }))
  }
  if (shown === Tab.PROJECTS) {
    const byProject = new Map<string, Array<Task>>()
    for (const t of d.open) {
      const key = t.project ?? 'No project'
      byProject.set(key, [...(byProject.get(key) ?? []), t])
    }
    return [...byProject].map(([heading, tasks]) => ({ key: 'project-' + heading, heading, tasks: byPriority(tasks) }))
  }
  return []
}

function tabCount(d: Dock, shown: Tab): number {
  if (shown === Tab.WRITES) return writes.length
  return groups(d, shown).reduce((sum, g) => sum + g.tasks.length, 0)
}

/**
 * About how wide 11px system sans draws a text. Only an estimate, which is enough: the badge
 * centres its text, so an error shows as a pixel or two of padding on each side.
 */
function textWidth(text: string): number {
  let width = 0
  for (const ch of text) {
    if ('iljftrI.,:;!|· \''.includes(ch)) width += 3.4
    else if ('mwMW'.includes(ch)) width += 9.2
    else if ('●○◑⊘'.includes(ch)) width += 8
    else if (/[A-Z]/.test(ch)) width += 7.4
    else if (/[0-9]/.test(ch)) width += 6.6
    // Wide scripts and emoji: CJK takes a full em.
    else if (ch.charCodeAt(0) > 0x2e7f) width += 11
    else width += 6.1
  }
  return width
}

function xmlText(text: string): string {
  return text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}

/** A badge's words with the state mark that leads a status badge. */
export function badgeText(spec: BadgeSpec): string {
  return spec.mark ? spec.mark + ' ' + spec.label : spec.label
}

/** A badge as a rounded, tinted pill image, with its own width. */
export function badgeSvg(spec: BadgeSpec): { source: string; width: number } {
  const text = badgeText(spec)
  const width = Math.ceil(textWidth(text)) + 14
  const paint = BADGE_PAINT[spec.tone]
  const style =
    `.f{fill:${paint.light};fill-opacity:.13}.t{fill:${paint.light};font:${BADGE_FONT}}` +
    `@media (prefers-color-scheme:dark){.f{fill:${paint.dark};fill-opacity:.17}.t{fill:${paint.dark}}}`
  const source =
    `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${BADGE_HEIGHT}" viewBox="0 0 ${width} ${BADGE_HEIGHT}">` +
    `<style>${style}</style><rect class="f" width="${width}" height="${BADGE_HEIGHT}" rx="5"/>` +
    `<text class="t" x="${width / 2}" y="12.6" text-anchor="middle">${xmlText(text)}</text></svg>`
  return { source, width }
}

/** A badge on the desktop, an image whose text is its alt. */
function badgeBox(Svg, spec: BadgeSpec, key?: string) {
  const { source, width } = badgeSvg(spec)
  return Svg({ ...(key ? { key } : {}), source, alt: badgeText(spec), width, height: BADGE_HEIGHT })
}

function errorText(error: unknown): string {
  return String((error as { message?: string })?.message ?? error)
}

export function register(on, options: Record<string, unknown> = {}) {
  showBand = options.show_dock_band !== false

  on('session.start', async ($, e, next) => {
    startSurface = typeof e.surface === 'string' ? e.surface : null
    try {
      await $.command.register({
        name: 'synapsidian',
        description: 'Show the synapsidian band above the prompt: overdue, due today and in-progress tasks, with a button to the task pane',
        argumentHint: '[tasks | refresh]',
        immediate: true,
      })
    } catch (error) {
      $.ui.log('/synapsidian is taken, so the dock has no command: ' + errorText(error))
    }
    refresh($, false).catch((error) => $.ui.log('synapsidian dock: ' + errorText(error), { to: 'debug' }))
    $.clock.every(REFRESH_MS, () => refresh($, false))
    return next(e)
  })

  on('command.run', { command: 'synapsidian' }, async ($, e) => {
    if ((e.args ?? '').trim() === 'refresh') {
      await refresh($, true)
      return {}
    }
    if (dock === null) await refresh($, false)
    // Where nothing draws (claude -p), answer in text instead. Not `isInteractive`: the desktop
    // app reports false there too, yet draws the band. An app attached now counts as a surface.
    if (!(await canDraw($))) return { text: summaryText(dock) }
    showBand = true
    $.ui.invalidate('ui.render')
    // `/synapsidian tasks` also opens the pane, for the keyboard.
    if ((e.args ?? '').trim() === 'tasks') await openPane($)
    return {}
  })

  // Observe only: a note Claude wrote changes what the dock shows. The call itself is untouched.
  on('tool.call', { tool: WRITE_TOOLS }, async ($, e, next) => {
    const result = await next(e)
    try {
      const path = typeof e.file_path === 'string' ? e.file_path : typeof e.notebook_path === 'string' ? e.notebook_path : ''
      if (!result?.deny && !result?.isError && dock?.ok && path.startsWith(dock.vault + '/')) {
        writes = [{ rel: path.slice(dock.vault.length + 1), what: e.tool, at: await clockTime($) }, ...writes].slice(0, 30)
        refreshSoon($)
      }
    } catch (error) {
      $.ui.log('synapsidian dock: ' + errorText(error), { to: 'debug' })
    }
    return result
  })

  on('tool.call', { tool: 'Bash' }, async ($, e, next) => {
    const result = await next(e)
    try {
      if (typeof e.command === 'string' && SYNAPSIDIAN_BASH.test(e.command)) refreshSoon($)
    } catch (error) {
      $.ui.log('synapsidian dock: ' + errorText(error), { to: 'debug' })
    }
    return result
  })

  // One row: the synapsidian mark, what needs attention, then Tasks and the native close. Other mods'
  // bands go under it. In the apps a button is taller than a line of text, so there the row keeps
  // a step of space above and below, or its buttons overlap those of the bands around it.
  on('ui.render', { component: 'AbovePrompt' }, async ($, e, next) => {
    if (!showBand || !dock?.ok) return next(e)
    const { Box, Text, Button, Svg } = $.ui.resolve(e)
    const theirs = await next(e)
    const isTerminal = e.surface === 'terminal'
    const mark = isTerminal
      ? Text({ color: Tone.ACCENT, children: ['✻'] })
      : Svg({ source: SYNAPSIDIAN_MARK, alt: 'Synapsidian', width: SYNAPSIDIAN_MARK_PX, height: SYNAPSIDIAN_MARK_PX })
    const said = bandFacts(dock)
    const nothing = [Text({ dimColor: true, wrap: 'truncate-end', children: ['Nothing overdue, due today or in progress'] })]
    const factBadgeBoxes = said.length ? said.map((fact, i) => badgeBox(Svg, fact.badge, 'fact-' + i)) : nothing
    const factTexts = said.length
      ? said.flatMap((fact, i) => [
          ...(i ? [Text({ dimColor: true, children: ['·'] })] : []),
          Text({
            wrap: 'truncate-end',
            color: fact.isAlert ? Tone.ALERT : undefined,
            children: [
              Text({ weight: fact.isAlert ? 'semibold' : 'medium', children: [fact.strong] }),
              Text({ dimColor: !fact.isAlert, children: [fact.rest] }),
            ],
          }),
        ])
      : nothing
    const row = Box({
      key: 'dock-row',
      flexDirection: 'row',
      justifyContent: 'space-between',
      alignItems: 'center',
      columnGap: 2,
      ...(isTerminal ? {} : { paddingY: 'sm' }),
      children: [
        Box({
          key: 'dock-facts',
          flexDirection: 'row',
          alignItems: 'center',
          columnGap: 1,
          flexShrink: 1,
          children: [
            mark,
            Text({ weight: 'semibold', children: ['Synapsidian'] }),
            isTerminal
              ? Box({ flexDirection: 'row', columnGap: 1, marginLeft: 1, flexShrink: 1, children: factTexts })
              : Box({ flexDirection: 'row', alignItems: 'center', columnGap: 'xs', marginLeft: 1, flexShrink: 1, flexWrap: 'wrap', children: factBadgeBoxes }),
          ],
        }),
        Box({
          key: 'dock-actions',
          flexDirection: 'row',
          alignItems: 'center',
          columnGap: 1,
          children: [
            Button({ key: 'dock-open', label: 'Tasks', onPress: () => openPane($) }),
            Button({
              key: 'dock-hide',
              label: '✕',
              role: 'dismiss',
              // The desktop draws a plain Button without chrome, so there the ✕ is a bare close icon.
              ...(isTerminal ? {} : { plain: true, dimColor: true }),
              onPress: () => {
                showBand = false
                $.ui.invalidate('ui.render')
              },
            }),
          ],
        }),
      ],
    })
    return Box({ flexDirection: 'column', children: [row, ...(theirs ? [theirs] : [])] })
  })

  on('ui.render', { component: 'Pane' }, async ($, e, next) => {
    if (e.requestId !== PANE) return next(e)
    const { Box, Text, Button, Select, Svg } = $.ui.resolve(e)
    const isTerminal = e.surface === 'terminal'
    /** Room for a title in the terminal, after the mark and id (about 8 cells) and a due label. */
    const columns = Math.max(20, (e.props?.bodyColumns ?? 80) - 20)

    function redraw() {
      $.ui.invalidate('ui.render')
    }
    function cut(text: string): string {
      return text.length > columns ? text.slice(0, columns - 1) + '…' : text
    }
    function toggle(t: Task) {
      selected = selected === t.rel ? null : t.rel
      redraw()
    }
    function setStatus(t: Task, status: Status) {
      if (status !== statusOf(t)) act($, t, { status })
    }
    /**
     * The desktop draws a Button's label with its hotkey as a badge beside it, and not its
     * children, so there a button says everything in its label and carries no hotkey; the
     * terminal, where the keyboard is the way in, draws `d: Done`.
     */
    function hotkeyProps(hotkey: string) {
      return isTerminal ? { hotkey, plain: true } : {}
    }

    function tabButton(name: Tab, count: number) {
      const isActive = tab === name
      return Button({
        key: 'tab-' + name,
        label: TAB_LABEL[name].label + ' ' + count,
        ...hotkeyProps(TAB_LABEL[name].hotkey),
        // On the desktop every tab is a full button, so each has the same size and hover; a plain
        // one's hover was smaller than the active tab's fill.
        ...(isActive ? { variant: 'primary' } : { dimColor: true, ...(isTerminal ? {} : { variant: 'secondary' }) }),
        onPress: () => {
          tab = name
          redraw()
        },
        ...(isTerminal
          ? {
              children: [
                Text({ weight: isActive ? 'semibold' : 'regular', children: [TAB_LABEL[name].label] }),
                Text({ dimColor: true, tabular: true, children: [' ' + count] }),
              ],
            }
          : {}),
      })
    }

    /**
     * A row's rounded hover fill. The desktop rounds a Box's fill only along a border, and pads the
     * Box by about 13 px a side for it (2.1.323), so the fill is an empty Box with a clear round
     * border: the padding is what makes it a row's height, and the pointer tints it. The row's
     * content lies over it as an absolute layer, which the desktop draws on top, so it takes the
     * presses. (An absolute fill under relative content was drawn on top and took them.)
     */
    function hoverFill() {
      return Box({ borderStyle: 'round', borderColor: Tone.CLEAR, hover: { backgroundColor: Tone.RAISED } })
    }

    /** The desktop's id column: a row's id, or nothing under it, so what follows lines up with the title. */
    function idColumn(children: Array<unknown>) {
      return Box({ minWidth: 4, flexShrink: 0, children })
    }

    /**
     * A row. In the terminal: the state mark, the id, the title and the due label, all one plain
     * button. On the desktop: the id, the title as a plain button (drawn without chrome), then
     * badges for when it is due, high priority and its state; hovering the row tints it and shows
     * the two likeliest status moves just before the badges.
     */
    function taskRow(t: Task, isOpen: boolean, today: string) {
      const mark = STATE_MARK[stateOf(t)]
      const due = dueLabel(t, today)
      const isLate = t.days !== null && t.days < 0
      // A long open title wraps; the due label beside it keeps its width instead of folding into a column.
      const dueText = Box({
        flexShrink: 0,
        children: [Text({ size: 'footnote', tabular: true, dimColor: !isLate, color: isLate ? Tone.ALERT : undefined, children: [due] })],
      })
      if (isTerminal) {
        return Box({
          key: 'row-' + t.rel,
          flexDirection: 'row',
          justifyContent: 'space-between',
          columnGap: 2,
          children: [
            Button({
              key: 'task-' + t.rel,
              label: t.title,
              plain: true,
              onPress: () => toggle(t),
              children: [
                Text({ color: mark.color, children: [mark.glyph] }),
                ' ',
                Text({ dimColor: true, children: [t.id] }),
                ' ',
                Text({ weight: isOpen ? 'semibold' : 'regular', children: [cut(bareTitle(t))] }),
              ],
            }),
            ...(due ? [dueText] : []),
          ],
        })
      }
      // The open card shows these facts as its own badges, so its row carries none.
      const when = dueBadge(t, today)
      const priority = priorityBadge(t)
      const badges = isOpen
        ? []
        : [
            ...(when === null
              ? []
              : [when.tone === null ? Text({ size: 'footnote', dimColor: true, tabular: true, children: [when.label] }) : badgeBox(Svg, { label: when.label, tone: when.tone })]),
            ...(priority ? [badgeBox(Svg, priority)] : []),
            badgeBox(Svg, statusBadge(t)),
          ]
      const meta = Box({ flexDirection: 'row', alignItems: 'center', columnGap: 'xs', flexShrink: 0, children: badges })
      // A hover may only reveal, never hide, so the moves show beside the badges, in the room the
      // title leaves, and keep the badges in place. They are plain buttons, as tall as the title:
      // a chromed button is taller than the row and made it jump on hover.
      const quick =
        busy === null && !isOpen
          ? [
              Box({
                display: 'none',
                hover: { display: 'flex' },
                flexDirection: 'row',
                alignItems: 'center',
                columnGap: 'xs',
                flexShrink: 0,
                children: nextStatuses(t).map((status) =>
                  Button({ key: 'quick-' + status + '-' + t.rel, label: STATUS_ACTION[status].label, plain: true, onPress: () => setStatus(t, status) }),
                ),
              }),
            ]
          : []
      // A Button's label can't be bold, so an open card's title is text, set bold to lead the card,
      // and its id is the button that closes it.
      const id = Text({ size: 'footnote', dimColor: true, tabular: true, children: [t.id] })
      const title = isOpen
        ? Text({ weight: 'semibold', wrap: 'wrap', children: [bareTitle(t)] })
        : // The row's tint is the hover; the title's own would draw a second one inside it.
          Button({ key: 'task-' + t.rel, label: bareTitle(t), plain: true, hover: { backgroundColor: Tone.CLEAR }, onPress: () => toggle(t) })
      // Over the hover fill a closed row's content is absolute, filling the fill's box; an open row
      // sits in its card and is laid out in the flow.
      const line = Box({
        ...(isOpen ? {} : { position: 'absolute', top: 0, right: 0, bottom: 0, left: 0 }),
        flexDirection: 'row',
        alignItems: 'center',
        columnGap: 1,
        paddingX: 1,
        children: [
          idColumn([isOpen ? Button({ key: 'task-' + t.rel, label: t.id, plain: true, dimColor: true, onPress: () => toggle(t) }) : id]),
          Box({ flexGrow: 1, flexShrink: 1, minWidth: 0, children: [title] }),
          ...quick,
          meta,
        ],
      })
      // The keyed outer Box is the hover scope; the surface applies hovers to what lies beneath it.
      // The open row sits in its card, which carries the fill.
      return Box({ key: 'row-' + t.rel, position: 'relative', flexDirection: 'column', children: isOpen ? [line] : [hoverFill(), line] })
    }

    /**
     * Under an open row: what the task is about, its facts, then its actions in two rows: the
     * status moves with the status and due pickers, then Claude and the note in Obsidian.
     */
    function details(t: Task, today: string) {
      // On the desktop the summary is secondary text, so the title above it leads.
      const summary = t.summary
        ? Text({ wrap: 'wrap', dimColor: !isTerminal, children: [t.summary] })
        : Text({ dimColor: true, children: ['No summary in the note.'] })
      const current = statusOf(t)
      // The terminal says the facts as label and value; the desktop as badges.
      const factRow = isTerminal
        ? Box({
            flexDirection: 'row',
            flexWrap: 'wrap',
            columnGap: 2,
            children: facts(t, today).map(([label, value]) =>
              Text({
                size: 'footnote',
                children: [
                  Text({ dimColor: true, children: [label + ' '] }),
                  Text({ weight: 'medium', color: label === 'Due' && t.days !== null && t.days < 0 ? Tone.ALERT : undefined, children: [value] }),
                ],
              }),
            ),
          })
        : Box({
            flexDirection: 'row',
            flexWrap: 'wrap',
            alignItems: 'center',
            columnGap: 'xs',
            rowGap: 'xs',
            children: factBadges(t, today).map((spec, i) => badgeBox(Svg, spec, 'fact-' + i)),
          })
      const moves = nextStatuses(t).map((status, i) =>
        Button({
          key: 'act-' + status,
          label: STATUS_ACTION[status].label,
          ...hotkeyProps(STATUS_ACTION[status].hotkey),
          ...(i === 0 ? { variant: 'primary' } : {}),
          onPress: () => setStatus(t, status),
        }),
      )
      const pickers = [
        Select({
          key: 'task-status',
          label: 'Status',
          options: statusOptions(),
          value: current,
          onSelect: (value: string) => setStatus(t, value as Status),
        }),
        Select({
          key: 'task-due',
          label: 'Due',
          options: dueOptions(t, today),
          value: Due.KEEP,
          onSelect: (value: string) => {
            if (value === Due.KEEP) return
            const due = value as Exclude<Due, typeof Due.KEEP>
            if (dueDate(due, today) !== t.due) act($, t, { due })
          },
        }),
      ]
      /** On the desktop the one-press moves and the pickers are two groups, with a thin line between. */
      function group(children: Array<unknown>) {
        return Box({ flexDirection: 'row', alignItems: 'center', columnGap: 'xs', children })
      }
      const actionRows =
        busy !== null
          ? [Text({ color: Tone.PAUSED, children: [busy + '…'] })]
          : [
              Box({
                flexDirection: 'row',
                flexWrap: 'wrap',
                alignItems: 'center',
                columnGap: isTerminal ? 2 : 'sm',
                rowGap: isTerminal ? 1 : 'xs',
                children: isTerminal ? [...moves, ...pickers] : [group(moves), Svg({ source: DIVIDER, alt: '|', width: 9, height: 18 }), group(pickers)],
              }),
              Box({
                flexDirection: 'row',
                flexWrap: 'wrap',
                alignItems: 'center',
                columnGap: isTerminal ? 2 : 'xs',
                rowGap: isTerminal ? 1 : 'xs',
                children: [
                  Button({ key: 'ask-about', label: 'Ask Claude', ...hotkeyProps('a'), onPress: () => askClaude($, t, Ask.ABOUT) }),
                  Button({ key: 'ask-do', label: 'Hand to Claude', ...hotkeyProps('c'), onPress: () => askClaude($, t, Ask.DO) }),
                  Button({ key: 'act-obsidian', label: 'Open in Obsidian', ...hotkeyProps('o'), onPress: () => openInObsidian($, t.rel) }),
                ],
              }),
            ]
      const actions = Box({ flexDirection: 'column', rowGap: isTerminal ? 0 : 'xs', children: actionRows })
      // The terminal row cuts a long title, so its details start with the whole of it.
      const fullTitle = isTerminal && bareTitle(t).length > columns ? [Text({ weight: 'semibold', wrap: 'wrap', children: [bareTitle(t)] })] : []
      const body = [...fullTitle, summary, factRow, actions]
      if (isTerminal) {
        return Box({ key: 'details-' + t.rel, flexDirection: 'column', rowGap: 1, borderStyle: 'quote', borderDimColor: true, paddingLeft: 1, marginLeft: 2, children: body })
      }
      // Laid out as a row is, an empty id column then the body, so the body starts where the title does.
      return Box({
        key: 'details-' + t.rel,
        flexDirection: 'row',
        columnGap: 1,
        paddingX: 1,
        children: [idColumn([]), Box({ flexDirection: 'column', flexGrow: 1, flexShrink: 1, minWidth: 0, rowGap: 'xs', children: body })],
      })
    }

    /** On the desktop the open row and its details share one tinted card; the terminal draws them apart. */
    function openTask(t: Task, today: string) {
      if (isTerminal) return [taskRow(t, true, today), details(t, today)]
      return [
        // The round border pads the card by about 12 px down and 22 px across (2.1.323). Down that is
        // its whole padding; across, the content is drawn two cells back, so the open row's id,
        // title and details line up with the closed rows around it.
        Box({
          key: 'card-' + t.rel,
          flexDirection: 'column',
          marginY: 'xs',
          backgroundColor: Tone.RAISED,
          borderStyle: 'round',
          borderDimColor: true,
          children: [
            Box({ flexDirection: 'column', rowGap: 'xs', marginX: -2, children: [taskRow(t, true, today), details(t, today)] }),
          ],
        }),
      ]
    }

    /** A section's title and its count, which the desktop draws as a badge, red under Overdue. */
    function heading(key: string, title: string, count: number) {
      const isOverdue = key === 'overdue'
      return Box({
        flexDirection: 'row',
        alignItems: 'center',
        columnGap: 1,
        // On the desktop a step under the heading sets it apart from its first row.
        ...(isTerminal ? {} : { paddingX: 1, paddingBottom: 'xs' }),
        children: [
          Text({ weight: 'semibold', color: isOverdue ? Tone.ALERT : undefined, children: [title] }),
          isTerminal
            ? Text({ dimColor: true, tabular: true, children: [String(count)] })
            : badgeBox(Svg, { label: String(count), tone: isOverdue ? Badge.ALERT : Badge.QUIET }),
        ],
      })
    }

    const now = await $.clock.now()
    const age = ageLabel(dockAt, now)
    const refreshButton = Button({
      key: 'refresh',
      label: '↻ ' + (age ? 'Updated ' + age : 'Refresh'),
      ...hotkeyProps('r'),
      plain: true,
      dimColor: true,
      onPress: () => refresh($, true),
    })

    if (dock === null || !dock.ok) {
      const message = dock === null ? Text({ dimColor: true, children: ['Reading the vault…'] }) : Text({ color: Tone.ALERT, wrap: 'wrap', children: ['Could not read the vault: ' + (dock.error ?? 'unknown error')] })
      return Box({
        flexDirection: 'column',
        rowGap: 1,
        children: [Box({ flexDirection: 'row', justifyContent: 'space-between', children: [Text({ size: 'heading', weight: 'semibold', children: ['Synapsidian'] }), refreshButton] }), message],
      })
    }
    const d = dock
    const today = d.today

    const context = [...d.meetings.map((m) => m.title.replace(today + ' ', '')), ...(d.inbox ? ['Inbox ' + d.inbox] : [])]
    const header = Box({
      flexDirection: 'column',
      children: [
        Box({
          flexDirection: 'row',
          justifyContent: 'space-between',
          alignItems: 'center',
          columnGap: 2,
          children: [Text({ size: 'heading', weight: 'semibold', wrap: 'truncate-end', children: [longDate(today)] }), refreshButton],
        }),
        ...(context.length ? [Text({ size: 'footnote', dimColor: true, wrap: 'truncate-end', children: [context.join(' · ')] })] : []),
      ],
    })
    const tabs = Box({
      flexDirection: 'row',
      columnGap: isTerminal ? 3 : 'xs',
      children: Object.values(Tab).map((name) => tabButton(name, tabCount(d, name))),
    })

    const body: Array<unknown> = []
    if (tab === Tab.WRITES) {
      if (!writes.length) body.push(Text({ dimColor: true, children: ['No vault changes in this session yet.'] }))
      for (const w of writes) {
        body.push(
          Box({
            flexDirection: 'row',
            columnGap: 2,
            children: [
              Text({ dimColor: true, tabular: true, children: [w.at] }),
              Text({ children: [w.what] }),
              Text({ dimColor: true, wrap: 'truncate-start', children: [w.rel] }),
            ],
          }),
        )
      }
    } else {
      const listed = groups(d, tab)
      if (!listed.some((g) => g.tasks.some((t) => t.rel === selected))) selected = null
      if (!listed.length) {
        body.push(
          Box({
            flexDirection: 'column',
            children: [
              Text({ children: ['Nothing overdue, due today or in progress.'] }),
              Text({ dimColor: true, size: 'footnote', children: ['Add a task with /synapsidian:task.'] }),
            ],
          }),
        )
      }
      for (const g of listed) {
        body.push(
          Box({
            key: 'section-' + g.key,
            flexDirection: 'column',
            children: [
              heading(g.key, g.heading, g.tasks.length),
              ...g.tasks.flatMap((t) => {
                const isOpen = t.rel === selected
                return isOpen ? openTask(t, today) : [taskRow(t, false, today)]
              }),
            ],
          }),
        )
      }
    }
    return Box({
      flexDirection: 'column',
      rowGap: 1,
      children: [header, tabs, Box({ flexDirection: 'column', rowGap: 1, marginTop: isTerminal ? 0 : 1, children: body })],
    })
  })
}
