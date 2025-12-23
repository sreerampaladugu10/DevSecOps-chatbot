"""
Ticket and user repositories for data access.

Provides data access layer for tickets and user management,
including password hashing for user authentication.
"""

from typing import Optional

from sqlalchemy.orm import Session

from app.models.database import Ticket, User
from app.models.schemas import TicketCreate, TicketUpdate


class TicketRepository:
    """
    Repository for ticket CRUD operations.

    Provides static methods for managing JIRA/ServiceNow tickets
    in the SQLite database.
    """

    @staticmethod
    def create(db: Session, ticket: TicketCreate) -> Ticket:
        """
        Create a new ticket.

        Args:
            db: Database session.
            ticket: Ticket data to create.

        Returns:
            Created Ticket model.
        """
        db_ticket = Ticket(**ticket.model_dump())
        db.add(db_ticket)
        db.commit()
        db.refresh(db_ticket)
        return db_ticket

    @staticmethod
    def get_by_id(db: Session, ticket_id: int) -> Optional[Ticket]:
        """
        Retrieve a ticket by ID.

        Args:
            db: Database session.
            ticket_id: Ticket ID to look up.

        Returns:
            Ticket if found, None otherwise.
        """
        return db.query(Ticket).filter(Ticket.id == ticket_id).first()

    @staticmethod
    def get_all(db: Session, skip: int = 0, limit: int = 100) -> list[Ticket]:
        """
        Retrieve all tickets with pagination.

        Args:
            db: Database session.
            skip: Number of records to skip.
            limit: Maximum records to return.

        Returns:
            List of Ticket models.
        """
        return db.query(Ticket).offset(skip).limit(limit).all()

    @staticmethod
    def update(db: Session, ticket_id: int, updates: TicketUpdate) -> Optional[Ticket]:
        """
        Update an existing ticket.

        Args:
            db: Database session.
            ticket_id: ID of ticket to update.
            updates: Fields to update.

        Returns:
            Updated Ticket if found, None otherwise.
        """
        ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
        if not ticket:
            return None
        for key, value in updates.model_dump(exclude_unset=True).items():
            setattr(ticket, key, value)
        db.commit()
        db.refresh(ticket)
        return ticket

    @staticmethod
    def delete(db: Session, ticket_id: int) -> bool:
        """
        Delete a ticket by ID.

        Args:
            db: Database session.
            ticket_id: ID of ticket to delete.

        Returns:
            True if deleted, False if not found.
        """
        ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
        if not ticket:
            return False
        db.delete(ticket)
        db.commit()
        return True
