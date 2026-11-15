# MCP for Claude, extension injection for ChatGPT and Gemini

Claude supports custom MCP connectors on personal plans, so it pulls context through MCP. ChatGPT custom MCP is Business/Enterprise only and Gemini's custom apps are US-only, so the extension pushes a Brief into those prompts instead. Both paths use one retrieval service, so enabling MCP on another Host later is configuration, not a rewrite.
