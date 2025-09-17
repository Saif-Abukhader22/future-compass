from shared import shared_settings
from shared.rag.es_client import ESClient
from langchain_openai import OpenAIEmbeddings

from shared.rag.es_enums import EsEnums


class ElasticsearchDeleteHandler:
    def __init__(self, es_client: ESClient):
        """
        Initialize the ElasticsearchDeleteHandler.
        """
        self.es = es_client
        self.rag_index_name = shared_settings.THEOSUMMA_ES_INDEX
        self.embed_model = OpenAIEmbeddings(
            model=EsEnums.get_embedding_model(),
            openai_api_key=shared_settings.OPENAI_API_KEY
        )

    async def delete_document_by_id(self, document_id: str):
        """
        Delete a document from Elasticsearch by its 'document_id' field.
        """
        try:
            query = {
                "term": {
                    "document_id": {
                        "value": document_id
                    }
                }
            }
            response = await self.es.elastic_client.delete_by_query(
                index=self.rag_index_name,
                body={"query": query},
                ignore_unavailable=True
            )
            return response
        except Exception as e:
            raise RuntimeError(f"Failed to delete document with document_id {document_id}: {str(e)}")

    async def delete_documents_by_query(self, query: dict):
        """
        Delete documents from Elasticsearch using a query.
        """
        try:
            response = await self.es.elastic_client.delete_by_query(
                index=self.rag_index_name,
                body={"query": query},
                ignore_unavailable=True
            )
            return response
        except Exception as e:
            raise RuntimeError(f"Failed to delete documents with query {query}: {str(e)}")

    async def delete_rag_index(self):
        """
        Delete the entire RAG index.
        """
        try:
            if await self.es.elastic_client.indices.exists(index=self.rag_index_name):
                response = await self.es.elastic_client.indices.delete(index=self.rag_index_name)
                return response
        except Exception as e:
            raise RuntimeError(f"Failed to delete RAG index {self.rag_index_name}: {str(e)}")
