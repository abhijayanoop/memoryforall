# Postgres is the single store

Relational data, vectors (pgvector) and keyword search (full-text) all live in one Postgres database, rather than a separate vector database. Both delivery paths read from the same store, there is one backup and one migration history, and the scale of one person's history does not need more.
