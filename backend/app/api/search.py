from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import text
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.schemas import SearchHit, SearchRequest, SearchResponse
from app.db import get_session

router = APIRouter(prefix="/search", tags=["search"])


@router.post("", response_model=SearchResponse)
async def search(
    request: Request,
    body: SearchRequest,
    session: AsyncSession = Depends(get_session),
) -> SearchResponse:
    embedding_provider = request.app.state.embedding_provider
    if not body.query.strip():
        raise HTTPException(status_code=422, detail="Query must not be empty")

    limit = max(1, min(body.limit, 100))

    vectors = await embedding_provider.embed([body.query])
    query_vec = vectors[0]
    vec_str = "[" + ",".join(str(v) for v in query_vec) + "]"

    filters = ["c.embedding IS NOT NULL", "d.deleted_at IS NULL"]
    params: dict = {"vec": vec_str, "limit": limit}

    if body.document_ids:
        placeholders = ", ".join(f":doc_id_{i}" for i in range(len(body.document_ids)))
        filters.append(f"c.document_id IN ({placeholders})")
        for i, did in enumerate(body.document_ids):
            params[f"doc_id_{i}"] = str(did)
    if body.file_category:
        filters.append("d.file_category = :file_category")
        params["file_category"] = body.file_category

    where = " AND ".join(filters)
    sql = text(f"""
        SELECT
            c.id AS chunk_id,
            c.document_id,
            d.filename,
            c.chunk_index,
            c.text,
            1 - (c.embedding <=> CAST(:vec AS vector)) AS score,
            c.token_count
        FROM chunks c
        JOIN documents d ON d.id = c.document_id
        WHERE {where}
        ORDER BY c.embedding <=> CAST(:vec AS vector)
        LIMIT :limit
    """)

    result = await session.execute(sql, params)
    rows = result.all()

    hits = [
        SearchHit(
            chunk_id=row.chunk_id,
            document_id=row.document_id,
            filename=row.filename,
            chunk_index=row.chunk_index,
            text=row.text,
            score=float(row.score),
            token_count=row.token_count,
        )
        for row in rows
    ]
    return SearchResponse(
        hits=hits,
        query=body.query,
        embedding_model=embedding_provider.identifier,
    )
