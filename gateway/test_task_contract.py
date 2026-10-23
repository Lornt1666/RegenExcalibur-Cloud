import unittest
from datetime import datetime, timedelta, timezone
from gateway.task_contract import ContractError, authorize_task, contract_digest, validate_contract


def sample(operation="repo.read_file"):
    return {
        "contract_version": "1JGM-GATEWAY-TASK-1.0", "task_id": "task-001",
        "idempotency_key": "idem-001", "initiated_by": "user-1",
        "session_ref": "session-1", "aigc_contract_ref": "aigc-task-001",
        "target": {"kind": "job_platform"} if operation in {"job.prepare_application", "job.submit_application", "job.search"} else {"kind": "repository", "repository": "Lornt1666/AIGC", "branch": "main"},
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

    def test_rejects_target_kind_mismatch(self):
        contract = sample()
        contract["target"] = {"kind": "cloud_shell", "project_id": "approved-project"}
        with self.assertRaisesRegex(ContractError, "target kind does not match"):
            validate_contract(contract)

    def test_rejects_insecure_or_credentialed_job_urls(self):
        contract = sample("job.submit_application")
        contract["arguments"]["job_url"] = "http://jobs.example/1"
        with self.assertRaisesRegex(ContractError, "credential-free HTTPS"):
            validate_contract(contract)
        contract["arguments"]["job_url"] = "https://user:secret@jobs.example/1"
        with self.assertRaisesRegex(ContractError, "credential-free HTTPS"):
            validate_contract(contract)

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



    def test_rejects_non_string_operation_without_crashing(self):
        contract = sample()
        contract["operation"] = ["repo.read_file"]
        with self.assertRaisesRegex(ContractError, "operation is not allowlisted"):
            validate_contract(contract)

    def test_rejects_malformed_trusted_identity_scope(self):
        contract = sample()
        identity = self.identity()
        identity["repositories"] = "Lornt1666/AIGC"
        with self.assertRaisesRegex(ContractError, "repositories scope is malformed"):
            authorize_task(contract, identity, lambda _: None)

    def test_rejects_aigc_target_outside_authorized_project_scope(self):
        contract = sample()
        contract["operation"] = "aigc.run_phase"
        contract["target"] = {"kind": "project", "project_id": "unapproved-project"}
        contract["arguments"] = {"phase": "phase2", "mode": "dry_run"}
        identity = self.identity()
        identity["projects"] = ["approved-project"]
        with self.assertRaisesRegex(ContractError, "outside authenticated identity scope"):
            authorize_task(contract, identity, lambda _: None)

    def test_rejects_expired_server_side_approval(self):
        contract = sample("job.submit_application")
        record = {"decision": "APPROVED", "task_id": contract["task_id"],
                  "contract_sha256": contract_digest(contract), "approver": "reviewer-2",
                  "expires_at": (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()}
        with self.assertRaisesRegex(ContractError, "approval has expired"):
            authorize_task(contract, self.identity(), lambda _: record)

    def test_rejects_antigravity_handoff_without_workspace_binding(self):
        contract = sample()
        contract["operation"] = "google.antigravity.prepare_handoff"
        contract["target"] = {"kind": "antigravity"}
        contract["arguments"] = {"task_brief": "Review a test change"}
        with self.assertRaisesRegex(ContractError, "explicit workspace binding"):
            validate_contract(contract)

if __name__ == "__main__":
    unittest.main()
