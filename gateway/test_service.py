import os
import tempfile
import unittest

from gateway.ledger import GatewayLedger
from gateway.service import GatewayIntakeService, IntakeDenied
from gateway.test_task_contract import sample


class GatewayIntakeServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.ledger = GatewayLedger(os.path.join(self.tmp.name, "gateway.sqlite3"))
        self.service = GatewayIntakeService(self.ledger)
        self.identity = {"subject": "user-1", "repositories": ["Lornt1666/AIGC"], "projects": [], "can_approve": True}

    def test_authorized_request_is_persisted_as_server_authorized_without_dispatch(self):
        result = self.service.submit(sample(), self.identity, lambda _: None)
        self.assertEqual(result["state"], "AUTHORIZED")
        self.assertEqual(self.ledger.get_task("task-001", "user-1")["state"], "AUTHORIZED")
        self.assertIn('"dispatch":"not_performed"', self.ledger.audit_events("user-1")[0]["details_json"])

    def test_wrong_scope_is_denied_and_durably_audited(self):
        contract = sample()
        contract["target"]["repository"] = "someone-else/private"
        with self.assertRaises(IntakeDenied):
            self.service.submit(contract, self.identity, lambda _: None)
        events = self.ledger.audit_events("user-1")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["outcome"], "DENIED")
        self.assertEqual(events[0]["action"], "repo.read_file")

    def test_missing_trusted_identity_is_denied(self):
        with self.assertRaises(IntakeDenied):
            self.service.submit(sample(), None, lambda _: None)
        self.assertEqual(self.ledger.audit_events("unauthenticated")[0]["outcome"], "DENIED")

    def test_client_cannot_submit_pre_authorized_state(self):
        contract = sample()
        contract["state"] = "AUTHORIZED"
        with self.assertRaisesRegex(IntakeDenied, "server-controlled"):
            self.service.submit(contract, self.identity, lambda _: None)
        self.assertIsNone(self.ledger.get_task("task-001", "user-1"))

if __name__ == "__main__":
    unittest.main()
