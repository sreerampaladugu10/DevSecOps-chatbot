"""
Security policy compliance agent.

Specialized agent for retrieving and interpreting security policies
using RAG (Retrieval Augmented Generation) over the policy vector store.
"""

from typing import Literal

from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langchain_core.messages import SystemMessage

from app.core.llm import get_llm
from app.tools.policy_rag import retrieve_policy, retrieve_policy_fast
from app.agents.state import AgentState

POLICY_AGENT_PROMPT = """You are a Security Policy Compliance agent. Retrieve and interpret security policies.

Tools available:
- retrieve_policy: Search policies with Flash Reranking for accurate results. Returns policies with relevance scores and retrieval metrics.
- retrieve_policy_fast: Quick search without reranking. Use when speed is critical.

Explain policy requirements clearly. Highlight severity and compliance implications.
When results include rerank_score, mention high-confidence matches (score > 0.7).

## Examples

User: "What is our password policy?"
Action: Call retrieve_policy("password requirements complexity length")
Response: Explain password requirements including length, complexity, expiration, and history

User: "How should we handle encryption?"
Action: Call retrieve_policy("encryption data at rest in transit requirements")
Response: Detail encryption standards for data at rest and in transit

User: "What are the access control requirements?"
Action: Call retrieve_policy("access control authentication authorization MFA")
Response: Explain access control policies including MFA, RBAC, and least privilege

User: "Are we SOC 2 compliant?"
Action: Call retrieve_policy("SOC 2 compliance audit requirements")
Response: Summarize relevant SOC 2 controls and compliance status"""

POLICY_TOOLS = [retrieve_policy, retrieve_policy_fast]


def create_policy_agent():
    """
    Create and compile the security policy compliance agent.

    Builds a LangGraph workflow that can:
    - Search for relevant security policies using semantic similarity
    - Interpret and explain policy requirements
    - Highlight compliance implications

    Returns:
        Compiled LangGraph agent for policy compliance queries.
    """
    llm = get_llm().bind_tools(POLICY_TOOLS).with_config({"run_name": "PolicyAgentLLM"})

    def call_model(state: AgentState) -> dict:
        """Invoke the LLM with policy compliance context."""
        messages = [SystemMessage(content=POLICY_AGENT_PROMPT)] + state["messages"]
        response = llm.invoke(messages)
        return {"messages": [response]}

    def should_continue(state: AgentState) -> Literal["tools", "end"]:
        """Determine if more tool calls are needed."""
        last = state["messages"][-1]
        if hasattr(last, "tool_calls") and last.tool_calls:
            return "tools"
        return "end"

    workflow = StateGraph(AgentState)
    workflow.add_node("policy_llm", call_model)
    workflow.add_node("policy_tools", ToolNode(POLICY_TOOLS))
    workflow.set_entry_point("policy_llm")
    workflow.add_conditional_edges("policy_llm", should_continue, {"tools": "policy_tools", "end": END})
    workflow.add_edge("policy_tools", "policy_llm")

    return workflow.compile()
