import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from permit_release_engine_v450 import evaluate_dict

RESP = {
    "licensing_documentation_accountable_party": "HOMEBUILDER",
    "owner_statutory_safety_codes_responsibility": "OWNER",
    "professional_authentication_party": "LICENSED_PROFESSIONAL",
    "ahj_authority_party": "AHJ",
}

BASE = {
    "mode": "SYNTHETIC",
    "synthetic": True,
    "responsibility": RESP,
    "jurisdiction_bound": True,
    "ahj_name": "SYNTHETIC TEST AHJ",
    "governing_codes": {"building": "NBC 2023 Alberta Edition"},
    "legal_site_evidence": True,
    "site_plan_evidence": True,
    "homebuilder_assigned": True,
    "development_permit_status": "ISSUED",
    "builder_licence_valid": True,
    "new_home_warranty_required": False,
    "professional_involvement_required": True,
    "professional_scope_matrix_complete": True,
    "crp_required": False,
    "required_rpr_disciplines": ["structural"],
    "schedule_B": {"structural": True},
    "engineering_firms": [{"name": "Synthetic Engineering", "corporate_practice_required": True, "permit_to_practice_valid": True}],
    "survey_required": True,
    "survey_professional_evidence_valid": True,
    "site_geometry_matches_survey": True,
    "geotech_required": True,
    "geotech": {"authenticated_report": True, "site_applicable": True, "bearing_basis": True, "sulphate_basis": True, "groundwater_basis": True, "foundation_recommendations": True},
    "critical_products": [{"name": "synthetic beam", "identity_traceable": True, "installation_manual_current": True, "scope_match": True, "code_path": "CCMC", "ccmc_active": True, "jurisdiction_acceptance_required": False}],
    "alternative_solutions": [],
    "permit_submission_documents_complete": True,
    "coordinate_consistency_pass": True,
    "professional_authentication_complete": True,
    "permit_submitted": True,
    "required_permits": {"building": "ISSUED"},
    "building_permit_authority_receipt": {"issuer_class": "AHJ", "identifier": "SYN-BP", "document_digest": "sha256:synthetic", "verified_against_primary_source": True, "verified_by_human": True, "non_synthetic": False},
    "approved_plan_digest_bound": True,
    "permit_conditions_acknowledged": True,
    "site_conditions_reconciled": True,
    "no_open_critical_design_holds": True,
    "homebuilder_preconstruction_review_complete": True,
    "construction_release_authority_receipt": {"issuer_class": "AHJ", "identifier": "SYN-REL", "document_digest": "sha256:synthetic", "verified_against_primary_source": True, "verified_by_human": True, "non_synthetic": False},
    "homebuilder_internal_release_signed": True,
    "no_stop_work_or_authority_hold": True,
}


def check(name, condition):
    if not condition:
        raise AssertionError(name)
    print(f"PASS {name}")


def main():
    r = evaluate_dict(BASE)
    check("synthetic receipt cannot prove permit", r["level"] == "PERMIT_SUBMITTED")

    x = copy.deepcopy(BASE)
    x["responsibility"]["owner_statutory_safety_codes_responsibility"] = "HOMEBUILDER"
    check("owner duty cannot transfer", evaluate_dict(x)["level"] == "SCHEMATIC")

    x = copy.deepcopy(BASE)
    x["responsibility"]["professional_authentication_party"] = "REGENEXCALIBUR"
    check("AI/company cannot self-authenticate professional work", evaluate_dict(x)["level"] == "SCHEMATIC")

    x = copy.deepcopy(BASE)
    x["geotech"]["bearing_basis"] = False
    check("geotechnical bearing basis is a hard gate", evaluate_dict(x)["level"] == "SCHEMATIC")

    x = copy.deepcopy(BASE)
    x["schedule_B"]["structural"] = False
    check("required Schedule B is a hard gate", evaluate_dict(x)["level"] == "SCHEMATIC")

    x = copy.deepcopy(BASE)
    x["critical_products"][0]["scope_match"] = False
    check("manufacturer evidence scope must match", evaluate_dict(x)["level"] == "SCHEMATIC")

    x = copy.deepcopy(BASE)
    x["synthetic"] = False
    x["mode"] = "LIVE"
    x["building_permit_authority_receipt"]["non_synthetic"] = True
    x["construction_release_authority_receipt"] = {}
    check("real permit supports release-feasible, not authorized", evaluate_dict(x)["level"] == "CONSTRUCTION_RELEASE_FEASIBLE")

    x["construction_release_authority_receipt"] = {"issuer_class": "AHJ", "identifier": "EXT-REL", "document_digest": "sha256:external", "verified_against_primary_source": True, "verified_by_human": True, "non_synthetic": True}
    check("real external authority plus builder signoff can authorize release", evaluate_dict(x)["level"] == "CONSTRUCTION_RELEASE_AUTHORIZED")

    print("AUTOHOUSE_V450_SELFTEST_PASS")


if __name__ == "__main__":
    main()
