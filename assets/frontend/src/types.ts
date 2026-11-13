export type Evidence = { id: string; url: string; label: string; excerpt?: string };
export type Person = { id: string; name: string; color: string; headline: string };
export type Metric = { value: string; label: string; basis: string };
export type Beat = { title: string; body: string; label?: string; sourceId?: string; url?: string };
export type Chapter = {
  id: string; title: string; kicker: string; body: string; insight?: string;
  layout: "cover"|"journey"|"contrast"|"map"|"ledger"|"spotlight"|"finale";
  metrics: Metric[]; beats: Beat[]; evidence: Evidence[]; before?: string; after?: string;
};
export type Story = { personId: string; title: string; thesis: string; theme: string; chapters: Chapter[] };
export type Milestone = {
  id: string; title: string; summary: string; date: string; people: string[]; repo: string;
  evidence: Evidence[]; stage: "implemented"|"design"|"merged"|"released"|"unknown"; caveat?: string;
};
export type Activity = { date: string; personId: string; commits: number; prs: number; reviews: number };
export type Totals = { commits: number; prs: number; reviews: number; repositories: number; basis?: string };
export type Presentation = {
  meta: { title: string; start: string; endExclusive: string; timezone: string; snapshotAt: string;
    coverageNotes: string[]; totals?: Record<string, Totals> };
  people: Person[]; timeline: Milestone[]; stories: Story[]; activity: Activity[];
  coverage: { summary: string; limitations: string[]; status?: "complete" | "partial" };
};
