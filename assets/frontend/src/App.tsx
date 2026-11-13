import { useEffect, useMemo, useRef, useState } from 'react';
import { Activity as ActivityIcon, ArrowDown, ArrowLeft, ArrowRight, ArrowUpRight, BookOpen,
  CalendarDays, ChevronDown, Download,
  Search, ShieldCheck, Users, X } from 'lucide-react';
import raw from './data.json';
import type { Beat, Chapter, Evidence, Milestone, Person, Presentation, Story } from './types';

const data = raw as Presentation;
const formatter = new Intl.NumberFormat('en');
const number = (value?: number) => value === undefined ? '—' : formatter.format(value);
const people = new Map(data.people.map(person => [person.id, person]));
const dateParts = new Intl.DateTimeFormat('en-CA', {
  timeZone: data.meta.timezone, year: 'numeric', month: '2-digit', day: '2-digit',
});

function dateKey(value: string) {
  if (!value || value.length === 10) return value;
  const fields = Object.fromEntries(dateParts.formatToParts(new Date(value)).map(part => [part.type, part.value]));
  return [fields.year, fields.month, fields.day].join('-');
}

function dateLabel(value: string, options: Intl.DateTimeFormatOptions = { day: 'numeric', month: 'short', year: 'numeric' }) {
  const key = dateKey(value);
  return key ? new Intl.DateTimeFormat('en-GB', { ...options, timeZone: 'UTC' }).format(new Date(key + 'T12:00:00Z')) : '—';
}

const monthLabel = (key: string) => dateLabel(key + '-01', { month: 'long', year: 'numeric' });
const endDate = data.meta.endExclusive ? dateKey(new Date(Date.parse(data.meta.endExclusive) - 1).toISOString()) : '';
const startDate = dateKey(data.meta.start);
const period = startDate && endDate ? dateLabel(startDate) + ' – ' + dateLabel(endDate) : 'Reporting period unavailable';
const coverageLabel = data.coverage.status === 'complete' ? 'Scope collected' :
  data.coverage.status === 'partial' ? 'Partial coverage' : 'Coverage notes';
const stages = { implemented: 'Implemented', design: 'Design', merged: 'Merged', released: 'Released', unknown: 'Recorded' };
const series = [
  { key: 'commits', label: 'Non-merge commits' },
  { key: 'prs', label: 'Authored pull requests' },
  { key: 'reviews', label: 'Submitted reviews' },
] as const;
type SeriesKey = typeof series[number]['key'];
type MonthActivity = { month: string } & Record<SeriesKey, number>;

function safeUrl(url: string) {
  try {
    const parsed = new URL(url);
    return parsed.protocol === 'https:' && !parsed.username && !parsed.password ? parsed.href : undefined;
  } catch { return undefined; }
}

function beatSource(beat: Beat, chapter: Chapter) {
  return chapter.evidence.find(item => beat.sourceId ? item.id === beat.sourceId : beat.url === item.url);
}

function downloadStory(story: Story) {
  const chapters = story.chapters.map(chapter => [
    '## ' + chapter.title,
    chapter.body,
    chapter.insight,
    ...chapter.metrics.map(metric => '- ' + metric.value + ' ' + metric.label + ' (' + metric.basis + ')'),
    ...chapter.beats.map(beat => '### ' + beat.title + '\n\n' + beat.body),
    ...chapter.evidence.filter(item => safeUrl(item.url)).map(item => '- [' + item.label + '](' + item.url + ')'),
  ].filter(Boolean).join('\n\n'));
  const content = ['# ' + story.title, story.thesis, ...chapters, '## Coverage', coverageLabel,
    data.coverage.summary, ...data.coverage.limitations].join('\n\n');
  const url = URL.createObjectURL(new Blob([content], { type: 'text/markdown;charset=utf-8' }));
  const link = document.createElement('a');
  link.href = url;
  link.download = 'year-in-review-' + story.personId + '.md';
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function Avatar({ person }: { person?: Person }) {
  const initials = person?.name.trim().split(/\s+/).slice(0, 2).map(word => word[0]).join('');
  return <span className="avatar" aria-hidden="true" style={{ backgroundColor: person?.color }}>
    {initials || <Users size={14} />}
  </span>;
}

function Stage({ stage }: { stage: Milestone['stage'] }) {
  return <span className={'stage stage-' + stage}>{stages[stage]}</span>;
}

function SourceList({ items }: { items: Evidence[] }) {
  if (!items.length) return <p className="muted">No sources are attached to this chapter.</p>;
  return <ul className="source-list">{items.map(item => {
    const url = safeUrl(item.url);
    return <li key={item.id}>
      <span className="source-id">{item.id}</span>
      {url ? <a href={url} target="_blank" rel="noreferrer">{item.label}<ArrowUpRight size={15} /></a> : <strong>{item.label}</strong>}
      {item.excerpt && <details><summary>Inspected excerpt</summary><pre>{item.excerpt}</pre></details>}
    </li>;
  })}</ul>;
}

function Dialog({ label, className, close, children }: {
  label: string; className: string; close: () => void; children: React.ReactNode;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const element = dialog.current;
    const previous = document.activeElement as HTMLElement | null;
    const overflow = document.body.style.overflow;
    element?.showModal();
    document.body.style.overflow = 'hidden';
    return () => {
      element?.close();
      document.body.style.overflow = overflow;
      previous?.focus();
    };
  }, []);
  return <dialog aria-label={label} className={className} ref={dialog}
    onCancel={event => { event.preventDefault(); close(); }}
    onClick={event => { if (event.target === event.currentTarget) close(); }}>
    <div className="dialog-shell">{children}</div>
  </dialog>;
}

function EvidenceDrawer({ item, close }: { item: Milestone; close: () => void }) {
  return <Dialog label="Milestone evidence" className="drawer" close={close}>
    <header className="dialog-top"><span><BookOpen size={17} /> Milestone evidence</span>
      <button className="icon-button" aria-label="Close milestone evidence" onClick={close}><X size={21} /></button>
    </header>
    <div className="drawer-content">
      <div className="milestone-meta"><Stage stage={item.stage} /><time dateTime={item.date}>{dateLabel(item.date)}</time></div>
      <h2>{item.title}</h2><p>{item.summary}</p><code>{item.repo}</code>
      {item.caveat && <p className="note">{item.caveat}</p>}
      <h3>Sources</h3><SourceList items={item.evidence} />
    </div>
  </Dialog>;
}

function ChapterBody({ chapter }: { chapter: Chapter }) {
  return <>
    <p className="chapter-body">{chapter.body}</p>
    {chapter.metrics.length > 0 && <div className="chapter-metrics">{chapter.metrics.map((metric, index) =>
      <div key={index}><strong>{metric.value}</strong><span>{metric.label}</span>
        <details><summary>Counting rule</summary><p>{metric.basis}</p></details></div>)}</div>}
    {(chapter.before || chapter.after || chapter.beats.length > 0) && <div className={'chapter-beats layout-' + chapter.layout}>
      {chapter.before && <p><strong>Before</strong>{chapter.before}</p>}
      {chapter.after && <p><strong>After</strong>{chapter.after}</p>}
      {chapter.beats.map((beat, index) => {
        const source = beatSource(beat, chapter);
        const url = source && safeUrl(source.url);
        return <article key={index}>{beat.label && <span className="eyebrow">{beat.label}</span>}
          <h3>{beat.title}</h3><p>{beat.body}</p>{url && <a href={url} target="_blank" rel="noreferrer">Source<ArrowUpRight size={14} /></a>}
        </article>;
      })}
    </div>}
    {chapter.insight && <blockquote>{chapter.insight}</blockquote>}
    {chapter.evidence.length > 0 && <details className="chapter-sources">
      <summary><BookOpen size={16} /> Chapter sources <span>{chapter.evidence.length}</span></summary>
      <SourceList items={chapter.evidence} />
    </details>}
  </>;
}

function Wrapped({ story, close, changePerson }: { story: Story; close: () => void; changePerson: (id: string) => void }) {
  const [step, setStep] = useState(0);
  const scroll = useRef<HTMLDivElement>(null);
  const chapter = story.chapters[step];
  function go(index: number) {
    setStep(Math.max(0, Math.min(index, story.chapters.length - 1)));
    scroll.current?.scrollTo({ top: 0 });
  }
  return <Dialog label="Wrapped story" className="wrapped" close={close}>
    <header className="dialog-top"><span><BookOpen size={18} /> Wrapped</span>
      <div className="wrapped-actions">
        <select aria-label="Choose Wrapped story" value={story.personId} onChange={event => { go(0); changePerson(event.target.value); }}>
          {data.stories.map(entry => <option key={entry.personId} value={entry.personId}>{people.get(entry.personId)?.name ?? 'Whole team'}</option>)}
        </select>
        <button className="icon-button" aria-label="Download story" onClick={() => downloadStory(story)}><Download size={18} /></button>
        <button className="icon-button" aria-label="Close Wrapped" onClick={close}><X size={21} /></button>
      </div>
    </header>
    <div className="reader-layout" onKeyDown={event => {
      if ((event.target as HTMLElement).closest('select')) return;
      if (event.key === 'ArrowLeft') { event.preventDefault(); go(step - 1); }
      if (event.key === 'ArrowRight') { event.preventDefault(); go(step + 1); }
    }}>
      <nav className="chapter-nav" aria-label="Chapters">
        {story.chapters.map((item, index) => <button key={item.id} aria-current={index === step ? 'step' : undefined}
          onClick={() => go(index)}><span>{index + 1}</span>{item.title}</button>)}
      </nav>
      <div className="chapter-scroll" ref={scroll}>
        <article className={'chapter-page chapter-' + chapter.layout}>
          <header><span className="eyebrow">{chapter.kicker}</span><h2>{chapter.title}</h2></header>
          <ChapterBody chapter={chapter} />
        </article>
      </div>
    </div>
    <footer className="reader-footer">
      <button className="button secondary" onClick={() => go(step - 1)} disabled={step === 0}><ArrowLeft size={16} /> Previous</button>
      <span aria-live="polite">{step + 1} / {story.chapters.length}</span>
      <button className="button primary" onClick={() => go(step + 1)} disabled={step === story.chapters.length - 1}>Next <ArrowRight size={16} /></button>
    </footer>
  </Dialog>;
}

function aggregate(person: string): MonthActivity[] {
  const months = new Map<string, MonthActivity>();
  if (startDate && endDate) {
    const cursor = new Date(startDate.slice(0, 7) + '-01T12:00:00Z');
    while (cursor.toISOString().slice(0, 10) <= endDate) {
      const month = cursor.toISOString().slice(0, 7);
      months.set(month, { month, commits: 0, prs: 0, reviews: 0 });
      cursor.setUTCMonth(cursor.getUTCMonth() + 1);
    }
  }
  for (const entry of data.activity) {
    if (entry.personId !== person) continue;
    const month = months.get(entry.date.slice(0, 7));
    if (month) for (const { key } of series) month[key] += entry[key];
  }
  return [...months.values()];
}

function MonthlyActivity({ months, chooseMonth, selected }: {
  months: MonthActivity[]; chooseMonth: (month: string) => void; selected: string;
}) {
  const [metric, setMetric] = useState<SeriesKey>('commits');
  const label = series.find(item => item.key === metric)!.label;
  const maximum = Math.max(1, ...months.map(month => month[metric]));
  return <section className="activity-card" aria-label="Monthly activity">
    <header><h2>Activity by month</h2><label className="select-field">
      <select aria-label="Activity metric" value={metric} onChange={event => setMetric(event.target.value as SeriesKey)}>
        {series.map(item => <option value={item.key} key={item.key}>{item.label}</option>)}
      </select><ChevronDown size={14} />
    </label></header>
    {months.length ? <div className="month-chart" aria-label={label + ' by month'}>
      {months.map(month => <button key={month.month} aria-pressed={selected === month.month}
        aria-label={monthLabel(month.month) + ', ' + number(month[metric]) + ' ' + label.toLowerCase()}
        onClick={() => chooseMonth(month.month)}>
        <span className="bar-track"><span style={{ height: 100 * month[metric] / maximum + '%' }} /></span>
        <span className="chart-month">{dateLabel(month.month + '-01', { month: 'short' })}</span>
        <strong>{number(month[metric])}</strong>
      </button>)}
    </div> : <p className="muted">Monthly activity is unavailable.</p>}
  </section>;
}

function ActivityTable({ months }: { months: MonthActivity[] }) {
  return <div className="table-scroll"><table>
    <caption>Monthly counts for the selected person or team</caption>
    <thead><tr><th scope="col">Month</th>{series.map(item => <th key={item.key} scope="col">{item.label}</th>)}</tr></thead>
    <tbody>{months.map(month => <tr key={month.month}><th scope="row">{monthLabel(month.month)}</th>
      {series.map(item => <td key={item.key}>{number(month[item.key])}</td>)}</tr>)}</tbody>
  </table></div>;
}

function Coverage() {
  return <section className="coverage-view">
    <span className="coverage-chip"><ShieldCheck size={15} />{coverageLabel}</span>
    <h2>Method & coverage</h2><p>{data.coverage.summary}</p>
    <dl><div><dt>Reporting period</dt><dd>{period}</dd></div><div><dt>Timezone</dt><dd>{data.meta.timezone}</dd></div>
      <div><dt>Snapshot</dt><dd>{dateLabel(data.meta.snapshotAt)}</dd></div></dl>
    <h3>Collection notes</h3>
    <ul>{[...new Set([...data.meta.coverageNotes, ...data.coverage.limitations])].map(note => <li key={note}>{note}</li>)}</ul>
  </section>;
}

export default function App() {
  const [person, setPerson] = useState('team');
  const [repo, setRepo] = useState('all');
  const [month, setMonth] = useState('all');
  const [query, setQuery] = useState('');
  const [view, setView] = useState<'timeline' | 'activity' | 'coverage'>('timeline');
  const [wrapped, setWrapped] = useState(false);
  const [selected, setSelected] = useState<Milestone | null>(null);
  const [limit, setLimit] = useState(24);
  const currentPerson = people.get(person);
  const story = data.stories.find(entry => entry.personId === person);
  const totals = data.meta.totals?.[person];
  const months = useMemo(() => aggregate(person), [person]);
  const ownTimeline = useMemo(() => data.timeline.filter(item => person === 'team' || item.people.includes(person)), [person]);
  const repositories = [...new Set(ownTimeline.map(item => item.repo))].sort();
  const search = query.trim().toLowerCase();
  const filtered = ownTimeline.filter(item => (repo === 'all' || item.repo === repo)
    && (month === 'all' || dateKey(item.date).startsWith(month))
    && (!search || [item.title, item.summary, item.repo].join(' ').toLowerCase().includes(search)))
    .sort((a, b) => Date.parse(a.date) - Date.parse(b.date));
  const grouped = new Map<string, Milestone[]>();
  for (const item of filtered.slice(0, limit)) {
    const key = dateKey(item.date).slice(0, 7);
    const group = grouped.get(key);
    if (group) group.push(item);
    else grouped.set(key, [item]);
  }

  useEffect(() => { document.title = data.meta.title || 'GitHub Wrap Up'; }, []);
  useEffect(() => setLimit(24), [person, repo, month, query]);

  function changePerson(id: string) { setPerson(id); setRepo('all'); }
  function selectMonth(value: string) { setMonth(value === month ? 'all' : value); setView('timeline'); }
  function showCoverage() { setView('coverage'); document.getElementById('report')?.scrollIntoView(); }
  function reset() { setRepo('all'); setMonth('all'); setQuery(''); }

  return <>
    <a className="skip-link" href="#report">Skip to the report</a>
    <header className="site-header"><div className="header-inner">
      <a href="#top" className="brand">GitHub Wrap Up</a>
      <div>
        <button className="text-button coverage-trigger" onClick={showCoverage}>{coverageLabel}</button>
        <button className="text-button" disabled={!story} onClick={() => setWrapped(true)}>Open Wrapped <ArrowUpRight size={16} /></button>
      </div>
    </div></header>
    <main id="top" className="container">
      <section className="overview">
        <div className="overview-copy">
          <h1>{data.meta.title || 'GitHub year in review'}</h1>
          {story?.thesis && <p>{story.thesis}</p>}
        </div>
        <div className="edition">
          <dl><dt>Reporting period</dt><dd>{period}</dd><dt>Reporting timezone</dt><dd>{data.meta.timezone}</dd></dl>
          <a href="#report" onClick={() => setView('timeline')}>Explore timeline <ArrowDown size={15} /></a>
        </div>
      </section>

      <section aria-label="Totals for the full reporting period" className="summary-section">
        <div className="summary-label"><span>{currentPerson?.name ?? 'Whole team'}</span><span>Full reporting period</span></div>
        <dl className="summary">
          {[...series, { key: 'repositories' as const, label: 'Repositories' }].map(({ key, label }) =>
            <div className="stat" key={key}><dt>{label}</dt><dd>{number(totals?.[key])}</dd></div>)}
        </dl>
      </section>

      <section id="report" className="report">
        <div className="report-nav">
          <nav aria-label="Report sections">
            {([['timeline', 'Timeline', CalendarDays], ['activity', 'Activity', ActivityIcon], ['coverage', 'Coverage', ShieldCheck]] as const)
              .map(([id, label, Icon]) => <button key={id} aria-pressed={view === id} onClick={() => setView(id)}><Icon size={17} />{label}</button>)}
          </nav>
          <label className="select-field person-select"><Users size={16} /><select aria-label="Select person" value={person} onChange={event => changePerson(event.target.value)}>
            <option value="team">Whole team</option>{data.people.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}
          </select><ChevronDown size={14} /></label>
        </div>
        {currentPerson && <div className="person-heading"><Avatar person={currentPerson} /><div><strong>{currentPerson.name}</strong><p>{currentPerson.headline}</p></div></div>}

        {view === 'coverage' ? <Coverage /> : view === 'activity' ? <div className="activity-view">
          <MonthlyActivity months={months} chooseMonth={selectMonth} selected={month} /><ActivityTable months={months} />
        </div> : <>
          <div className="report-grid">
            <section className="timeline-panel">
              <div className="timeline-heading"><div><h2>Timeline</h2><p aria-live="polite">{number(filtered.length)} {filtered.length === 1 ? 'milestone' : 'milestones'}</p></div>
                {(query || month !== 'all' || repo !== 'all') && <button className="text-button" onClick={reset}>Clear filters</button>}
              </div>
              <div className="filters">
                <label className="search-field"><Search size={17} /><input aria-label="Search milestones" placeholder="Search milestones" value={query} onChange={event => setQuery(event.target.value)} /></label>
                <label className="select-field"><select aria-label="Repository" value={repo} onChange={event => setRepo(event.target.value)}>
                  <option value="all">All repositories</option>{repositories.map(name => <option key={name}>{name}</option>)}
                </select><ChevronDown size={14} /></label>
                <label className="select-field"><select aria-label="Month" value={month} onChange={event => setMonth(event.target.value)}>
                  <option value="all">All months</option>{months.map(item => <option key={item.month} value={item.month}>{monthLabel(item.month)}</option>)}
                </select><ChevronDown size={14} /></label>
              </div>
              {filtered.length === 0 && <div className="empty"><CalendarDays size={24} /><h3>{ownTimeline.length ? 'No matching milestones' : 'No reviewed milestones'}</h3>
                <p>{ownTimeline.length ? 'Try a different search or clear the filters.' : 'Activity and coverage are available in the report tabs.'}</p></div>}
              {[...grouped].map(([key, items]) => <section className="month-section" key={key}>
                <h3>{monthLabel(key)}</h3>
                <div>{items.map(item => <article className="milestone" key={item.id}>
                  <time className="milestone-date" dateTime={item.date}>{dateLabel(item.date, { day: 'numeric', month: 'short' })}</time>
                  <div className="milestone-content">
                  <div className="milestone-meta"><code>{item.repo}</code><Stage stage={item.stage} /></div>
                  <h4><button onClick={() => setSelected(item)}>{item.title}<ArrowUpRight size={17} /></button></h4>
                  <p>{item.summary}</p>
                  <footer><span className="credit">{item.people.map(id => people.get(id)?.name || id).join(', ')}</span>
                    <button className="text-button" onClick={() => setSelected(item)}>{item.evidence.length} {item.evidence.length === 1 ? 'source' : 'sources'}<ArrowRight size={14} /></button>
                  </footer>
                  </div>
                </article>)}</div>
              </section>)}
              {filtered.length > limit && <button className="button secondary more" onClick={() => setLimit(limit + 24)}>Show more milestones <ArrowDown size={16} /></button>}
            </section>
            <aside className="report-aside">
              <MonthlyActivity months={months} chooseMonth={selectMonth} selected={month} />
              {story && <section className="story-card"><p className="eyebrow">Wrapped · {story.chapters.length} {story.chapters.length === 1 ? 'chapter' : 'chapters'}</p>
                <h2>{story.title}</h2>
                <button className="text-button" onClick={() => setWrapped(true)}>Read the story <ArrowUpRight size={16} /></button>
              </section>}
            </aside>
          </div>
        </>}
      </section>
      <footer className="page-footer"><span>GitHub Wrap Up</span><span>{period}</span>
        {story && <button className="text-button" onClick={() => downloadStory(story)}><Download size={15} /> Download story</button>}
      </footer>
    </main>
    {wrapped && story && <Wrapped story={story} close={() => setWrapped(false)} changePerson={changePerson} />}
    {selected && <EvidenceDrawer item={selected} close={() => setSelected(null)} />}
  </>;
}
