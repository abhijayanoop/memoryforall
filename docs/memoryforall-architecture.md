# memoryforall — Cross-Platform AI Context Layer

Nov 14, 2026 · @Abhijay

## Overview

memoryforall automatically captures your ChatGPT, Claude and Gemini conversations. It turns them into a store of decisions, requirements and facts, organized by project and kept current over time. It then hands the relevant slice to whichever AI platform you're using right now. memoryforall never generates answers. ChatGPT, Claude or Gemini always writes the reply. memoryforall only decides what context they see.

**What it is:** a context layer for AI platforms. It handles capture, extraction, retrieval and delivery.

**What it is not:** a chatbot, an answer engine, or a multi-tenant SaaS product.

Principles that every component follows:

- **No LLM calls at query time.** Retrieval is embedding the query plus ranking, and the brief is assembled from templates. LLMs run only at ingest time, to extract items and judge supersession.
- **Automatic capture.** No manual uploads. The browser extension backfills your history and keeps syncing.
- **Visible, user-approved context.** Nothing is injected silently unless you've turned on auto-attach for that project.
- **Traceable.** Every stored item links back to the exact messages it came from.
- **Your data stays on your machine by default.** Postgres runs on your home server. Only scrubbed text reaches hosted APIs.

*memoryforall* is the project name and the repo name.

## Decision log

Every decision below was settled in the design review on 14 Nov 2026. Change one here first, then update the sections that depend on it.

| Area | Decision | Why |
| --- | --- | --- |
| Sources | ChatGPT and Claude first; Gemini is a week-3 stretch goal | Cleanest data. Gemini's internal format is obfuscated |
| Capture | Browser extension calls each provider's internal JSON endpoints with your session. It backfills your history, then syncs live | Automatic capture with no uploads. Gives message IDs and branches, which scraping the page doesn't |
| Delivery: Claude | MCP server | Claude supports custom MCP connectors on personal plans |
| Delivery: ChatGPT, Gemini | Extension shows a suggestion chip; you attach with one click; auto-attach is optional per project | ChatGPT custom MCP is Business/Enterprise only. Gemini's custom apps are US-only |
| Retrieval unit | Extracted items, with raw chunks behind them for detail | Answers "what did I decide", not just "what did I say" |
| Change over time | Ingest-time judge labels each new item new / duplicate / supersedes / contradicts | Retrieval only returns current decisions, and history is kept |
| Projects | LLM assigns a project, matched against existing projects; the UI lets you merge and rename | Automatic, with readable names |
| Users | Single user, self-hosted | Multi-tenancy is already proven in DocuMind |
| Privacy | Hosted APIs behind an interface; secrets and personal data scrubbed first | A switch to fully local is a config change |
| Query-time LLM | None | Fast, cheap, predictable, and keeps answer generation in the host platform |
| Echo loop | Marked context blocks and MCP tool results are removed before extraction | Stops injected context being re-learned as new facts |
| Edits and branches | Index only the active branch; save messages idempotently by provider message ID; extract only new messages | Conversations change after you capture them |
| Stack | Python, FastAPI, Postgres with pgvector, Redis. Extension in TypeScript on WXT (Manifest V3) | Builds on the Circular stack; extension uses your strongest language |
| Hosting | Home server behind Cloudflare Tunnel; the same Docker Compose setup deploys to the cloud for a live demo | Data stays home |
| Auth | MCP and web UI: sign-in through Clerk, restricted to one account; the server only verifies tokens (ADR 0007). Extension: device pairing with a revocable token | No open endpoint serving your history, and no hand-built OAuth server |
| Backfill | Last 6 months automatically; older conversations on demand; monthly spending cap | Controls cost and rate limits |
| Timebox | 3 weeks, with an eval that runs in CI through EvalKit | Proves the token and accuracy claim |
| Forget | Forgetting a conversation tombstones it so capture skips it, and a hard purge after 7 days removes its raw payloads, messages and chunks, plus items sourced only from it | Soft delete alone would leave the text in `raw_payloads` and re-capture it on the next sync |
| Summary items | Replaced in place, never superseded, and left out of briefs; reachable through `search_history` and `get_source` | They are rewritten as a conversation grows, so supersession does not apply |
| Orphaned items | An item is `orphaned` only when all its sources are orphaned, and returns to `active` if any source becomes active again | Switching back to an earlier branch should restore its items |
| Supersession direction | Follows `said_at`, never ingest time | Re-syncing an old conversation must not demote newer decisions |
| Provider terms | Personal-use risk accepted; official export import is the fallback (see ADR 0001) | Anthropic's consumer terms prohibit scripted access except via API key |

## System architecture

memoryforall has three parts: a browser extension, a home server, and hosted model APIs that only ever see scrubbed text.

&#91;embedded content: memoryforall architecture · browser, home server, hosted APIs\]

The extension is the only part that runs inside the providers' pages. Everything that learns from or ranks your history runs on the home server. Postgres is the single store that both delivery paths read from.

## Capture and ingestion pipeline

The extension acts as a simple pipe: it sends each provider's raw JSON to the server. All the parsing logic runs in Python on the server, where it can be tested.

**In the extension (background service worker):**

1. **Backfill.** On first pairing, page through each provider's conversation-list endpoint for the last 6 months. Throttle to about 1 request per second, and keep the current position so a restart resumes where it stopped.
2. **Live sync.** When you open a conversation, or a reply finishes streaming, fetch that conversation's JSON again. Wait 10 seconds after the last change, so a long chat triggers one fetch instead of dozens.
3. **Ship.** Group payloads into batches of up to 20 conversations and send them to `POST /ingest` with the device token. Queue failed batches in IndexedDB and retry with exponential backoff.

**On the server:**

1. **API** checks the token, stores the raw payload in `raw_payloads` (useful for replaying and for test fixtures), puts one job per conversation on a Redis queue, and returns `202 Accepted`.
2. **Adapter** (one per provider) turns the raw JSON into the shared `Conversation` / `Message` shape. It walks the message tree from the active leaf back to the root, so only the current branch is kept.
3. **Message save** inserts each message keyed on `(provider, provider_message_id)`, so re-saving the same message does nothing. It then finds the new messages since the last run and marks messages on abandoned branches as `orphaned`.
4. **Echo filter** removes `⟦ctx:v1 …⟧ … ⟦/ctx⟧` blocks and MCP tool-call results from the text sent to extraction.
5. **Scrub** replaces secrets and personal data with placeholders, and logs only how many were redacted.
6. **Extract** sends the new messages, plus the 6 messages before them for context, to the LLM and gets back typed items as JSON.
7. **Project resolution** matches each item to an existing project or creates a new one.
8. **Supersession judge** compares each new item against similar items in the same project and labels it.
9. **Embed and index** stores embeddings for new items and raw message chunks, and updates the full-text search columns.
10. **Cost ledger** records the tokens used by each LLM call and pauses the queue at the monthly cap.

Use **arq** for the queue: a small async job queue built on Redis that fits FastAPI's async style. A job is the processing of one conversation's new messages. Jobs must be safe to retry, because every step above is idempotent.

## Data model

One Postgres database holds everything: relational data, vectors (pgvector) and keyword search (`tsvector`). Use Alembic for migrations from day one.

| Table | Key columns | Notes |
| --- | --- | --- |
| `devices` | id, name, token\_hash, scopes, created\_at, revoked\_at | Paired extensions. Store only a hash of the token |
| `raw_payloads` | id, provider, provider\_conv\_id, payload jsonb, received\_at | Untouched input, for replays and test fixtures |
| `conversations` | id, provider, provider\_conv\_id (unique per provider), title, active\_leaf\_id, last\_processed\_msg\_id, project\_hint | One row per provider conversation |
| `messages` | id, conversation\_id, provider\_message\_id (unique), parent\_id, role, content, created\_at, branch\_state (active / orphaned), has\_injected\_ctx | The message tree |
| `chunks` | id, message\_id, text, embedding vector(1536), tsv tsvector | Raw message chunks for detail retrieval |
| `projects` | id, name, aliases text\[\], embedding, created\_at | Matched against when extraction assigns a project |
| `items` | id, project\_id, type, text, embedding, tsv, status (active / superseded / orphaned / deleted), said\_at, provider, confidence | The main retrieval unit |
| `item_sources` | item\_id, message\_id | Links each item to the messages it came from |
| `item_relations` | from\_item, to\_item, relation (supersedes / duplicate / contradicts), judged\_at, rationale | Supersession history |
| `llm_calls` | id, job\_id, purpose, model, input\_tokens, output\_tokens, cost\_usd, created\_at | Cost ledger |
| `redactions` | job\_id, kind, count | Counts only, never the redacted values |

Indexes: HNSW on `items.embedding` and `chunks.embedding`, GIN on both `tsv` columns, and a B-tree on `(project_id, status, said_at)`. Set the embedding dimension in one config value, so swapping models is a migration rather than code changes all over the codebase.

## Extraction and supersession

Extraction turns conversation into a small set of typed, sourced items. The supersession judge keeps that set current. These two steps are what make memoryforall more than RAG over chat logs.

**Item types (no others):**

| Type | Example |
| --- | --- |
| `decision` | Use pgvector, not Pinecone, for Sentinel's store |
| `requirement` | Every MCP tool must accept a token budget |
| `fact` | Saathi runs on the Swiggy MCP over WhatsApp |
| `open_question` | Should Gemini capture fall back to scraping the page? |
| `code_artifact` | Snippet plus one line on what it does |
| `summary` | One per conversation, rewritten as the conversation grows |

**How extraction works:**

- One call per job, using a cheap, fast model. The output must match a Pydantic `ExtractionResult` schema through structured output. Validate it, retry once with the validation error included, then send the job to the failed-jobs queue.
- The prompt includes the list of existing projects (names and aliases), so the model reuses a project name instead of inventing a new one.
- Each item returns `source_message_ids`. Reject any item that cites a message ID that wasn't in the input; that's a cheap check against made-up citations.
- Drop items with confidence below 0.5. Keep conversational noise (greetings, "thanks", restated questions) out of the prompt's examples.

**Project resolution:** an exact match on name or alias wins. Otherwise compare the proposed project name's embedding with each project's. If similarity is 0.85 or more, attach the item to that project and add the new name as an alias. Otherwise create a new project. These thresholds are starting values; tune them against the eval.

**Supersession judge:**

1. For each new item, fetch the 5 most similar `active` items of the same type in the same project.
2. If there are none, mark the item `new` and skip the LLM call. Most items take this path, which keeps cost low.
3. Otherwise make one judge call that returns one label per candidate: `new` / `duplicate` / `supersedes` / `contradicts`, with a one-line rationale.
4. `duplicate`: add the new item's sources to the existing item and drop the new one. `supersedes`: mark the old item `superseded` and record the relation. `contradicts` (same date range, unclear winner): keep both `active` and flag them in the UI for you to resolve.

Order matters: when backfilling, process conversations oldest first, so "supersedes" points forward in time.

## Retrieval and context packing

At query time memoryforall makes one embedding call and runs two Postgres queries. There are no LLM calls. Target under 300 ms at p95 on the home server.

**Hybrid search:**

1. Embed the query.
2. Run vector search (top 30 by cosine distance) and full-text search (top 30 by `ts_rank`) over `items`, filtered to `status = 'active'` plus any project or type filter.
3. Merge the two lists with **Reciprocal Rank Fusion**: each item scores the sum of `1 / (60 + rank)` across the lists it appears in. It needs no score normalization, which makes it a robust default.
4. Multiply by a recency weight, `0.85 + 0.15 × exp(−age_days / 90)`, so newer items win close ties without burying older ones.
5. Run the same search over `chunks` only when `get_source` asks for detail, or the item results are thin (fewer than 3 above the threshold).

**Relevance threshold:** the extension's chip appears only when the top fused score is above a cutoff you calibrate on the eval set. Use the same cutoff to decide whether `search_history` reports "nothing relevant".

**Brief assembly (`get_project_brief`):**

- Fixed section order: Decisions → Requirements → Facts → Open questions → Code (titles only).
- One line per item: `- [decision · Claude · 2026-10-02] Use pgvector, not Pinecone (id: it_8f2)`.
- Fill greedily by rank within each section until `token_budget` is used up, counting tokens with `tiktoken`. Drop the code section first, then facts.
- Always wrap the brief in the context markers, so the echo filter removes it if it gets captured back.

The item IDs in the brief let the host model call `get_source(item_id)` for detail. That's how the token-saving works: a compact brief first, full detail only on request.

## Delivery

Claude pulls context through MCP. ChatGPT and Gemini get it pushed by the extension. Both paths call the same retrieval service and produce the same marked brief.

**MCP server (for Claude).** Built with the official MCP Python SDK, using the streamable HTTP transport, mounted at `/mcp` inside the FastAPI app.

| Tool | Inputs | Returns |
| --- | --- | --- |
| `list_projects` | none | Project names, item counts, last activity |
| `get_project_brief` | project, token\_budget = 1500 | The packed brief described in Retrieval and context packing |
| `search_history` | query, project?, types?, include\_superseded = false, k = 8 | Ranked items with provider, date and ID |
| `get_source` | item\_id | The source messages, with up to 4 neighbouring messages |

Tool descriptions do half the work: they tell Claude *when* to call each tool. Write them like API docs. For example: "Call `get_project_brief` when the user refers to a project, decision or past discussion that isn't in this conversation."

**Extension (for ChatGPT and Gemini).** A content script per provider keeps all of that provider's DOM selectors in one `selectors.ts` file.

1. Watch the prompt box. 600 ms after you stop typing, and only if the text has at least 20 characters, call `POST /suggest`.
2. If the top score is above the threshold, show a chip next to the send button, for example: *3 items · Sentinel · via Claude — attach?* Hovering shows the item lines.
3. On click, insert the brief at the top of the prompt, inside `⟦ctx:v1 id=…⟧ … ⟦/ctx⟧`. You can see it and delete it before you send.
4. **Auto-attach**, a per-project toggle in the extension popup, skips the click for projects you trust. The chip still appears, showing that context was attached.

**Echo-loop rule:** every block memoryforall produces carries the marker, and every adapter removes markers and MCP tool results before extraction. A contract test captures an injected conversation again and asserts that 0 new items are created.

## Security and privacy

memoryforall holds your entire AI chat history, so treat it like a password manager. Every way in is authenticated, and only scrubbed text leaves your machine.

| Surface | Control |
| --- | --- |
| Web UI | Sign in through Clerk, restricted to one account; everyone else is rejected |
| MCP endpoint | OAuth, following the MCP authorization spec. Clerk is the authorization server; the MCP server only verifies its tokens with the SDK's token verifier. Check the SDK's current auth APIs before building. Clerk issues refresh tokens, so connectors don't silently log out |
| Extension | Pairing: the web UI shows a 6-digit code that expires in 5 minutes. The extension exchanges it for a device token scoped to `ingest` and `suggest`. Store only the token's hash; revoke it from the UI |
| Network | Cloudflare Tunnel only, with no open ports on the home router. TLS ends at Cloudflare |
| Hosted LLM and embedding calls | Scrub every outgoing request: `detect-secrets` plus custom rules (AWS keys, JWTs, `postgres://` URLs, `.env` lines), then Presidio for emails and phone numbers. The placeholders, like `⟦SECRET:aws_key⟧`, are what get stored in `items` |
| Data at rest | Postgres on the home server with full-disk encryption. Nightly `pg_dump` to an encrypted backup |
| Correction | "Forget item" and "forget conversation" in the UI. Both are soft deletes, with a hard purge after 7 days |

State the provider-terms risk plainly in the README: capture uses undocumented web endpoints with your own session, for personal use only. Don't publish the extension to the Chrome Web Store.

## Evaluation plan

The eval measures four things, runs in CI through EvalKit, and produces the README's headline table. Build the datasets in week 1 from your real history, before you tune anything.

| Suite | Dataset | Metric | Pass bar (initial) |
| --- | --- | --- | --- |
| Retrieval | 25 questions across 3–4 of your projects, each labeled with the item IDs that should come back | recall@5, MRR | recall@5 ≥ 0.8 |
| Supersession judge | 40 hand-labeled item pairs covering all four labels | Precision and recall per label | `supersedes` precision ≥ 0.85 |
| End to end | The same 25 questions plus written gold answers | LLM-judge correctness and input tokens, for 3 setups | Brief matches the full dump on correctness, with ≥ 70% fewer tokens |
| Echo regression | 5 conversations with injected context, captured again | New items created | Exactly 0 |

**End-to-end setup.** memoryforall never answers, so the eval stands in for the host platform. It calls the OpenAI and Anthropic APIs with the question plus one of three contexts:

1. **No context.** The floor.
2. **Full dump.** The entire source conversations pasted in. The "re-explain everything" baseline.
3. **memoryforall brief.** `get_project_brief` output at a 1,500-token budget.

A separate judge model grades each answer against the gold answer on a 0–2 scale. Report correctness and input tokens per setup and per host model. That 3 × 2 table is the main README exhibit.

The pass bars are starting targets, not results; adjust them once the first run gives you real numbers. CI fails when any suite drops more than 5 points below its last recorded score on `main`.

## 3-week build plan

Each week ends with something working that you can demo. Week 1 runs data from Claude through to MCP, week 2 adds intelligence and ChatGPT, and week 3 adds proof and polish. Each week follows the same order: concepts, then build, then an understanding check.

### Week 1 — Claude, captured end to end

Concepts: MV3 service workers vs content scripts · idempotent upserts · arq job semantics · MCP tools and streamable HTTP.

- [ ] Days 1–2: Repo, Docker Compose (Postgres + pgvector, Redis, API, worker), Alembic, schema for `raw_payloads`, `conversations`, `messages`. WXT extension skeleton with device pairing.
- [ ] Day 3: Claude adapter. Save 5 real raw payloads as fixtures and write contract tests (active-branch walk, idempotent re-save).
- [ ] Day 4: Backfill and live sync for claude.ai, `POST /ingest`, the queue, saving messages.
- [ ] Day 5: Chunk, embed, and a basic hybrid `search_history` over chunks.
- [ ] Days 6–7: MCP server with `search_history` and `get_source`, exposed through Cloudflare Tunnel and connected in Claude. Start writing the 25 eval questions from your real history.

Understanding check:

- [ ] Can you explain why the extension forwards raw JSON instead of parsing it?
- [ ] Can you show that ingesting the same conversation twice changes 0 rows?
- [ ] Can you explain how Claude decides to call your tool, and what the tool description changes?

### Week 2 — Extraction, supersession, ChatGPT

Concepts: structured output with Pydantic · LLM-as-judge design · Reciprocal Rank Fusion · token budgeting.

- [ ] Day 8: Scrubbing (detect-secrets + Presidio), the `redactions` log, the cost ledger and spending cap.
- [ ] Days 9–10: Extraction into `items` and `item_sources`, project resolution, and item-level hybrid search with the recency weight.
- [ ] Day 11: Supersession judge plus `item_relations`. Hand-label the 40 judge pairs.
- [ ] Day 12: `get_project_brief` with packing to the token budget, plus `list_projects`.
- [ ] Days 13–14: ChatGPT adapter and fixtures, the chip and injection content script, context markers, the echo filter and the echo regression test.

Understanding check:

- [ ] Can you show a decision that changed across ChatGPT and Claude, and the brief showing only the latest one?
- [ ] Can you explain why RRF needs no score normalization?
- [ ] Can you trace one secret from captured text to its placeholder in `items`?

### Week 3 — Proof, UI, stretch

Concepts: CI eval gating · HTMX partial updates · OAuth for MCP.

- [ ] Day 15: All four eval suites wired into EvalKit, the first baseline run recorded, the relevance threshold calibrated.
- [ ] Day 16: OAuth on the MCP endpoint, GitHub sign-in for the UI.
- [ ] Day 17: Web UI with projects (merge and rename), the item browser with supersession history, forget, and ingestion and cost status.
- [ ] Day 18: Tune with the eval, adding the reranker only if precision is weak. Freeze the README numbers.
- [ ] Day 19: Stretch goal: Gemini capture and injection. Skip it without guilt if days 15–18 slipped.
- [ ] Days 20–21: README with the architecture diagram and the 3 × 2 results table, a 3-minute demo video (decide in Claude, continue in ChatGPT), and a cloud deploy for the live demo.

Understanding check:

- [ ] Can you defend every number in the README table, and say what would make it drop?
- [ ] Can you explain the provider-terms risk and how the adapter design limits it?

### Step 0: One-time setup (about 1 hour)

You do this once, in Claude Code on your laptop, before any feature work. These skills run in Claude Code, not in the claude.ai chat, so the plugin has to be installed there.

- [ ] Use this repo (`abhijayanoop/memoryforall`), and open Claude Code inside it.
- [ ] Install the skills: `claude plugins install mattpocock-skills`. Two skills used below are in Matt's beta folder, which the plugin leaves out. If `/implement-spec` or `/pr` don't show up, add them with `npx skills@latest add mattpocock/skills --skill=implement-spec` and the same command with `--skill=pr`.
- [ ] Run **`/setup-matt-pocock-skills`**. Choose **GitHub** as the issue tracker, keep the **default triage labels**, and use a **single-context** layout for the docs. It writes a `## Agent skills` block into `CLAUDE.md` and three files under `docs/agents/`. Every other skill reads those to learn where tickets live.
- [ ] Run **`/git-guardrails-claude-code`**. It installs hooks that block `git push`, `reset --hard` and `branch -D`, so an agent working through tickets can't damage your history. You push yourself.
- [ ] Put this doc in the repo as `docs/memoryforall-architecture.md` (export it as Markdown). Every later skill reads it as the source of truth.
- [ ] Let **`/wizard`** handle the steps only you can do. The agent reaches for it automatically when it hits one, or you can ask: "use /wizard to set up the Cloudflare Tunnel, the GitHub OAuth app, and the OpenAI and Anthropic API keys." It produces a script that opens each dashboard and writes the values into `.env` and GitHub secrets.

Why GitHub over local files: `/to-tickets` turns blocking edges into **native GitHub issue dependencies**, so the issues page shows you which tickets are ready to work on. A history of closed issues and PRs also reads well to recruiters.

### Step 1: Seed the repo's shared language (one session)

The big decisions are already made, so skip **`/wayfinder`**. It's for an effort where the way forward isn't clear yet, and this doc already maps it. What the repo still lacks is the paper trail, and **`/grill-with-docs`** creates it.

Run: `/grill-with-docs` and point it at the architecture doc. Ask it to settle the vocabulary and record the decisions that would be hard to reverse. Expect a short session, since most answers are already in the doc. It should leave you with:

- **`GLOSSARY.md`**: the glossary agents will use in code and tickets. Make sure it pins down at least these terms: *Capture, Backfill, Live sync, Adapter, Conversation, Active branch, Item, Item type, Project, Supersession, Echo marker, Brief, Token budget, Device, Pairing.* Once these are fixed, a function name like `resolve_supersession` means the same thing in every ticket.
- **ADRs in `docs/adr/`**, one for each decision that would be painful to undo:
  1. Capture through providers' internal endpoints rather than official exports.
  2. MCP for Claude, extension injection for ChatGPT and Gemini.
  3. No LLM calls at query time.
  4. Postgres as the single store (pgvector plus full-text search).
  5. Raw JSON is forwarded to the server, and adapters run there.
  6. Self-hosted on a home server behind Cloudflare Tunnel.

Two questions can't be settled in conversation, so take them on the side routes before writing Spec 1:

- **`/research`** runs as a background agent and writes a Markdown file of cited findings into the repo. Use it for: "current shape of the claude.ai and chatgpt.com internal conversation endpoints" and "the current MCP Python SDK's OAuth / auth-provider support". Keep working on something else while it reads.
- **`/prototype`** builds throwaway code that answers a single question. Use it for the **suggestion chip**: does suggesting as you type feel good, or annoying? Run `/handoff` out to a separate prototype folder, build it there, and `/handoff` the answer back. The prototype is kept on a `prototype/chip` branch.

### Step 2: Split the product into five specs

Don't write one spec for all of memoryforall. Matt's rule is to keep the grilling, spec and tickets in **one unbroken context window**, about 150k tokens before the model starts reasoning worse. The whole product won't fit in that. Each spec below is a milestone you can demo on its own, which maps to a week of the build plan.

| # | Spec (GitHub issue) | Demo when done | Build-plan days |
| --- | --- | --- | --- |
| 1 | Claude capture → MCP search | A Claude chat is captured, and `search_history` finds it from inside Claude | 1–7 |
| 2 | Extraction, supersession and project brief | A changed decision shows only its latest version in `get_project_brief` | 8–12 |
| 3 | ChatGPT capture and chip injection | You type in ChatGPT, the chip offers Claude-derived items, and attached context doesn't come back as new items | 13–14 |
| 4 | Eval, auth and web UI | EvalKit reports four suites in CI, OAuth works on MCP, and you can correct items in the UI | 15–18 |
| 5 | Gemini (stretch) | Gemini captures and injects | 19 |

**Example: the tickets you should expect for Spec 1.** `/to-tickets` writes the real ones. Use this to judge whether its breakdown is about the right size. Each ticket is a **tracer bullet**: a thin slice that works end to end through every layer, small enough for one fresh context.

| # | Ticket | Blocked by | Done when |
| --- | --- | --- | --- |
| 01 | Walking skeleton: compose, migrations, CI | None | `docker compose up` gives a healthy API, and CI runs pytest |
| 02 | Ingest one Claude conversation from a fixture | 01 | Posting a saved payload stores the messages from the active branch. Ingesting it twice changes 0 rows |
| 03 | Device pairing | 01 | A code from the UI becomes a scoped device token, and `/ingest` rejects requests without one |
| 04 | Live sync from claude.ai | 02, 03 | Opening a chat in the browser puts it in the database within about 15 seconds |
| 05 | Backfill with resume | 04 | The last 6 months are imported, and a restarted backfill continues from where it stopped |
| 06 | `search_history` over chunks via MCP | 02 | A Claude connector reached through the tunnel returns a relevant earlier message |

Tickets 02 and 03 can run side by side once 01 is done. This is the parallelism `/implement-spec` takes advantage of.

### Step 3: The loop for each spec

Run these in order for each of the five specs. Steps 1 to 3 happen in **one session**, with no `/clear` or `/compact` until the tickets are published.

1. **`/grill-with-docs`**, scoped: "grill me on Spec N of docs/memoryforall-architecture.md." It updates `GLOSSARY.md` and adds ADRs if a new hard-to-reverse decision comes up. After Spec 1 these sessions are short.
2. **`/to-spec`** turns the session into a GitHub issue with user stories, implementation decisions and testing decisions, labelled `ready-for-agent`. Before writing, it asks you to agree **seams**: the public boundaries where tests are written. Agree on these four, and turn down anything finer:
   - **Adapter**: saved raw JSON fixture → normalized `Conversation`.
   - **Ingest API**: `POST /ingest` → messages and items in Postgres. Tests run against a fake LLM provider.
   - **Retrieval service**: query → ranked items, and the packed brief.
   - **Extension marker/inject module** (TypeScript): brief → marked block in the prompt box.
3. **`/to-tickets`** proposes tracer-bullet tickets with their blocking edges. Check that each ticket fits in one fresh context, that blockers are real, and that the walking skeleton comes first. Once you approve, it publishes them as GitHub issues with native "blocked by" links.
4. **Create the spec branch:** `git switch -c spec-1-claude-capture`. All of this spec's tickets are committed to this branch.
5. **Pick the next ticket.** The **frontier** is the set of open tickets whose blockers are all closed. `gh issue list --label ready-for-agent --state open` shows candidates, and the blocked-by column on GitHub's issues page shows which ones are free. Work them blockers first, lowest number first.
6. **`/implement #<issue>`** builds the ticket. Internally it drives **`/tdd`** at the agreed seams, one red-green slice at a time. It runs type checks (`mypy`, `tsc`) and individual test files as it goes, then the full suite. It then runs **`/code-review`** against the commit where the ticket started, and commits. Close the issue from the commit with `Closes #<issue>`.
7. **`/clear`**, then go back to step 5. Each ticket stands on its own, so the previous ticket's context isn't needed.
8. **When the frontier is empty:** run `/code-review main` across the whole branch, open one PR per spec (the `/pr` skill gives a good PR body: summary, evidence, what was left out), and merge it.
9. **Health pass:** run `/improve-codebase-architecture` and pick at most one improvement. It becomes an idea that enters the next spec's grilling.

**Once Spec 1 has taught you the rhythm:** for Specs 2 to 4 you can replace steps 5 to 8 with **`/implement-spec #<spec issue>`**. It works the ticket graph with parallel sub-agents, each in its own git worktree, merges them into one branch, reviews, and opens the PR. Use it only after you've done the loop by hand at least once. It's beta and gives you less control.

**Bugs you find while using memoryforall yourself** go in as normal GitHub issues. Run **`/triage`** on those only, to turn them into tickets an agent can pick up. Never triage tickets from `/to-tickets`; they're already ready for an agent.

## Risks and mitigations

The biggest risk is a provider changing its internal endpoints mid-build. The adapter-plus-fixtures design limits that to a one-file fix.

| Risk | Impact | Mitigation |
| --- | --- | --- |
| ChatGPT or Claude changes its internal API or DOM | Capture or injection breaks | Raw payloads are stored, adapters live on the server with fixture tests, selectors are in one file. Fix, replay `raw_payloads`, done |
| Account flagged for automated requests | Lost access to a provider | Throttle backfill to about 1 request per second, sync only on your own activity, never run unattended high-volume crawls |
| Extraction quality is poor | Brief is noisy, eval fails | Hand-labeled eval from week 1, confidence filter, forget and edit in the UI |
| Supersession judge mislabels items | Old decision shown as current, or a current one hidden | `contradicts` keeps both visible, judge precision is gated in CI, history is kept and reversible |
| Backfill cost spike | Unexpected bill | Last 6 months only, cheap model tier, skip the judge when there are no candidates, hard monthly cap |
| Host model doesn't call MCP tools | Claude answers without context | Tool descriptions say when to call; you can name the connector in the prompt; the eval checks how often tools get called |
| Gemini eats into the schedule | Core quality slips | Gemini is a stretch goal on day 19 only |
| Endpoint exposed through the tunnel | Your history leaks | OAuth on MCP, an allowlist on the UI, scoped device tokens, no open ports |
| ChatGPT or Gemini adds personal MCP support later | The injection path becomes redundant | Good outcome: both paths share one retrieval service, so you just turn on MCP there |
