# DevSecOps Knowledge Chat

A multi-agent conversational AI system built with FastAPI and LangGraph. Features intelligent routing, RAG-based policy retrieval with Flash Reranking, and token-aware context management.

## Features

- **Multi-Agent Architecture** - LangGraph supervisor routes requests to specialized agents
- **Agent Chaining** - Sequential multi-agent execution for complex requests (e.g., "show scans and create tickets")
- **RAG with Flash Reranking** - Semantic search with LLM-based relevance scoring
- **Token-Aware Context Management** - Automatic summarization for long conversations
- **Streaming Responses** - Server-Sent Events for real-time token streaming
- **Cost Tracking** - Per-request and session token/cost metrics
- **Observability** - LangSmith tracing integration
- **Security Guardrails** - Prompt injection detection, PII redaction

## Screenshots

### Chat Interface
![Chat Interface](../docs/images/chat-interface.png)

### Tool Calls & Token Usage
![Tool Calls](../docs/images/tool-calls.png)

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              API Layer (FastAPI)                            │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐      │
│  │ /chat    │  │ /chat/   │  │ /auth    │  │/policies │  │ /tickets │      │
│  │          │  │ stream   │  │          │  │          │  │          │      │
│  └────┬─────┘  └────┬─────┘  └──────────┘  └──────────┘  └──────────┘      │
└───────┼─────────────┼──────────────────────────────────────────────────────┘
        │             │
        ▼             ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Service Layer                                      │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                      AgentService                                    │    │
│  │  • Input validation (guardrails)                                     │    │
│  │  • Context management                                                │    │
│  │  • Response formatting                                               │    │
│  └───────────────────────────┬─────────────────────────────────────────┘    │
└──────────────────────────────┼──────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Agent Layer (LangGraph)                              │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                        SUPERVISOR                                    │    │
│  │            Intent Classification & Routing                           │    │
│  │                                                                      │    │
│  │   "What vulnerabilities..." → scan_agent                            │    │
│  │   "What is our policy..." → policy_agent                            │    │
│  │   "Create a ticket..." → ticket_agent                               │    │
│  │   "Hello" → FINISH (direct response)                                │    │
│  └──────────────────────────┬──────────────────────────────────────────┘    │
│                             │                                                │
│         ┌───────────────────┼───────────────────┐                           │
│         ▼                   ▼                   ▼                           │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐                      │
│  │ Scan Agent  │    │Policy Agent │    │Ticket Agent │                      │
│  │             │    │             │    │             │                      │
│  │ Analyzes    │    │ RAG search  │    │ CRUD ops    │                      │
│  │ Azure       │    │ over        │    │ for JIRA/   │                      │
│  │ Defender    │    │ security    │    │ ServiceNow  │                      │
│  │ scan data   │    │ policies    │    │ tickets     │                      │
│  └──────┬──────┘    └──────┬──────┘    └──────┬──────┘                      │
│         │                  │                  │                              │
└─────────┼──────────────────┼──────────────────┼──────────────────────────────┘
          │                  │                  │
          ▼                  ▼                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            Tool Layer                                        │
│                                                                              │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐           │
│  │ get_latest_scan  │  │ retrieve_policy  │  │ create_ticket    │           │
│  │ get_findings_by_ │  │ retrieve_policy_ │  │ get_ticket       │           │
│  │   severity       │  │   fast           │  │ list_tickets     │           │
│  │ get_scan_summary │  │                  │  │ delete_ticket    │           │
│  └────────┬─────────┘  └────────┬─────────┘  └────────┬─────────┘           │
│           │                     │                     │                      │
└───────────┼─────────────────────┼─────────────────────┼──────────────────────┘
            │                     │                     │
            ▼                     ▼                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Repository Layer                                     │
│                                                                              │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐           │
│  │  Mock Scanner    │  │ Policy Repo      │  │ Ticket Repo      │           │
│  │  (JSON data)     │  │ + VectorRepo     │  │ (SQLite)         │           │
│  │                  │  │ (ChromaDB)       │  │                  │           │
│  │                  │  │                  │  │                  │           │
│  │                  │  │ ┌──────────────┐ │  │                  │           │
│  │                  │  │ │Flash Reranker│ │  │                  │           │
│  │                  │  │ │(LLM-based)   │ │  │                  │           │
│  │                  │  │ └──────────────┘ │  │                  │           │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘           │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Agent Orchestration Flow

The supervisor supports **agent chaining** for multi-part requests. After each agent completes,
control returns to the supervisor which decides if another agent is needed.

```
                    ┌──────────────────┐
                    │   User Message   │
                    │                  │
                    │ "Show scans and  │
                    │  check policy    │
                    │  violations"     │
                    └────────┬─────────┘
                             │
                             ▼
                    ┌──────────────────┐
                    │ Context Manager  │
                    │                  │
                    │ • Load history   │
                    │ • Include summary│
                    │   if available   │
                    └────────┬─────────┘
                             │
                             ▼
               ┌─────────────────────────────┐
               │                             │
               │         SUPERVISOR          │◄──────────────────────┐
               │                             │                       │
               │  Structured Output:         │                       │
               │  RouteDecision {            │                       │
               │    next_agent: "...",       │                       │
               │    reasoning: "..."         │                       │
               │  }                          │                       │
               │                             │                       │
               │  Checks:                    │                       │
               │  • Original request         │                       │
               │  • What agents responded    │         Loop back     │
               │  • What still needs done    │         for next      │
               │  • agent_calls < 3          │         agent         │
               └─────────────┬───────────────┘                       │
                             │                                       │
            ┌────────────────┼────────────────┐                      │
            ▼                ▼                ▼                      │
    ┌──────────────┐ ┌──────────────┐ ┌──────────────┐              │
    │  scan_agent  │ │ policy_agent │ │ ticket_agent │              │
    └──────┬───────┘ └──────┬───────┘ └──────┬───────┘              │
           │                │                │                       │
           ▼                ▼                ▼                       │
    ┌──────────────┐ ┌──────────────┐ ┌──────────────┐              │
    │  Tool Calls  │ │  Tool Calls  │ │  Tool Calls  │              │
    │              │ │              │ │              │              │
    │get_latest_   │ │retrieve_     │ │create_ticket │              │
    │  scan()      │ │  policy()    │ │get_ticket()  │              │
    └──────┬───────┘ └──────┬───────┘ └──────┬───────┘              │
           │                │                │                       │
           ▼                ▼                ▼                       │
    ┌──────────────┐ ┌──────────────┐ ┌──────────────┐              │
    │ Tool Results │ │ Tool Results │ │ Tool Results │              │
    │              │ │+ Rerank Score│ │              │              │
    │              │ │+ Metrics     │ │              │              │
    └──────┬───────┘ └──────┬───────┘ └──────┬───────┘              │
           │                │                │                       │
           ▼                ▼                ▼                       │
    ┌──────────────┐ ┌──────────────┐ ┌──────────────┐              │
    │ Agent        │ │ Agent        │ │ Agent        │              │
    │ Response     │ │ Response     │ │ Response     │              │
    └──────┬───────┘ └──────┬───────┘ └──────┬───────┘              │
           │                │                │                       │
           └────────────────┴────────────────┘                       │
                            │                                        │
                            │ agent_calls++                          │
                            │                                        │
                            └────────────────────────────────────────┘
                            │
                            │ (when next_agent == "FINISH")
                            ▼
                   ┌──────────────────┐
                   │ Context Update   │
                   │                  │
                   │ • Add exchange   │
                   │ • Check tokens   │
                   │ • Summarize if   │
                   │   > 80K tokens   │
                   └────────┬─────────┘
                            │
                            ▼
                   ┌──────────────────┐
                   │    Response      │
                   │                  │
                   │ • AI message     │
                   │ • Tool calls     │
                   │ • Token usage    │
                   │ • Context stats  │
                   │ • Trace URL      │
                   └──────────────────┘
```

**Example: Multi-Agent Chaining**

User: "Show me scan results and explain which findings violate our security policies"

1. **Supervisor** → routes to `scan_agent`
2. **scan_agent** → calls `get_latest_scan()`, returns findings
3. **Supervisor** → sees scan complete, routes to `policy_agent`
4. **policy_agent** → calls `retrieve_policy()`, analyzes violations
5. **Supervisor** → all parts addressed, returns `FINISH`

## Example Questions

Try these queries to explore different agent capabilities:

### Security Scan Analysis (scan_agent)

| Question | What it demonstrates |
| -------- | -------------------- |
| "What vulnerabilities were found in the latest scan?" | Full scan retrieval with CVE details |
| "Show me only critical and high severity findings" | Filtered severity search |
| "Give me a quick security overview" | Summary without details |
| "Are there any SQL injection vulnerabilities?" | Specific vulnerability search |

### Policy Compliance (policy_agent)

| Question | What it demonstrates |
| -------- | -------------------- |
| "What is our password policy?" | RAG search with reranking |
| "What are the encryption requirements for data at rest?" | Policy retrieval with context |
| "How should we handle access control and MFA?" | Multi-topic policy search |
| "Are we compliant with SOC 2 requirements?" | Compliance-focused query |

### Ticket Management (ticket_agent)

| Question | What it demonstrates |
| -------- | -------------------- |
| "Create a JIRA ticket for the SQL injection vulnerability" | Ticket creation |
| "List all open security tickets" | Filtered ticket listing |
| "Show me ticket SEC-001" | Single ticket retrieval |
| "Create a high priority ticket for the expired SSL certificate" | Priority-based creation |

### Multi-Agent Chaining

| Question | Agents involved |
| -------- | --------------- |
| "Show me scan results and check which ones violate our policies" | scan_agent → policy_agent |
| "Find critical vulnerabilities and create tickets for each" | scan_agent → ticket_agent |
| "What's our encryption policy and are there any related scan findings?" | policy_agent → scan_agent |
| "Review the latest scan, identify policy violations, and create remediation tickets" | scan_agent → policy_agent → ticket_agent |

## Tool Implementations

### Scanner Tools (`app/tools/scanner.py`)

| Tool                                 | Description                                               |
| ------------------------------------ | --------------------------------------------------------- |
| `get_latest_scan()`                  | Returns full Azure Defender scan results with CVE details |
| `get_findings_by_severity(severity)` | Filters findings by Critical/High/Medium/Low              |
| `get_scan_summary()`                 | Quick overview: counts by severity, no details            |

### Policy RAG Tools (`app/tools/policy_rag.py`)

| Tool                          | Description                                                                                            |
| ----------------------------- | ------------------------------------------------------------------------------------------------------ |
| `retrieve_policy(query)`      | Semantic search with Flash Reranking. Returns policies with `rerank_score` (0-1) and retrieval metrics |
| `retrieve_policy_fast(query)` | Embedding-only search, no reranking. Faster but less accurate                                          |

### Ticket Tools (`app/tools/tickets.py`)

| Tool                                                | Description                        |
| --------------------------------------------------- | ---------------------------------- |
| `create_ticket(type, title, description, priority)` | Create JIRA or ServiceNow ticket   |
| `get_ticket(ticket_id)`                             | Retrieve ticket by ID              |
| `list_tickets(status, limit)`                       | List tickets with optional filters |
| `delete_ticket(ticket_id)`                          | Delete a ticket                    |

## RAG Pipeline with Flash Reranking

```
Query: "What is our password policy?"
                │
                ▼
┌──────────────────────────────────────┐
│         Embedding Search             │
│                                      │
│  ChromaDB → Top 10 candidates        │
│  (Azure text-embedding-ada-002)      │
│                                      │
│  Results sorted by cosine distance   │
└─────────────────┬────────────────────┘
                  │
                  ▼
┌──────────────────────────────────────┐
│         Flash Reranker               │
│                                      │
│  Single LLM call scores all 10 docs  │
│                                      │
│  Prompt: "Score relevance 0.0-1.0"   │
│  Response: [0.92, 0.34, 0.87, ...]   │
│                                      │
│  Re-sort by rerank_score             │
│  Return top 3                        │
└─────────────────┬────────────────────┘
                  │
                  ▼
┌──────────────────────────────────────┐
│         Retrieval Metrics            │
│                                      │
│  • embedding_latency_ms: 120         │
│  • rerank_latency_ms: 450            │
│  • top_score: 0.92                   │
│  • rank_changes: 3                   │
│  • avg_rerank_score: 0.71            │
└──────────────────────────────────────┘
```

## Context Management

The system uses token-aware context management to handle long conversations efficiently.

### Strategy: Hybrid (Default)

```
Conversation grows to 85K tokens (> 80K target)
                │
                ▼
┌──────────────────────────────────────┐
│         Summarization                │
│                                      │
│  Messages 1-20 → LLM Summary (~500   │
│                   tokens)            │
│                                      │
│  Messages 21-26 → Kept verbatim      │
│  (keep_recent=6)                     │
└─────────────────┬────────────────────┘
                  │
                  ▼
┌──────────────────────────────────────┐
│         New Context (~15K)           │
│                                      │
│  [System] Previous summary: ...      │
│  [User] Message 21                   │
│  [Assistant] Message 22              │
│  ...                                 │
│  [User] Current message              │
└──────────────────────────────────────┘
```

### Configuration

| Parameter       | Default      | Description                                |
| --------------- | ------------ | ------------------------------------------ |
| `strategy`      | `hybrid`     | `sliding_window`, `summarize`, or `hybrid` |
| `target_tokens` | 80,000       | Trigger compression above this             |
| `keep_recent`   | 6            | Messages to keep unsummarized              |
| `model_limits`  | GPT-4o: 128K | Auto-detected from deployment name         |

## API Endpoints

### Chat

| Method | Endpoint       | Description                                            |
| ------ | -------------- | ------------------------------------------------------ |
| POST   | `/chat/`       | Synchronous chat - returns complete response           |
| POST   | `/chat/stream` | Streaming chat - SSE with tokens, tool calls, metadata |

**Request Body:**

```json
{
  "message": "What vulnerabilities were found in the latest scan?",
  "conversation_history": [
    { "role": "user", "content": "Hello" },
    { "role": "assistant", "content": "Hi! How can I help?" }
  ]
}
```

**Response:**

```json
{
  "response": "The latest scan found 3 critical vulnerabilities...",
  "tool_calls": [{ "tool_name": "get_latest_scan", "arguments": {} }],
  "token_usage": {
    "input_tokens": 1250,
    "output_tokens": 320,
    "total_tokens": 1570,
    "llm_calls": 3,
    "cost": { "input": 0.003125, "output": 0.0032, "total": 0.006325 }
  },
  "context_stats": {
    "current_tokens": 2100,
    "target_tokens": 80000,
    "utilization_pct": 2.6,
    "has_summary": false
  },
  "trace_url": "https://smith.langchain.com/..."
}
```

### Streaming Events

| Event       | Data                                                |
| ----------- | --------------------------------------------------- |
| `token`     | `{"token": "The"}`                                  |
| `tool_call` | `{"tool_name": "get_latest_scan", "arguments": {}}` |
| `metadata`  | Token usage, trace URL, context stats               |
| `done`      | `{"status": "complete"}`                            |
| `error`     | `{"error": "message"}`                              |

### Authentication

| Method | Endpoint         | Description           |
| ------ | ---------------- | --------------------- |
| POST   | `/auth/register` | Create new user       |
| POST   | `/auth/login`    | Get JWT token         |
| GET    | `/auth/me`       | Get current user info |

### Policies

| Method | Endpoint     | Description                               |
| ------ | ------------ | ----------------------------------------- |
| GET    | `/policies/` | List all policies                         |
| POST   | `/policies/` | Create policy (also adds to vector store) |

### Tickets

| Method | Endpoint        | Description      |
| ------ | --------------- | ---------------- |
| GET    | `/tickets/`     | List tickets     |
| POST   | `/tickets/`     | Create ticket    |
| GET    | `/tickets/{id}` | Get ticket by ID |
| DELETE | `/tickets/{id}` | Delete ticket    |

## Configuration

### Environment Variables

Create a `.env` file in the backend directory:

```bash
# Azure OpenAI (Required)
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com
AZURE_OPENAI_API_KEY=your-api-key
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4o
AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT_NAME=text-embedding-ada-002
OPENAI_API_VERSION=2024-08-01-preview

# Database
DATABASE_URL=sqlite:///./devsecops.db
CHROMA_PERSIST_DIR=./chroma_db

# JWT Authentication
JWT_SECRET_KEY=your-secret-key-here
JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=24

# LangSmith Tracing (Optional)
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=your-langsmith-key
LANGSMITH_PROJECT=devsecops-chat
```

### Azure OpenAI Setup

1. Create an Azure OpenAI resource
2. Deploy models:
   - `gpt-4o` (or `gpt-4o-mini`) for chat/routing
   - `text-embedding-ada-002` for embeddings
3. Copy endpoint and API key to `.env`

## Installation

```bash
# Clone and navigate
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your Azure OpenAI credentials

# Run server
uvicorn app.main:app --reload --port 8000
```

## Project Structure

```
backend/
├── app/
│   ├── api/                 # FastAPI route handlers
│   │   ├── auth.py          # JWT authentication
│   │   ├── chat.py          # Chat endpoints (sync + stream)
│   │   ├── policies.py      # Policy CRUD
│   │   └── tickets.py       # Ticket CRUD
│   │
│   ├── agents/              # LangGraph multi-agent system
│   │   ├── supervisor.py    # Main orchestrator + context mgmt
│   │   ├── scan_agent.py    # Security scan analysis
│   │   ├── policy_agent.py  # Policy compliance (RAG)
│   │   ├── ticket_agent.py  # Ticket management
│   │   └── state.py         # Shared TypedDict state
│   │
│   ├── core/                # Core utilities
│   │   ├── config.py        # Pydantic settings
│   │   ├── llm.py           # Azure OpenAI initialization
│   │   ├── db.py            # SQLAlchemy setup
│   │   ├── security.py      # JWT + password hashing
│   │   ├── reranker.py      # Flash Reranker implementation
│   │   ├── context_manager.py  # Token-aware context mgmt
│   │   └── utils.py         # Guardrails, caching, retry
│   │
│   ├── tools/               # Agent tool implementations
│   │   ├── scanner.py       # Mock Azure Defender tools
│   │   ├── policy_rag.py    # Policy search with reranking
│   │   └── tickets.py       # Ticket CRUD tools
│   │
│   ├── repositories/        # Data access layer
│   │   ├── policy_repo.py   # Policy + vector search
│   │   ├── ticket_repo.py   # Ticket operations
│   │   └── vector_repo.py   # ChromaDB wrapper
│   │
│   ├── models/              # Data models
│   │   ├── database.py      # SQLAlchemy ORM models
│   │   └── schemas.py       # Pydantic validation schemas
│   │
│   └── data/                # Mock data
│       ├── mock_scan.json   # Sample scan results
│       └── security_policies.py  # Policy fixtures
│
├── tests/
│   ├── test_api.py          # API endpoint tests
│   └── test_routing_eval.py # Agent routing + unit tests
│
├── requirements.txt
└── README.md
```

## Technical Details

### Token Tracking

All LLM calls are monitored via `TokenTracker` callback:

```python
{
  "input_tokens": 1250,
  "output_tokens": 320,
  "total_tokens": 1570,
  "llm_calls": 3,  # supervisor + agent + tool response
  "cost": {
    "input": 0.003125,   # $2.50/1M tokens
    "output": 0.0032,    # $10.00/1M tokens
    "total": 0.006325
  }
}
```

### Security Guardrails

Input validation in `ContentGuardrails`:

- **Prompt Injection Detection**: 11 regex patterns for common attacks
- **PII Detection**: Email, phone, SSN, credit card patterns
- **PII Redaction**: Automatic redaction in outputs
- **Length Limits**: 4000 chars for messages, 10000 for sanitization

### Retry Logic

Exponential backoff via tenacity:

```python
@with_retry(max_attempts=3, min_wait=1, max_wait=10)
def api_call():
    ...
```

### Embedding Cache

TTL cache for embeddings to reduce API calls:

```python
TTLCache(maxsize=10000, ttl=3600)  # 1 hour, 10K entries
```

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app

# Run specific test class
pytest tests/test_routing_eval.py::TestFlashReranker -v
```

## License

MIT
