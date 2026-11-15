# Clerk is the authorization server for MCP and the web UI

Claude's connector needs a full OAuth flow, and hand-building an authorization server (registration, PKCE, rotating refresh tokens) is the riskiest piece of week one. Instead Clerk issues the tokens and the memoryforall server only verifies them; sign-ups are restricted to the owner's single account. Only sign-in identity reaches Clerk, never conversation data, which keeps ADR 0006 intact. The cost is a hosted dependency for login, and a provider outage locks the owner out of the MCP endpoint and web UI.
