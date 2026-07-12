"""
聊天会话路由 — 持久化历史聊天

接口：
  GET    /api/chat/sessions                  获取用户所有会话列表
  POST   /api/chat/sessions                  新建会话
  GET    /api/chat/sessions/{session_id}     获取单个会话（含所有消息）
  PATCH  /api/chat/sessions/{session_id}     重命名会话标题
  DELETE /api/chat/sessions/{session_id}     删除单个会话
  DELETE /api/chat/sessions                  清空所有会话
  POST   /api/chat/stream                    流式发送消息（自动存库）
  POST   /api/chat/message                   非流式发送消息
"""

import json
import traceback
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from database.db import get_db
from models.user import UserInDB
from services.auth_service import get_current_user
from services.llm_settings import complete_llm_json, get_user_llm_settings, stream_llm_text
from routers.study import retrieve_admin_knowledge_context

router = APIRouter()

# Pydantic 模型

class MessageItem(BaseModel):
    id: str
    session_id: str
    role: str
    content: str
    created_at: str


class SessionItem(BaseModel):
    id: str
    user_id: str
    title: str
    mode: str
    created_at: str
    updated_at: str
    last_message: Optional[str] = None


class SessionDetail(SessionItem):
    messages: List[MessageItem] = []


class CreateSessionRequest(BaseModel):
    mode: str = "general"
    title: str = "新对话"


class RenameSessionRequest(BaseModel):
    title: str


class ChatRequest(BaseModel):
    session_id: str
    content: str
    mode: str = "general"


# 工具函数

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _chat_rag_debug(step: str, **data: Any) -> None:
    safe_data = json.dumps(data, ensure_ascii=False, default=str)
    if len(safe_data) > 4000:
        safe_data = safe_data[:4000] + "...<truncated>"
    print(f"[AetherStudy:RAG DEBUG] chat_{step} | {safe_data}", flush=True)


def _chat_rag_debug_exception(step: str, exc: Exception, **data: Any) -> None:
    _chat_rag_debug(
        step,
        error_type=type(exc).__name__,
        error=str(exc),
        traceback=traceback.format_exc(limit=3),
        **data,
    )


def _format_admin_knowledge_context(context: List[Dict[str, Any]]) -> str:
    if not context:
        return ""
    parts = []
    for index, item in enumerate(context, 1):
        parts.append(
            f"[{index}] 来源={item.get('filename')}；主题={item.get('subject_name') or '管理员知识库'}；"
            f"内容={item.get('excerpt', '')[:700]}"
        )
    return "\n".join(parts)


def _get_session_or_404(conn, session_id: str, user_id: str):
    row = conn.execute(
        "SELECT * FROM chat_sessions WHERE id=? AND user_id=?",
        (session_id, user_id)
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="会话不存在")
    return row


def _save_message(conn, session_id: str, role: str, content: str) -> str:
    msg_id = str(uuid.uuid4())
    conn.execute(
        "INSERT INTO chat_messages (id, session_id, role, content, created_at) VALUES (?,?,?,?,?)",
        (msg_id, session_id, role, content, now_iso())
    )
    return msg_id


def _touch_session(conn, session_id: str, title: Optional[str] = None):
    now = now_iso()
    if title:
        conn.execute(
            "UPDATE chat_sessions SET updated_at=?, title=? WHERE id=?",
            (now, title, session_id)
        )
    else:
        conn.execute("UPDATE chat_sessions SET updated_at=? WHERE id=?", (now, session_id))


def _row_to_session(row, last_message: str = None) -> dict:
    return {
        "id": row["id"], "user_id": row["user_id"],
        "title": row["title"], "mode": row["mode"],
        "created_at": row["created_at"], "updated_at": row["updated_at"],
        "last_message": last_message,
    }


#  会话 CRUD 

@router.get("/sessions", response_model=List[SessionItem])
async def list_sessions(current_user: UserInDB = Depends(get_current_user)):
    with get_db() as conn:
        sessions = conn.execute(
            "SELECT * FROM chat_sessions WHERE user_id=? ORDER BY updated_at DESC",
            (current_user.id,)
        ).fetchall()
        result = []
        for s in sessions:
            last = conn.execute(
                "SELECT content FROM chat_messages WHERE session_id=? ORDER BY created_at DESC LIMIT 1",
                (s["id"],)
            ).fetchone()
            preview = None
            if last:
                c = last["content"]
                preview = (c[:60] + "…") if len(c) > 60 else c
            result.append(_row_to_session(s, preview))
        return result


@router.post("/sessions", response_model=SessionDetail)
async def create_session(
    req: CreateSessionRequest,
    current_user: UserInDB = Depends(get_current_user)
):
    session_id = str(uuid.uuid4())
    now = now_iso()
    with get_db() as conn:
        conn.execute(
            "INSERT INTO chat_sessions (id, user_id, title, mode, created_at, updated_at) VALUES (?,?,?,?,?,?)",
            (session_id, current_user.id, req.title, req.mode, now, now)
        )
    return SessionDetail(
        id=session_id, user_id=current_user.id,
        title=req.title, mode=req.mode,
        created_at=now, updated_at=now, messages=[]
    )


@router.get("/sessions/{session_id}", response_model=SessionDetail)
async def get_session(session_id: str, current_user: UserInDB = Depends(get_current_user)):
    with get_db() as conn:
        s = _get_session_or_404(conn, session_id, current_user.id)
        msgs = conn.execute(
            "SELECT * FROM chat_messages WHERE session_id=? ORDER BY created_at ASC",
            (session_id,)
        ).fetchall()
    messages = [
        MessageItem(id=m["id"], session_id=m["session_id"],
                    role=m["role"], content=m["content"], created_at=m["created_at"])
        for m in msgs
    ]
    return SessionDetail(**_row_to_session(s), messages=messages)


@router.patch("/sessions/{session_id}", response_model=SessionItem)
async def rename_session(
    session_id: str, req: RenameSessionRequest,
    current_user: UserInDB = Depends(get_current_user)
):
    with get_db() as conn:
        _get_session_or_404(conn, session_id, current_user.id)
        _touch_session(conn, session_id, title=req.title.strip() or "新对话")
        row = conn.execute("SELECT * FROM chat_sessions WHERE id=?", (session_id,)).fetchone()
        return _row_to_session(row)


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str, current_user: UserInDB = Depends(get_current_user)):
    with get_db() as conn:
        _get_session_or_404(conn, session_id, current_user.id)
        conn.execute("DELETE FROM chat_sessions WHERE id=?", (session_id,))
    return {"status": "deleted", "session_id": session_id}


@router.delete("/sessions")
async def clear_all_sessions(current_user: UserInDB = Depends(get_current_user)):
    with get_db() as conn:
        conn.execute("DELETE FROM chat_sessions WHERE user_id=?", (current_user.id,))
    return {"status": "cleared"}


# 流式聊天（核心，自动持久化）

@router.post("/stream")
async def chat_stream(req: ChatRequest, current_user: UserInDB = Depends(get_current_user)):
    """
    整合版：流式发送消息 + 自动持久化 + 画像提取
    """
    with get_db() as conn:
        # 验证会话并获取历史画像上下文
        _get_session_or_404(conn, req.session_id, current_user.id)
        
        # 获取用户最新的画像数据（如果存在）
        profile_row = conn.execute(
            "SELECT profile_json FROM student_profiles WHERE user_id = ?", 
            (current_user.id,)
        ).fetchone()
        profile_context = json.loads(profile_row["profile_json"]) if profile_row else {}

        # 保存当前用户发送的消息
        _save_message(conn, req.session_id, "user", req.content)
        
        # 构建发送给 LLM 的历史消息列表（从数据库取最近 10 条，保证不超出 token）
        history_rows = conn.execute(
            "SELECT role, content FROM chat_messages WHERE session_id = ? ORDER BY created_at ASC LIMIT 20",
            (req.session_id,)
        ).fetchall()

    async def event_stream():
        # --- 构造 System Prompt ---
        system_content = "你是一个专业的 AI 学习助手 AetherStudy。"
        settings = get_user_llm_settings(current_user.id)
        admin_knowledge_context: List[Dict[str, Any]] = []
        try:
            admin_knowledge_context = await retrieve_admin_knowledge_context(settings, req.content, subject_name="all", limit=4)
            _chat_rag_debug(
                "admin_knowledge_context_ready",
                user_id=current_user.id,
                session_id=req.session_id,
                context_count=len(admin_knowledge_context),
                sources=[
                    {"filename": item.get("filename"), "score": item.get("score"), "excerpt": item.get("excerpt", "")[:120]}
                    for item in admin_knowledge_context
                ],
            )
        except Exception as exc:
            _chat_rag_debug_exception(
                "admin_knowledge_context_failed_continue_without_rag",
                exc,
                user_id=current_user.id,
                session_id=req.session_id,
            )

        admin_knowledge_text = _format_admin_knowledge_context(admin_knowledge_context)
        if admin_knowledge_text:
            system_content += (
                "\n\n[管理员持久知识库检索结果]\n"
                f"{admin_knowledge_text}\n"
                "请优先结合这些服务器端持久资料回答；如果资料不足，再明确说明需要补充材料。"
            )

        if req.mode == "profile_building":
            system_content += "当前任务：引导用户建立学习画像。请了解其专业、薄弱点、目标及偏好。"
        else:
            system_content += f"请根据用户的画像上下文提供针对性辅导：{json.dumps(profile_context, ensure_ascii=False)}"

        messages = [{"role": "system", "content": system_content}]
        for row in history_rows:
            messages.append({"role": row["role"], "content": row["content"]})

        full_content = ""

        # --- 调用用户配置的 OpenAI 兼容 API ---
        try:
            async for delta in stream_llm_text(settings, messages):
                if delta:
                    full_content += delta
                    yield f"data: {json.dumps({'type': 'delta', 'content': delta}, ensure_ascii=False)}\n\n"

            # --- AI 回复结束，进行持久化 ---
            with get_db() as conn:
                # 保存 AI 回复到数据库
                ai_msg_id = _save_message(conn, req.session_id, "assistant", full_content)
                
                # 如果是第一条消息，自动更新会话标题
                count = conn.execute(
                    "SELECT COUNT(*) as c FROM chat_messages WHERE session_id=?", (req.session_id,)
                ).fetchone()["c"]
                new_title = (req.content[:20] + "...") if count <= 2 else None
                _touch_session(conn, req.session_id, title=new_title)

            extracted = None
            if req.mode == "profile_building":
                try:
                    # 建议同时传入 user_input 和 ai_response
                    extract_prompt = f"""
                        你是一个资深的教育数据分析师。请分析以下对话片段，从中提取或更新用户的个人画像特征。

                        [对话上下文]
                        用户提问："{req.content}"
                        AI 助手回复："{full_content}"
                        这是已有的用户画像上下文: {json.dumps(profile_context, ensure_ascii=False)}

                        [提取要求]
                        1. 仅提取对话中明确提到或强烈暗示的信息。
                        2. "description" 必须使用第二人称（如“你...”），总结用户的学科背景、当前遇到的阻碍及学习动力。
                        3. "weak_points" 和 "learning_goals" 必须是具体的知识点或任务，不要使用笼统的词汇。
                        4. 严格遵守 JSON 格式，若某项信息未提及且你没有把握，则对应字段填为 null 或 []。
                        5. 我需要你在原有画像基础上修改和补充，而不是完全重写。也就是说，如果对话中没有提到某个维度的信息，就保持原来的值不变。如果有所冲突，根据最新画像为准
                        6. 如果画像已有的的信息不需要修改就返回 null

                        [输出格式]
                        {{
                            "major": "专业名称或 null",
                            "school": "学校名称或 null",
                            "grade": "年级或 null",
                            "weak_points": ["知识点1", "知识点2"],
                            "learning_goals": ["目标1", "目标2"],
                            "cognition_style": "认知风格或 null",
                            "learning_pace": "学习节奏或 null",
                            "description": "对用户学习状态的精准深度画像总结或者 null"
                        }}
                        """
                    extracted = await complete_llm_json(
                        settings,
                        [
                            {"role": "system", "content": "You are a helpful assistant that outputs JSON."},
                            {"role": "user", "content": extract_prompt}
                        ]
                    )

                    print(f"[*] klog 提取到的画像特征: {json.dumps(extracted, ensure_ascii=False)}")
                    
                    # 将提取到的画像持久化到 student_profiles 表
                    with get_db() as conn:
                        conn.execute("""
                            INSERT INTO student_profiles (user_id, profile_json, updated_at)
                            VALUES (?, ?, ?)
                            ON CONFLICT(user_id) DO UPDATE SET 
                                profile_json = excluded.profile_json,
                                updated_at = excluded.updated_at
                        """, (current_user.id, json.dumps(extracted, ensure_ascii=False), now_iso()))
                except Exception as e:
                    print(f"[*] klog 画像更新失败: {e}")

            # --- 发送完成信号 ---
            yield f"""data: {json.dumps({
                'type': 'done', 
                'ai_message_id': ai_msg_id, 
                'extracted_features': extracted,
                'new_title': new_title
            }, ensure_ascii=False)}\n\n"""

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )

@router.post("/message")
async def chat_message(req: ChatRequest, current_user: UserInDB = Depends(get_current_user)):
    """非流式备用接口"""
    with get_db() as conn:
        _get_session_or_404(conn, req.session_id, current_user.id)
        _save_message(conn, req.session_id, "user", req.content)

    ai_content = f"收到你的消息：{req.content[:40]}..."

    with get_db() as conn:
        _save_message(conn, req.session_id, "assistant", ai_content)
        _touch_session(conn, req.session_id)

    return {"content": ai_content, "session_id": req.session_id}
