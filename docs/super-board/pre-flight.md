# Pre-flight

Credentials, tools and environment the board will need. Values live only in the local env file (never committed); the committed example env file lists key names.

## Credentials

- [ ] OPENAI_API_KEY with a provider-side spend limit (#4, #11, #51)
- [ ] ANTHROPIC_API_KEY for extraction, judging and eval host models (#22, #25, #51)
- [ ] Clerk application with dynamic client registration on and sign-ups restricted to one account: publishable and secret keys (#5, #17, #18, #56)
- [ ] Cloudflare Tunnel hostname (#5, #17, #19)
- [ ] CI secrets for the full eval job only, with a spend cap (#53)

## Tools

- [x] gh CLI authenticated (project, read:project, repo scopes)
- [x] Docker
- [x] uv
- [x] Node and npm
- [ ] Chrome with the unpacked extension loaded for capture tickets (#14, #15, #16, #42)

## Environment

- [ ] Real claude.ai and chatgpt.com sessions available for the human fixture tickets (#3, #33, #44)
- [ ] Private data folders exist locally: `server/tests/private/`, `server/evals/private/` (gitignored)

## Notes

- Wave 1 (#2, the walking skeleton) needs only the verified tools above. The unchecked credentials gate later tickets, not the first.
