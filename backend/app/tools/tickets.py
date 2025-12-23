from langchain_core.tools import tool
from app.repositories.ticket_repo import TicketRepository
from app.models.schemas import TicketCreate, TicketType, TicketPriority
from app.core.db import SessionLocal


@tool
def create_ticket(
    ticket_type: str,
    title: str,
    description: str,
    priority: str = "medium",
    assignee: str = None
) -> dict:
    """Create a JIRA or ServiceNow ticket. ticket_type: 'jira' or 'servicenow'. priority: 'low', 'medium', 'high', 'critical'."""
    db = SessionLocal()
    try:
        ticket_data = TicketCreate(
            ticket_type=TicketType(ticket_type.lower()),
            title=title,
            description=description,
            priority=TicketPriority(priority.lower()),
            assignee=assignee,
            created_by="agent"
        )
        ticket = TicketRepository.create(db, ticket_data)
        return {
            "id": ticket.id,
            "ticket_type": ticket.ticket_type.value,
            "title": ticket.title,
            "status": ticket.status.value,
            "priority": ticket.priority.value,
            "created_at": ticket.created_at.isoformat()
        }
    finally:
        db.close()


@tool
def get_ticket(ticket_id: int) -> dict:
    """Get ticket details by ID."""
    db = SessionLocal()
    try:
        ticket = TicketRepository.get_by_id(db, ticket_id)
        if not ticket:
            return {"error": "Ticket not found"}
        return {
            "id": ticket.id,
            "ticket_type": ticket.ticket_type.value,
            "title": ticket.title,
            "description": ticket.description,
            "status": ticket.status.value,
            "priority": ticket.priority.value,
            "assignee": ticket.assignee,
            "created_at": ticket.created_at.isoformat()
        }
    finally:
        db.close()


@tool
def list_tickets() -> list[dict]:
    """List all tickets."""
    db = SessionLocal()
    try:
        tickets = TicketRepository.get_all(db)
        return [
            {
                "id": t.id,
                "ticket_type": t.ticket_type.value,
                "title": t.title,
                "status": t.status.value,
                "priority": t.priority.value
            }
            for t in tickets
        ]
    finally:
        db.close()


@tool
def delete_ticket(ticket_id: int) -> dict:
    """Delete a ticket by ID. Returns success status and deleted ticket info."""
    db = SessionLocal()
    try:
        ticket = TicketRepository.get_by_id(db, ticket_id)
        if not ticket:
            return {"success": False, "error": f"Ticket {ticket_id} not found"}

        ticket_info = {
            "id": ticket.id,
            "title": ticket.title,
            "ticket_type": ticket.ticket_type.value
        }

        deleted = TicketRepository.delete(db, ticket_id)
        if deleted:
            return {
                "success": True,
                "message": f"Ticket {ticket_id} deleted successfully",
                "deleted_ticket": ticket_info
            }
        else:
            return {"success": False, "error": f"Failed to delete ticket {ticket_id}"}
    finally:
        db.close()
