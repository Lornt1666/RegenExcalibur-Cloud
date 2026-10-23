"""Transactional local ledger primitive for gateway intake and audit.

This is a single-node SQLite implementation for tests and local integration.
Production multi-instance deployment should implement the same interface on the
approved PostgreSQL/Supabase data plane with database-enforced uniqueness.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import sqlite3
from contextlib import closing
from typing import Any, Mapping

from gateway.task_contract import contract_digest


class IdempotencyConflict(ValueError):
    """An idempotency key was reused for a different task intent."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class GatewayLedger:
    def __init__(self, database_path: str):
        self.database_path = database_path
        with closing(self._connect()) as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS gateway_tasks (
                    task_id TEXT PRIMARY KEY,
                    initiated_by TEXT NOT NULL,
                    idempotency_key TEXT NOT NULL,
                    contract_digest TEXT NOT NULL,
                    contract_json TEXT NOT NULL,
                    state TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE (initiated_by, idempotency_key)
                );
                CREATE TABLE IF NOT EXISTS gateway_audit_events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    occurred_at TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    action TEXT NOT NULL,
                    outcome TEXT NOT NULL,
                    task_id TEXT,
                    contract_digest TEXT,
                    details_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS gateway_audit_task_idx
                    ON gateway_audit_events(task_id, event_id);
            """)

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.database_path, timeout=5.0, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON")
        db.execute("PRAGMA busy_timeout = 5000")
        return db

    @staticmethod
    def _audit(db: sqlite3.Connection, *, actor: str, action: str, outcome: str,
               task_id: str | None, digest: str | None, details: Mapping[str, Any]) -> None:
        db.execute(
            """INSERT INTO gateway_audit_events
               (occurred_at, actor, action, outcome, task_id, contract_digest, details_json)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (_utc_now(), actor, action, outcome, task_id, digest,
             json.dumps(dict(details), sort_keys=True, separators=(",", ":"))),
        )

    def create_task(self, contract: Mapping[str, Any], authenticated_subject: str) -> dict[str, Any]:
        """Persist a validated contract with atomic, identity-scoped idempotency.

        Caller must validate/authorize the contract and derive authenticated_subject
        from trusted server authentication before calling this method.
        """
        if not isinstance(authenticated_subject, str) or not authenticated_subject.strip():
            raise ValueError("authenticated_subject is required")
        if not isinstance(contract, Mapping):
            self.record_denial(actor=authenticated_subject, action="TASK_CREATE",
                               reason_code="MALFORMED_CONTRACT")
            raise ValueError("contract must be an object")
        if contract.get("initiated_by") != authenticated_subject:
            self.record_denial(actor=authenticated_subject, action="TASK_CREATE",
                               reason_code="INITIATOR_MISMATCH",
                               task_id=contract.get("task_id") if isinstance(contract.get("task_id"), str) else None)
            raise ValueError("contract initiator does not match authenticated subject")
        digest = contract_digest(contract)
        encoded = json.dumps(dict(contract), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        now = _utc_now()
        conflict: str | None = None
        result: dict[str, Any] | None = None
        with closing(self._connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            existing = db.execute(
                "SELECT * FROM gateway_tasks WHERE initiated_by=? AND idempotency_key=?",
                (authenticated_subject, contract["idempotency_key"]),
            ).fetchone()
            if existing:
                if existing["contract_digest"] != digest:
                    self._audit(db, actor=authenticated_subject, action="TASK_CREATE",
                                outcome="DENIED_IDEMPOTENCY_CONFLICT", task_id=existing["task_id"],
                                digest=digest, details={"reason": "idempotency key reused with different task intent"})
                    conflict = "idempotency key reused with different task intent"
                else:
                    self._audit(db, actor=authenticated_subject, action="TASK_CREATE",
                                outcome="IDEMPOTENT_REPLAY", task_id=existing["task_id"],
                                digest=digest, details={"reason": "same identity, key, and immutable intent"})
                    result = dict(existing)
                    result["replayed"] = True
            else:
                db.execute(
                    """INSERT INTO gateway_tasks
                       (task_id, initiated_by, idempotency_key, contract_digest, contract_json,
                        state, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (contract["task_id"], authenticated_subject, contract["idempotency_key"],
                     digest, encoded, contract["state"], now, now),
                )
                self._audit(db, actor=authenticated_subject, action="TASK_CREATE",
                            outcome="ACCEPTED_INTAKE", task_id=contract["task_id"], digest=digest,
                            details={"state": contract["state"], "dispatch": "not_performed"})
                result = {
                    "task_id": contract["task_id"], "initiated_by": authenticated_subject,
                    "idempotency_key": contract["idempotency_key"], "contract_digest": digest,
                    "contract_json": encoded, "state": contract["state"],
                    "created_at": now, "updated_at": now, "replayed": False,
                }
            db.commit()
        if conflict:
            raise IdempotencyConflict(conflict)
        assert result is not None
        return result

    def cancel_task(self, task_id: str, authenticated_subject: str) -> dict[str, Any] | None:
        """Atomically cancel an owned task before execution; this prototype never dispatches work."""
        if not isinstance(authenticated_subject, str) or not authenticated_subject.strip():
            raise ValueError("authenticated_subject is required")
        with closing(self._connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT * FROM gateway_tasks WHERE task_id=? AND initiated_by=?",
                (task_id, authenticated_subject),
            ).fetchone()
            if row is None:
                self._audit(db, actor=authenticated_subject, action="TASK_CANCEL",
                            outcome="DENIED_NOT_FOUND_OR_NOT_OWNED", task_id=task_id,
                            digest=None, details={"reason_code": "TASK_NOT_FOUND_OR_NOT_OWNED"})
                db.commit()
                return None
            current_state = row["state"]
            if current_state == "CANCELLED":
                self._audit(db, actor=authenticated_subject, action="TASK_CANCEL",
                            outcome="IDEMPOTENT_CANCEL", task_id=task_id,
                            digest=row["contract_digest"], details={"state": current_state})
                db.commit()
                return {"task_id": task_id, "state": current_state,
                        "cancelled": False, "already_cancelled": True}
            if current_state not in {"REQUESTED", "AUTHORIZED"}:
                self._audit(db, actor=authenticated_subject, action="TASK_CANCEL",
                            outcome="DENIED_NOT_CANCELLABLE", task_id=task_id,
                            digest=row["contract_digest"], details={"state": current_state})
                db.commit()
                return {"task_id": task_id, "state": current_state,
                        "cancelled": False, "already_cancelled": False}
            contract = json.loads(row["contract_json"])
            contract["state"] = "CANCELLED"
            now = _utc_now()
            updated = db.execute(
                """UPDATE gateway_tasks
                   SET state='CANCELLED', contract_json=?, updated_at=?
                   WHERE task_id=? AND initiated_by=? AND state=?""",
                (json.dumps(contract, sort_keys=True, separators=(",", ":"), ensure_ascii=False),
                 now, task_id, authenticated_subject, current_state),
            )
            if updated.rowcount != 1:
                db.rollback()
                raise RuntimeError("task cancellation lost its expected-state race")
            self._audit(db, actor=authenticated_subject, action="TASK_CANCEL",
                        outcome="CANCELLED", task_id=task_id, digest=row["contract_digest"],
                        details={"from_state": current_state, "to_state": "CANCELLED",
                                 "dispatch": "not_performed"})
            db.commit()
            return {"task_id": task_id, "state": "CANCELLED",
                    "cancelled": True, "already_cancelled": False}

    def record_denial(self, *, actor: str, action: str, reason_code: str,
                      task_id: str | None = None, digest: str | None = None) -> None:
        """Durably record a policy denial without storing raw secrets or request bodies."""
        if not actor.strip() or not action.strip() or not reason_code.strip():
            raise ValueError("actor, action, and reason_code are required")
        with closing(self._connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            self._audit(db, actor=actor, action=action, outcome="DENIED", task_id=task_id,
                        digest=digest, details={"reason_code": reason_code})
            db.commit()

    def get_task(self, task_id: str, authenticated_subject: str) -> dict[str, Any] | None:
        """Read only the caller's own task; administrative access needs a separate privileged interface."""
        if not isinstance(authenticated_subject, str) or not authenticated_subject.strip():
            raise ValueError("authenticated_subject is required")
        with closing(self._connect()) as db:
            row = db.execute(
                "SELECT * FROM gateway_tasks WHERE task_id=? AND initiated_by=?",
                (task_id, authenticated_subject),
            ).fetchone()
            return dict(row) if row else None

    def audit_events(self, authenticated_subject: str, task_id: str | None = None) -> list[dict[str, Any]]:
        """Return events for the caller's tasks or events the caller personally generated."""
        if not isinstance(authenticated_subject, str) or not authenticated_subject.strip():
            raise ValueError("authenticated_subject is required")
        with closing(self._connect()) as db:
            if task_id is None:
                rows = db.execute(
                    """SELECT e.* FROM gateway_audit_events e
                       LEFT JOIN gateway_tasks t ON t.task_id=e.task_id
                       WHERE t.initiated_by=? OR e.actor=?
                       ORDER BY e.event_id""",
                    (authenticated_subject, authenticated_subject),
                ).fetchall()
            else:
                rows = db.execute(
                    """SELECT e.* FROM gateway_audit_events e
                       LEFT JOIN gateway_tasks t ON t.task_id=e.task_id
                       WHERE e.task_id=? AND (t.initiated_by=? OR e.actor=?)
                       ORDER BY e.event_id""",
                    (task_id, authenticated_subject, authenticated_subject),
                ).fetchall()
            return [dict(row) for row in rows]
