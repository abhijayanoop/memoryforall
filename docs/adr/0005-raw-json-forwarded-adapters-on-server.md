# The extension forwards raw JSON; Adapters run on the server

The extension is a thin pipe and does no parsing, so all Provider-specific logic is Python that can be tested against saved fixtures. When a Provider changes its format, the fix is one Adapter and a replay of the stored raw payloads. The cost is storing untouched payloads, which Forget must also purge.
