import unittest
from gateway.cloud_shell_handoff import HandoffError, build_cloud_shell_handoff, verify_cloud_shell_receipt


class CloudShellHandoffTests(unittest.TestCase):
    def test_builds_only_allowlisted_read_only_command(self):
        handoff = build_cloud_shell_handoff("project", "my-project-123", "task-1")
        self.assertEqual(handoff["mode"], "USER_ASSISTED_ONLY")
        self.assertEqual(handoff["commands"], ["gcloud config get-value project"])
        self.assertIn("has not executed", handoff["verification"])

    def test_rejects_arbitrary_command_type(self):
        with self.assertRaisesRegex(HandoffError, "not allowlisted"):
            build_cloud_shell_handoff("bash -c 'cat ~/.config/gcloud'", "my-project-123", "task-1")

    def test_rejects_wrong_project_receipt(self):
        with self.assertRaisesRegex(HandoffError, "does not match"):
            verify_cloud_shell_receipt("project", "my-project-123", {"output": "other-project", "executed_at": "2026-10-23T12:00:00Z"})

    def test_receipt_is_not_claimed_as_independently_verified(self):
        result = verify_cloud_shell_receipt("project", "my-project-123", {"output": "my-project-123", "executed_at": "2026-10-23T12:00:00Z"})
        self.assertEqual(result["status"], "USER_REPORTED_MATCH")
        self.assertFalse(result["independently_verified"])


if __name__ == "__main__":
    unittest.main()
