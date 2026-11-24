import { expect, mock, test } from 'claude-code/testing'
import {
  addDays,
  ageLabel,
  badgeSvg,
  bandFacts,
  bareTitle,
  byPriority,
  claudeDraft,
  dueBadge,
  dueDate,
  dueLabel,
  dueOptions,
  factBadges,
  facts,
  longDate,
  nextStatuses,
  obsidianUrl,
  priorityBadge,
  shortDate,
  stateOf,
  statusBadge,
  statusOptions,
} from '../hooks/register.ts'

const VAULT = '/vault'

type Node = { type: string; props?: Record<string, any>; children?: Array<unknown> }

/** Every Svg under a node, in drawing order; Svg drops its `key`, so `find` can't reach one alone. */
function svgs(node: unknown): Array<Node> {
  if (node === null || typeof node !== 'object') return []
  const n = node as Node
  return [...(n.type === 'Svg' ? [n] : []), ...(n.children ?? []).flatMap(svgs)]
}

function task(id: string, extra: Record<string, unknown> = {}) {
  return {
    id,
    title: id + ' Do the thing',
    rel: 'Tasks/' + id + ' Do the thing.md',
    status: 'todo',
    priority: 'medium',
    due: null,
    days: null,
    blocked_by: [],
    project: null,
    repeat: null,
    ...extra,
  }
}

const OVERDUE = task('T33', { due: '2026-10-20', days: -16, summary: 'Read the review and answer each comment' })
const DOING = [task('T55', { status: 'doing', project: 'web-app' }), task('T16', { status: 'doing', priority: 'high' })]
const STATE = {
  ok: true,
  vault: VAULT,
  today: '2026-11-05',
  daily: 'Daily/2026-11-05.md',
  meetings: [{ title: '2026-11-05 Team sync', rel: 'Meetings/2026-11-05 Team sync.md' }],
  sections: [
    { key: 'overdue', title: 'Overdue', tasks: [OVERDUE] },
    { key: 'today', title: 'Due today', tasks: [] },
    { key: 'doing', title: 'In progress', tasks: DOING },
    { key: 'upcoming', title: 'Due in the next 7 days', tasks: [] },
  ],
  open: [OVERDUE, ...DOING],
  projects: ['web-app'],
  inbox: 2,
}

const PANE = {
  plugin: 'synapsidian-dock',
  component: 'Pane',
  requestId: 'synapsidian-dock',
  viewport: { columns: 120, rows: 40 },
  props: { title: 'Synapsidian', isFocused: true, bodyColumns: 80, placement: 'inline', scroll: { offset: 0, bodyRows: 20 }, view: {} },
} as const

const BAND = {
  plugin: 'synapsidian-dock',
  component: 'AbovePrompt',
  requestId: 'above-prompt',
  viewport: { columns: 120, rows: 40 },
  props: { hasSurvey: false, isWorking: false, maxRows: 5, bodyColumns: 100, scroll: { offset: 0, bodyRows: 5 }, view: {} },
} as const

const INSTALLED_SYNAPSIDIAN = '/home/a/.claude/plugins/cache/local/synapsidian/0.32.0/bin/synapsidian'
const INSTALLED = {
  version: 2,
  plugins: {
    'synapsidian@local': [
      { scope: 'user', installPath: '/home/a/.claude/plugins/cache/local/synapsidian/0.31.0', lastUpdated: '2026-10-01T00:00:00Z' },
      { scope: 'project', installPath: '/home/a/.claude/plugins/cache/local/synapsidian/0.32.0', lastUpdated: '2026-11-05T00:00:00Z' },
    ],
    'synapsidian-work@local': [{ scope: 'user', installPath: '/home/a/.claude/plugins/cache/local/synapsidian-work/0.6.0' }],
  },
}

/** Stubs Claude Code's side: the scripts answer from `answers`, every argv is recorded. */
function stubWorld(
  on,
  answers: {
    set?: unknown
    commit?: unknown
    noSynapsidian?: boolean
    slow?: boolean
    /** Like the desktop app: `synapsidian` is not on PATH, but the install record names its folder. */
    pathless?: boolean
  } = {},
) {
  const runs: Array<Array<string>> = []
  const toasts: Array<string> = []
  const saved = new Map<string, unknown>()
  const clock = mock.clock(on, { now: Date.UTC(2026, 10, 5, 9, 0) })
  on('session.start', () => ({ cwd: '/work' }))
  on('command.register', () => ({ value: undefined }))
  on('store.get', ($, e) => ({ value: saved.get(e.key) }))
  on('store.set', ($, e) => {
    saved.set(e.key, e.value)
    return { value: undefined }
  })
  on('ui.toast', ($, e) => {
    toasts.push(e.text)
    return { value: undefined }
  })
  on('ui.log', () => ({ value: undefined }))
  const opened: Array<string> = []
  on('ui.open', ($, e) => {
    opened.push(e.id)
    return { value: { isPlaced: true } }
  })
  on('ui.render', () => ({ type: 'Text', props: {}, children: ['drawn by Claude Code'] }))
  on('tool.call', () => ({ result: 'ok' }))
  mock.env(on, { HOME: '/home/a' })
  on('fs.read', ($, e) =>
    e.path === '/home/a/.claude/plugins/installed_plugins.json' && answers.pathless
      ? { value: JSON.stringify(INSTALLED) }
      : { deny: 'ENOENT: no such file ' + e.path },
  )
  on('fs.exists', ($, e) => ({ value: answers.pathless === true && e.path === INSTALLED_SYNAPSIDIAN }))
  on('process.run', ($, e) => {
    runs.push(e.argv)
    if (answers.noSynapsidian || (answers.pathless && e.argv[0] === 'synapsidian')) return { deny: 'spawn synapsidian ENOENT' }
    if (answers.slow) return { deny: 'timed out after 30000 ms' }
    const viaFile = e.argv[0] === '/bin/sh' && e.argv[1] === INSTALLED_SYNAPSIDIAN
    const command = e.argv[0] === 'synapsidian' ? e.argv[1] : viaFile ? e.argv[2] : ''
    let answer: unknown = { ok: false, error: 'unexpected command' }
    if (command === 'brief') answer = STATE
    if (command === 'note') answer = answers.set ?? { ok: true, rel: OVERDUE.rel, changed: { status: 'done' } }
    if (command === 'commit') answer = answers.commit ?? { ok: true, sha: 'abc', committed: true }
    return { value: { exitCode: 0, stdout: JSON.stringify(answer) + '\n', stderr: '' } }
  })
  return { runs, toasts, saved, clock, opened }
}

/** What follows `synapsidian <command>` in a recorded call. */
function scriptArgs(argv: Array<string>): Array<string> {
  return argv.slice(2)
}

function isSynapsidian(argv: Array<string>, command: string): boolean {
  return argv[0] === 'synapsidian' && argv[1] === command
}

/** A session where the user has asked for the band with /synapsidian. */
async function start($) {
  await $.session.start({ surface: 'terminal', isInteractive: true, cwd: '/work' })
  await $.command.run({ command: 'synapsidian', args: 'refresh' })
  await $.command.run({ command: 'synapsidian', args: '' })
}

test('the band stays hidden at session start until /synapsidian asks for it', async ($, on) => {
  stubWorld(on)
  await $.session.start({ surface: 'desktop', isInteractive: false, cwd: '/work' })
  await $.command.run({ command: 'synapsidian', args: 'refresh' })
  const band = await $.ui.mount({ ...BAND, surface: 'desktop' })
  expect(await band.find({ key: 'dock-row' })).toBeUndefined()
  expect(await $.command.run({ command: 'synapsidian', args: '' })).toEqual({})
  expect(await band.find({ key: 'dock-row' })).toBeDefined()
})

test('the band names the overdue task, what is in progress and the inbox', async ($, on) => {
  stubWorld(on)
  await start($)
  expect(bandFacts(STATE)).toEqual([
    { strong: 'T33', rest: ' 16 days overdue', isAlert: true, badge: { label: 'T33 · 16d late', tone: 'alert' } },
    { strong: '2', rest: ' in progress', isAlert: false, badge: { label: '2 in progress', tone: 'ok', mark: '●' } },
    { strong: '2', rest: ' in Inbox', isAlert: false, badge: { label: 'Inbox 2', tone: 'quiet' } },
  ])
  const terminal = await $.ui.mount({ ...BAND, surface: 'terminal' })
  expect(await terminal.find({ type: 'Text', text: '✻' })).toBeDefined()
  expect(await terminal.find({ type: 'Text', text: 'T33' })).toBeDefined()
  expect(await terminal.find({ type: 'Svg' })).toBeUndefined()
  const desktop = await $.ui.mount({ ...BAND, surface: 'desktop' })
  expect(await desktop.find({ type: 'Svg' })).toMatchObject({ props: { alt: 'Synapsidian', width: 26, height: 26 } })
  expect(await desktop.find({ key: 'dock-hide' })).toMatchObject({ props: { role: 'dismiss', label: '✕', plain: true } })
  const facts = svgs(await desktop.find({ key: 'dock-facts' }))
  expect(facts.map((s) => s.props.alt)).toEqual(['Synapsidian', 'T33 · 16d late', '● 2 in progress', 'Inbox 2'])
  expect(facts[1].props.height).toBe(18)
  expect(facts[1].props.source).toContain('#ef7a6a')
})

test('rows and the open card say state, due date and priority as badges on the desktop', async ($, on) => {
  stubWorld(on)
  await start($)
  const today = '2026-11-05'
  expect(statusBadge(DOING[0])).toEqual({ label: 'In progress', tone: 'ok', mark: '●' })
  expect(statusBadge(task('T1', { status: 'waiting' }))).toEqual({ label: 'Waiting', tone: 'paused', mark: '◑' })
  expect(statusBadge(task('T1', { blocked_by: ['T5'] }))).toEqual({ label: 'Blocked', tone: 'alert', mark: '⊘' })
  expect(statusBadge(task('T1', { status: 'done' }))).toEqual({ label: 'Done', tone: 'quiet' })
  expect(dueBadge(OVERDUE, today)).toEqual({ label: '16d late', tone: 'alert' })
  expect(dueBadge(task('T1', { due: today, days: 0 }), today)).toEqual({ label: 'Today', tone: 'paused' })
  expect(dueBadge(task('T1', { due: '2026-11-06', days: 1 }), today)).toEqual({ label: 'Tomorrow', tone: null })
  expect(dueBadge(task('T1'), today)).toBeNull()
  expect(priorityBadge(DOING[1])).toEqual({ label: 'High', tone: 'accent' })
  expect(priorityBadge(DOING[0])).toBeNull()
  expect(factBadges(OVERDUE, today)).toEqual([
    { label: 'To do', tone: 'quiet', mark: '○' },
    { label: 'Due 20 Oct · 16d late', tone: 'alert' },
    { label: 'Medium', tone: 'quiet' },
  ])
  expect(factBadges(task('T9', { blocked_by: ['T5 Buy the paint'], project: 'web-app' }), today)).toEqual([
    { label: 'Blocked by T5', tone: 'alert', mark: '⊘' },
    { label: 'Medium', tone: 'quiet' },
    { label: 'web-app', tone: 'quiet' },
  ])
  const long = factBadges(task('T9', { blocked_by: ['T5 A', 'T6 B', 'T7 C', 'T8 D', 'T10 E', 'T11 F'], project: 'a-very-long-project-name-for-the-badge' }), today)
  expect(long[0].label).toBe('Blocked by T5, T6, T7, T8, T10,…')
  expect(long[2].label).toHaveLength(32)
  // A late task whose brief carried no day count is still red.
  expect(dueBadge(task('T1', { due: '2026-11-01' }), today)).toEqual({ label: '4d late', tone: 'alert' })

  const pill = badgeSvg({ label: 'web-app <beta>', tone: 'quiet' })
  expect(pill.source).toContain('web-app &lt;beta&gt;')
  expect(pill.width).toBeGreaterThan(badgeSvg({ label: 'web-app', tone: 'quiet' }).width)

  const pane = await $.ui.mount({ ...PANE, surface: 'desktop' })
  /** The badges under a keyed Box, less the divider between the action groups. */
  async function alts(key: string) {
    return svgs(await pane.find({ key }))
      .map((s) => s.props?.alt)
      .filter((alt) => alt !== '|')
  }
  expect(await alts('section-overdue')).toEqual(['1', '16d late', '○ To do'])
  expect(await alts('section-doing')).toEqual(['2', 'High', '● In progress', '● In progress'])
  expect(await pane.find({ key: 'tab-projects' })).toMatchObject({ props: { variant: 'secondary', dimColor: true } })
  await pane.press({ key: 'task-' + OVERDUE.rel })
  expect(await alts('card-' + OVERDUE.rel)).toEqual(['○ To do', 'Due 20 Oct · 16d late', 'Medium'])
  expect(await pane.find({ type: 'Text', text: 'Do the thing' })).toMatchObject({ props: { weight: 'semibold' } })
  // The open card's id closes it.
  expect(await pane.find({ key: 'task-' + OVERDUE.rel })).toMatchObject({ props: { label: 'T33', plain: true } })
  expect(await pane.find({ key: 'card-' + OVERDUE.rel })).toMatchObject({ props: { backgroundColor: '#8080801f', borderStyle: 'round' } })
  expect(await pane.find({ type: 'Text', text: 'Read the review and answer each comment' })).toMatchObject({ props: { dimColor: true } })

  const terminal = await $.ui.mount({ ...PANE, surface: 'terminal' })
  expect(await terminal.find({ type: 'Svg' })).toBeUndefined()
  expect(await terminal.find({ type: 'Text', text: '●' })).toBeDefined()
})

test('with nothing to say the band says so', () => {
  const quiet = { ...STATE, sections: STATE.sections.map((s) => ({ ...s, tasks: [] })), open: [], inbox: 0 }
  expect(bandFacts(quiet)).toEqual([])
})

test('Tasks in the band opens the pane', async ($, on) => {
  const world = stubWorld(on)
  await start($)
  const band = await $.ui.mount({ ...BAND, surface: 'desktop' })
  await band.press({ key: 'dock-open' })
  expect(world.opened).toEqual(['synapsidian-dock'])
})

test('✕ hides the band and /synapsidian shows it again', async ($, on) => {
  stubWorld(on)
  await start($)
  const band = await $.ui.mount({ ...BAND, surface: 'terminal' })
  await band.press({ key: 'dock-hide' })
  expect(await band.find({ key: 'dock-open' })).toBeUndefined()
  expect(await $.command.run({ command: 'synapsidian', args: '' })).toEqual({})
  expect(await band.find({ key: 'dock-open' })).toBeDefined()
})

test('in the desktop app /synapsidian shows the band, though the session is not interactive', async ($, on) => {
  stubWorld(on)
  await $.session.start({ surface: 'desktop', isInteractive: false, cwd: '/work' })
  await $.command.run({ command: 'synapsidian', args: 'refresh' })
  await $.command.run({ command: 'synapsidian', args: '' })
  const band = await $.ui.mount({ ...BAND, surface: 'desktop' })
  await band.press({ key: 'dock-hide' })
  expect(await $.command.run({ command: 'synapsidian', args: '' })).toEqual({})
  expect(await band.find({ key: 'dock-open' })).toBeDefined()
  expect(await band.find({ key: 'dock-row' })).toMatchObject({ props: { paddingY: 'sm' } })
})

test('/synapsidian answers in text where nothing draws', async ($, on) => {
  stubWorld(on)
  on('session.surfaces', () => ({ value: [] }))
  await $.session.start({ surface: null, isInteractive: false, cwd: '/work' })
  await $.command.run({ command: 'synapsidian', args: 'refresh' })
  const answer = await $.command.run({ command: 'synapsidian', args: '' })
  expect(answer.text).toContain('Overdue:\n- T33 Do the thing (due 2026-10-20, 16d overdue)')
  expect(answer.text).toContain('- T16 Do the thing (doing, high)')
})

test('rows go by priority with state marks, and a press opens and closes their details', async ($, on) => {
  stubWorld(on)
  await start($)
  const pane = await $.ui.mount({ ...PANE, surface: 'desktop' })
  const section = await pane.find({ key: 'section-doing' })
  const keys = JSON.stringify(section).match(/task-Tasks\/T\d+/g) ?? []
  expect(keys.indexOf('task-Tasks/T16') < keys.indexOf('task-Tasks/T55')).toBe(true) // high before medium
  expect(await pane.find({ type: 'Text', text: 'Thursday, 5 November' })).toBeDefined()
  expect(await pane.find({ key: 'task-status' })).toBeUndefined()

  await pane.press({ key: 'task-' + OVERDUE.rel })
  expect(await pane.find({ type: 'Text', text: 'Read the review and answer each comment' })).toBeDefined()
  for (const key of ['act-doing', 'act-done', 'task-status', 'task-due', 'ask-about', 'ask-do', 'act-obsidian']) {
    expect(await pane.find({ key })).toBeDefined()
  }
  expect(await pane.find({ key: 'act-doing' })).toMatchObject({ props: { variant: 'primary', label: 'Start' } })
  expect((await pane.find({ key: 'act-doing' })).props.hotkey).toBeUndefined() // the desktop shows no hotkey badges
  expect(await pane.find({ key: 'tab-today' })).toMatchObject({ props: { label: 'Today 3', variant: 'primary' } })
  expect(await pane.find({ key: 'card-' + OVERDUE.rel })).toBeDefined()
  expect(await pane.find({ key: 'task-status' })).toMatchObject({ props: { value: 'todo' } })

  await pane.press({ key: 'task-' + OVERDUE.rel })
  expect(await pane.find({ key: 'task-status' })).toBeUndefined()
})

test('on the desktop a hovered row offers its two likeliest status moves', async ($, on) => {
  const world = stubWorld(on)
  await start($)
  const desktop = await $.ui.mount({ ...PANE, surface: 'desktop' })
  // A rounded fill the pointer tints, with the row's content laid over it.
  expect(await desktop.find({ key: 'row-' + DOING[0].rel })).toMatchObject({
    children: [{ props: { borderStyle: 'round', borderColor: '#00000000' }, hover: { backgroundColor: '#8080801f' } }, { props: { position: 'absolute', top: 0, bottom: 0 } }],
  })
  await desktop.press({ key: 'quick-done-' + DOING[0].rel })
  expect(scriptArgs(world.runs.find((argv) => isSynapsidian(argv, 'note')) ?? [])).toEqual(['set', '--file', DOING[0].rel, '--field', 'status=done'])
  const terminal = await $.ui.mount({ ...PANE, surface: 'terminal' })
  expect(await terminal.find({ key: 'quick-done-' + DOING[0].rel })).toBeUndefined()
})

test('Start in the details starts a task with one press', async ($, on) => {
  const world = stubWorld(on)
  await start($)
  const pane = await $.ui.mount({ ...PANE, surface: 'terminal' })
  await pane.press({ key: 'task-' + OVERDUE.rel })
  expect(await pane.find({ key: 'act-doing' })).toMatchObject({ props: { hotkey: 's', plain: true } })
  await pane.press({ key: 'act-doing' })
  expect(scriptArgs(world.runs.find((argv) => isSynapsidian(argv, 'note')) ?? [])).toEqual(['set', '--file', OVERDUE.rel, '--field', 'status=doing'])
  expect(world.toasts).toEqual(['start T33'])
})

test('rows say due dates the way a person would', () => {
  const today = '2026-11-05'
  expect(dueLabel(OVERDUE, today)).toBe('16d late')
  expect(dueLabel(task('T1', { due: today, days: 0 }), today)).toBe('today')
  expect(dueLabel(task('T1', { due: '2026-11-06', days: 1 }), today)).toBe('tomorrow')
  expect(dueLabel(task('T1', { due: '2026-11-09', days: 4 }), today)).toBe('Mon')
  expect(dueLabel(task('T1', { due: '2026-11-24', days: 19 }), today)).toBe('24 Nov')
  expect(dueLabel(task('T1', { due: '2027-01-04', days: 60 }), today)).toBe('4 Jan 2027')
  expect(dueLabel(task('T1', { priority: 'high' }), today)).toBe('high')
  expect(dueLabel(task('T1'), today)).toBe('')
  expect(bareTitle(OVERDUE)).toBe('Do the thing')
  expect(bareTitle(task('T1', { title: 'Untitled' }))).toBe('Untitled')
  expect(longDate('2026-11-17')).toBe('Tuesday, 17 November')
  expect(shortDate('2026-11-17', today)).toBe('17 Nov')
  expect(ageLabel(null, 0)).toBe('')
  expect(ageLabel(0, 30_000)).toBe('just now')
  expect(ageLabel(0, 120_000)).toBe('2 min ago')
  expect(nextStatuses(task('T1', { status: 'doing' }))).toEqual(['done', 'waiting'])
  expect(nextStatuses(task('T1', { status: 'waiting' }))).toEqual(['doing', 'done'])
  expect(nextStatuses(task('T1'))).toEqual(['doing', 'done'])
})

test('a blocked task is blocked whatever its status; due options end each span', () => {
  const blocked = task('T9', { status: 'doing', blocked_by: ['T5 Buy the paint'] })
  expect(stateOf(blocked)).toBe('blocked')
  expect(facts(blocked, '2026-11-05')).toEqual([
    ['Status', 'Blocked by T5 Buy the paint'],
    ['Priority', 'Medium'],
  ])
  expect(facts(OVERDUE, '2026-11-05')).toEqual([
    ['Status', 'To do'],
    ['Priority', 'Medium'],
    ['Due', '20 Oct, 16 days late'],
  ])
  expect(statusOptions().map((o) => o.value)).toEqual(['todo', 'doing', 'waiting', 'done', 'dropped'])
  /** 2026-11-05 is a Thursday. */
  expect(dueDate('today', '2026-11-05')).toBe('2026-11-05')
  expect(dueDate('week', '2026-11-05')).toBe('2026-11-08')
  expect(dueDate('week', '2026-11-08')).toBe('2026-11-08')
  expect(dueDate('month', '2026-02-10')).toBe('2026-02-28')
  expect(dueDate('year', '2026-11-05')).toBe('2026-12-31')
  expect(dueOptions(task('T1', { due: '2026-11-17' }), '2026-11-05').map((o) => o.label)).toEqual([
    '17 Nov',
    'Today (5 Nov)',
    'This week (8 Nov)',
    'This month (30 Nov)',
    'This year (31 Dec)',
    'No date',
  ])
  expect(dueOptions(task('T1'), '2026-11-05').map((o) => o.value)).toEqual(['keep', 'today', 'week', 'month', 'year'])
  expect(byPriority([task('T2', { priority: 'low' }), task('T10', { priority: 'high' }), task('T3', { priority: 'high', due: '2026-11-01' })]).map((t) => t.id)).toEqual(['T3', 'T10', 'T2'])
})

test('the Projects tab opens a task with its project in the details', async ($, on) => {
  stubWorld(on)
  await start($)
  const pane = await $.ui.mount({ ...PANE, surface: 'terminal' })
  await pane.press({ key: 'tab-projects' })
  await pane.press({ key: 'task-' + DOING[0].rel })
  expect(JSON.stringify(await pane.find({ key: 'details-' + DOING[0].rel }))).toContain('web-app')
  expect(facts(DOING[0], '2026-11-05')).toContainEqual(['Project', 'web-app'])
})

test('Status → Done sets the status, commits that one note and refreshes', async ($, on) => {
  const world = stubWorld(on)
  await start($)
  const pane = await $.ui.mount({ ...PANE, surface: 'terminal' })
  await pane.press({ key: 'task-' + OVERDUE.rel })
  const before = world.runs.length

  await pane.select({ key: 'task-status', value: 'done' })

  const [set, commit, brief] = world.runs.slice(before)
  expect(scriptArgs(set)).toEqual(['set', '--file', OVERDUE.rel, '--field', 'status=done'])
  expect(scriptArgs(commit)).toEqual(['--skill', 'task', '--message', 'close T33 (dock)', OVERDUE.rel])
  expect(brief).toEqual(['synapsidian', 'brief', '--json'])
  expect(world.toasts).toEqual(['close T33'])
})

test('a recurring task commits its next occurrence too and the toast names it', async ($, on) => {
  const next = { rel: 'Tasks/T70 Do the thing.md', id: 'T70', due: '2026-11-12' }
  const world = stubWorld(on, { set: { ok: true, rel: OVERDUE.rel, changed: { status: 'done' }, next } })
  await start($)
  const pane = await $.ui.mount({ ...PANE, surface: 'desktop' })
  await pane.press({ key: 'task-' + OVERDUE.rel })
  await pane.select({ key: 'task-status', value: 'done' })
  expect(world.runs.find((argv) => isSynapsidian(argv, 'commit'))?.slice(-2)).toEqual([OVERDUE.rel, next.rel])
  expect(world.toasts).toEqual(['close T33 · next T70 due 2026-11-12'])
})

test('Due → This week sets the due date to this Sunday; picking the same status changes nothing', async ($, on) => {
  const world = stubWorld(on)
  await start($)
  const pane = await $.ui.mount({ ...PANE, surface: 'terminal' })
  await pane.press({ key: 'task-' + DOING[1].rel })
  await pane.select({ key: 'task-status', value: 'doing' })
  expect(world.runs.some((argv) => isSynapsidian(argv, 'note'))).toBe(false)
  await pane.select({ key: 'task-due', value: 'week' })
  const set = world.runs.find((argv) => isSynapsidian(argv, 'note'))
  expect(scriptArgs(set ?? [])).toEqual(['set', '--file', DOING[1].rel, '--field', 'due=2026-11-08'])
  expect(world.toasts).toEqual(['move T16 to 2026-11-08'])
})

test('Due → No date clears the field', async ($, on) => {
  const world = stubWorld(on)
  await start($)
  const pane = await $.ui.mount({ ...PANE, surface: 'terminal' })
  await pane.press({ key: 'task-' + OVERDUE.rel })
  await pane.select({ key: 'task-due', value: 'none' })
  expect(scriptArgs(world.runs.find((argv) => isSynapsidian(argv, 'note')) ?? [])).toEqual(['set', '--file', OVERDUE.rel, '--field', 'due='])
  expect(world.toasts).toEqual(['clear the due date of T33'])
})

test('Hand to Claude puts a draft in the prompt box and runs nothing', async ($, on) => {
  const world = stubWorld(on)
  const drafts: Array<string> = []
  on('prompt.fill', ($, e) => {
    drafts.push(e.text)
    return { isFilled: true }
  })
  await start($)
  const before = world.runs.length
  const pane = await $.ui.mount({ ...PANE, surface: 'desktop' })
  await pane.press({ key: 'task-' + OVERDUE.rel })
  await pane.press({ key: 'ask-do' })
  expect(drafts).toEqual([claudeDraft('do', OVERDUE)])
  expect(drafts[0]).toMatch(/^Work on the task \[\[T33 Do the thing\]\]/)
  expect(world.runs.length).toBe(before)
})

test('a refused change commits nothing and says why', async ($, on) => {
  const world = stubWorld(on, { set: { ok: false, error: 'unknown field' } })
  await start($)
  const pane = await $.ui.mount({ ...PANE, surface: 'terminal' })
  await pane.press({ key: 'task-' + OVERDUE.rel })
  await pane.select({ key: 'task-status', value: 'dropped' })
  expect(world.runs.some((argv) => isSynapsidian(argv, 'commit'))).toBe(false)
  expect(world.toasts).toEqual(['T33 unchanged: unknown field'])
})

test('a note Claude writes in the vault shows under Writes; one outside it does not', async ($, on) => {
  const world = stubWorld(on)
  await start($)
  await $.tool.call({ tool: 'Write', file_path: VAULT + '/Notes/Feature flags.md', content: 'x' })
  await $.tool.call({ tool: 'Write', file_path: '/work/src/app.ts', content: 'x' })
  const before = world.runs.length
  await world.clock.advance(1500)
  expect(world.runs.length).toBe(before + 1) // one refresh for the vault write, none for the other

  const pane = await $.ui.mount({ ...PANE, surface: 'terminal' })
  await pane.press({ key: 'tab-writes' })
  expect(await pane.find({ type: 'Text', text: 'Notes/Feature flags.md' })).toBeDefined()
  expect(await pane.find({ type: 'Text', text: 'Write' })).toBeDefined()
  expect(await pane.find({ type: 'Text', text: /app\.ts/ })).toBeUndefined()
})

test('the Projects tab groups open tasks by project', async ($, on) => {
  stubWorld(on)
  await start($)
  const pane = await $.ui.mount({ ...PANE, surface: 'vscode' })
  await pane.press({ key: 'tab-projects' })
  expect(await pane.find({ type: 'Text', text: 'web-app' })).toBeDefined()
  expect(await pane.find({ type: 'Text', text: 'No project' })).toBeDefined()
})

test('sessions reuse a fresh shared state instead of running the brief again', async ($, on) => {
  const world = stubWorld(on)
  world.saved.set('dock', { at: Date.UTC(2026, 10, 5, 8, 59, 30), state: STATE })
  await $.session.start({ surface: 'terminal', isInteractive: true, cwd: '/work' })
  await world.clock.settle()
  await $.command.run({ command: 'synapsidian', args: '' })
  expect(world.runs.length).toBe(0)
})

test('without synapsidian on PATH it runs the installed synapsidian script, and keeps using it', async ($, on) => {
  const world = stubWorld(on, { pathless: true })
  await start($)
  const pane = await $.ui.mount({ ...PANE, surface: 'desktop' })
  expect(await pane.find({ key: 'task-' + OVERDUE.rel })).toBeDefined()
  expect(world.runs).toContainEqual(['/bin/sh', INSTALLED_SYNAPSIDIAN, 'brief', '--json'])
  const bare = world.runs.filter((argv) => argv[0] === 'synapsidian').length
  await pane.press({ key: 'task-' + OVERDUE.rel })
  await pane.select({ key: 'task-status', value: 'done' })
  expect(world.runs.filter((argv) => argv[0] === 'synapsidian').length).toBe(bare)
  expect(world.runs).toContainEqual(['/bin/sh', INSTALLED_SYNAPSIDIAN, 'note', 'set', '--file', OVERDUE.rel, '--field', 'status=done'])
  expect(world.toasts).toEqual(['close T33'])
})

test('with synapsidian nowhere the pane says it is not installed', async ($, on) => {
  const world = stubWorld(on, { noSynapsidian: true })
  await start($)
  const pane = await $.ui.mount({ ...PANE, surface: 'terminal' })
  expect(await pane.find({ type: 'Text', text: /found neither on PATH nor among the installed plugins/ })).toBeDefined()
  expect(world.saved.has('dock')).toBe(false)
})

test('a synapsidian run that times out is reported as that, not as a missing command', async ($, on) => {
  stubWorld(on, { slow: true })
  await start($)
  const pane = await $.ui.mount({ ...PANE, surface: 'terminal' })
  expect(await pane.find({ type: 'Text', text: /synapsidian brief did not finish: .*timed out/ })).toBeDefined()
  expect(await pane.find({ type: 'Text', text: /not on PATH/ })).toBeUndefined()
})

test('dates and Obsidian links', () => {
  expect(addDays('2026-12-31', 1)).toBe('2027-01-01')
  expect(addDays('2026-11-05', 7)).toBe('2026-11-12')
  expect(obsidianUrl('/Users/a/My Synapsidian', 'Tasks/T1 A & B.md')).toBe('obsidian://open?vault=My%20Synapsidian&file=Tasks%2FT1%20A%20%26%20B')
})
