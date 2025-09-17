from typing import List, Dict, Any, Optional
from elasticsearch import AsyncElasticsearch
from shared.utils.logger import TsLogger

logger = TsLogger(name=__name__)

class ESClient:
    _instance = None

    def __init__(
        self, 
        es_host: Optional[str] = None, 
        es_port: Optional[int] = None, 
        es_user: Optional[str] = None, 
        es_password: Optional[str] = None, 
        cloud_id: Optional[str] = None,
        api_key: Optional[str] = None
    ):
        """
        Initialize Elasticsearch client.
        
        Args:
            es_host (Optional[str]): Elasticsearch host
            es_port (Optional[int]): Elasticsearch port
            es_user (Optional[str]): Elasticsearch username
            es_password (Optional[str]): Elasticsearch password
            cloud_id (Optional[str]): Elastic Cloud ID for cloud connection
            api_key (Optional[str]): Elasticsearch API key
        """
        self.es_host = es_host
        self.es_port = es_port
        self.es_user = es_user
        self.es_password = es_password
        self.cloud_id = cloud_id
        self.api_key = api_key
        
        # Initialize Elasticsearch client
        if cloud_id and api_key:
            self.client = AsyncElasticsearch(
                cloud_id=cloud_id,
                api_key=api_key
            )
        elif cloud_id:
            self.client = AsyncElasticsearch(
                cloud_id=cloud_id,
                basic_auth=(es_user, es_password) if es_user and es_password else None
            )
        else:
            self.client = AsyncElasticsearch(
                hosts=[f"http://{es_host}:{es_port}"],
                basic_auth=(es_user, es_password) if es_user and es_password else None
            )
    
    @classmethod
    async def initialize_client(
        cls, es_host: Optional[str] = None, es_port: Optional[int] = None, es_user: Optional[str] = None,
            es_password: Optional[str] = None,cloud_id: Optional[str] = None, api_key: Optional[str] = None
    ) -> 'ESClient':
        """
        Initialize and return a singleton instance of ESClient.
        
        Args:
            es_host (Optional[str]): Elasticsearch host
            es_port (Optional[int]): Elasticsearch port
            es_user (Optional[str]): Elasticsearch username
            es_password (Optional[str]): Elasticsearch password
            cloud_id (Optional[str]): Elastic Cloud ID for cloud connection
            api_key (Optional[str]): Elasticsearch API key
            
        Returns:
            ESClient: Singleton instance of ESClient
        """
        if cls._instance is None:
            cls._instance = cls(
                es_host=es_host,
                es_port=es_port,
                es_user=es_user,
                es_password=es_password,
                cloud_id=cloud_id,
                api_key=api_key
            )
            logger.info("Initialized Elasticsearch client")
        return cls._instance
    
    @classmethod
    async def close_client(cls):
        """Close the Elasticsearch client connection."""
        if cls._instance:
            await cls._instance.close()
            cls._instance = None
            logger.info("Closed Elasticsearch client")
    
    async def create_index(self, index_name: str, mappings: Dict[str, Any]) -> bool:
        """
        Create an Elasticsearch index with the specified mappings.
        
        Args:
            index_name (str): Name of the index to create
            mappings (Dict[str, Any]): Index mappings
            
        Returns:
            bool: True if index was created successfully, False otherwise
        """
        try:
            if not await self.client.indices.exists(index=index_name):
                await self.client.indices.create(
                    index=index_name,
                    mappings=mappings
                )
                logger.info(f"Created index: {index_name}")
                return True
            return False
        except Exception as e:
            logger.error(f"Error creating index {index_name}: {str(e)}")
            return False
    
    async def index_document(self, index_name: str, document: Dict[str, Any], doc_id: Optional[str] = None) -> bool:
        """
        Index a document in Elasticsearch.
        
        Args:
            index_name (str): Name of the index
            document (Dict[str, Any]): Document to index
            doc_id (Optional[str]): Document ID
            
        Returns:
            bool: True if document was indexed successfully, False otherwise
        """
        try:
            await self.client.index(
                index=index_name,
                document=document,
                id=doc_id
            )
            return True
        except Exception as e:
            logger.error(f"Error indexing document in {index_name}: {str(e)}")
            return False
    
    async def search(self, index_name: str, query: Dict[str, Any], size: int = 10) -> List[Dict[str, Any]]:
        """
        Search for documents in Elasticsearch.
        
        Args:
            index_name (str): Name of the index
            query (Dict[str, Any]): Search query
            size (int): Number of results to return
            
        Returns:
            List[Dict[str, Any]]: List of search results
        """
        try:
            response = await self.client.search(
                index=index_name,
                query=query,
                size=size
            )
            return [hit["_source"] for hit in response["hits"]["hits"]]
        except Exception as e:
            logger.error(f"Error searching in {index_name}: {str(e)}")
            return []
    
    async def delete_document(self, index_name: str, doc_id: str) -> bool:
        """
        Delete a document from Elasticsearch.
        
        Args:
            index_name (str): Name of the index
            doc_id (str): ID of the document to delete
            
        Returns:
            bool: True if document was deleted successfully, False otherwise
        """
        try:
            await self.client.delete(
                index=index_name,
                id=doc_id
            )
            return True
        except Exception as e:
            logger.error(f"Error deleting document {doc_id} from {index_name}: {str(e)}")
            return False
    
    async def close(self):
        """Close the Elasticsearch client connection."""
        await self.client.close() 