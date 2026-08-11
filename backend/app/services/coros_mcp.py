"""COROS official MCP client: OAuth 2.1 PKCE + JSON-RPC tools/call."""

from __future__ import annotations

import base64
import hashlib
import json
import re
import secrets
from pathlib import Path
from typing import Any
from urllib.parse import urlencode, urljoin, urlparse

import httpx

from app.config import (
    COROS_MCP_CLIENT_ID,
    COROS_MCP_SCOPES,
    COROS_MCP_URL,
    COROS_OAUTH_CLIENT_FILE,
    COROS_REDIRECT_URI,
)


class CorosMcpError(Exception):
    pass


def _parse_resource_metadata_url(www_authenticate: str | None) -> str | None:
    if not www_authenticate:
        return None
    match = re.search(r'resource_metadata="([^"]+)"', www_authenticate)
    return match.group(1) if match else None


def discover_mcp_auth(mcp_url: str = COROS_MCP_URL) -> dict[str, Any]:
    """Resolve regional MCP URL + OAuth metadata via unauthenticated probe."""
    with httpx.Client(timeout=30.0, follow_redirects=True) as client:
        probe = client.post(
            mcp_url,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
            },
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-03-26",
                    "capabilities": {},
                    "clientInfo": {"name": "advance-athlete-lab", "version": "0.1.0"},
                },
            },
        )
        resource_meta_url = _parse_resource_metadata_url(
            probe.headers.get("www-authenticate")
        )
        resolved_mcp = str(probe.url)
        if not resource_meta_url:
            parsed = urlparse(resolved_mcp)
            base = f"{parsed.scheme}://{parsed.netloc}"
            candidates = [
                f"{base}/.well-known/oauth-protected-resource/mcp",
                f"{base}/.well-known/oauth-protected-resource",
            ]
            for candidate in candidates:
                meta_resp = client.get(candidate)
                if meta_resp.status_code == 200:
                    resource_meta_url = candidate
                    resource_meta = meta_resp.json()
                    break
            else:
                raise CorosMcpError(
                    "Could not discover COROS MCP protected resource metadata."
                )
        else:
            meta_resp = client.get(resource_meta_url)
            meta_resp.raise_for_status()
            resource_meta = meta_resp.json()

        resource = resource_meta.get("resource") or resolved_mcp
        auth_servers = resource_meta.get("authorization_servers") or []
        if not auth_servers:
            raise CorosMcpError("COROS MCP metadata missing authorization_servers.")
        authorization_server = auth_servers[0].rstrip("/")

        as_meta = None
        for path in (
            "/.well-known/oauth-authorization-server",
            "/.well-known/openid-configuration",
        ):
            as_resp = client.get(f"{authorization_server}{path}")
            if as_resp.status_code == 200:
                as_meta = as_resp.json()
                break
        if as_meta is None:
            raise CorosMcpError("Could not load COROS OAuth authorization server metadata.")

        # Prefer the regional /mcp resource URL from metadata
        if resource.endswith("/mcp"):
            mcp_endpoint = resource
        else:
            mcp_endpoint = urljoin(resource.rstrip("/") + "/", "mcp")

        return {
            "mcp_url": mcp_endpoint,
            "resource": resource if resource.endswith("/mcp") else mcp_endpoint,
            "authorization_server": authorization_server,
            "authorization_endpoint": as_meta["authorization_endpoint"],
            "token_endpoint": as_meta["token_endpoint"],
            "registration_endpoint": as_meta.get("registration_endpoint"),
            "scopes_supported": as_meta.get("scopes_supported")
            or resource_meta.get("scopes_supported")
            or COROS_MCP_SCOPES.split(),
        }


def _load_persisted_client_id() -> str | None:
    if COROS_MCP_CLIENT_ID:
        return COROS_MCP_CLIENT_ID
    path = Path(COROS_OAUTH_CLIENT_FILE)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
        return data.get("client_id")
    except (OSError, json.JSONDecodeError):
        return None


def _persist_client_id(client_id: str, registration_endpoint: str) -> None:
    path = Path(COROS_OAUTH_CLIENT_FILE)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "client_id": client_id,
                "registration_endpoint": registration_endpoint,
                "redirect_uri": COROS_REDIRECT_URI,
            },
            indent=2,
        )
    )


def ensure_oauth_client(auth_discovery: dict[str, Any]) -> str:
    existing = _load_persisted_client_id()
    if existing:
        return existing

    registration_endpoint = auth_discovery.get("registration_endpoint")
    if not registration_endpoint:
        raise CorosMcpError(
            "COROS MCP does not expose dynamic client registration and "
            "COROS_MCP_CLIENT_ID is not configured."
        )

    payload = {
        "client_name": "Advance Athlete Lab",
        "redirect_uris": [COROS_REDIRECT_URI],
        "grant_types": ["authorization_code", "refresh_token"],
        "response_types": ["code"],
        "token_endpoint_auth_method": "none",
        "scope": COROS_MCP_SCOPES,
    }
    with httpx.Client(timeout=30.0, follow_redirects=True) as client:
        response = client.post(registration_endpoint, json=payload)
        if response.status_code >= 400:
            raise CorosMcpError(
                f"COROS dynamic client registration failed: {response.status_code} {response.text}"
            )
        data = response.json()
    client_id = data.get("client_id")
    if not client_id:
        raise CorosMcpError("COROS registration response missing client_id.")
    _persist_client_id(client_id, registration_endpoint)
    return client_id


def generate_pkce_pair() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest())
        .decode("ascii")
        .rstrip("=")
    )
    return verifier, challenge


def build_authorization_url(
    *,
    auth_discovery: dict[str, Any],
    client_id: str,
    state: str,
    code_challenge: str,
) -> str:
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": COROS_REDIRECT_URI,
        "scope": COROS_MCP_SCOPES,
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "resource": auth_discovery["resource"],
    }
    return f"{auth_discovery['authorization_endpoint']}?{urlencode(params)}"


def exchange_code_for_tokens(
    *,
    token_endpoint: str,
    client_id: str,
    code: str,
    code_verifier: str,
    resource: str,
) -> dict[str, Any]:
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": COROS_REDIRECT_URI,
        "client_id": client_id,
        "code_verifier": code_verifier,
        "resource": resource,
    }
    with httpx.Client(timeout=30.0, follow_redirects=True) as client:
        response = client.post(token_endpoint, data=data)
        if response.status_code >= 400:
            raise CorosMcpError(
                f"COROS token exchange failed: {response.status_code} {response.text}"
            )
        return response.json()


def refresh_access_token(
    *,
    token_endpoint: str,
    client_id: str,
    refresh_token: str,
    resource: str,
) -> dict[str, Any]:
    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": client_id,
        "resource": resource,
    }
    with httpx.Client(timeout=30.0, follow_redirects=True) as client:
        response = client.post(token_endpoint, data=data)
        if response.status_code >= 400:
            raise CorosMcpError(
                f"COROS token refresh failed: {response.status_code} {response.text}"
            )
        return response.json()


def _parse_mcp_http_body(response: httpx.Response) -> dict[str, Any]:
    content_type = response.headers.get("content-type", "")
    text = response.text.strip()
    if not text:
        raise CorosMcpError(f"Empty MCP response (HTTP {response.status_code})")

    if "text/event-stream" in content_type or text.startswith("event:") or "data:" in text:
        # Streamable HTTP: take the last JSON data payload
        payloads: list[dict[str, Any]] = []
        for line in text.splitlines():
            if line.startswith("data:"):
                chunk = line[5:].strip()
                if not chunk or chunk == "[DONE]":
                    continue
                try:
                    payloads.append(json.loads(chunk))
                except json.JSONDecodeError:
                    continue
        if not payloads:
            raise CorosMcpError(f"Could not parse MCP SSE response: {text[:500]}")
        return payloads[-1]

    try:
        return response.json()
    except json.JSONDecodeError as exc:
        raise CorosMcpError(f"Invalid MCP JSON response: {text[:500]}") from exc


class CorosMcpClient:
    def __init__(
        self,
        *,
        access_token: str,
        mcp_url: str,
        client_id: str | None = None,
        refresh_token: str | None = None,
        token_endpoint: str | None = None,
        resource: str | None = None,
        on_token_refresh: Any | None = None,
    ):
        self.access_token = access_token
        self.mcp_url = mcp_url
        self.client_id = client_id
        self.refresh_token = refresh_token
        self.token_endpoint = token_endpoint
        self.resource = resource or mcp_url
        self.on_token_refresh = on_token_refresh
        self._initialized = False
        self._request_id = 0

    def _next_id(self) -> int:
        self._request_id += 1
        return self._request_id

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }

    def _maybe_refresh(self) -> None:
        if not (self.refresh_token and self.token_endpoint and self.client_id):
            raise CorosMcpError("COROS access token rejected and refresh is unavailable.")
        token_data = refresh_access_token(
            token_endpoint=self.token_endpoint,
            client_id=self.client_id,
            refresh_token=self.refresh_token,
            resource=self.resource,
        )
        self.access_token = token_data["access_token"]
        if token_data.get("refresh_token"):
            self.refresh_token = token_data["refresh_token"]
        if self.on_token_refresh:
            self.on_token_refresh(token_data)

    def _rpc(self, method: str, params: dict[str, Any] | None = None) -> Any:
        payload = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": method,
            "params": params or {},
        }
        with httpx.Client(timeout=60.0, follow_redirects=True) as client:
            response = client.post(self.mcp_url, headers=self._headers(), json=payload)
            if response.status_code == 401:
                self._maybe_refresh()
                response = client.post(self.mcp_url, headers=self._headers(), json=payload)
            if response.status_code >= 400:
                raise CorosMcpError(
                    f"MCP {method} failed: HTTP {response.status_code} {response.text[:500]}"
                )
            body = _parse_mcp_http_body(response)

        if "error" in body and body["error"]:
            raise CorosMcpError(f"MCP {method} error: {body['error']}")
        return body.get("result")

    def initialize(self) -> Any:
        result = self._rpc(
            "initialize",
            {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "advance-athlete-lab", "version": "0.1.0"},
            },
        )
        # Best-effort notifications/initialized (stateless servers may ignore)
        try:
            with httpx.Client(timeout=15.0, follow_redirects=True) as client:
                client.post(
                    self.mcp_url,
                    headers=self._headers(),
                    json={
                        "jsonrpc": "2.0",
                        "method": "notifications/initialized",
                        "params": {},
                    },
                )
        except httpx.HTTPError:
            pass
        self._initialized = True
        return result

    def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> Any:
        if not self._initialized:
            self.initialize()
        result = self._rpc(
            "tools/call",
            {"name": name, "arguments": arguments or {}},
        )
        return _normalize_tool_result(result)


def _normalize_tool_result(result: Any) -> Any:
    """Unwrap MCP tool content blocks into plain JSON when possible."""
    if result is None:
        return None
    if isinstance(result, dict) and "content" in result:
        contents = result.get("content") or []
        texts: list[str] = []
        for item in contents:
            if isinstance(item, dict) and item.get("type") == "text":
                texts.append(item.get("text") or "")
            elif isinstance(item, dict) and item.get("type") == "resource":
                resource = item.get("resource") or {}
                if "text" in resource:
                    texts.append(resource["text"])
        if len(texts) == 1:
            text = texts[0]
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return text
        if texts:
            return texts
        if "structuredContent" in result:
            return result["structuredContent"]
    return result
