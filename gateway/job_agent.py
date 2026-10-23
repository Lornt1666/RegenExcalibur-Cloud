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
        datetime.fromisoformat(retrieved.replace("Z", "+00:00"))
    except ValueError as exc:
        raise JobDataError("retrieved_at must be ISO-8601") from exc
    requirements = raw.get("required_skills", [])
    preferred = raw.get("preferred_skills", [])
    if not isinstance(requirements, list) or any(not isinstance(x, str) or not x.strip() for x in requirements):
        raise JobDataError("required_skills must be a list of non-empty strings")
    if not isinstance(preferred, list) or any(not isinstance(x, str) or not x.strip() for x in preferred):
        raise JobDataError("preferred_skills must be a list of non-empty strings")
    remote = raw.get("remote_eligibility", "unknown")
    if remote not in {"remote", "hybrid", "onsite", "unknown"}:
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
