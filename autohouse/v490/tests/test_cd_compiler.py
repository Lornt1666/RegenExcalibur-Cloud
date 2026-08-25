import json
from pathlib import Path

from autohouse.v490.cd_compiler import compile_project, load_trade_manifest


def test_manifest_contains_core_disciplines():
    manifest = load_trade_manifest()
    required = {"G", "C", "A", "S", "GTE", "EN", "M", "P", "GAS", "E", "FP", "DD", "SP"}
    assert required.issubset(set(manifest["disciplines"]))


def test_missing_site_evidence_is_not_silently_defaulted(tmp_path: Path):
    project = {
        "project_id": "TEST-001",
        "name": "Synthetic House",
        "jurisdiction": {"country": "Canada", "province_state": "Alberta", "municipality": "Test Municipality"},
        "site": {"civic_address": "1 Test Street"},
        "building": {"use": "single detached dwelling", "storeys": 2, "units": 1},
        "external_inputs": {},
    }
    receipt = compile_project(project, tmp_path)
    assert receipt.state == "BRIEF_INGESTED"
    unresolved = json.loads((tmp_path / "unresolved_register.json").read_text())
    codes = {x["code"] for x in unresolved}
    assert "EXT:survey" in codes
    assert "EXT:geotechnical" in codes
    assert "EXT:ahj_requirements" in codes


def test_complete_external_basis_advances_site_authority_state(tmp_path: Path):
    project = {
        "project_id": "TEST-002",
        "name": "Synthetic House",
        "jurisdiction": {"country": "Canada", "province_state": "Alberta", "municipality": "Test Municipality"},
        "site": {"civic_address": "2 Test Street"},
        "building": {"use": "single detached dwelling", "storeys": 2, "units": 1},
        "external_inputs": {
            "survey": {"state": "RESOLVED"},
            "geotechnical": {"state": "RESOLVED"},
            "utility_information": {"state": "RESOLVED"},
            "ahj_requirements": {"state": "RESOLVED"},
        },
    }
    receipt = compile_project(project, tmp_path)
    assert receipt.state == "SITE_AND_AUTHORITY_BOUND"
    sheet_index = (tmp_path / "sheet_index.csv").read_text()
    assert "S000" in sheet_index
    assert "M000" in sheet_index
    assert "P000" in sheet_index
    assert "E000" in sheet_index
