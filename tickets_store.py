"""
Shared ticket store used by agent tools and the admin UI.
Persists to tickets.json so CRUD changes survive server restarts.
"""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, Optional

DATA_FILE = Path(__file__).resolve().parent / "tickets.json"

DEFAULT_TICKETS: Dict[str, Dict[str, Any]] = {
    "101": {
        "ticket_id": "101",
        "customer_name": "Alice Johnson",
        "customer_email": "alice@example.com",
        "issue": "Flight delayed by 5 hours, requesting compensation/refund.",
        "purchase_amount": 150.00,
        "status": "Open",
        "eligible_for_refund": True,
        "max_refund": 150.00,
    },
    "102": {
        "ticket_id": "102",
        "customer_name": "Bob Smith",
        "customer_email": "bob@example.com",
        "issue": "Double billed for hotel reservation.",
        "purchase_amount": 50.00,
        "status": "Open",
        "eligible_for_refund": True,
        "max_refund": 50.00,
    },
    "103": {
        "ticket_id": "103",
        "customer_name": "Charlie Brown",
        "customer_email": "charlie@example.com",
        "issue": "Changed mind 30 days after non-refundable booking.",
        "purchase_amount": 200.00,
        "status": "Open",
        "eligible_for_refund": False,
        "max_refund": 0.00,
    },
}

# Live in-memory database. Tools and the API mutate this same dict.
MOCK_TICKETS_DB: Dict[str, Dict[str, Any]] = {}


def _normalize(ticket: Dict[str, Any], ticket_id: str) -> Dict[str, Any]:
    purchase = float(ticket.get("purchase_amount", 0) or 0)
    max_refund = ticket.get("max_refund")
    if max_refund is None or max_refund == "":
        max_refund = purchase if ticket.get("eligible_for_refund", True) else 0.0
    return {
        "ticket_id": str(ticket_id).strip(),
        "customer_name": str(ticket.get("customer_name", "")).strip(),
        "customer_email": str(ticket.get("customer_email", "")).strip(),
        "issue": str(ticket.get("issue", "")).strip(),
        "purchase_amount": purchase,
        "status": str(ticket.get("status") or "Open").strip(),
        "eligible_for_refund": bool(ticket.get("eligible_for_refund", True)),
        "max_refund": float(max_refund),
    }


def persist() -> None:
    DATA_FILE.write_text(
        json.dumps(MOCK_TICKETS_DB, indent=2),
        encoding="utf-8",
    )


def load() -> None:
    MOCK_TICKETS_DB.clear()
    if DATA_FILE.exists():
        raw = json.loads(DATA_FILE.read_text(encoding="utf-8"))
        for ticket_id, ticket in raw.items():
            MOCK_TICKETS_DB[str(ticket_id)] = _normalize(ticket, ticket_id)
        return
    MOCK_TICKETS_DB.update(deepcopy(DEFAULT_TICKETS))
    persist()


def list_tickets() -> list[Dict[str, Any]]:
    return [deepcopy(t) for t in sorted(MOCK_TICKETS_DB.values(), key=lambda t: t["ticket_id"])]


def get_ticket(ticket_id: str) -> Optional[Dict[str, Any]]:
    ticket = MOCK_TICKETS_DB.get(str(ticket_id).strip())
    return deepcopy(ticket) if ticket else None


def next_ticket_id() -> str:
    numeric_ids = []
    for key in MOCK_TICKETS_DB:
        if str(key).isdigit():
            numeric_ids.append(int(key))
    return str(max(numeric_ids) + 1 if numeric_ids else 101)


def create_ticket(data: Dict[str, Any]) -> Dict[str, Any]:
    ticket_id = str(data.get("ticket_id") or next_ticket_id()).strip()
    if not ticket_id:
        ticket_id = next_ticket_id()
    if ticket_id in MOCK_TICKETS_DB:
        raise ValueError(f"Ticket #{ticket_id} already exists.")
    ticket = _normalize(data, ticket_id)
    if not ticket["customer_name"] or not ticket["issue"]:
        raise ValueError("Customer name and issue are required.")
    MOCK_TICKETS_DB[ticket_id] = ticket
    persist()
    return deepcopy(ticket)


def update_ticket(ticket_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    clean_id = str(ticket_id).strip()
    if clean_id not in MOCK_TICKETS_DB:
        raise KeyError(f"Ticket #{clean_id} not found.")
    merged = {**MOCK_TICKETS_DB[clean_id], **data, "ticket_id": clean_id}
    ticket = _normalize(merged, clean_id)
    MOCK_TICKETS_DB[clean_id] = ticket
    persist()
    return deepcopy(ticket)


def delete_ticket(ticket_id: str) -> None:
    clean_id = str(ticket_id).strip()
    if clean_id not in MOCK_TICKETS_DB:
        raise KeyError(f"Ticket #{clean_id} not found.")
    del MOCK_TICKETS_DB[clean_id]
    persist()


load()
