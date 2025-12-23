"""
SQLAlchemy database models.

Defines the ORM models for users, tickets, and security policies.
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, Enum
from sqlalchemy.sql import func
import enum

from app.core.db import Base


class TicketStatus(str, enum.Enum):
    """Possible states for a ticket."""

    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"


class TicketPriority(str, enum.Enum):
    """Priority levels for tickets."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TicketType(str, enum.Enum):
    """Supported ticket system types."""

    JIRA = "jira"
    SERVICENOW = "servicenow"


class AuthProvider(str, enum.Enum):
    """Authentication provider types."""

    LOCAL = "local"
    AZURE_AD = "azure_ad"


class User(Base):
    """
    User model for authentication.

    Supports both local (username/password) and SSO (Azure AD) authentication.

    Attributes:
        id: Primary key.
        username: Unique username for login (email for SSO users).
        hashed_password: Bcrypt-hashed password with salt (nullable for SSO).
        email: User email address.
        display_name: User's display name.
        auth_provider: Authentication provider (local or azure_ad).
        azure_ad_id: Azure AD object ID for SSO users.
        created_at: Account creation timestamp.
    """

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=True)  # Nullable for SSO users
    email = Column(String(255), unique=True, index=True, nullable=True)
    display_name = Column(String(255), nullable=True)
    auth_provider = Column(Enum(AuthProvider), default=AuthProvider.LOCAL)
    azure_ad_id = Column(String(255), unique=True, nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Ticket(Base):
    """
    Ticket model for JIRA/ServiceNow tickets.

    Attributes:
        id: Primary key.
        ticket_type: JIRA or ServiceNow.
        title: Ticket title/summary.
        description: Detailed ticket description.
        priority: LOW, MEDIUM, HIGH, or CRITICAL.
        status: Current ticket status.
        assignee: Username of assigned person.
        created_by: Username of ticket creator.
        created_at: Creation timestamp.
        updated_at: Last update timestamp.
    """

    __tablename__ = "tickets"

    id = Column(Integer, primary_key=True, index=True)
    ticket_type = Column(Enum(TicketType), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    priority = Column(Enum(TicketPriority), default=TicketPriority.MEDIUM)
    status = Column(Enum(TicketStatus), default=TicketStatus.OPEN)
    assignee = Column(String(100), nullable=True)
    created_by = Column(String(100), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class Policy(Base):
    """
    Security policy model.

    Attributes:
        id: Unique policy identifier (string).
        title: Policy title.
        content: Full policy text content.
        category: Policy category classification.
        severity: Policy severity level.
        created_at: Creation timestamp.
        updated_at: Last update timestamp.
    """

    __tablename__ = "policies"

    id = Column(String(50), primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    category = Column(String(100), nullable=True)
    severity = Column(String(50), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
