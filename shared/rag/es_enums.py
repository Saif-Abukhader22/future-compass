from core_service.config import settings

# Move the DEFAULT_TS_INDEX_MAPPING outside the class to avoid unresolved reference.
DEFAULT_TS_RAG_INDEX_MAPPING = {
    "mappings": {
        "properties": {
            "text": {"type": "text"},
            "embedding": {
                "type": "dense_vector",
                "dims": 3072,
                "index": True,
                "similarity": "cosine"
            },
            "account_id": {"type": "keyword"},
            "document_type": {"type": "keyword"},
            "book_id": {"type": "keyword"},
            "authors": {"type": "keyword"},
            "chunk_sequence": {"type": "integer"},
            "prev_chunk_hash": {"type": "keyword"},
            "next_chunk_hash": {"type": "keyword"},
            "hash": {"type": "keyword"},
            "processed_at": {"type": "date"},
            "agent_id": {"type": "keyword"}
        }
    }
}

DEFAULT_TS_CHATTING_INDEX_MAPPING = {
    "mappings": {
        "properties": {
            "user_id": {
                "type": "keyword"
            },
            "timestamp": {
                "type": "date"
            },
            "gender": {
                "type": "keyword"
            },
            "thread_id": {
                "type": "keyword"
            },
            "agent_id": {
                "type": "keyword"
            },
            "source_id": {
                "type": "keyword"
            },
            "inquiry_message_id": {
                "type": "keyword",
            },
            "response_message_id": {
                "type": "keyword",
            },
            "context_messages_ids": {
                "type": "keyword",
            },
            "inquiry": {
                "type": "text",
                "analyzer": "standard"
            },
            "response": {
                "type": "text",
                "analyzer": "standard"
            },
            "context_messages": {
                "type": "text",
                "analyzer": "standard"
            },
            "inquiry_embedding": {
                "type": "dense_vector",
                "dims": 3072,  # This corresponds to TEXT_EMBED_3_LARGE dimensions
            },
            "response_embedding": {
                "type": "dense_vector",
                "dims": 3072,  # This corresponds to TEXT_EMBED_3_LARGE dimensions
            },
            "interaction_embedding": {
                "type": "dense_vector",
                "dims": 3072,  # This corresponds to TEXT_EMBED_3_LARGE dimensions

            },
            "interaction_text": {
                "type": "text",
                "analyzer": "standard"
            },
            "rag_chunks_hashes": {
                "type": "keyword",
            }
        }
    }
}


class EsEnums:
    @staticmethod
    def get_embedding_model() -> str:
        return "text-embedding-3-large"

    @staticmethod
    def get_rag_index_based_on_settings():
        if settings.THEOSUMMA_ES_INDEX == EsEnums.DevIndexV1.RAG_INDEX_NAME:

            return EsEnums.DevIndexV1()
        elif settings.THEOSUMMA_ES_INDEX == EsEnums.ProdIndexV1.RAG_INDEX_NAME:
            return EsEnums.ProdIndexV1()

    @staticmethod
    def get_chatting_index_based_on_settings():
        if settings.THEOSUMMA_ES_CHATTING_INDEX == EsEnums.DevIndexV1.CHATTING_INDEX_NAME:

            return EsEnums.DevIndexV1()
        elif settings.THEOSUMMA_ES_CHATTING_INDEX == EsEnums.ProdIndexV1.CHATTING_INDEX_NAME:
            return EsEnums.ProdIndexV1()

    class DevIndexV1:
        RAG_INDEX_NAME = "theosumma_dev_index_v3"
        CHATTING_INDEX_NAME = "theosumma_dev_chatting_index_v3"
        MAPPINGS_TO_CREATE_RAG_INDEX = DEFAULT_TS_RAG_INDEX_MAPPING
        MAPPINGS_TO_CREATE_CHATTING_INDEX = DEFAULT_TS_CHATTING_INDEX_MAPPING

    class ProdIndexV1:
        RAG_INDEX_NAME = "theosumma_prod_index_v3"
        CHATTING_INDEX_NAME = "theosumma_prod_chatting_index_v3"
        MAPPINGS_TO_CREATE_RAG_INDEX = DEFAULT_TS_RAG_INDEX_MAPPING
        MAPPINGS_TO_CREATE_CHATTING_INDEX = DEFAULT_TS_CHATTING_INDEX_MAPPING
