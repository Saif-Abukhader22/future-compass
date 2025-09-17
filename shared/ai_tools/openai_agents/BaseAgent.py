import datetime
import json
import re
from typing import Optional, List, Union, Any
import asyncio
from uuid import UUID

from agents import (
    Agent,
    Runner,
    Tool,
    TResponseInputItem,
    ModelSettings,
    OpenAIChatCompletionsModel,
    RunHooks, RunContextWrapper,
)
from openai import AsyncOpenAI
from rich.logging import RichHandler
from rich.pretty import Pretty
from rich.console import Console

from core_service.DB.models.mongo.message import Message, MessageRole
from shared import shared_settings
from shared.enums import OpenAIModelSlugEnum
from core_service.schemas.open_ai_client import FunctionCall, UsageInfo, BaseAgentRunResponse
from shared.utils.logger import TsLogger

logger = TsLogger(__name__)
console = Console(force_terminal=True)  # Force color output in all terminal environments


class BaseAgent:
    """
    A reusable base for any Agent-driven workflow.
    Manages:
      - model / client
      - instructions
      - tools
      - conversation memory
      - run loop
    """

    def __init__(
            self,
            source_id: UUID,
            agent_name: str,
            model_name: OpenAIModelSlugEnum,
            instructions: str,
            tools: Optional[List[Tool]] = None,
            *,
            model_settings: Optional[ModelSettings] = None,
            openai_client: Optional[AsyncOpenAI] = None,
            context_messages: Optional[List[TResponseInputItem]] = None,
            thread_memory: Optional[str] = '',
            store_fnc_calls: Optional[bool] = False,
    ):
        self._source_id = source_id
        self._agent_name = agent_name
        self._model_name = model_name
        self._instructions = f"""
           {instructions}
           {thread_memory}
        """
        self._tools = tools or []
        self._store_fnc_calls = store_fnc_calls

        # defaults if not provided
        self._model_settings = model_settings or ModelSettings()

        if openai_client is not None:
            self._openai_client = openai_client
        else:
            import httpx

            async def log_response(response: httpx.Response):
                try:
                    await response.aread()
                    try:
                        content = response.json()
                    except Exception:
                        content = response.text
                    # logging.info(
                    #     f"[RESPONSE {response.status_code}] {response.url}\n{json.dumps(content, indent=2) if isinstance(content, dict) else content}"
                    # )
                except Exception as e:
                    logger.error(f"[RESPONSE ERROR] Failed to read response body: {e}")

            http_client = httpx.AsyncClient(
                event_hooks={"response": [log_response]}
            )
            from openai import AsyncOpenAI
            self._openai_client = AsyncOpenAI(http_client=http_client, api_key=shared_settings.OPENAI_API_KEY)

        # preserve history across runs
        self._context_messages: List[TResponseInputItem] = context_messages or []

        # will be built on first run
        self._agent: Optional[Agent] = None

    def add_tool(self, tool: Tool) -> None:
        """Attach an extra tool to this agent."""
        self._tools.append(tool)

    def set_openai_client(self, client: AsyncOpenAI) -> None:
        """If you need a custom HTTP client or hooks, inject it here."""
        self._openai_client = client
        # force rebuild on the next run
        self._agent = None

    def _build_agent(self) -> Agent:
        """Instantiate the Agent object only once (or after a client change)."""
        if self._agent is None:
            llm = OpenAIChatCompletionsModel(
                model=self._model_name.value,
                openai_client=self._openai_client,
            )
            self._agent = Agent(
                name=self._agent_name,
                model=llm,
                model_settings=self._model_settings,
                instructions=self._instructions,
                tools=self._tools,
            )
        return self._agent

    @staticmethod
    def strip_html_tags(text: str) -> str:
        """Remove HTML tags from a string."""
        return re.sub(r'<[^>]+>', '', text)

    async def run(
            self,
            user_input: Union[str, List[TResponseInputItem]],
            *,
            hooks: Optional[RunHooks] = None,
            context: Any = None
    ) -> BaseAgentRunResponse:
        # — prepare context —
        if isinstance(user_input, str):
            self._context_messages.append({"role": "user", "content": user_input})
        else:
            self._context_messages = user_input

        agent = self._build_agent()

        # Clean and normalize all context messages before sending to OpenAI
        cleaned_input = []
        for msg in self._context_messages:
            role = msg.get("role")
            raw_content = msg.get("content")

            # 🔐 Skip invalid message
            if role is None or raw_content is None:
                continue

            # Normalize content into a string
            if isinstance(raw_content, str):
                content = raw_content
            elif isinstance(raw_content, dict) and raw_content.get("type") == "text":
                content = raw_content.get("text", "")
            elif isinstance(raw_content, list):
                content = "".join(
                    item.get("text", "") for item in raw_content if item.get("type") == "text"
                )
            else:
                content = str(raw_content)  # fallback

            # Optional: Strip HTML from assistant messages
            if role == "assistant":
                content = self.strip_html_tags(content)

            cleaned_input.append({"role": role, "content": content})

        # run the agent
        result = await Runner.run(
            agent,
            input=cleaned_input,
            hooks=hooks,
            context=context,
        )

        # — extract usage —
        usage_wrapper: RunContextWrapper = result.context_wrapper
        usage = UsageInfo(
            requests=usage_wrapper.usage.requests,
            input_tokens=usage_wrapper.usage.input_tokens,
            output_tokens=usage_wrapper.usage.output_tokens,
            total_tokens=usage_wrapper.usage.total_tokens,
        )

        # — extract function calls —
        call_items = [i for i in result.new_items if i.type == "tool_call_item"]
        output_items = [i for i in result.new_items if i.type == "tool_call_output_item"]

        function_calls: List[FunctionCall] = []
        for call_item in call_items:
            raw = call_item.raw_item
            call_id = getattr(raw, "call_id", getattr(raw, "id", None))
            name = raw.name

            try:
                arguments = json.loads(raw.arguments)
            except Exception:
                arguments = raw.arguments

            result_output = None
            for out_item in output_items:
                out_raw = out_item.raw_item
                if out_raw.get("call_id") == call_id:
                    result_output = out_item.output
                    break

            function_calls.append(FunctionCall(
                call_id=call_id,
                name=name,
                arguments=arguments,
                result=result_output,
            ))

            if self._store_fnc_calls:
                for fc in function_calls:
                    tool_msg = Message(
                        thread_id=context.thread_id,
                        source_id=self._source_id,
                        role=MessageRole.tool,
                        content="",  # no direct user text
                        is_function_call=True,
                        function_name=fc.name,
                        function_args=json.dumps(fc.arguments, default=str, ensure_ascii=False),
                        function_result=json.dumps(fc.result, default=str, ensure_ascii=False),
                        created_at=datetime.datetime.now(datetime.timezone.utc)
                    )
                    tool_msg.save()
            # TODO: store function responses from the system..

        # — update context —
        self._context_messages = result.to_input_list()

        # — return structured response —
        return BaseAgentRunResponse(
            response=result.final_output,
            usage=usage,
            function_calls=function_calls
        )

    def run_sync(
            self,
            user_input: Union[str, List[TResponseInputItem]],
            *,
            hooks: Optional[RunHooks] = None,
    ) -> dict:
        return asyncio.get_event_loop().run_until_complete(
            self.run(user_input, hooks=hooks)
        )
