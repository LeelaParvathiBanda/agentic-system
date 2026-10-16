"""
Agentic System Core Engine using LangChain / LangGraph with LangSmith Tracing support.
"""

import os
import re
import uuid
from typing import Any, Dict, List, Optional, Tuple

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage

from tools import ALL_TOOLS

# Load environment variables from .env
load_dotenv()


def is_langsmith_enabled() -> bool:
    """Check if LangSmith tracing environment variables are properly set."""
    tracing = os.getenv("LANGCHAIN_TRACING_V2", "false").lower() == "true"
    api_key = os.getenv("LANGCHAIN_API_KEY", "").strip()
    return tracing and bool(api_key)


def get_llm():
    """
    Initialize the LLM based on available environment variables.
    Supports Google Gemini (default if GOOGLE_API_KEY present) or OpenAI (if OPENAI_API_KEY present).
    """
    google_key = os.getenv("GOOGLE_API_KEY", "").strip()
    openai_key = os.getenv("OPENAI_API_KEY", "").strip()

    if google_key:
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
            return ChatGoogleGenerativeAI(model="gemini-2.0-flash", temperature=0)
        except Exception as e:
            print(f"Warning: Could not initialize Gemini model ({e}). Checking OpenAI fallback...")

    if openai_key:
        try:
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(model="gpt-4o-mini", temperature=0)
        except Exception as e:
            print(f"Warning: Could not initialize OpenAI model ({e}).")

    return None


SYSTEM_PROMPT = (
    "You are an intelligent Customer Support Ticket Management Agent.\n"
    "Your goal is to assist customers and support agents with managing tickets, "
    "checking refund eligibility, looking up ticket details, and executing refunds.\n"
    "CRITICAL: Never answer ticket facts from memory or prior chat. "
    "If the user mentions a ticket id, you MUST call lookup_ticket (and other tools as needed) "
    "on this turn before you reply. Do not skip tools even if you have seen the ticket before.\n"
    "If there is no ticket id and the user asks to dump all tickets or emails, refuse and call no tools.\n"
    "Always use your available tools to retrieve accurate information before making decisions.\n"
    "Be helpful, professional, and clear in your responses."
)

# In-memory chat histories keyed by session_id so follow-up questions keep context.
_CHAT_SESSIONS: Dict[str, List[BaseMessage]] = {}
_MAX_HISTORY_MESSAGES = 20


def clear_chat_session(session_id: str) -> None:
    _CHAT_SESSIONS.pop((session_id or "").strip(), None)


def _tool_status(output: str) -> str:
    text = (output or "").strip().lower()
    if not text:
        return "fail"
    if text.startswith("error:") or "not found" in text or "refund failed" in text:
        return "fail"
    return "success"


def extract_toolcalls(messages: Optional[List[BaseMessage]]) -> List[Dict[str, Any]]:
    """Build toolcalls list: name, status (success|fail), args. Current turn only."""
    pending: Dict[str, Dict[str, Any]] = {}
    ordered: List[str] = []
    if not messages:
        return []

    def _register(call_id: str, name: str, args: Any) -> None:
        if not call_id:
            call_id = f"call_{len(ordered)}"
        if isinstance(args, str):
            try:
                import json
                args = json.loads(args)
            except Exception:
                args = {"raw": args}
        pending[call_id] = {"name": name or "", "args": args or {}, "output": ""}
        ordered.append(call_id)

    last_human = 0
    for i, message in enumerate(messages):
        if isinstance(message, HumanMessage):
            last_human = i

    for message in messages[last_human + 1 :]:
        if isinstance(message, AIMessage):
            calls = list(getattr(message, "tool_calls", None) or [])
            extra = (getattr(message, "additional_kwargs", None) or {}).get("tool_calls") or []
            if extra and not calls:
                for raw in extra:
                    fn = (raw or {}).get("function") or {}
                    _register(str(raw.get("id") or ""), fn.get("name") or "", fn.get("arguments") or {})
            for call in calls:
                if isinstance(call, dict):
                    _register(str(call.get("id") or ""), call.get("name") or "", call.get("args") or {})
                else:
                    _register(
                        str(getattr(call, "id", "") or ""),
                        getattr(call, "name", "") or "",
                        getattr(call, "args", None) or {},
                    )
        elif isinstance(message, ToolMessage):
            call_id = str(getattr(message, "tool_call_id", "") or f"tool_{len(ordered)}")
            name = getattr(message, "name", None)
            if call_id not in pending:
                pending[call_id] = {"name": name or "", "args": {}, "output": ""}
                ordered.append(call_id)
            pending[call_id]["output"] = str(message.content)
            if name:
                pending[call_id]["name"] = name

    return [
        {
            "name": pending[cid]["name"],
            "status": _tool_status(str(pending[cid].get("output") or "")),
            "args": pending[cid].get("args") or {},
        }
        for cid in ordered
        if pending[cid].get("name")
    ]


def run_agentic_flow(user_message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Executes the agentic reasoning loop and keeps conversation history for the session.
    """
    session_id = (session_id or "").strip() or str(uuid.uuid4())
    history = _CHAT_SESSIONS.setdefault(session_id, [])
    llm = get_llm()

    if llm is None:
        reply, toolcalls = handle_simulated_agent_flow(user_message, history)
        _append_turn(history, user_message, reply)
        return {"response": reply, "session_id": session_id, "toolcalls": toolcalls}

    try:
        from langgraph.prebuilt import create_react_agent

        agent_executor = create_react_agent(
            model=llm,
            tools=ALL_TOOLS,
            prompt=SYSTEM_PROMPT,
        )

        ticket_in_prompt = bool(re.search(r"(?:ticket\s*#?|#)(\d+)", user_message, re.I))
        incoming = [HumanMessage(content=user_message)] if ticket_in_prompt else [*history, HumanMessage(content=user_message)]

        result = agent_executor.invoke({
            "messages": incoming
        })

        messages: List[BaseMessage] = result.get("messages", [])
        reply = str(messages[-1].content) if messages else "Task processed, but no output text was generated."
        toolcalls = extract_toolcalls(messages)
        _append_turn(history, user_message, reply)
        return {"response": reply, "session_id": session_id, "toolcalls": toolcalls}

    except Exception as e:
        reply = f"Agent Execution Error: {str(e)}"
        _append_turn(history, user_message, reply)
        return {"response": reply, "session_id": session_id, "toolcalls": []}


def _append_turn(history: List[BaseMessage], user_message: str, reply: str) -> None:
    history.append(HumanMessage(content=user_message))
    history.append(AIMessage(content=reply))
    if len(history) > _MAX_HISTORY_MESSAGES:
        del history[:-_MAX_HISTORY_MESSAGES]


def handle_simulated_agent_flow(
    user_message: str, history: Optional[List[BaseMessage]] = None
) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Simulated agent execution flow used when LLM API keys are not yet added to .env.
    Demonstrates tool execution and reasoning logic.
    """
    from tools import lookup_ticket, check_refund_eligibility, process_refund

    msg_lower = user_message.lower()
    ticket_match = re.search(r'(?:ticket\s*#?|#)(\d+)', msg_lower)
    ticket_id = ticket_match.group(1) if ticket_match else None
    if not ticket_id and history:
        for message in reversed(history):
            prior = re.search(r'(?:ticket\s*#?|#)(\d+)', str(message.content).lower())
            if prior:
                ticket_id = prior.group(1)
                break
    ticket_id = ticket_id or "102"
    toolcalls: List[Dict[str, Any]] = []

    def _record(name: str, args: Dict[str, Any], output: str) -> None:
        toolcalls.append({"name": name, "status": _tool_status(output), "args": args})

    if "refund" in msg_lower:
        t_info = lookup_ticket.invoke({"ticket_id": ticket_id})
        _record("lookup_ticket", {"ticket_id": ticket_id}, t_info)
        t_elig = check_refund_eligibility.invoke({"ticket_id": ticket_id})
        _record("check_refund_eligibility", {"ticket_id": ticket_id}, t_elig)
        if "IS ELIGIBLE" in t_elig:
            args = {"ticket_id": ticket_id, "amount": 50.0, "reason": "User request"}
            t_proc = process_refund.invoke(args)
            _record("process_refund", args, t_proc)
            return f"[Simulated ReAct Agent]\n1. {t_info}\n2. {t_elig}\n3. {t_proc}", toolcalls
        return f"[Simulated ReAct Agent]\n1. {t_info}\n2. {t_elig}", toolcalls

    t_info = lookup_ticket.invoke({"ticket_id": ticket_id})
    _record("lookup_ticket", {"ticket_id": ticket_id}, t_info)
    return f"[Simulated ReAct Agent]\n{t_info}", toolcalls
