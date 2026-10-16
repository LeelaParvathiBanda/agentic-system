"""
FastAPI Server for Smart Ticket Management Agentic System.
"""

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional

from agent import clear_chat_session, is_langsmith_enabled, run_agentic_flow
from tickets_store import (
    create_ticket,
    delete_ticket,
    get_ticket,
    list_tickets,
    update_ticket,
)

STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(
    title="Smart Ticket Management Agentic System",
    description="Agentic System for Customer Support Ticket Management with LangSmith Tracing",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class SupportRequest(BaseModel):
    message: str = Field(..., description="User query or instruction for the ticket agent", json_schema_extra={"example": "Can you check ticket #102 and process a refund of $50?"})
    user_id: Optional[str] = Field(None, description="Optional customer or user identifier", json_schema_extra={"example": "usr_123"})
    session_id: Optional[str] = Field(None, description="Pass this back on follow-up messages to keep chat context")


class ToolCallInfo(BaseModel):
    name: str
    status: str = Field(..., description="success or fail")
    args: Dict[str, Any] = Field(default_factory=dict)


class ChatSimpleResponse(BaseModel):
    status: str = Field(..., json_schema_extra={"example": "success"})
    response: str = Field(..., json_schema_extra={"example": "Refund of $50.00 for ticket #102 processed successfully."})


class SupportResponse(BaseModel):
    status: str = Field(..., json_schema_extra={"example": "success"})
    response: str = Field(..., json_schema_extra={"example": "Refund of $50.00 for ticket #102 processed successfully."})
    session_id: str = Field(..., json_schema_extra={"example": "7c2e1a3b-4d5f-6789-abcd-ef0123456789"})
    toolcalls: List[ToolCallInfo] = Field(default_factory=list)


class TicketPayload(BaseModel):
    ticket_id: Optional[str] = Field(None, description="Leave blank to auto-assign the next ID")
    customer_name: str
    customer_email: str = ""
    issue: str
    purchase_amount: float = 0
    status: str = "Open"
    eligible_for_refund: bool = True
    max_refund: Optional[float] = None


@app.get("/")
def serve_ui():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api")
def read_root():
    return {
        "service": "Smart Ticket Management Agentic System API",
        "status": "online",
        "langsmith_tracing": "enabled" if is_langsmith_enabled() else "disabled (set LANGCHAIN_API_KEY in .env)",
        "ui": "/",
        "endpoints": {
            "agent_chat": "POST /api/support-agent",
            "tickets": "GET/POST /api/tickets",
            "health_check": "GET /health",
        },
    }


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "langsmith_enabled": is_langsmith_enabled(),
    }


@app.get("/api/tickets")
def api_list_tickets():
    return {"tickets": list_tickets()}


@app.get("/api/tickets/{ticket_id}")
def api_get_ticket(ticket_id: str):
    ticket = get_ticket(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail=f"Ticket #{ticket_id} not found.")
    return ticket


@app.post("/api/tickets", status_code=201)
def api_create_ticket(payload: TicketPayload):
    try:
        return create_ticket(payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.put("/api/tickets/{ticket_id}")
def api_update_ticket(ticket_id: str, payload: TicketPayload):
    try:
        data = payload.model_dump()
        data.pop("ticket_id", None)
        return update_ticket(ticket_id, data)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.delete("/api/tickets/{ticket_id}")
def api_delete_ticket(ticket_id: str):
    try:
        delete_ticket(ticket_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"status": "deleted", "ticket_id": ticket_id}


@app.post("/api/support-agent", response_model=SupportResponse)
def process_agent_request(payload: SupportRequest):
    if not payload.message or not payload.message.strip():
        raise HTTPException(status_code=400, detail="The 'message' field cannot be empty.")

    try:
        result = run_agentic_flow(payload.message, session_id=payload.session_id)
        return SupportResponse(
            status="success",
            response=result["response"],
            session_id=result["session_id"],
            toolcalls=result.get("toolcalls") or [],
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred while executing the agentic request: {str(e)}",
        )


@app.post("/api/agent/chat", response_model=ChatSimpleResponse)
def process_agent_chat(payload: SupportRequest):
    if not payload.message or not payload.message.strip():
        raise HTTPException(status_code=400, detail="The 'message' field cannot be empty.")

    try:
        result = run_agentic_flow(payload.message, session_id=payload.session_id)
        return ChatSimpleResponse(
            status="success",
            response=result["response"],
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred while executing the agentic request: {str(e)}",
        )


@app.delete("/api/support-agent/sessions/{session_id}")
def reset_agent_session(session_id: str):
    clear_chat_session(session_id)
    return {"status": "cleared", "session_id": session_id}


if __name__ == "__main__":
    from app import ensure_lan_access, print_lan_urls
    import uvicorn

    ensure_lan_access()
    print_lan_urls(port=8000)
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
