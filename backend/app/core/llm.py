"""
Multi-LLM abstraction.

Supports Ollama (local), OpenAI, and Anthropic interchangeably.
The choice is driven by `LLM_PROVIDER` in `.env`. Adding a new provider
only requires adding a branch in `get_chat_llm` / `get_embeddings`.
"""
from functools import lru_cache
from typing import List
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.embeddings import Embeddings
from loguru import logger

from app.config import get_settings


@lru_cache
def get_chat_llm() -> BaseChatModel:
    s = get_settings()
    logger.info(f"Initializing chat LLM: provider={s.llm_provider}")

    if s.llm_provider == "ollama":
        from langchain_ollama import ChatOllama
        return ChatOllama(
            base_url=s.ollama_base_url,
            model=s.ollama_model,
            temperature=0.3,
            num_predict=s.max_output_tokens,
        )
    if s.llm_provider == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            api_key=s.openai_api_key,
            model=s.openai_model,
            temperature=0.3,
            max_tokens=s.max_output_tokens,
        )
    if s.llm_provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            api_key=s.anthropic_api_key,
            model=s.anthropic_model,
            temperature=0.3,
            max_tokens=s.max_output_tokens,
        )
    raise ValueError(f"Unknown LLM provider: {s.llm_provider}")


@lru_cache
def get_embeddings() -> Embeddings:
    s = get_settings()
    logger.info(f"Initializing embeddings: provider={s.llm_provider}")

    if s.llm_provider == "ollama":
        from langchain_ollama import OllamaEmbeddings
        return OllamaEmbeddings(
            base_url=s.ollama_base_url,
            model=s.ollama_embed_model,
        )
    if s.llm_provider == "openai":
        from langchain_openai import OpenAIEmbeddings
        return OpenAIEmbeddings(
            api_key=s.openai_api_key,
            model=s.openai_embed_model,
        )
    # Anthropic doesn't ship its own embeddings — fall back to a local
    # SentenceTransformer model for self-hosted parity.
    from langchain_community.embeddings import HuggingFaceEmbeddings
    return HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")


async def llm_complete(system: str, user: str) -> str:
    """Lightweight one-shot completion helper used outside the RAG chain."""
    from langchain_core.messages import SystemMessage, HumanMessage
    llm = get_chat_llm()
    resp = await llm.ainvoke([SystemMessage(content=system), HumanMessage(content=user)])
    return resp.content if isinstance(resp.content, str) else str(resp.content)
