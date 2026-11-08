# Research depth and token-aware execution

Read before model-facing research. The invoking prompt selects low, medium or high (case-insensitive; med/meduim normalize to medium). Default Medium for a new run without asking; an unspecified mode on resume preserves the existing choice. Each mode also resolves suitable model capability and supported reasoning effort; read [model-selection.md](model-selection.md) before dispatch. The root retains harness-selected settings. A mode is a work allowance, never a claim about exact token billing or a quality score.

| Per person | Low | Medium (default) | High |
| Researcher profile | Efficient / economical effort | Balanced / moderate effort | Balanced or deep / deep effort |
|---|---:|---:|---:|
| Initial substantive evidence packets | 24 | 80 | 240 |
| Follow-up rounds | 1 | 2 | 3 |
| Additional packets per follow-up round | 6 | 20 | 60 |
| Researcher contexts | 1, no repo children | Up to 3 repository batches | One per relevant repository |
| Person coordinator (multiple people) | None | Up to 1 | Up to 1 |
| Inspector | Combined factual/editorial | Separate factual and editorial | Separate factual/editorial plus independent challenge |
| Optional independent challenge | No | Material uncertainty only | Required |
| Presentation effort | Reuse personalized layouts | Selected custom diagrams | Broader bespoke composition where useful |

These are ceilings, not quotas. Do less for a sparse record. Each packet is at most 12,000 JSON characters; a huge PR is split across packets. Each returned job summary is at most 10,000 characters. There are at most two bounded metadata-brief deliveries per subject. The shared root/team allowance is 12/32/64 initial packets in Low/Medium/High, with 3/8/16 packets per allowed follow-up round. It covers synthesis and inspection; it is not multiplied by team size.

## What remains identical

Collect the same accessible archive in all modes; calculations remain exhaustive over recovered records. Keep identity resolution, role separation, SHA deduplication, timezone rules, source-backed claims, privacy, honest gaps, monthly/weekly indexes, core UI, exports and all automated correctness checks. Low omits or qualifies underinvestigated claims rather than lowering evidence standards. No forced badges, rankings, jokes, insight categories or slide counts.

Low starts from scripted month/repo/role summaries and reads representative changes supporting the strongest milestones. Medium follows selected threads through implementation, tests, integration and corrections and connects repositories. High investigates important threads more extensively, including ambiguity and alternatives. Each run still discovers its own story.

The complete weekly record stays on disk in all modes. Low can produce metadata-based weekly summaries clearly labeled as such, with source-inspected narrative reserved for selected weeks. Do not invent delivered features from uninspected messages. Medium/High deepen relevant weeks, rather than repeatedly reading every generated file.

## Workflow

1. After facts generation, create the selected plan. Keep mode out of collector config: changes in depth do not recollect GitHub or invalidate the raw cache.

```sh
python3 <skill>/scripts/research_mode.py --run <run> plan --mode medium
```

If usable agents or model discovery/selection are unavailable, choose `--execution sequential-fallback --reason '<actual runtime limitation>'` and report that child model/effort profiles and their relative cost savings are not achieved. A model-only harness can instead use selected workers with inherited/unknown effort; disclose that the effort profile was not achieved. Switching only execution strategy records the runtime reason; it does not authorize an increase in depth. For multiple people, coordinate one at a time/in bounded waves so workers can run.

2. Register every fresh model research context before delivering evidence. Low has one efficient researcher per person, including a single-person run, no person coordinator or repository subagents. Medium uses bounded batches and High single-repository researchers. Reuse existing agent contexts for follow-up rather than spawning duplicates. The root inspector is a shared team job. Use the actual agent identifier, not a generic placeholder, in real runs.

```sh
python3 <skill>/scripts/research_mode.py --run <run> job --subject <person> --job-id <job> --role researcher --agent <agent> --repos <owner/repo>
python3 <skill>/scripts/research_mode.py --run <run> brief --subject <person> --job-id <job>
python3 <skill>/scripts/research_mode.py --run <run> packet --subject <person> --job-id <job> --bundle-id <unique-reading> --sources '<source-id>' --level diff
```

Briefs contain full totals, bounded monthly facts and representative metadata leads selected across month/repo/role groups. They disclose clipped groups/inventory. Never load entire facts.sourceIndex, raw records or every patch into an agent context. Use scripts to locate IDs and request focused packets. All repositories/months retain recorded activity and coverage, even when the reading allowance cannot cover them substantively.

Packets deliver selected source excerpts, not a declaration that an agent inspected them. After reading, write observations to the normal read log with returned budgetEntryId, sourceId, actual agent and inspection level. Source metadata cannot be relabeled as diff inspection. Re-reading in another context requires another delivery/unique bundle ID and consumes the recipient's allowance. Source-file paths must remain inside the run; historical excerpts can use `--file <run-relative-file>` with one source ID. Do not execute studied code.

After returning a summary, resume the same actual agent context for a follow-up; this does not register a replacement researcher:

```sh
python3 <skill>/scripts/research_mode.py --run <run> resume --job-id <job> --round 1 --reason '<inspection follow-up>'
python3 <skill>/scripts/research_mode.py --run <run> packet --subject <person> --job-id <job> --bundle-id <new-reading> --sources '<source-id>' --level diff --round 1
```

Finish the job again after the follow-up. Use rounds 2/3 only where allowed. A packet round must match the active context's registered round. After an authorized upgrade, an existing context with matching model/effort may resume at round 0 to use the higher remaining initial allowance. A changed profile needs an allowed new context, preserving earlier jobs and packet usage. If the runtime cannot resume that actual agent, use the root inspector's bounded shared context or qualify the claim; do not disguise a fresh researcher as a resumed context.

 The allowance applies to all reads in that round, not an unlimited budget per candidate. If it is exhausted, qualify/omit unsupported claims or request an explicit user-authorized upgrade. Do not silently upgrade, create a second run to reset accounting, or hide repeated reads outside the ledger.

3. Finish jobs with a concise returned summary file. Full research artifacts remain on disk; do not paste them into every parent context.

```sh
python3 <skill>/scripts/research_mode.py --run <run> finish --job-id <job> --summary-file <concise-return.md>
```

The root inspector job uses subject team/role inspector. A challenge job uses team/role challenge, with `--reason` required for Medium. High with agents requires a completed challenge context whose actual registered agent differs from all research/coordinator/inspector agents. Free-form reviewer display names do not establish independence. Without agents, High performs a distinct challenge pass and discloses that it was not independent. No hidden additional review agents in Low.

## Inspection and approval

Keep factCheck and editorialCheck passed in every mode. Add substantive `reviewPasses` to decisions.json:

- Low: `{type:"combined",status:"passed",reviewer,notes}` covers both criteria.
- Medium: separate factual and editorial entries; they may be performed by the root in separate passes. Optional challenge requires material uncertainty and a registered separate reviewer.
- High: factual, editorial and challenge entries. With agents, challenge reviewer must match a completed independent registered job. Root adjudicates the findings.

Complete all registered jobs before sealing. validate_analysis checks allowances, packets, reader attribution and required passes, then binds the exact plan/ledger hashes alongside the existing evidence/content hashes. Changing mode or usage invalidates a previous seal; reinspect and reseal. Old already-approved archives without mode accounting remain explicitly legacy-unmetered; do not invent prior token usage. New content must use a plan.

## Upgrade and reuse

```sh
python3 <skill>/scripts/research_mode.py --run <run> plan --mode high --authorization '<actual user request to deepen this run>'
```

Reuse the archive, facts, accepted evidence and existing summaries. Packet usage carries over: 24 initial Low packets leave at most 56 of Medium's 80. Old jobs retain their original mode; new jobs obey the new mode's limits. Do not rerun completed work simply to fill the new budget. Once higher-mode work is spent, the planner refuses to relabel it as Low. Changes to underlying scope/evidence require a new frozen research run, not an accounting reset disguised as a mode change.

## Actual token consumption

```sh
python3 <skill>/scripts/research_mode.py --run <run> report
python3 <skill>/scripts/research_mode.py --run <run> tokens --measurement-id <runtime-call-id> --input <measured-count> --output <measured-count> --source '<runtime usage source>'
```

Record per-call usage only when the runtime exposes it; cached input is an optional subset. No whole-account usage percentages or guessed character-to-token conversions. No measurements means actualTokens:null. Measured totals cover only recorded calls, not necessarily reasoning/orchestration/presentation/uncaptured contexts or a whole run. Do not claim a hard backend token cap: helpers enforce registered work units and declared context sizes, not all model consumption. Collect real usage from representative runs before publishing expected token ranges for each mode.

Capture available research token measurements before sealing. A later usage measurement changes the research ledger and therefore requires a renewed seal before scaffolding. If usage only becomes available after approval/export, retain it in a separate clearly labeled final runtime report instead of silently changing the sealed research ledger. Do not imply that the frozen research ledger includes later presentation work or the final assistant response.
