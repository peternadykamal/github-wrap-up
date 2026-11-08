# Resolve models for the chosen mode

Read after choosing depth and before dispatching research. Low/Medium/High is the only user-facing control. Each mode selects work allowances, model capability and effort intent together. Preserve an explicit user model constraint; if incompatible with the selected mode, explain the tradeoff rather than silently replacing it. The root conversation always retains harness-selected settings. Read [harnesses.md](harnesses.md) for native dispatch and fallbacks.

| Role | Low | Medium | High |
|---|---|---|---|
| Researcher | Efficient; economical reasoning | Balanced; moderate reasoning | Balanced or deep; deep reasoning |
| Person coordinator, when applicable | Unused | Balanced, then deep; deep reasoning | Deep; deep reasoning |
| Independent challenge | Unused | Deep, then balanced; deep reasoning, only for material uncertainty | Deep; deep reasoning |
| Root inspector | Inherited | Inherited | Inherited |

Classes describe suitability for this research, not vendor model names. “Efficient” requires evidence for economical tool-based extraction and narrow source reading; “balanced” for reliable implementation/discussion synthesis; “deep” for complex attribution and alternative interpretations. These classes are assessments, not built-in runtime facts. Effort intents are mapped to supported values separately for each model. Do not infer capabilities, supported effort, cost or quality from a model ID, suffix, release date or availability alone. This is relative workload policy, not a guarantee that every High run bills more than every Medium run.

## Capture current capabilities

Use the actual model/agent discovery interface, or the currently exposed agent tool metadata. Record the models this runtime can dispatch, their supported reasoning settings, tool support and override/context controls. A public API model listing does not establish availability in the current harness, task suitability, effort support or pricing. No model API key is required by the helpers; the harness manages its own model access. Do not read authentication stores or scrape hidden app settings to discover models.

Write `analysis/runtime-models.json` with **schemaVersion 2**, capturedAt (UTC), source `{kind: "tool-metadata" | "runtime-discovery", identifier}`, controls `{modelOverride: boolean, effortOverride: boolean, freshContextRequired: boolean}`, optional parent `{agentId, confirmedByRuntime, modelId, effort}`, and models `[{id, available: boolean, toolCalling: boolean, supportedEfforts: [string], effortValues?: {label: nativeJsonValue}}]`. Effort labels come from the host; numeric/structured controls can use descriptive accounting labels with their exact native values in effortValues. No mapping means the label itself is the native value. Preserve actual descriptors for assessment. Capture within 24 hours at resolution; a frozen run can resume later without claiming its catalog is live. Parent settings stay unknown unless the runtime reports them.

Declare `adapter` using actual runtime fields:

```json
{
  "kind": "tool-arguments",
  "interface": "<actual native agent tool>",
  "modelPath": ["<native model field>"],
  "effortPath": ["<native effort field>"],
  "freshContext": {"strategy": "native"},
  "fixedArguments": {}
}
```

Paths are arrays of nested JSON field names. Use kind `agent-configuration` for supported definition-time controls; the helper still returns JSON data and does not write settings. When the tool requires a fresh-context argument, use `freshContext:{strategy:"parameter",path:["<native field>"],value:<native JSON value>}`. Otherwise native means the invoked worker already starts separately. Parameter paths must not overlap each other or fixed fields. If effortOverride is false, omit effortPath; the selected model is still usable, but effort remains null/inherited and the requested effort profile is explicitly unachieved. Model override/discovery failures require disclosed sequential fallback. Version 1 remains readable for already-frozen Codex runs; use version 2 for new runs.

Consult the selected provider/harness's current official model-selection/reasoning documentation and actual runtime descriptions as needed. Fetch the relevant pages; do not merely cite an unvisited URL. Write `analysis/model-assessments.json` with schemaVersion 1 and models containing:

- modelId, selectionClass (`efficient`, `balanced` or `deep`), applicable roles, rationale.
- effortByIntent mapping `economical`, `moderate` and/or `deep` to this model's **advertised** effort values.
- guidance: dated records `{kind:"official-documentation",publisher,url,checkedAt}` or `{kind:"runtime-metadata",identifier,description,checkedAt}`. Verify that a documentation URL belongs to its named publisher; provider-neutral HTTPS validation is not certification of official ownership. Preserve actual descriptors, not an invented recommendation. Establish the relevant capability/cost rationale; documentation for reasoning syntax alone does not prove a model's suitability.
- validation `{status:"guidance-only"}` for a cold start. When representative local evaluations actually exist, use `{status:"validated",evidence:[{path,sha256}]}`. Each run-relative JSON evidence file identifies modelId, passed:true and evaluated roles; retain evaluation cases, outputs, criteria and measured outcomes there so the judgment is auditable. Never fabricate a benchmark to remove the provisional label.

Prefer validated candidates within the policy's preferred capability class, then currently documented recommendations, then runtime order for otherwise equal candidates. A new guidance-only release does not displace a validated peer just because its ID looks newer. Class preference still applies: High's preferred balanced researcher can be guidance-only when its only validated alternative is a deep model. Treat guidance-only choices as provisional and disclose that they are not locally benchmarked. Reuse relevant prior evaluation artifacts by copying and hashing them into the new run, checking that the runtime/model behavior and task still match. Do not automatically benchmark every model: evaluation work also consumes tokens.

## Resolve, freeze and dispatch

```sh
python3 <skill>/scripts/model_policy.py --run <run> resolve
python3 <skill>/scripts/model_policy.py --run <run> launch-spec --role researcher
python3 <skill>/scripts/research_mode.py --run <run> job --subject <person> --job-id <job> --role researcher --repos <owner/repo> --preview
```

Planning resolves automatically if both input files already exist; otherwise it records pending. Resolve before starting child jobs. The preview checks scope/job allowance without spending a job. Use its launch settings with the runtime's agent tool, then register the returned actual agent identifier with the same job arguments and `--agent <actual-id>`. The helper produces a launch specification; it cannot call an agent tool itself. Adapt argument names only to the actual supported tool interface. Respect runtime permissions and user model constraints; the skill is not authorization to acquire paid access or bypass runtime limits.

Apply the returned dispatch envelope to its declared interface: pass `arguments` as the native fields, and add the compact task brief/file paths through the host's normal prompt fields. Do not pass Codex-specific names to other hosts. If overrides need a fresh context, apply the captured native argument/mechanism rather than inheriting history. All launches, including nested workers, use their resolved role binding. Root can schedule them if nested overrides are unavailable. A single-person Low run still uses one efficient worker when supported; root at unknown/different settings cannot be relabeled as that worker. In sequential fallback, root performs the logical job with inherited settings and a visible limitation.

Record requested settings in each job's modelRequest. Only attach `--runtime-reported <json>` when the runtime supplies evidence `{source,modelId?,effort?}`; a launch request or generic successful launch is not confirmation of the effective backend model. Unknown confirmation stays unknown. An observed mismatch stops profile accounting until explained/resolved. An alias may change behind a stable ID: pinning requested IDs and evidence does not promise a physical backend snapshot.

Resolution snapshots live under `analysis/model-selections/<id>/` with hashes in research-plan.json. Resume uses these frozen choices, not a fresh ranking. If a launch fails because a frozen model is unavailable, refresh actual runtime availability, record the failure, and resolve a supported replacement with `resolve --authorization '<concrete runtime availability reason>'`. Never silently replace a profile or repeatedly retry failed launches. New resolution affects new contexts; old jobs retain their original binding. A fresh job ID must have a genuinely distinct actual child agent ID, even after an upgrade. Finish existing jobs to retain their completed records; use their summaries rather than delivering new-profile packets into incompatible active contexts. Reuse evidence files/summaries; do not call an existing context a different model.

Mode upgrades require the existing user authorization and resolve a new profile from current inputs. Refresh stale inputs first. Resume old contexts only when settings still match; otherwise open an allowed new-mode job. Inspection seals bind model profiles and ledger along with content/facts. Changes require renewed validation/sealing.

## Runtime limitations

If model discovery/selection is unavailable, mark unresolved/blocked; never invent a catalog or silently inherit a potentially expensive root. Explain the runtime limitation. An absent effort override alone permits a selected version-2 model with effortControl:inherited, effort:null and a disclosure; this retains real worker independence. A disclosed sequential fallback can continue with the current conversation using `plan --execution sequential-fallback` and the actual runtime reason. It retains selected depth/evidence standards, but child model/effort and relative cost savings are **not achieved**; independent challenge is also unavailable. Do not describe this as measured Low token consumption. Runtime override support can exist even if model discovery is unavailable; both must be established.

Old archives can keep legacy settings unknown rather than retrospectively inventing requests. Current runs register every new job. Reports distinguish frozen selections, requested settings, runtime-reported settings, inherited fallback, provisional assessment and measured token usage. No extra user-facing model/effort knob or hardcoded model ID belongs in this skill.
