# app/services/chunk_embedder.py
import asyncio
import logging
from typing import List, Optional

from elasticsearch import exceptions as es_exceptions

from shared.enums import OpenAIModelSlugEnum
from shared.rag.es_client import ESClient
from shared.rag.es_write_handler import ElasticsearchWriteHandler
from shared.schemas.document import DocumentChunk
from shared.utils.ts_tokenizer import TsTokenizer
from shared.utils.logger import TsLogger

logger = TsLogger(__name__)


class ChunkEmbedder:
    def __init__(self, tenant: TenantRead, es_client: ESClient | None = None):
        """
        Initialize the ChunkEmbedder.
        """
        self.embed_model = OpenAIModelSlugEnum.TEXT_EMBEDDING_3_LARGE.value
        if es_client is None:
            es = ESClient()
        else:
            es = es_client
        self.es_client = es.elastic_client  # AsyncElasticsearch instance
        self.es_writer_handler = ElasticsearchWriteHandler(tenant=tenant, es_client=es)
        self.tokenizer = TsTokenizer(OpenAIModelSlugEnum.GPT_4O_MINI)
        self.failed_chunks = []
        self.char_count = 0
        self.words_count = 0
        self.tokens_count = 0

    async def check_existing_embedding(self, chunk_hash: str) -> Optional[List[float]]:
        """
        Check if an embedding for the given chunk hash exists in Elasticsearch.

        :param chunk_hash: The SHA-256 hash of the chunk text.
        :return: The existing embedding if found, else None.
        """
        query = {
            "query": {
                "term": {
                    "hash.keyword": chunk_hash
                }
            }
        }
        try:
            response = await self.es_client.search(index=self.es_writer_handler.rag_index_name, body=query)
            hits = response['hits']['hits']
            if hits:
                es_source = hits[0]['_source']
                if es_source['text'] == hits[0]['_source']['text']:
                    return es_source['embedding']
            return None
        except Exception as e:
            return None

    async def embed_text(self, text: str) -> List[float]:
        """
        Generate embeddings for the given text using the embedding model.

        :param text: The text to embed.
        :return: A list of floats representing the embedding.
        """
        try:
            embedding = self.es_writer_handler.embed_model.embed_query(text)
            return embedding
        except Exception as e:
            raise

    async def index_chunk(self, chunk: DocumentChunk):
        """
        Index a single DocumentChunk into Elasticsearch.

        :param chunk: The DocumentChunk instance to index.
        """
        # Check if embedding exists
        # existing_embedding = await self.check_existing_embedding(chunk.hash)
        # if existing_embedding:
        #     chunk.embedding = existing_embedding
        # else:
        #     # Generate embedding
        #     try:
        #         embedding = await self.embed_text(chunk.text)
        #         chunk.embedding = embedding
        #     except Exception as e:
        #         self.failed_chunks.append(chunk)
        #         return

        # Generate embedding
        try:
            embedding = await self.embed_text(chunk.text)
            chunk.embedding = embedding
        except Exception as e:
            self.failed_chunks.append(chunk)
            return

        # Prepare the document for Elasticsearch
        document = {
            "text": chunk.text,
            "embedding": chunk.embedding,
            "document_id": chunk.document_id,
            "chunk_sequence": chunk.chunk_sequence,
            "prev_chunk_hash": chunk.prev_chunk_hash,
            "next_chunk_hash": chunk.next_chunk_hash,
            "hash": chunk.hash,
            "processed_at": chunk.processed_at.isoformat()
        }

        # Index the document
        try:
            await self.es_client.index(
                index=self.es_writer_handler.rag_index_name,
                id=chunk.hash,  # Use hash as the document ID to prevent duplicates
                body=document,
                op_type='create'  # Use 'create' to avoid overwriting existing documents
            )
        except es_exceptions.ConflictError:
            # self.failed_chunks.append(chunk)
            pass
        except Exception as e:
            self.failed_chunks.append(chunk)

    async def retry_failed_chunks(self, max_retries: int = 10):
        """
        Retry embedding and storing failed chunks up to max_retries times.
        """
        retry_attempt = 0
        while self.failed_chunks and retry_attempt < max_retries:
            retry_attempt += 1
            # Temporarily hold the current failed chunks and reset the list
            current_failed_chunks = self.failed_chunks
            self.failed_chunks = []

            tasks = [self.index_chunk(chunk) for chunk in current_failed_chunks]
            await asyncio.gather(*tasks)

            if self.failed_chunks:
                # Log how many chunks failed in this retry attempt
                logger.info(f"Retry attempt {retry_attempt}: {len(self.failed_chunks)} chunks failed to embed/store.")
            else:
                logger.info("All chunks embedded and stored successfully on retry.")

        if self.failed_chunks:
            # After max retries, some chunks still failed
            logger.error(f"{len(self.failed_chunks)} chunks failed after {max_retries} attempts.")

    async def embed_and_store_chunks(self, chunks: List[DocumentChunk]):
        """
        Embed and store a list of DocumentChunk instances into Elasticsearch with retry logic.
        """
        logger.info(f"Embedding and storing {len(chunks)} chunks...")
        await self.es_writer_handler.create_rag_index_if_not_exists()

        # Sort chunks by chunk_sequence
        chunks.sort(key=lambda x: x.chunk_sequence)

        # Calculate character, word, and token counts
        self.char_count = sum(len(chunk.text) for chunk in chunks)
        self.words_count = sum(len(chunk.text.split(' ')) for chunk in chunks)
        self.tokens_count = sum(self.tokenizer.num_of_tokens(chunk.text) for chunk in chunks)

        logger.info("starting embedding and storing chunks...")
        tasks = [self.index_chunk(chunk) for chunk in chunks]
        await asyncio.gather(*tasks)

        logger.info(f"Embedded and stored {len(chunks)} chunks.")
        # Retry failed chunks up to max retries
        await self.retry_failed_chunks(max_retries=10)
