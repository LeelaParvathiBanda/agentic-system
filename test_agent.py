"""
Unit and Integration Tests for Ticket Management Agentic System.
"""

import sys
from fastapi.testclient import TestClient
from main import app
from tools import lookup_ticket, check_refund_eligibility, process_refund, MOCK_TICKETS_DB
from agent import run_agentic_flow

client = TestClient(app)


def test_tools_directly():
    """Verify tool functions directly."""
    print("\n--- Testing Tools Directly ---")
    
    # 1. Test lookup_ticket
    res_101 = lookup_ticket.invoke({"ticket_id": "101"})
    assert "Alice Johnson" in res_101
    print("[PASS] Tool lookup_ticket passed for ticket #101")
    
    # 2. Test check_refund_eligibility
    elig_102 = check_refund_eligibility.invoke({"ticket_id": "102"})
    assert "IS ELIGIBLE" in elig_102
    print("[PASS] Tool check_refund_eligibility passed for ticket #102")
    
    # 3. Test process_refund
    refund_102 = process_refund.invoke({"ticket_id": "102", "amount": 50.0, "reason": "Double billing"})
    assert "Refund SUCCESSFUL" in refund_102
    assert MOCK_TICKETS_DB["102"]["status"] == "Refunded / Resolved"
    print("[PASS] Tool process_refund passed for ticket #102")


def test_agentic_flow():
    """Verify agentic flow engine."""
    print("\n--- Testing Agentic Engine ---")
    
    output = run_agentic_flow("Can you check ticket #101 and refund it?")
    assert output["response"]
    print(f"[PASS] Agentic Engine Response:\n{output['response']}\n")


def test_fastapi_endpoints():
    """Verify FastAPI endpoint responses."""
    print("\n--- Testing FastAPI Endpoints ---")
    
    # 1. Health check
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
    print("[PASS] GET /health endpoint passed")
    
    # 2. Agent Chat API
    payload = {"message": "Please look up ticket #101 details"}
    response = client.post("/api/support-agent", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "response" in data
    print(f"[PASS] POST /api/support-agent passed. API Response:\n{data}\n")


if __name__ == "__main__":
    print("Starting Automated Tests...")
    test_tools_directly()
    test_agentic_flow()
    test_fastapi_endpoints()
    print("All Tests Passed Successfully!")

