# app/schemas/document.py
from uuid import UUID

from pydantic import BaseModel, UUID4, ConfigDict, Field
from datetime import datetime
from typing import Optional, List

from shared.enums import AgentDocumentProcessingStatus, PlatformSupportedLanguages


class DocumentBase(BaseModel):
    model_config = ConfigDict(
        from_attributes=True
    )
    object_name: str
    title: str
    authors: Optional[List[str]] = Field(default_factory=list)
    is_deleted: bool = False
    size: Optional[int] = 0
    char_count: Optional[int] = 0
    words_count: Optional[int] = 0
    tokens_count: Optional[int] = 0



class DocumentCreate(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        use_enum_values=True
    )
    document_id: UUID4
    tenant_id: UUID4
    object_name: str
    title: str
    processing_status: AgentDocumentProcessingStatus
    ext: str
    size: Optional[int] = 0
    main_language: PlatformSupportedLanguages
    ai_supporting_information: Optional[str] = None


class DocumentUpdate(BaseModel):
    model_config = ConfigDict(
        from_attributes=True
    )
    object_name: Optional[str] = None
    processing_status: Optional[AgentDocumentProcessingStatus] = None
    ext: Optional[str] = None
    title: Optional[str] = None
    authors: Optional[List[str]] = None
    is_deleted: Optional[bool] = None
    size: Optional[int] = None
    char_count: Optional[int] = None
    words_count: Optional[int] = None
    tokens_count: Optional[int] = None
    main_language: Optional[PlatformSupportedLanguages] = None
    ai_supporting_information: Optional[str] = None


class DocumentRead(DocumentBase):
    document_id: UUID4
    created_at: datetime
    updated_at: Optional[datetime]
    processing_status: AgentDocumentProcessingStatus
    ai_supporting_information: Optional[str] = None

class DocumentChunk(BaseModel):
    document_id: UUID4  # It's str because it will be embedded and stored in ES
    text: str
    embedding: Optional[List[float]] = None  # Changed to list of floats
    prev_chunk_hash: Optional[str] = None
    hash: str
    next_chunk_hash: Optional[str] = None
    chunk_sequence: int
    processed_at: datetime

class DocumentsIdsSchema(BaseModel):
    documents_ids: List[UUID] = Field(default_factory=list)

class DocumentsLanguagesResponse(BaseModel):
    languages: List[str] = Field(default_factory=list)