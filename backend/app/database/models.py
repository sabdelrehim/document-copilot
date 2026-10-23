"""Register all ORM tables on ``Base.metadata`` and re-export model types."""

from app.database.base import EMBEDDING_DIMENSIONS, Base
from app.database.chat_message import ChatMessage, MessageRole
from app.database.chat_thread import ChatThread
from app.database.document_chunk import DocumentChunk
from app.database.message_citation import MessageCitation
from app.database.source_document import SourceDocument
from app.database.user import User

__all__ = [
    "Base",
    "EMBEDDING_DIMENSIONS",
    "ChatMessage",
    "ChatThread",
    "DocumentChunk",
    "MessageCitation",
    "MessageRole",
    "SourceDocument",
    "User",
]
