# Self-hosted on a home server behind Cloudflare Tunnel

Your chat history stays on your own machine, exposed only through a Cloudflare Tunnel with no open router ports; only scrubbed text reaches hosted model APIs. The same Docker Compose setup deploys to a cloud host for a live demo. Single-user and self-hosted is a scope decision: multi-tenancy is explicitly not a goal.
