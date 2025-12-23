"""
Multi-agent supervisor for DevSecOps chat orchestration.

This module implements a LangGraph-based supervisor that routes user requests
to specialized agents (scan, policy, ticket) based on intent classification.
Includes token tracking, cost calculation, and context management.
"""

from typing import Literal, Optional, AsyncGenerator
import uuid
import json
import asyncio

from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.callbacks import BaseCallbackHandler
from pydantic import BaseModel

from app.core.llm import get_llm
from app.core.config import settings
from app.core.context_manager import SessionContextManager, count_tokens
from app.agents.state import AgentState, add_messages
from app.agents.scan_agent import create_scan_agent
from app.agents.policy_agent import create_policy_agent
from app.agents.ticket_agent import create_ticket_agent

# GPT-4o pricing (per 1M tokens)
PRICING = {
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4": {"input": 30.00, "output": 60.00},
}


class TokenTracker(BaseCallbackHandler):
    """
    Callback handler for tracking LLM token usage.

    Monitors all LLM calls during agent execution and accumulates
    input/output token counts for cost calculation.

    Attributes:
        total_input_tokens: Cumulative input tokens across all calls.
        total_output_tokens: Cumulative output tokens across all calls.
        llm_calls: Number of LLM invocations.
    """

    def __init__(self):
        """Initialize token counters to zero."""
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.llm_calls = 0

    def on_llm_end(self, response, **kwargs) -> None:
        """
        Callback triggered after each LLM call completes.

        Extracts token usage from the response and updates counters.

        Args:
            response: LLM response containing usage metadata.
            **kwargs: Additional callback arguments (unused).
        """
        self.llm_calls += 1
        if hasattr(response, 'llm_output') and response.llm_output:
            usage = response.llm_output.get('token_usage', {})
            self.total_input_tokens += usage.get('prompt_tokens', 0)
            self.total_output_tokens += usage.get('completion_tokens', 0)
        for gen in response.generations:
            for g in gen:
                if hasattr(g, 'message') and hasattr(g.message, 'usage_metadata'):
                    metadata = g.message.usage_metadata
                    if metadata:
                        self.total_input_tokens += metadata.get('input_tokens', 0)
                        self.total_output_tokens += metadata.get('output_tokens', 0)


class RouteDecision(BaseModel):
    """
    Structured output schema for supervisor routing decisions.

    Attributes:
        next_agent: The agent to route to, or FINISH if complete.
        reasoning: Explanation for the routing decision.
    """

    next_agent: Literal["scan_agent", "policy_agent", "ticket_agent", "FINISH"]
    reasoning: str


# Track which agents have been called to prevent infinite loops
MAX_AGENT_CALLS = 3


SUPERVISOR_PROMPT = """You are a DevSecOps supervisor that routes requests to specialized agents.

Available agents:
- scan_agent: For security scan queries (vulnerabilities, CVEs, Azure Defender results)
- policy_agent: For security policy questions (compliance, rules, requirements)
- ticket_agent: For ticket operations (create, view, list JIRA/ServiceNow tickets)

Analyze the user's request and conversation history to decide:
1. Which agent should handle the NEXT step
2. If ALL parts of the request have been addressed, choose FINISH

IMPORTANT: For multi-part requests, you will be called multiple times. After each agent completes,
check if there are remaining parts of the original request that need another agent.

## Examples

User: "What critical vulnerabilities were found in the latest scan?"
→ Route to: scan_agent (security scan query)

User: "What is our password policy?"
→ Route to: policy_agent (policy question)

User: "Create a JIRA ticket for the SQL injection vulnerability"
→ Route to: ticket_agent (ticket creation)

User: "Hello, how are you?"
→ Route to: FINISH (simple greeting)

User: "Show me high severity findings and create tickets for each"
→ First call: Route to scan_agent (get the findings first)
→ After scan_agent responds: Route to ticket_agent (now create tickets)
→ After ticket_agent responds: Route to FINISH (all parts complete)

User: "Show me scan results and explain which ones violate our security policies"
→ First call: Route to scan_agent (get scan results)
→ After scan_agent responds: Route to policy_agent (analyze policy violations)
→ After policy_agent responds: Route to FINISH (all parts complete)

When deciding, look at:
- The original user request
- What agents have already responded (in conversation history)
- What parts of the request still need to be addressed

Respond with your routing decision."""


def create_supervisor():
    """
    Create and compile the multi-agent supervisor graph with chaining support.

    Builds a LangGraph StateGraph with:
    - Supervisor node for intent classification and routing
    - Scan agent node for security scan analysis
    - Policy agent node for compliance queries
    - Ticket agent node for ticket management

    Agents loop back to supervisor for potential chaining to handle
    multi-part requests (e.g., "show scans and create tickets").

    Returns:
        Compiled LangGraph ready for invocation.
    """
    llm = get_llm()
    router_llm = llm.with_structured_output(RouteDecision).with_config(
        {"run_name": "SupervisorRouter"}
    )

    scan_agent = create_scan_agent()
    policy_agent = create_policy_agent()
    ticket_agent = create_ticket_agent()

    def supervisor_node(state: AgentState) -> dict:
        """Route user request to appropriate specialized agent."""
        agent_calls = state.get("agent_calls", 0)

        # Prevent infinite loops - force finish after max calls
        if agent_calls >= MAX_AGENT_CALLS:
            return {"next_agent": "FINISH", "agent_calls": agent_calls}

        messages = [SystemMessage(content=SUPERVISOR_PROMPT)] + state["messages"]
        decision = router_llm.invoke(messages)
        return {"next_agent": decision.next_agent, "agent_calls": agent_calls}

    def scan_node(state: AgentState) -> dict:
        """Execute security scan analysis agent."""
        result = scan_agent.invoke(
            {"messages": state["messages"], "next_agent": "", "agent_calls": 0},
            config={"run_name": "ScanAgent"}
        )
        return {
            "messages": result["messages"],
            "agent_calls": state.get("agent_calls", 0) + 1
        }

    def policy_node(state: AgentState) -> dict:
        """Execute security policy compliance agent."""
        result = policy_agent.invoke(
            {"messages": state["messages"], "next_agent": "", "agent_calls": 0},
            config={"run_name": "PolicyAgent"}
        )
        return {
            "messages": result["messages"],
            "agent_calls": state.get("agent_calls", 0) + 1
        }

    def ticket_node(state: AgentState) -> dict:
        """Execute ticket management agent."""
        result = ticket_agent.invoke(
            {"messages": state["messages"], "next_agent": "", "agent_calls": 0},
            config={"run_name": "TicketAgent"}
        )
        return {
            "messages": result["messages"],
            "agent_calls": state.get("agent_calls", 0) + 1
        }

    def route_to_agent(state: AgentState) -> Literal["scan_agent", "policy_agent", "ticket_agent", "end"]:
        """Determine next node based on supervisor decision."""
        next_agent = state.get("next_agent", "FINISH")
        if next_agent == "FINISH":
            return "end"
        return next_agent

    workflow = StateGraph(AgentState)

    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("scan_agent", scan_node)
    workflow.add_node("policy_agent", policy_node)
    workflow.add_node("ticket_agent", ticket_node)

    workflow.set_entry_point("supervisor")

    workflow.add_conditional_edges(
        "supervisor",
        route_to_agent,
        {
            "scan_agent": "scan_agent",
            "policy_agent": "policy_agent",
            "ticket_agent": "ticket_agent",
            "end": END
        }
    )

    # Route agents back to supervisor for potential chaining
    workflow.add_edge("scan_agent", "supervisor")
    workflow.add_edge("policy_agent", "supervisor")
    workflow.add_edge("ticket_agent", "supervisor")

    return workflow.compile()


def run_agent(
    user_message: str,
    history: Optional[list[dict]] = None,
    username: Optional[str] = None,
    session_id: Optional[str] = None,
    use_context_management: bool = True
) -> dict:
    """
    Execute the multi-agent supervisor with a user message.

    Processes the user message through the supervisor graph, tracking
    token usage and calculating costs. Optionally uses context management
    to handle long conversations efficiently.

    Args:
        user_message: The user's input message.
        history: Optional conversation history as list of role/content dicts.
        username: Optional username for tracking and metadata.
        session_id: Optional session ID for context management.
        use_context_management: Whether to use token-aware context management.

    Returns:
        Dictionary containing:
        - response: AI-generated response text
        - tool_calls: List of tools invoked with their arguments
        - trace_url: LangSmith trace URL for debugging
        - token_usage: Token counts and cost breakdown
        - context_stats: Context management statistics (if enabled)
    """
    graph = create_supervisor()
    token_tracker = TokenTracker()

    messages = []

    # Use context management if enabled and username provided
    if use_context_management and username:
        # Get managed context (includes summary if conversation is long)
        context_messages = SessionContextManager.get_messages(username, session_id)
        for msg in context_messages:
            if msg["role"] == "user":
                messages.append(HumanMessage(content=msg["content"]))
            elif msg["role"] == "assistant":
                messages.append(AIMessage(content=msg["content"]))
            elif msg["role"] == "system":
                messages.append(SystemMessage(content=msg["content"]))
    elif history:
        for msg in history:
            if msg["role"] == "user":
                messages.append(HumanMessage(content=msg["content"]))
            else:
                messages.append(AIMessage(content=msg["content"]))

    messages.append(HumanMessage(content=user_message))

    run_id = uuid.uuid4()
    metadata = {"user_message": user_message[:100]}
    if username:
        metadata["username"] = username

    config = RunnableConfig(
        run_name="DevSecOpsSupervisor",
        tags=["devsecops", "multi-agent"],
        metadata=metadata,
        run_id=run_id,
        callbacks=[token_tracker]
    )

    result = graph.invoke({"messages": messages, "next_agent": "", "agent_calls": 0}, config=config)

    tool_calls = []
    response_content = ""

    for msg in result["messages"]:
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            for tc in msg.tool_calls:
                tool_calls.append({
                    "tool_name": tc["name"],
                    "arguments": tc["args"]
                })
        if isinstance(msg, AIMessage) and msg.content:
            response_content = msg.content

    trace_url = None
    if settings.LANGSMITH_TRACING and settings.LANGSMITH_ORG_ID and settings.LANGSMITH_PROJECT_ID:
        trace_url = f"https://smith.langchain.com/o/{settings.LANGSMITH_ORG_ID}/projects/p/{settings.LANGSMITH_PROJECT_ID}?peek={run_id}"

    model_name = settings.AZURE_OPENAI_DEPLOYMENT_NAME.lower()
    pricing = PRICING.get(model_name, PRICING["gpt-4o"])
    input_cost = (token_tracker.total_input_tokens / 1_000_000) * pricing["input"]
    output_cost = (token_tracker.total_output_tokens / 1_000_000) * pricing["output"]
    total_cost = input_cost + output_cost

    # Get context stats if using context management
    context_stats = None
    if use_context_management and username:
        context_stats = SessionContextManager.get_stats(username, session_id)

    return {
        "response": response_content,
        "tool_calls": tool_calls,
        "trace_url": trace_url,
        "token_usage": {
            "input_tokens": token_tracker.total_input_tokens,
            "output_tokens": token_tracker.total_output_tokens,
            "total_tokens": token_tracker.total_input_tokens + token_tracker.total_output_tokens,
            "llm_calls": token_tracker.llm_calls,
            "cost": {
                "input": round(input_cost, 6),
                "output": round(output_cost, 6),
                "total": round(total_cost, 6)
            }
        },
        "context_stats": context_stats
    }


async def run_agent_with_context(
    user_message: str,
    username: str,
    session_id: Optional[str] = None
) -> dict:
    """
    Execute agent with full context management including async summarization.

    This is the recommended entry point for production use. It:
    1. Retrieves managed context (with summary if available)
    2. Runs the agent
    3. Updates context with new exchange
    4. Triggers summarization if needed

    Args:
        user_message: The user's input message.
        username: Username for context management.
        session_id: Optional session identifier.

    Returns:
        Agent response with context statistics.
    """
    # Run the agent with context management
    result = run_agent(
        user_message=user_message,
        username=username,
        session_id=session_id,
        use_context_management=True
    )

    # Update context with this exchange and compress if needed
    if result.get("response"):
        context_stats = await SessionContextManager.add_exchange(
            username=username,
            user_message=user_message,
            assistant_response=result["response"],
            session_id=session_id
        )
        result["context_stats"] = context_stats

    return result


async def run_agent_stream(
    user_message: str,
    history: Optional[list[dict]] = None,
    username: Optional[str] = None
) -> AsyncGenerator[dict, None]:
    """
    Execute the multi-agent supervisor with streaming response.

    Processes the user message through the supervisor graph and streams
    tokens as they are generated.

    Args:
        user_message: The user's input message.
        history: Optional conversation history as list of role/content dicts.
        username: Optional username for tracking and metadata.

    Yields:
        Server-Sent Event dictionaries containing:
        - token: Individual tokens as generated
        - tool_call: When a tool is invoked
        - metadata: Final token usage and trace URL
        - done: Stream complete signal
    """
    graph = create_supervisor()
    token_tracker = TokenTracker()

    messages = []
    if history:
        for msg in history:
            if msg["role"] == "user":
                messages.append(HumanMessage(content=msg["content"]))
            else:
                messages.append(AIMessage(content=msg["content"]))

    messages.append(HumanMessage(content=user_message))

    run_id = uuid.uuid4()
    metadata = {"user_message": user_message[:100]}
    if username:
        metadata["username"] = username

    config = RunnableConfig(
        run_name="DevSecOpsSupervisor",
        tags=["devsecops", "multi-agent", "streaming"],
        metadata=metadata,
        run_id=run_id,
        callbacks=[token_tracker]
    )

    tool_calls = []
    response_content = ""

    # Stream the graph execution
    async for event in graph.astream_events(
        {"messages": messages, "next_agent": "", "agent_calls": 0},
        config=config,
        version="v2"
    ):
        kind = event.get("event")

        # Stream LLM tokens
        if kind == "on_chat_model_stream":
            chunk = event.get("data", {}).get("chunk")
            if chunk and hasattr(chunk, "content") and chunk.content:
                yield {
                    "event": "token",
                    "data": json.dumps({"token": chunk.content})
                }
                response_content += chunk.content

        # Track tool calls
        elif kind == "on_tool_start":
            tool_name = event.get("name", "unknown")
            tool_input = event.get("data", {}).get("input", {})
            tool_calls.append({
                "tool_name": tool_name,
                "arguments": tool_input
            })
            yield {
                "event": "tool_call",
                "data": json.dumps({
                    "tool_name": tool_name,
                    "arguments": tool_input
                })
            }

    # Calculate costs
    model_name = settings.AZURE_OPENAI_DEPLOYMENT_NAME.lower()
    pricing = PRICING.get(model_name, PRICING["gpt-4o"])
    input_cost = (token_tracker.total_input_tokens / 1_000_000) * pricing["input"]
    output_cost = (token_tracker.total_output_tokens / 1_000_000) * pricing["output"]
    total_cost = input_cost + output_cost

    trace_url = None
    if settings.LANGSMITH_TRACING and settings.LANGSMITH_ORG_ID and settings.LANGSMITH_PROJECT_ID:
        trace_url = f"https://smith.langchain.com/o/{settings.LANGSMITH_ORG_ID}/projects/p/{settings.LANGSMITH_PROJECT_ID}?peek={run_id}"

    # Send metadata
    yield {
        "event": "metadata",
        "data": json.dumps({
            "tool_calls": tool_calls,
            "trace_url": trace_url,
            "token_usage": {
                "input_tokens": token_tracker.total_input_tokens,
                "output_tokens": token_tracker.total_output_tokens,
                "total_tokens": token_tracker.total_input_tokens + token_tracker.total_output_tokens,
                "llm_calls": token_tracker.llm_calls,
                "cost": {
                    "input": round(input_cost, 6),
                    "output": round(output_cost, 6),
                    "total": round(total_cost, 6)
                }
            }
        })
    }

    yield {"event": "done", "data": json.dumps({"status": "complete"})}
