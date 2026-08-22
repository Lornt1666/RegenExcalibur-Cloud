from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Any, Dict, List

TRUTH = "SCHEMATIC — NOT FOR CONSTRUCTION — UNSEALED — PROFESSIONAL / AHJ REVIEW REQUIRED."

LEVELS = [
    "SCHEMATIC",
    "PERMIT_SUBMISSION_FEASIBLE",
    "PERMIT_SUBMITTED",
    "PERMITS_ISSUED_SCOPE_LIMITED",
    "CONSTRUCTION_RELEASE_FEASIBLE",
    "CONSTRUCTION_RELEASE_AUTHORIZED",
    "OCCUPANCY_READY",
    "OCCUPANCY_AUTHORIZED",
    "AS_BUILT_CLOSEOUT",
]

NON_TRANSFERABLE = {
    "owner_statutory_safety_codes_responsibility": "OWNER",
    "professional_work_product_authentication": "LICENSED_PROFESSIONAL",
    "legal_land_survey_authority": "ALBERTA_LAND_SURVEYOR",
    "permit_variance_inspection_occupancy_authority": "AHJ",
}

@dataclass
class Evaluation:
    level: str
    blockers: List[str]
    holds: List[str]
    warnings: List[str]
    passed_gates: List[str]
    authority_receipts_accepted: List[str]
    truth_boundary: str = TRUTH


def _yes(v: Any) -> bool:
    return v is True or (isinstance(v, str) and v.upper() in {
        "YES", "TRUE", "VALID", "ACTIVE", "ISSUED", "APPROVED",
        "PASS", "PASSED", "ACCEPTED", "COMPLETE", "CLOSED"
    })


def _status(v: Any) -> str:
    return str(v).upper() if v is not None else ""


def _authority_receipt_ok(r: Dict[str, Any], expected_issuer=("AHJ", "SCO")) -> bool:
    return bool(
        r
        and r.get("issuer_class") in expected_issuer
        and r.get("identifier")
        and r.get("document_digest")
        and _yes(r.get("verified_against_primary_source"))
        and _yes(r.get("verified_by_human"))
        and _yes(r.get("non_synthetic"))
    )


def evaluate(project: Dict[str, Any]) -> Evaluation:
    b: List[str] = []
    h: List[str] = []
    w: List[str] = []
    passed: List[str] = []
    accepted: List[str] = []
    mode = _status(project.get("mode", "SCHEMATIC"))
    synthetic = bool(project.get("synthetic", False)) or mode in {"SYNTHETIC", "TEST", "TEST_FIXTURE"}

    resp = project.get("responsibility", {})
    if resp.get("licensing_documentation_accountable_party") != "HOMEBUILDER":
        b.append("R0-001 homebuilder must be the licensing/document-control accountable party under project governance")
    if resp.get("owner_statutory_safety_codes_responsibility") != "OWNER":
        b.append("R0-002 owner statutory Safety Codes responsibility is non-transferable")
    if resp.get("professional_authentication_party") in {"HOMEBUILDER", "REGENEXCALIBUR", "AUTOHOUSE", "AI"}:
        b.append("R0-003 professional authentication cannot be assigned to builder/RegenExcalibur/AI")
    if resp.get("ahj_authority_party") not in (None, "AHJ"):
        b.append("R0-004 permit/variance/inspection/occupancy authority cannot be reassigned from AHJ")
    if b:
        return Evaluation("SCHEMATIC", b, h, w, passed, accepted)
    passed.append("R0_RESPONSIBILITY")

    if not _yes(project.get("jurisdiction_bound")):
        b.append("G0-001 jurisdiction not bound")
    if not project.get("ahj_name"):
        b.append("G0-002 AHJ not identified")
    if not project.get("governing_codes"):
        b.append("G0-003 governing code snapshot not bound")
    if b:
        return Evaluation("SCHEMATIC", b, h, w, passed, accepted)
    passed.append("G0_JURISDICTION")

    for key, msg in [
        ("legal_site_evidence", "G1-001 legal title/site evidence missing"),
        ("site_plan_evidence", "G1-002 site plan/geodetic grading basis missing"),
        ("homebuilder_assigned", "G1-003 homebuilder not assigned"),
    ]:
        if not _yes(project.get(key)):
            b.append(msg)
    if _status(project.get("development_permit_status")) not in {"ISSUED", "APPROVED", "NOT_REQUIRED"}:
        b.append("G1-004 development/zoning approval unresolved")
    builder_path = (_yes(project.get("builder_licence_valid")) or _yes(project.get("owner_builder_authorization_valid")) or _yes(project.get("builder_licence_not_applicable")))
    if not builder_path:
        b.append("G1-005 builder licence / owner-builder authorization / valid non-applicability unresolved")
    if _yes(project.get("new_home_warranty_required")):
        if not _yes(project.get("new_home_registration_valid")):
            b.append("G1-006 approved new-home registration missing")
        if not _yes(project.get("warranty_enrolment_valid")):
            b.append("G1-007 new-home warranty evidence missing")
    if b:
        return Evaluation("SCHEMATIC", b, h, w, passed, accepted)
    passed.append("G1_SITE_BUILDER")

    if _yes(project.get("professional_involvement_required")):
        if not _yes(project.get("professional_scope_matrix_complete")):
            b.append("G2-001 professional scope matrix incomplete")
        if _yes(project.get("crp_required")) and not _yes(project.get("schedule_A_valid")):
            b.append("G2-002 Schedule A / CRP commitment missing")
        for disc in project.get("required_rpr_disciplines", []):
            if not _yes(project.get("schedule_B", {}).get(disc)):
                b.append(f"G2-003 Schedule B missing for {disc}")
        for firm in project.get("engineering_firms", []):
            if firm.get("corporate_practice_required") and not _yes(firm.get("permit_to_practice_valid")):
                b.append(f"G2-004 APEGA Permit to Practice unresolved for {firm.get('name', 'engineering firm')}")
    if b:
        return Evaluation("SCHEMATIC", b, h, w, passed, accepted)
    passed.append("G2_PROFESSIONAL")

    if _yes(project.get("survey_required")):
        if not _yes(project.get("survey_professional_evidence_valid")):
            b.append("G3-001 required survey evidence not authenticated/valid")
        if not _yes(project.get("site_geometry_matches_survey")):
            b.append("G3-002 digital twin/site geometry not reconciled to survey")
    if _yes(project.get("geotech_required")):
        ge = project.get("geotech", {})
        for key, label in [("authenticated_report", "authenticated report"),("site_applicable", "site applicability"),("bearing_basis", "bearing basis"),("sulphate_basis", "sulphate/concrete-exposure basis"),("groundwater_basis", "groundwater basis"),("foundation_recommendations", "foundation recommendations")]:
            if not _yes(ge.get(key)):
                b.append(f"G3-003 geotechnical {label} unresolved")
    if b:
        return Evaluation("SCHEMATIC", b, h, w, passed, accepted)
    passed.append("G3_SURVEY_GEOTECH")

    for prod in project.get("critical_products", []):
        name = prod.get("name", "product")
        if not _yes(prod.get("identity_traceable")):
            b.append(f"G4-001 {name}: identity/lot/model not traceable")
        if not _yes(prod.get("installation_manual_current")):
            b.append(f"G4-002 {name}: current installation instructions missing")
        if not _yes(prod.get("scope_match")):
            b.append(f"G4-003 {name}: evidence scope does not match intended project use")
        path = _status(prod.get("code_path"))
        if path == "CCMC":
            if not _yes(prod.get("ccmc_active")):
                b.append(f"G4-004 {name}: active CCMC evidence not verified")
            if _yes(prod.get("jurisdiction_acceptance_required")) and not _yes(prod.get("ahj_acceptance")):
                b.append(f"G4-005 {name}: AHJ acceptance required but absent")
        elif path == "CERTIFIED_STANDARD":
            if not _yes(prod.get("certification_current")):
                b.append(f"G4-006 {name}: current code-referenced certification not verified")
        elif path == "PRESCRIPTIVE":
            if not _yes(prod.get("prescriptive_scope_match", True)):
                b.append(f"G4-007 {name}: prescriptive scope mismatch")
        elif path == "ALTERNATIVE_SOLUTION":
            if not _yes(prod.get("professional_dossier_complete")):
                b.append(f"G4-008 {name}: alternative-solution professional dossier incomplete")
            if not _yes(prod.get("ahj_acceptance")):
                b.append(f"G4-009 {name}: AHJ alternative-solution acceptance missing")
        else:
            b.append(f"G4-010 {name}: code-compliance path unresolved")
    for alt in project.get("alternative_solutions", []):
        if not _yes(alt.get("division_c_documentation_complete")):
            b.append("G4-011 alternative-solution Division C documentation incomplete")
        if not _yes(alt.get("professional_authentication")):
            b.append("G4-012 alternative-solution professional authentication missing")
        if not _yes(alt.get("owner_request_or_authorization")):
            b.append("G4-013 alternative-solution owner request/authorization missing")
        if not _yes(alt.get("ahj_acceptance")):
            b.append("G4-014 alternative-solution AHJ acceptance missing")
    if b:
        return Evaluation("SCHEMATIC", b, h, w, passed, accepted)
    passed.append("G4_MANUFACTURER_ALTERNATIVES")

    if not _yes(project.get("permit_submission_documents_complete")):
        b.append("G5-001 permit submission set incomplete")
    if not _yes(project.get("coordinate_consistency_pass")):
        b.append("G5-002 drawings/model/schedules/specs not reconciled")
    if _yes(project.get("professional_involvement_required")) and not _yes(project.get("professional_authentication_complete")):
        b.append("G5-003 required professional work products not authenticated")
    if b:
        return Evaluation("SCHEMATIC", b, h, w, passed, accepted)
    passed.append("G5_PERMIT_SUBMISSION_FEASIBLE")
    level = "PERMIT_SUBMISSION_FEASIBLE"

    if not _yes(project.get("permit_submitted")):
        h.append("G6-HOLD permit package has not been submitted to the AHJ")
        return Evaluation(level, b, h, w, passed, accepted)
    passed.append("G6_PERMIT_SUBMITTED")
    level = "PERMIT_SUBMITTED"

    permits = project.get("required_permits", {})
    missing = [k for k, v in permits.items() if _status(v) not in {"ISSUED", "APPROVED", "NOT_REQUIRED"}]
    if missing:
        h.append("G7-HOLD required permits unresolved: " + ", ".join(sorted(missing)))
        return Evaluation(level, b, h, w, passed, accepted)
    permit_receipt = project.get("building_permit_authority_receipt", {})
    if not _authority_receipt_ok(permit_receipt):
        h.append("G7-HOLD building permit lacks a verified non-synthetic external AHJ/SCO receipt")
        if synthetic:
            w.append("Synthetic/test evidence can exercise logic but cannot prove real permit issuance")
        return Evaluation(level, b, h, w, passed, accepted)
    accepted.append(str(permit_receipt.get("identifier")))
    passed.append("G7_PERMITS_ISSUED")
    level = "PERMITS_ISSUED_SCOPE_LIMITED"

    for key, msg in [("approved_plan_digest_bound", "approved permit-plan digest not bound to construction set"),("permit_conditions_acknowledged", "permit conditions not incorporated"),("site_conditions_reconciled", "site/survey/geotechnical conditions not reconciled to design"),("no_open_critical_design_holds", "critical design/professional/manufacturer holds remain"),("homebuilder_preconstruction_review_complete", "homebuilder preconstruction review incomplete")]:
        if not _yes(project.get(key)):
            b.append("G8-" + msg)
    if b:
        return Evaluation(level, b, h, w, passed, accepted)
    passed.append("G8_CONSTRUCTION_RELEASE_FEASIBLE")
    level = "CONSTRUCTION_RELEASE_FEASIBLE"

    if synthetic:
        h.append("G9-HOLD synthetic/test project cannot reach CONSTRUCTION_RELEASE_AUTHORIZED")
        return Evaluation(level, b, h, w, passed, accepted)
    release_receipt = project.get("construction_release_authority_receipt", {})
    if not _authority_receipt_ok(release_receipt):
        h.append("G9-HOLD verified external authority construction-release receipt absent")
        return Evaluation(level, b, h, w, passed, accepted)
    if not _yes(project.get("homebuilder_internal_release_signed")):
        h.append("G9-HOLD homebuilder internal release sign-off absent")
        return Evaluation(level, b, h, w, passed, accepted)
    if not _yes(project.get("no_stop_work_or_authority_hold")):
        h.append("G9-HOLD stop-work/authority-hold status unresolved")
        return Evaluation(level, b, h, w, passed, accepted)
    accepted.append(str(release_receipt.get("identifier")))
    passed.append("G9_CONSTRUCTION_RELEASE_AUTHORIZED")
    level = "CONSTRUCTION_RELEASE_AUTHORIZED"

    if not _yes(project.get("final_inspections_passed")):
        h.append("G10-HOLD final inspections incomplete")
        return Evaluation(level, b, h, w, passed, accepted)
    if _yes(project.get("professional_involvement_required")) and not _yes(project.get("professional_closeout_complete")):
        h.append("G10-HOLD required professional closeout assurances incomplete")
        return Evaluation(level, b, h, w, passed, accepted)
    if not _yes(project.get("critical_deficiencies_closed")):
        h.append("G10-HOLD critical deficiencies remain")
        return Evaluation(level, b, h, w, passed, accepted)
    passed.append("G10_OCCUPANCY_READY")
    level = "OCCUPANCY_READY"

    occ = project.get("occupancy_authority_receipt", {})
    if not _authority_receipt_ok(occ):
        h.append("G11-HOLD verified external occupancy permission absent")
        return Evaluation(level, b, h, w, passed, accepted)
    accepted.append(str(occ.get("identifier")))
    passed.append("G11_OCCUPANCY_AUTHORIZED")
    level = "OCCUPANCY_AUTHORIZED"

    if not _yes(project.get("as_built_closeout_complete")):
        h.append("G12-HOLD as-built / survey / warranty / O&M closeout incomplete")
        return Evaluation(level, b, h, w, passed, accepted)
    passed.append("G12_AS_BUILT_CLOSEOUT")
    return Evaluation("AS_BUILT_CLOSEOUT", b, h, w, passed, accepted)


def evaluate_dict(project: Dict[str, Any]) -> Dict[str, Any]:
    return asdict(evaluate(project))
