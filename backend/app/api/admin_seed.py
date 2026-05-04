"""
TEMPORARY admin endpoints for one-time seeding on platforms without shell access.
Protected by SEED_TOKEN env var. Remove this file after first deploy.
"""
import asyncio
import os
import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException, Header

router = APIRouter()

SEED_TOKEN = os.getenv("SEED_TOKEN", "")


def _check(token: str | None) -> None:
    if not SEED_TOKEN:
        raise HTTPException(500, "SEED_TOKEN not configured on server")
    if token != SEED_TOKEN:
        raise HTTPException(401, "Invalid seed token")


@router.post("/seed/db")
async def seed_db(x_seed_token: str | None = Header(default=None)):
    _check(x_seed_token)
    # Run seed_db.py inline
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
    from scripts.seed_db import main as seed_main
    await seed_main()
    return {"ok": True, "msg": "Database seeded"}


@router.post("/seed/kb-generate")
async def kb_generate(x_seed_token: str | None = Header(default=None)):
    _check(x_seed_token)
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
    from scripts.generate_kb_rbac import main as gen_main
    gen_main()
    return {"ok": True, "msg": "KB articles generated"}


@router.post("/seed/kb-ingest")
async def kb_ingest(x_seed_token: str | None = Header(default=None)):
    _check(x_seed_token)
    import json
    from app.core.rag import ingest_articles, reset_collection, collection_size
    from app.models.schemas import KBArticle

    kb_file = Path(__file__).resolve().parent.parent / "data" / "kb_articles.json"
    raw = json.loads(kb_file.read_text())
    articles = [KBArticle(**a) for a in raw]
    reset_collection()
    total = 0
    for i in range(0, len(articles), 64):
        chunk = articles[i:i + 64]
        n = ingest_articles(chunk)
        total += n
    return {"ok": True, "msg": f"Ingested {total} chunks from {len(articles)} articles",
            "collection_size": collection_size()}
