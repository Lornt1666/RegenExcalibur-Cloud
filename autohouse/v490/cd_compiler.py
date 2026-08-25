"""AutoHouse Ω v490 construction-document manifest compiler.

Zero third-party runtime dependencies. This is the coordination nucleus that turns a
canonical project payload into the drawing/calculation/review registers used by the
free BIM/render/solver adapters.
"""

from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
TRADE_MANIFEST = HERE / "trade_manifest.json"


class CompileError(ValueError):
    pass


@dataclass(frozen=True)
class CompileReceipt:
    project_id: str
    state: str
    manifest_digest: str
    output_dir: str


def _sha(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def load_trade_manifest() -> dict[str, Any]:
    return json.loads(TRADE_MANIFEST.read_text(encoding="utf-8"))


def validate_project(project: dict[str, Any]) -> list[dict[str, str]]:
    unresolved: list[dict[str, str]] = []
    required = [
        ("project_id", "Project identifier"),
        ("name", "Project name"),
        ("jurisdiction.country", "Country"),
        ("jurisdiction.province_state", "Province/state"),
        ("jurisdiction.municipality", "Municipality / AHJ"),
        ("site.civic_address", "Civic address"),
        ("building.use", "Building use / occupancy"),
        ("building.storeys", "Storey count"),
        ("building.units", "Unit count"),
    ]

    def get(path: str):
        node: Any = project
        for part in path.split("."):
            if not isinstance(node, dict) or part not in node:
                return None
            node = node[part]
        return node

    for path, description in required:
        if get(path) in (None, "", []):
            unresolved.append({
                "code": f"REQ:{path}",
                "discipline": "G",
                "description": description,
                "state": "UNRESOLVED",
            })

    # Project-specific external inputs that must never be silently fabricated.
    external = project.get("external_inputs", {})
    for key, description, discipline in [
        ("survey", "Current legal/site survey or accepted site basis", "C"),
        ("geotechnical", "Geotechnical/foundation design basis", "GTE"),
        ("utility_information", "Utility/service information", "C"),
        ("ahj_requirements", "Municipality/AHJ submission requirements", "G"),
    ]:
        state = external.get(key, {}).get("state", "UNRESOLVED")
        if state in {"UNRESOLVED", "PROFESSIONAL_HOLD", "AUTHORITY_HOLD", "TESTING_HOLD"}:
            unresolved.append({
                "code": f"EXT:{key}",
                "discipline": discipline,
                "description": description,
                "state": state,
            })

    return unresolved


def compile_project(project: dict[str, Any], output_dir: str | Path) -> CompileReceipt:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    manifest = load_trade_manifest()
    unresolved = validate_project(project)

    disciplines = project.get("disciplines") or list(manifest["disciplines"].keys())
    invalid = sorted(set(disciplines) - set(manifest["disciplines"]))
    if invalid:
        raise CompileError(f"Unknown disciplines: {invalid}")

    sheet_rows: list[dict[str, str]] = []
    calc_plan: list[dict[str, Any]] = []
    professional_matrix: list[dict[str, str]] = []

    professional_disciplines = set(project.get("professional_disciplines", ["S", "M", "P", "E", "EN", "C"]))

    for code in disciplines:
        entry = manifest["disciplines"][code]
        for sheet in entry.get("sheets", []):
            number, _, title = sheet.partition(" ")
            sheet_rows.append({"discipline": code, "sheet_number": number, "sheet_title": title})
        if entry.get("required_analyses"):
            calc_plan.append({
                "discipline": code,
                "analyses": entry["required_analyses"],
                "state": "PLANNED",
            })
        professional_matrix.append({
            "discipline": code,
            "discipline_name": entry["name"],
            "professional_authentication": "REQUIRED_AS_APPLICABLE" if code in professional_disciplines else "PROJECT_SPECIFIC",
            "software_state": "NOT_ANALYZED_YET",
            "external_state": "NOT_BOUND",
        })

    project_digest = _sha(project)
    compiled_manifest = {
        "schema": "AUTOHOUSE_V490_COMPILED_CD_MANIFEST",
        "project_id": project.get("project_id", "UNRESOLVED"),
        "project_name": project.get("name", "UNRESOLVED"),
        "project_digest": project_digest,
        "disciplines": disciplines,
        "sheet_count": len(sheet_rows),
        "calculation_packages": calc_plan,
        "unresolved_count": len(unresolved),
        "release_state": "BRIEF_INGESTED" if unresolved else "SITE_AND_AUTHORITY_BOUND",
        "truth_boundary": "No professional seal, signature, permit or AHJ approval is created by compilation.",
    }
    compiled_manifest["manifest_digest"] = _sha(compiled_manifest)

    (output / "cd_manifest.json").write_text(json.dumps(compiled_manifest, indent=2), encoding="utf-8")
    (output / "calculation_plan.json").write_text(json.dumps(calc_plan, indent=2), encoding="utf-8")
    (output / "unresolved_register.json").write_text(json.dumps(unresolved, indent=2), encoding="utf-8")

    with (output / "sheet_index.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["discipline", "sheet_number", "sheet_title"])
        writer.writeheader()
        writer.writerows(sheet_rows)

    with (output / "professional_review_matrix.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["discipline", "discipline_name", "professional_authentication", "software_state", "external_state"],
        )
        writer.writeheader()
        writer.writerows(professional_matrix)

    return CompileReceipt(
        project_id=compiled_manifest["project_id"],
        state=compiled_manifest["release_state"],
        manifest_digest=compiled_manifest["manifest_digest"],
        output_dir=str(output),
    )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Compile an AutoHouse Ω v490 CD manifest")
    parser.add_argument("project_json", type=Path)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()
    receipt = compile_project(json.loads(args.project_json.read_text(encoding="utf-8")), args.output_dir)
    print(json.dumps(receipt.__dict__, indent=2))
