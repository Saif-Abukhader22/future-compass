import logging

from shared.config import shared_settings
from shared.rag.es_client import ESClient
from langchain_openai import OpenAIEmbeddings

from shared.rag.es_enums import EsEnums
from shared.utils.logger import TsLogger

logger = TsLogger(name=__name__)


class ElasticsearchQueryHandler:
    def __init__(self, es_client: ESClient):
        """
        Initialize the ElasticsearchQueryHandler.
        """
        self.es = es_client
        self.rag_index_name = shared_settings.THEOSUMMA_ES_INDEX
        self.embed_model = OpenAIEmbeddings(
            model=EsEnums.get_embedding_model(),
            openai_api_key=shared_settings.OPENAI_API_KEY
        )


    async def query_by_metadata(self, query_params, top_k: int = 10):
        """
        Perform a metadata search based on the provided query parameters.
        """
        # Build the Elasticsearch query
        query = {"bool": {"must": [{"match": {k: v}} for k, v in query_params.items()]}}
        try:
            response = await self.es_client.elastic_client.search(
                index=self.rag_index_name,
                body={"query": query},
                size=top_k  # Adjust the number of results as needed
            )
            return response["hits"]["hits"]
        except Exception as e:
            logger.error(f"Error 1, querying Elasticsearch: {str(e)}")
            return []

    async def query_by_embedding(self, query_text, top_k: int = 10):
        """
        Perform a semantic search by embedding the query text and comparing with stored embeddings.
        """
        try:
            query_embedding = self.embed_model.embed_query(query_text)

            # Build the Elasticsearch query using `dense_vector` for semantic search
            query = {
                "script_score": {
                    "query": {"match_all": {}},
                    "script": {
                        "source": "cosineSimilarity(params.query_embedding, 'embedding') + 1.0",
                        "params": {"query_embedding": query_embedding}
                    }
                }
            }

            response = await self.es_client.elastic_client.search(
                index=self.rag_index_name,
                body={"query": query},
                size=top_k  # Adjust the number of results as needed
            )
            return response["hits"]["hits"]
        except Exception as e:
            logger.error(f"Error 2, querying Elasticsearch: {str(e)}")
            return []

    async def search_and_filter(self, query_text: str, metadata_filters: dict[str, str] | None = None, top_k: int = 10):
        """
        Perform a semantic search by embedding the query text and filtering by metadata.

        Args:
            query_text (str): The text to search for semantically.
            metadata_filters (dict): Metadata filters to apply, e.g., {"document_id": "1234", "author_name": "John Doe"}

        Returns:
            list: A list of search hits matching both the semantic search and metadata filters.
            :param query_text:
            :param metadata_filters:
            :param top_k:
        """
        try:
            query_embedding = self.embed_model.embed_query(query_text)

            # Build the Elasticsearch query
            query = {
                "bool": {
                    "must": [
                        {
                            "script_score": {
                                "query": {"match_all": {}},
                                "script": {
                                    "source": "cosineSimilarity(params.query_embedding, 'embedding') + 1.0",
                                    "params": {"query_embedding": query_embedding}
                                }
                            }
                        }
                    ]
                }
            }

            # Apply metadata filters if provided
            if metadata_filters:
                filter_clauses = []
                for key, value in metadata_filters.items():
                    if key in ["document_id", "prev_chunk_hash", "next_chunk_hash", "hash"]:  # Fields that are keywords
                        filter_clauses.append({
                            "term": {
                                key: value
                            }
                        })

                query["bool"]["filter"] = filter_clauses

            # Execute the query
            response = await self.es_client.elastic_client.search(
                index=self.rag_index_name,
                body={"query": query},
                size=top_k  # Adjust the number of results as needed
            )

            return response["hits"]["hits"]

        except Exception as e:
            logger.error(f"Error 3, querying Elasticsearch: {str(e)}")
            return []

    async def search_and_filter_by_document_ids(self, query_text: str, document_ids: list[str], top_k: int = 10):
        """
        Perform a semantic search by embedding the query text and filtering by a list of document IDs.

        Args:
            query_text (str): The text to search for semantically.
            document_ids (list[str]): List of document IDs to restrict the search to.
            top_k (int): Number of results to return.

        Returns:
            list: A list of search hits matching both the semantic search and document_id filters.
        """
        try:
            query_embedding = self.embed_model.embed_query(query_text)

            # Build the Elasticsearch query
            query = {
                "bool": {
                    "must": [
                        {
                            "script_score": {
                                "query": {"match_all": {}},
                                "script": {
                                    "source": "cosineSimilarity(params.query_embedding, 'embedding') + 1.0",
                                    "params": {"query_embedding": query_embedding}
                                }
                            }
                        }
                    ],
                    "filter": [
                        {"terms": {"document_id": document_ids}}  # Filter by document IDs
                    ]
                }
            }

            # Execute the query
            response = await self.es_client.elastic_client.search(
                index=self.rag_index_name,
                body={"query": query},
                size=top_k  # Adjust the number of results as needed
            )

            return response["hits"]["hits"]

        except Exception as e:
            logger.error(f"Error 4, querying Elasticsearch: {str(e)}")
            return []
