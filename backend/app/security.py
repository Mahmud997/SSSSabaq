import hashlib, hmac
from fastapi import Header, HTTPException
from .config import settings

def digest(value: str) -> str:
    return hmac.new(settings.app_secret.encode(), value.encode(), hashlib.sha256).hexdigest()

def require_workspace_key(x_workspace_key: str = Header(default="")) -> str:
    if not x_workspace_key or len(x_workspace_key) < 40:
        raise HTTPException(status_code=401, detail="Workspace key required")
    return digest(x_workspace_key)

def require_admin(authorization: str = Header(default="")):
    expected = "Bearer " + settings.admin_secret
    if not settings.admin_secret or settings.admin_secret.startswith("CHANGE_") or not hmac.compare_digest(authorization, expected):
        raise HTTPException(status_code=403, detail="Admin access denied")
    return True
