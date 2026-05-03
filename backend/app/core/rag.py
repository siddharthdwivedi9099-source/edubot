"""
LangChain RAG pipeline.

- Ingests knowledge-base articles into a Chroma vector store.
- Retrieves top-k relevant chunks for a query, optionally filtered by
  audience/category.
- Returns both the answer and the cited sources so the UI can render them.
"""
import os
from typing import List, Optional, Tuple

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from loguru import logger

from app.config import get_settings
from app.core.llm import get_embeddings, get_chat_llm
from app.models.schemas import KBArticle, Source


COLLECTION = "edubot_kb"


def _splitter() -> RecursiveCharacterTextSplitter:
    return RecursiveCharacterTextSplitter(
        chunk_size=800, chunk_overlap=120,
        separators=["\n\n", "\n", ". ", " ", ""],
    )


def _vector_store() -> Chroma:
    s = get_settings()
    os.makedirs(s.chroma_persist_dir, exist_ok=True)
    return Chroma(
        collection_name=COLLECTION,
        embedding_function=get_embeddings(),
        persist_directory=s.chroma_persist_dir,
    )


def ingest_articles(articles: List[KBArticle]) -> int:
    """Chunk + embed + persist articles. Returns chunks added."""
    splitter = _splitter()
    docs: List[Document] = []
    for art in articles:
        chunks = splitter.split_text(art.content)
        for i, chunk in enumerate(chunks):
            docs.append(
                Document(
                    page_content=chunk,
                    metadata={
                        "article_id": art.id,
                        "title": art.title,
                        "category": art.category,
                        "audience": ",".join(art.audience),
                        "tags": ",".join(art.tags),
                        "chunk": i,
                    },
                )
            )
    vs = _vector_store()
    vs.add_documents(docs)
    logger.info(f"Ingested {len(docs)} chunks from {len(articles)} articles")
    return len(docs)


def search(query: str, k: int = 5, audience: Optional[str] = None,
           category: Optional[str] = None) -> List[Tuple[Document, float]]:
    vs = _vector_store()
    flt = {}
    if audience:
        flt["audience"] = {"$contains": audience}  # comma-list contains
    if category:
        flt["category"] = category
    # Chroma's $contains isn't on plain string fields; we filter client-side
    # for audience to keep this portable across versions.
    raw = vs.similarity_search_with_score(query, k=k * 3 if audience else k)
    if audience:
        raw = [(d, s) for d, s in raw if audience in (d.metadata.get("audience") or "")]
    if category:
        raw = [(d, s) for d, s in raw if (d.metadata.get("category") or "") == category]
    return raw[:k]


def collection_size() -> int:
    try:
        return _vector_store()._collection.count()
    except Exception as e:
        logger.warning(f"Could not read collection size: {e}")
        return 0


def reset_collection() -> None:
    """Wipe the collection — used by re-ingestion scripts."""
    try:
        _vector_store().delete_collection()
        logger.info("Collection deleted")
    except Exception as e:
        logger.warning(f"Could not reset collection: {e}")


# ── RAG generation ──────────────────────────────────────────────────────────

RAG_SYSTEM_TEMPLATE = """You are EduBot, an AI assistant for a school. Answer the user's question \
using ONLY the context provided below. If the context does not contain the answer, say so honestly \
and suggest who the user should contact (e.g. class teacher, admin office). Be concise and clear.

User role: {persona}

Context from school knowledge base:
{context}

Rules:
- Cite article titles inline when you use them, e.g. (Source: Attendance Policy).
- Do not invent facts not present in the context.
- If the user asks about personal data (their attendance, fees, etc.), tell them you'll fetch it \
  from the school ERP — do not fabricate numbers.
- Keep answers under 200 words unless the user asks for detail.
"""


async def rag_answer(query: str, persona: str, k: int = 5) -> Tuple[str, List[Source]]:
    """Run RAG retrieval and produce a grounded answer + sources."""
    hits = search(query, k=k, audience=persona)
    if not hits:
        # graceful fallback: search without audience filter
        hits = search(query, k=k)

    sources: List[Source] = []
    context_parts: List[str] = []
    seen_titles = set()
    for doc, score in hits:
        title = doc.metadata.get("title", "Untitled")
        context_parts.append(f"[{title}]\n{doc.page_content}")
        if title not in seen_titles:
            sources.append(Source(
                type="kba",
                title=title,
                snippet=doc.page_content[:160] + ("..." if len(doc.page_content) > 160 else ""),
            ))
            seen_titles.add(title)

    context = "\n\n---\n\n".join(context_parts) if context_parts else "(no relevant articles found)"

    from langchain_core.messages import SystemMessage, HumanMessage
    llm = get_chat_llm()
    prompt = RAG_SYSTEM_TEMPLATE.format(persona=persona, context=context)
    resp = await llm.ainvoke([SystemMessage(content=prompt), HumanMessage(content=query)])
    text = resp.content if isinstance(resp.content, str) else str(resp.content)
    return text, sources
