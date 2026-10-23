import unittest
from datetime import datetime, timedelta, timezone

from gateway.aigc_contract_bridge import AIGCContractError, validate_aigc_runtime_contract


def contract():
    return {
        "contract_id": "aigc-001", "objective": "Read-only review",
        "authorized_scope": "repository:read; idempotent", "resource_budget": 100,
        "permitted_actions": ["repo.read_file"], "evidence_requirements": ["test output"],
        "postconditions": ["no production changes"], "termination_conditions": ["review complete"],
        "retry_max": 1, "rollback_enabled": False, "rollback_compensating_action": "",
        "escalation_policy": "human-review", "owner": "user-1",
        "policy_reference": "policy-v1",
        "expiration": (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat(),
    }


class AIGCBridgeTests(unittest.TestCase):
    def test_validates_existing_runtime_contract_shape_without_dispatch(self):
        result = validate_aigc_runtime_contract(contract(), "aigc-001", {"repo.read_file"}, 1000)
        self.assertEqual(result["status"], "VALIDATED_SHAPE_AND_GATEWAY_ALLOWLIST")
        self.assertFalse(result["execution_dispatched"])
        self.assertEqual(result["authoritative_aigc_validation"], "REQUIRED_UPSTREAM")

    def test_rejects_contract_reference_mismatch(self):
        with self.assertRaisesRegex(AIGCContractError, "reference mismatch"):
            validate_aigc_runtime_contract(contract(), "other-id", {"repo.read_file"}, 1000)

    def test_rejects_action_outside_gateway_allowlist(self):
        with self.assertRaisesRegex(AIGCContractError, "outside the gateway allowlist"):
            validate_aigc_runtime_contract(contract(), "aigc-001", set(), 1000)

    def test_rejects_expired_contract(self):
        value = contract()
        value["expiration"] = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
        with self.assertRaisesRegex(AIGCContractError, "expired"):
            validate_aigc_runtime_contract(value, "aigc-001", {"repo.read_file"}, 1000)

    def test_rejects_retry_without_explicit_idempotency_scope(self):
        value = contract()
        value["authorized_scope"] = "repository:read"
        with self.assertRaisesRegex(AIGCContractError, "explicitly declare idempotency"):
            validate_aigc_runtime_contract(value, "aigc-001", {"repo.read_file"}, 1000)

    def test_rejects_excessive_resource_budget(self):
        value = contract()
        value["resource_budget"] = 1001
        with self.assertRaisesRegex(AIGCContractError, "resource budget"):
            validate_aigc_runtime_contract(value, "aigc-001", {"repo.read_file"}, 1000)


if __name__ == "__main__":
    unittest.main()
