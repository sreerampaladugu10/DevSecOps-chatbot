"""
Ticket management agent.

Specialized agent for creating and managing JIRA and ServiceNow tickets
based on security findings and user requests.
"""

from typing import Literal

from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langchain_core.messages import SystemMessage

from app.core.llm import get_llm
from app.tools.tickets import create_ticket, get_ticket, list_tickets, delete_ticket
from app.agents.state import AgentState

TICKET_AGENT_PROMPT = """You are a Ticket Management agent. Create and manage JIRA/ServiceNow tickets.

Tools available:
- create_ticket: Create ticket (jira/servicenow, title, description, priority, assignee)
- get_ticket: Get ticket by ID
- list_tickets: List all tickets
- delete_ticket: Delete a ticket by ID

Use clear titles, include CVE IDs in description, set priority based on severity.

## Examples

User: "Create a ticket for the SQL injection vulnerability"
Action: Call create_ticket(system="jira", title="[Critical] SQL Injection Vulnerability - CVE-2024-XXXX", description="...", priority="critical")
Response: Confirm ticket creation with ticket ID and details

User: "Show me all open tickets"
Action: Call list_tickets()
Response: List all tickets with ID, title, status, and priority

User: "What's the status of JIRA-123?"
Action: Call get_ticket("JIRA-123")
Response: Show ticket details including status, assignee, and description

User: "Create a ServiceNow incident for the failed backup"
Action: Call create_ticket(system="servicenow", title="Backup Failure Alert", description="...", priority="high")
Response: Confirm incident creation with reference number

User: "Delete ticket 5"
Action: Call delete_ticket(ticket_id=5)
Response: Confirm deletion with the deleted ticket details

Severity to Priority mapping:
- Critical vulnerability → priority="critical"
- High severity → priority="high"
- Medium severity → priority="medium"
- Low severity → priority="low" """

TICKET_TOOLS = [create_ticket, get_ticket, list_tickets, delete_ticket]


def create_ticket_agent():
    """
    Create and compile the ticket management agent.

    Builds a LangGraph workflow that can:
    - Create JIRA or ServiceNow tickets
    - Retrieve ticket details by ID
    - List all existing tickets
    - Delete tickets by ID

    Returns:
        Compiled LangGraph agent for ticket management.
    """
    llm = get_llm().bind_tools(TICKET_TOOLS).with_config({"run_name": "TicketAgentLLM"})

    def call_model(state: AgentState) -> dict:
        """Invoke the LLM with ticket management context."""
        messages = [SystemMessage(content=TICKET_AGENT_PROMPT)] + state["messages"]
        response = llm.invoke(messages)
        return {"messages": [response]}

    def should_continue(state: AgentState) -> Literal["tools", "end"]:
        """Determine if more tool calls are needed."""
        last = state["messages"][-1]
        if hasattr(last, "tool_calls") and last.tool_calls:
            return "tools"
        return "end"

    workflow = StateGraph(AgentState)
    workflow.add_node("ticket_llm", call_model)
    workflow.add_node("ticket_tools", ToolNode(TICKET_TOOLS))
    workflow.set_entry_point("ticket_llm")
    workflow.add_conditional_edges("ticket_llm", should_continue, {"tools": "ticket_tools", "end": END})
    workflow.add_edge("ticket_tools", "ticket_llm")

    return workflow.compile()
