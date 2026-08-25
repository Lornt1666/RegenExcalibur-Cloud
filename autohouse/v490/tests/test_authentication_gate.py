from autohouse.v490.authentication_gate import (
    PackageEvidence,
    Requirement,
    State,
    permit_submission_readiness,
    professional_authentication_readiness,
)


def complete_internal_package() -> PackageEvidence:
    return PackageEvidence(
        canonical_model_digest="sha256:model",
        drawing_set_digest="sha256:drawings",
        calculation_set_digest="sha256:calculations",
        code_register_digest="sha256:codes",
        clash_receipt_digest="sha256:clash",
        qaqc_receipt_digest="sha256:qaqc",
        requirements=[
            Requirement("A-001", "Architectural model coordinated", State.RESOLVED, "A"),
            Requirement("S-001", "Structural calculation package complete", State.RESOLVED, "S", True),
            Requirement("M-001", "Mechanical calculation package complete", State.RESOLVED, "M", True),
            Requirement("P-001", "Plumbing design coordinated", State.RESOLVED, "P"),
            Requirement("E-001", "Electrical design coordinated", State.RESOLVED, "E"),
        ],
    )


def test_unresolved_blocks_professional_ready():
    p = complete_internal_package()
    p.requirements.append(Requirement("S-099", "Foundation soil basis", State.PROFESSIONAL_HOLD, "S"))
    result = professional_authentication_readiness(p)
    assert result.state == "INTERNAL_COORDINATION_INCOMPLETE"
    assert any("S:S-099:PROFESSIONAL_HOLD" in x for x in result.blockers)


def test_internal_completion_stops_at_professional_authentication_ready():
    result = professional_authentication_readiness(complete_internal_package())
    assert result.state == "PROFESSIONAL_AUTHENTICATION_READY"
    assert "has not authenticated" in result.truth_boundary


def test_ai_cannot_self_promote_to_permit_ready():
    p = complete_internal_package()
    result = permit_submission_readiness(
        p,
        require_permit_holder_validation=True,
        require_professional_schedules=True,
        require_delegated_design=True,
    )
    assert result.state == "EXTERNAL_AUTHENTICATION_OR_AUTHORITY_PENDING"
    assert "LICENSED_PROFESSIONAL_AUTHENTICATION_NOT_BOUND" in result.blockers
    assert "PERMIT_HOLDER_VALIDATION_NOT_BOUND" in result.blockers
    assert "REQUIRED_PROFESSIONAL_SCHEDULES_NOT_BOUND" in result.blockers
    assert "DELEGATED_DESIGN_NOT_BOUND" in result.blockers
    assert "AHJ_SUBMISSION_PREREQUISITES_NOT_BOUND" in result.blockers


def test_real_external_bindings_allow_submission_ready_not_permit_issued():
    p = complete_internal_package()
    p.professional_authentication_bound = True
    p.permit_holder_validation_bound = True
    p.professional_schedules_bound = True
    p.delegated_design_bound = True
    p.ahj_submission_prerequisites_bound = True
    result = permit_submission_readiness(
        p,
        require_permit_holder_validation=True,
        require_professional_schedules=True,
        require_delegated_design=True,
    )
    assert result.state == "PERMIT_SUBMISSION_READY"
    assert "does not mean a permit has been issued" in result.truth_boundary
