"""EduBot FastAPI app with auto-seed on startup."""
import asyncio
import json
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger
from sqlalchemy import text

from app.config import get_settings
from app.api import auth, chat, kb, erp, whatsapp, admin_seed


async def auto_seed():
    """If the users table is missing, run the full seed pipeline."""
    try:
        from app.core.erp_connector import get_engine
        eng = get_engine()
        async with eng.connect() as conn:
            try:
                await conn.execute(text("SELECT 1 FROM users LIMIT 1"))
                logger.info("Database already seeded.")
                seeded = True
            except Exception:
                seeded = False

        if not seeded:
            logger.warning("Users table missing — running auto-seed...")
            scripts = Path(__file__).resolve().parent.parent / "scripts"
            sys.path.insert(0, str(scripts.parent))
            import importlib.util
            spec = importlib.util.spec_from_file_location("seed_db", scripts / "seed_db.py")
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            await mod.main()
            logger.info("Auto-seed complete.")
    except Exception as e:
        logger.exception(f"Auto-seed failed: {e}")

    # Auto-ingest KB if empty
    try:
        from app.core.rag import collection_size, ingest_articles, reset_collection
        from app.models.schemas import KBArticle
        if collection_size() == 0:
            logger.warning("KB empty — running auto-ingest...")
            kb_file = Path(__file__).resolve().parent / "data" / "kb_articles.json"
            if kb_file.exists():
                raw = json.loads(kb_file.read_text())
                articles = [KBArticle(**a) for a in raw]
                reset_collection()
                for i in range(0, len(articles), 64):
                    ingest_articles(articles[i:i+64])
                logger.info(f"Auto-ingest complete: {collection_size()} chunks")
    except Exception as e:
        logger.exception(f"Auto-ingest failed: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    s = get_settings()
    logger.info(f"EduBot starting in {s.app_env} mode")
    if os.getenv("AUTO_SEED", "true").lower() == "true":
        await auto_seed()
    yield
    logger.info("EduBot shutting down")


settings = get_settings()
app = FastAPI(title="EduBot", version="2.0", lifespan=lifespan)

origins = [o.strip() for o in settings.allowed_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception):
    logger.exception(f"Error on {request.url}")
    return JSONResponse(status_code=500, content={"detail": "Internal server error", "error": str(exc)})


@app.get("/")
async def root():
    return {"app": "EduBot", "version": "2.0"}


@app.get("/health")
async def health():
    from app.core.erp_connector import is_erp_connected
    from app.core.rag import collection_size
    erp_ok = await is_erp_connected()
    return {
        "status": "ok",
        "llm_provider": settings.llm_provider,
        "vector_store": settings.vector_store,
        "erp_connected": erp_ok,
        "kb_count": collection_size(),
    }


app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(admin_seed.router, prefix="/admin", tags=["admin"])
app.include_router(chat.router, prefix="/chat", tags=["chat"])
app.include_router(kb.router, prefix="/kb", tags=["knowledge-base"])
app.include_router(erp.router, prefix="/erp", tags=["erp"])
app.include_router(whatsapp.router, prefix="/whatsapp", tags=["whatsapp"])
