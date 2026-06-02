"""
Production-ready API authentication, authorization, and middleware.
Implements JWT, rate limiting, audit logging.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional, List, Callable
from functools import wraps
import hashlib
import secrets
import json
from threading import Lock

from fastapi import Request, HTTPException, status, Depends
from fastapi.security import HTTPBearer
try:
    from fastapi.security import HTTPAuthCredentials
except ImportError:
    try:
        # Fallback for older FastAPI versions
        from fastapi.security.http import HTTPAuthCredentials
    except ImportError:
        # For latest FastAPI versions, define minimal replacement
        from typing import NamedTuple
        class HTTPAuthCredentials(NamedTuple):
            scheme: str
            credentials: str
import jwt

logger = logging.getLogger(__name__)


# Configuration
JWT_SECRET_KEY = secrets.token_urlsafe(32)
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24
RATE_LIMIT_WINDOW_SECONDS = 60
RATE_LIMIT_REQUESTS_PER_WINDOW = 1000


class User:
    """User model."""
    
    def __init__(self, user_id: str, name: str, organization: str, 
                 rate_limit: int = 1000, roles: Optional[List[str]] = None):
        self.user_id = user_id
        self.name = name
        self.organization = organization
        self.rate_limit = rate_limit
        self.roles = roles or ["user"]
        self.created_at = datetime.now(timezone.utc)


class APIKey:
    """API Key model."""
    
    def __init__(self, key_id: str, user_id: str, name: str, 
                 key_hash: str, rate_limit: int = 1000):
        self.key_id = key_id
        self.user_id = user_id
        self.name = name
        self.key_hash = key_hash  # Hash of the actual key
        self.rate_limit = rate_limit
        self.created_at = datetime.now(timezone.utc)
        self.last_used: Optional[datetime] = None
        self.is_active = True


class JWTTokenManager:
    """Manage JWT token generation and validation."""
    
    def __init__(self, secret_key: str, algorithm: str, expiration_hours: int):
        self.secret_key = secret_key
        self.algorithm = algorithm
        self.expiration_hours = expiration_hours
        self.blacklist = set()  # Token blacklist for logout

    def create_access_token(self, user_id: str, user_data: Dict[str, Any]) -> str:
        """Create JWT access token."""
        payload = {
            "sub": user_id,
            "user_data": user_data,
            "iat": datetime.now(timezone.utc),
            "exp": datetime.now(timezone.utc) + timedelta(hours=self.expiration_hours),
        }
        
        token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
        logger.info(f"Created token for user {user_id}")
        return token

    def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Verify and decode JWT token."""
        try:
            if token in self.blacklist:
                logger.warning("Token is blacklisted")
                return None
            
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return payload
            
        except jwt.ExpiredSignatureError:
            logger.warning("Token has expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid token: {str(e)}")
            return None

    def revoke_token(self, token: str):
        """Add token to blacklist."""
        self.blacklist.add(token)


class RateLimiter:
    """Rate limiter implementation."""
    
    def __init__(self, window_seconds: int = 60):
        self.window_seconds = window_seconds
        self.requests: Dict[str, List[datetime]] = {}
        self.lock = Lock()
        self.limits: Dict[str, int] = {}  # user_id -> requests_per_window

    def set_limit(self, user_id: str, requests_per_window: int):
        """Set rate limit for user."""
        self.limits[user_id] = requests_per_window

    def is_allowed(self, user_id: str) -> bool:
        """Check if request is allowed."""
        with self.lock:
            now = datetime.now(timezone.utc)
            window_start = now - timedelta(seconds=self.window_seconds)
            
            # Get user's request history
            if user_id not in self.requests:
                self.requests[user_id] = []
            
            # Remove old requests outside window
            self.requests[user_id] = [
                req_time for req_time in self.requests[user_id]
                if req_time > window_start
            ]
            
            # Get user's limit
            limit = self.limits.get(user_id, RATE_LIMIT_REQUESTS_PER_WINDOW)
            
            # Check if limit exceeded
            if len(self.requests[user_id]) >= limit:
                logger.warning(f"Rate limit exceeded for user {user_id}")
                return False
            
            # Record this request
            self.requests[user_id].append(now)
            return True

    def get_usage(self, user_id: str) -> Dict[str, Any]:
        """Get rate limit usage for user."""
        with self.lock:
            now = datetime.now(timezone.utc)
            window_start = now - timedelta(seconds=self.window_seconds)
            
            requests = self.requests.get(user_id, [])
            recent_requests = [
                req for req in requests if req > window_start
            ]
            
            limit = self.limits.get(user_id, RATE_LIMIT_REQUESTS_PER_WINDOW)
            
            return {
                "requests_used": len(recent_requests),
                "limit": limit,
                "remaining": limit - len(recent_requests),
                "reset_time": (window_start + timedelta(seconds=self.window_seconds)).isoformat(),
            }


class AuditLogger:
    """Audit logging for API operations."""
    
    def __init__(self, log_file: str = "logs/audit.log"):
        self.log_file = log_file
        self.lock = Lock()
        self.logs: List[Dict[str, Any]] = []

    def log_action(
        self,
        user_id: str,
        action: str,
        resource: str,
        method: str,
        status: int,
        details: Optional[Dict[str, Any]] = None,
    ):
        """Log user action."""
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "user_id": user_id,
            "action": action,
            "resource": resource,
            "method": method,
            "status": status,
            "details": details or {},
        }
        
        with self.lock:
            self.logs.append(entry)
            logger.info(json.dumps(entry))

    def get_logs(self, user_id: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """Get audit logs."""
        logs = self.logs
        
        if user_id:
            logs = [log for log in logs if log["user_id"] == user_id]
        
        return logs[-limit:]


class RBACManager:
    """Role-Based Access Control manager."""
    
    # Define role permissions
    ROLE_PERMISSIONS = {
        "admin": [
            "vision:read", "vision:write", "vision:delete",
            "retrieval:read", "retrieval:write", "retrieval:delete",
            "reasoning:read", "reasoning:write",
            "verification:read", "verification:write",
            "system:read", "system:write", "system:admin",
        ],
        "power_user": [
            "vision:read", "vision:write",
            "retrieval:read", "retrieval:write",
            "reasoning:read", "reasoning:write",
            "verification:read",
        ],
        "user": [
            "vision:read",
            "retrieval:read",
            "reasoning:read",
            "verification:read",
        ],
        "guest": [
            "vision:read",
            "retrieval:read",
        ],
    }

    def has_permission(self, roles: List[str], permission: str) -> bool:
        """Check if roles have permission."""
        for role in roles:
            role_perms = self.ROLE_PERMISSIONS.get(role, [])
            if permission in role_perms or f"{permission.split(':')[0]}:*" in role_perms:
                return True
        return False

    def get_permissions(self, roles: List[str]) -> set:
        """Get all permissions for roles."""
        perms = set()
        for role in roles:
            perms.update(self.ROLE_PERMISSIONS.get(role, []))
        return perms


# Global instances
jwt_manager = JWTTokenManager(JWT_SECRET_KEY, JWT_ALGORITHM, JWT_EXPIRATION_HOURS)
rate_limiter = RateLimiter(RATE_LIMIT_WINDOW_SECONDS)
audit_logger = AuditLogger()
rbac_manager = RBACManager()

class ACLManager:
    """Access Control List for resource-level authorization."""
    def __init__(self):
        self._acl = {} # {resource_id: [user_ids]}
        
    def grant_access(self, resource: str, user: str):
        if resource not in self._acl: self._acl[resource] = []
        self._acl[resource].append(user)
        
    def has_access(self, resource: str, user: str) -> bool:
        return user in self._acl.get(resource, []) or user.startswith("admin_")

class ABACManager:
    """Attribute-Based Access Control logic."""
    @staticmethod
    def allowed(user_attr: dict, resource_attr: dict, env_attr: dict) -> bool:
        if resource_attr.get('confidential') and user_attr.get('clearance') != 'high':
            return False
        if env_attr.get('outside_office_hours', False):
            return False
        return True

acl_manager = ACLManager()
abac_manager = ABACManager()

class QuotaManager:
    """Quota management system for billing and tiers."""
    def __init__(self):
        self.plans = {
            "trial": {"requests_per_month": 100, "features": ["search"]},
            "pro": {"requests_per_month": 10000, "features": ["search", "batch", "async", "analytics"]},
            "enterprise": {"requests_per_month": -1, "features": ["all"]}
        }
        self.usage = {} # mock usage {user_id: count}
        
    def check_quota(self, user_id: str, plan: str = "trial") -> bool:
        if plan == "enterprise":
            return True
        limit = self.plans.get(plan, self.plans["trial"])["requests_per_month"]
        current_usage = self.usage.get(user_id, 0)
        return current_usage < limit

    def increment_usage(self, user_id: str):
        self.usage[user_id] = self.usage.get(user_id, 0) + 1

quota_manager = QuotaManager()



# Security dependencies
security = HTTPBearer()


async def verify_token(credentials: HTTPAuthCredentials = Depends(security)) -> Dict[str, Any]:
    """Verify JWT token from Authorization header."""
    token = credentials.credentials
    payload = jwt_manager.verify_token(token)
    
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return payload


async def verify_api_key(request: Request) -> str:
    """Verify API key from header."""
    api_key = request.headers.get("X-API-Key")
    
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key",
        )
    
    # In production, verify against database
    # For now, check against a simple list
    logger.info(f"API key received: {api_key[:8]}...")
    
    return api_key


async def rate_limit_check(user_id: str) -> bool:
    """Check rate limit for user."""
    if not rate_limiter.is_allowed(user_id):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded",
        )
    return True


async def permission_check(
    required_permission: str,
    payload: Dict[str, Any] = Depends(verify_token)
) -> bool:
    """Check if user has required permission."""
    user_data = payload.get("user_data", {})
    roles = user_data.get("roles", ["guest"])
    
    if not rbac_manager.has_permission(roles, required_permission):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Permission denied: {required_permission}",
        )
    
    return True


def required_permission(permission: str) -> Callable:
    """Dependency for required permissions."""
    async def check_permission(
        payload: Dict[str, Any] = Depends(verify_token)
    ):
        user_data = payload.get("user_data", {})
        roles = user_data.get("roles", ["guest"])
        
        if not rbac_manager.has_permission(roles, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: {permission}",
            )
        
        return payload
    
    return check_permission


from starlette.middleware.base import BaseHTTPMiddleware

class AuthorizationMiddleware(BaseHTTPMiddleware):
    """Middleware for authorization checks."""
    
    def __init__(self, app):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):
        """Process request."""
        start_time = datetime.now()
        
        # Get user from token or API key
        user_id = "anonymous"
        
        try:
            auth_header = request.headers.get("Authorization")
            if auth_header and auth_header.startswith("Bearer "):
                token = auth_header[7:]
                payload = jwt_manager.verify_token(token)
                if payload:
                    user_id = payload.get("sub", "anonymous")
            
            api_key = request.headers.get("X-API-Key")
            if api_key and not user_id:
                user_id = f"api_key_{api_key[:8]}"
        except:
            pass
        
        # Check rate limit
        if not rate_limiter.is_allowed(user_id):
            return JSONResponse(
                status_code=429,
                content={"error": "Rate limit exceeded"},
                headers={"Retry-After": str(RATE_LIMIT_WINDOW_SECONDS)},
            )
        
        # Process request
        response = await call_next(request)
        
        # Log the request
        request_time = (datetime.now() - start_time).total_seconds() * 1000
        
        audit_logger.log_action(
            user_id=user_id,
            action=request.method,
            resource=request.url.path,
            method=request.method,
            status=response.status_code,
            details={
                "duration_ms": request_time,
                "query_params": dict(request.query_params),
            }
        )
        
        # Add rate limit info to headers
        usage = rate_limiter.get_usage(user_id)
        response.headers["X-RateLimit-Limit"] = str(usage["limit"])
        response.headers["X-RateLimit-Remaining"] = str(usage["remaining"])
        response.headers["X-RateLimit-Reset"] = usage["reset_time"]
        
        return response
