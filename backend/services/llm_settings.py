"""用户 LLM 配置读取与 OpenAI 兼容调用工具。"""

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx
from fastapi import HTTPException
from openai import AsyncOpenAI

from database.db import get_db


DEFAULT_LLM_SETTINGS: Dict[str, Any] = {
    "provider": "OpenAI",
    "model": "gpt-5.4",
    "review_model": "gpt-5.5",
    "base_url": "https://api.dstopology.com/v1",
    "wire_api": "responses",
    "reasoning_effort": "xhigh",
    "disable_response_storage": True,
    "network_access": "enabled",
    "context_window": 400000,
    "auto_compact_token_limit": 360000,
}


@dataclass
class LLMSettings:
    provider: str
    model: str
    review_model: str
    base_url: str
    api_key: str
    wire_api: str
    reasoning_effort: str
    disable_response_storage: bool
    network_access: str
    context_window: int
    auto_compact_token_limit: int
    updated_at: Optional[str] = None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _env_api_key() -> str:
    return (
        os.getenv("OPENAI_API_KEY")
        or os.getenv("DEEPSEEK_API_KEY")
        or os.getenv("OPENAI_ADMIN_KEY")
        or ""
    )


def _env_base_url() -> str:
    return os.getenv("OPENAI_BASE_URL") or os.getenv("DEEPSEEK_BASE_URL") or DEFAULT_LLM_SETTINGS["base_url"]


def _row_to_settings(row) -> LLMSettings:
    return LLMSettings(
        provider=row["provider"],
        model=row["model"],
        review_model=row["review_model"],
        base_url=row["base_url"],
        api_key=row["api_key"],
        wire_api=row["wire_api"],
        reasoning_effort=row["reasoning_effort"],
        disable_response_storage=bool(row["disable_response_storage"]),
        network_access=row["network_access"],
        context_window=int(row["context_window"]),
        auto_compact_token_limit=int(row["auto_compact_token_limit"]),
        updated_at=row["updated_at"],
    )


def get_user_llm_settings(user_id: str) -> LLMSettings:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM user_llm_settings WHERE user_id = ?", (user_id,)).fetchone()
    if row:
        return _row_to_settings(row)

    return LLMSettings(
        provider=DEFAULT_LLM_SETTINGS["provider"],
        model=os.getenv("OPENAI_MODEL", DEFAULT_LLM_SETTINGS["model"]),
        review_model=os.getenv("OPENAI_REVIEW_MODEL", DEFAULT_LLM_SETTINGS["review_model"]),
        base_url=_env_base_url(),
        api_key=_env_api_key(),
        wire_api=DEFAULT_LLM_SETTINGS["wire_api"],
        reasoning_effort=DEFAULT_LLM_SETTINGS["reasoning_effort"],
        disable_response_storage=DEFAULT_LLM_SETTINGS["disable_response_storage"],
        network_access=DEFAULT_LLM_SETTINGS["network_access"],
        context_window=DEFAULT_LLM_SETTINGS["context_window"],
        auto_compact_token_limit=DEFAULT_LLM_SETTINGS["auto_compact_token_limit"],
        updated_at=None,
    )


def save_user_llm_settings(user_id: str, payload: Dict[str, Any]) -> LLMSettings:
    current = get_user_llm_settings(user_id)
    api_key = payload.get("api_key")
    merged = {
        "provider": payload.get("provider") or current.provider or DEFAULT_LLM_SETTINGS["provider"],
        "model": payload.get("model") or current.model or DEFAULT_LLM_SETTINGS["model"],
        "review_model": payload.get("review_model") or current.review_model or DEFAULT_LLM_SETTINGS["review_model"],
        "base_url": payload.get("base_url") or current.base_url or DEFAULT_LLM_SETTINGS["base_url"],
        "api_key": current.api_key if api_key is None else api_key,
        "wire_api": payload.get("wire_api") or current.wire_api or DEFAULT_LLM_SETTINGS["wire_api"],
        "reasoning_effort": payload.get("reasoning_effort") or current.reasoning_effort or DEFAULT_LLM_SETTINGS["reasoning_effort"],
        "disable_response_storage": bool(payload.get("disable_response_storage", current.disable_response_storage)),
        "network_access": payload.get("network_access") or current.network_access or DEFAULT_LLM_SETTINGS["network_access"],
        "context_window": int(payload.get("context_window") or current.context_window or DEFAULT_LLM_SETTINGS["context_window"]),
        "auto_compact_token_limit": int(
            payload.get("auto_compact_token_limit")
            or current.auto_compact_token_limit
            or DEFAULT_LLM_SETTINGS["auto_compact_token_limit"]
        ),
        "updated_at": _now(),
    }

    with get_db() as conn:
        conn.execute(
            """INSERT INTO user_llm_settings
               (user_id, provider, model, review_model, base_url, api_key, wire_api,
                reasoning_effort, disable_response_storage, network_access,
                context_window, auto_compact_token_limit, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(user_id) DO UPDATE SET
                provider = excluded.provider,
                model = excluded.model,
                review_model = excluded.review_model,
                base_url = excluded.base_url,
                api_key = excluded.api_key,
                wire_api = excluded.wire_api,
                reasoning_effort = excluded.reasoning_effort,
                disable_response_storage = excluded.disable_response_storage,
                network_access = excluded.network_access,
                context_window = excluded.context_window,
                auto_compact_token_limit = excluded.auto_compact_token_limit,
                updated_at = excluded.updated_at""",
            (
                user_id,
                merged["provider"],
                merged["model"],
                merged["review_model"],
                merged["base_url"],
                merged["api_key"],
                merged["wire_api"],
                merged["reasoning_effort"],
                1 if merged["disable_response_storage"] else 0,
                merged["network_access"],
                merged["context_window"],
                merged["auto_compact_token_limit"],
                merged["updated_at"],
            ),
        )
    return get_user_llm_settings(user_id)


def public_llm_settings(settings: LLMSettings) -> Dict[str, Any]:
    return {
        "provider": settings.provider,
        "model": settings.model,
        "review_model": settings.review_model,
        "base_url": settings.base_url,
        "wire_api": settings.wire_api,
        "reasoning_effort": settings.reasoning_effort,
        "disable_response_storage": settings.disable_response_storage,
        "network_access": settings.network_access,
        "context_window": settings.context_window,
        "auto_compact_token_limit": settings.auto_compact_token_limit,
        "has_api_key": bool(settings.api_key),
        "updated_at": settings.updated_at,
    }


def build_openai_client(settings: LLMSettings) -> AsyncOpenAI:
    if not settings.api_key:
        raise HTTPException(status_code=400, detail="请先在账户设置中配置 OPENAI_API_KEY")
    return AsyncOpenAI(api_key=settings.api_key, base_url=settings.base_url)


def _responses_url(settings: LLMSettings) -> str:
    return f"{settings.base_url.rstrip('/')}/responses"


def _headers(settings: LLMSettings) -> Dict[str, str]:
    if not settings.api_key:
        raise HTTPException(status_code=400, detail="请先在账户设置中配置 OPENAI_API_KEY")
    return {
        "Authorization": f"Bearer {settings.api_key}",
        "Content-Type": "application/json",
    }


def _responses_payload(
    settings: LLMSettings,
    messages: List[Dict[str, str]],
    stream: bool = False,
    model: Optional[str] = None,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "model": model or settings.model,
        "input": messages,
        "stream": stream,
    }
    if settings.reasoning_effort:
        payload["reasoning"] = {"effort": settings.reasoning_effort}
    if settings.disable_response_storage:
        payload["store"] = False
    return payload


def _extract_responses_text(data: Dict[str, Any]) -> str:
    if data.get("output_text"):
        return data["output_text"]

    chunks: List[str] = []
    for output in data.get("output", []) or []:
        for content in output.get("content", []) or []:
            text = content.get("text") or content.get("output_text")
            if text:
                chunks.append(text)
    return "".join(chunks)


async def stream_llm_text(settings: LLMSettings, messages: List[Dict[str, str]]) -> AsyncGenerator[str, None]:
    """按用户配置流式输出文本，支持 responses 与 chat_completions 两种 wire API。"""
    if settings.wire_api == "responses":
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream(
                "POST",
                _responses_url(settings),
                headers=_headers(settings),
                json=_responses_payload(settings, messages, stream=True),
            ) as response:
                if response.status_code >= 400:
                    detail = await response.aread()
                    raise HTTPException(status_code=response.status_code, detail=detail.decode("utf-8", errors="ignore"))
                seen_delta = False
                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    raw = line[6:].strip()
                    if not raw or raw == "[DONE]":
                        continue
                    try:
                        event = json.loads(raw)
                    except json.JSONDecodeError:
                        continue
                    if event.get("type") == "response.output_text.delta" and event.get("delta"):
                        seen_delta = True
                        yield event["delta"]
                    elif event.get("type") == "response.completed":
                        text = _extract_responses_text(event.get("response") or {})
                        if text and not seen_delta:
                            yield text
        return

    client = build_openai_client(settings)
    response = await client.chat.completions.create(
        model=settings.model,
        messages=messages,
        stream=True,
    )
    async for chunk in response:
        delta = chunk.choices[0].delta.content or ""
        if delta:
            yield delta


async def complete_llm_json(settings: LLMSettings, messages: List[Dict[str, str]]) -> Dict[str, Any]:
    """按用户配置生成 JSON，用于画像抽取等结构化任务。"""
    if settings.wire_api == "responses":
        payload = _responses_payload(settings, messages, stream=False, model=settings.review_model or settings.model)
        payload["text"] = {"format": {"type": "json_object"}}
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(_responses_url(settings), headers=_headers(settings), json=payload)
            if response.status_code >= 400:
                raise HTTPException(status_code=response.status_code, detail=response.text)
            content = _extract_responses_text(response.json())
            return json.loads(content)

    client = build_openai_client(settings)
    response = await client.chat.completions.create(
        model=settings.review_model or settings.model,
        messages=messages,
        response_format={"type": "json_object"},
    )
    return json.loads(response.choices[0].message.content)
