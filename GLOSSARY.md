# memoryforall

A personal context layer: it captures your AI chat history across platforms, distills it into current decisions, requirements and facts, and hands the relevant slice to whichever platform you are using. It never answers questions itself.

## Platforms

**Provider**:
A platform whose conversations are captured (ChatGPT, Claude, Gemini).
_Avoid_: Source, vendor

**Host**:
The platform you are prompting right now, which receives a Brief. ChatGPT and Claude are both Providers and Hosts.
_Avoid_: Target, client

## Capture

**Conversation**:
One chat thread on one Provider, identified by the Provider and its own conversation id.
_Avoid_: Chat, thread, session

**Active branch**:
The path of messages from a Conversation's current leaf back to its root. Only the active branch is indexed.
_Avoid_: Current thread

**Orphaned**:
Describes a message, or an Item sourced only from such messages, that is no longer on the Active branch. It returns to active if the branch is switched back.
_Avoid_: Stale, deleted

**Capture**:
The browser extension's job of getting Conversations to the server, ending when the server accepts a batch.
_Avoid_: Sync (alone), scrape, upload

**Backfill**:
Capture of past Conversations when a Device is first paired, covering a bounded window of history.
_Avoid_: Import

**Live sync**:
Capture of a Conversation as it changes, after you open it or a reply finishes.
_Avoid_: Real-time sync

**Adapter**:
The per-Provider translation of a Provider's raw data into the shared Conversation shape.
_Avoid_: Parser, connector

**Ingestion**:
The server-side processing of captured Conversations into Items.
_Avoid_: Processing, import

## Knowledge

**Item**:
A typed, sourced piece of knowledge extracted from Conversations, and the unit that is retrieved.
_Avoid_: Memory, note, entry

**Item type**:
One of decision, requirement, fact, open question, code artifact, or summary. A summary is replaced in place, never superseded, and never appears in a Brief.
_Avoid_: Category, kind

**Project**:
A named, automatically assigned topic that groups Items. A Conversation never belongs to a Project; its Items do.
_Avoid_: Workspace, topic, folder

**Supersession**:
The process of labelling a new Item against similar existing ones as new, duplicate, supersedes or contradicts. Direction follows when things were said, never when they were ingested.
_Avoid_: Update, versioning

**Contradiction**:
Two active Items in a Project that disagree with no clear winner, kept visible for you to resolve.
_Avoid_: Conflict

## Delivery

**Brief**:
The compact, sectioned text for one Project that is handed to a Host. Always delivered wrapped in an Echo marker.
_Avoid_: Context block, summary, dump

**Token budget**:
The cap on how many model tokens a Brief may use.
_Avoid_: Limit, token limit (bare "token" is ambiguous)

**Echo marker**:
The delimiters wrapped around every Brief so Ingestion can recognise and discard it if it is captured back.
_Avoid_: Tag, watermark

**Suggestion chip**:
The small prompt shown in a Host's page offering to attach a Brief.
_Avoid_: Popup, banner

## Access

**Device**:
One paired browser extension, which can be revoked.
_Avoid_: Client, session

**Pairing**:
Exchanging a short-lived code shown in the web UI for a Device token.
_Avoid_: Login, registration

**Device token**:
The credential a Device uses; only its hash is stored.
_Avoid_: Token (bare), API key

## Correction

**Forget**:
Removing an Item or a Conversation from use, with permanent deletion after a grace period. Forgetting a Conversation also stops it being captured again.
_Avoid_: Delete, archive
