"""
Configuration module for DevSecOps Chat application.

Loads settings from environment variables and .env file using Pydantic.
"""

import secrets
from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.

    Attributes:
        APP_NAME: Application display name.
        DATABASE_URL: SQLAlchemy database connection string.
        CHROMA_PERSIST_DIR: Directory for ChromaDB vector store persistence.
        JWT_SECRET_KEY: Secret key for JWT token signing.
        JWT_ALGORITHM: Algorithm used for JWT encoding.
        JWT_EXPIRATION_HOURS: Token expiration time in hours.
    """

    APP_NAME: str = "DevSecOps Chat"
    DATABASE_URL: str = "sqlite:///./devsecops.db"
    CHROMA_PERSIST_DIR: str = "./chroma_db"

    # JWT Authentication
    JWT_SECRET_KEY: str = secrets.token_urlsafe(32)
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_HOURS: int = 24

    # Azure AD SSO Configuration
    AZURE_AD_CLIENT_ID: str = ""
    AZURE_AD_CLIENT_SECRET: str = ""
    AZURE_AD_TENANT_ID: str = ""
    AZURE_AD_REDIRECT_URI: str = "http://localhost:5173/auth/callback"

    # Frontend URL for redirects
    FRONTEND_URL: str = "http://localhost:5173"

    # Azure OpenAI
    AZURE_OPENAI_ENDPOINT: str = ""
    AZURE_OPENAI_API_KEY: str = ""
    AZURE_OPENAI_DEPLOYMENT_NAME: str = "gpt-4o"
    AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT_NAME: str = "text-embedding-ada-002"
    OPENAI_API_VERSION: str = "2024-08-01-preview"

    # LangSmith
    LANGSMITH_TRACING: bool = True
    LANGSMITH_ENDPOINT: str = "https://api.smith.langchain.com"
    LANGSMITH_API_KEY: str = ""
    LANGSMITH_PROJECT: str = "devsecops-chat"
    LANGSMITH_ORG_ID: str = ""
    LANGSMITH_PROJECT_ID: str = ""

    class Config:
        env_file = ".env"


settings = Settings()
BASE_DIR = Path(__file__).resolve().parent.parent.parent
