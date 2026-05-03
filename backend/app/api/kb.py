"""/kb endpoints — search and ingestion."""
from fastapi import APIRouter, HTTPException
from loguru import logger

from app.core.rag import search, ingest_articles, collection_size
from app.models.schemas import KBSearchRequest, KBIngestRequest

router = APIRouter()


@router.get("/count")
async def count() -> dict:
    return {"count": collection_size()}


@router.post("/search")
async def kb_search(req: KBSearchRequest) -> dict:
    hits = search(req.query, k=req.k, audience=req.audience, category=req.category)
    return {
        "results": [
            {
                "title": doc.metadata.get("title"),
                "category": doc.metadata.get("category"),
                "snippet": doc.page_content[:300],
                "score": float(score),
            }
            for doc, score in hits
        ]
    }


@router.post("/ingest")
async def kb_ingest(req: KBIngestRequest) -> dict:
    if not req.articles:
        raise HTTPException(400, "No articles provided.")
    n = ingest_articles(req.articles)
    return {"chunks_added": n, "articles": len(req.articles)}
