"""MCP Server có Authentication — minh hoạ bảo mật cho production.

Server chạy qua HTTP (Streamable HTTP) thay vì stdio, kèm bearer token
verification. Chỉ request mang token hợp lệ mới được phép khám phá và gọi tool.

Luồng hoạt động:
  Client gửi request HTTP kèm header "Authorization: Bearer <token>"
    → MCP SDK tự chạy BearerAuthBackend để xác minh token
    → Token hợp lệ → cho phép truy cập tool
    → Token sai / thiếu → trả về 401/403

Cách chạy:
    pip install -r ../requirements.txt     # từ thư mục gốc repo
    python auth_server.py
    # Server lắng nghe tại http://localhost:8000/mcp
"""

from __future__ import annotations

import os

from mcp.server.auth.provider import AccessToken, TokenVerifier
from mcp.server.auth.settings import AuthSettings
from mcp.server.mcpserver import MCPServer

# --- Token store (production: dùng DB, Redis, hoặc JWT verification) ---
VALID_TOKENS: dict[str, str] = {
    os.environ.get("MCP_AUTH_TOKEN", "dev-token-abc123"): "dev-user",
    "prod-key-xyz789": "prod-service",
}


class StaticTokenVerifier(TokenVerifier):
    """Kiểm tra bearer token dựa trên danh sách tĩnh.

    Production nên thay bằng: JWT decode, OAuth introspection, hoặc
    gọi tới identity provider (Keycloak, Auth0, Google IAM, ...).
    """

    async def verify_token(self, token: str) -> AccessToken | None:
        client_id = VALID_TOKENS.get(token)
        if client_id is None:
            return None
        return AccessToken(token=token, client_id=client_id, scopes=["weather:read"])


# --- MCP Server — logic tool không biết gì về auth --------------------
AUTH_PORT = int(os.environ.get("AUTH_PORT", 8001))

mcp = MCPServer(
    "weather-secure",
    auth=AuthSettings(
        issuer_url=f"http://localhost:{AUTH_PORT}",
        resource_server_url=f"http://localhost:{AUTH_PORT}",
    ),
    token_verifier=StaticTokenVerifier(),
)

_MOCK_DB = {
    "Hanoi": "29°C, trời mưa",
    "Haiphong": "33°C, mưa rào",
    "Danang": "30°C, nhiều mây",
}


@mcp.tool()
def get_weather(city: str) -> str:
    """Lấy thời tiết hiện tại của một thành phố."""
    return f"{city}: {_MOCK_DB.get(city, '28°C, không có dữ liệu chi tiết')}"


if __name__ == "__main__":
    mcp.run(transport="streamable-http", host="0.0.0.0", port=AUTH_PORT)
