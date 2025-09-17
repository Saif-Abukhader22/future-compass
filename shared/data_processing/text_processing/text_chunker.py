from datetime import datetime
from hashlib import sha256
from typing import List

import ftfy
from pydantic.v1 import UUID4
from semantic_text_splitter import TextSplitter
from shared.enums import OpenAIModelSlugEnum
from shared.schemas.document import DocumentChunk


class TextChunker:
    def __init__(self, document_id: UUID4, extracted_text: str, min_tokens: int = 300, max_tokens: int = 500):
        self.document_id: str = str(document_id)
        self.extracted_text = extracted_text
        self.min_tokens = min_tokens
        self.max_tokens = max_tokens

    # Normalize the text to handle escape sequences and encoding issues
    def _normalize_text(self, input_text: str) -> str:
        try:
            input_text = input_text.replace("\\", "\\\\")
            decoded_text = input_text.encode('utf-8').decode('unicode_escape')
            fixed_text = ftfy.fix_text(decoded_text)
            return fixed_text
        except UnicodeDecodeError as e:
            return input_text

    # Chunk the text semantically while respecting token limits
    def semantic_chunk_with_token_limits(self, text: str) -> List[str]:
        normalized_text = self._normalize_text(text)
        splitter = TextSplitter.from_tiktoken_model(OpenAIModelSlugEnum.GPT_4O_MINI.value,
                                                    (self.min_tokens, self.max_tokens))
        semantic_chunks = splitter.chunks(normalized_text)
        return semantic_chunks

    # Method to return chunked text as a list of strings
    def _chunk(self) -> List[str]:
        chunks = self.semantic_chunk_with_token_limits(self.extracted_text)
        return chunks

    @staticmethod
    def generate_chunk_hash(chunk_text):
        """Generate a unique hash for the chunk content."""
        return sha256(chunk_text.encode('utf-8')).hexdigest()

    def get_document_chunks(self) -> List[DocumentChunk]:
        chunks = self._chunk()
        document_chunks = []
        for index, chunk_text in enumerate(chunks):
            chunk_hash = self.generate_chunk_hash(chunk_text)
            document_chunk = DocumentChunk(
                document_id=UUID4(self.document_id),
                text=chunk_text,
                prev_chunk_hash=None if index == 0 else self.generate_chunk_hash(chunks[index - 1]),
                next_chunk_hash=None if index == len(chunks) - 1 else self.generate_chunk_hash(chunks[index + 1]),
                hash=chunk_hash,
                chunk_sequence=index,
                processed_at=datetime.now(),
            )
            document_chunks.append(document_chunk)
        return document_chunks
