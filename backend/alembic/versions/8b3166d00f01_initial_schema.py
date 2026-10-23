"""initial schema

Revision ID: 8b3166d00f01
Revises:
Create Date: 2026-10-24 02:28:00.116627

"""

from collections.abc import Sequence

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8b3166d00f01"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

message_role = sa.Enum(
    "user",
    "assistant",
    "system",
    name="message_role",
    native_enum=False,
)


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    message_role.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "source_documents",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("accession_number", sa.String(length=32), nullable=False),
        sa.Column("ticker", sa.String(length=16), nullable=False),
        sa.Column("company_name", sa.String(length=255), nullable=False),
        sa.Column("form_type", sa.String(length=16), nullable=False),
        sa.Column("filing_date", sa.Date(), nullable=False),
        sa.Column("fiscal_year", sa.Integer(), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("markdown_content", sa.Text(), nullable=False),
        sa.Column(
            "document_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("accession_number", name="uq_source_documents_accession_number"),
    )
    op.create_index(
        "ix_source_documents_ticker_filing_date",
        "source_documents",
        ["ticker", "filing_date"],
        unique=False,
    )

    op.create_table(
        "users",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_foreign_key(
        "users_id_fkey",
        "users",
        "users",
        ["id"],
        ["id"],
        source_schema="public",
        referent_schema="auth",
        ondelete="CASCADE",
    )

    op.create_table(
        "chat_threads",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_chat_threads_user_id_updated_at",
        "chat_threads",
        ["user_id", "updated_at"],
        unique=False,
    )

    op.create_table(
        "document_chunks",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("document_id", sa.UUID(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("chunk_text", sa.Text(), nullable=False),
        sa.Column("page_label", sa.String(length=64), nullable=True),
        sa.Column("section_label", sa.String(length=255), nullable=True),
        sa.Column("token_count", sa.Integer(), nullable=False),
        sa.Column("embedding", Vector(1536), nullable=True),
        sa.Column(
            "chunk_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["source_documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id", "chunk_index", name="uq_document_chunks_document_index"),
    )
    op.create_index(
        "ix_document_chunks_document_id_chunk_index",
        "document_chunks",
        ["document_id", "chunk_index"],
        unique=False,
    )
    op.execute(
        """
        ALTER TABLE document_chunks
        ADD COLUMN search_vector tsvector
        GENERATED ALWAYS AS (to_tsvector('english', coalesce(chunk_text, ''))) STORED
        """
    )
    op.execute(
        """
        CREATE INDEX ix_document_chunks_embedding_hnsw
        ON document_chunks USING hnsw (embedding vector_cosine_ops)
        """
    )
    op.execute(
        """
        CREATE INDEX ix_document_chunks_search_vector_gin
        ON document_chunks USING gin (search_vector)
        """
    )
    op.execute(
        """
        CREATE INDEX ix_document_chunks_chunk_metadata_gin
        ON document_chunks USING gin (chunk_metadata)
        """
    )

    op.create_table(
        "chat_messages",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("thread_id", sa.UUID(), nullable=False),
        sa.Column("role", message_role, nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("message_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["thread_id"], ["chat_threads.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("thread_id", "sequence", name="uq_chat_messages_thread_sequence"),
    )
    op.create_index(
        "ix_chat_messages_thread_id_sequence",
        "chat_messages",
        ["thread_id", "sequence"],
        unique=False,
    )

    op.create_table(
        "message_citations",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("message_id", sa.UUID(), nullable=False),
        sa.Column("chunk_id", sa.UUID(), nullable=True),
        sa.Column("source_document_id", sa.UUID(), nullable=False),
        sa.Column("excerpt", sa.Text(), nullable=False),
        sa.Column(
            "citation_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["chunk_id"], ["document_chunks.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["message_id"], ["chat_messages.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["source_document_id"],
            ["source_documents.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_message_citations_message_id",
        "message_citations",
        ["message_id"],
        unique=False,
    )

    _enable_rls()


def downgrade() -> None:
    _disable_rls()

    op.drop_index("ix_message_citations_message_id", table_name="message_citations")
    op.drop_table("message_citations")
    op.drop_index("ix_chat_messages_thread_id_sequence", table_name="chat_messages")
    op.drop_table("chat_messages")
    op.execute("DROP INDEX IF EXISTS ix_document_chunks_chunk_metadata_gin")
    op.execute("DROP INDEX IF EXISTS ix_document_chunks_search_vector_gin")
    op.execute("DROP INDEX IF EXISTS ix_document_chunks_embedding_hnsw")
    op.drop_index("ix_document_chunks_document_id_chunk_index", table_name="document_chunks")
    op.drop_table("document_chunks")
    op.drop_index("ix_chat_threads_user_id_updated_at", table_name="chat_threads")
    op.drop_table("chat_threads")
    op.drop_constraint("users_id_fkey", "users", type_="foreignkey")
    op.drop_table("users")
    op.drop_index("ix_source_documents_ticker_filing_date", table_name="source_documents")
    op.drop_table("source_documents")
    message_role.drop(op.get_bind(), checkfirst=True)
    op.execute("DROP EXTENSION IF EXISTS vector")


def _enable_rls() -> None:
    op.execute("ALTER TABLE public.users ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE public.chat_threads ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE public.chat_messages ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE public.message_citations ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE public.source_documents ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE public.document_chunks ENABLE ROW LEVEL SECURITY")

    op.execute(
        """
        CREATE POLICY users_select_own ON public.users
        FOR SELECT USING (id = auth.uid())
        """
    )
    op.execute(
        """
        CREATE POLICY users_update_own ON public.users
        FOR UPDATE USING (id = auth.uid())
        """
    )
    op.execute(
        """
        CREATE POLICY users_insert_own ON public.users
        FOR INSERT WITH CHECK (id = auth.uid())
        """
    )

    op.execute(
        """
        CREATE POLICY chat_threads_owner ON public.chat_threads
        FOR ALL USING (user_id = auth.uid())
        WITH CHECK (user_id = auth.uid())
        """
    )

    op.execute(
        """
        CREATE POLICY chat_messages_owner ON public.chat_messages
        FOR ALL USING (
            EXISTS (
                SELECT 1 FROM public.chat_threads t
                WHERE t.id = chat_messages.thread_id AND t.user_id = auth.uid()
            )
        )
        WITH CHECK (
            EXISTS (
                SELECT 1 FROM public.chat_threads t
                WHERE t.id = chat_messages.thread_id AND t.user_id = auth.uid()
            )
        )
        """
    )

    op.execute(
        """
        CREATE POLICY message_citations_owner ON public.message_citations
        FOR ALL USING (
            EXISTS (
                SELECT 1
                FROM public.chat_messages m
                JOIN public.chat_threads t ON t.id = m.thread_id
                WHERE m.id = message_citations.message_id AND t.user_id = auth.uid()
            )
        )
        WITH CHECK (
            EXISTS (
                SELECT 1
                FROM public.chat_messages m
                JOIN public.chat_threads t ON t.id = m.thread_id
                WHERE m.id = message_citations.message_id AND t.user_id = auth.uid()
            )
        )
        """
    )

    op.execute(
        """
        CREATE POLICY source_documents_read_authenticated ON public.source_documents
        FOR SELECT TO authenticated USING (true)
        """
    )
    op.execute(
        """
        CREATE POLICY document_chunks_read_authenticated ON public.document_chunks
        FOR SELECT TO authenticated USING (true)
        """
    )


def _disable_rls() -> None:
    for policy, table in (
        ("users_select_own", "users"),
        ("users_update_own", "users"),
        ("users_insert_own", "users"),
        ("chat_threads_owner", "chat_threads"),
        ("chat_messages_owner", "chat_messages"),
        ("message_citations_owner", "message_citations"),
        ("source_documents_read_authenticated", "source_documents"),
        ("document_chunks_read_authenticated", "document_chunks"),
    ):
        op.execute(f"DROP POLICY IF EXISTS {policy} ON public.{table}")

    for table in (
        "document_chunks",
        "source_documents",
        "message_citations",
        "chat_messages",
        "chat_threads",
        "users",
    ):
        op.execute(f"ALTER TABLE public.{table} DISABLE ROW LEVEL SECURITY")
