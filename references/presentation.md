# Reviewed evidence to a portable yearbook

Read this only after the inspector has finished the content. Do not start frontend work during scraping or candidate generation. The retained starter is `assets/frontend/`; do not modify it for an individual run. It contains no real identities, company branding, site IDs or research data.

## Fixed stack and visual structure

Use React 19, TypeScript, Tailwind CSS 4, Vite 8, Recharts 3 and lucide-react. Scoped CSS and ordinary SVG supply custom editorial compositions and diagrams. The portable Vite build preserves the React/TypeScript structure of the original yearbook while making an entirely static site and standalone HTML possible without server authentication or hosting plugins. Use this stack consistently; dependency versions in the starter are a tested baseline, not an instruction to upgrade the user's unrelated projects.

Keep the cream/lime editorial introduction, sticky top person filters with **Whole team selected by default**, vertical month-grouped timeline, evidence drawer, activity view and method/coverage view. Use initials rather than remote avatar dependencies. Timeline filters affect milestones; full-year totals and charts retain explicit reporting-scope labels.

The starter provides dynamic Wrapped layouts (`cover`, `journey`, `contrast`, `map`, `ledger`, `spotlight`, `finale`) and several palettes. They are a vocabulary, not a mandated slide sequence. Change the copied app's visual composition when the reviewed story benefits; keep the stack. Each person's story should have its own evidence-led thesis, meaningful chapter selection, layout rhythm and visual motif. Do not fill a fixed slide quota, assign personalities or recycle one story with new names/counts. The starter's orbit artwork is a neutral starting point, not sufficient final customization for every person. Adapt it using the particular architecture, lifecycle, dependency chain or other inspected structure found in that person's work.

Use Recharts for accessible quantitative comparisons with explicit units and counting rules. Use SVG diagrams when relationships or states explain the work more clearly than a chart. A chart's data must come from approved facts or a reproducible calculation; never invent data to complete a composition. Supply a table/text alternative and respect reduced-motion preferences. No user-provided repository HTML is rendered.

## Data and approval boundary

The exact rendering contract is `assets/frontend/src/types.ts`. The analysis inspector may add provenance fields beyond these display types. Required envelope:

- `meta`: title, inclusive start, exclusive end, declared timezone, snapshot time, coverage notes, optional approved totals per canonical person ID and `team`.
- `people`: canonical IDs, display names, headline and color.
- `timeline`: source-linked milestones, people, repository, date, stage and caveat. Stage vocabulary is `implemented`, `design`, `merged`, `released`, `unknown`. A merge is not a release.
- `stories`: one `team` story and each selected person's distinct story, with a variable number of chapters. Metrics require a counting basis. Beats and chapters reference source evidence.
- `activity`: daily `{date,personId,commits,prs,reviews}` rows. `date` is the declared timezone's `YYYY-MM-DD`. Include independently SHA-deduplicated `personId: "team"` rows. Never sum contributor commit counts to reconstruct team totals: co-authorship/mirrors can duplicate them.
- `coverage`: summary and limitations, including partial collection or a deliberately empty period. An empty chart is not evidence of absence when history is missing.

Evidence entries contain `{id,url,label,excerpt?}`. Optional `excerpt` is already-sanitized inspected source text. Include only excerpts necessary to support a finding. Do not copy raw caches, identity emails, secrets, Git mirrors or arbitrary attachments into the app. The application makes no network fetches. Links open original source pages under the viewer's existing access; an offline export cannot grant repository access.

The scaffold requires an approval seal with `status: "approved"`, `presentationSha256`, `factsSha256` and `sourceManifestSha256`. Each hash binds exact file bytes. `create_presentation.py` rechecks the presentation, facts and source manifest so an old approval cannot authorize changed inputs. The seal records an inspector decision; it is not a substitute for the inspection.

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

`npm run build` verifies the seal, type-checks, builds the static `dist/` site, and bundles `year-in-review.html`. `npm run export` repeats that full build so stale CSS cannot silently enter the export. Vite compiles Tailwind through PostCSS. The standalone exporter bundles React, Recharts, icons and data into an inline IIFE and includes compiled CSS. It has no CDN, web-font or API dependency. Its CSP disables outgoing data connections and form submissions. Story Markdown downloads are created locally with Blob URLs.

Keep the complete `dist/` folder for static hosting; the standalone HTML is a separate file. The generated `dist/export-manifest.json` records file size, hash and story counts. Neither building nor exporting authorizes publishing; ask for a destination/audience only if the user requests hosting, and then follow that host's workflow. Preserve the existing audience on updates.

## Verification and handoff

Run `npm test` for the approval guard, then TypeScript and production builds. The guard fixtures verify that data modified after scaffolding cannot reach build/export output and that errors do not echo the modified payload. Inspect desktop and narrow-screen layouts using available browser tooling. Check default team selection, every individual filter, month/repository/search filters, positive/empty results, actual evidence links, optional source excerpts, dynamic chapter navigation, Escape and focus restoration, and Markdown downloads. Read any browser/preview instructions before testing. Avoid running source-repository build scripts as part of this retrospective.

Verify the standalone file has embedded runtime/data/CSS, no remote asset dependencies, safe inline script/style termination, and correct copied approval hashes. If browser file navigation is blocked, report that direct-file preview limitation and use byte/runtime checks; do not bypass browser policy by rehosting the blocked file. A separately developed local web preview remains appropriate for the app.

Return links to the standalone HTML, static/source folder and research coverage/recaps. Report build and browser verification accurately. Retain the source-based stage and limitations in the final presentation.

The retained package-lock.json is included in every scaffold. Use npm ci for the tested transitive dependency set. A clean installation and production export were verified independently of the original yearbook workspace.

## Mode-specific presentation effort

Every mode keeps the same stack, vertical timeline, team/person filters, evidence access, chart alternatives, responsiveness, privacy and offline HTML. Low reuses established layouts/palettes with concise personal content; Medium adds selected bespoke diagrams and chapter arrangements; High permits broader evidence-led visual composition. No mode uses filler, interchangeable names/counts, or a mandatory number of chapters. Deep research does not require a longer final Wrapped. New mode-aware seals additionally bind research-plan.json and research-ledger.jsonl; stale research usage must be reinspected before scaffolding.
