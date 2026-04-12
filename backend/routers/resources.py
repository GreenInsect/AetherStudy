"""
资源生成路由 - 支持SSE流式进度推送
"""

import json
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from agents.orchestrator import orchestrator
from models.resources import ResourceGenerationRequest, ResourceType

router = APIRouter()


@router.post("/generate/stream")
async def generate_resources_stream(request: ResourceGenerationRequest):
    """
    流式资源生成接口
    前端通过 EventSource 接收实时进度
    """
    task_id = await orchestrator.create_task(request.dict())
    
    async def event_stream():
        async for event in orchestrator.execute_task_stream(task_id, request.dict()):
            yield f"data: {json.dumps(event, ensure_ascii=False, default=str)}\n\n"
    
    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )


@router.post("/generate")
async def generate_resources(request: ResourceGenerationRequest):
    """非流式资源生成（等待全部完成）"""
    task_id = await orchestrator.create_task(request.dict())
    
    # 执行所有智能体
    async for _ in orchestrator.execute_task_stream(task_id, request.dict()):
        pass
    
    task = orchestrator.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return {
        "task_id": task_id,
        "status": task.status,
        "resources": [r.dict() for r in task.resources]
    }


@router.get("/task/{task_id}")
async def get_task_status(task_id: str):
    """查询任务状态"""
    task = orchestrator.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.get("/types")
async def get_resource_types():
    """获取所有支持的资源类型"""
    return {
        "types": [
            {"id": ResourceType.DOCUMENT, "name": "课程讲解文档", "icon": "📄"},
            {"id": ResourceType.MIND_MAP, "name": "知识思维导图", "icon": "🗺️"},
            {"id": ResourceType.QUIZ, "name": "练习题库", "icon": "📝"},
            {"id": ResourceType.READING, "name": "拓展阅读", "icon": "📚"},
            {"id": ResourceType.VIDEO_SCRIPT, "name": "教学视频/动画", "icon": "🎬"},
            {"id": ResourceType.CODE_CASE, "name": "代码实操案例", "icon": "💻"},
            {"id": ResourceType.PPT, "name": "PPT课件", "icon": "📊"},
            {"id": ResourceType.FLASHCARD, "name": "记忆闪卡", "icon": "🃏"},
        ]
    }
