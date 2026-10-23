import unittest
from datetime import datetime, timedelta, timezone
from gateway.task_contract import ContractError, authorize_task, contract_digest, validate_contract


def sample(operation="repo.read_file"):
    return {
        "contract_version": "1JGM-GATEWAY-TASK-1.0", "task_id": "task-001",
        "idempotency_key": "idem-001", "initiated_by": "user-1",
        "session_ref": "session-1", "aigc_contract_ref": "aigc-task-001",
        "target": {"kind": "repository", "repository": "Lornt1666/AIGC", "branch": "main"},
        "operation": operation,
        "arguments": {"path": "README.md"} if operation == "repo.read_file" else {"job_url": "https://jobs.example/1", "application_reference": "application-1"},
        "resource_scope": ["repository:read"],
        "risk_level": "low" if operation == "repo.read_file" else "high",
        "approval_id": None if operation == "repo.read_file" else "approval-1",
        "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat(),
        "execution": {"timeout_seconds": 30, "max_output_bytes": 10000},
        "expected_outputs": ["result"], "acceptance_criteria": ["evidence recorded"],
        "state": "REQUESTED", "audit_correlation_id": "audit-001",
    }


class TaskContractTests(unittest.TestCase):
    def identity(self):
        return {"subject": "user-1", "repositories": ["Lornt1666/AIGC"], "projects": [], "can_approve": True}

    def test_authorizes_scoped_read_only_repository_operation(self):
        self.assertEqual(authorize_task(sample(), self.identity(), lambda _: None), "ALLOW")

    def test_rejects_unknown_top_level_fields(self):
        contract = sample()
        contract["shell_command"] = "cat secrets"
        with self.assertRaisesRegex(ContractError, "unsupported contract fields"):
            validate_contract(contract)

    def test_rejects_repository_path_traversal(self):
        contract = sample()
        contract["arguments"]["path"] = "../../secrets"
        with self.assertRaisesRegex(ContractError, "path traversal"):
            validate_contract(contract)

    def test_rejects_wrong_repository_scope(self):
        contract = sample()
        contract["target"]["repository"] = "someone-else/private"
        with self.assertRaisesRegex(ContractError, "outside authenticated identity scope"):
            authorize_task(contract, self.identity(), lambda _: None)

    def test_rejects_expired_contract(self):
        contract = sample()
        contract["expires_at"] = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
        with self.assertRaisesRegex(ContractError, "expired"):
            validate_contract(contract)

    def test_protected_submission_requires_durable_non_self_approval(self):
        contract = sample("job.submit_application")
        record = {"decision": "APPROVED", "task_id": contract["task_id"],
                  "contract_sha256": contract_digest(contract), "approver": "reviewer-2",
                  "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()}
        self.assertEqual(authorize_task(contract, self.identity(), lambda _: record), "ALLOW")
        record["approver"] = "user-1"
        with self.assertRaisesRegex(ContractError, "self-approval"):
            authorize_task(contract, self.identity(), lambda _: record)

    def test_rejects_approval_bound_to_different_contract(self):
        contract = sample("job.submit_application")
        record = {"decision": "APPROVED", "task_id": contract["task_id"],
                  "contract_sha256": "wrong-digest", "approver": "reviewer-2",
                  "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()}
        with self.assertRaisesRegex(ContractError, "digest mismatch"):
            authorize_task(contract, self.identity(), lambda _: record)


if __name__ == "__main__":
    unittest.main()
