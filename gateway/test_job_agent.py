import unittest
from gateway.job_agent import JobDataError, assess_eligibility, canonical_job_url, deduplicate_listings, normalize_listing


class JobAgentTests(unittest.TestCase):
    def test_normalizes_listing_and_removes_url_fragment(self):
        listing = normalize_listing({
            "employer": "Example Employer", "title": "Junior Analyst",
            "source_url": "https://jobs.example/role/1#apply",
            "required_skills": ["Python", "Python"], "preferred_skills": ["SQL"],
        }, "2026-10-23T12:00:00Z")
        self.assertEqual(listing["source_url"], "https://jobs.example/role/1")
        self.assertEqual(listing["required_skills"], ["Python"])

    def test_rejects_insecure_or_credentialed_urls(self):
        with self.assertRaises(JobDataError):
            canonical_job_url("http://jobs.example/role")
        with self.assertRaises(JobDataError):
            canonical_job_url("https://user:pass@jobs.example/role")

    def test_missing_profile_facts_are_unknown_not_matches(self):
        listing = {
            "listing_id": "job-1", "employer": "Example", "title": "Analyst",
            "source_url": "https://jobs.example/1", "retrieved_at": "2026-10-23T12:00:00Z",
            "required_skills": ["Python"], "preferred_skills": ["SQL"],
            "work_authorization": "Canada", "remote_eligibility": "remote",
        }
        result = assess_eligibility(listing, {"skills": ["Python"]})
        self.assertEqual(result["recommendation"], "NEEDS_VERIFICATION")
        self.assertEqual(result["matched_required_skills"], ["Python"])
        self.assertEqual(result["unknown_eligibility_fields"], ["work_authorization"])

    def test_missing_required_skill_is_not_fabricated(self):
        listing = {"listing_id": "job-2", "required_skills": ["AutoCAD", "Python"], "preferred_skills": []}
        result = assess_eligibility(listing, {"skills": ["AutoCAD"]})
        self.assertEqual(result["missing_required_skills"], ["Python"])
        self.assertEqual(result["recommendation"], "REVIEW_GAPS")

    def test_deduplicates_by_id_and_keeps_latest_retrieval(self):
        rows = [
            {"listing_id": "same", "retrieved_at": "2026-10-22T12:00:00Z", "value": "old"},
            {"listing_id": "same", "retrieved_at": "2026-10-23T12:00:00Z", "value": "new"},
            {"listing_id": "other", "retrieved_at": "2026-10-23T12:00:00Z", "value": "other"},
        ]
        result = deduplicate_listings(rows)
        self.assertEqual([x["value"] for x in result], ["new", "other"])


if __name__ == "__main__":
    unittest.main()
