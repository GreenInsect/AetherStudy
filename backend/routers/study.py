"""学科资料库、RAG 出题与历史题库路由"""

import json
import html
import hashlib
import os
import re
import math
import shutil
import traceback
import uuid
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import quote
from xml.etree import ElementTree

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, Field

from database.db import get_db
from models.user import UserInDB
from services.auth_service import get_current_admin, get_current_user
from services.llm_settings import LLMSettings, complete_llm_json, get_user_llm_settings

router = APIRouter()

MAX_UPLOAD_BYTES = 12 * 1024 * 1024
SUPPORTED_EXTENSIONS = {".md", ".markdown", ".txt", ".pdf"}
WEB_TIMEOUT_SECONDS = float(os.getenv("AETHERSTUDY_WEB_TIMEOUT", "15"))
WEB_PROXY = os.getenv("AETHERSTUDY_WEB_PROXY") or os.getenv("HTTPS_PROXY") or os.getenv("HTTP_PROXY")
UPLOAD_ROOT = Path(os.getenv("AETHERSTUDY_UPLOAD_DIR") or Path(__file__).resolve().parents[1] / "storage" / "study_uploads")
ADMIN_KB_ROOT = Path(os.getenv("AETHERSTUDY_ADMIN_KB_DIR") or Path(__file__).resolve().parents[1] / "storage" / "admin_knowledge")
DEEP_RAG_ENABLED = os.getenv("AETHERSTUDY_DEEP_RAG_ENABLED", "1").lower() not in {"0", "false", "no", "off"}
DEEP_RAG_EMBEDDING_PROVIDER = "dashscope"
DEEP_RAG_EMBEDDING_MODEL = os.getenv("AETHERSTUDY_EMBEDDING_MODEL", "text-embedding-v4")
DEEP_RAG_EMBEDDING_BASE_URL = (
    os.getenv("DASHSCOPE_BASE_URL")
    or os.getenv("AETHERSTUDY_EMBEDDING_BASE_URL")
    or "https://dashscope.aliyuncs.com/compatible-mode/v1"
)
DEEP_RAG_EMBEDDING_DIMENSIONS = int(os.getenv("AETHERSTUDY_EMBEDDING_DIMENSIONS", "1024"))
DEEP_RAG_EMBEDDING_BATCH_SIZE = max(1, min(10, int(os.getenv("AETHERSTUDY_EMBEDDING_BATCH_SIZE", "10"))))
DEEP_RAG_TIMEOUT_SECONDS = float(os.getenv("AETHERSTUDY_EMBEDDING_TIMEOUT", "30"))
LIGHTWEIGHT_EMBEDDING_PROVIDER = "lightweight_hash"
LIGHTWEIGHT_EMBEDDING_MODEL = "local_hash_96"
ADMIN_KB_COMMON_SUBJECTS = {"通用", "general", "common", "global"}


def _debug(step: str, **data: Any) -> None:
    """统一打印 RAG 出题调试信息到后端终端。"""
    safe_data = json.dumps(data, ensure_ascii=False, default=str)
    if len(safe_data) > 4000:
        safe_data = safe_data[:4000] + "...<truncated>"
    print(f"[AetherStudy:RAG DEBUG] {step} | {safe_data}", flush=True)


def _debug_exception(step: str, exc: Exception, **data: Any) -> None:
    _debug(
        step,
        error_type=type(exc).__name__,
        error=str(exc),
        traceback=traceback.format_exc(limit=3),
        **data,
    )


class SubjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    description: str = Field("", max_length=500)


class QuizGenerateRequest(BaseModel):
    subject_id: str
    topic: str = Field(..., min_length=1, max_length=120)
    question_type: str = "single_choice"
    count: int = Field(5, ge=1, le=30)
    difficulty: str = "medium"


class QuizRenameRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=160)


class QuizMergeRequest(BaseModel):
    quiz_ids: List[str] = Field(default_factory=list)
    title: str = Field("", max_length=160)


class FrontendDebugLogRequest(BaseModel):
    step: str = Field(..., min_length=1, max_length=120)
    data: Dict[str, Any] = Field(default_factory=dict)


class AdminKnowledgeReindexRequest(BaseModel):
    force: bool = False


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _extension(filename: str) -> str:
    lower = filename.lower()
    for ext in SUPPORTED_EXTENSIONS:
        if lower.endswith(ext):
            return ext
    return ""


def _decode_text(data: bytes) -> str:
    for encoding in ("utf-8", "utf-8-sig", "gb18030", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="ignore")


def _extract_pdf_text(data: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="PDF 解析依赖未安装，请先安装 requirements.txt 中的 pypdf",
        ) from exc

    try:
        reader = PdfReader(BytesIO(data))
        pages = [page.extract_text() or "" for page in reader.pages]
        text = "\n\n".join(pages).strip()
        _debug("pdf_extract_done", page_count=len(reader.pages), text_chars=len(text))
    except Exception as exc:
        _debug_exception("pdf_extract_failed", exc, bytes=len(data))
        raise HTTPException(status_code=400, detail="PDF 解析失败，请确认文件未加密且可复制文本") from exc

    if not text:
        _debug("pdf_extract_empty", bytes=len(data))
        raise HTTPException(status_code=400, detail="未能从 PDF 提取文本，暂不支持扫描版 PDF OCR")
    return text


def _clean_text(text: str) -> str:
    text = re.sub(r"\r\n?", "\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _knowledge_text(text: str) -> str:
    """把上传资料中的 Markdown/URL 噪音转成适合出题的知识文本。"""
    text = re.sub(r"!\[([^\]]*)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"^\s{0,3}#{1,6}\s*", "", text, flags=re.M)
    text = re.sub(r"^\s*[-*+]\s+", "", text, flags=re.M)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    return _clean_text(text)


def _is_low_value_knowledge_text(text: str) -> bool:
    compact = re.sub(r"\s+", "", text)
    if len(compact) < 35:
        return True
    linkish_count = len(re.findall(r"https?://|\[[^\]]+\]\([^)]+\)", text))
    chinese_or_word_count = len(_tokens(text))
    if linkish_count >= 3 and chinese_or_word_count < 24:
        return True
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) >= 4:
        sentence_marks = len(re.findall(r"[。！？.!?]", text))
        short_title_lines = sum(1 for line in lines if len(line) <= 90)
        title_separators = sum(1 for line in lines if "|" in line or line.startswith(("图解", "ShowMeAI", "机器学习 |")))
        if sentence_marks <= 1 and short_title_lines / len(lines) >= 0.75 and title_separators >= 2:
            return True
    return False


def _split_chunks(text: str, max_chars: int = 1000) -> List[str]:
    blocks = [b.strip() for b in re.split(r"\n\s*\n", text) if b.strip()]
    chunks: List[str] = []
    current = ""
    for block in blocks:
        if len(current) + len(block) + 2 <= max_chars:
            current = f"{current}\n\n{block}".strip()
        else:
            if current:
                chunks.append(current)
            if len(block) > max_chars:
                chunks.extend(block[i:i + max_chars] for i in range(0, len(block), max_chars))
                current = ""
            else:
                current = block
    if current:
        chunks.append(current)
    return chunks or [text[:max_chars]]


def _tokens(text: str) -> List[str]:
    return [t.lower() for t in re.findall(r"[a-zA-Z0-9_]{2,}|[\u4e00-\u9fff]{2,}", text)]


def _safe_filename(filename: str) -> str:
    stem = re.sub(r"[^a-zA-Z0-9_.\-\u4e00-\u9fff]+", "_", filename or "document").strip("._")
    return stem[:120] or "document"


def _document_storage_dir(user_id: str, subject_id: str, document_id: str) -> Path:
    return UPLOAD_ROOT / user_id / subject_id / document_id


def _save_uploaded_file(user_id: str, subject_id: str, document_id: str, filename: str, data: bytes) -> tuple[str, str]:
    directory = _document_storage_dir(user_id, subject_id, document_id)
    directory.mkdir(parents=True, exist_ok=True)
    stored_filename = _safe_filename(filename)
    path = directory / stored_filename
    path.write_bytes(data)
    return str(path), stored_filename


def _delete_document_storage(path: str) -> None:
    if not path:
        return
    file_path = Path(path)
    try:
        if file_path.is_file():
            parent = file_path.parent
            file_path.unlink()
            if parent.exists() and parent != UPLOAD_ROOT:
                shutil.rmtree(parent, ignore_errors=True)
    except Exception as exc:
        _debug_exception("document_storage_delete_failed", exc, path=path)


def _file_content_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _extract_document_text(filename: str, data: bytes) -> tuple[str, str]:
    ext = _extension(filename)
    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"unsupported_file_extension: {filename}")
    text = _extract_pdf_text(data) if ext == ".pdf" else _decode_text(data)
    return ext, _clean_text(text)


def _iter_admin_knowledge_files() -> List[Path]:
    ADMIN_KB_ROOT.mkdir(parents=True, exist_ok=True)
    files: List[Path] = []
    for path in sorted(ADMIN_KB_ROOT.rglob("*")):
        if not path.is_file():
            continue
        try:
            rel_parts = path.relative_to(ADMIN_KB_ROOT).parts
        except ValueError:
            rel_parts = path.parts
        if any(part.startswith(".") for part in rel_parts):
            continue
        if _extension(path.name) in SUPPORTED_EXTENSIONS:
            files.append(path)
    return files


def _admin_subject_from_path(path: Path) -> str:
    try:
        rel = path.relative_to(ADMIN_KB_ROOT)
        return rel.parts[0] if len(rel.parts) > 1 else "通用"
    except ValueError:
        return "通用"


def _admin_subject_dir(subject_name: str) -> Path:
    safe_subject = _safe_filename(subject_name.strip() or "通用")
    return ADMIN_KB_ROOT / safe_subject


def _admin_storage_path(subject_name: str, filename: str) -> Path:
    directory = _admin_subject_dir(subject_name)
    directory.mkdir(parents=True, exist_ok=True)
    return directory / _safe_filename(filename)


def _delete_admin_document_storage(path: str) -> None:
    if not path:
        return
    file_path = Path(path)
    try:
        if file_path.is_file() and ADMIN_KB_ROOT.resolve() in file_path.resolve().parents:
            parent = file_path.parent
            file_path.unlink()
            while parent != ADMIN_KB_ROOT and parent.exists() and not any(parent.iterdir()):
                parent.rmdir()
                parent = parent.parent
    except Exception as exc:
        _debug_exception("admin_kb_storage_delete_failed", exc, path=path)


def _embedding_from_tokens(tokens: List[str], dimensions: int = 96) -> List[float]:
    vector = [0.0] * dimensions
    for token in tokens:
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        bucket = int.from_bytes(digest[:4], "big") % dimensions
        vector[bucket] += 1.0
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [round(value / norm, 6) for value in vector]


def _set_lightweight_embedding(chunk: Dict[str, Any]) -> None:
    embedding = _embedding_from_tokens(chunk.get("tokens") or _tokens(chunk.get("content") or ""))
    chunk["embedding"] = embedding
    chunk["embedding_provider"] = LIGHTWEIGHT_EMBEDDING_PROVIDER
    chunk["embedding_model"] = LIGHTWEIGHT_EMBEDDING_MODEL
    chunk["embedding_dim"] = len(embedding)


def _dashscope_api_key() -> str:
    return os.getenv("DASHSCOPE_API_KEY") or os.getenv("AETHERSTUDY_EMBEDDING_API_KEY") or ""


def _embedding_endpoint() -> str:
    return f"{DEEP_RAG_EMBEDDING_BASE_URL.rstrip('/')}/embeddings"


def _embedding_headers() -> Dict[str, str]:
    api_key = _dashscope_api_key()
    if not api_key:
        raise ValueError("missing_dashscope_api_key")
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }


async def _try_deep_embeddings(texts: List[str], purpose: str) -> Optional[List[List[float]]]:
    cleaned = [_knowledge_text(text)[:6000] for text in texts if _knowledge_text(text)]
    if not DEEP_RAG_ENABLED:
        _debug("deep_rag_embedding_skipped_disabled", purpose=purpose)
        return None
    if not cleaned:
        _debug("deep_rag_embedding_skipped_empty_text", purpose=purpose)
        return None

    _debug(
        "deep_rag_embedding_start",
        purpose=purpose,
        text_count=len(cleaned),
        provider=DEEP_RAG_EMBEDDING_PROVIDER,
        model=DEEP_RAG_EMBEDDING_MODEL,
        base_url=DEEP_RAG_EMBEDDING_BASE_URL,
        dimensions=DEEP_RAG_EMBEDDING_DIMENSIONS,
        batch_size=DEEP_RAG_EMBEDDING_BATCH_SIZE,
        timeout_seconds=DEEP_RAG_TIMEOUT_SECONDS,
        has_api_key=bool(_dashscope_api_key()),
    )
    try:
        vectors: List[List[float]] = []
        async with httpx.AsyncClient(timeout=DEEP_RAG_TIMEOUT_SECONDS, trust_env=True) as client:
            for start in range(0, len(cleaned), DEEP_RAG_EMBEDDING_BATCH_SIZE):
                batch = cleaned[start:start + DEEP_RAG_EMBEDDING_BATCH_SIZE]
                payload: Dict[str, Any] = {"model": DEEP_RAG_EMBEDDING_MODEL, "input": batch}
                if DEEP_RAG_EMBEDDING_DIMENSIONS > 0:
                    payload["dimensions"] = DEEP_RAG_EMBEDDING_DIMENSIONS
                response = await client.post(
                    _embedding_endpoint(),
                    headers=_embedding_headers(),
                    json=payload,
                )
                _debug(
                    "deep_rag_embedding_response",
                    purpose=purpose,
                    provider=DEEP_RAG_EMBEDDING_PROVIDER,
                    batch_start=start,
                    batch_size=len(batch),
                    status_code=response.status_code,
                    response_chars=len(response.text),
                    content_type=response.headers.get("content-type"),
                )
                if response.status_code >= 400:
                    raise ValueError(f"embedding_http_{response.status_code}: {response.text[:500]}")
                data = response.json()
                items = data.get("data") or []
                vectors_by_index: Dict[int, List[float]] = {}
                for item in items:
                    index = int(item.get("index", len(vectors_by_index)))
                    vector = item.get("embedding")
                    if isinstance(vector, list) and vector:
                        vectors_by_index[index] = [float(value) for value in vector]
                vectors.extend(vectors_by_index[index] for index in range(len(batch)) if index in vectors_by_index)
        if len(vectors) != len(cleaned):
            raise ValueError(f"embedding_count_mismatch: expected={len(cleaned)} actual={len(vectors)}")
        dims = sorted({len(vector) for vector in vectors})
        if len(dims) != 1:
            raise ValueError(f"embedding_dim_mismatch: dims={dims}")
        _debug(
            "deep_rag_embedding_done",
            purpose=purpose,
            provider=DEEP_RAG_EMBEDDING_PROVIDER,
            model=DEEP_RAG_EMBEDDING_MODEL,
            vector_count=len(vectors),
            embedding_dim=dims[0],
        )
        return vectors
    except Exception as exc:
        _debug_exception(
            "deep_rag_embedding_failed_fallback_lightweight",
            exc,
            purpose=purpose,
            provider=DEEP_RAG_EMBEDDING_PROVIDER,
            model=DEEP_RAG_EMBEDDING_MODEL,
            base_url=DEEP_RAG_EMBEDDING_BASE_URL,
            text_count=len(cleaned),
        )
        return None


async def _attach_best_embeddings(chunks: List[Dict[str, Any]], purpose: str) -> str:
    for chunk in chunks:
        _set_lightweight_embedding(chunk)

    vectors = await _try_deep_embeddings([chunk["content"] for chunk in chunks], purpose=purpose)
    if not vectors:
        _debug("rag_embedding_mode_selected", purpose=purpose, mode="lightweight", chunk_count=len(chunks))
        return "lightweight"

    for chunk, vector in zip(chunks, vectors):
        chunk["embedding"] = vector
        chunk["embedding_provider"] = DEEP_RAG_EMBEDDING_PROVIDER
        chunk["embedding_model"] = DEEP_RAG_EMBEDDING_MODEL
        chunk["embedding_dim"] = len(vector)
    _debug("rag_embedding_mode_selected", purpose=purpose, mode="deep", chunk_count=len(chunks), embedding_dim=len(vectors[0]))
    return "deep"


def _cosine_similarity(left: List[float], right: List[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    return sum(a * b for a, b in zip(left, right))


def _build_document_chunks(text: str, max_chars: int = 1000) -> List[Dict[str, Any]]:
    chunks = []
    for raw_chunk in _split_chunks(text, max_chars=max_chars):
        if _is_low_value_knowledge_text(raw_chunk):
            continue
        chunk = _knowledge_text(raw_chunk)
        if _is_low_value_knowledge_text(chunk):
            continue
        tokens = _tokens(chunk)
        chunks.append({
            "id": str(uuid.uuid4()),
            "chunk_index": len(chunks),
            "content": chunk,
            "tokens": tokens,
        })
    if not chunks:
        fallback = _knowledge_text(text)[:max_chars]
        tokens = _tokens(fallback)
        chunks.append({
            "id": str(uuid.uuid4()),
            "chunk_index": 0,
            "content": fallback,
            "tokens": tokens,
        })
    for chunk in chunks:
        _set_lightweight_embedding(chunk)
    return chunks


def _ensure_vector_index_for_subject(conn, subject_id: str, user_id: str) -> None:
    docs = conn.execute(
        """SELECT id, subject_id, user_id, filename, content
           FROM study_documents
           WHERE subject_id = ? AND user_id = ?
             AND (
               vector_index_ready = 0
               OR NOT EXISTS (
                 SELECT 1 FROM study_document_chunks c
                 WHERE c.document_id = study_documents.id
               )
             )""",
        (subject_id, user_id),
    ).fetchall()
    if not docs:
        return

    now = _now()
    _debug("local_vector_index_rebuild_start", subject_id=subject_id, user_id=user_id, document_count=len(docs))
    for doc in docs:
        chunks = _build_document_chunks(doc["content"] or "")
        conn.execute("DELETE FROM study_document_chunks WHERE document_id = ?", (doc["id"],))
        for chunk in chunks:
            conn.execute(
                """INSERT INTO study_document_chunks
                   (id, document_id, subject_id, user_id, chunk_index, content,
                    embedding_json, embedding_provider, embedding_model, embedding_dim, token_count, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    chunk["id"],
                    doc["id"],
                    subject_id,
                    user_id,
                    chunk["chunk_index"],
                    chunk["content"],
                    json.dumps(chunk["embedding"], ensure_ascii=False),
                    chunk["embedding_provider"],
                    chunk["embedding_model"],
                    chunk["embedding_dim"],
                    len(chunk["tokens"]),
                    now,
                ),
            )
        conn.execute(
            "UPDATE study_documents SET chunk_count = ?, vector_index_ready = 1 WHERE id = ?",
            (len(chunks), doc["id"]),
        )
        _debug("local_vector_index_document_ready", document_id=doc["id"], filename=doc["filename"], chunk_count=len(chunks))


def _sentence_candidates(text: str, topic: str) -> List[str]:
    text = _knowledge_text(text)
    sentences = [s.strip() for s in re.split(r"(?<=[。！？.!?])\s+|\n+|[；;]", text) if s.strip()]
    if len(sentences) <= 1 and len(text) > 180:
        sentences = [text[i:i + 180].strip() for i in range(0, len(text), 180) if text[i:i + 180].strip()]
    topic_tokens = set(_tokens(topic))
    scored = []
    seen = set()
    for index, sentence in enumerate(sentences):
        normalized = re.sub(r"\s+", "", sentence)
        if len(normalized) < 8 or normalized in seen:
            continue
        seen.add(normalized)
        score = sum(1 for token in topic_tokens if token in sentence.lower())
        scored.append((score, -abs(len(sentence) - 110), -index, sentence))
    scored.sort(reverse=True)
    return [item[3].strip()[:220] for item in scored] or [text[:160].strip()]


def _best_sentence(text: str, topic: str, offset: int = 0) -> str:
    candidates = _sentence_candidates(text, topic)
    return candidates[offset % len(candidates)]


def _get_subject(conn, subject_id: str, user_id: str):
    row = conn.execute(
        "SELECT * FROM study_subjects WHERE id = ? AND user_id = ?",
        (subject_id, user_id),
    ).fetchone()
    if not row:
        _debug("subject_not_found", subject_id=subject_id, user_id=user_id)
        raise HTTPException(status_code=404, detail="学科不存在")
    _debug("subject_loaded", subject_id=subject_id, user_id=user_id, subject_name=row["name"])
    return row


def _retrieve_local_context(conn, subject_id: str, user_id: str, query: str, limit: int = 5) -> List[Dict[str, Any]]:
    _debug("local_retrieval_start", subject_id=subject_id, user_id=user_id, query=query, limit=limit)
    _ensure_vector_index_for_subject(conn, subject_id, user_id)
    chunk_rows = conn.execute(
        """SELECT c.document_id, d.filename, c.content, c.embedding_json, c.token_count
           FROM study_document_chunks c
           JOIN study_documents d ON d.id = c.document_id
           WHERE c.subject_id = ? AND c.user_id = ?
           ORDER BY d.created_at DESC, c.chunk_index ASC""",
        (subject_id, user_id),
    ).fetchall()
    _debug("local_vector_chunks_loaded", chunk_count=len(chunk_rows))

    if chunk_rows:
        query_tokens = set(_tokens(query))
        query_embedding = _embedding_from_tokens(list(query_tokens))
        ranked: List[Dict[str, Any]] = []
        for row in chunk_rows:
            raw_content = row["content"] or ""
            if _is_low_value_knowledge_text(raw_content):
                continue
            content = _knowledge_text(raw_content)
            if _is_low_value_knowledge_text(content):
                continue
            lower = content.lower()
            try:
                embedding = json.loads(row["embedding_json"] or "[]")
            except json.JSONDecodeError:
                embedding = []
            lexical_score = sum(lower.count(token) for token in query_tokens)
            if query and query.lower() in lower:
                lexical_score += 3
            vector_score = _cosine_similarity(query_embedding, embedding)
            if vector_score == 0.0 and len(embedding) != len(query_embedding):
                vector_score = _cosine_similarity(query_embedding, _embedding_from_tokens(_tokens(content)))
            ranked.append({
                "document_id": row["document_id"],
                "filename": row["filename"],
                "source_type": "user_upload",
                "excerpt": content[:900],
                "score": round(lexical_score + vector_score * 8, 4),
                "vector_score": round(vector_score, 4),
                "token_count": row["token_count"],
            })
        ranked.sort(key=lambda item: item["score"], reverse=True)
        result = ranked[:limit]
        if result:
            _debug(
                "local_vector_retrieval_done",
                ranked_count=len(ranked),
                returned_count=len(result),
                top_scores=[{"filename": item["filename"], "score": item["score"], "vector_score": item["vector_score"], "excerpt": item["excerpt"][:120]} for item in result[:5]],
            )
            return result
        _debug("local_vector_retrieval_empty_after_filter", chunk_count=len(chunk_rows))

    docs = conn.execute(
        """SELECT id, filename, content FROM study_documents
           WHERE subject_id = ? AND user_id = ?
           ORDER BY created_at DESC""",
        (subject_id, user_id),
    ).fetchall()
    _debug(
        "local_documents_loaded",
        doc_count=len(docs),
        docs=[{"id": d["id"], "filename": d["filename"], "chars": len(d["content"] or "")} for d in docs],
    )
    if not docs:
        raise HTTPException(status_code=400, detail="该学科还没有上传资料，无法进行本地 RAG 出题")

    query_tokens = set(_tokens(query))
    _debug("local_query_tokens", tokens=sorted(query_tokens))
    ranked: List[Dict[str, Any]] = []
    for doc in docs:
        chunks = _split_chunks(doc["content"])
        _debug("local_document_chunked", document_id=doc["id"], filename=doc["filename"], chunk_count=len(chunks))
        for chunk in chunks:
            chunk = _knowledge_text(chunk)
            if _is_low_value_knowledge_text(chunk):
                continue
            lower = chunk.lower()
            score = sum(lower.count(token) for token in query_tokens)
            if query and query.lower() in lower:
                score += 3
            ranked.append({
                "document_id": doc["id"],
                "filename": doc["filename"],
                "source_type": "user_upload",
                "excerpt": chunk[:900],
                "score": score,
            })

    ranked.sort(key=lambda item: item["score"], reverse=True)
    result = ranked[:limit] if ranked else []
    _debug(
        "local_retrieval_done",
        ranked_count=len(ranked),
        returned_count=len(result),
        top_scores=[{"filename": item["filename"], "score": item["score"], "excerpt": item["excerpt"][:120]} for item in result[:5]],
    )
    return result


def _score_chunk_rows(
    chunk_rows,
    query: str,
    query_embedding: List[float],
    limit: int,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    dim: Optional[int] = None,
    source_type: str = "user_upload",
) -> List[Dict[str, Any]]:
    query_tokens = set(_tokens(query))
    ranked: List[Dict[str, Any]] = []
    for row in chunk_rows:
        if provider and row["embedding_provider"] != provider:
            continue
        if model and row["embedding_model"] != model:
            continue
        if dim and int(row["embedding_dim"] or 0) != dim:
            continue
        raw_content = row["content"] or ""
        if _is_low_value_knowledge_text(raw_content):
            continue
        content = _knowledge_text(raw_content)
        if _is_low_value_knowledge_text(content):
            continue
        lower = content.lower()
        try:
            embedding = json.loads(row["embedding_json"] or "[]")
        except json.JSONDecodeError:
            embedding = []
        lexical_score = sum(lower.count(token) for token in query_tokens)
        if query and query.lower() in lower:
            lexical_score += 3
        vector_score = _cosine_similarity(query_embedding, embedding)
        if vector_score == 0.0 and len(embedding) != len(query_embedding):
            vector_score = _cosine_similarity(query_embedding, _embedding_from_tokens(_tokens(content)))
        ranked.append({
            "document_id": row["document_id"],
            "filename": row["filename"],
            "source_type": source_type,
            "excerpt": content[:900],
            "score": round(lexical_score + vector_score * 8, 4),
            "vector_score": round(vector_score, 4),
            "token_count": row["token_count"],
            "embedding_provider": row["embedding_provider"],
            "embedding_model": row["embedding_model"],
            "embedding_dim": row["embedding_dim"],
        })
    ranked.sort(key=lambda item: item["score"], reverse=True)
    return ranked[:limit]


async def _retrieve_local_context_deep_or_light(
    conn,
    settings: LLMSettings,
    subject_id: str,
    user_id: str,
    query: str,
    limit: int = 5,
) -> List[Dict[str, Any]]:
    _debug("rag_retrieval_start", subject_id=subject_id, user_id=user_id, query=query, limit=limit)
    _ensure_vector_index_for_subject(conn, subject_id, user_id)
    chunk_rows = conn.execute(
        """SELECT c.document_id, d.filename, c.content, c.embedding_json, c.embedding_provider,
                  c.embedding_model, c.embedding_dim, c.token_count
           FROM study_document_chunks c
           JOIN study_documents d ON d.id = c.document_id
           WHERE c.subject_id = ? AND c.user_id = ?
           ORDER BY d.created_at DESC, c.chunk_index ASC""",
        (subject_id, user_id),
    ).fetchall()
    provider_counts: Dict[str, int] = {}
    for row in chunk_rows:
        provider_counts[row["embedding_provider"]] = provider_counts.get(row["embedding_provider"], 0) + 1
    _debug("rag_retrieval_chunks_loaded", chunk_count=len(chunk_rows), provider_counts=provider_counts)

    deep_query_vectors = await _try_deep_embeddings([query], purpose="query_retrieval")
    if deep_query_vectors:
        deep_query = deep_query_vectors[0]
        deep_results = _score_chunk_rows(
            chunk_rows,
            query,
            deep_query,
            limit,
            provider=DEEP_RAG_EMBEDDING_PROVIDER,
            model=DEEP_RAG_EMBEDDING_MODEL,
            dim=len(deep_query),
        )
        if deep_results:
            _debug(
                "deep_rag_retrieval_done",
                returned_count=len(deep_results),
                top_scores=[
                    {
                        "filename": item["filename"],
                        "score": item["score"],
                        "vector_score": item["vector_score"],
                        "excerpt": item["excerpt"][:120],
                    }
                    for item in deep_results[:5]
                ],
            )
            return deep_results
        _debug(
            "deep_rag_retrieval_empty_fallback_lightweight",
            deep_chunk_count=provider_counts.get(DEEP_RAG_EMBEDDING_PROVIDER, 0),
            query_embedding_dim=len(deep_query),
            model=DEEP_RAG_EMBEDDING_MODEL,
        )
    else:
        _debug("deep_rag_query_embedding_unavailable_fallback_lightweight", query=query)

    return _retrieve_local_context(conn, subject_id, user_id, query, limit=limit)


async def _retrieve_admin_context_deep_or_light(
    conn,
    settings: LLMSettings,
    subject_name: str,
    query: str,
    limit: int = 5,
) -> List[Dict[str, Any]]:
    subject_key = subject_name.strip().lower()
    include_all_subjects = subject_key in {"", "*", "all", "__all__"}
    candidates = {subject_key, *(item.lower() for item in ADMIN_KB_COMMON_SUBJECTS)}
    candidates.discard("")

    if include_all_subjects:
        chunk_rows = conn.execute(
            """SELECT c.document_id, d.filename, d.subject_name, c.content, c.embedding_json,
                      c.embedding_provider, c.embedding_model, c.embedding_dim, c.token_count
               FROM study_admin_document_chunks c
               JOIN study_admin_documents d ON d.id = c.document_id
               ORDER BY d.updated_at DESC, c.chunk_index ASC"""
        ).fetchall()
    else:
        placeholders = ",".join("?" for _ in candidates)
        if not placeholders:
            _debug("admin_rag_retrieval_skipped_no_subject", subject_name=subject_name, query=query)
            return []
        chunk_rows = conn.execute(
            f"""SELECT c.document_id, d.filename, d.subject_name, c.content, c.embedding_json,
                       c.embedding_provider, c.embedding_model, c.embedding_dim, c.token_count
                FROM study_admin_document_chunks c
                JOIN study_admin_documents d ON d.id = c.document_id
                WHERE LOWER(c.subject_name) IN ({placeholders})
                ORDER BY d.updated_at DESC, c.chunk_index ASC""",
            tuple(candidates),
        ).fetchall()
    provider_counts: Dict[str, int] = {}
    for row in chunk_rows:
        provider_counts[row["embedding_provider"]] = provider_counts.get(row["embedding_provider"], 0) + 1
    _debug(
        "admin_rag_retrieval_chunks_loaded",
        subject_name=subject_name,
        include_all_subjects=include_all_subjects,
        candidate_subjects=sorted(candidates),
        chunk_count=len(chunk_rows),
        provider_counts=provider_counts,
    )
    if not chunk_rows:
        return []

    deep_query_vectors = await _try_deep_embeddings([query], purpose="admin_query_retrieval")
    if deep_query_vectors:
        deep_query = deep_query_vectors[0]
        deep_results = _score_chunk_rows(
            chunk_rows,
            query,
            deep_query,
            limit,
            provider=DEEP_RAG_EMBEDDING_PROVIDER,
            model=DEEP_RAG_EMBEDDING_MODEL,
            dim=len(deep_query),
            source_type="admin_persistent",
        )
        if deep_results:
            _debug(
                "admin_deep_rag_retrieval_done",
                returned_count=len(deep_results),
                top_scores=[
                    {
                        "filename": item["filename"],
                        "score": item["score"],
                        "vector_score": item["vector_score"],
                        "excerpt": item["excerpt"][:120],
                    }
                    for item in deep_results[:5]
                ],
            )
            return deep_results
        _debug(
            "admin_deep_rag_retrieval_empty_fallback_lightweight",
            deep_chunk_count=provider_counts.get(DEEP_RAG_EMBEDDING_PROVIDER, 0),
            query_embedding_dim=len(deep_query),
            model=DEEP_RAG_EMBEDDING_MODEL,
        )

    lightweight_query = _embedding_from_tokens(_tokens(query))
    lightweight_results = _score_chunk_rows(
        chunk_rows,
        query,
        lightweight_query,
        limit,
        source_type="admin_persistent",
    )
    _debug(
        "admin_lightweight_rag_retrieval_done",
        returned_count=len(lightweight_results),
        top_scores=[
            {"filename": item["filename"], "score": item["score"], "excerpt": item["excerpt"][:120]}
            for item in lightweight_results[:5]
        ],
    )
    return lightweight_results


async def _retrieve_combined_context_deep_or_light(
    conn,
    settings: LLMSettings,
    subject_id: str,
    subject_name: str,
    user_id: str,
    query: str,
    limit: int = 5,
) -> List[Dict[str, Any]]:
    user_context: List[Dict[str, Any]] = []
    try:
        user_context = await _retrieve_local_context_deep_or_light(conn, settings, subject_id, user_id, query, limit=limit)
    except HTTPException as exc:
        if exc.status_code != 400:
            raise
        _debug("user_upload_rag_unavailable_try_admin_kb", subject_id=subject_id, subject_name=subject_name, query=query, detail=exc.detail)

    admin_context = await _retrieve_admin_context_deep_or_light(conn, settings, subject_name, query, limit=limit)
    combined = [*user_context, *admin_context]
    if not combined:
        raise HTTPException(status_code=400, detail="该学科没有可用资料：用户上传资料为空，管理员持久知识库也没有匹配资料")

    def priority(item: Dict[str, Any]) -> tuple[int, float]:
        return (0 if item.get("source_type") == "user_upload" else 1, -float(item.get("score") or 0))

    combined.sort(key=priority)
    result = combined[: max(limit, 1)]
    _debug(
        "combined_rag_context_ready",
        returned_count=len(result),
        user_context_count=len(user_context),
        admin_context_count=len(admin_context),
        sources=[
            {
                "filename": item.get("filename"),
                "source_type": item.get("source_type"),
                "score": item.get("score"),
                "excerpt": (item.get("excerpt") or "")[:100],
            }
            for item in result[:8]
        ],
    )
    return result


async def retrieve_admin_knowledge_context(
    settings: LLMSettings,
    query: str,
    subject_name: str = "all",
    limit: int = 4,
) -> List[Dict[str, Any]]:
    with get_db() as conn:
        return await _retrieve_admin_context_deep_or_light(conn, settings, subject_name, query, limit=limit)


async def _index_admin_knowledge_file(settings: LLMSettings, path: Path, force: bool = False) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "path": str(path),
        "filename": path.name,
        "subject_name": _admin_subject_from_path(path),
    }
    try:
        data = path.read_bytes()
        ext, text = _extract_document_text(path.name, data)
        content_hash = _file_content_hash(data)
        stat = path.stat()
        result.update({"file_type": ext.lstrip("."), "char_count": len(text), "content_hash": content_hash[:16]})
        if len(text) < 20:
            result["status"] = "skipped_short_text"
            _debug("admin_kb_file_skipped_short_text", **result)
            return result

        storage_path = str(path.resolve())
        was_existing = False
        with get_db() as conn:
            existing = conn.execute(
                "SELECT * FROM study_admin_documents WHERE storage_path = ?",
                (storage_path,),
            ).fetchone()
            was_existing = bool(existing)
            if (
                existing
                and not force
                and existing["content_hash"] == content_hash
                and int(existing["vector_index_ready"] or 0) == 1
            ):
                result.update({
                    "status": "skipped_unchanged",
                    "document_id": existing["id"],
                    "chunk_count": existing["chunk_count"],
                    "embedding_provider": existing["embedding_provider"],
                    "embedding_model": existing["embedding_model"],
                    "embedding_dim": existing["embedding_dim"],
                })
                _debug("admin_kb_file_skipped_unchanged", **result)
                return result
            doc_id = existing["id"] if existing else str(uuid.uuid4())

        chunks = _build_document_chunks(text)
        embedding_mode = await _attach_best_embeddings(chunks, purpose=f"admin_kb:{result['subject_name']}:{path.name}")
        now = _now()
        with get_db() as conn:
            conn.execute(
                """INSERT INTO study_admin_documents
                   (id, subject_name, filename, file_type, char_count, content, storage_path,
                    content_hash, file_mtime, chunk_count, vector_index_ready,
                    embedding_provider, embedding_model, embedding_dim, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(storage_path) DO UPDATE SET
                    subject_name = excluded.subject_name,
                    filename = excluded.filename,
                    file_type = excluded.file_type,
                    char_count = excluded.char_count,
                    content = excluded.content,
                    content_hash = excluded.content_hash,
                    file_mtime = excluded.file_mtime,
                    chunk_count = excluded.chunk_count,
                    vector_index_ready = excluded.vector_index_ready,
                    embedding_provider = excluded.embedding_provider,
                    embedding_model = excluded.embedding_model,
                    embedding_dim = excluded.embedding_dim,
                    updated_at = excluded.updated_at""",
                (
                    doc_id,
                    result["subject_name"],
                    path.name,
                    ext.lstrip("."),
                    len(text),
                    text,
                    storage_path,
                    content_hash,
                    stat.st_mtime,
                    len(chunks),
                    1,
                    chunks[0]["embedding_provider"] if chunks else LIGHTWEIGHT_EMBEDDING_PROVIDER,
                    chunks[0]["embedding_model"] if chunks else LIGHTWEIGHT_EMBEDDING_MODEL,
                    chunks[0]["embedding_dim"] if chunks else 96,
                    now,
                    now,
                ),
            )
            conn.execute("DELETE FROM study_admin_document_chunks WHERE document_id = ?", (doc_id,))
            for chunk in chunks:
                conn.execute(
                    """INSERT INTO study_admin_document_chunks
                       (id, document_id, subject_name, chunk_index, content, embedding_json,
                        embedding_provider, embedding_model, embedding_dim, token_count, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        chunk["id"],
                        doc_id,
                        result["subject_name"],
                        chunk["chunk_index"],
                        chunk["content"],
                        json.dumps(chunk["embedding"], ensure_ascii=False),
                        chunk["embedding_provider"],
                        chunk["embedding_model"],
                        chunk["embedding_dim"],
                        len(chunk["tokens"]),
                        now,
                    ),
                )

        result.update({
            "status": "updated" if was_existing else "indexed",
            "document_id": doc_id,
            "chunk_count": len(chunks),
            "embedding_mode": embedding_mode,
            "embedding_provider": chunks[0].get("embedding_provider") if chunks else None,
            "embedding_model": chunks[0].get("embedding_model") if chunks else None,
            "embedding_dim": chunks[0].get("embedding_dim") if chunks else None,
        })
        _debug("admin_kb_file_indexed", **result)
        return result
    except Exception as exc:
        _debug_exception("admin_kb_file_index_failed", exc, **result)
        result.update({"status": "failed", "error": f"{type(exc).__name__}: {exc}"})
        return result


def _flatten_duckduckgo_topics(items: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    sources: List[Dict[str, str]] = []
    for item in items:
        if "Topics" in item:
            sources.extend(_flatten_duckduckgo_topics(item.get("Topics") or []))
            continue
        text = item.get("Text")
        url = item.get("FirstURL")
        if text and url:
            sources.append({"title": text.split(" - ")[0][:120], "url": url, "snippet": text[:500]})
    return sources


def _web_client_kwargs(headers: Dict[str, str]) -> Dict[str, Any]:
    kwargs: Dict[str, Any] = {
        "timeout": httpx.Timeout(WEB_TIMEOUT_SECONDS, connect=WEB_TIMEOUT_SECONDS),
        "headers": headers,
        "follow_redirects": True,
        "trust_env": True,
    }
    if WEB_PROXY:
        kwargs["proxy"] = WEB_PROXY
    return kwargs


def _strip_html(value: str) -> str:
    value = re.sub(r"<script[\s\S]*?</script>", "", value, flags=re.I)
    value = re.sub(r"<style[\s\S]*?</style>", "", value, flags=re.I)
    value = re.sub(r"<[^>]+>", " ", value)
    value = html.unescape(value)
    return re.sub(r"\s+", " ", value).strip()


def _html_title(text: str) -> str:
    match = re.search(r"<title[^>]*>([\s\S]*?)</title>", text, flags=re.I)
    return _strip_html(match.group(1))[:120] if match else ""


def _html_meta_description(text: str) -> str:
    patterns = [
        r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']description["\']',
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.I)
        if match:
            return _strip_html(match.group(1))[:700]
    return ""


def _source_relevance_score(subject: str, topic: str, source: Dict[str, str]) -> int:
    haystack = " ".join([
        source.get("title") or "",
        source.get("snippet") or "",
        source.get("url") or "",
    ]).lower()
    subject_text = subject.strip().lower()
    topic_text = topic.strip().lower()
    score = 0
    if topic_text and topic_text in haystack:
        score += 10
    if subject_text and subject_text in haystack:
        score += 5
    for token in set(_tokens(f"{subject} {topic}")):
        if token in haystack:
            score += 2
    return score


def _is_relevant_web_source(subject: str, topic: str, source: Dict[str, str]) -> bool:
    haystack = " ".join([
        source.get("title") or "",
        source.get("snippet") or "",
        source.get("url") or "",
    ]).lower()
    topic_text = topic.strip().lower()
    subject_text = subject.strip().lower()
    if topic_text and topic_text not in haystack:
        return False
    if subject_text and subject_text != topic_text and subject_text not in haystack:
        return False
    if subject_text and subject_text in haystack:
        return True
    return _source_relevance_score(subject, topic, source) >= 10


def _filter_relevant_web_sources(subject: str, topic: str, sources: List[Dict[str, str]]) -> List[Dict[str, str]]:
    filtered = []
    rejected = []
    for source in sources:
        score = _source_relevance_score(subject, topic, source)
        item = {**source, "relevance_score": score}
        if _is_relevant_web_source(subject, topic, source):
            filtered.append(item)
        else:
            rejected.append({
                "title": source.get("title"),
                "url": source.get("url"),
                "score": score,
                "snippet": (source.get("snippet") or "")[:120],
            })
    filtered.sort(key=lambda item: item.get("relevance_score", 0), reverse=True)
    _debug(
        "web_relevance_filter_done",
        kept_count=len(filtered),
        rejected_count=len(rejected),
        rejected=rejected[:8],
    )
    return filtered


async def _fetch_baidu_baike(client: httpx.AsyncClient, subject: str, topic: str) -> List[Dict[str, str]]:
    candidates = [topic]
    results: List[Dict[str, str]] = []
    for candidate in candidates:
        url = f"https://baike.baidu.com/item/{quote(candidate)}"
        _debug("web_fetch_baidu_baike_request", url=url, candidate=candidate)
        response = await client.get(url)
        _debug(
            "web_fetch_baidu_baike_response",
            candidate=candidate,
            status_code=response.status_code,
            content_type=response.headers.get("content-type"),
            response_chars=len(response.text),
        )
        if response.status_code >= 400:
            continue
        title = _html_title(response.text) or candidate
        snippet = _html_meta_description(response.text)
        if not snippet:
            snippet = _strip_html(response.text)[:700]
        source = {"title": title, "url": str(response.url), "snippet": snippet}
        if snippet and _is_relevant_web_source(subject, topic, source):
            results.append(source)
            break
        _debug(
            "web_fetch_baidu_baike_rejected_irrelevant",
            candidate=candidate,
            title=title,
            url=str(response.url),
            snippet=snippet[:160],
            relevance_score=_source_relevance_score(subject, topic, source),
        )
    return results


async def _fetch_bing_rss(client: httpx.AsyncClient, query: str) -> List[Dict[str, str]]:
    url = "https://www.bing.com/search"
    _debug("web_fetch_bing_rss_request", url=url, query=query)
    response = await client.get(url, params={"q": query, "format": "rss"})
    _debug(
        "web_fetch_bing_rss_response",
        status_code=response.status_code,
        content_type=response.headers.get("content-type"),
        response_chars=len(response.text),
    )
    if response.status_code >= 400:
        return []

    root = ElementTree.fromstring(response.text)
    results: List[Dict[str, str]] = []
    for item in root.findall(".//item")[:5]:
        title = item.findtext("title") or query
        link = item.findtext("link") or "https://www.bing.com/"
        description = _strip_html(item.findtext("description") or title)
        if link and description:
            results.append({"title": title[:120], "url": link, "snippet": description[:700]})
    _debug("web_fetch_bing_rss_json", result_count=len(results), titles=[item["title"] for item in results])
    return results


async def _fetch_web_sources(subject: str, topic: str) -> List[Dict[str, str]]:
    query = f"{subject} {topic}".strip()
    sources: List[Dict[str, str]] = []
    errors: List[Dict[str, str]] = []
    headers = {"User-Agent": "AetherStudy/1.0 educational quiz generator"}
    _debug(
        "web_fetch_start",
        subject=subject,
        topic=topic,
        query=query,
        timeout_seconds=WEB_TIMEOUT_SECONDS,
        proxy_configured=bool(WEB_PROXY),
    )

    async with httpx.AsyncClient(**_web_client_kwargs(headers)) as client:
        try:
            _debug("web_fetch_duckduckgo_request", url="https://api.duckduckgo.com/", query=query)
            ddg = await client.get(
                "https://api.duckduckgo.com/",
                params={"q": query, "format": "json", "no_html": "1", "skip_disambig": "1"},
            )
            _debug(
                "web_fetch_duckduckgo_response",
                status_code=ddg.status_code,
                content_type=ddg.headers.get("content-type"),
                response_chars=len(ddg.text),
            )
            if ddg.status_code == 200:
                data = ddg.json()
                _debug(
                    "web_fetch_duckduckgo_json",
                    heading=data.get("Heading"),
                    has_abstract=bool(data.get("AbstractText")),
                    related_topics_count=len(data.get("RelatedTopics") or []),
                )
                if data.get("AbstractText"):
                    sources.append({
                        "title": data.get("Heading") or query,
                        "url": data.get("AbstractURL") or "https://duckduckgo.com/",
                        "snippet": data["AbstractText"][:600],
                    })
                sources.extend(_flatten_duckduckgo_topics(data.get("RelatedTopics") or []))
            else:
                errors.append({"source": "duckduckgo", "error": f"HTTP {ddg.status_code}: {ddg.text[:300]}"})
        except Exception as exc:
            errors.append({"source": "duckduckgo", "error": f"{type(exc).__name__}: {exc}"})
            _debug_exception("web_fetch_duckduckgo_failed", exc, query=query)

        try:
            _debug("web_fetch_wikipedia_request", url="https://zh.wikipedia.org/w/api.php", query=query)
            wiki = await client.get(
                "https://zh.wikipedia.org/w/api.php",
                params={"action": "opensearch", "search": query, "limit": 5, "namespace": 0, "format": "json"},
            )
            _debug(
                "web_fetch_wikipedia_response",
                status_code=wiki.status_code,
                content_type=wiki.headers.get("content-type"),
                response_chars=len(wiki.text),
            )
            if wiki.status_code == 200:
                data = wiki.json()
                titles = data[1] if len(data) > 1 else []
                snippets = data[2] if len(data) > 2 else []
                urls = data[3] if len(data) > 3 else []
                _debug("web_fetch_wikipedia_json", title_count=len(titles), titles=titles[:5])
                for title, snippet, url in zip(titles, snippets, urls):
                    if title and url:
                        sources.append({"title": title, "url": url, "snippet": (snippet or title)[:500]})
            else:
                errors.append({"source": "wikipedia", "error": f"HTTP {wiki.status_code}: {wiki.text[:300]}"})
        except Exception as exc:
            errors.append({"source": "wikipedia", "error": f"{type(exc).__name__}: {exc}"})
            _debug_exception("web_fetch_wikipedia_failed", exc, query=query)

        try:
            sources.extend(await _fetch_bing_rss(client, query))
        except Exception as exc:
            errors.append({"source": "bing_rss", "error": f"{type(exc).__name__}: {exc}"})
            _debug_exception("web_fetch_bing_rss_failed", exc, query=query)

        try:
            sources.extend(await _fetch_baidu_baike(client, subject, topic))
        except Exception as exc:
            errors.append({"source": "baidu_baike", "error": f"{type(exc).__name__}: {exc}"})
            _debug_exception("web_fetch_baidu_baike_failed", exc, query=query)

    deduped: List[Dict[str, str]] = []
    seen = set()
    for source in sources:
        key = source.get("url")
        if key and key not in seen and source.get("snippet"):
            seen.add(key)
            deduped.append(source)
    relevant = _filter_relevant_web_sources(subject, topic, deduped)
    _debug(
        "web_fetch_done",
        raw_source_count=len(sources),
        deduped_count=len(deduped),
        relevant_count=len(relevant),
        errors=errors,
        sources=[{"title": s.get("title"), "url": s.get("url"), "score": s.get("relevance_score"), "snippet": (s.get("snippet") or "")[:120]} for s in relevant[:5]],
    )
    return relevant[:5]


def _local_only_web_source(subject: str, topic: str) -> Dict[str, Any]:
    return {
        "title": "联网资料不可用，已优先使用本地资料",
        "url": "local-only://web-search-unavailable",
        "snippet": (
            f"联网搜索暂时不可用，系统已根据本地上传资料优先生成「{subject} / {topic}」相关题目。"
            "本条为降级标记，不作为外部知识依据。"
        ),
        "offline": True,
    }


def _question_type_at(base_type: str, index: int) -> str:
    if base_type != "mixed":
        return base_type
    return ["single_choice", "multiple_choice", "true_false", "fill_blank", "short_answer"][index % 5]


def _single_choice_options(correct: str, distractors: List[str], seq_no: int) -> tuple[List[str], str]:
    labels = ["A", "B", "C", "D"]
    options = [correct, *distractors[:3]]
    shift = (seq_no - 1) % len(options)
    rotated = options[shift:] + options[:shift]
    answer = labels[rotated.index(correct)]
    return rotated, answer


def _quiz_type_label(q_type: str) -> str:
    return {
        "single_choice": "单选题",
        "multiple_choice": "多选题",
        "true_false": "判断题",
        "fill_blank": "填空题",
        "short_answer": "简答题",
    }.get(q_type, q_type)


def _difficulty_label(difficulty: str) -> str:
    return {"easy": "入门", "medium": "中级", "hard": "进阶"}.get(difficulty, difficulty)


def _normalize_choice_answer(answer: Any, fallback: str = "A") -> str:
    value = str(answer or fallback).strip().upper()
    match = re.search(r"[A-D]", value)
    return match.group(0) if match else fallback


def _normalize_multi_answer(answer: Any) -> List[str]:
    if isinstance(answer, list):
        values = answer
    else:
        values = re.findall(r"[A-D]", str(answer or "").upper())
    cleaned = []
    for value in values:
        letter = str(value).strip().upper()
        if letter in {"A", "B", "C", "D"} and letter not in cleaned:
            cleaned.append(letter)
    return cleaned or ["A", "C"]


def _normalize_llm_question(raw: Dict[str, Any], seq_no: int, requested_type: str, local: Dict[str, Any], web: Dict[str, Any], topic: str, difficulty: str) -> Dict[str, Any]:
    q_type = raw.get("type") or requested_type
    if requested_type != "mixed":
        q_type = requested_type
    if q_type not in {"single_choice", "multiple_choice", "true_false", "fill_blank", "short_answer"}:
        q_type = "single_choice"

    prompt = _knowledge_text(str(raw.get("prompt") or "")).strip()
    if not prompt:
        prompt = f"{_quiz_type_label(q_type)}：围绕「{topic}」，根据资料判断下列说法。"

    options = raw.get("options") if isinstance(raw.get("options"), list) else []
    options = [_knowledge_text(str(option)).strip() for option in options if str(option).strip()]
    if q_type in {"single_choice", "multiple_choice"}:
        fallback_correct = f"资料表明，「{topic}」需要结合概念、条件和应用场景理解。"
        fallback_distractors = [
            f"学习「{topic}」只需要记住名称，不需要理解适用条件。",
            f"只要题目出现「{topic}」，结论就一定相同。",
            f"资料中的例子和限制条件可以忽略。",
        ]
        if len(options) < 4:
            options = [*options, fallback_correct, *fallback_distractors]
        options = options[:4]
    else:
        options = []

    if q_type == "single_choice":
        answer: Any = _normalize_choice_answer(raw.get("answer"))
    elif q_type == "multiple_choice":
        answer = _normalize_multi_answer(raw.get("answer"))
    elif q_type == "true_false":
        answer = bool(raw.get("answer", True))
    else:
        answer = _knowledge_text(str(raw.get("answer") or topic)).strip()

    explanation = _knowledge_text(str(raw.get("explanation") or "")).strip()
    if len(explanation) < 20:
        explanation = f"这道题用于理解和记忆「{topic}」：应先抓住资料中的定义或机制，再判断适用条件、优缺点和常见误区。"

    return {
        "id": str(uuid.uuid4()),
        "seq_no": seq_no,
        "type": q_type,
        "prompt": prompt,
        "options": options,
        "answer": answer,
        "explanation": explanation,
        "difficulty": difficulty,
        "local_citation": raw.get("local_citation") or f"{local['filename']}：{_best_sentence(local['excerpt'], topic, seq_no - 1)[:80]}",
        "web_citation": raw.get("web_citation") or ("联网资料不可用：本题优先依据本地上传资料生成" if web.get("offline") else f"{web.get('title', '联网资料')}：{_knowledge_text(web.get('snippet') or '')[:80]}"),
    }


async def _generate_learning_questions_with_llm(
    user_id: str,
    subject_name: str,
    req: QuizGenerateRequest,
    local_context: List[Dict[str, Any]],
    web_sources: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    local_materials = [
        {
            "index": index + 1,
            "filename": item["filename"],
            "source_type": item.get("source_type", "user_upload"),
            "excerpt": _knowledge_text(item["excerpt"])[:1200],
        }
        for index, item in enumerate(local_context[: min(len(local_context), 8)])
    ]
    web_materials = [
        {
            "index": index + 1,
            "title": item.get("title"),
            "url": item.get("url"),
            "snippet": _knowledge_text(item.get("snippet") or "")[:700],
            "offline": bool(item.get("offline")),
        }
        for index, item in enumerate(web_sources[:5])
    ]
    requested_types = [_question_type_at(req.question_type, index) for index in range(req.count)]

    messages = [
        {
            "role": "system",
            "content": (
                "你是严谨的学科助教，任务是生成能帮助学生理解、记忆和迁移应用知识的练习题。"
                "必须基于给定资料，不要把网页链接、文章标题、文件名当作知识点本身。"
                "题目要考查定义、机制、适用条件、优缺点、对比、常见误区或应用判断。"
                "错误选项必须是有迷惑性的真实学习误区，不能写'与当前学科无关'、'不需要上下文'这类无价值选项。"
                "解释要像老师讲题，说明为什么正确、为什么干扰项错。"
                "只输出 JSON。"
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                {
                    "task": "generate_learning_quiz",
                    "subject": subject_name,
                    "topic": req.topic,
                    "difficulty": _difficulty_label(req.difficulty),
                    "count": req.count,
                    "requested_question_types": requested_types,
                    "local_materials": local_materials,
                    "web_materials": web_materials,
                    "output_schema": {
                        "questions": [
                            {
                                "seq_no": 1,
                                "type": "single_choice | multiple_choice | true_false | fill_blank | short_answer",
                                "prompt": "题干，不要出现资料来源标题或 URL",
                                "options": ["选择题必须给 4 个选项；非选择题为空数组"],
                                "answer": "单选为 A/B/C/D；多选为数组；判断为 true/false；填空/简答为文本",
                                "explanation": "面向理解与记忆的解析",
                                "local_citation": "引用本地资料文件名和一句关键依据",
                                "web_citation": "如果有真实联网资料，引用标题和一句关键依据；如果 offline 则说明联网资料不可用",
                            }
                        ]
                    },
                    "quality_rules": [
                        "每道题必须考查不同角度，不能模板化重复。",
                        "单选题必须只有一个最佳答案，错误选项要接近但明确错误。",
                        "不要把 Markdown 链接、目录标题、文章列表当成正确答案。",
                        "如果本地材料只是链接列表或目录，必须用可用的解释性材料出题；没有足够依据时在 explanation 中说明依据不足。",
                    ],
                },
                ensure_ascii=False,
            ),
        },
    ]

    settings = get_user_llm_settings(user_id)
    data = await complete_llm_json(settings, messages)
    raw_questions = data.get("questions") if isinstance(data, dict) else None
    if not isinstance(raw_questions, list):
        raise ValueError("LLM did not return questions list")

    questions: List[Dict[str, Any]] = []
    for index in range(req.count):
        raw = raw_questions[index] if index < len(raw_questions) and isinstance(raw_questions[index], dict) else {}
        local = local_context[index % len(local_context)]
        web = web_sources[index % len(web_sources)]
        requested_type = _question_type_at(req.question_type, index)
        questions.append(_normalize_llm_question(raw, index + 1, requested_type, local, web, req.topic, req.difficulty))
    return questions


def _build_question(seq_no: int, q_type: str, topic: str, difficulty: str, local: Dict[str, Any], web: Dict[str, str]) -> Dict[str, Any]:
    local_point = _best_sentence(local["excerpt"], topic, seq_no - 1)
    local_extra = _best_sentence(local["excerpt"], topic, seq_no)
    web_point = _best_sentence(web.get("snippet") or web.get("title") or "", topic, seq_no - 1)
    local_ref = f"{local['filename']}：{local_point[:80]}"
    web_is_offline = bool(web.get("offline"))
    web_ref = "联网资料不可用：本题优先依据本地上传资料生成" if web_is_offline else f"{web.get('title', '联网资料')}：{web_point[:80]}"
    focus = ["概念理解", "适用条件", "方法特点", "常见误区", "应用场景"][(seq_no - 1) % 5]

    if q_type == "multiple_choice":
        options = [
            f"理解「{topic}」时，应结合资料中的概念、机制和适用条件来判断。",
            f"只要记住「{topic}」这个名称，就能准确解决所有相关题目。",
            "联网资料暂时不可用时，应优先依据已上传资料出题和解析。" if web_is_offline else f"联网资料提到：{web_point[:90]}",
            f"学习「{topic}」时可以忽略资料中的限制、例子和反例。",
        ]
        answer: Any = ["A", "C"]
        prompt = f"多选题 {seq_no}（{focus}）：关于「{topic}」的学习方法，哪些说法更有助于理解和记忆？"
    elif q_type == "true_false":
        options = []
        answer = True
        prompt = f"判断题（{focus}）：本地资料中与「{topic}」相关的要点包括：{local_point}"
    elif q_type == "fill_blank":
        options = []
        answer = topic
        prompt = f"填空题（{focus}）：本题优先依据本地资料「{local['filename']}」考查的核心主题是____。" if web_is_offline else f"填空题（{focus}）：本题结合本地资料「{local['filename']}」和联网资料「{web.get('title', '资料')}」考查的核心主题是____。"
    elif q_type == "short_answer":
        options = []
        answer = f"可依据本地资料作答：本地资料指出「{local_point}」。作答时需说明概念、适用条件或应用场景。" if web_is_offline else f"可从两点作答：本地资料指出「{local_point}」；联网资料补充「{web_point}」。作答时需说明概念、适用条件或应用场景。"
        prompt = f"简答题（{focus}）：依据本地资料，说明「{topic}」的一个关键知识点及其适用场景。" if web_is_offline else f"简答题（{focus}）：结合本地资料和联网资料，说明「{topic}」的一个关键知识点及其适用场景。"
    else:
        q_type = "single_choice"
        correct = f"应结合资料中的关键依据理解「{topic}」：{local_point[:90]}"
        distractors = [
            f"学习「{topic}」时只需要背名称，不需要理解概念之间的关系。",
            f"只要某个方法包含「{topic}」相关术语，就一定适用于所有数据和任务。",
            f"可以忽略资料中关于「{topic}」的适用条件、限制和例子。",
        ]
        options, answer = _single_choice_options(correct, distractors, seq_no)
        prompt = f"单选题 {seq_no}（{focus}）：为了真正理解和记忆「{topic}」，以下哪项学习判断最合理？"

    explanation = (
        f"依据本地资料：{local_point}。联网资料暂时不可用，本题按本地资料优先策略生成。"
        if web_is_offline
        else f"依据本地资料：{local_point}；联网资料：{web_point}"
    )

    return {
        "id": str(uuid.uuid4()),
        "seq_no": seq_no,
        "type": q_type,
        "prompt": prompt,
        "options": options,
        "answer": answer,
        "explanation": explanation,
        "difficulty": difficulty,
        "local_citation": local_ref,
        "web_citation": web_ref,
    }


def _serialize_quiz(conn, quiz_id: str, include_questions: bool = True) -> Dict[str, Any]:
    quiz = conn.execute(
        """SELECT qs.*, ss.name AS subject_name
           FROM quiz_sets qs
           JOIN study_subjects ss ON ss.id = qs.subject_id
           WHERE qs.id = ?""",
        (quiz_id,),
    ).fetchone()
    if not quiz:
        raise HTTPException(status_code=404, detail="题目记录不存在")

    data = {
        "id": quiz["id"],
        "user_id": quiz["user_id"],
        "subject_id": quiz["subject_id"],
        "subject_name": quiz["subject_name"],
        "title": quiz["title"],
        "topic": quiz["topic"],
        "question_type": quiz["question_type"],
        "count": quiz["count"],
        "difficulty": quiz["difficulty"],
        "local_sources": json.loads(quiz["local_sources"] or "[]"),
        "web_sources": json.loads(quiz["web_sources"] or "[]"),
        "created_at": quiz["created_at"],
    }
    if include_questions:
        rows = conn.execute(
            "SELECT * FROM quiz_questions WHERE quiz_set_id = ? ORDER BY seq_no ASC",
            (quiz_id,),
        ).fetchall()
        data["questions"] = [
            {
                "id": row["id"],
                "seq_no": row["seq_no"],
                "type": row["question_type"],
                "prompt": row["prompt"],
                "options": json.loads(row["options_json"] or "[]"),
                "answer": json.loads(row["answer_json"] or "null"),
                "explanation": row["explanation"],
                "local_citation": row["local_citation"],
                "web_citation": row["web_citation"],
            }
            for row in rows
        ]
    return data


@router.get("/subjects")
async def list_subjects(current_user: UserInDB = Depends(get_current_user)):
    with get_db() as conn:
        rows = conn.execute(
            """SELECT s.*,
                      COUNT(DISTINCT d.id) AS document_count,
                      COUNT(DISTINCT q.id) AS quiz_count
               FROM study_subjects s
               LEFT JOIN study_documents d ON d.subject_id = s.id
               LEFT JOIN quiz_sets q ON q.subject_id = s.id
               WHERE s.user_id = ?
               GROUP BY s.id
               ORDER BY s.updated_at DESC""",
            (current_user.id,),
        ).fetchall()
        return {"subjects": [dict(row) for row in rows]}


@router.post("/debug-log")
async def frontend_debug_log(req: FrontendDebugLogRequest, current_user: UserInDB = Depends(get_current_user)):
    """接收前端调试日志并打印到后端终端，便于只看一个终端定位问题。"""
    _debug(f"frontend_{req.step}", user_id=current_user.id, **req.data)
    return {"ok": True}


@router.get("/admin/knowledge")
async def list_admin_knowledge(_admin: UserInDB = Depends(get_current_admin)):
    ADMIN_KB_ROOT.mkdir(parents=True, exist_ok=True)
    with get_db() as conn:
        rows = conn.execute(
            """SELECT id, subject_name, filename, file_type, char_count, storage_path,
                      content_hash, file_mtime, chunk_count, vector_index_ready,
                      embedding_provider, embedding_model, embedding_dim, created_at, updated_at
               FROM study_admin_documents
               ORDER BY subject_name ASC, filename ASC"""
        ).fetchall()
    summary: Dict[str, int] = {}
    documents = [dict(row) for row in rows]
    for item in documents:
        summary[item["subject_name"]] = summary.get(item["subject_name"], 0) + 1
    return {
        "root": str(ADMIN_KB_ROOT),
        "document_count": len(documents),
        "summary": summary,
        "documents": documents,
    }


@router.post("/admin/knowledge/upload", status_code=status.HTTP_201_CREATED)
async def upload_admin_knowledge(
    subject_name: str = Form(..., min_length=1, max_length=80),
    files: List[UploadFile] = File(...),
    admin: UserInDB = Depends(get_current_admin),
):
    settings = get_user_llm_settings(admin.id)
    results: List[Dict[str, Any]] = []
    _debug(
        "admin_kb_upload_start",
        admin_id=admin.id,
        subject_name=subject_name,
        file_count=len(files),
        root=str(ADMIN_KB_ROOT),
    )

    for file in files:
        result: Dict[str, Any] = {"filename": file.filename, "subject_name": subject_name}
        try:
            ext = _extension(file.filename or "")
            if ext not in SUPPORTED_EXTENSIONS:
                result.update({"status": "failed", "error": "仅支持 Markdown、TXT 和 PDF 文件"})
                results.append(result)
                _debug("admin_kb_upload_rejected_extension", **result, extension=ext)
                continue

            data = await file.read()
            if len(data) > MAX_UPLOAD_BYTES:
                result.update({"status": "failed", "error": "文件过大，单个文件最多 12MB", "bytes": len(data)})
                results.append(result)
                _debug("admin_kb_upload_rejected_size", **result)
                continue

            target_path = _admin_storage_path(subject_name, file.filename or "document")
            target_path.write_bytes(data)
            result.update({"storage_path": str(target_path), "bytes": len(data)})
            _debug("admin_kb_upload_file_saved", **result)

            indexed = await _index_admin_knowledge_file(settings, target_path, force=True)
            results.append({**result, **indexed})
        except Exception as exc:
            _debug_exception("admin_kb_upload_file_failed", exc, **result)
            results.append({**result, "status": "failed", "error": f"{type(exc).__name__}: {exc}"})

    status_counts: Dict[str, int] = {}
    for item in results:
        status_counts[item["status"]] = status_counts.get(item["status"], 0) + 1
    _debug("admin_kb_upload_done", admin_id=admin.id, subject_name=subject_name, status_counts=status_counts)
    return {
        "root": str(ADMIN_KB_ROOT),
        "subject_name": subject_name,
        "status_counts": status_counts,
        "results": results,
    }


@router.post("/admin/knowledge/reindex")
async def reindex_admin_knowledge(
    req: AdminKnowledgeReindexRequest,
    admin: UserInDB = Depends(get_current_admin),
):
    settings = get_user_llm_settings(admin.id)
    files = _iter_admin_knowledge_files()
    _debug(
        "admin_kb_reindex_start",
        admin_id=admin.id,
        root=str(ADMIN_KB_ROOT),
        file_count=len(files),
        force=req.force,
    )

    seen_paths = {str(path.resolve()) for path in files}
    removed: List[Dict[str, Any]] = []
    with get_db() as conn:
        existing_rows = conn.execute("SELECT id, storage_path, filename, subject_name FROM study_admin_documents").fetchall()
        for row in existing_rows:
            if row["storage_path"] in seen_paths:
                continue
            conn.execute("DELETE FROM study_admin_document_chunks WHERE document_id = ?", (row["id"],))
            conn.execute("DELETE FROM study_admin_documents WHERE id = ?", (row["id"],))
            removed.append({"document_id": row["id"], "filename": row["filename"], "subject_name": row["subject_name"]})
    if removed:
        _debug("admin_kb_removed_missing_files", removed_count=len(removed), removed=removed[:20])

    results = []
    for path in files:
        results.append(await _index_admin_knowledge_file(settings, path, force=req.force))

    status_counts: Dict[str, int] = {}
    for item in results:
        status_counts[item["status"]] = status_counts.get(item["status"], 0) + 1
    _debug(
        "admin_kb_reindex_done",
        admin_id=admin.id,
        status_counts=status_counts,
        removed_count=len(removed),
    )
    return {
        "root": str(ADMIN_KB_ROOT),
        "file_count": len(files),
        "status_counts": status_counts,
        "removed": removed,
        "results": results,
    }


@router.delete("/admin/knowledge/{document_id}")
async def delete_admin_knowledge_document(
    document_id: str,
    _admin: UserInDB = Depends(get_current_admin),
):
    with get_db() as conn:
        doc = conn.execute(
            "SELECT id, subject_name, filename, storage_path FROM study_admin_documents WHERE id = ?",
            (document_id,),
        ).fetchone()
        if not doc:
            raise HTTPException(status_code=404, detail="管理员知识库资料不存在")
        _debug(
            "admin_kb_delete_start",
            document_id=document_id,
            subject_name=doc["subject_name"],
            filename=doc["filename"],
            storage_path=doc["storage_path"],
        )
        conn.execute("DELETE FROM study_admin_document_chunks WHERE document_id = ?", (document_id,))
        conn.execute("DELETE FROM study_admin_documents WHERE id = ?", (document_id,))
        _delete_admin_document_storage(doc["storage_path"])
    _debug("admin_kb_delete_done", document_id=document_id)
    return {"ok": True, "deleted_document_id": document_id}


@router.post("/subjects", status_code=status.HTTP_201_CREATED)
async def create_subject(req: SubjectCreate, current_user: UserInDB = Depends(get_current_user)):
    subject_id = str(uuid.uuid4())
    now = _now()
    _debug("subject_create_start", user_id=current_user.id, name=req.name, description_chars=len(req.description or ""))
    with get_db() as conn:
        try:
            conn.execute(
                """INSERT INTO study_subjects (id, user_id, name, description, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (subject_id, current_user.id, req.name.strip(), req.description.strip(), now, now),
            )
        except Exception as exc:
            _debug_exception("subject_create_failed", exc, user_id=current_user.id, name=req.name)
            raise HTTPException(status_code=409, detail="该学科已存在") from exc
    _debug("subject_create_done", subject_id=subject_id, user_id=current_user.id, name=req.name.strip())
    return {"id": subject_id, "name": req.name.strip(), "description": req.description.strip(), "created_at": now, "updated_at": now}


@router.get("/subjects/{subject_id}/documents")
async def list_documents(subject_id: str, current_user: UserInDB = Depends(get_current_user)):
    with get_db() as conn:
        _get_subject(conn, subject_id, current_user.id)
        rows = conn.execute(
            """SELECT id, subject_id, filename, file_type, char_count, storage_path,
                      chunk_count, vector_index_ready, created_at
               FROM study_documents
               WHERE subject_id = ? AND user_id = ?
               ORDER BY created_at DESC""",
            (subject_id, current_user.id),
        ).fetchall()
        return {"documents": [dict(row) for row in rows]}


@router.post("/subjects/{subject_id}/documents", status_code=status.HTTP_201_CREATED)
async def upload_document(
    subject_id: str,
    file: UploadFile = File(...),
    current_user: UserInDB = Depends(get_current_user),
):
    _debug(
        "document_upload_start",
        subject_id=subject_id,
        user_id=current_user.id,
        filename=file.filename,
        content_type=file.content_type,
    )
    ext = _extension(file.filename or "")
    _debug("document_upload_extension_checked", filename=file.filename, extension=ext)
    if ext not in SUPPORTED_EXTENSIONS:
        _debug("document_upload_rejected_extension", filename=file.filename, extension=ext)
        raise HTTPException(status_code=400, detail="仅支持 Markdown、TXT 和 PDF 文件")

    data = await file.read()
    _debug("document_upload_bytes_read", filename=file.filename, bytes=len(data), max_bytes=MAX_UPLOAD_BYTES)
    if len(data) > MAX_UPLOAD_BYTES:
        _debug("document_upload_rejected_size", filename=file.filename, bytes=len(data), max_bytes=MAX_UPLOAD_BYTES)
        raise HTTPException(status_code=400, detail="文件过大，单个文件最多 12MB")

    text = _extract_pdf_text(data) if ext == ".pdf" else _decode_text(data)
    text = _clean_text(text)
    _debug(
        "document_upload_text_ready",
        filename=file.filename,
        extension=ext,
        text_chars=len(text),
        preview=text[:180],
    )
    if len(text) < 20:
        _debug("document_upload_rejected_short_text", filename=file.filename, text_chars=len(text), preview=text[:180])
        raise HTTPException(status_code=400, detail="资料文本过短，无法用于 RAG 出题")

    incoming_stored_filename = _safe_filename(file.filename or "document")
    with get_db() as conn:
        _get_subject(conn, subject_id, current_user.id)
        existing_docs = conn.execute(
            """SELECT id, filename, stored_filename, storage_path
               FROM study_documents
               WHERE subject_id = ? AND user_id = ? AND (stored_filename = ? OR filename = ?)
               ORDER BY created_at DESC""",
            (subject_id, current_user.id, incoming_stored_filename, file.filename),
        ).fetchall()

    existing_doc = existing_docs[0] if existing_docs else None
    duplicate_docs = existing_docs[1:] if len(existing_docs) > 1 else []
    doc_id = existing_doc["id"] if existing_doc else str(uuid.uuid4())
    upload_status = "updated" if existing_doc else "created"
    now = _now()
    storage_path, stored_filename = _save_uploaded_file(current_user.id, subject_id, doc_id, file.filename or "document", data)
    chunks = _build_document_chunks(text)
    embedding_mode = await _attach_best_embeddings(chunks, purpose="document_upload")
    _debug(
        "document_vector_index_ready",
        document_id=doc_id,
        chunk_count=len(chunks),
        embedding_mode=embedding_mode,
        embedding_provider=chunks[0].get("embedding_provider") if chunks else None,
        embedding_model=chunks[0].get("embedding_model") if chunks else None,
        embedding_dim=chunks[0].get("embedding_dim") if chunks else None,
        storage_path=storage_path,
        stored_filename=stored_filename,
    )
    duplicate_storage_paths = [doc["storage_path"] for doc in duplicate_docs if doc["storage_path"]]
    with get_db() as conn:
        _get_subject(conn, subject_id, current_user.id)
        _debug(
            "document_upload_db_write_start",
            document_id=doc_id,
            subject_id=subject_id,
            user_id=current_user.id,
            status=upload_status,
            duplicate_cleanup_count=len(duplicate_docs),
        )
        for duplicate_doc in duplicate_docs:
            conn.execute("DELETE FROM study_document_chunks WHERE document_id = ?", (duplicate_doc["id"],))
            conn.execute(
                "DELETE FROM study_documents WHERE id = ? AND user_id = ?",
                (duplicate_doc["id"], current_user.id),
            )

        if existing_doc:
            conn.execute("DELETE FROM study_document_chunks WHERE document_id = ?", (doc_id,))
            conn.execute(
                """UPDATE study_documents
                   SET filename = ?, file_type = ?, char_count = ?, content = ?,
                       storage_path = ?, stored_filename = ?, chunk_count = ?,
                       vector_index_ready = 1, created_at = ?
                   WHERE id = ? AND user_id = ?""",
                (
                    file.filename,
                    ext.lstrip("."),
                    len(text),
                    text,
                    storage_path,
                    stored_filename,
                    len(chunks),
                    now,
                    doc_id,
                    current_user.id,
                ),
            )
        else:
            conn.execute(
                """INSERT INTO study_documents
                   (id, subject_id, user_id, filename, file_type, char_count, content,
                    storage_path, stored_filename, chunk_count, vector_index_ready, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    doc_id,
                    subject_id,
                    current_user.id,
                    file.filename,
                    ext.lstrip("."),
                    len(text),
                    text,
                    storage_path,
                    stored_filename,
                    len(chunks),
                    1,
                    now,
                ),
            )
        for chunk in chunks:
            conn.execute(
                """INSERT INTO study_document_chunks
                   (id, document_id, subject_id, user_id, chunk_index, content,
                    embedding_json, embedding_provider, embedding_model, embedding_dim, token_count, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    chunk["id"],
                    doc_id,
                    subject_id,
                    current_user.id,
                    chunk["chunk_index"],
                    chunk["content"],
                    json.dumps(chunk["embedding"], ensure_ascii=False),
                    chunk["embedding_provider"],
                    chunk["embedding_model"],
                    chunk["embedding_dim"],
                    len(chunk["tokens"]),
                    now,
                ),
            )
        conn.execute("UPDATE study_subjects SET updated_at = ? WHERE id = ?", (now, subject_id))

    for duplicate_storage_path in duplicate_storage_paths:
        if duplicate_storage_path != storage_path:
            _delete_document_storage(duplicate_storage_path)

    _debug(
        "document_upload_done",
        document_id=doc_id,
        subject_id=subject_id,
        filename=file.filename,
        file_type=ext.lstrip("."),
        char_count=len(text),
        chunk_count=len(chunks),
        vector_index_ready=True,
        storage_path=storage_path,
        status=upload_status,
        duplicate_cleanup_count=len(duplicate_docs),
    )
    return {
        "id": doc_id,
        "subject_id": subject_id,
        "filename": file.filename,
        "file_type": ext.lstrip("."),
        "char_count": len(text),
        "storage_path": storage_path,
        "chunk_count": len(chunks),
        "vector_index_ready": True,
        "created_at": now,
        "status": upload_status,
        "replaced_existing": bool(existing_doc),
        "duplicate_cleanup_count": len(duplicate_docs),
    }


@router.delete("/documents/{document_id}")
async def delete_document(document_id: str, current_user: UserInDB = Depends(get_current_user)):
    with get_db() as conn:
        doc = conn.execute(
            """SELECT d.*, s.name AS subject_name
               FROM study_documents d
               JOIN study_subjects s ON s.id = d.subject_id
               WHERE d.id = ? AND d.user_id = ?""",
            (document_id, current_user.id),
        ).fetchone()
        if not doc:
            raise HTTPException(status_code=404, detail="资料不存在")

        _debug(
            "document_delete_start",
            document_id=document_id,
            subject_id=doc["subject_id"],
            user_id=current_user.id,
            filename=doc["filename"],
            storage_path=doc["storage_path"],
        )
        conn.execute("DELETE FROM study_document_chunks WHERE document_id = ?", (document_id,))
        conn.execute("DELETE FROM study_documents WHERE id = ? AND user_id = ?", (document_id, current_user.id))
        conn.execute("UPDATE study_subjects SET updated_at = ? WHERE id = ?", (_now(), doc["subject_id"]))
        _delete_document_storage(doc["storage_path"])
        _debug("document_delete_done", document_id=document_id, subject_id=doc["subject_id"], filename=doc["filename"])
        return {"ok": True, "deleted_document_id": document_id}


@router.post("/quizzes/generate", status_code=status.HTTP_201_CREATED)
async def generate_quiz(req: QuizGenerateRequest, current_user: UserInDB = Depends(get_current_user)):
    _debug(
        "quiz_generate_start",
        user_id=current_user.id,
        subject_id=req.subject_id,
        topic=req.topic,
        question_type=req.question_type,
        count=req.count,
        difficulty=req.difficulty,
    )
    settings = get_user_llm_settings(current_user.id)
    with get_db() as conn:
        subject = _get_subject(conn, req.subject_id, current_user.id)
        local_context = await _retrieve_combined_context_deep_or_light(
            conn,
            settings,
            req.subject_id,
            subject["name"],
            current_user.id,
            req.topic,
            limit=max(5, req.count),
        )

    _debug(
        "quiz_generate_local_context_ready",
        subject_name=subject["name"],
        local_context_count=len(local_context),
        local_context_preview=[
            {
                "filename": item["filename"],
                "source_type": item.get("source_type"),
                "score": item["score"],
                "excerpt": item["excerpt"][:120],
            }
            for item in local_context[:3]
        ],
    )
    try:
        web_sources = await _fetch_web_sources(subject["name"], req.topic)
    except Exception as exc:
        _debug_exception(
            "quiz_generate_web_sources_failed_use_local_only",
            exc,
            subject_name=subject["name"],
            topic=req.topic,
        )
        web_sources = []
    if not web_sources:
        _debug(
            "quiz_generate_web_sources_unavailable_use_local_only",
            subject_name=subject["name"],
            topic=req.topic,
            local_context_count=len(local_context),
        )
        web_sources = [_local_only_web_source(subject["name"], req.topic)]
    _debug(
        "quiz_generate_web_sources_ready",
        web_source_count=len(web_sources),
        offline=all(bool(item.get("offline")) for item in web_sources),
        web_sources=[{"title": item.get("title"), "url": item.get("url"), "offline": bool(item.get("offline"))} for item in web_sources],
    )

    try:
        questions = await _generate_learning_questions_with_llm(
            current_user.id,
            subject["name"],
            req,
            local_context,
            web_sources,
        )
        _debug(
            "quiz_generate_llm_questions_ready",
            question_count=len(questions),
            previews=[{"seq_no": item["seq_no"], "type": item["type"], "prompt": item["prompt"][:140]} for item in questions[:5]],
        )
    except Exception as exc:
        _debug_exception(
            "quiz_generate_llm_questions_failed_fallback",
            exc,
            subject_name=subject["name"],
            topic=req.topic,
        )
        questions = []
        for i in range(req.count):
            q_type = _question_type_at(req.question_type, i)
            local = local_context[i % len(local_context)]
            web = web_sources[i % len(web_sources)]
            question = _build_question(i + 1, q_type, req.topic, req.difficulty, local, web)
            _debug(
                "quiz_generate_fallback_question_built",
                seq_no=i + 1,
                question_type=q_type,
                local_filename=local["filename"],
                web_title=web.get("title"),
                prompt_preview=question["prompt"][:140],
            )
            questions.append(question)

    quiz_id = str(uuid.uuid4())
    now = _now()
    title = f"{subject['name']} - {req.topic} 练习"
    local_sources = [
        {
            "document_id": item["document_id"],
            "filename": item["filename"],
            "source_type": item.get("source_type", "user_upload"),
            "excerpt": item["excerpt"][:180],
        }
        for item in local_context[:5]
    ]

    with get_db() as conn:
        _debug(
            "quiz_generate_db_insert_start",
            quiz_id=quiz_id,
            title=title,
            question_count=len(questions),
            local_source_count=len(local_sources),
            web_source_count=len(web_sources),
        )
        conn.execute(
            """INSERT INTO quiz_sets
               (id, user_id, subject_id, title, topic, question_type, count, difficulty,
                local_sources, web_sources, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                quiz_id,
                current_user.id,
                req.subject_id,
                title,
                req.topic,
                req.question_type,
                req.count,
                req.difficulty,
                json.dumps(local_sources, ensure_ascii=False),
                json.dumps(web_sources, ensure_ascii=False),
                now,
            ),
        )
        for question in questions:
            conn.execute(
                """INSERT INTO quiz_questions
                   (id, quiz_set_id, seq_no, question_type, prompt, options_json, answer_json,
                    explanation, local_citation, web_citation)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    question["id"],
                    quiz_id,
                    question["seq_no"],
                    question["type"],
                    question["prompt"],
                    json.dumps(question["options"], ensure_ascii=False),
                    json.dumps(question["answer"], ensure_ascii=False),
                    question["explanation"],
                    question["local_citation"],
                    question["web_citation"],
                ),
            )
        conn.execute("UPDATE study_subjects SET updated_at = ? WHERE id = ?", (now, req.subject_id))
        result = _serialize_quiz(conn, quiz_id)
        _debug("quiz_generate_done", quiz_id=quiz_id, question_count=len(result.get("questions", [])))
        return result


@router.get("/quizzes")
async def list_quizzes(
    subject_id: Optional[str] = None,
    current_user: UserInDB = Depends(get_current_user),
):
    query = [
        """SELECT qs.*, ss.name AS subject_name
           FROM quiz_sets qs
           JOIN study_subjects ss ON ss.id = qs.subject_id
           WHERE qs.user_id = ?"""
    ]
    params: List[Any] = [current_user.id]
    if subject_id:
        query.append("AND qs.subject_id = ?")
        params.append(subject_id)
    query.append("ORDER BY qs.created_at DESC LIMIT 80")

    with get_db() as conn:
        rows = conn.execute(" ".join(query), params).fetchall()
        return {
            "quizzes": [
                {
                    "id": row["id"],
                    "subject_id": row["subject_id"],
                    "subject_name": row["subject_name"],
                    "title": row["title"],
                    "topic": row["topic"],
                    "question_type": row["question_type"],
                    "count": row["count"],
                    "difficulty": row["difficulty"],
                    "created_at": row["created_at"],
                }
                for row in rows
            ]
        }


@router.patch("/quizzes/{quiz_id}")
async def rename_quiz(
    quiz_id: str,
    req: QuizRenameRequest,
    current_user: UserInDB = Depends(get_current_user),
):
    title = req.title.strip()
    if not title:
        raise HTTPException(status_code=400, detail="题组名称不能为空")

    with get_db() as conn:
        quiz = conn.execute(
            "SELECT id, subject_id, title FROM quiz_sets WHERE id = ? AND user_id = ?",
            (quiz_id, current_user.id),
        ).fetchone()
        if not quiz:
            raise HTTPException(status_code=404, detail="题目记录不存在")

        _debug(
            "quiz_rename_start",
            quiz_id=quiz_id,
            old_title=quiz["title"],
            new_title=title,
            user_id=current_user.id,
        )
        conn.execute(
            "UPDATE quiz_sets SET title = ? WHERE id = ? AND user_id = ?",
            (title, quiz_id, current_user.id),
        )
        conn.execute("UPDATE study_subjects SET updated_at = ? WHERE id = ?", (_now(), quiz["subject_id"]))
        result = _serialize_quiz(conn, quiz_id)
        _debug("quiz_rename_done", quiz_id=quiz_id, new_title=title)
        return result


@router.post("/quizzes/merge", status_code=status.HTTP_201_CREATED)
async def merge_quizzes(
    req: QuizMergeRequest,
    current_user: UserInDB = Depends(get_current_user),
):
    quiz_ids: List[str] = []
    seen_ids = set()
    for quiz_id in req.quiz_ids:
        clean_id = str(quiz_id).strip()
        if clean_id and clean_id not in seen_ids:
            quiz_ids.append(clean_id)
            seen_ids.add(clean_id)

    if len(quiz_ids) < 2:
        raise HTTPException(status_code=400, detail="至少选择两个历史题组才能合并")
    if len(quiz_ids) > 20:
        raise HTTPException(status_code=400, detail="一次最多合并 20 个历史题组")

    placeholders = ",".join("?" for _ in quiz_ids)
    now = _now()

    with get_db() as conn:
        rows = conn.execute(
            f"""SELECT qs.*, ss.name AS subject_name
                FROM quiz_sets qs
                JOIN study_subjects ss ON ss.id = qs.subject_id
                WHERE qs.user_id = ? AND qs.id IN ({placeholders})""",
            [current_user.id, *quiz_ids],
        ).fetchall()
        if len(rows) != len(quiz_ids):
            raise HTTPException(status_code=404, detail="部分题组不存在或无权访问")

        by_id = {row["id"]: row for row in rows}
        ordered_quizzes = [by_id[quiz_id] for quiz_id in quiz_ids]
        subject_ids = {row["subject_id"] for row in ordered_quizzes}
        if len(subject_ids) != 1:
            raise HTTPException(status_code=400, detail="只能合并同一学科下的历史题组")

        question_rows: List[Any] = []
        for quiz in ordered_quizzes:
            question_rows.extend(
                conn.execute(
                    "SELECT * FROM quiz_questions WHERE quiz_set_id = ? ORDER BY seq_no ASC",
                    (quiz["id"],),
                ).fetchall()
            )
        if not question_rows:
            raise HTTPException(status_code=400, detail="所选题组没有可合并的题目")

        def merge_sources(field_name: str) -> List[Dict[str, Any]]:
            merged: List[Dict[str, Any]] = []
            seen_sources = set()
            for quiz in ordered_quizzes:
                try:
                    sources = json.loads(quiz[field_name] or "[]")
                except Exception as exc:
                    _debug_exception("quiz_merge_source_parse_error", exc, quiz_id=quiz["id"], field=field_name)
                    sources = []
                for source in sources:
                    if not isinstance(source, dict):
                        continue
                    key = (
                        source.get("url")
                        or source.get("document_id")
                        or f"{source.get('filename', '')}:{source.get('title', '')}"
                        or json.dumps(source, ensure_ascii=False, sort_keys=True)
                    )
                    if key in seen_sources:
                        continue
                    seen_sources.add(key)
                    merged.append(source)
            return merged

        new_quiz_id = str(uuid.uuid4())
        subject_id = ordered_quizzes[0]["subject_id"]
        subject_name = ordered_quizzes[0]["subject_name"]
        title = req.title.strip() or ordered_quizzes[0]["title"] or f"{subject_name} - 合并练习"
        topics = list(dict.fromkeys([row["topic"] for row in ordered_quizzes if row["topic"]]))
        topic = " / ".join(topics)[:120] if topics else "合并练习"
        question_types = {row["question_type"] for row in ordered_quizzes if row["question_type"]}
        question_type = question_types.pop() if len(question_types) == 1 else "mixed"
        difficulties = [row["difficulty"] for row in ordered_quizzes if row["difficulty"]]
        difficulty = difficulties[0] if difficulties else "medium"
        local_sources = merge_sources("local_sources")
        web_sources = merge_sources("web_sources")

        _debug(
            "quiz_merge_start",
            user_id=current_user.id,
            quiz_ids=quiz_ids,
            new_quiz_id=new_quiz_id,
            title=title,
            question_count=len(question_rows),
        )
        conn.execute(
            """INSERT INTO quiz_sets
               (id, user_id, subject_id, title, topic, question_type, count, difficulty,
                local_sources, web_sources, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                new_quiz_id,
                current_user.id,
                subject_id,
                title,
                topic,
                question_type,
                len(question_rows),
                difficulty,
                json.dumps(local_sources, ensure_ascii=False),
                json.dumps(web_sources, ensure_ascii=False),
                now,
            ),
        )
        for seq_no, question in enumerate(question_rows, start=1):
            conn.execute(
                """INSERT INTO quiz_questions
                   (id, quiz_set_id, seq_no, question_type, prompt, options_json, answer_json,
                    explanation, local_citation, web_citation)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    str(uuid.uuid4()),
                    new_quiz_id,
                    seq_no,
                    question["question_type"],
                    question["prompt"],
                    question["options_json"],
                    question["answer_json"],
                    question["explanation"],
                    question["local_citation"],
                    question["web_citation"],
                ),
            )

        conn.execute(f"DELETE FROM quiz_questions WHERE quiz_set_id IN ({placeholders})", quiz_ids)
        conn.execute(
            f"DELETE FROM quiz_sets WHERE user_id = ? AND id IN ({placeholders})",
            [current_user.id, *quiz_ids],
        )
        conn.execute("UPDATE study_subjects SET updated_at = ? WHERE id = ?", (now, subject_id))

        result = _serialize_quiz(conn, new_quiz_id)
        _debug(
            "quiz_merge_done",
            new_quiz_id=new_quiz_id,
            merged_from=quiz_ids,
            question_count=len(result.get("questions", [])),
        )
        return result


@router.get("/quizzes/{quiz_id}")
async def get_quiz(quiz_id: str, current_user: UserInDB = Depends(get_current_user)):
    with get_db() as conn:
        quiz = _serialize_quiz(conn, quiz_id)
        if quiz["user_id"] != current_user.id:
            raise HTTPException(status_code=404, detail="题目记录不存在")
        return quiz


@router.delete("/quizzes/{quiz_id}")
async def delete_quiz(quiz_id: str, current_user: UserInDB = Depends(get_current_user)):
    with get_db() as conn:
        quiz = conn.execute(
            "SELECT id, subject_id, title FROM quiz_sets WHERE id = ? AND user_id = ?",
            (quiz_id, current_user.id),
        ).fetchone()
        if not quiz:
            raise HTTPException(status_code=404, detail="题目记录不存在")

        _debug("quiz_delete_start", quiz_id=quiz_id, subject_id=quiz["subject_id"], title=quiz["title"], user_id=current_user.id)
        conn.execute("DELETE FROM quiz_questions WHERE quiz_set_id = ?", (quiz_id,))
        conn.execute("DELETE FROM quiz_sets WHERE id = ? AND user_id = ?", (quiz_id, current_user.id))
        conn.execute("UPDATE study_subjects SET updated_at = ? WHERE id = ?", (_now(), quiz["subject_id"]))
        _debug("quiz_delete_done", quiz_id=quiz_id, subject_id=quiz["subject_id"])
        return {"ok": True, "deleted_quiz_id": quiz_id}
