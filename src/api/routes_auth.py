import logging
from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from src.api.auth import jwt_manager, verify_token

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

class LoginRequest(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

@router.post("/token", response_model=TokenResponse)
async def login_for_access_token(request: LoginRequest):
    """
    Issue JWT token for testing Task 27.
    """
    # Simple mock authentication logic for demonstration
    if request.username == "admin" and request.password == "adminpass":
        user_data = {
            "organization": "System",
            "roles": ["admin"]
        }
    elif request.username == "user" and request.password == "userpass":
        user_data = {
            "organization": "Guest",
            "roles": ["user"]
        }
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    access_token = jwt_manager.create_access_token(
        user_id=request.username,
        user_data=user_data
    )
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/me")
async def read_users_me(current_user: Dict[str, Any] = Depends(verify_token)):
    """
    Returns the current authenticated user's information.
    """
    return {"user_id": current_user.get("sub"), "roles": current_user.get("user_data", {}).get("roles", [])}

from fastapi.security import OAuth2PasswordRequestForm
from src.api.auth import jwt_manager, verify_token

@router.post("/login")
async def login_oauth2(form_data: OAuth2PasswordRequestForm = Depends()):
    """Standard OAuth 2.0 flow for login."""
    user_id = form_data.username
    if user_id != 'admin' and user_id != 'user':
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    
    token = jwt_manager.create_token(
        user_id=user_id,
        roles=["admin"] if user_id == 'admin' else ["user"]
    )
    return {"access_token": token, "token_type": "bearer"}

@router.post("/logout")
async def logout(payload: dict = Depends(verify_token)):
    """Logout user by invalidating token in Redis blacklist (mocked)."""
    user_id = payload.get('sub')
    logger.info(f"User {user_id} logged out via OIDC/SAML integration.")
    return {"message": "Logged out successfully"}

@router.get("/sso/saml")
async def saml_login():
    """Mock endpoint for SAML Enterprise login redirection."""
    return {"redirect_url": "https://sso.enterprise.com/saml/login"}

@router.get("/sso/oidc/callback")
async def oidc_callback(code: str):
    """Mock endpoint for OpenID Connect Callback validation."""
    return {"access_token": f"mock_oidc_token_for_{code}", "token_type": "bearer"}
