import os

from elasticsearch import AsyncElasticsearch
from langchain_community.embeddings import OpenAIEmbeddings

from shared import shared_settings
from shared.rag.es_enums import EsEnums


class ESClient:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ESClient, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    async def close(self):
        """Close the Elasticsearch connection."""
        if hasattr(self, 'es') and self.elastic_client:
            await self.elastic_client.close()
            print("Closed Elasticsearch connection.")

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True

        self.rag_index_name = shared_settings.THEOSUMMA_ES_INDEX
        # Initialize OpenAI embedding model
        self.embed_model = OpenAIEmbeddings(
            model=EsEnums.get_embedding_model(),
            openai_api_key=shared_settings.OPENAI_API_KEY
        )

        # Initialize Elasticsearch connection
        self.elastic_client: AsyncElasticsearch = AsyncElasticsearch(
            [f"https://{shared_settings.ES_HOST}:9200"],
            basic_auth=(shared_settings.ES_USER, shared_settings.ES_PASSWORD),
            ca_certs=os.path.join(os.path.dirname(__file__), 'ts_http_ca.crt'),
            timeout=60,  # Increase the timeout (in seconds)
            max_retries=3,  # Add retries in case of temporary failures
            retry_on_timeout=True  # Retry if there's a timeout
        )
        print("Connected to Elasticsearch.")

    async def initialize_client(self):
        """Call this method to initialize the client asynchronously."""
        await self.create_rag_index_if_not_exists()

    async def create_rag_index_if_not_exists(self):
        current_index = EsEnums.get_rag_index_based_on_settings()
        """Ensure the Elasticsearch index exists."""
        if not await self.elastic_client.indices.exists(index=self.rag_index_name):
            mapping = current_index.MAPPINGS_TO_CREATE_RAG_INDEX
            await self.elastic_client.indices.create(index=self.rag_index_name, body=mapping)
            print(f"Created index: {self.rag_index_name}")
        else:
            print(f"Index {self.rag_index_name} already exists.")

