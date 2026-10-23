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
        result = assess_eligibility(listing, {"skills": ["Python"], "remote_eligibility": "remote"})
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



    def test_rejects_timezone_free_retrieval_timestamp(self):
        with self.assertRaisesRegex(JobDataError, "must include a timezone"):
            normalize_listing({"employer": "Example", "title": "Role", "source_url": "https://jobs.example/1"}, "2026-10-23T12:00:00")

    def test_rejects_malformed_remote_eligibility_without_crashing(self):
        with self.assertRaisesRegex(JobDataError, "remote_eligibility is invalid"):
            normalize_listing({"employer": "Example", "title": "Role", "source_url": "https://jobs.example/1", "remote_eligibility": ["remote"]}, "2026-10-23T12:00:00Z")


    def test_application_draft_uses_only_supplied_profile_facts(self):
        from gateway.job_agent import prepare_application_packet
        listing = {"employer": "Example Employer", "title": "Junior Analyst", "source_url": "https://jobs.example/role/1", "required_documents": ["resume"]}
        profile = {"name": "Candidate", "skills": ["Python"], "experience": [{"title": "Analyst Intern", "employer": "Sample Co", "summary": "Prepared weekly data reports"}], "education": [], "certifications": []}
        packet = prepare_application_packet(listing, profile)
        self.assertEqual(packet["status"], "DRAFT_FOR_REVIEW")
        self.assertIn("Python", packet["cover_letter_draft"])
        self.assertIn("Prepared weekly data reports", packet["cover_letter_draft"])
        self.assertNotIn("10 years", packet["cover_letter_draft"])
        self.assertFalse(packet["external_submission_performed"])
        self.assertTrue(packet["approval_required_before_submission"])

    def test_application_draft_marks_missing_profile_facts(self):
        from gateway.job_agent import prepare_application_packet
        packet = prepare_application_packet({"employer": "Example", "title": "Role", "source_url": "https://jobs.example/1"}, {"skills": [], "experience": [], "education": [], "certifications": []})
        self.assertEqual(packet["missing_profile_sections"], ["skills", "experience", "education", "certifications"])
        self.assertIn("Add verified", packet["cover_letter_draft"])

if __name__ == "__main__":
    unittest.main()
