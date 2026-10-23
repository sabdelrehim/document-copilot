from app.database.models import Base


def test_all_product_tables_registered() -> None:
    assert set(Base.metadata.tables) == {
        "users",
        "chat_threads",
        "chat_messages",
        "message_citations",
        "source_documents",
        "document_chunks",
    }
