# Provider internal conversation endpoints (claude.ai, chatgpt.com)

Researched 2026-11-15. Neither provider documents these endpoints; all schema facts come from third-party open-source exporters and can change without notice. I could not re-verify against live traffic (no authenticated session), so "VERIFIED" means "confirmed in the cited source's code or text", not "confirmed live today".

Labels: VERIFIED (source URL given) / UNVERIFIED (inferred or not found).

## Summary

- Both web apps use unofficial, undocumented, cookie/bearer-authenticated JSON endpoints. Any adapter must be defensive (optional fields, schema-drift tests, fixtures).
- ChatGPT: list is offset/limit (max 100); conversation is a `mapping` node graph with `current_node` as the active leaf; auth is a bearer token obtained from `/api/auth/session`.
- claude.ai: org-scoped REST; messages are a flat `chat_messages` array linked by `parent_message_uuid`, with `current_leaf_message_uuid` as the active leaf; auth is browser session cookies.
- Both providers' consumer terms prohibit automated/scripted access outside their APIs. A browser extension acting on the user's own logged-in session is still a grey area; the official data-export (conversations.json) is the lower-risk ingest path.
- Prefer official export files as the primary importer; treat live-endpoint capture as best-effort, user-initiated, and rate-limited.

## claude.ai

### Endpoints
- VERIFIED: base `https://claude.ai/api`. `GET /organizations` returns an array; the script uses `organizations[0].uuid` as org id. `GET /organizations/{orgId}/chat_conversations` lists conversations; `GET /organizations/{orgId}/chat_conversations/{chatId}` fetches one. Source: https://greasyfork.org/scripts/499310-claude-ai-sharegpt-exporter/code
- VERIFIED: single-conversation fetch with tree: `/api/organizations/${orgId}/chat_conversations/${chatId}?tree=True&rendering_mode=messages&render_all_tools=true`; chatId taken from page URL after `/chat/`. Source: https://github.com/Emnolope/claude-conversation-export
- UNVERIFIED: list pagination params (limit/offset/cursor) and list-item fields. The cited scripts pass no query params to the list call; I found no source documenting pagination. Do not assume any.
- UNVERIFIED: whether `tree=True` is required to get all branches vs. only the active path. One source claims Claude stores a tree/DAG and the UI shows one branch (search summary of the Emnolope README), but not confirmed in code.

### Tree / branches / active leaf
- VERIFIED: response has `chat_messages` (array), `current_leaf_message_uuid`, `name` (title). Each message has `uuid`, `parent_message_uuid`, `sender`, `text`. Active branch = walk from `current_leaf_message_uuid` up via `parent_message_uuid`, stopping at root sentinel `00000000-0000-4000-8000-000000000000`. Source: greasyfork URL above.
- VERIFIED: also read per message: `created_at`, `content` (Emnolope URL above).
- VERIFIED (official-export shape, not live API): conversation has `uuid`, `account.uuid`, `name`, `summary`, `created_at`, `updated_at`, `chat_messages`; message has `uuid`, `sender` (`human`|`assistant`), `created_at`, `updated_at`, `content` (array of blocks: `text`, `thinking`, `tool_use`{id,name,input}, `tool_result`{name,is_error,content}), `attachments`, `files`. `tool_result` lacks a `tool_use_id`. That adapter treats message `uuid` as possibly missing. Source: https://docs.rs/pond-db/0.3.2/src/pond/adapter/claude_ai_export.rs.html
- UNVERIFIED: whether the official export contains `parent_message_uuid`/`current_leaf_message_uuid` (a Reddit report of KeyError on `parent_message_uuid` suggests it may be missing/null in some data; unconfirmed).

### Auth
- VERIFIED: session cookies only; fetch with `credentials:"include"`, no custom auth header, only `Content-Type: application/json`. Sources: Emnolope and greasyfork URLs above.
- UNVERIFIED: any CSRF or extra headers (e.g. anthropic-client-* headers) currently required; none appear in the cited scripts.

### Rate limits / terms
- VERIFIED: Anthropic Consumer Terms prohibit scraping/harvesting and "access the Services through automated or non-human means, whether through a bot, script, or otherwise" except via an API key; also prohibit bypassing protective measures and sharing credentials. Source: https://www.anthropic.com/legal/consumer-terms
- UNVERIFIED: any numeric rate limit on these endpoints. None documented.

## chatgpt.com

### Endpoints
- VERIFIED: path set (relative to the app's backend-api base): `/conversations` (list), `/conversation/:id` (single), `/share/:id`, `/gizmos/:gizmo/conversations` (project conversations), `/gizmos/snorlax/sidebar`, `/files/download/:id`; session at `/api/auth/session`. Source: https://raw.githubusercontent.com/pionxzh/chatgpt-exporter/master/src/api.ts
- VERIFIED: list `GET /backend-api/conversations?offset=0&limit=100`; response `items`, `limit`, `offset`, `total`; each item has `id`, `title`, `create_time`. `limit` > 100 returns validation error ("ensure this value is less than or equal to 100"). `total` was off by one in one observation. Source: https://gist.github.com/0xdevalias/4e54bb28a02db5357ea4fa3a872fc5fc (host there was chat.openai.com, older; current host likely chatgpt.com, UNVERIFIED).
- VERIFIED: pionxzh response type `ApiConversations`: `has_missing_conversations`, `items`, `limit`, `offset`, `total`, `cursor`. Main list page size 100, offset-advanced; stops on empty page, `offset+limit >= total`, or neither total nor cursor. Project conversations use `cursor` + `limit` (page size 50). `order` is not used in that code. (pionxzh URL)
- VERIFIED (secondary): main list excludes conversations inside Projects; one article reported a list returning far fewer than actual (775 of 10,500) - title only seen via search, body not fetched. UNVERIFIED as a current behavior; treat `has_missing_conversations` as a signal to surface.

### Tree / branches / active leaf
- VERIFIED: conversation object: `create_time`, `conversation_id`(optional), `current_node`, `mapping`, `moderation_results`, `title`, `is_archived`, `update_time`, `safe_urls`. `mapping` is keyed by node id; node = `{id, message?, parent?, children: string[], thinking?}`. Active branch = walk `parent` from `current_node` to root; siblings in `children` are alternate branches. (pionxzh URL; the walk-algorithm itself is the standard use, inferred.)
- VERIFIED: node `message`: `id`, `author {role: system|assistant|user|tool, name?, metadata}`, `content` (discriminated by `content_type`; text has `parts: string[]`; others: `code`, `execution_output`, `multimodal_text`, `thoughts`, `reasoning_recap`), `status`, `end_turn?`, `weight`, `metadata?` (e.g. `model_slug`, `citations`, `is_visually_hidden_from_conversation`), `recipient?`, `create_time?`, `update_time?`, `channel?`. (pionxzh URL)
- UNVERIFIED: root node conventions (root usually has no `message`; inferred from optional `message?`), and which nodes are hidden/system.

### Auth
- VERIFIED: `Authorization: Bearer <access token>` (also `X-Authorization` with the same value), plus `Chatgpt-Account-Id` only for workspace accounts. Token obtained from `/api/auth/session`; accounts at `/accounts/check/v4-2023-04-27`. Device id appears as cookie `oai-did`, not sent as header by that tool. (pionxzh URL)
- UNVERIFIED: whether current ChatGPT additionally requires sentinel/proof-of-work or `oai-device-id` headers for these GETs; not seen in the cited code.

### Rate limits / terms
- VERIFIED: 429 handled via `Retry-After` header (fallback 30s fetch / 60s probe); 401/403 not distinguished by that client. (pionxzh URL)
- VERIFIED (secondary only): OpenAI Terms of Use list automatic or programmatic extraction of data or Output as prohibited (search-result summary; official page returned HTTP 403 to my fetcher, so exact wording UNVERIFIED). Check https://openai.com/policies/terms-of-use/ manually.

## Official-export alternative
- UNVERIFIED in this research: ChatGPT/Claude settings "Export data" emails a zip with `conversations.json` (Claude zip described by third-party guides as `conversations.json`, `projects.json`, `users.json`). ChatGPT's export reuses a `mapping`/`current_node` tree (inferred; not confirmed). Verify with real files.

## Open assumptions
1. Claude list endpoint pagination (params, max page size, item fields) is unknown - needs live capture.
2. Claude `tree=True` semantics (all branches vs active path) unconfirmed.
3. Claude root sentinel `00000000-0000-4000-8000-000000000000` may change; code should also stop on null/missing parent or unknown id.
4. Claude message `uuid` is stable across fetches (assumed; dedupe key).
5. ChatGPT current host/paths (`chatgpt.com/backend-api/...`) and required extra headers (sentinel, device id) unverified for late 2026.
6. ChatGPT `total` is unreliable; use empty-page termination plus dedupe by `id`.
7. ChatGPT project conversations are absent from the main list and need the gizmo endpoints.
8. ChatGPT node `id` equals message `id` (inferred from both having `id`).
9. No numeric rate limits are published; use conservative concurrency and honor `Retry-After`.
10. ToS risk: both providers prohibit scripted access; legal/policy decision needed before shipping a live-scrape feature. Prefer user-initiated export-file import.
11. All schemas may change; add fixture-based contract tests and tolerant parsing.
