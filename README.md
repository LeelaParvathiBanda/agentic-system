# Smart Ticket Management Agentic System 🤖🎫

An intelligent, production-ready Agentic System built with **Python**, **FastAPI**, **LangChain / LangGraph**, and **LangSmith Tracing**.

---

## 🌟 Key Features

1. **True Agentic ReAct Reasoning Loop**:
   - Accepts natural language support requests.
   - Autonomously selects backend tools (`lookup_ticket`, `check_refund_eligibility`, `process_refund`, `update_ticket_status`).
   - Executes multi-step reasoning before providing the final resolution.

2. **LangSmith Trace Logging**:
   - Automatically records full execution traces, step-by-step tool calls, latency timing, and token metrics to your LangSmith Dashboard.

3. **Clean & Lightweight API Contract**:
   - The API response remains clean and concise, while all deep telemetry is captured in LangSmith.

---

## 📁 Project Structure

```
Agentic System/
├── main.py            # FastAPI Web Server & Endpoints
├── agent.py           # ReAct Agent Engine (LangChain / LangGraph)
├── tools.py           # Backend Tools (@tool decorators)
├── test_agent.py      # Automated Test Suite
├── requirements.txt   # Dependencies
├── .env.example       # Environment Template
└── .env               # Configuration File (API Keys)
```

---

## ⚙️ Quick Setup Guide

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Environment Variables (`.env`)
Open `.env` and fill in your API keys:

```env
# Enable LangSmith Tracing
LANGCHAIN_TRACING_V2=true
LANGCHAIN_ENDPOINT=https://api.smith.langchain.com
LANGCHAIN_API_KEY=your_langsmith_api_key_here
LANGCHAIN_PROJECT=ticket-management-agent

# LLM API Keys (Gemini or OpenAI)
GOOGLE_API_KEY=your_gemini_api_key_here
# OPENAI_API_KEY=your_openai_api_key_here
```

---

## 🚀 Running the System

### Start the FastAPI Server
```bash
python main.py
```
Or with Uvicorn directly:
```bash
uvicorn main:app --reload --port 8000
```

The interactive API documentation will be available at:
- **Swagger UI:** `http://127.0.0.1:8000/docs`
- **ReDoc:** `http://127.0.0.1:8000/redoc`

---

## 📡 API Usage Example

### Request
`POST /api/support-agent`

```json
{
  "message": "Can you check ticket #102 and issue a refund of $50?"
}
```

### Response
```json
{
  "status": "success",
  "response": "Ticket #102 details have been verified: Bob Smith was double billed. Refund of $50.00 has been processed successfully under transaction ID tx_rf_102_998."
}
```

---

## 🧪 Running Tests

Run the test suite to verify tool execution, agent workflow, and API routes:

```bash
python test_agent.py
```
