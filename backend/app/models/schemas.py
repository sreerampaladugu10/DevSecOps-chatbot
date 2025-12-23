"""
Pydantic schemas for request/response validation.

Defines all input validation and output serialization schemas
for the API endpoints.
"""

from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional
from enum import Enum


class TicketStatus(str, Enum):
    """Possible states for a ticket."""

    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"


class TicketPriority(str, Enum):
    """Priority levels for tickets."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TicketType(str, Enum):
    """Supported ticket system types."""

    JIRA = "jira"
    SERVICENOW = "servicenow"


class AuthProvider(str, Enum):
    """Authentication provider types."""

    LOCAL = "local"
    AZURE_AD = "azure_ad"


class UserCreate(BaseModel):
    """
    Schema for user registration.

    Attributes:
        username: Unique username (3-50 characters).
        password: User password (minimum 8 characters).
    """

    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8)


class UserResponse(BaseModel):
    """
    Schema for user data in responses.

    Attributes:
        id: Unique user identifier.
        username: User's username.
        email: User's email address.
        display_name: User's display name.
        auth_provider: Authentication provider (local or azure_ad).
        created_at: Account creation timestamp.
    """

    id: int
    username: str
    email: Optional[str] = None
    display_name: Optional[str] = None
    auth_provider: AuthProvider = AuthProvider.LOCAL
    created_at: datetime

    class Config:
        from_attributes = True


class TicketCreate(BaseModel):
    """
    Schema for creating a new ticket.

    Attributes:
        ticket_type: JIRA or ServiceNow.
        title: Ticket title (5-255 characters).
        description: Detailed description (minimum 10 characters).
        priority: Ticket priority level.
        assignee: Optional assignee username.
        created_by: Username of ticket creator.
    """

    ticket_type: TicketType
    title: str = Field(..., min_length=5, max_length=255)
    description: str = Field(..., min_length=10)
    priority: TicketPriority = TicketPriority.MEDIUM
    assignee: Optional[str] = None
    created_by: str


class TicketResponse(BaseModel):
    """
    Schema for ticket data in responses.

    Includes all ticket fields with timestamps.
    """

    id: int
    ticket_type: TicketType
    title: str
    description: str
    priority: TicketPriority
    status: TicketStatus
    assignee: Optional[str]
    created_by: str
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class TicketUpdate(BaseModel):
    """
    Schema for updating an existing ticket.

    All fields are optional - only provided fields are updated.
    """

    title: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[TicketPriority] = None
    status: Optional[TicketStatus] = None
    assignee: Optional[str] = None


class PolicyCreate(BaseModel):
    """
    Schema for creating a security policy.

    Attributes:
        id: Unique policy identifier.
        title: Policy title (5-255 characters).
        content: Policy content (minimum 10 characters).
        category: Optional category classification.
        severity: Optional severity level.
    """

    id: str = Field(..., min_length=1, max_length=50)
    title: str = Field(..., min_length=5, max_length=255)
    content: str = Field(..., min_length=10)
    category: Optional[str] = None
    severity: Optional[str] = None


class PolicyResponse(BaseModel):
    """Schema for policy data in responses."""

    id: str
    title: str
    content: str
    category: Optional[str]
    severity: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class PolicySearchResult(BaseModel):
    """
    Schema for policy search results.

    Includes similarity distance from vector search.
    """

    id: str
    title: str
    content: str
    category: Optional[str]
    severity: Optional[str]
    distance: Optional[float] = None


class ChatMessage(BaseModel):
    """
    Schema for a single chat message.

    Attributes:
        role: Message role ('user' or 'assistant').
        content: Message text content.
    """

    role: str
    content: str


class ChatRequest(BaseModel):
    """
    Schema for chat API requests.

    Attributes:
        message: Current user message (1-4000 characters).
        conversation_history: Previous messages in the conversation.
    """

    message: str = Field(..., min_length=1, max_length=4000)
    conversation_history: list[ChatMessage] = []


class ToolCall(BaseModel):
    """
    Schema for a tool invocation during chat.

    Attributes:
        tool_name: Name of the tool called.
        arguments: Arguments passed to the tool.
        result: Optional result from tool execution.
    """

    tool_name: str
    arguments: dict
    result: Optional[str] = None


class ChatResponse(BaseModel):
    """
    Schema for chat API responses.

    Attributes:
        response: AI-generated response text.
        tool_calls: List of tools invoked during processing.
        token_usage: Token consumption and cost breakdown.
        trace_url: LangSmith trace URL for debugging.
    """

    response: str
    tool_calls: list[ToolCall] = []
    token_usage: Optional[dict] = None
    trace_url: Optional[str] = None
