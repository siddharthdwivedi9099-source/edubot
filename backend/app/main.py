"""EduBot FastAPI app."""
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger

from app.config import get_settings
from app.api import auth, chat, kb, erp, whatsapp, admin_seed


@asynccontextmanager
async def lifespan(app: FastAPI):
    s = get_settings()
    logger.info(f"EduBot starting in {s.app_env} mode")
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
