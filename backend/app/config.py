"""
EduBot — Application configuration.
All settings are loaded from environment variables (or `.env` file).
"""
from functools import lru_cache
from typing import List, Literal
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # App
    app_name: str = "EduBot"
    app_env: Literal["development", "production"] = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    app_secret_key: str = "change-me"
    allowed_origins: str = "http://localhost:5173,http://localhost:3000"

    # LLM
    llm_provider: Literal["ollama", "openai", "anthropic"] = "ollama"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1:8b"
    ollama_embed_model: str = "nomic-embed-text"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    openai_embed_model: str = "text-embedding-3-small"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-5"

    # Vector store
    vector_store: Literal["chroma", "pgvector"] = "chroma"
    chroma_persist_dir: str = "./data/chroma"

    # ERP
    erp_db_url: str = "sqlite+aiosqlite:///./data/demo_school.db"
    erp_read_only: bool = True
    erp_allowed_tables: str = ""        # comma-separated allowlist; empty = all
    erp_max_rows: int = 100
    erp_query_timeout: int = 15

    # WhatsApp
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_whatsapp_from: str = "whatsapp:+14155238886"

    # Rate limiting
    rate_limit_per_minute: int = 30

    # Guardrails
    enable_pii_redaction: bool = True
    enable_profanity_filter: bool = True
    enable_off_topic_filter: bool = True
    max_input_tokens: int = 2000
    max_output_tokens: int = 1000
    max_input_chars: int = 4000

    @property
    def cors_origins(self) -> List[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    @property
    def erp_allowed_tables_list(self) -> List[str]:
        return [t.strip() for t in self.erp_allowed_tables.split(",") if t.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
