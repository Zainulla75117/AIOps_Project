"""Admin API routes for document management and authentication.

All document routes are protected by the admin JWT token.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status, BackgroundTasks

from kubernetes_agent.api.auth import (
    create_access_token,
    verify_admin_token,
    verify_password,
)
from kubernetes_agent.config import AgentConfig, get_config
from kubernetes_agent.rag import ingestor, vector_store
from kubernetes_agent.rag.ingestor import SUPPORTED_EXTENSIONS
from kubernetes_agent.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/admin", tags=["Admin"])


# ---- Authentication ----

class _LoginRequest:
    """Manually parse login request to avoid circular import issues."""
    pass


@router.post("/login")
async def admin_login(
    body: dict,
    cfg: AgentConfig = Depends(lambda: get_config()),
):
    """Authenticate with the admin password and receive a JWT token."""
    password = body.get("password", "")

    if not cfg.admin_password_hash:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Admin authentication is not configured. Set AIOPS_ADMIN_PASSWORD_HASH in .env",
        )

    if not verify_password(password, cfg.admin_password_hash):
        logger.warning("admin_login_failed")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid password",
        )

    token = create_access_token(cfg)
    logger.info("admin_login_success")
    return {"token": token}


# ---- Document Management (Protected) ----

@router.post("/documents/upload", dependencies=[Depends(verify_admin_token)], status_code=status.HTTP_202_ACCEPTED)
async def upload_document(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    """Upload and schedule a document for RAG ingestion in the background."""
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No filename provided",
        )

    import os
    import tempfile
    import shutil
    
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type: {ext}. Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}",
        )

    # Save to a temporary file on disk so the background task can process it
    # without running out of memory and after the request closes.
    fd, temp_path = tempfile.mkstemp(suffix=ext)
    try:
        with os.fdopen(fd, 'wb') as f:
            shutil.copyfileobj(file.file, f)
    except Exception as exc:
        os.unlink(temp_path)
        logger.error("file_save_failed", error=str(exc))
        raise HTTPException(status_code=500, detail="Failed to save uploaded file")
        
    logger.info("document_upload_accepted", filename=file.filename, temp_path=temp_path)
    
    # Delegate to the ingestor background task
    background_tasks.add_task(ingestor.ingest_file_background, temp_path, file.filename)
    
    return {
        "source": file.filename,
        "chunks_created": 0,
        "message": f"Processing of {file.filename} started in background.",
    }


@router.get("/documents", dependencies=[Depends(verify_admin_token)])
async def list_documents():
    """List all documents in the RAG vector store."""
    try:
        sources = vector_store.list_sources()
        return {"documents": sources}
    except Exception as exc:
        logger.error("document_list_failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )


@router.delete("/documents/{source}", dependencies=[Depends(verify_admin_token)])
async def delete_document(source: str):
    """Delete a document and all its chunks from the vector store."""
    try:
        count = vector_store.delete_by_source(source)
        if count == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No document found with source: {source}",
            )
        logger.info("document_deleted", source=source, chunks_deleted=count)
        return {"source": source, "chunks_deleted": count}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("document_delete_failed", source=source, error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )


@router.get("/documents/{source}/chunks", dependencies=[Depends(verify_admin_token)])
async def get_document_chunks(source: str):
    """Preview chunks for a specific document."""
    try:
        chunks = vector_store.get_chunk_previews(source)
        if not chunks:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No chunks found for source: {source}",
            )
        return {"source": source, "chunks": chunks, "total": len(chunks)}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("chunk_preview_failed", source=source, error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )
