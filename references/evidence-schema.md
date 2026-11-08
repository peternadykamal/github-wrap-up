# Evidence and analysis contracts, version 1

## Collection

manifest.json: schemaVersion, snapshotAt, window {start,endExclusive,timezone,dateBasis}, subjects [{id,login,aliases}], repos [owner/name], configHash, coverage. Keep requestedEndExclusive/timezoneConfirmed/weekendDays when supplied. Raw aliases and cache are private.

repos/<owner>__<name>/records.jsonl: each record has id (globally scoped), kind, repo, actor (canonical login or unresolved/null), occurredAt, url, title, body, data. Kinds: commit, pull_request, issue, review, comment, timeline, workflow, release, deployment. Commit data: sha, merge, authoredAt, committedAt, paths, sourceAccount, attribution, detail. PR data: number, lifetime createdAt/mergedAt/closedAt, author, mergedBy and branch context. Other events keep their own actors/timestamps. Lifetime context can precede the window; annual activity uses occurrence dates. Per-user/month indexes reference shared repository evidence. See collection.md for exact collector options.

## Facts and reading

analysis/facts.json: people/team totals, monthly/weekly/hour/weekday distributions, activity rows, sourceIndex, limitations. Source IDs in sourceIndex map to URLs, kind, actor, repository, SHA/PR metadata and detail paths. Team activity has explicit personId:"team" rows, deduplicated globally. File categories overlap. Quantities describe recorded activity, not effort.

Each analysis/inspection/read-log.jsonl entry is written AFTER actual inspection:

```json
{"budgetEntryId":"usage-000003","sourceId":"<existing ID>","level":"diff","location":"repos/owner__repo/changes/<sha>.json","agent":"person/repo-worker","notes":"Concrete supported observation","inspectedAt":"2026-12-20T10:00:00Z"}
```

Levels: metadata, diff, discussion, historical_source. Reading a file list is metadata. Collector never manufactures this log. Keep bounded/binary/missing excerpt limits visible; inspect more when a claim needs it. Merge worker logs with attribution before validation.

## Research

Month/week summaries carry interval, observed counts or fact references, narrative, timeline/candidate/source IDs and coverage. Every window month appears as observed/no-observed-activity/unknown.

Candidates in analysis/people/<id>/insight-candidates.json and analysis/team/insight-candidates.json are arrays (or {candidates:[...]}) of: id, subjectIds, observation, interpretation, whyItMatters, period, evidence [{id,url,label}], inspectionIds (source IDs read), metricRefs, alternatives, coverage, confidence (high/medium/low). Optional presentation suggestions are welcome; no mandated insight types.

New calculations under analysis/calculations/*.json: id, method, inputs (source IDs), result, unit, caveats. These are reviewed derivations, never automatically executed code.

## Inspector

analysis/inspection/decisions.json before sealing:

```json
{"status":"reviewed","reviewPasses":[{"type":"factual","status":"passed","reviewer":"root inspector","notes":"Findings"},{"type":"editorial","status":"passed","reviewer":"root inspector","notes":"Findings"}],"factCheck":"passed","editorialCheck":"passed","reviewedBy":"root inspector","notes":"Specific numerical and editorial findings","decisions":[{"candidateId":"<id>","decision":"accept","reason":"Concrete source-backed reason"}]}
```

Other decisions: rewrite, combine, reject, needs-evidence. Finalized rewrites/combinations need their final candidate accepted. Only accepts may appear. Sealing validates then sets status approved and presentationSha256/factsSha256/sourceManifestSha256/researchPlanSha256/researchLedgerSha256; changed content/facts need renewed review.

## Presentation

Authoritative UI types: assets/frontend/src/types.ts. Data includes meta, people, timeline, stories, activity, coverage. See presentation.md. Additional research fields below are ignored by the UI but required by validation:

- Timeline: candidateId (accepted), contributionRole author/coauthor/pr-author/issue-author/reviewer/discussion/integrator/mixed. stage implemented/design/merged/released/unknown. Implemented/design claims need an actual diff or historical-source reading. Merged/released claims require matching source state.
- Each chapter: insightIds array of accepted candidates; evidence uses real sourceIndex IDs/URLs. Cover/finale can reference multiple accepted candidates. No fixed chapter count.
- Each metric: value, label, basis, provenance {factPath:"people.<login>.totals.commits"} OR {calculationId:"..."}. Values match exact facts/results; use unrounded strings with optional thousands separators.
- meta.totals copies facts.totals for people and team; activity copies facts.activity, including explicit team rows. Do not reconstruct team by summing people.
- Source excerpts must already be redacted; never export raw identity emails, cache, credentials or repo configuration secrets. URLs must match canonical source URLs. Missing totals show unknown, not fabricated zero.

The validator checks shape, reference integrity, metrics, reading support, privacy and hashes. It cannot certify all prose; factual and editorial judgment remain essential, with review passes determined by the selected mode.

People with no recovered contributions may have a short coverage-only story with availability "no-observed-activity" or "unavailable". All observed contribution counters, including coauthoredCommits, must be zero. Its chapters state availability/coverage and have empty evidence and insightIds; no invented candidate is required. Coverage-only stories still use complete UI fields (kicker, metrics, beats, evidence arrays). meta.coverageNotes is always an array.

Primary-authored commits and coauthoredCommits remain distinct potentially overlapping measures. Reviewer/commenter/integrator timeline credit requires evidence of that role; personal implementation credit requires an authored/coauthored commit, not merely PR ownership.

The facts include integrations (PRs merged by the person) and otherActivities (recorded timeline/workflow/release/deployment actor events) separately from primary authored code. These can overlap related lifecycle records and must not be summed into a productivity score. Release sources must retain publishedAt/draft state and refer to the same repository; draft releases never establish released status.

## Research modes

Research depth lives in analysis/research-plan.json, separate from collector identity/window config. analysis/research-ledger.jsonl records registered contexts, bounded packet/brief delivery, concise job returns and actual runtime token measurements when available. Every new read-log entry cites budgetEntryId and the actual registered reader. Delivery records are not inspection records. Mode upgrades require explicit user authorization and retain all packet counts. New unsealed content requires a plan (Medium default); previously sealed archives without a plan remain legacy-unmetered until deliberately reinspected. See modes.md for commands, packet definitions and mode-specific reviewPasses.

## Model-selection provenance

The mode plan stores active modelSelection plus previousModelSelections and snapshot hashes. See [model-selection.md](model-selection.md) for runtime catalog and assessment schemas. Each new job records modelRequest with resolutionId, role, requested modelId/effort and dispatch; runtimeReported is separate and needs an actual source. Inherited root/sequential settings can be unknown; never fabricate effective-model confirmation. Local evaluation evidence remains in the private run and is hash checked. Mode/model replacement retains historical jobs. The seal covers these bindings through the exact plan and ledger hashes. Existing jobs predating model policy remain explicitly legacy/unknown.

New runtime catalogs use schemaVersion 2 and include native adapter paths, JSON argument/configuration payloads and provider-neutral guidance with a named publisher. Older frozen version-1 records retain their original dispatch. A model-only host records effort:null and effortControl:inherited; this must not be presented as achieving the requested reasoning level. See harnesses.md for execution limits.
