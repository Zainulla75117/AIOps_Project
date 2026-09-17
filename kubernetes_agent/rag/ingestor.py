"""Document ingestor for the RAG pipeline.

Handles loading, chunking, and inserting documents into ChromaDB.
Supports PDF, TXT, MD, CSV, and SQLite (.db) files.
"""

from __future__ import annotations

import csv
import io
import sqlite3
import tempfile
from pathlib import Path
from typing import BinaryIO

from langchain_core.documents import Document
from langchain_text_splitters import CharacterTextSplitter

from kubernetes_agent.config import AgentConfig, get_config
from kubernetes_agent.rag import vector_store
from kubernetes_agent.utils.logging import get_logger

logger = get_logger(__name__)

# Supported file extensions
SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".md", ".csv", ".db"}


def _get_splitter(cfg: AgentConfig) -> CharacterTextSplitter:
    """Create the configured text splitter."""
    return CharacterTextSplitter(
        separator="\n",
        chunk_size=cfg.rag_chunk_size,
        chunk_overlap=cfg.rag_chunk_overlap,
        length_function=len,
    )


def _load_pdf(file_bytes: bytes, source_name: str) -> list[Document]:
    """Load a PDF file and return raw Document objects."""
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(file_bytes))
    docs = []
    for i, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        if text.strip():
            docs.append(Document(
                page_content=text,
                metadata={"source": source_name, "page": i + 1},
            ))
    return docs


def _load_text(file_bytes: bytes, source_name: str) -> list[Document]:
    """Load a plain text or markdown file."""
    text = file_bytes.decode("utf-8", errors="replace")
    if not text.strip():
        return []
    return [Document(page_content=text, metadata={"source": source_name})]


def _load_csv(file_bytes: bytes, source_name: str) -> list[Document]:
    """Load a CSV file, converting each row to a text representation."""
    text = file_bytes.decode("utf-8", errors="replace")
    reader = csv.DictReader(io.StringIO(text))

    docs = []
    for row in reader:
        row_text = "\n".join(f"{k}: {v}" for k, v in row.items() if v)
        if row_text.strip():
            docs.append(Document(
                page_content=row_text,
                metadata={"source": source_name},
            ))
    return docs


def _load_sqlite(file_bytes: bytes, source_name: str) -> list[Document]:
    """Load a SQLite database, reading all tables."""
    docs = []

    # Write to a temp file since sqlite3 requires a file path
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        tmp.write(file_bytes)
        tmp_path = tmp.name

    try:
        conn = sqlite3.connect(tmp_path)
        cursor = conn.cursor()

        # Get all table names
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cursor.fetchall()]

        for table_name in tables:
            try:
                cursor.execute(f"SELECT * FROM [{table_name}]")  # noqa: S608
                columns = [desc[0] for desc in cursor.description]
                rows = cursor.fetchall()

                for row in rows:
                    row_text = "\n".join(
                        f"{col}: {val}" for col, val in zip(columns, row) if val is not None
                    )
                    if row_text.strip():
                        docs.append(Document(
                            page_content=row_text,
                            metadata={"source": source_name, "table": table_name},
                        ))
            except Exception as exc:
                logger.warning("sqlite_table_read_failed", table=table_name, error=str(exc))

        conn.close()
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    return docs


def ingest_file(
    file_bytes: bytes,
    filename: str,
    cfg: AgentConfig | None = None,
) -> dict[str, int]:
    """Ingest a file into the RAG vector store.

    Args:
        file_bytes: Raw file content.
        filename: Original filename (used for source metadata and type detection).
        cfg: Optional config override.

    Returns:
        Dict with ``chunks_created`` count.

    Raises:
        ValueError: If the file type is unsupported.
    """
    cfg = cfg or get_config()
    ext = Path(filename).suffix.lower()

    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"Unsupported file type: {ext}. "
            f"Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )

    logger.info("ingesting_document", filename=filename, extension=ext)

    # 1. Load raw documents
    if ext == ".pdf":
        raw_docs = _load_pdf(file_bytes, filename)
    elif ext in (".txt", ".md"):
        raw_docs = _load_text(file_bytes, filename)
    elif ext == ".csv":
        raw_docs = _load_csv(file_bytes, filename)
    elif ext == ".db":
        raw_docs = _load_sqlite(file_bytes, filename)
    else:
        raise ValueError(f"Unsupported file type: {ext}")

    if not raw_docs:
        logger.warning("no_content_extracted", filename=filename)
        return {"chunks_created": 0}

    # 2. Chunk the documents
    splitter = _get_splitter(cfg)
    chunks = splitter.split_documents(raw_docs)

    # Ensure all chunks have the source metadata
    for chunk in chunks:
        chunk.metadata.setdefault("source", filename)

    logger.info(
        "document_chunked",
        filename=filename,
        raw_docs=len(raw_docs),
        chunks=len(chunks),
    )

    # 3. Add to vector store
    vector_store.add_documents(chunks, cfg)

    return {"chunks_created": len(chunks)}


async def ingest_file_background(
    file_path: str,
    filename: str,
    job_id: str,
    cfg: AgentConfig | None = None,
):
    """Background task to ingest a file with progress tracking via MongoDB.

    Args:
        file_path: Temporary path to the saved file on disk.
        filename: Original filename for source metadata.
        job_id: Ingestion job ID for progress tracking.
        cfg: Optional config override.
    """
    cfg = cfg or get_config()
    ext = Path(filename).suffix.lower()

    logger.info("starting_background_ingestion", filename=filename, job_id=job_id)

    # Get the MongoDB database for progress updates
    from kubernetes_agent.api.dependencies import get_mongo
    from kubernetes_agent.database import ingestion_progress as ingestion_progress

    try:
        mongo = get_mongo()
        db = mongo.db if mongo else None
    except RuntimeError:
        db = None

    try:
        # Currently, only .db supports streaming batch processing.
        # Other files fall back to reading bytes directly.
        if ext == ".db":
            splitter = _get_splitter(cfg)
            total_chunks = 0

            # Count total rows first for accurate progress
            total_rows = _count_sqlite_rows(file_path)
            if db is not None:
                await ingestion_progress.update_progress(
                    db, job_id, total_rows=total_rows
                )

            processed_rows = 0

            # Stream documents in batches from the database
            for batch_docs, table_name in _stream_sqlite_with_table(file_path, filename, batch_size=2000):
                if not batch_docs:
                    continue

                # Update current table
                if db is not None:
                    await ingestion_progress.update_progress(
                        db, job_id, current_table=table_name
                    )

                # Split this specific batch
                chunks = splitter.split_documents(batch_docs)
                for chunk in chunks:
                    chunk.metadata.setdefault("source", filename)

                # Add to vector store
                if chunks:
                    vector_store.add_documents(chunks, cfg)
                    total_chunks += len(chunks)

                # Update progress
                processed_rows += len(batch_docs)
                if db is not None:
                    await ingestion_progress.update_progress(
                        db, job_id,
                        processed_rows=processed_rows,
                        chunks_created=total_chunks,
                    )

                logger.debug(
                    "inserted_chunk_batch",
                    filename=filename,
                    batch_chunks=len(chunks),
                    processed_rows=processed_rows,
                    total_rows=total_rows,
                )

            # Mark completed
            if db is not None:
                await ingestion_progress.mark_completed(db, job_id, total_chunks)

            logger.info("background_ingestion_complete", filename=filename, total_chunks=total_chunks)

        else:
            # For non-DB files, fall back to standard in-memory ingestion
            with open(file_path, 'rb') as f:
                file_bytes = f.read()
            result = ingest_file(file_bytes, filename, cfg)

            # Mark completed
            if db is not None:
                await ingestion_progress.mark_completed(db, job_id, result["chunks_created"])

            logger.info("background_ingestion_complete", filename=filename, total_chunks=result["chunks_created"])

    except Exception as exc:
        logger.error("background_ingestion_failed", filename=filename, error=str(exc))
        if db is not None:
            await ingestion_progress.mark_failed(db, job_id, str(exc))
    finally:
        # Always clean up the temporary file
        Path(file_path).unlink(missing_ok=True)
        logger.debug("cleaned_up_temp_file", path=file_path)


def _count_sqlite_rows(file_path: str) -> int:
    """Count total rows across all tables in a SQLite database."""
    total = 0
    try:
        conn = sqlite3.connect(file_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cursor.fetchall()]

        for table_name in tables:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM [{table_name}]")  # noqa: S608
                total += cursor.fetchone()[0]
            except Exception:
                pass

        conn.close()
    except Exception as exc:
        logger.warning("sqlite_row_count_failed", error=str(exc))
    return total


def _stream_sqlite_with_table(file_path: str, source_name: str, batch_size: int = 1000):
    """Generator that yields (batch_docs, table_name) tuples from a SQLite database."""
    try:
        conn = sqlite3.connect(file_path)
        cursor = conn.cursor()

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cursor.fetchall()]

        for table_name in tables:
            try:
                # Use a separate cursor for querying the table
                table_cursor = conn.cursor()
                table_cursor.execute(f"SELECT * FROM [{table_name}]")  # noqa: S608
                columns = [desc[0] for desc in table_cursor.description]

                while True:
                    rows = table_cursor.fetchmany(batch_size)
                    if not rows:
                        break

                    batch_docs = []
                    for row in rows:
                        row_text = "\n".join(
                            f"{col}: {val}" for col, val in zip(columns, row) if val is not None
                        )
                        if row_text.strip():
                            batch_docs.append(Document(
                                page_content=row_text,
                                metadata={"source": source_name, "table": table_name},
                            ))

                    if batch_docs:
                        yield (batch_docs, table_name)

            except Exception as exc:
                logger.warning("sqlite_table_stream_failed", table=table_name, error=str(exc))

        conn.close()
    except Exception as exc:
        logger.error("sqlite_stream_failed", error=str(exc))


# Keep the old generator for backward compatibility
def _stream_sqlite(file_path: str, source_name: str, batch_size: int = 1000):
    """Generator that yields batches of Documents from a SQLite database without loading everything into RAM."""
    for batch_docs, _ in _stream_sqlite_with_table(file_path, source_name, batch_size):
        yield batch_docs
