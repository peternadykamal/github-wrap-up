# Reviewed evidence to a portable yearbook

Read this only after the inspector has finished the content. Do not start frontend work during scraping or candidate generation. The retained starter is `assets/frontend/`; do not modify it for an individual run. It contains no real identities, company branding, site IDs or research data.

## Report layout

The template uses React, TypeScript, Vite, CSS and Lucide. The overview uses a compact title and reporting period above a single row of counts. Use the page typography and column rules to establish hierarchy. Keep the timeline as dated entries with repository, contributor and source labels. The main workspace has a person selector and three views for the timeline, activity and collection coverage. Keep Whole team selected on arrival.

Use reviewed milestones for the timeline and source drawers. Keep person and time labels visible. Repository, month and text filters narrow the timeline while monthly activity and totals cover the selected person or team for the full period. Use the existing monthly chart and exact-value table for commits, authored PRs and submitted reviews. Keep the chart keyboard accessible and preserve its full-period basis.

Wrapped uses a chapter reader with an overview, chapter navigation, metrics, source links and a Markdown download. Keep each person's storyline grounded in their accepted evidence. Use the chapter layout fields to express the structure of the work. Adapt typography, color or composition where it improves readability and keep layout mobile-friendly. Bundle custom assets locally and check that extensions remain usable offline.

## Data and approval boundary

The exact rendering contract is `assets/frontend/src/types.ts`. The analysis inspector may add provenance fields beyond these display types. Required envelope:

- `meta`: title, inclusive start, exclusive end, declared timezone, snapshot time, coverage notes, optional approved totals per canonical person ID and `team`.
- `people`: canonical IDs, display names, headline and color.
- `timeline`: source-linked milestones, people, repository, date, stage and caveat. Stage vocabulary is `implemented`, `design`, `merged`, `released`, `unknown`. A merge is not a release.
- `stories`: one `team` story and each selected person's distinct story, with a variable number of chapters. Metrics require a counting basis. Beats and chapters reference source evidence.
- `activity`: daily `{date,personId,commits,prs,reviews}` rows. `date` is the declared timezone's `YYYY-MM-DD`. Include independently SHA-deduplicated `personId: "team"` rows. Never sum contributor commit counts to reconstruct team totals: co-authorship/mirrors can duplicate them.
- `coverage`: summary and limitations, including partial collection or a deliberately empty period. A new seal writes the collection status from the facts. An empty chart is not evidence of absence when history is missing.

Evidence entries contain `{id,url,label,excerpt?}`. Optional `excerpt` is already-sanitized inspected source text. Include only excerpts necessary to support a finding. Do not copy raw caches, identity emails, secrets, Git mirrors or arbitrary attachments into the app. The application makes no network fetches. Links open original source pages under the viewer's existing access; an offline export cannot grant repository access.

The scaffold verifies the approval seal against the presentation, facts, source manifest, research plan and ledger when present, and the inspection input digest. The digest covers the read log, candidate files, calculations and local files cited in the log. For older seals without this digest, the scaffold reruns the validation checks. Renew editorial inspection before resealing an older run.

```sh
python3 <skill>/scripts/validate_analysis.py --run <run> --presentation <run>/analysis/presentation.json --seal
python3 <skill>/scripts/create_presentation.py \
  --data <run>/analysis/presentation.json \
  --decisions <run>/analysis/inspection/decisions.json \
  --run <run> --output <run>/presentation
```

Existing nonempty output is not overwritten. Resume UI, CSS, diagram and artwork changes in the copied app while leaving approved `src/data.json` unchanged. To revise research data, update the analysis, rerun the inspector and `validate_analysis.py --seal`, then scaffold a **fresh output directory** using the new decisions. Carry over reviewed UI customizations separately; do not edit the provenance hash to bypass inspection.

## Build and export

Inside the generated presentation folder:

```sh
npm ci
npm run build
```

`npm run check`, `dev`, `build` and `preview` verify `src/data.json` against `research-provenance.json` before their respective operations. A stale or missing seal fails before Vite can write a new `dist/`. The exporter independently rechecks the seal when invoked directly and again before writing output. UI/art edits remain permitted without research-data changes.

`npm run build` verifies the seal, type-checks, builds the static `dist/` site, and bundles `year-in-review.html`. `npm run export` repeats that full build so stale CSS cannot silently enter the export. The standalone exporter bundles React, icons and data with compiled CSS. It has no CDN, web-font or API dependency. Its CSP disables outgoing data connections and form submissions. Story Markdown downloads are created locally with Blob URLs.

Keep the complete `dist/` folder for static hosting; the standalone HTML is a separate file. The generated `dist/export-manifest.json` records file size, hash and story counts. Neither building nor exporting authorizes publishing; ask for a destination/audience only if the user requests hosting, and then follow that host's workflow. Preserve the existing audience on updates.

## Verification and handoff

Run `npm test` for the approval guard, then TypeScript and production builds. The guard fixtures verify that data modified after scaffolding cannot reach build/export output and that errors do not echo the modified payload. Inspect desktop and narrow-screen layouts using available browser tooling. Check default team selection, every individual filter, month/repository/search filters, positive/empty results, actual evidence links, optional source excerpts, dynamic chapter navigation, Escape and focus restoration, and Markdown downloads. Read any browser/preview instructions before testing. Avoid running source-repository build scripts as part of this retrospective.

Verify the standalone file has embedded runtime/data/CSS, no remote asset dependencies, safe inline script/style termination, and correct copied approval hashes. If browser file navigation is blocked, report that direct-file preview limitation and use byte/runtime checks; do not bypass browser policy by rehosting the blocked file. A separately developed local web preview remains appropriate for the app.

Return links to the standalone HTML, static/source folder and research coverage/recaps. Report build and browser verification accurately. Retain the source-based stage and limitations in the final presentation.

The retained package-lock.json is included in every scaffold. Use npm ci for the tested transitive dependency set. A clean installation and production export were verified independently of the original yearbook workspace.

## Mode-specific presentation effort

Every mode keeps the same stack, vertical timeline, team/person filters, evidence access, chart alternatives, responsiveness, privacy and offline HTML. Low reuses established layouts/palettes with concise personal content; Medium adds selected bespoke diagrams and chapter arrangements; High permits broader evidence-led visual composition. No mode uses filler, interchangeable names/counts, or a mandatory number of chapters. Deep research does not require a longer final Wrapped. New mode-aware seals additionally bind research-plan.json and research-ledger.jsonl; stale research usage must be reinspected before scaffolding.
