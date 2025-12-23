from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.db import get_db
from app.models.schemas import PolicyCreate, PolicyResponse
from app.repositories.policy_repo import PolicyRepository

router = APIRouter(prefix="/policies", tags=["policies"])


def get_policy_repo(db: Session = Depends(get_db)) -> PolicyRepository:
    return PolicyRepository(db)


@router.post("/", response_model=PolicyResponse)
def create_policy(policy: PolicyCreate, repo: PolicyRepository = Depends(get_policy_repo)):
    existing = repo.get_by_id(policy.id)
    if existing:
        raise HTTPException(status_code=400, detail="Policy ID already exists")
    return repo.create(policy)


@router.get("/", response_model=list[PolicyResponse])
def list_policies(skip: int = 0, limit: int = 100, repo: PolicyRepository = Depends(get_policy_repo)):
    return repo.get_all(skip, limit)


@router.get("/{policy_id}", response_model=PolicyResponse)
def get_policy(policy_id: str, repo: PolicyRepository = Depends(get_policy_repo)):
    policy = repo.get_by_id(policy_id)
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    return policy


@router.delete("/{policy_id}")
def delete_policy(policy_id: str, repo: PolicyRepository = Depends(get_policy_repo)):
    if not repo.delete(policy_id):
        raise HTTPException(status_code=404, detail="Policy not found")
    return {"message": "Policy deleted"}
