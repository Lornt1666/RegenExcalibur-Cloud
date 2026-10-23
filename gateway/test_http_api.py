import io
import json
import os
import tempfile
import unittest

from gateway.http_api import AuthenticationError, GovernedGatewayWSGI
from gateway.ledger import GatewayLedger
from gateway.test_task_contract import sample


def invoke(app, method="GET", path="/healthz", payload=None, auth="Bearer valid"):
    raw = b"" if payload is None else json.dumps(payload).encode("utf-8")
    environ = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "CONTENT_TYPE": "application/json",
        "CONTENT_LENGTH": str(len(raw)),
        "wsgi.input": io.BytesIO(raw),
        "HTTP_AUTHORIZATION": auth,
    }
    status = {}
    def start_response(value, headers):
        status["value"] = value
        status["headers"] = dict(headers)
    body = b"".join(app(environ, start_response))
    return status["value"], status["headers"], json.loads(body.decode("utf-8"))


class GatewayHTTPAPITests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.ledger = GatewayLedger(os.path.join(self.tmp.name, "gateway.sqlite3"))

        def authenticate(environ):
            token = environ.get("HTTP_AUTHORIZATION")
            if token == "Bearer valid":
                return {"subject": "user-1", "repositories": ["Lornt1666/AIGC"], "projects": [], "can_approve": True}
            if token == "Bearer user2":
                return {"subject": "user-2", "repositories": ["Lornt1666/AIGC"], "projects": [], "can_approve": True}
            raise AuthenticationError("bad token")

        self.app = GovernedGatewayWSGI(self.ledger, authenticate)

    def test_health_is_static_and_never_claims_dispatch(self):
        status, _, body = invoke(self.app)
        self.assertEqual(status, "200 OK")
        self.assertFalse(body["dispatch_enabled"])

    def test_authenticated_intake_persists_contract_and_does_not_dispatch(self):
        status, headers, body = invoke(self.app, "POST", "/v1/tasks", sample())
        self.assertEqual(status, "201 Created")
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertFalse(body["dispatch_performed"])
        self.assertEqual(self.ledger.get_task("task-001", "user-1")["state"], "AUTHORIZED")

    def test_same_request_replays_idempotently(self):
        first = invoke(self.app, "POST", "/v1/tasks", sample())
        second = invoke(self.app, "POST", "/v1/tasks", sample())
        self.assertEqual(first[0], "201 Created")
        self.assertEqual(second[0], "200 OK")
        self.assertTrue(second[2]["replayed"])

    def test_authentication_failure_is_denied_and_audited(self):
        status, _, body = invoke(self.app, "POST", "/v1/tasks", sample(), auth="Bearer bad")
        self.assertEqual(status, "401 Unauthorized")
        self.assertEqual(body["error"], "authentication_required")
        events = self.ledger.audit_events("unauthenticated")
        self.assertEqual(events[0]["outcome"], "DENIED")
        self.assertIn("AUTHENTICATION_FAILED", events[0]["details_json"])

    def test_wrong_repository_scope_is_denied_before_task_creation(self):
        status, _, body = invoke(self.app, "POST", "/v1/tasks", sample())
        self.assertEqual(status, "201 Created")
        changed = sample()
        changed["task_id"] = "task-002"
        changed["idempotency_key"] = "idem-002"
        changed["target"]["repository"] = "other/private"
        # Authenticator permits only Lornt1666/AIGC, so this request must be denied.
        status, _, body = invoke(self.app, "POST", "/v1/tasks", changed)
        self.assertEqual(status, "403 Forbidden")
        self.assertEqual(body["error"], "task_not_authorized")
        self.assertIsNone(self.ledger.get_task("task-002", "user-1"))
        self.assertIn("AUTHORIZATION_DENIED", self.ledger.audit_events("user-1")[-1]["details_json"])

    def test_contract_must_enter_requested_state(self):
        contract = sample()
        contract["state"] = "AUTHORIZED"
        status, _, body = invoke(self.app, "POST", "/v1/tasks", contract)
        self.assertEqual(status, "400 Bad Request")
        self.assertEqual(body["error"], "invalid_task_contract")
        self.assertIsNone(self.ledger.get_task("task-001", "user-1"))

    def test_task_and_audit_reads_are_owner_scoped(self):
        invoke(self.app, "POST", "/v1/tasks", sample())
        status, _, body = invoke(self.app, "GET", "/v1/tasks/task-001")
        self.assertEqual(status, "200 OK")
        self.assertEqual(body["task_id"], "task-001")
        self.assertFalse(body["dispatch_performed"])
        status, _, body = invoke(self.app, "GET", "/v1/tasks/task-001", auth="Bearer user2")
        self.assertEqual(status, "404 Not Found")
        self.assertEqual(body["error"], "task_not_found")
        status, _, body = invoke(self.app, "GET", "/v1/tasks/task-001/audit", auth="Bearer user2")
        self.assertEqual(status, "404 Not Found")
        self.assertEqual(body["error"], "task_not_found")

    def test_denial_fails_closed_if_audit_storage_is_unavailable(self):
        def fail_audit(**_kwargs):
            raise OSError("disk unavailable")
        self.ledger.record_denial = fail_audit
        status, _, body = invoke(self.app, "POST", "/v1/tasks", sample(), auth="Bearer bad")
        self.assertEqual(status, "503 Service Unavailable")
        self.assertEqual(body["error"], "audit_unavailable")
        self.assertFalse(body["dispatch_performed"])




    def test_unauthenticated_read_fails_closed_if_audit_storage_is_unavailable(self):
        def fail_audit(**_kwargs):
            raise OSError("disk unavailable")
        self.ledger.record_denial = fail_audit
        status, _, body = invoke(self.app, "GET", "/v1/tasks/task-001", auth="Bearer bad")
        self.assertEqual(status, "503 Service Unavailable")
        self.assertEqual(body["error"], "audit_unavailable")
        self.assertFalse(body["dispatch_performed"])

    def test_persistence_failure_is_denied_and_audited(self):
        def fail_create(*_args, **_kwargs):
            raise RuntimeError("database unavailable")
        self.ledger.create_task = fail_create
        status, _, body = invoke(self.app, "POST", "/v1/tasks", sample())
        self.assertEqual(status, "503 Service Unavailable")
        self.assertEqual(body["error"], "task_not_accepted")
        self.assertFalse(body["dispatch_performed"])
        events = self.ledger.audit_events("user-1")
        self.assertEqual(events[-1]["outcome"], "DENIED")
        self.assertIn("PERSISTENCE_REJECTED", events[-1]["details_json"])

if __name__ == "__main__":
    unittest.main()
