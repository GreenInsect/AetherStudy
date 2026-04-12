"""学习路径路由"""
from fastapi import APIRouter
from pydantic import BaseModel
from typing import List, Optional, Dict

router = APIRouter()


class LearningStep(BaseModel):
    step_no: int
    title: str
    description: str
    resource_types: List[str]
    estimated_hours: float
    prerequisites: List[str] = []
    status: str = "pending"  # pending/in_progress/completed


class LearningPath(BaseModel):
    user_id: str
    course: str
    total_steps: int
    estimated_total_hours: float
    steps: List[LearningStep]
    current_step: int = 0


@router.post("/generate")
async def generate_learning_path(user_id: str, course: str, profile_context: Optional[Dict] = None):
    """
    生成个性化学习路径
    【待实现】基于学生画像调用LLM规划学习路径
    """
    # TODO: 根据画像和课程信息生成真实路径
    path = LearningPath(
        user_id=user_id,
        course=course,
        total_steps=5,
        estimated_total_hours=20.0,
        steps=[
            LearningStep(
                step_no=1, title="基础概念导入", description="了解核心术语和基础理论",
                resource_types=["document", "mind_map"], estimated_hours=2.0
            ),
            LearningStep(
                step_no=2, title="理论深化", description="系统学习核心知识点",
                resource_types=["document", "video_script"], estimated_hours=5.0,
                prerequisites=["step_1"]
            ),
            LearningStep(
                step_no=3, title="实践练习", description="通过题目巩固理解",
                resource_types=["quiz"], estimated_hours=3.0, prerequisites=["step_2"]
            ),
            LearningStep(
                step_no=4, title="案例实操", description="代码/项目实践",
                resource_types=["code_case"], estimated_hours=6.0, prerequisites=["step_3"]
            ),
            LearningStep(
                step_no=5, title="综合评估", description="测验与总结",
                resource_types=["quiz"], estimated_hours=4.0, prerequisites=["step_4"]
            ),
        ]
    )
    return path


@router.get("/{user_id}")
async def get_learning_path(user_id: str):
    """获取当前学习路径"""
    # TODO: 从数据库获取
    return {"message": "No active learning path", "user_id": user_id}


@router.patch("/{user_id}/progress")
async def update_progress(user_id: str, step_no: int, status: str):
    """更新学习进度"""
    # TODO: 更新数据库
    return {"status": "updated", "step_no": step_no, "new_status": status}
