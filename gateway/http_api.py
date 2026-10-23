"""Dependency-injected WSGI intake API for the governed gateway.

This API does not dispatch external work. A production host must inject a real
cryptographic identity verifier and an approved persistent ledger. The default
design is fail-closed: no global application is created without those dependencies.
"""
from __future__ import annotations

import json
import re
from typing import Any, Callable, Mapping
from urllib.parse import unquote

from gateway.ledger import GatewayLedger, IdempotencyConflict
from gateway.service import AuditUnavailable, GatewayIntakeService, IntakeDenied, PersistenceUnavailable
from gateway.task_contract import ContractError, validate_contract

MAX_BODY_BYTES = 128 * 1024


class AuthenticationError(Exception):
    pass


Authenticator = Callable[[Mapping[str, Any]], Mapping[str, Any]]
ApprovalLookup = Callable[[str], Mapping[str, Any] | None]


class GovernedGatewayWSGI:
    def __init__(
        self,
        ledger: GatewayLedger,
        authenticate: Authenticator,
        approval_lookup: ApprovalLookup | None = None,
    ):
        if not callable(authenticate):
            raise ValueError("a trusted server-side authenticator is required")
        self.ledger = ledger
        self.authenticate = authenticate
        self.approval_lookup = approval_lookup or (lambda _approval_id: None)
        self.intake_service = GatewayIntakeService(ledger)

    def _response(self, start_response, status: str, payload: Mapping[str, Any]):
        body = json.dumps(dict(payload), ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        start_response(status, [
            ("Content-Type", "application/json; charset=utf-8"),
            ("Content-Length", str(len(body))),
            ("Cache-Control", "no-store"),
            ("X-Content-Type-Options", "nosniff"),
            ("Referrer-Policy", "no-referrer"),
        ])
        return [body]

    def _identity(self, environ: Mapping[str, Any]) -> Mapping[str, Any]:
        try:
            identity = self.authenticate(environ)
        except Exception as exc:
            raise AuthenticationError("authentication failed") from exc
        if not isinstance(identity, Mapping) or not isinstance(identity.get("subject"), str) or not identity["subject"].strip():
            raise AuthenticationError("authenticator returned no trusted subject")
        return identity

    def _audit_denial(self, actor: str, reason: str, task_id: str | None = None) -> bool:
        try:
            self.ledger.record_denial(actor=actor, action="TASK_INTAKE", reason_code=reason, task_id=task_id)
            return True
        except Exception:
            return False

    def _deny(self, start_response, actor: str, reason: str, status: str,
              payload: Mapping[str, Any], task_id: str | None = None):
        if not self._audit_denial(actor, reason, task_id):
            return self._response(start_response, "503 Service Unavailable",
                                  {"error": "audit_unavailable", "dispatch_performed": False})
        return self._response(start_response, status, payload)

    def __call__(self, environ, start_response):
        method = str(environ.get("REQUEST_METHOD", "GET")).upper()
        path = str(environ.get("PATH_INFO", "/"))
        if method == "GET" and path == "/healthz":
            return self._response(start_response, "200 OK", {"status": "ok", "dispatch_enabled": False})
        if path == "/v1/tasks" and method == "POST":
            try:
                identity = self._identity(environ)
            except AuthenticationError:
                return self._deny(start_response, "unauthenticated", "AUTHENTICATION_FAILED",
                                  "401 Unauthorized", {"error": "authentication_required"})
            subject = identity["subject"]
            try:
                length = int(environ.get("CONTENT_LENGTH") or "0")
                if length <= 0 or length > MAX_BODY_BYTES:
                    raise ValueError("invalid body size")
                if str(environ.get("CONTENT_TYPE", "")).split(";")[0].strip().lower() != "application/json":
                    raise ValueError("JSON content type required")
                raw = environ["wsgi.input"].read(length)
                contract = json.loads(raw.decode("utf-8"))
                if not isinstance(contract, Mapping):
                    raise ValueError("contract must be an object")
                if contract.get("state") != "REQUESTED":
                    raise ContractError("new intake must start in REQUESTED state")
                validate_contract(contract)
            except (ValueError, UnicodeDecodeError, json.JSONDecodeError, ContractError, KeyError):
                return self._deny(start_response, subject, "INVALID_OR_MALFORMED_CONTRACT",
                                  "400 Bad Request", {"error": "invalid_task_contract"},
                                  contract.get("task_id") if "contract" in locals() and isinstance(contract, Mapping) and isinstance(contract.get("task_id"), str) else None)
            try:
                stored = self.intake_service.submit(contract, identity, self.approval_lookup)
            except IdempotencyConflict:
                return self._response(start_response, "409 Conflict", {"error": "idempotency_conflict"})
            except IntakeDenied:
                return self._response(start_response, "403 Forbidden", {"error": "task_not_authorized"})
            except AuditUnavailable:
                return self._response(start_response, "503 Service Unavailable",
                                      {"error": "audit_unavailable", "dispatch_performed": False})
            except PersistenceUnavailable:
                return self._response(start_response, "503 Service Unavailable",
                                      {"error": "task_not_accepted", "dispatch_performed": False})
            return self._response(start_response, "200 OK" if stored["replayed"] else "201 Created", {
                "task_id": stored["task_id"],
                "state": stored["state"],
                "contract_digest": stored["contract_digest"],
                "replayed": stored["replayed"],
                "dispatch_performed": False,
            })
        match = re.fullmatch(r"/v1/tasks/([^/]+)(?:/(audit|cancel))?", path)
        if match and match.group(2) == "cancel" and method == "POST":
            try:
                identity = self._identity(environ)
            except AuthenticationError:
                return self._deny(start_response, "unauthenticated", "AUTHENTICATION_FAILED",
                                  "401 Unauthorized", {"error": "authentication_required"})
            task_id = unquote(match.group(1))
            try:
                result = self.ledger.cancel_task(task_id, identity["subject"])
            except Exception:
                return self._response(start_response, "503 Service Unavailable",
                                      {"error": "cancellation_unavailable", "dispatch_performed": False})
            if result is None:
                return self._response(start_response, "404 Not Found", {"error": "task_not_found"})
            if not result["cancelled"] and not result["already_cancelled"]:
                return self._response(start_response, "409 Conflict", {
                    "error": "task_not_cancellable", "state": result["state"],
                    "dispatch_performed": False,
                })
            return self._response(start_response, "200 OK", {
                **result, "dispatch_performed": False,
            })
        if match and method == "GET":
            try:
                identity = self._identity(environ)
            except AuthenticationError:
                return self._deny(start_response, "unauthenticated", "AUTHENTICATION_FAILED",
                                  "401 Unauthorized", {"error": "authentication_required"})
            task_id = unquote(match.group(1))
            subject = identity["subject"]
            task = self.ledger.get_task(task_id, subject)
            if task is None:
                return self._response(start_response, "404 Not Found", {"error": "task_not_found"})
            if match.group(2) == "audit":
                return self._response(start_response, "200 OK", {"task_id": task_id, "events": self.ledger.audit_events(subject, task_id)})
            return self._response(start_response, "200 OK", {
                "task_id": task["task_id"], "state": task["state"],
                "contract_digest": task["contract_digest"], "contract": json.loads(task["contract_json"]),
                "created_at": task["created_at"], "updated_at": task["updated_at"],
                "dispatch_performed": False,
            })
        if path == "/v1/tasks" or match:
            return self._response(start_response, "405 Method Not Allowed", {"error": "method_not_allowed"})
        return self._response(start_response, "404 Not Found", {"error": "not_found"})
