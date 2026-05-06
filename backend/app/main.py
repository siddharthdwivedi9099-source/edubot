"""
EduBot — FastAPI entry point.

Run locally:        uvicorn app.main:app --reload
Run in production:  uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from loguru import logger

from app.config import get_settings
from app.api import auth, admin_seed, chat, kb, erp, whatsapp
from app.core.erp_connector import is_erp_connected
from app.core.rag import collection_size
from app.models.schemas import HealthResponse


limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI):
    s = get_settings()
    logger.info(f"🎓 {s.app_name} starting in {s.app_env} mode")
    logger.info(f"   LLM:    {s.llm_provider}")
    logger.info(f"   Vector: {s.vector_store} @ {s.chroma_persist_dir}")
    logger.info(f"   ERP:    {s.erp_db_url.split('@')[-1]} (read_only={s.erp_read_only})")
    yield
    logger.info(f"👋 {s.app_name} shutting down")


def create_app() -> FastAPI:
    s = get_settings()
    app = FastAPI(
        title=f"{s.app_name} API",
        description="School AI Assistant — RAG + ERP + Agentic chatbot",
        version="1.0.0",
        lifespan=lifespan,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=s.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Rate limiter
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # Routers
    app.include_router(chat.router, prefix="/chat", tags=["chat"])
    app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(admin_seed.router, prefix="/admin", tags=["admin"])
    app.include_router(kb.router, prefix="/kb", tags=["knowledge-base"])
    app.include_router(erp.router, prefix="/erp", tags=["erp"])
    app.include_router(whatsapp.router, prefix="/whatsapp", tags=["whatsapp"])

    @app.get("/", tags=["meta"])
    async def root():
        return {
            "name": s.app_name,
            "status": "ok",
            "docs": "/docs",
            "version": "1.0.0",
        }

    @app.get("/health", response_model=HealthResponse, tags=["meta"])
    async def health():
        return HealthResponse(
            status="ok",
            llm_provider=s.llm_provider,
            vector_store=s.vector_store,
            erp_connected=await is_erp_connected(),
            kb_count=collection_size(),
        )

    @app.exception_handler(Exception)
    async def unhandled(request: Request, exc: Exception):
        logger.exception(f"Unhandled exception on {request.url}")
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error", "error": str(exc)},
        )

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn
    s = get_settings()
    uvicorn.run("app.main:app", host=s.app_host, port=s.app_port, reload=(s.app_env == "development"))
