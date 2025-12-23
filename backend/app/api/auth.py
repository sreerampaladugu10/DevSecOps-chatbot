"""
Authentication API endpoints.

Provides user registration, login, and token management endpoints.
Uses JWT tokens for stateless authentication.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.api.dependencies import get_db
from app.models.database import User
from app.models.schemas import UserCreate, UserResponse
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_user,
)

router = APIRouter(prefix="/auth", tags=["auth"])


class TokenResponse(BaseModel):
    """
    JWT token response schema.

    Attributes:
        access_token: The JWT access token string.
        token_type: Token type, always "bearer".
        user: User information.
    """

    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class LoginRequest(BaseModel):
    """
    Login request schema for JSON-based login.

    Attributes:
        username: User's username.
        password: User's plain text password.
    """

    username: str
    password: str


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(user: UserCreate, db: Session = Depends(get_db)) -> TokenResponse:
    """
    Register a new user account.

    Creates a new user with hashed password and returns a JWT token
    for immediate authentication.

    Args:
        user: User registration data with username and password.
        db: Database session.

    Returns:
        TokenResponse with access token and user info.

    Raises:
        HTTPException: 400 if username already exists.
    """
    existing = db.query(User).filter(User.username == user.username).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already exists"
        )

    db_user = User(
        username=user.username,
        hashed_password=hash_password(user.password)
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    access_token = create_access_token(data={"sub": db_user.username})

    return TokenResponse(
        access_token=access_token,
        user=UserResponse.model_validate(db_user)
    )


@router.post("/login", response_model=TokenResponse)
def login(request: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    """
    Authenticate user and return JWT token.

    Validates username and password, then issues a JWT access token.

    Args:
        request: Login credentials with username and password.
        db: Database session.

    Returns:
        TokenResponse with access token and user info.

    Raises:
        HTTPException: 401 if credentials are invalid.
    """
    user = db.query(User).filter(User.username == request.username).first()

    if not user or not verify_password(request.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(data={"sub": user.username})

    return TokenResponse(
        access_token=access_token,
        user=UserResponse.model_validate(user)
    )


@router.post("/token", response_model=TokenResponse)
def login_for_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
) -> TokenResponse:
    """
    OAuth2 compatible token endpoint.

    Accepts form data for OAuth2 password flow compatibility.
    Used by OAuth2PasswordBearer for automatic token handling.

    Args:
        form_data: OAuth2 form with username and password.
        db: Database session.

    Returns:
        TokenResponse with access token and user info.

    Raises:
        HTTPException: 401 if credentials are invalid.
    """
    user = db.query(User).filter(User.username == form_data.username).first()

    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(data={"sub": user.username})

    return TokenResponse(
        access_token=access_token,
        user=UserResponse.model_validate(user)
    )


@router.get("/me", response_model=UserResponse)
def get_current_user_info(current_user: User = Depends(get_current_user)) -> UserResponse:
    """
    Get current authenticated user's information.

    Requires a valid JWT token in the Authorization header.

    Args:
        current_user: Authenticated user from JWT token.

    Returns:
        UserResponse with current user's information.
    """
    return UserResponse.model_validate(current_user)
