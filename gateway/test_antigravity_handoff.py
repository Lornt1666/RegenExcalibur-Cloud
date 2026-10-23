import unittest
from gateway.antigravity_handoff import AntigravityHandoffError, build_antigravity_handoff


class AntigravityHandoffTests(unittest.TestCase):
    def test_builds_scoped_manual_handoff(self):
        result = build_antigravity_handoff({
            "task_id": "task-1",
            "operation": "google.antigravity.prepare_handoff",
            "target": {"kind": "antigravity", "workspace_id": "aigc-review"},
            "arguments": {"task_brief": "Review this isolated branch"},
        })
        self.assertEqual(result["mode"], "USER_ASSISTED_ONLY")
        self.assertEqual(result["workspace_id"], "aigc-review")
        self.assertIn("actual test results", result["constraints"][-2])

    def test_rejects_missing_workspace_binding(self):
        with self.assertRaisesRegex(AntigravityHandoffError, "workspace_id"):
            build_antigravity_handoff({
                "task_id": "task-1", "operation": "google.antigravity.prepare_handoff",
                "target": {"kind": "antigravity"}, "arguments": {"task_brief": "Review"},
            })

    def test_rejects_wrong_operation(self):
        with self.assertRaisesRegex(AntigravityHandoffError, "not an Antigravity"):
            build_antigravity_handoff({"operation": "repo.read_file"})


if __name__ == "__main__":
    unittest.main()
