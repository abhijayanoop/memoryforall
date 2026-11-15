# MCP Python SDK: streamable HTTP, auth, and Claude connectors (state as of 2026-11-15)

Labels: VERIFIED = read in the cited primary source this session; UNVERIFIED = inference or not found. No API name below is invented; every identifier comes from a fetched source. Note: SDK doc pages were read through a summarizing fetch tool, so re-check identifiers against source at the pinned version.

## Summary

1. VERIFIED: `pip install mcp` now installs 2.x (latest on PyPI 2.3.0, released 2026-10-02). `FastMCP` was renamed `MCPServer` (`from mcp.server import MCPServer`). 1.x is maintenance only (pin `mcp>=1.28,<2`). Sources: https://pypi.org/pypi/mcp/json, https://py.sdk.modelcontextprotocol.io/whats-new/, GitHub releases (v2.0.0 2026-07-28, v2.3.0 2026-10-02).
2. VERIFIED: Mounting streamable HTTP at `/mcp` inside Starlette/FastAPI is supported. The host app must enter `mcp.session_manager.run()` in its own lifespan, and you must set `transport_security` allowed hosts for a public hostname. Source: https://py.sdk.modelcontextprotocol.io/run/asgi/
3. VERIFIED: The SDK's recommended design is resource-server only (`token_verifier=` + `auth=AuthSettings(...)`). Embedding an authorization server via `auth_server_provider=` exists but the docs say new servers should not use it. The SDK has no GitHub example and no persistent provider.
4. VERIFIED: Claude custom connectors are available on Pro and Max, need a publicly reachable HTTPS server on port 443, and Anthropic docs name Cloudflare Tunnel as a way to test. Claude needs OAuth via DCR, CIMD, or Anthropic-held credentials, with PKCE S256. UNVERIFIED: an end-to-end Pro + Cloudflare Tunnel + SDK-hosted AS run (no source documents this exact combination).
5. Practical consequence: GitHub OAuth is not itself an MCP-compliant authorization server (no DCR in the docs read), so "delegate to GitHub with a one-user allowlist" means building a thin AS in front of GitHub (own register/authorize/token/discovery endpoints), using the SDK's `OAuthAuthorizationServerProvider` interface or a separate AS app. See section D.

## Findings

### A. SDK version and status

- VERIFIED (https://pypi.org/pypi/mcp/json): latest 2.3.0, requires Python >=3.10. Recent releases: 1.26.0 (2026-01-24), 1.27.0 (2026-04-02), 1.28.0 (2026-06-16), 1.29.0 (2026-07-28), 1.30.0 (2026-09-07).
- VERIFIED (https://api.github.com/repos/modelcontextprotocol/python-sdk/releases): v2.0.0 2026-07-28 (stable, supports protocol revision 2026-07-28 and earlier); v2.1.0 2026-08-24; v2.2.0 2026-09-07 (idle Streamable HTTP sessions expire after 30 minutes by default; redirects followed only within the endpoint origin); v2.3.0 2026-10-02 (requires `httpx2>=2.10.0`).
- VERIFIED (whats-new page): HTTP client dependency moved from `httpx` to `httpx2`. `mcp.types` stays as an alias of the new `mcp_types` package. WebSocket transport removed.
- VERIFIED (v2.2.0 notes): deprecation warning when `AuthSettings` sets `resource_server_url` without `validate_token_resource`; 3.0 will default it to True.

### B. Streamable HTTP mounted in FastAPI/Starlette at /mcp

VERIFIED (https://py.sdk.modelcontextprotocol.io/run/asgi/, SDK 2.x):
- `mcp.streamable_http_app()` returns the ASGI app; default endpoint path is `/mcp`. With `Mount("/", app=mcp.streamable_http_app())` the endpoint is `/mcp`. `streamable_http_app(streamable_http_path="/")` with `Mount("/notes", ...)` serves at `/notes/`.
- Mounted sub-app lifespans do not run. The host must do `async with mcp.session_manager.run(): yield` in its lifespan; otherwise the first request fails with `RuntimeError: Task group is not initialized. Make sure to use run().` `mcp.session_manager` exists only after `streamable_http_app()` is called.
- FastAPI: pass `lifespan=` to `FastAPI(...)` and call `app.mount(...)` (page states the same pattern works since FastAPI subclasses Starlette).
- `Mount("/")` is a catch-all, so list your own routes first.
- DNS rebinding protection: behind a real hostname every request gets `421 Misdirected Request` until you pass `transport_security=` (class `TransportSecuritySettings` in `mcp.server.transport_security`, with `allowed_hosts`, `allowed_origins`). This matters for a Cloudflare Tunnel hostname. Migration guide: https://py.sdk.modelcontextprotocol.io/migration/
- Transport options (`json_response`, `stateless_http`, `streamable_http_path`, `max_request_body_size`, `event_store`, `retry_interval`, `transport_security`) are arguments of `run()`/`streamable_http_app()`, no longer of `MCPServer(...)`. `mount_path` removed. Default POST body limit 4 MiB (HTTP 413).
- `@mcp.custom_route()` endpoints are never authenticated.
- `streamable_http_app()` serves both 2025-era and 2026-era clients without configuration; on the 2026 path there is no `Mcp-Session-Id`.
- UNVERIFIED: exact signature for passing `TransportSecuritySettings` to `streamable_http_app()`; the pages read only say `transport_security=`.

### C. Auth in the SDK

Spec context, VERIFIED (https://modelcontextprotocol.io/specification/latest/basic/authorization, revision 2026-07-28):
- MCP server = OAuth 2.1 resource server; MUST implement RFC 9728 Protected Resource Metadata; AS MUST provide RFC 8414 or OIDC discovery.
- Client registration: Client ID Metadata Documents SHOULD be supported; Dynamic Client Registration (RFC 7591) is MAY and documented as deprecated, retained for backwards compatibility.
- Clients MUST send PKCE and the RFC 8707 `resource` param; servers MUST validate token audience; no tokens in query strings; invalid/expired token gets 401.
- Refresh tokens: AS retains discretion; resource servers SHOULD NOT advertise `offline_access`; clients MUST NOT assume refresh tokens are issued.
- AS implementation is out of scope of the spec; it may be hosted with the resource server or separately.

SDK server side, VERIFIED (https://py.sdk.modelcontextprotocol.io/run/authorization/ and source at https://github.com/modelcontextprotocol/python-sdk/tree/main/src/mcp/server/auth):
- `MCPServer("name", token_verifier=..., auth=AuthSettings(...))`. Both must be passed together or `ValueError`.
- `TokenVerifier` protocol (`mcp.server.auth.provider`): `async def verify_token(self, token: str) -> AccessToken | None`.
- `AccessToken` fields: `token, client_id, scopes, expires_at, resource, subject, claims`.
- `AuthSettings` (`mcp.server.auth.settings`): `issuer_url`, `resource_server_url`, `required_scopes`, `validate_token_resource`, `service_documentation_url`, `client_registration_options`, `revocation_options`, `identity_assertion_enabled`.
- `ClientRegistrationOptions`: `enabled` (default False), `client_secret_expiry_seconds`, `valid_scopes`, `default_scopes`. `RevocationOptions`: `enabled`.
- Protected Resource Metadata served at `/.well-known/oauth-protected-resource/mcp`; unauthenticated `/mcp` returns 401 with `WWW-Authenticate` containing `resource_metadata`.
- `get_access_token()` from `mcp.server.auth.middleware.auth_context` returns the verified `AccessToken` inside tools (None on stdio).
- Built-in AS interface (provider.py): `OAuthAuthorizationServerProvider` with `get_client`, `register_client`, `authorize`, `load_authorization_code`, `exchange_authorization_code`, `load_refresh_token`, `exchange_refresh_token(client, refresh_token, scopes)`, `load_access_token`, `revoke_token`, `exchange_identity_assertion` (default raises `unsupported_grant_type`). Models: `AuthorizationParams`, `AuthorizationCode`, `RefreshToken`, `AccessToken`; errors `RegistrationError`, `AuthorizeError`, `TokenError`; helper `construct_redirect_uri`; `ProviderTokenVerifier(provider)` adapts a provider into a verifier. `auth/routes.py` and `auth/handlers/` exist (directory listing); route details not read.
- So DCR (`register_client` + `ClientRegistrationOptions(enabled=True)`) and refresh tokens (`load_refresh_token`/`exchange_refresh_token`) are supported by the interface.
- VERIFIED warning: docs say the SDK provides only the resource-server half (verify, advertise, refuse), with no login page, consent screen, or token issuance, and describe `auth_server_provider=` as discouraged for new servers.
- UNVERIFIED: that `auth_server_provider=` on `MCPServer` in 2.3.0 serves `/authorize`, `/token`, `/register`, and AS metadata end to end as it did in 1.x.
- VERIFIED: official example `examples/servers/simple-auth` is in-memory, uses hardcoded demo credentials, is labeled "not a production-ready implementation", has no refresh support (`exchange_refresh_token` raises `NotImplementedError`), and does not mention GitHub. Its README describes a split AS (:9000, with `/introspect`) and resource server (:8001) plus a legacy combined mode (`legacy_as_server.py`).
- No SDK-provided GitHub or upstream-IdP delegation exists. VERIFIED by absence in the authorization page, the simple-auth example, and the docs index (llms.txt).

### D. GitHub sign-in with a one-user allowlist (design; glue is UNVERIFIED)

VERIFIED GitHub facts (https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/authorizing-oauth-apps):
- Authorize `https://github.com/login/oauth/authorize`; token `POST https://github.com/login/oauth/access_token`; user `GET https://api.github.com/user` with Bearer token.
- PKCE S256 supported; `state` recommended; code expires in 10 minutes.
- Refresh tokens are opt-in (expiring tokens setting or `offline_access`): access token 8 h, refresh token 6 months; refresh rotates both.

Design (UNVERIFIED as a combination; derived from the above):
1. Your AS exposes DCR (or CIMD) so Claude can register. With the SDK pattern, implement `OAuthAuthorizationServerProvider.authorize()` to store `AuthorizationParams` keyed by a random `state` and return the GitHub authorize URL (redirect_uri = your own callback, a custom route).
2. In the callback: exchange the GitHub code, call `GET /user`, compare the numeric user ID to the allowlisted ID, reject otherwise. (UNVERIFIED: the field name `id` is standard GitHub API but not in the page fetched. Comparing the numeric ID rather than the login is my reasoning, since logins can be renamed.)
3. On success mint an `AuthorizationCode` (set `subject`), redirect via `construct_redirect_uri` to Claude's redirect URI. Issue your own opaque MCP access/refresh tokens; do not pass the GitHub token to Claude (spec: servers MUST NOT accept or transit other tokens).
4. Persist clients/codes/tokens in a real store. The example's in-memory dicts lose state on restart and would force Claude to re-authenticate.
5. Set `resource` on tokens and `validate_token_resource=True`; `resource_server_url` must equal the public URL of `/mcp` (Claude requires an exact match, see E).
- Alternative (viability UNVERIFIED): put an external AS with DCR and GitHub social login in front (the SDK docs recommend an external IdP) and keep the Python server as a `TokenVerifier` only. The allowlist would then live in that IdP.

### E. Claude custom connectors on a personal plan via Cloudflare Tunnel

VERIFIED:
- Plans: custom connectors via remote MCP on Free (one), Pro, Max, Ultra, Team, Enterprise. Pro/Max add via Customize > Connectors > "+" > Add custom connector. Source: https://support.claude.com/en/articles/11175166-get-started-with-custom-connectors-using-remote-mcp
- Connections originate from Anthropic's cloud; server must be publicly reachable on standard HTTPS port 443 only. Same source.
- Tunnel: Anthropic's testing page says to expose a local server with "a tunnel such as Cloudflare Tunnel or ngrok" and add the tunnel URL as a custom connector; keep auth enabled. Source: https://claude.com/docs/connectors/building/testing
- That page documents a TS-SDK 403 `Invalid Host` for tunnel hostnames; the Python SDK analogue is the 421 in section B.
- Auth types: `oauth_dcr`, `oauth_cimd`, `oauth_anthropic_creds`, static headers (beta, limited orgs), `none`. `client_credentials` not supported. Source: https://www.claude.com/docs/connectors/building/authentication
- Callback `https://claude.ai/api/mcp/auth_callback`. PKCE S256 on every request; AS must advertise `"code_challenge_methods_supported": ["S256"]`; `/token` must accept `application/x-www-form-urlencoded`; `/register` is JSON.
- DCR registers Claude as a public client, anew on each fresh connection.
- Refresh: Claude refreshes on 401 and up to 5 minutes before expiry; return `invalid_grant` for dead refresh tokens; rotate refresh tokens and return the new one in the same response. Discovery/registration/token endpoints get 10 s, refresh 30 s.
- Discovery: 401 with `WWW-Authenticate` `resource_metadata` pointer; PRM `resource` must exactly match the MCP URL including path; Claude uses only the first `authorization_servers` entry; AS metadata host must be reachable from Anthropic egress (`160.79.104.0/21`). A WAF/CDN returning 403 can break the flow.
- The personal-plan UI also lets you enter your own OAuth client ID and secret instead of DCR (same support page).

UNVERIFIED:
- Which auth spec revisions Claude supports: a search snippet of Anthropic's page said 2025-03-26, 2025-06-18, 2025-11-25; not read directly, and 2026-07-28 support is unknown. The SDK serves 2025-era clients too, so likely fine.
- Cloudflare Tunnel (`cloudflared`) with Anthropic's IPs: Cloudflare Bot Fight Mode or WAF rules could return 403 (Claude's troubleshooting guidance warns about CDN/WAF blocks). No source tests this combination. Behavior of streamed (SSE) responses through the tunnel not checked.
- The Enterprise-only "MCP tunnels" feature is a separate product (per search result; https://claude.com/docs/connectors/mcp-tunnels/overview not read) and not applicable to a personal plan.
- Third-party reports of Claude-side OAuth bugs exist (anthropics/claude-ai-mcp issue 122, anthropics/claude-code issue 46140); not evaluated.

## Open assumptions

1. SDK pin: assume `mcp>=2.3,<3`. Before relying on `MCPServer(auth_server_provider=...)`, read `src/mcp/server/mcpserver/server.py` at that tag to confirm it is still wired and which routes it mounts.
2. Assume GitHub `/user` returns a numeric `id` usable as the allowlist key.
3. Assume a GitHub OAuth App with callback on the tunnel hostname; GitHub is used only for sign-in, and we issue our own MCP tokens, so GitHub expiring-token settings are irrelevant.
4. Assume a stable named tunnel hostname on your own domain, because `resource`, issuer, and the connector URL all embed it; a random quick-tunnel hostname would break registration.
5. Assume Cloudflare WAF/Bot settings permit Anthropic egress `160.79.104.0/21`; test with Claude and MCP Inspector (`npx @modelcontextprotocol/inspector --cli <url> --transport http --method tools/list`, from Anthropic's testing page).
6. Assume Claude keeps accepting DCR although the spec deprecates it (Anthropic lists `oauth_dcr` as supported). Server-side CIMD support in the SDK was not found in the sources read.
7. Assume a durable single-user store (e.g. SQLite) and that we implement refresh-token rotation, `invalid_grant`, and sub-10-second endpoint latency ourselves, since the SDK example does not.
8. Assume the TS-SDK-oriented Anthropic testing guidance about Host validation transfers to the Python SDK's `TransportSecuritySettings` behavior.
