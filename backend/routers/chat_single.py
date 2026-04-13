"""
对话路由 - 支持流式输出
"""

import asyncio
import json
import os
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from openai import AsyncOpenAI
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("DEEPSEEK_API_KEY")
base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
client = AsyncOpenAI(
    api_key=api_key,
    base_url=base_url
)

router = APIRouter()


class ChatMessage(BaseModel):
    role: str           # "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    user_id: str
    messages: List[ChatMessage]
    mode: str = "general"   # general | profile_building | tutoring
    profile_context: Optional[Dict[str, Any]] = None


class ChatResponse(BaseModel):
    message: str
    extracted_features: Optional[Dict[str, Any]] = None
    suggested_actions: List[str] = []


async def stream_chat_response(request: ChatRequest):
    """
    接入 DeepSeek 流式调用
    """

    system_content = "你是一个专业的 AI 学习助手 AetherStudy。"

    # print("[*] klog request:", request)  # 调试日志

    if request.mode == "profile_building":
        system_content += (
            "当前任务：引导用户建立学习画像。请通过交流，了解用户的专业背景、"
            "目前的知识薄弱点、学习目标及偏好的学习方式（视频/文档/练习）。"
            "你的语气应当亲切且具有引导性。"
        )
    else:
        system_content += f"请根据用户的画像上下文提供针对性辅导：{json.dumps(request.profile_context)}"

    messages = [{"role": "system", "content": system_content}]
    for msg in request.messages:
        messages.append({"role": msg.role, "content": msg.content})

    full_content = ""
    
    try:
        response = await client.chat.completions.create(
            model="deepseek-chat",  
            messages=messages,
            stream=True
        )

        async for chunk in response:
            delta = chunk.choices[0].delta.content or ""
            if delta:
                full_content += delta
                yield f"data: {json.dumps({'type': 'delta', 'content': delta})}\n\n"

        # 调用 LLM 提取画像特征
        try:
            # 构建一个专门用于提取信息的 Prompt
            extract_prompt = f"""
            你是一个教育专家。请分析以下 AI 助手与用户的对话内容，提取用户的个人画像信息。
            
            对话内容：
            "{full_content}"
            
            请严格按照以下 JSON 格式返回，不要包含任何其他文字：
            {{
                "major": "专业名称或 null",
                "weak_points": ["薄弱知识点1", "薄弱知识点2"],
                "learning_goals": ["学习目标1", "学习目标2"],
                "description": "一段简短的总结话语，描述用户的当前学习状态,兴趣和需求或者其他个人画像信息"
            }}
            """

            # 使用非流式调用获取 JSON 结果
            extract_response = await client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "system", "content": "You are a helpful assistant that outputs JSON."},
                          {"role": "user", "content": extract_prompt}],
                response_format={'type': 'json_object'} # 强制返回 JSON 格式
            )
            print("[*] klog extract_response:", extract_response)  # 调试日志

            extracted = json.loads(extract_response.choices[0].message.content)

        except Exception as e:
            print(f"画像提取失败: {e}")
            # 失败时的保底方案
            extracted = {
                "major": None,
                "weak_points": [],
                "learning_goals": [],
                "description": "暂时无法生成画像总结。"
            }

        yield f"data: {json.dumps({'type': 'done', 'extracted_features': extracted})}\n\n"

    except Exception as e:
        yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"

@router.post("/stream")
async def chat_stream(request: ChatRequest):
    """流式对话接口"""
    return StreamingResponse(
        stream_chat_response(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        }
    )


@router.post("/message")
async def chat_message(request: ChatRequest) -> ChatResponse:
    """
    非流式对话接口：一次性返回完整回答和画像提取结果
    """
    try:
        system_content = "你是一个专业的 AI 学习助手 AetherStudy。"
        if request.mode == "profile_building":
            system_content += "当前任务：通过对话引导用户完善学习画像。"
        
        messages = [{"role": "system", "content": system_content}]
        for msg in request.messages:
            messages.append({"role": msg.role, "content": msg.content})

        main_response = await client.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
            stream=False  # 非流式
        )
        
        full_text = main_response.choices[0].message.content

        extract_prompt = f"""
        基于以下对话内容，提取用户的学习画像：
        "{full_text}"
        
        严格按 JSON 返回：
        {{
            "major": "专业",
            "weak_points": ["知识点"],
            "learning_goals": ["目标"],
            "description": "一句话总结"
        }}
        """
        
        extract_res = await client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that outputs JSON."},
                {"role": "user", "content": extract_prompt}
            ],
            response_format={'type': 'json_object'}
        )
        
        extracted = json.loads(extract_res.choices[0].message.content)

        actions = ["查看详细路径", "生成针对性练习"]
        if "项目" in full_text or "实战" in full_text:
            actions.append("推荐开源项目")

        return ChatResponse(
            message=full_text,
            extracted_features=extracted,
            suggested_actions=actions
        )

    except Exception as e:
        return ChatResponse(
            message=f"抱歉，服务遇到了点问题：{str(e)}",
            extracted_features=None,
            suggested_actions=[]
        )