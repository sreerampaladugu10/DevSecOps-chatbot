"""
Security scan analysis agent.

Specialized agent for analyzing Azure Defender security scan results,
identifying vulnerabilities, and providing remediation guidance.
"""

from typing import Literal

from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langchain_core.messages import SystemMessage

from app.core.llm import get_llm
from app.tools.scanner import get_latest_scan, get_findings_by_severity, get_scan_summary
from app.agents.state import AgentState

SCAN_AGENT_PROMPT = """You are a Security Scan Analyst. Analyze Azure Defender scan results.

Tools available:
- get_latest_scan: Full scan with all findings
- get_findings_by_severity: Filter by severity (Critical/High/Medium/Low)
- get_scan_summary: Quick summary

Focus on Critical and High severity first. Be concise.

## Examples

User: "What vulnerabilities were found?"
Action: Call get_scan_summary() first, then get_findings_by_severity("Critical") and get_findings_by_severity("High")
Response: Summarize findings by severity, highlight critical issues first

User: "Show me the latest scan results"
Action: Call get_latest_scan()
Response: Present all findings organized by severity

User: "Are there any critical issues?"
Action: Call get_findings_by_severity("Critical")
Response: List critical vulnerabilities with CVE IDs and remediation steps

User: "Give me a quick overview of security status"
Action: Call get_scan_summary()
Response: Provide counts by severity and overall risk assessment"""

SCAN_TOOLS = [get_latest_scan, get_findings_by_severity, get_scan_summary]


def create_scan_agent():
    """
    Create and compile the security scan analysis agent.

    Builds a LangGraph workflow that can:
    - Retrieve latest security scan results
    - Filter findings by severity level
    - Provide scan summaries

    Returns:
        Compiled LangGraph agent for security scan analysis.
    """
    llm = get_llm().bind_tools(SCAN_TOOLS).with_config({"run_name": "ScanAgentLLM"})

    def call_model(state: AgentState) -> dict:
        """Invoke the LLM with scan analysis context."""
        messages = [SystemMessage(content=SCAN_AGENT_PROMPT)] + state["messages"]
        response = llm.invoke(messages)
        return {"messages": [response]}

    def should_continue(state: AgentState) -> Literal["tools", "end"]:
        """Determine if more tool calls are needed."""
        last = state["messages"][-1]
        if hasattr(last, "tool_calls") and last.tool_calls:
            return "tools"
        return "end"

    workflow = StateGraph(AgentState)
    workflow.add_node("scan_llm", call_model)
    workflow.add_node("scan_tools", ToolNode(SCAN_TOOLS))
    workflow.set_entry_point("scan_llm")
    workflow.add_conditional_edges("scan_llm", should_continue, {"tools": "scan_tools", "end": END})
    workflow.add_edge("scan_tools", "scan_llm")

    return workflow.compile()
