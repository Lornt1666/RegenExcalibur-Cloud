"""Pure job listing normalization and eligibility assessment.

No network discovery, personal-data retrieval, external messaging, or application
submission occurs here. Callers must supply retrieved listings and a verified
profile record from authorized sources.
"""
from __future__ import annotations

from datetime import datetime
from hashlib import sha256
from typing import Any, Mapping
from urllib.parse import urlsplit, urlunsplit


class JobDataError(ValueError):
    pass


def _nonempty_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise JobDataError(f"{field} must be a non-empty string")
    return value.strip()


def canonical_job_url(value: Any) -> str:
    raw = _nonempty_text(value, "source_url")
    parsed = urlsplit(raw)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise JobDataError("source_url must be an HTTPS URL without embedded credentials")
    return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path.rstrip("/") or "/", parsed.query, ""))


def normalize_listing(raw: Mapping[str, Any], retrieved_at: str) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        raise JobDataError("listing must be an object")
    employer = _nonempty_text(raw.get("employer"), "employer")
    title = _nonempty_text(raw.get("title"), "title")
    url = canonical_job_url(raw.get("source_url"))
    retrieved = _nonempty_text(retrieved_at, "retrieved_at")
    try:
        parsed_retrieved = datetime.fromisoformat(retrieved.replace("Z", "+00:00"))
    except ValueError as exc:
        raise JobDataError("retrieved_at must be ISO-8601") from exc
    if parsed_retrieved.tzinfo is None:
        raise JobDataError("retrieved_at must include a timezone")
    requirements = raw.get("required_skills", [])
    preferred = raw.get("preferred_skills", [])
    if not isinstance(requirements, list) or any(not isinstance(x, str) or not x.strip() for x in requirements):
        raise JobDataError("required_skills must be a list of non-empty strings")
    if not isinstance(preferred, list) or any(not isinstance(x, str) or not x.strip() for x in preferred):
        raise JobDataError("preferred_skills must be a list of non-empty strings")
    remote = raw.get("remote_eligibility", "unknown")
    if not isinstance(remote, str) or remote not in {"remote", "hybrid", "onsite", "unknown"}:
        raise JobDataError("remote_eligibility is invalid")
    listing_id = sha256(f"{employer.casefold()}|{title.casefold()}|{url}".encode()).hexdigest()
    return {
        "listing_id": listing_id,
        "employer": employer,
        "title": title,
        "source_url": url,
        "retrieved_at": retrieved,
        "posting_date": raw.get("posting_date"),
        "location": raw.get("location"),
        "remote_eligibility": remote,
        "employment_type": raw.get("employment_type"),
        "salary_range": raw.get("salary_range"),
        "deadline": raw.get("deadline"),
        "required_skills": list(dict.fromkeys(x.strip() for x in requirements)),
        "preferred_skills": list(dict.fromkeys(x.strip() for x in preferred)),
        "required_education": raw.get("required_education"),
        "work_authorization": raw.get("work_authorization"),
    }


def assess_eligibility(listing: Mapping[str, Any], verified_profile: Mapping[str, Any]) -> dict[str, Any]:
    """Assess only explicit profile facts; missing data remains unknown, not a match."""
    if not isinstance(listing, Mapping) or not isinstance(verified_profile, Mapping):
        raise JobDataError("listing and verified_profile must be objects")
    profile_skills = verified_profile.get("skills", [])
    if not isinstance(profile_skills, list) or any(not isinstance(x, str) for x in profile_skills):
        raise JobDataError("verified profile skills must be a list of strings")
    normalized_skills = {x.strip().casefold() for x in profile_skills if x.strip()}
    required = listing.get("required_skills", [])
    preferred = listing.get("preferred_skills", [])
    if not isinstance(required, list) or not isinstance(preferred, list):
        raise JobDataError("listing skill requirements must be arrays")
    matched_required = [x for x in required if isinstance(x, str) and x.casefold() in normalized_skills]
    missing_required = [x for x in required if x not in matched_required]
    matched_preferred = [x for x in preferred if isinstance(x, str) and x.casefold() in normalized_skills]
    unknowns = []
    for field in ("work_authorization", "required_education", "location", "remote_eligibility"):
        required_value = listing.get(field)
        profile_value = verified_profile.get(field)
        if required_value not in (None, "", "unknown") and profile_value in (None, "", "unknown"):
            unknowns.append(field)
    total = len(required)
    skill_coverage = (len(matched_required) / total) if total else None
    if missing_required:
        recommendation = "REVIEW_GAPS"
    elif unknowns:
        recommendation = "NEEDS_VERIFICATION"
    else:
        recommendation = "POTENTIAL_MATCH"
    return {
        "listing_id": listing.get("listing_id"),
        "employer": listing.get("employer"),
        "title": listing.get("title"),
        "source_url": listing.get("source_url"),
        "retrieved_at": listing.get("retrieved_at"),
        "matched_required_skills": matched_required,
        "missing_required_skills": missing_required,
        "matched_preferred_skills": matched_preferred,
        "required_skill_coverage": skill_coverage,
        "unknown_eligibility_fields": unknowns,
        "recommendation": recommendation,
        "limitations": ["Assessment uses only supplied verified profile facts; it is not an employer eligibility decision."],
    }


def deduplicate_listings(listings: list[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    """Keep the newest retrieved record per stable listing ID, preserving input order."""
    chosen: dict[str, Mapping[str, Any]] = {}
    for item in listings:
        key = _nonempty_text(item.get("listing_id"), "listing_id")
        current = chosen.get(key)
        if current is None or str(item.get("retrieved_at", "")) > str(current.get("retrieved_at", "")):
            chosen[key] = item
    return list(chosen.values())


def prepare_application_packet(listing: Mapping[str, Any], verified_profile: Mapping[str, Any]) -> dict[str, Any]:
    """Create a truthful draft packet from supplied verified facts; never submit it."""
    if not isinstance(listing, Mapping) or not isinstance(verified_profile, Mapping):
        raise JobDataError("listing and verified_profile must be objects")
    employer = _nonempty_text(listing.get("employer"), "employer")
    title = _nonempty_text(listing.get("title"), "title")
    source_url = canonical_job_url(listing.get("source_url"))
    name = verified_profile.get("name")
    if name is not None and (not isinstance(name, str) or not name.strip()):
        raise JobDataError("profile name must be a non-empty string when supplied")
    skills = verified_profile.get("skills", [])
    experience = verified_profile.get("experience", [])
    education = verified_profile.get("education", [])
    certifications = verified_profile.get("certifications", [])
    for field, values in (("skills", skills), ("experience", experience), ("education", education), ("certifications", certifications)):
        if not isinstance(values, list):
            raise JobDataError(f"profile {field} must be a list")
    if any(not isinstance(x, str) or not x.strip() for x in skills + education + certifications):
        raise JobDataError("profile skills, education and certifications must contain non-empty strings")
    if any(not isinstance(item, Mapping) for item in experience):
        raise JobDataError("profile experience entries must be objects")
    experience_lines = []
    for item in experience:
        role = _nonempty_text(item.get("title"), "experience.title")
        employer_name = _nonempty_text(item.get("employer"), "experience.employer")
        summary = _nonempty_text(item.get("summary"), "experience.summary")
        experience_lines.append(f"{role} at {employer_name}: {summary}")
    profile_facts = []
    profile_facts.extend([f"Skill: {skill}" for skill in skills])
    profile_facts.extend([f"Experience: {line}" for line in experience_lines])
    profile_facts.extend([f"Education: {item}" for item in education])
    profile_facts.extend([f"Certification: {item}" for item in certifications])
    greeting = f"Dear Hiring Team at {employer},"
    opener = f"I am applying for the {title} role. My application is based on the qualifications listed below."
    if profile_facts:
        qualifications = "\n".join(f"- {fact}" for fact in profile_facts)
    else:
        qualifications = "[Add verified skills, experience, education, or certifications before sending.]"
    closing = "Thank you for considering my application. I would welcome the opportunity to discuss my fit for the role."
    cover_letter = "\n\n".join([greeting, opener, "Relevant qualifications:\n" + qualifications, closing])
    required_documents = listing.get("required_documents", [])
    if not isinstance(required_documents, list) or any(not isinstance(x, str) or not x.strip() for x in required_documents):
        raise JobDataError("required_documents must be a list of non-empty strings")
    return {
        "status": "DRAFT_FOR_REVIEW",
        "employer": employer,
        "role": title,
        "source_url": source_url,
        "candidate_name": name.strip() if isinstance(name, str) else None,
        "qualification_facts_used": profile_facts,
        "cover_letter_draft": cover_letter,
        "required_documents": list(required_documents),
        "missing_profile_sections": [
            field for field, values in (("skills", skills), ("experience", experience), ("education", education), ("certifications", certifications))
            if not values
        ],
        "review_required": True,
        "external_submission_performed": False,
        "approval_required_before_submission": True,
    }
