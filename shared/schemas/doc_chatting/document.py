from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict

from shared.enums import ChattingTools


class ChatPDFRequest(BaseModel):
    model_config = ConfigDict(
        use_enum_values=True
    )
    account_id: UUID
    query: str
    tool: ChattingTools


class DocumentChunk(BaseModel):
    chunk_text: str
    page_number: Optional[int]
