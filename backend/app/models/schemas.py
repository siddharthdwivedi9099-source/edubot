"""Pydantic schemas for API requests and responses."""
from datetime import datetime
from typing import List, Literal, Optional
from pydantic import BaseModel, Field

Persona = Literal["student", "teacher", "parent", "admin"]
Role = Literal["user", "assistant", "system"]


class ChatMessage(BaseModel):
    role: Role
    content: str


class ChatRequest(BaseModel):
    persona: Persona = "student"
    user_id: Optional[str] = Field(None, description="ERP user ID for personalized data")
    messages: List[ChatMessage]
    use_rag: bool = True
    use_erp: bool = True
    use_web: bool = False
    session_id: Optional[str] = None


class Source(BaseModel):
    type: Literal["kba", "erp", "web", "system"]
    title: str
    snippet: Optional[str] = None
    url: Optional[str] = None


class ChatResponse(BaseModel):
    content: str
    agent: str
    sources: List[Source] = []
    blocked: bool = False
    block_reason: Optional[str] = None
    latency_ms: int = 0


class KBArticle(BaseModel):
    id: str
    title: str
    category: str
    content: str
    tags: List[str] = []
    audience: List[Persona] = ["student", "teacher", "parent", "admin"]
    icon: Optional[str] = "📄"
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class KBSearchRequest(BaseModel):
    query: str
    k: int = 5
    category: Optional[str] = None
    audience: Optional[Persona] = None


class KBIngestRequest(BaseModel):
    articles: List[KBArticle]


class ERPQueryRequest(BaseModel):
    query: str = Field(..., description="Natural-language question about school data")
    persona: Persona = "admin"
    user_id: Optional[str] = None


class ERPQueryResponse(BaseModel):
    sql: str
    rows: List[dict]
    summary: str
    blocked: bool = False
    block_reason: Optional[str] = None


class WhatsAppInbound(BaseModel):
    """Subset of Twilio webhook fields we use."""
    From: str
    To: str
    Body: str
    MessageSid: str


class HealthResponse(BaseModel):
    status: str
    llm_provider: str
    vector_store: str
    erp_connected: bool
    kb_count: int
