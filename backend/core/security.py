"""
Security helpers: API key auth, SSRF protection, permission scope resolution.
"""
import ipaddress
import os
import socket
from typing import Optional
from urllib.parse import urlparse

from fastapi import Header, HTTPException

API_KEY = os.getenv("API_KEY", "")
REQUIRE_AUTH_FOR_READS = os.getenv("REQUIRE_AUTH_FOR_READS", "false").lower() == "true"
INTERNAL_BROADCAST_KEY = os.getenv("INTERNAL_BROADCAST_KEY", "")
ALLOWED_PROXY_HOSTS = {
    h.strip().lower()
    for h in os.getenv("ALLOWED_PROXY_HOSTS", "").split(",")
    if h.strip()
}

DESTRUCTIVE_TOOLS = {"code_executor", "sql_query", "email_sender", "file_writer", "shell_exec"}
TOOL_SCOPES = {
    "github_search": "read",
    "web_browser": "read",
    "file_reader": "read",
    "memory_store": "write",
    "code_executor": "admin",
    "sql_query": "admin",
    "email_sender": "admin",
}


def resolve_permission_scope(tool_name: str, requested: Optional[str] = None) -> str:
    """Resolve scope server-side from tool registry; ignore client-supplied admin claims."""
    registry_scope = TOOL_SCOPES.get(tool_name, "read")
    if tool_name in DESTRUCTIVE_TOOLS:
        return registry_scope
    return registry_scope


async def verify_api_key(
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
):
    if not API_KEY:
        return
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


async def verify_api_key_reads(
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
):
    if REQUIRE_AUTH_FOR_READS:
        await verify_api_key(x_api_key)


async def verify_internal_key(
    x_internal_key: Optional[str] = Header(default=None, alias="X-Internal-Key"),
):
    env = os.getenv("ENVIRONMENT", "development")
    if not INTERNAL_BROADCAST_KEY:
        if env == "production":
            raise HTTPException(status_code=503, detail="Internal broadcast disabled")
        return
    if x_internal_key != INTERNAL_BROADCAST_KEY:
        raise HTTPException(status_code=401, detail="Invalid internal key")


def _is_private_ip(hostname: str) -> bool:
    try:
        for info in socket.getaddrinfo(hostname, None):
            addr = info[4][0]
            ip = ipaddress.ip_address(addr)
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                return True
    except socket.gaierror:
        return True
    return False


def validate_forward_url(url: str) -> str:
    """Validate proxy forward URL against SSRF. Returns normalized URL or raises."""
    parsed = urlparse(url)
    if parsed.scheme not in ("https", "http"):
        raise HTTPException(status_code=400, detail="forward_url must use http or https")
    if parsed.scheme == "http" and os.getenv("ENVIRONMENT", "development") == "production":
        raise HTTPException(status_code=400, detail="HTTP forward URLs not allowed in production")
    hostname = (parsed.hostname or "").lower()
    if not hostname:
        raise HTTPException(status_code=400, detail="Invalid forward_url host")
    if ALLOWED_PROXY_HOSTS and hostname not in ALLOWED_PROXY_HOSTS:
        raise HTTPException(status_code=403, detail="forward_url host not in allowlist")
    if _is_private_ip(hostname):
        raise HTTPException(status_code=403, detail="forward_url resolves to private/reserved IP")
    return url


async def verify_ws_api_key(api_key: Optional[str] = None) -> bool:
    if not API_KEY:
        return True
    return api_key == API_KEY
