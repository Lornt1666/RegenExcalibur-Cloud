"""AutoHouse Ω v490 professional-authentication / permit-readiness gate.

This module intentionally separates software readiness from regulated authentication.
It can prove that a package is ready for a licensed professional to review/authenticate,
but it cannot manufacture professional credentials, signatures, seals, permits, or AHJ approval.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable


class State(str, Enum):
    RESOLVED = "RESOLVED"
    DEFAULTED = "DEFAULTED"
    PROVISIONAL = "PROVISIONAL"
    UNRESOLVED = "UNRESOLVED"
    DEFERRED = "DEFERRED"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    CONTRADICTORY = "CONTRADICTORY"
    PROFESSIONAL_HOLD = "PROFESSIONAL_HOLD"
    AUTHORITY_HOLD = "AUTHORITY_HOLD"
    MANUFACTURER_HOLD = "MANUFACTURER_HOLD"
    TESTING_HOLD = "TESTING_HOLD"


BLOCKING_STATES = {
    State.UNRESOLVED,
    State.CONTRADICTORY,
    State.PROFESSIONAL_HOLD,
    State.AUTHORITY_HOLD,
    State.MANUFACTURER_HOLD,
    State.TESTING_HOLD,
}


@dataclass(frozen=True)
class Requirement:
    code: str
    description: str
    state: State
    discipline: str
    external_authority_required: bool = False


@dataclass
class PackageEvidence:
    canonical_model_digest: str | None = None
    drawing_set_digest: str | None = None
    calculation_set_digest: str | None = None
    code_register_digest: str | None = None
    clash_receipt_digest: str | None = None
    qaqc_receipt_digest: str | None = None
    requirements: list[Requirement] = field(default_factory=list)
    professional_authentication_bound: bool = False
    permit_holder_validation_bound: bool = False
    professional_schedules_bound: bool = False
    delegated_design_bound: bool = False
    ahj_submission_prerequisites_bound: bool = False


@dataclass(frozen=True)
class GateResult:
    state: str
    blockers: tuple[str, ...]
    truth_boundary: str


def _missing_core_digests(evidence: PackageEvidence) -> list[str]:
    required = {
        "canonical_model_digest": evidence.canonical_model_digest,
        "drawing_set_digest": evidence.drawing_set_digest,
        "calculation_set_digest": evidence.calculation_set_digest,
        "code_register_digest": evidence.code_register_digest,
        "clash_receipt_digest": evidence.clash_receipt_digest,
        "qaqc_receipt_digest": evidence.qaqc_receipt_digest,
    }
    return [name for name, value in required.items() if not value]


def professional_authentication_readiness(evidence: PackageEvidence) -> GateResult:
    blockers: list[str] = []
    blockers.extend(f"MISSING:{name}" for name in _missing_core_digests(evidence))

    for requirement in evidence.requirements:
        if requirement.state in BLOCKING_STATES:
            blockers.append(
                f"{requirement.discipline}:{requirement.code}:{requirement.state.value}"
            )

    if blockers:
        return GateResult(
            state="INTERNAL_COORDINATION_INCOMPLETE",
            blockers=tuple(sorted(set(blockers))),
            truth_boundary=(
                "Not ready for professional authentication. AutoHouse does not create "
                "professional approval, seals, signatures, permits, or AHJ acceptance."
            ),
        )

    return GateResult(
        state="PROFESSIONAL_AUTHENTICATION_READY",
        blockers=(),
        truth_boundary=(
            "Software package is ready for licensed-professional review/authentication only. "
            "AutoHouse has not authenticated the professional work product."
        ),
    )


def permit_submission_readiness(
    evidence: PackageEvidence,
    *,
    require_permit_holder_validation: bool,
    require_professional_schedules: bool,
    require_delegated_design: bool,
) -> GateResult:
    pre = professional_authentication_readiness(evidence)
    if pre.state != "PROFESSIONAL_AUTHENTICATION_READY":
        return GateResult(
            state="PERMIT_SUBMISSION_BLOCKED",
            blockers=pre.blockers,
            truth_boundary=pre.truth_boundary,
        )

    blockers: list[str] = []
    if not evidence.professional_authentication_bound:
        blockers.append("LICENSED_PROFESSIONAL_AUTHENTICATION_NOT_BOUND")
    if require_permit_holder_validation and not evidence.permit_holder_validation_bound:
        blockers.append("PERMIT_HOLDER_VALIDATION_NOT_BOUND")
    if require_professional_schedules and not evidence.professional_schedules_bound:
        blockers.append("REQUIRED_PROFESSIONAL_SCHEDULES_NOT_BOUND")
    if require_delegated_design and not evidence.delegated_design_bound:
        blockers.append("DELEGATED_DESIGN_NOT_BOUND")
    if not evidence.ahj_submission_prerequisites_bound:
        blockers.append("AHJ_SUBMISSION_PREREQUISITES_NOT_BOUND")

    if blockers:
        return GateResult(
            state="EXTERNAL_AUTHENTICATION_OR_AUTHORITY_PENDING",
            blockers=tuple(blockers),
            truth_boundary=(
                "The technical package may be complete, but permit-submission readiness "
                "requires the actual external professional/permit-holder/AHJ prerequisites."
            ),
        )

    return GateResult(
        state="PERMIT_SUBMISSION_READY",
        blockers=(),
        truth_boundary=(
            "Permit submission package is assembled with required external authentication "
            "and prerequisites bound. This state does not mean a permit has been issued."
        ),
    )


def assert_no_silent_omissions(requirements: Iterable[Requirement]) -> None:
    allowed = set(State)
    for requirement in requirements:
        if requirement.state not in allowed:
            raise ValueError(f"Unknown state for {requirement.code}")
        if not requirement.code.strip() or not requirement.description.strip():
            raise ValueError("Every requirement needs a code and description")
