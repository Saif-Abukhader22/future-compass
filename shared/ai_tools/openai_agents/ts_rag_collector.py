# ── add near the other imports ────────────────────────────────────────────────
import asyncio
from collections import Counter, defaultdict
from typing import Dict, List, Optional, Tuple
from uuid import UUID

from agents import ModelSettings
from langdetect import detect_langs
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core_service.DB.models.ai_agents import AgentDocument, Document
from core_service.rag.es_query_handler import ElasticsearchQueryHandler
from core_service.schemas.open_ai_client import (BaseAgentRunResponse,
                                                 FunctionCall, UsageInfo)
from core_service.utils.ai_utils.translate import Translate
from core_service.utils.ts_tokenizer import TsTokenizer
from shared.ai_tools.openai_agents.BaseAgent import BaseAgent
from shared.enums import OpenAIModelSlugEnum
from shared.utils.logger import TsLogger

logger = TsLogger(__name__)
# ──────────────────────────────────────────────────────────────────────────────


def get_ts_rag_collector_instructions() -> str:  # noqa: D401
    """
    System prompt handed to the *LLM inside* the collector **if** it is ever
    invoked.  (The current implementation performs all heuristics in Python, so
    the LLM is never called – we keep this helper for completeness.)
    """
    return (
        "You are *TS RAG Collector* – a silent background agent. "
        "When explicitly asked you will decide whether additional Retrieval‑"
        "Augmented Generation (RAG) context is required, and if so you will "
        "return ONLY the string provided to you by the host process.  Under no "
        "circumstances should you talk to the user directly."
    )


class TsRAGCollector(BaseAgent):
    """
    Collects RAG‑ready chunks for an **area‑of‑knowledge agent**.

    Workflow
    --------
    1.  Decide – via cheap heuristics – whether a RAG query is warranted.
    2.  If not, return an **empty string** so the caller can skip RAG.
    3.  Otherwise:
        • Find all documents attached to the agent.
        • Detect the document language that appears most frequently.
        • Craft/translate the user’s latest inquiry into that language.
        • Embed & query Elasticsearch (filtered by this agent) for the
          top‑`TOP_K` hits.
        • Expand around each hit until ~`MAX_TOKENS` tokens are reached, using
          the `prev_chunk_hash` and `next_chunk_hash` links in ES.
        • Build one consolidated prompt that:
            – clearly separates the chunks,
            – prefixes them with the originating **book title**, and
            – instructs the downstream answering agent to rely primarily on
              these chunks while respecting each book’s broader context.
    """

    # tuning knobs
    TOP_K: int = 5
    MAX_TOKENS: int = 1000

    def __init__(
        self,
        *,
        source_id: UUID,
        agent_id: UUID,
        db: AsyncSession,
    ) -> None:
        self._db: AsyncSession = db
        self._agent_id: UUID = agent_id

        # no LLM tools – we will work fully in Python
        super().__init__(
            source_id=source_id,
            agent_name="TS RAG Collector",
            model_name=OpenAIModelSlugEnum.GPT_4_1_NANO,
            instructions=get_ts_rag_collector_instructions(),
            tools=[],
            model_settings=ModelSettings(temperature=0),
        )

    # --------------------------------------------------------------------- #
    # internal helpers                                                      #
    # --------------------------------------------------------------------- #

    async def _fetch_agent_documents(self) -> List[Document]:
        """Return all `Document`s linked to the current agent."""
        stmt = (
            select(Document)
            .join(AgentDocument, Document.document_id == AgentDocument.document_id)
            .where(AgentDocument.agent_id == self._agent_id)
        )
        result = await self._db.execute(stmt)
        return result.scalars().all()

    async def _dominant_language(self, docs: List[Document]) -> Optional[str]:
        """Most frequent `main_language` among the agent’s documents."""
        if not docs:
            return None
        counts = Counter(d.main_language for d in docs)
        return counts.most_common(1)[0][0]

    @staticmethod
    def _latest_user_query(messages: List[dict]) -> str:
        """Extract plain‑text from the last user message in the payload."""
        for item in reversed(messages):
            if item.get("type") == "message" and item.get("role") == "user":
                # concatenate all text parts
                return "".join(
                    part.get("text", "")
                    for part in item.get("content", [])
                    if part.get("type") == "text"
                ).strip()
        return ""

    @staticmethod
    def _needs_rag(query: str) -> bool:
        """
        Ridiculously cheap heuristic:
        • No RAG for very short queries (< 4 words).
        • No RAG when the query clearly is a simple greeting / acknowledgment.
        """
        simple_phrases = {"thanks", "thank you", "okay", "hi", "hello"}
        if not query or len(query.split()) < 4:
            return False
        if query.lower().strip(" .,!") in simple_phrases:
            return False
        return True

    async def _maybe_translate(
        self, text: str, target_lang: str
    ) -> Tuple[str, bool]:
        """Translate `text` to `target_lang` if needed; returns (final_text, did_translate)."""
        try:
            detected = detect_langs(text)[0].lang
        except Exception:
            detected = "en"

        if detected == target_lang:
            return text, False

        # translation required
        translate = Translate(self._db)
        translated = await translate.get_translated_string(text, dest_lang=target_lang)
        return translated, True

    async def _es_search(
        self, query_text: str
    ) -> List[Dict]:
        """
        Query ES with filters:
            • agent_id = current agent
            • semantic search with embeddings (handled inside `search_and_filter`)
        """
        es_q = ElasticsearchQueryHandler()
        hits = await es_q.search_and_filter(
            query_text=query_text,
            metadata_filters={"agent_id": str(self._agent_id)},
            top_k=self.TOP_K,
        )
        return hits or []

    async def _fetch_chunk_by_hash(self, chunk_hash: str) -> Optional[Dict]:
        """Helper that fetches a *single* chunk doc by ES _id (=hash)."""
        es_q = ElasticsearchQueryHandler()
        try:
            doc = await es_q.get_by_id(chunk_hash)
            return doc.get("_source")
        except Exception:  # noqa: BLE001
            return None

    async def _expand_chunks_to_token_budget(
        self, primary_hits: List[Dict]
    ) -> List[Dict]:
        """
        For each primary hit, include adjacent chunks until the overall selection
        is close to `MAX_TOKENS`.
        """
        tokenizer = TsTokenizer()  # auto‑detects best model
        selected: Dict[str, Dict] = {}

        async def add_chunk(c: Dict):
            if c and c["chunk_hash"] not in selected:
                selected[c["chunk_hash"]] = c

        # first add primaries
        for hit in primary_hits:
            await add_chunk(hit["_source"])

        # token counting loop
        async def total_tokens() -> int:
            return sum(
                tokenizer.num_of_tokens(chunk["chunk_text"])
                for chunk in selected.values()
            )

        for hit in primary_hits:
            if await total_tokens() >= self.MAX_TOKENS:
                break

            src = hit["_source"]
            # fetch prev / next while budget allows
            for neighbour_hash in (src.get("prev_chunk_hash"), src.get("next_chunk_hash")):
                if neighbour_hash and await total_tokens() < self.MAX_TOKENS:
                    neighbour = await self._fetch_chunk_by_hash(neighbour_hash)
                    await add_chunk(neighbour)

        # return chunks ordered by (document_id, chunk_sequence)
        grouped = defaultdict(list)
        for c in selected.values():
            grouped[c["document_id"]].append(c)
        for lst in grouped.values():
            lst.sort(key=lambda x: x.get("chunk_sequence", 0))

        flattened: List[Dict] = []
        for doc_id in grouped:
            flattened.extend(grouped[doc_id])
        return flattened

    async def _build_prompt(
        self, chunks: List[Dict], documents_by_id: Dict[str, Document]
    ) -> str:
        """
        Human‑readable prompt instructing the answering agent to rely on these
        specific chunks.  Each chunk is preceded by the book title.
        """
        lines: List[str] = [
            "The following reference chunks have been retrieved for the "
            "user’s inquiry. **You must ground your answer primarily in these "
            "chunks.** Feel free to use normal knowledge to connect them, but "
            "*do not* hallucinate details outside the provided books.\n"
        ]
        current_doc: Optional[str] = None
        counter = 1

        for c in chunks:
            doc_id = c["document_id"]
            if doc_id != current_doc:
                current_doc = doc_id
                book_name = documents_by_id.get(doc_id).document_title  # type: ignore[arg-type]
                lines.append(f"\n### Book: {book_name}\n")

            lines.append(f"--- chunk {counter} ---")
            lines.append(c["chunk_text"].strip())
            lines.append(f"--- end chunk {counter} ---\n")
            counter += 1

        lines.append(
            "\nWhen answering, **explicitly reference** the above chunks where "
            "appropriate, and take into account the broader context of each "
            "source book."
        )
        return "\n".join(lines)

    # ------------------------------------------------------------------ #
    # public API – overrides BaseAgent                                   #
    # ------------------------------------------------------------------ #

    async def run(  # type: ignore[override]
        self,
        user_input: List[dict],
        *,
        hooks=None,
        context=None,
    ) -> BaseAgentRunResponse:
        """
        Override `BaseAgent.run()` with a *pure‑Python* RAG collector.

        The return type matches what the surrounding infrastructure expects,
        but `usage` and `function_calls` are empty because no LLM call happens
        here.
        """
        try:
            # 1) extract latest user query
            query_text = self._latest_user_query(user_input)

            # 2) quick check → bail early if no RAG needed
            if not self._needs_rag(query_text):
                return BaseAgentRunResponse(
                    response="",
                    usage=UsageInfo(requests=0, input_tokens=0, output_tokens=0, total_tokens=0),
                    function_calls=[],
                )

            # 3) fetch attached documents & dominant language
            docs = await self._fetch_agent_documents()
            if not docs:
                logger.warning("Agent %s has no linked documents – skipping RAG.", self._agent_id)
                return BaseAgentRunResponse(
                    response="",
                    usage=UsageInfo(requests=0, input_tokens=0, output_tokens=0, total_tokens=0),
                    function_calls=[],
                )
            dom_lang = await self._dominant_language(docs)

            # 4) translate query if necessary
            query_text, _ = await self._maybe_translate(query_text, dom_lang)

            # 5) ES semantic search
            hits = await self._es_search(query_text)
            if not hits:
                logger.debug("No ES hits – returning empty RAG prompt.")
                return BaseAgentRunResponse(
                    response="",
                    usage=UsageInfo(requests=0, input_tokens=0, output_tokens=0, total_tokens=0),
                    function_calls=[],
                )

            # 6) expand to ~1000 tokens
            chunks = await self._expand_chunks_to_token_budget(hits)

            # 7) build final RAG prompt
            doc_by_id = {str(d.document_id): d for d in docs}
            prompt = await self._build_prompt(chunks, doc_by_id)

            return BaseAgentRunResponse(
                response=prompt,
                usage=UsageInfo(requests=0, input_tokens=0, output_tokens=0, total_tokens=0),
                function_calls=[],
            )

        except Exception as exc:  # noqa: BLE001
            logger.error("TsRAGCollector failed: %s", exc, exc_info=True)
            # On failure fall back to “no‑RAG”.
            return BaseAgentRunResponse(
                response="",
                usage=UsageInfo(requests=0, input_tokens=0, output_tokens=0, total_tokens=0),
                function_calls=[],
            )
