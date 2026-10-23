import os
import tempfile
import unittest

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
        self.assertEqual(self.ledger.get_task("task-001", "user-1")["contract_digest"], created["contract_digest"])
        self.assertIsNone(self.ledger.get_task("task-001", "different-user"))
        events = self.ledger.audit_events("user-1", "task-001")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["outcome"], "ACCEPTED_INTAKE")
        self.assertIn('"dispatch":"not_performed"', events[0]["details_json"])

    def test_same_idempotency_key_and_intent_returns_original_task(self):
        contract = sample()
        first = self.ledger.create_task(contract, "user-1")
        replay = self.ledger.create_task(contract, "user-1")
        self.assertTrue(replay["replayed"])
        self.assertEqual(replay["task_id"], first["task_id"])
        self.assertEqual([e["outcome"] for e in self.ledger.audit_events("user-1")], ["ACCEPTED_INTAKE", "IDEMPOTENT_REPLAY"])

    def test_reused_idempotency_key_with_changed_intent_is_denied_and_audited(self):
        first = sample()
        self.ledger.create_task(first, "user-1")
        changed = sample()
        changed["target"]["branch"] = "other-branch"
        with self.assertRaises(IdempotencyConflict):
            self.ledger.create_task(changed, "user-1")
        events = self.ledger.audit_events("user-1")
        self.assertEqual(events[-1]["outcome"], "DENIED_IDEMPOTENCY_CONFLICT")

    def test_contract_initiator_must_match_trusted_identity_and_is_audited(self):
        with self.assertRaisesRegex(ValueError, "does not match"):
            self.ledger.create_task(sample(), "different-user")
        events = self.ledger.audit_events("different-user")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["outcome"], "DENIED")
        self.assertIn("INITIATOR_MISMATCH", events[0]["details_json"])

    def test_denial_event_does_not_store_raw_request(self):
        self.ledger.record_denial(actor="user-1", action="job.submit_application",
                                  reason_code="APPROVAL_MISSING", task_id="task-001")
        event = self.ledger.audit_events("user-1")[0]
        self.assertEqual(event["outcome"], "DENIED")
        self.assertIn("APPROVAL_MISSING", event["details_json"])
        self.assertNotIn("secret", event["details_json"])

    def test_audit_events_are_scoped_to_task_owner_or_actor(self):
        own = sample()
        self.ledger.create_task(own, "user-1")
        other = sample()
        other["task_id"] = "task-002"
        other["idempotency_key"] = "idem-002"
        self.ledger.create_task(other, "user-2")
        self.assertEqual(len(self.ledger.audit_events("user-1")), 1)
        self.assertEqual(self.ledger.audit_events("user-1", "task-002"), [])


if __name__ == "__main__":
    unittest.main()
