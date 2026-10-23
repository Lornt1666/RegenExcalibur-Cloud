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
from gateway.task_contract import ContractError, authorize_task, validate_contract

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

    def _audit_denial(self, actor: str, reason: str, task_id: str | None = None) -> None:
        try:
            self.ledger.record_denial(actor=actor, action="TASK_INTAKE", reason_code=reason, task_id=task_id)
        except Exception:
            # Do not falsely report durable audit success. The response remains denied.
            pass

    def __call__(self, environ, start_response):
        method = str(environ.get("REQUEST_METHOD", "GET")).upper()
        path = str(environ.get("PATH_INFO", "/"))
        if method == "GET" and path == "/healthz":
            return self._response(start_response, "200 OK", {"status": "ok", "dispatch_enabled": False})
        if path == "/v1/tasks" and method == "POST":
            try:
                identity = self._identity(environ)
            except AuthenticationError:
                self._audit_denial("unauthenticated", "AUTHENTICATION_FAILED")
                return self._response(start_response, "401 Unauthorized", {"error": "authentication_required"})
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
                self._audit_denial(subject, "INVALID_OR_MALFORMED_CONTRACT",
                                   contract.get("task_id") if "contract" in locals() and isinstance(contract, Mapping) and isinstance(contract.get("task_id"), str) else None)
                return self._response(start_response, "400 Bad Request", {"error": "invalid_task_contract"})
            try:
                authorize_task(contract, identity, self.approval_lookup)
            except ContractError:
                self._audit_denial(subject, "AUTHORIZATION_DENIED",
                                   contract.get("task_id") if isinstance(contract.get("task_id"), str) else None)
                return self._response(start_response, "403 Forbidden", {"error": "task_not_authorized"})
            try:
                stored = self.ledger.create_task(contract, subject)
            except IdempotencyConflict:
                return self._response(start_response, "409 Conflict", {"error": "idempotency_conflict"})
            except (ValueError, KeyError, TypeError):
                self._audit_denial(subject, "PERSISTENCE_REJECTED",
                                   contract.get("task_id") if isinstance(contract.get("task_id"), str) else None)
                return self._response(start_response, "400 Bad Request", {"error": "task_not_accepted"})
            return self._response(start_response, "200 OK" if stored["replayed"] else "201 Created", {
                "task_id": stored["task_id"],
                "state": stored["state"],
                "contract_digest": stored["contract_digest"],
                "replayed": stored["replayed"],
                "dispatch_performed": False,
            })
        match = re.fullmatch(r"/v1/tasks/([^/]+)(?:/(audit))?", path)
        if match and method == "GET":
            try:
                identity = self._identity(environ)
            except AuthenticationError:
                self._audit_denial("unauthenticated", "AUTHENTICATION_FAILED")
                return self._response(start_response, "401 Unauthorized", {"error": "authentication_required"})
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
