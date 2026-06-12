# Agent Execution Ledger: User Guide

The Agent Execution Ledger provides tamper-evident logging, semantic drift detection, and causal blame attribution for autonomous AI pipelines. This guide will walk you through setting up the project, running it in testing environments, and integrating it seamlessly into your production applications.

---

## 1. Running the Platform

You can either use the live deployed instances or run the platform locally.

### Cloud Deployment (Recommended)
- **Frontend Dashboard:** [https://agent-ledger-frontend.onrender.com/](https://agent-ledger-frontend.onrender.com/)
- **Backend API:** [https://agent-ledger-backend.onrender.com](https://agent-ledger-backend.onrender.com)

When using the cloud deployment, you don't need to run the servers yourself. You can point your scripts to the deployed backend URL.

### Running Locally

To see the live streaming capabilities and use the dashboard locally, you'll need to run both the FastAPI backend and the React frontend.

#### Prerequisites
- Python 3.9+
- Node.js 18+
- MongoDB instance (local or Atlas)

### Starting the Backend
The backend processes tool executions, runs semantic drift, and handles live WebSocket connections.

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Start the server (runs on port 8000 by default)
fastapi dev main.py
```

### Starting the Frontend
The frontend provides a rich, real-time dashboard visualization.

```bash
cd frontend
npm install
npm run dev
```

Your dashboard will now be accessible at `http://localhost:5173`.

---

## 2. Testing the System (Simulations)

The platform comes with built-in test scripts that simulate AI agent behavior and send live data to your dashboard. This is the fastest way to see the dashboard "light up" with activity.

### Running the Simulator
To test basic adapters (LangChain, CrewAI, Proxy) without hitting real LLMs:

```bash
# Ensure the backend server is running first!
python "Testing Phase/tests/simulate_frameworks.py"
```

### Running Real LLM Integrations
To see a real Groq Llama 3.3 agent execute tools and be intercepted by the Ledger:

```bash
# Ensure the backend server is running first!
python "Testing Phase/tests/real_groq_test.py"
```

> [!NOTE]
> When you run these test scripts, the data diffuses instantly to the frontend dashboard. The live WebSocket streaming allows you to see semantic drift, latency issues, and tool executions in real-time!

---

## 3. Production Integration Guide

Integrating the Agent Execution Ledger into your production system is straightforward. We offer native wrappers for popular frameworks and a universal proxy for everything else.

### Option A: Using the LangChain Adapter
If you use LangChain or LangGraph, the Ledger transparently wraps your tools without requiring you to change your agent logic.

```python
from core.adapters import LangChainAdapter
from core.ledger_store import LedgerStore

# 1. Initialize Ledger
ledger_store = LedgerStore(db, broadcast_fn=your_broadcast_function)
adapter = LangChainAdapter(ledger_store)

# 2. Define a standard LangChain tool
@tool
def calculate_metrics(data: str) -> str:
    return "Metrics calculated."

# 3. Wrap it with Cryptographic boundaries
wrapped_tool = adapter.wrap_tool(
    calculate_metrics, 
    metadata={"run_id": "prod-run-123", "agent_id": "DataAnalystAgent"}
)

# 4. Pass 'wrapped_tool' to your LangChain agent instead of the raw tool!
```

### Option B: Using the CrewAI Adapter
Similarly, for CrewAI setups:

```python
from core.adapters import CrewAIAdapter

adapter = CrewAIAdapter(ledger_store)

# Wrap any Python function
secure_tool = adapter.wrap_tool(
    my_function,
    metadata={"run_id": "crew-run-456", "agent_id": "ResearchSpecialist"}
)
```

### Option C: Universal HTTP Proxy Adapter
If your agents are written in JavaScript, Go, or any other language, simply point them to the Ledger API endpoint instead of the raw tool API.

Make a POST request to the `/proxy` endpoint on the Ledger backend. If using the cloud backend, use `https://agent-ledger-backend.onrender.com/proxy`.

```http
POST https://agent-ledger-backend.onrender.com/proxy
X-API-Key: your_api_key
X-Agent-ID: nodejs_agent_01
X-Run-ID: global-pipeline-id
Content-Type: application/json

{
    "tool_name": "database_query_tool",
    "input_body": { "query": "SELECT * FROM users" },
    "forward_url": "https://api.your-internal-tool.com/execute"
}
```

The Ledger will intercept the request, log it cryptographically, optionally calculate semantic drift, forward it to `forward_url`, and return the response back to your agent.

---

## 4. Key Concepts

### Semantic Drift Detection (all-MiniLM-L6-v2)
Every time a tool returns output, our Semantic Drift Engine embeds the output and compares it to the agent's expected interpretation. This ensures that agents aren't "hallucinating" or misinterpreting tool responses. We utilize the lightning-fast `all-MiniLM-L6-v2` SentenceTransformer for this calculation.

### Tamper-Evident Receipts
Each step an agent takes generates a cryptographically signed "receipt." These receipts are chained together using SHA-256 hashes, ensuring that no execution logs can be tampered with or silently dropped.

### Causal Blame Attribution
If an agent pipeline fails at step 10, but the actual hallucination occurred at step 3, our causal blame engine will trace the DAG (Directed Acyclic Graph) and highlight step 3 as the root cause in the dashboard.
