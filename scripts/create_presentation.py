#!/usr/bin/env python3
"""Copy the portable presentation only after inspection seals its exact inputs."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys

import model_policy


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def create(data_path: Path, decisions_path: Path, output: Path, run: Path | None = None) -> dict:
    data_path, decisions_path, output = data_path.resolve(), decisions_path.resolve(), output.resolve()
    run = run.resolve() if run else data_path.parent.parent if data_path.parent.name == "analysis" else None
    if run is None:
        raise ValueError("Specify --run unless data is located at <run>/analysis/presentation.json.")
    decisions = json.loads(decisions_path.read_text())
    if decisions.get("status") != "approved":
        raise ValueError("Inspector decisions are not approved. Complete the analysis gate first.")
    bound = [
        ("presentationSha256", data_path),
        ("factsSha256", run / "analysis/facts.json"),
        ("sourceManifestSha256", run / "manifest.json"),
    ]
    mode_keys = {"researchPlanSha256", "researchLedgerSha256"}
    if mode_keys & decisions.keys():
        if not mode_keys <= decisions.keys():
            raise ValueError("Incomplete research-mode approval seal.")
        bound += [("researchPlanSha256", run / "analysis/research-plan.json"),
                  ("researchLedgerSha256", run / "analysis/research-ledger.jsonl")]
    for key, path in bound:
        if not path.is_file() or decisions.get(key) != digest(path):
            raise ValueError(f"Inspection seal is missing or stale for {key}. Revalidate the research.")
    plan = json.loads((run / "analysis/research-plan.json").read_text()) if "researchPlanSha256" in decisions else {}
    for resolution in model_policy.all_resolutions(plan).values():
        model_policy.validate_resolution(run, resolution)
    data = json.loads(data_path.read_text())
    if not all(key in data for key in ["meta", "people", "timeline", "stories", "activity", "coverage"]):
        raise ValueError("Presentation does not satisfy the required data envelope.")
    if not data["people"] or not data["stories"]:
        raise ValueError("Presentation needs reviewed people and stories, including a team story.")
    if not any(s.get("personId") == "team" for s in data["stories"]):
        raise ValueError("Presentation needs an inspector-approved team story for its default view.")
    template = Path(__file__).resolve().parent.parent / "assets/frontend"
    if output == template or template in output.parents:
        raise ValueError("Output cannot be inside the skill's retained presentation starter.")
    if output.exists() and any(output.iterdir()):
        raise ValueError("Output must be a new or empty directory; existing work is not overwritten.")
    output.mkdir(parents=True, exist_ok=True)
    shutil.copytree(template, output, dirs_exist_ok=True, ignore=shutil.ignore_patterns("node_modules", "dist", "year-in-review.html"))
    (output / "src/data.json").write_bytes(data_path.read_bytes())
    provenance = {key: decisions[key] for key, _ in bound}
    provenance.update({"schemaVersion": 1, "status": "inspector-approved", "rawSourceIncluded": False, "researchMode": decisions.get("researchMode", "legacy-unmetered")})
    if plan.get("modelSelection"):
        selection = plan["modelSelection"]
        provenance["modelProfiles"] = {"status": selection["status"], "executionMode": plan["executionMode"],
            "executionReasonRecorded": bool(plan.get("executionReason")),
            "reviewIndependence": "unavailable in sequential fallback" if plan["executionMode"] == "sequential-fallback" else "requires distinct completed registered agents",
            "disclosures": selection.get("disclosures", []),
            "requestedRoles": {role: {key: value.get(key) for key in ["status", "modelId", "effort", "effortControl", "basis", "provisional", "runtimeConfirmed"]}
                               for role, value in selection.get("roles", {}).items()},
            "note": "Requested profiles; effective settings require separate runtime confirmation. Sequential fallback inherits root settings."}
    (output / "research-provenance.json").write_text(json.dumps(provenance, indent=2) + "\n")
    return {"output": str(output), "presentationSha256": provenance["presentationSha256"],
            "commands": ["npm ci", "npm run build"], "staticSite": "dist/", "singleHtml": "year-in-review.html"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", required=True, type=Path)
    parser.add_argument("--decisions", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--run", type=Path)
    args = parser.parse_args()
    try:
        result = create(args.data, args.decisions, args.output, args.run)
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
