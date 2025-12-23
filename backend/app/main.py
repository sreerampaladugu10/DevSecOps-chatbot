from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.core.db import engine, Base, SessionLocal
from app.core.tracing import setup_langsmith
from app.repositories.policy_repo import PolicyRepository
from app.data.security_policies import SECURITY_POLICIES
from app.api import policies, chat, auth, tickets

setup_langsmith()


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        policy_repo = PolicyRepository(db)
        if policy_repo.count() == 0:
            policy_repo.bulk_create(SECURITY_POLICIES)
    finally:
        db.close()
    yield


app = FastAPI(title="DevSecOps Chat", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(policies.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
app.include_router(auth.router, prefix="/api")
app.include_router(tickets.router, prefix="/api")


@app.get("/health")
def health():
    return {"status": "ok"}
