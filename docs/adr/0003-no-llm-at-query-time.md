# No LLM calls at query time

Language models run only during Ingestion (extraction and the Supersession judge). Retrieval is an embedding call plus ranking, and Briefs are built from templates. This keeps queries fast, cheap and predictable and leaves answer generation to the Host. Adding query-time LLM reranking later would be a deliberate reversal of this ADR.
