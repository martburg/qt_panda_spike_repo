# src/steuerung3d/apps/yellow/controllers/param_txn.py
"""Parameter edit transactional helper (Qt-free).

This module centralizes the HiP<->Core "best effort" reliability shim used for
parameter editing:

- generate req_id + session_id
- track pending intents until Core acks them via TelemetrySnapshot.core_acks
- resend intents with bounded retries
- provide a small policy helper for reflecting param-edit state without UI flicker

The goal is to keep controller logic readable and keep the state machine testable
without importing PySide6.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import time
from typing import Callable, Dict, Iterable, List, Optional

from steuerung3d.core.intents import Intent, ParamCancel, ParamEditBegin, ParamWrite


@dataclass(frozen=True)
class RetryEvent:
    """A resend/giveup decision emitted by :meth:`ParamEditTxnClient.retry_pending`."""

    req_id: str
    action: str  # "resend" | "giveup"
    retries: int
    intent_type: str


@dataclass
class ParamEditTxnClient:
    """State + helpers for HiP parameter edit transactions."""

    hip_id: str

    # retransmission policy
    resend_after_ms: int = 250
    max_retries: int = 8

    # UI flicker suppression after a local write/cancel
    ignore_remote_after_end_ns: int = 800_000_000  # 0.8s

    # --- local edit state (mirrors UI state but survives stale telemetry) ---
    local_edit_active: bool = False
    local_edit_group: str = ""
    ignore_remote_until_ns: int = 0

    # --- transaction bookkeeping ---
    _req_seq: int = 0
    _session_by_group: Dict[str, str] = field(default_factory=dict)
    _pending_txn: Dict[str, Dict] = field(default_factory=dict)

    # ------------------------------------------------------------------
    # Local edit state
    # ------------------------------------------------------------------

    def reset_local(self) -> None:
        self.local_edit_active = False
        self.local_edit_group = ""
        self.ignore_remote_until_ns = 0

    def start_local_edit(self, group: str) -> None:
        self.local_edit_active = True
        self.local_edit_group = str(group)

    def end_local_edit(self, *, now_ns: Optional[int] = None) -> None:
        self.local_edit_active = False
        self.local_edit_group = ""
        if now_ns is None:
            now_ns = time.monotonic_ns()
        self.ignore_remote_until_ns = int(now_ns) + int(self.ignore_remote_after_end_ns)

    def effective_remote_edit_state(self, *, remote_active: bool, remote_group: str, now_ns: int) -> tuple[bool, str]:
        """Compute the effective edit state to show in the UI."""

        if self.local_edit_active:
            return True, str(self.local_edit_group)
        if int(now_ns) < int(self.ignore_remote_until_ns or 0):
            return False, ""
        return bool(remote_active), str(remote_group or "")

    # ------------------------------------------------------------------
    # Intent factories
    # ------------------------------------------------------------------

    def _next_req_id(self) -> str:
        self._req_seq += 1
        return f"hip-{self._req_seq:06d}"

    def _new_session_id(self, group: str) -> str:
        return f"sess-{group}-{int(time.monotonic() * 1000)}"

    def ensure_session(self, group: str) -> str:
        sid = self._session_by_group.get(group)
        if not sid:
            sid = self._new_session_id(group)
            self._session_by_group[group] = sid
        return sid

    def make_begin_intent(self, *, axis_id: str, group: str) -> ParamEditBegin:
        session_id = self._new_session_id(group)
        self._session_by_group[group] = session_id
        req_id = self._next_req_id()
        return ParamEditBegin(
            axis_id=str(axis_id),
            hip_id=str(self.hip_id),
            group=str(group),
            req_id=req_id,
            session_id=session_id,
        )

    def make_write_intent(self, *, axis_id: str, group: str, values: Dict[str, float]) -> ParamWrite:
        session_id = self.ensure_session(group)
        req_id = self._next_req_id()
        return ParamWrite(
            axis_id=str(axis_id),
            hip_id=str(self.hip_id),
            group=str(group),
            values=dict(values),
            req_id=req_id,
            session_id=session_id,
        )

    def make_cancel_intent(self, *, axis_id: str, group: str) -> ParamCancel:
        session_id = self.ensure_session(group)
        req_id = self._next_req_id()
        return ParamCancel(
            axis_id=str(axis_id),
            hip_id=str(self.hip_id),
            group=str(group),
            req_id=req_id,
            session_id=session_id,
        )

    # ------------------------------------------------------------------
    # Transaction tracking / retry
    # ------------------------------------------------------------------

    def send(
        self,
        intent: Intent,
        *,
        group: str,
        kind: str,
        publish: Callable[[Intent], None],
        now_ns: Optional[int] = None,
    ) -> str:
        """Track an intent (if it has req_id) and publish it."""

        rid = str(getattr(intent, "req_id", "") or "")
        if now_ns is None:
            now_ns = time.monotonic_ns()
        if rid:
            self._pending_txn[rid] = {
                "intent": intent,
                "group": str(group),
                "kind": str(kind or ""),
                "sent_ns": int(now_ns),
                "retries": 0,
            }
        publish(intent)
        return rid

    def handle_core_acks(self, acks: Iterable[str]) -> List[str]:
        """Remove pending transactions that the core acknowledged."""

        removed: List[str] = []
        for rid in list(acks or []):
            if rid in self._pending_txn:
                self._pending_txn.pop(rid, None)
                removed.append(rid)
        return removed

    def retry_pending(self, now_ns: int, publish: Callable[[Intent], None]) -> List[RetryEvent]:
        """Resend pending transactions when their resend timer expires."""

        events: List[RetryEvent] = []
        if not self._pending_txn:
            return events

        resend_after_ns = int(self.resend_after_ms) * 1_000_000
        for rid, info in list(self._pending_txn.items()):
            sent_ns = int(info.get("sent_ns", 0))
            retries = int(info.get("retries", 0))
            if int(now_ns) - sent_ns < resend_after_ns:
                continue

            intent = info.get("intent")
            itype = type(intent).__name__ if intent is not None else "<?>"

            if retries >= int(self.max_retries):
                events.append(RetryEvent(req_id=rid, action="giveup", retries=retries, intent_type=itype))
                self._pending_txn.pop(rid, None)
                continue

            info["retries"] = retries + 1
            info["sent_ns"] = int(now_ns)
            events.append(RetryEvent(req_id=rid, action="resend", retries=int(info["retries"]), intent_type=itype))
            if intent is not None:
                publish(intent)

        return events

    def is_group_busy(self, group: str) -> bool:
        for info in self._pending_txn.values():
            if str(info.get("group")) != str(group):
                continue
            if str(info.get("kind") or "") in ("write", "cancel"):
                return True
        return False
