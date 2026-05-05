"""Temporary HTTP seed endpoints. Remove after first deploy."""
import os, sys, json, asyncio
from pathlib import Path
from fastapi import APIRouter, HTTPException, Header

router = APIRouter()
SEED_TOKEN = os.getenv("SEED_TOKEN", "")

def _check(token):
    if not SEED_TOKEN:
        raise HTTPException(500, "SEED_TOKEN not configured")
    if token != SEED_TOKEN:
        raise HTTPException(401, "Invalid token")

# Ensure scripts/ is importable
SCRIPTS = Path(__file__).resolve().parent.parent.parent / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS.parent))


@router.post("/seed/db")
async def seed_db(x_seed_token: str | None = Header(default=None)):
    _check(x_seed_token)
    import importlib.util
    spec = importlib.util.spec_from_file_location("seed_db", SCRIPTS / "seed_db.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    await mod.main()
    return {"ok": True, "msg": "Database seeded"}


@router.post("/seed/kb-generate")
async def kb_generate(x_seed_token: str | None = Header(default=None)):
    _check(x_seed_token)
    import importlib.util
    spec = importlib.util.spec_from_file_location("gen_kb", SCRIPTS / "generate_kb_rbac.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.main()
    return {"ok": True, "msg": "KB generated"}


@router.post("/seed/kb-ingest")
async def kb_ingest(x_seed_token: str | None = Header(default=None)):
    _check(x_seed_token)
    from app.core.rag import ingest_articles, reset_collection, collection_size
    from app.models.schemas import KBArticle
    kb_file = Path(__file__).resolve().parent.parent / "data" / "kb_articles.json"
    raw = json.loads(kb_file.read_text())
    articles = [KBArticle(**a) for a in raw]
    reset_collection()
    total = 0
    for i in range(0, len(articles), 64):
        n = ingest_articles(articles[i:i+64])
        total += n
    return {"ok": True, "msg": f"Ingested {total} chunks", "size": collection_size()}
