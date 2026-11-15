"""spec 1 capture tables: devices, raw_payloads, conversations, messages

Revision ID: 0001
Revises:
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None


def _id() -> sa.Column[int]:
    return sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True)


def _now(name: str) -> sa.Column[object]:
    return sa.Column(name, sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "devices",
        _id(),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("token_hash", sa.Text, nullable=False, unique=True),
        sa.Column("scopes", postgresql.ARRAY(sa.Text), nullable=False),
        _now("created_at"),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
    )
    op.create_table(
        "raw_payloads",
        _id(),
        sa.Column("provider", sa.Text, nullable=False),
        sa.Column("provider_conv_id", sa.Text, nullable=False),
        sa.Column("payload", postgresql.JSONB, nullable=False),
        _now("received_at"),
    )
    op.create_table(
        "conversations",
        _id(),
        sa.Column("provider", sa.Text, nullable=False),
        sa.Column("provider_conv_id", sa.Text, nullable=False),
        sa.Column("title", sa.Text),
        sa.Column("active_leaf_id", sa.Text),
        sa.Column("last_processed_msg_id", sa.BigInteger),
        sa.Column("project_hint", sa.Text),
        sa.UniqueConstraint("provider", "provider_conv_id"),
    )
    op.create_table(
        "messages",
        _id(),
        sa.Column(
            "conversation_id", sa.BigInteger, sa.ForeignKey("conversations.id"), nullable=False
        ),
        sa.Column("provider_message_id", sa.Text, nullable=False, unique=True),
        sa.Column("parent_id", sa.BigInteger),
        sa.Column("role", sa.Text, nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("branch_state", sa.Text, nullable=False, server_default="active"),
        sa.Column("has_injected_ctx", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.CheckConstraint("branch_state IN ('active', 'orphaned')", name="branch_state_values"),
    )


def downgrade() -> None:
    for table in ("messages", "conversations", "raw_payloads", "devices"):
        op.drop_table(table)
