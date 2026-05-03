"""/erp endpoints — natural-language query over the school SQL database."""
from fastapi import APIRouter, HTTPException
from loguru import logger

from app.core.erp_connector import answer_with_erp, get_schema_text, is_erp_connected
from app.core.guardrails import check_input
from app.models.schemas import ERPQueryRequest, ERPQueryResponse

router = APIRouter()


@router.get("/health")
async def health() -> dict:
    return {"connected": await is_erp_connected()}


@router.get("/schema")
async def schema() -> dict:
    return {"schema": await get_schema_text()}


@router.post("/query", response_model=ERPQueryResponse)
async def query(req: ERPQueryRequest) -> ERPQueryResponse:
    g = check_input(req.query, req.persona)
    if not g.ok:
        return ERPQueryResponse(
            sql="", rows=[], summary=g.reason or "blocked",
            blocked=True, block_reason=g.reason,
        )
    try:
        sql, summary, rows, block = await answer_with_erp(
            req.query, req.persona, req.user_id
        )
    except Exception as e:
        logger.exception("ERP query failed")
        raise HTTPException(500, f"ERP query failed: {e}")

    return ERPQueryResponse(
        sql=sql, rows=rows, summary=summary,
        blocked=bool(block), block_reason=block,
    )
