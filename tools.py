"""
Backend Tools for Ticket Management Agent.
These tools are decorated with @tool from LangChain so the Agentic LLM engine can invoke them.
"""

from typing import Optional
from langchain_core.tools import tool

from tickets_store import MOCK_TICKETS_DB, persist

__all__ = ["ALL_TOOLS", "MOCK_TICKETS_DB"]


@tool
def lookup_ticket(ticket_id: str) -> str:
    """
    Look up customer support ticket details by ticket ID.
    Returns customer info, issue description, status, and purchase details.
    """
    clean_id = str(ticket_id).strip()
    ticket = MOCK_TICKETS_DB.get(clean_id)
    if not ticket:
        return f"Error: Ticket #{clean_id} not found in system."
    return (
        f"Ticket #{ticket['ticket_id']} Details:\n"
        f"- Customer: {ticket['customer_name']} ({ticket['customer_email']})\n"
        f"- Issue: {ticket['issue']}\n"
        f"- Purchase Amount: ${ticket['purchase_amount']:.2f}\n"
        f"- Status: {ticket['status']}"
    )


@tool
def check_refund_eligibility(ticket_id: str) -> str:
    """
    Check if a support ticket is eligible for a refund according to company policy.
    Returns refund eligibility and maximum allowable refund amount.
    """
    clean_id = str(ticket_id).strip()
    ticket = MOCK_TICKETS_DB.get(clean_id)
    if not ticket:
        return f"Error: Ticket #{clean_id} not found in system."

    if ticket["eligible_for_refund"]:
        return f"Ticket #{clean_id} IS ELIGIBLE for a refund up to ${ticket['max_refund']:.2f}."
    return f"Ticket #{clean_id} IS NOT ELIGIBLE for a refund based on company policy."


@tool
def process_refund(ticket_id: str, amount: float, reason: Optional[str] = "Customer request") -> str:
    """
    Process a financial refund for a support ticket.
    Parameters:
      - ticket_id: The ticket ID to refund.
      - amount: The refund amount in USD.
      - reason: The reason for processing the refund.
    Returns refund transaction status and transaction ID.
    """
    clean_id = str(ticket_id).strip()
    ticket = MOCK_TICKETS_DB.get(clean_id)
    if not ticket:
        return f"Error: Ticket #{clean_id} not found in system."

    if not ticket["eligible_for_refund"]:
        return f"Refund Failed: Ticket #{clean_id} is marked non-refundable."

    if amount > ticket["max_refund"]:
        return (
            f"Refund Failed: Requested amount ${amount:.2f} exceeds "
            f"maximum allowed refund of ${ticket['max_refund']:.2f}."
        )

    transaction_id = f"tx_rf_{clean_id}_998"
    ticket["status"] = "Refunded / Resolved"
    persist()

    return (
        f"Refund SUCCESSFUL for Ticket #{clean_id}:\n"
        f"- Refunded Amount: ${amount:.2f}\n"
        f"- Reason: {reason}\n"
        f"- Transaction ID: {transaction_id}\n"
        f"- Updated Ticket Status: {ticket['status']}"
    )


@tool
def update_ticket_status(ticket_id: str, new_status: str, notes: str) -> str:
    """
    Update the status of a support ticket (e.g. 'Resolved', 'Escalated', 'Closed').
    """
    clean_id = str(ticket_id).strip()
    ticket = MOCK_TICKETS_DB.get(clean_id)
    if not ticket:
        return f"Error: Ticket #{clean_id} not found in system."

    ticket["status"] = new_status
    persist()
    return f"Ticket #{clean_id} status updated to '{new_status}'. Notes: {notes}"


ALL_TOOLS = [lookup_ticket, check_refund_eligibility, process_refund, update_ticket_status]
