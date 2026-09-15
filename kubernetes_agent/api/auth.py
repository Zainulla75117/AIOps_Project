"""Admin authentication utilities.

Provides JWT-based authentication for the admin panel.
Password is validated against a bcrypt hash stored in config.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from kubernetes_agent.config import AgentConfig, get_config
from kubernetes_agent.utils.logging import get_logger

logger = get_logger(__name__)

_bearer_scheme = HTTPBearer(auto_error=False)

# JWT settings
_JWT_ALGORITHM = "HS256"
_JWT_EXPIRY_HOURS = 24


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain-text password against a bcrypt hash."""
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8"),
        )
    except Exception:
        return False


def create_access_token(cfg: AgentConfig | None = None) -> str:
    """Create a signed JWT for admin access."""
    cfg = cfg or get_config()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": "admin",
        "iat": now,
        "exp": now + timedelta(hours=_JWT_EXPIRY_HOURS),
    }
    return jwt.encode(payload, cfg.jwt_secret, algorithm=_JWT_ALGORITHM)


def decode_token(token: str, cfg: AgentConfig | None = None) -> dict:
    """Decode and validate a JWT. Raises on invalid/expired tokens."""
    cfg = cfg or get_config()
    return jwt.decode(token, cfg.jwt_secret, algorithms=[_JWT_ALGORITHM])


async def verify_admin_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    cfg: AgentConfig = Depends(lambda: get_config()),
) -> dict:
    """FastAPI dependency that validates the admin JWT.

    Returns the decoded token payload on success.
    Raises 401 if the token is missing, invalid, or expired.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = decode_token(credentials.credentials, cfg)
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )
