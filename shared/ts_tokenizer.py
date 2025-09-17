from typing import List

import tiktoken
from sqlalchemy.ext.asyncio import AsyncSession

from shared.enums import OpenAIModelSlugEnum
from core_service.DB.models.platform_management import OpenAIModel
from core_service.schemas.api_request import TokenStats
from core_service.services.open_ai_model import OpenAIModelService


# from utils.errors import log_error


class TsTokenizer:

    def __init__(self, model: OpenAIModelSlugEnum | OpenAIModel):
        """
        Initialize tokenizer with provided or default OpenAI model.

        :param model: Slug of OpenAI model or OpenAIModel instance
        :raise ValueError: If provided model is not found
        """
        # TODO: fix to encode all models, now its GPT4o by default
        self.model = None

        encoding = self.model.name  # Use provided model
        try:
            self.encoding = tiktoken.encoding_for_model(encoding)
        except KeyError as e:
            self.encoding = None

    async def init(self):
        gpt_4o_mini_model = await OpenAIModelService().get_model_by_slug(
            model_slug=OpenAIModelSlugEnum.GPT_4O_MINI,
            db=self.db,
        )
        if gpt_4o_mini_model is None:
            raise ValueError("GPT-4O-Mini model not found.")


    def num_of_tokens(self, text: str) -> int | None:
        if self.encoding:
            return len(self.encoding.encode(text))
        else:
            return None

    def tokens_stats(
            self,
            prompt: str = '',
            context_messages: List[str] = None,
            user_message: str = '',
            ai_response: str = ''
    ) -> TokenStats:
        stats = TokenStats()
        if self.encoding is None:
            return stats

        # Token counts
        stats.prompt_tokens = len(self.encoding.encode(prompt))
        context_text = ''
        for message in context_messages:
            context_text += str(message)
        stats.context_tokens = len(self.encoding.encode(context_text))
        stats.input_tokens = len(self.encoding.encode(user_message))
        stats.response_tokens = len(self.encoding.encode(ai_response))

        # Calculating costs
        # Token counts
        stats.prompt_cost = stats.prompt_tokens * self.model.input_cost / 1000
        stats.context_cost = stats.context_tokens * self.model.input_cost / 1000
        stats.input_cost = stats.input_tokens * self.model.input_cost / 1000
        stats.response_cost = stats.response_tokens * self.model.output_cost / 1000

        stats.prompt_cost = "{:.6f}".format(stats.prompt_cost)
        stats.context_cost = "{:.6f}".format(stats.context_cost)
        stats.input_cost = "{:.6f}".format(stats.input_cost)
        stats.response_cost = "{:.6f}".format(stats.response_cost)

        return stats
