from shared.config import shared_settings
from shared.enums import OpenAIModelSlugEnum
from shared.rag.es_client import ESClient
from langchain_openai import OpenAIEmbeddings

from shared.rag.es_enums import EsEnums


class ElasticsearchWriteHandler:
    def __init__(self, es_client: ESClient):
        """
        Initialize the ElasticsearchWriteHandler.
        """
        self.es = es_client
        self.rag_index_name = shared_settings.THEOSUMMA_ES_INDEX
        self.embed_model = OpenAIEmbeddings(
            model=EsEnums.get_embedding_model(),
            openai_api_key=shared_settings.OPENAI_API_KEY
        )