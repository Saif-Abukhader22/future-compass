"""
Algorithm: RAG Document Indexing with Validation

1. Pre-validation Stage:
    1.1. Load all filenames in the 'raw_documents' directory and store in `raw_doc_names`.
    1.2. Load all filenames in the 'documents_names' directory and store in `existing_doc_names`.
    1.3. Initialize `documents_will_be_used` as an empty list.
    1.4. Initialize `missing_in_raw` as an empty list.
    1.5. For each name in `existing_doc_names`:
        - If name is in `raw_doc_names`, append to `documents_will_be_used`.
        - Else, append to `missing_in_raw`.
    1.6. Compute `unused_raw` as all names in `raw_doc_names` not in `documents_will_be_used`.
    1.7. Print all items in `missing_in_raw`.
    1.8. Print all items in `unused_raw`.
    1.9. Ask the user: "Do you want to proceed with indexing? (yes/no)"
        - If user answers "no", stop the execution.

2. Load AI Agents:
    2.1. Call `load_agent_data()` with `db=session` and `load=True` to load all AI agents.

3. Document Indexing:
    3.1. For each agent in loaded agents:
        3.1.1. Fetch all related documents for the agent.
        3.1.2. For each document:
            - If document status == COMPLETED, skip.
            - Else:
                3.1.2.1. Extract text from the document.
                3.1.2.2. If no text is extracted:
                    - Run OCR on the document using pytesseract inside an async worker pool.
                    - Make sure the extracted text in another worker is returned and put in sequential order.
                3.1.2.3. Detect language of the text.
                3.1.2.4. If language is not English or text is not readable:
                    - Clean text to remove special characters and artifacts. decide the best way to clean according to the language, whether to use specific libraries or OCR.
                3.1.2.5. Semantically chunk the cleaned text.
                    - For each chunk, build a chunk object with:
                        - chunk_text
                        - chunk_hash
                        - prev_chunk_hash
                        - next_chunk_hash
                        - chunk_sequence
                        - document_id
                        - agents_ids
                        - token_count
                        - language
                        - source_page (if available)
                3.1.2.6. For each chunk object:
                    - Create an asyncio task to:
                        - Embed the chunk_text
                        - Store it in Elasticsearch with the associated metadata
                3.1.2.7. Await all embedding + storing tasks.
                3.1.2.8. Update document status to COMPLETED.
    Note: even the tasks are async, each document should be processed sequentially to prevent memory overflow.
"""
import logging
import os
from uuid import UUID

from mistralai import Mistral
import regex as re
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pypdf import PdfReader, PdfWriter
from sqlalchemy import select
from rich.console import Console
from rich.pretty import Pretty
from rich.table import Table
import markdown
from bs4 import BeautifulSoup

from community_service.DB import AsyncSessionLocal
from core_service.DB import Document, AgentDocument, Agent
from core_service.config import settings
from core_service.rag.es_client import ESClient
from shared.data_processing.text_processing.text_extractor import TextExtractor
from shared.enums import AgentDocumentProcessingStatus

console = Console()
PROCESS_ONLY_FOUND_FILES = True

"""
Fully‑working RAG document indexer.

▫  Performs a safety pre‑validation pass on the raw/processed‑name folders
▫  Loads all agents, walks their attached documents one‑by‑one
▫  Extracts / OCRs text, cleans & language‑detects
▫  Semantic‑chunks, embeds, and stores each chunk in Elasticsearch
▫  Updates document‑processing status flags along the way
"""

import asyncio
import hashlib
import sys
from pathlib import Path
from typing import List

from pdfminer.high_level import extract_text as pdf_extract
from docx import Document as DocxDocument

from langchain_community.document_loaders.text import TextLoader
from langdetect import detect, LangDetectException

from core_service.services.agent_manager import AgentManager

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

#############################################
# ------------ UTILITY FUNCS ---------------#
#############################################


RAW_DIR = Path("raw_documents")
ALPHA_RE = r'\p{L}'  # any Unicode letter
ALPHA3_RE = r'\p{L}{3,}'  # ≥3 consecutive letters


def get_raw_doc_names() -> set:
    return {p.name for p in RAW_DIR.iterdir() if p.is_file()}


def prevalidate(raw_doc_names: set, used_doc_names: set) -> None:
    """
    Validate based on actual used document names.
    Print what's missing and unused before proceeding.
    """
    missing_in_raw = used_doc_names - raw_doc_names
    unused_raw = raw_doc_names - used_doc_names

    if missing_in_raw:
        table = Table(title="Missing in Raw Documents")
        table.add_column("Filename", style="red")
        for name in sorted(missing_in_raw):
            table.add_row(name)
        console.print(table)

    if unused_raw:
        table = Table(title="Unused Raw Documents")
        table.add_column("Filename", style="yellow")
        for name in sorted(unused_raw):
            table.add_row(name)
        console.print(table)

    proceed = input("Do you want to proceed with indexing? (y/n): ").strip().lower()
    if proceed != "y":
        console.print("[bold red]User aborted execution – exiting.[/bold red]")
        sys.exit(0)


async def extract_text(path: Path) -> str:
    """
    Load text from .txt, .pdf, or .docx. Falls back to empty string if it fails.
    """
    ext = path.suffix.lower()
    try:
        if ext == ".txt":
            return (await asyncio.to_thread(path.read_text)).strip()
        elif ext == ".pdf":
            # synchronous but offloaded to thread so we don't block the event loop
            return await asyncio.to_thread(pdf_extract, str(path))
        elif ext in (".docx", ".doc"):
            def _load_docx():
                doc = DocxDocument(str(path))
                return "\n".join(p.text for p in doc.paragraphs)

            return await asyncio.to_thread(_load_docx)
        else:
            # fallback to LangChain for anything else (markdown, etc.)
            loader = TextLoader(str(path))
            docs = await asyncio.to_thread(loader.load)
            return "\n".join(d.page_content for d in docs)
    except Exception as exc:
        logger.error("Extraction failed for %s: %s", path.name, exc)
        return ""


async def ocr_text(path: Path, lang_hint: str = "eng+ara") -> str:
    content = await asyncio.to_thread(path.read_bytes)
    extractor = TextExtractor(content, file_ext="pdf")
    return extractor.extract_text_from_uploaded_file()


async def mistral_ocr_text(path: Path) -> str:
    """
    Fallback: upload PDF to Mistral and get OCR result via signed URL.
    Extracts structured text from markdown of each page.
    """

    def _sync_mistral(pdf_path: Path) -> str:
        api_key = settings.MISTRAL_API_KEY
        if not api_key:
            raise RuntimeError("MISTRAL_API_KEY is not set")

        client = Mistral(api_key=api_key)

        pdf_bytes = pdf_path.read_bytes()
        uploaded_pdf = client.files.upload(
            file={
                "file_name": pdf_path.name,
                "content": pdf_bytes,
            },
            purpose="ocr",
        )

        signed_url = client.files.get_signed_url(file_id=uploaded_pdf.id)

        ocr_response = client.ocr.process(
            model="mistral-ocr-latest",
            document={
                "type": "document_url",
                "document_url": signed_url.url,
            },
        )

        pages_sorted = sorted(ocr_response.pages, key=lambda p: p.index)
        markdown_text = "\n\n".join(p.markdown for p in pages_sorted)

        html = markdown.markdown(markdown_text)
        soup = BeautifulSoup(html, "html.parser")
        plain_text = soup.get_text(separator="\n")

        return plain_text.strip()

    return await asyncio.to_thread(_sync_mistral, path)


async def mistral_ocr_paginated(path: Path, max_pages: int = 1000) -> str:
    reader = await asyncio.to_thread(PdfReader, str(path))
    total = len(reader.pages)
    parts = []
    for start in range(0, total, max_pages):
        end = min(start + max_pages, total)

        # build the chunk writer off-thread

        def _write_chunk(reader, start, end, temp_path):
            writer = PdfWriter()

            for p in range(start, end):
                writer.add_page(reader.pages[p])

            with open(temp_path, "wb") as f:
                writer.write(f)

        temp = path.with_name(f"{path.stem}_{start + 1}_{end}{path.suffix}")
        await asyncio.to_thread(_write_chunk, reader, start, end, str(temp))
        try:
            part_text = await mistral_ocr_text(temp)
        finally:
            temp.unlink()
        parts.append(part_text)
    return "\n\n".join(parts)


def clean_text(text: str, language: str) -> str:
    """
    Naïve cleaning – strip control chars, multiple‑spaces, etc.
    You can plug in language‑specific pipelines here.
    """
    text = re.sub(r"\s+", " ", text)
    if language != "en":
        # remove latin artifacts & keep language‑specific chars + basic punctuation
        pattern = r"[^؀-ۿ\w\s\.,;:!\?\-]" if language == "ar" else r"[^\w\s\.,;:!\?\-]"
        text = re.sub(pattern, " ", text)
    return text.strip()


def is_meaningful_chunk(chunk: str) -> bool:
    tokens = chunk.split()
    if len(tokens) < 20:  # was 10 – beef it up a little
        return False

    # Strip everything that is not a letter for the ratio test
    alpha_chars = re.findall(ALPHA_RE, chunk)
    alpha_ratio = len(alpha_chars) / max(len(chunk), 1)

    # How many tokens contain a “real” word‑like substring?
    word_like = [t for t in tokens if re.search(ALPHA3_RE, t)]
    word_like_ratio = len(word_like) / len(tokens)

    # How many tokens are only a single letter?
    single_letter = [t for t in tokens if re.fullmatch(ALPHA_RE, t)]
    single_ratio = len(single_letter) / len(tokens)

    return (
            alpha_ratio > 0.65  # raise the bar
            and word_like_ratio > 0.50  # at least half the tokens look like words
            and single_ratio < 0.20  # too many single letters → gibberish
    )


def looks_like_real_text(text: str) -> bool:
    if len(text) < 400:
        return False

    words = text.split()
    if len(words) < 50:
        return False

    alpha_chars = re.findall(ALPHA_RE, text)
    alpha_ratio = len(alpha_chars) / max(len(text), 1)

    # Word-like tokens: must have 3+ consecutive letters
    word_like = [w for w in words if re.search(ALPHA3_RE, w)]
    word_like_ratio = len(word_like) / len(words)

    # Penalize texts with too many special characters or symbols
    gibberish_penalty = len(re.findall(r"[^\w\s\.,;:!?-]", text)) / len(text)

    # Fail if there are too few good words or too many odd symbols
    # print("Alpha Ratio:", alpha_ratio)
    # print("Word-like Ratio:", word_like_ratio)
    # print("Gibberish Penalty:", gibberish_penalty)
    return (
            alpha_ratio > 0.65
            and word_like_ratio > 0.50
            and gibberish_penalty < 0.10
    )


def semantic_chunk(text: str, chunk_size_tokens: int = 380, overlap: int = 40) -> List[str]:
    """
    Simple RecursiveCharacter splitter.  For more advanced semantic splitting,
    plug in semantic-text-splitter once it's installed.
    """
    splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
        chunk_size=chunk_size_tokens,
        chunk_overlap=overlap,
    )
    return splitter.split_text(text)


def sha256_hex(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


#############################################
# ------------ MAIN LOGIC ------------------#
#############################################


agent_manager = AgentManager()
es_client = ESClient()


async def process_document(
        session,
        agent_id,
        doc: Document,
) -> None:
    """
    End‑to‑end pipeline for one document.
    Processes sequentially; embeds + ES writes within the doc are batched async.
    """
    logger.info("▶︎ Processing document «%s» (%s)", doc.document_title, doc.document_id)
    doc.document_status = AgentDocumentProcessingStatus.EXTRACTING_TEXT
    await session.commit()

    file_path = RAW_DIR / doc.name_with_ext
    text = await extract_text(file_path)

    if not looks_like_real_text(text):
        logger.warning("Low‑quality PDFMiner output – trying OCR for %s", file_path.name)
        try:
            text = await mistral_ocr_paginated(file_path, max_pages=1000)
        except Exception as e:
            logger.error("Mistral OCR failed for %s: %s", file_path.name, e)
            text = ""
        # print(text)

    if len(text.strip()) < 100 or not any(c.isalpha() for c in text):  # too short or no real text
        logger.warning("Still too short after OCR – skipping %s", doc.name_with_ext)
        doc.document_status = AgentDocumentProcessingStatus.EXTRACTING_TEXT_FAILED
        await session.commit()
        return

    # language detection
    try:
        language = detect(text)
    except LangDetectException:
        language = "unknown"

    # chunking
    doc.document_status = AgentDocumentProcessingStatus.CHUNKING_TEXT_SEMANTICALLY
    await session.commit()

    raw_chunks = semantic_chunk(text)
    chunks = [c for c in raw_chunks if is_meaningful_chunk(c)]

    if not chunks:
        doc.document_status = AgentDocumentProcessingStatus.CHUNKING_TEXT_SEMANTICALLY_FAILED
        await session.commit()
        logger.warning("All chunks discarded as meaningless for document: %s", doc.name_with_ext)
        return

    # build meta objects
    docs_to_index = []
    embeddings_input = []
    for idx, chunk in enumerate(chunks):
        chunk_hash = sha256_hex(f"{doc.document_id}:{idx}:{chunk}")
        prev_hash = sha256_hex(f"{doc.document_id}:{idx - 1}") if idx > 0 else ""
        next_hash = sha256_hex(f"{doc.document_id}:{idx + 1}") if idx < len(chunks) - 1 else ""
        embeddings_input.append(chunk)
        meta = {
            "chunk_text": chunk,
            "chunk_hash": chunk_hash,
            "prev_chunk_hash": prev_hash,
            "next_chunk_hash": next_hash,
            "chunk_sequence": idx,
            "document_id": str(doc.document_id),
            "agent_ids": [str(agent_id)],
            "token_count": len(chunk.split()),  # rough estimate
            "language": language,
            "source_page": None,
        }
        docs_to_index.append(meta)
        # console.print(Pretty(meta))

    # embed with batching to respect token limits
    doc.document_status = AgentDocumentProcessingStatus.EMBEDDING_AND_STORING_IN_ES
    await session.commit()

    async def batch_embed(texts: List[str], batch_size: int = 500) -> List[List[float]]:
        vectors = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i: i + batch_size]
            batch_vectors = await es_client.embed(batch)
            vectors.extend(batch_vectors)
        return vectors

    embeddings = await batch_embed(embeddings_input, batch_size=500)
    for meta, vector in zip(docs_to_index, embeddings):
        meta["embedding"] = vector

    await es_client.bulk_index(docs_to_index)

    # finalise
    doc.document_status = AgentDocumentProcessingStatus.COMPLETED
    await session.commit()
    logger.info("✓ Completed document «%s»", doc.document_title)


async def agent_loop(session) -> None:
    """
    Iterate over agents one‑after‑another,
    processing their attached documents sequentially.
    """
    result = await session.execute(select(Agent))
    agents = result.scalars().all()

    for agent in agents:
        agent_read = await agent_manager.get_agent_by_id(session, agent.agent_id)
        logger.info("=== Agent %s (%s) ===", agent_read.name, agent.agent_id)
        # Explicitly load this agent’s documents via join
        result = await session.execute(
            select(Document)
            .join(AgentDocument, Document.document_id == AgentDocument.document_id)
            .where(AgentDocument.agent_id == agent.agent_id)
        )

        for doc in result.scalars().all():
            if doc.document_status == AgentDocumentProcessingStatus.COMPLETED:
                continue
            await process_document(session, agent.agent_id, doc)  # sequential per doc


async def main() -> None:
    raw_doc_names = get_raw_doc_names()
    used_doc_names = set()

    async with AsyncSessionLocal() as session:
        await es_client.initialize_client()

        await agent_manager.load_agent_data(db=session, load=True)
        result = await session.execute(select(Agent))
        agents = result.scalars().all()

        for agent in agents:
            # load docs for validation
            result = await session.execute(
                select(Document)
                .join(AgentDocument, Document.document_id == AgentDocument.document_id)
                .where(AgentDocument.agent_id == agent.agent_id)
            )

            for doc in result.scalars().all():
                used_doc_names.add(doc.name_with_ext)

        prevalidate(raw_doc_names, used_doc_names)

        choice = input("Do you want to process only found documents? (y/n): ").strip().lower()
        global PROCESS_ONLY_FOUND_FILES
        PROCESS_ONLY_FOUND_FILES = (choice == "y")

        # Now re-iterate to actually process the documents
        for agent in agents:
            agent_read = await agent_manager.get_agent_by_id(session, agent.agent_id)
            logger.info("=== Agent %s (%s) ===", agent_read.name, agent.agent_id)

            result = await session.execute(
                select(Document)
                .join(AgentDocument, Document.document_id == AgentDocument.document_id)
                .where(AgentDocument.agent_id == agent.agent_id)
            )
            docs = result.scalars().all()

            # console.print(f"[bold cyan]Documents for agent {agent.name} ({agent.agent_id}):[/bold cyan]")
            # console.print(Pretty([doc.name_with_ext for doc in docs]))

            for doc in docs:
                file_path = RAW_DIR / doc.name_with_ext
                if PROCESS_ONLY_FOUND_FILES and not file_path.exists():
                    # console.print(f"[yellow]⚠ Skipping missing file:[/yellow] {file_path.name}")
                    continue

                if doc.document_status == AgentDocumentProcessingStatus.COMPLETED:
                    continue

                await process_document(session, agent.agent_id, doc)

        await es_client.close()


if __name__ == "__main__":
    asyncio.run(main())
