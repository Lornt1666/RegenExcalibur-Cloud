import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

from gateway.ledger import GatewayLedger, IdempotencyConflict
from gateway.test_task_contract import sample


class GatewayLedgerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.ledger = GatewayLedger(os.path.join(self.tmp.name, "gateway.sqlite3"))

    def test_create_persists_task_and_audit_atomically(self):
        contract = sample()
        created = self.ledger.create_task(contract, "user-1")
        self.assertFalse(created["replayed"])
        self.assertEqual(self.ledger.get_task("task-001")["contract_digest"], created["contract_digest"])
        events = self.ledger.audit_events("task-001")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["outcome"], "ACCEPTED_INTAKE")
        self.assertIn('"dispatch":"not_performed"', events[0]["details_json"])

    def test_same_idempotency_key_and_intent_returns_original_task(self):
        contract = sample()
        first = self.ledger.create_task(contract, "user-1")
        replay = self.ledger.create_task(contract, "user-1")
        self.assertTrue(replay["replayed"])
        self.assertEqual(replay["task_id"], first["task_id"])
        self.assertEqual([e["outcome"] for e in self.ledger.audit_events()], ["ACCEPTED_INTAKE", "IDEMPOTENT_REPLAY"])

    def test_reused_idempotency_key_with_changed_intent_is_denied_and_audited(self):
        first = sample()
        self.ledger.create_task(first, "user-1")
        changed = sample()
        changed["target"]["branch"] = "other-branch"
        with self.assertRaises(IdempotencyConflict):
            self.ledger.create_task(changed, "user-1")
        events = self.ledger.audit_events()
        self.assertEqual(events[-1]["outcome"], "DENIED_IDEMPOTENCY_CONFLICT")

    def test_contract_initiator_must_match_trusted_identity(self):
        with self.assertRaisesRegex(ValueError, "does not match"):
            self.ledger.create_task(sample(), "different-user")
        self.assertEqual(self.ledger.audit_events(), [])

    def test_denial_event_does_not_store_raw_request(self):
        self.ledger.record_denial(actor="user-1", action="job.submit_application",
                                  reason_code="APPROVAL_MISSING", task_id="task-001")
        event = self.ledger.audit_events()[0]
        self.assertEqual(event["outcome"], "DENIED")
        self.assertIn("APPROVAL_MISSING", event["details_json"])
        self.assertNotIn("secret", event["details_json"])


if __name__ == "__main__":
    unittest.main()
