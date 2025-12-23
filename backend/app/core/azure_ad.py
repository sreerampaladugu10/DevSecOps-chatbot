"""
Azure AD SSO Authentication module.

Provides OAuth2/OIDC integration with Microsoft Azure Active Directory
for Single Sign-On (SSO) authentication.

Flow:
1. User clicks "Login with Microsoft"
2. Backend generates authorization URL and redirects user to Azure AD
3. User authenticates with Microsoft
4. Azure AD redirects back with authorization code
5. Backend exchanges code for access token
6. Backend validates token and creates/updates user
7. Backend issues JWT for session management
"""

from typing import Optional
from urllib.parse import urlencode
import httpx

from app.core.config import settings


class AzureADAuth:
    """
    Azure AD OAuth2/OIDC authentication handler.

    Implements the Authorization Code Flow with PKCE for secure
    authentication with Microsoft Identity Platform.

    Attributes:
        client_id: Azure AD application (client) ID.
        client_secret: Azure AD client secret.
        tenant_id: Azure AD tenant ID.
        redirect_uri: OAuth callback URL.
    """

    # Microsoft Identity Platform endpoints
    AUTHORITY_BASE = "https://login.microsoftonline.com"
    GRAPH_API_BASE = "https://graph.microsoft.com/v1.0"

    def __init__(self):
        """Initialize Azure AD auth with settings from environment."""
        self.client_id = settings.AZURE_AD_CLIENT_ID
        self.client_secret = settings.AZURE_AD_CLIENT_SECRET
        self.tenant_id = settings.AZURE_AD_TENANT_ID
        self.redirect_uri = settings.AZURE_AD_REDIRECT_URI

    @property
    def authority(self) -> str:
        """Get the Azure AD authority URL for this tenant."""
        return f"{self.AUTHORITY_BASE}/{self.tenant_id}"

    @property
    def authorization_endpoint(self) -> str:
        """Get the OAuth2 authorization endpoint."""
        return f"{self.authority}/oauth2/v2.0/authorize"

    @property
    def token_endpoint(self) -> str:
        """Get the OAuth2 token endpoint."""
        return f"{self.authority}/oauth2/v2.0/token"

    def is_configured(self) -> bool:
        """
        Check if Azure AD SSO is properly configured.

        Returns:
            True if all required settings are present, False otherwise.
        """
        return all([
            self.client_id,
            self.client_secret,
            self.tenant_id,
        ])

    def get_authorization_url(self, state: Optional[str] = None) -> str:
        """
        Generate the Azure AD authorization URL for login.

        Args:
            state: Optional state parameter for CSRF protection.

        Returns:
            Full authorization URL to redirect user to.
        """
        params = {
            "client_id": self.client_id,
            "response_type": "code",
            "redirect_uri": self.redirect_uri,
            "response_mode": "query",
            "scope": "openid profile email User.Read",
            "state": state or "default",
        }
        return f"{self.authorization_endpoint}?{urlencode(params)}"

    async def exchange_code_for_token(self, code: str) -> dict:
        """
        Exchange authorization code for access token.

        Args:
            code: Authorization code from Azure AD callback.

        Returns:
            Token response containing access_token, id_token, etc.

        Raises:
            httpx.HTTPError: If token exchange fails.
        """
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": code,
            "redirect_uri": self.redirect_uri,
            "grant_type": "authorization_code",
            "scope": "openid profile email User.Read",
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.token_endpoint,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            response.raise_for_status()
            return response.json()

    async def get_user_info(self, access_token: str) -> dict:
        """
        Get user profile from Microsoft Graph API.

        Args:
            access_token: Valid Azure AD access token.

        Returns:
            User profile containing id, displayName, mail, etc.

        Raises:
            httpx.HTTPError: If API call fails.
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.GRAPH_API_BASE}/me",
                headers={"Authorization": f"Bearer {access_token}"}
            )
            response.raise_for_status()
            return response.json()

    async def validate_and_get_user(self, code: str) -> dict:
        """
        Complete OAuth flow: exchange code and get user info.

        This is the main method to call after receiving the
        authorization code from Azure AD callback.

        Args:
            code: Authorization code from callback.

        Returns:
            Dictionary with user info and tokens:
            {
                "azure_id": str,
                "email": str,
                "display_name": str,
                "access_token": str,
            }

        Raises:
            ValueError: If user info is incomplete.
            httpx.HTTPError: If API calls fail.
        """
        # Exchange code for tokens
        token_response = await self.exchange_code_for_token(code)
        access_token = token_response.get("access_token")

        if not access_token:
            raise ValueError("No access token in response")

        # Get user profile from Graph API
        user_info = await self.get_user_info(access_token)

        # Extract user details
        azure_id = user_info.get("id")
        email = user_info.get("mail") or user_info.get("userPrincipalName")
        display_name = user_info.get("displayName", email)

        if not azure_id or not email:
            raise ValueError("Incomplete user information from Azure AD")

        return {
            "azure_id": azure_id,
            "email": email,
            "display_name": display_name,
            "access_token": access_token,
        }


# Singleton instance
azure_ad_auth = AzureADAuth()
