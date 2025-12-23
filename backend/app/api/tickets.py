from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.api.dependencies import get_db
from app.repositories.ticket_repo import TicketRepository
from app.models.schemas import TicketCreate, TicketResponse, TicketUpdate

router = APIRouter(prefix="/tickets", tags=["tickets"])


@router.post("/", response_model=TicketResponse)
def create_ticket(ticket: TicketCreate, db: Session = Depends(get_db)):
    return TicketRepository.create(db, ticket)


@router.get("/", response_model=list[TicketResponse])
def list_tickets(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return TicketRepository.get_all(db, skip, limit)


@router.get("/{ticket_id}", response_model=TicketResponse)
def get_ticket(ticket_id: int, db: Session = Depends(get_db)):
    ticket = TicketRepository.get_by_id(db, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket


@router.patch("/{ticket_id}", response_model=TicketResponse)
def update_ticket(ticket_id: int, updates: TicketUpdate, db: Session = Depends(get_db)):
    ticket = TicketRepository.update(db, ticket_id, updates)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket


@router.delete("/{ticket_id}")
def delete_ticket(ticket_id: int, db: Session = Depends(get_db)):
    success = TicketRepository.delete(db, ticket_id)
    if not success:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return {"message": "Ticket deleted"}
