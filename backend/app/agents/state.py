"""
Agent state definitions for LangGraph workflows.

Defines the shared state structure used across all agents in the
multi-agent system.
"""

from typing import TypedDict, Annotated
from langchain_core.messages import BaseMessage
import operator


class AgentState(TypedDict):
    """
    Shared state for multi-agent LangGraph workflows.

    This TypedDict defines the state structure passed between nodes
    in the agent graph. Messages are accumulated using operator.add.

    Attributes:
        messages: List of conversation messages, accumulated across nodes.
        next_agent: Identifier for the next agent to route to.
        agent_calls: Counter for number of agent invocations (prevents infinite loops).
    """

    messages: Annotated[list[BaseMessage], operator.add]
    next_agent: str
    agent_calls: int


def add_messages(left: list, right: list) -> list:
    """Combine message lists, used for state accumulation."""
    return left + right
