import os
from datetime import datetime, timedelta
from jose import jwt, JWTError

CLIENT_ID      = os.getenv("MCP_CLIENT_ID")
CLIENT_SECRET  = os.getenv("MCP_CLIENT_SECRET")
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
ALGORITHM      = "HS256"
TOKEN_EXPIRE_MINUTES = 60


def generate_token(client_id: str) -> dict:
    """Generate a JWT access token for a valid client."""
    payload = {
        "sub":   client_id,
        "iat":   datetime.utcnow(),
        "exp":   datetime.utcnow() + timedelta(minutes=TOKEN_EXPIRE_MINUTES),
        "scope": "mcp:tools"
    }
    token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=ALGORITHM)
    return {
        "access_token": token,
        "token_type":   "Bearer",
        "expires_in":   TOKEN_EXPIRE_MINUTES * 60,
        "scope":        "mcp:tools"
    }


def validate_token(token: str) -> dict:
    """Validate JWT token. Returns payload if valid."""
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError as e:
        raise ValueError(f"Invalid token: {str(e)}")