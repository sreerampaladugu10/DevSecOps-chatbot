"""
Authentication API endpoints.

Provides user registration, login, token management, and Azure AD SSO endpoints.
Uses JWT tokens for stateless authentication.
Supports both local (username/password) and SSO (Azure AD) authentication.
"""

import secrets
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.api.dependencies import get_db
from app.models.database import User, AuthProvider
from app.models.schemas import UserCreate, UserResponse
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_user,
)
from app.core.azure_ad import azure_ad_auth
from app.core.config import settings

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


# =============================================================================
# Azure AD SSO Endpoints
# =============================================================================


class SSOStatusResponse(BaseModel):
    """Response schema for SSO configuration status."""

    enabled: bool
    provider: str = "azure_ad"


@router.get("/sso/status", response_model=SSOStatusResponse)
def get_sso_status() -> SSOStatusResponse:
    """
    Check if Azure AD SSO is configured and enabled.

    Returns:
        SSOStatusResponse with enabled status.
    """
    return SSOStatusResponse(enabled=azure_ad_auth.is_configured())


@router.get("/sso/login")
def sso_login():
    """
    Initiate Azure AD SSO login flow.

    Generates a random state for CSRF protection and redirects
    the user to the Azure AD authorization endpoint.

    Returns:
        RedirectResponse to Azure AD login page.

    Raises:
        HTTPException: 503 if SSO is not configured.
    """
    if not azure_ad_auth.is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Azure AD SSO is not configured. Please set AZURE_AD_CLIENT_ID, "
                   "AZURE_AD_CLIENT_SECRET, and AZURE_AD_TENANT_ID environment variables."
        )

    # Generate state for CSRF protection
    state = secrets.token_urlsafe(32)

    # Get authorization URL
    auth_url = azure_ad_auth.get_authorization_url(state=state)

    return {"auth_url": auth_url, "state": state}


@router.get("/sso/callback")
async def sso_callback(
    code: str = Query(..., description="Authorization code from Azure AD"),
    state: str = Query(default=None, description="State parameter for CSRF validation"),
    error: str = Query(default=None, description="Error code if authentication failed"),
    error_description: str = Query(default=None, description="Error description"),
    db: Session = Depends(get_db)
):
    """
    Handle Azure AD OAuth callback.

    This endpoint is called by Azure AD after user authentication.
    It exchanges the authorization code for tokens, creates/updates
    the user in the database, and redirects to the frontend with a JWT.

    Args:
        code: Authorization code from Azure AD.
        state: State parameter for CSRF validation.
        error: Error code if authentication failed.
        error_description: Error description from Azure AD.
        db: Database session.

    Returns:
        RedirectResponse to frontend with JWT token in URL.

    Raises:
        HTTPException: 400 if authentication fails.
    """
    # Handle error from Azure AD
    if error:
        error_msg = error_description or error
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/auth/callback?error={error_msg}"
        )

    try:
        # Exchange code for token and get user info
        user_data = await azure_ad_auth.validate_and_get_user(code)

        # Check if user exists by Azure AD ID
        user = db.query(User).filter(
            User.azure_ad_id == user_data["azure_id"]
        ).first()

        if not user:
            # Check if user exists by email (might have registered locally)
            user = db.query(User).filter(
                User.email == user_data["email"]
            ).first()

            if user:
                # Link existing user to Azure AD
                user.azure_ad_id = user_data["azure_id"]
                user.auth_provider = AuthProvider.AZURE_AD
                user.display_name = user_data["display_name"]
            else:
                # Create new user
                user = User(
                    username=user_data["email"],
                    email=user_data["email"],
                    display_name=user_data["display_name"],
                    azure_ad_id=user_data["azure_id"],
                    auth_provider=AuthProvider.AZURE_AD,
                    hashed_password=None  # SSO users don't have passwords
                )
                db.add(user)

        db.commit()
        db.refresh(user)

        # Create JWT token for the application
        access_token = create_access_token(data={"sub": user.username})

        # Redirect to frontend with token
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/auth/callback?token={access_token}"
        )

    except ValueError as e:
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/auth/callback?error={str(e)}"
        )
    except Exception as e:
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/auth/callback?error=Authentication failed: {str(e)}"
        )
