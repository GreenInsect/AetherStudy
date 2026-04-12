"""
资源生成相关数据模型
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from enum import Enum
from datetime import datetime


class ResourceType(str, Enum):
    """资源类型 - 至少5种"""
    DOCUMENT = "document"       # 课程讲解文档
    MIND_MAP = "mind_map"       # 思维导图
    QUIZ = "quiz"               # 练习题目
    READING = "reading"         # 拓展阅读
    VIDEO_SCRIPT = "video_script"  # 教学视频脚本/动画
    CODE_CASE = "code_case"     # 代码实操案例
    PPT = "ppt"                 # PPT课件
    FLASHCARD = "flashcard"     # 记忆卡片


class GenerationStatus(str, Enum):
    PENDING = "pending"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"


class ResourceGenerationRequest(BaseModel):
    """资源生成请求"""
    user_id: str
    resource_types: List[ResourceType]
    topic: str                          # 主题/知识点
    course: Optional[str] = None        # 课程名称
    difficulty: Optional[str] = "medium"  # easy/medium/hard
    context: Optional[str] = None       # 额外上下文（来自画像）
    language: str = "zh"


class ResourceItem(BaseModel):
    """单个资源条目"""
    id: str
    type: ResourceType
    title: str
    content: Any                        # 具体内容，结构因类型而异
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    agent_id: str = ""                  # 生成该资源的智能体ID


class GenerationTask(BaseModel):
    """生成任务"""
    task_id: str
    user_id: str
    status: GenerationStatus = GenerationStatus.PENDING
    progress: float = 0.0              # 0-1
    resources: List[ResourceItem] = Field(default_factory=list)
    error: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ========== 具体资源内容结构 ==========

class DocumentContent(BaseModel):
    """课程文档内容"""
    sections: List[Dict[str, str]]     # [{title, content}]
    summary: str
    key_concepts: List[str]


class MindMapContent(BaseModel):
    """思维导图内容（Mermaid格式）"""
    mermaid_code: str
    root_node: str
    node_count: int


class QuizContent(BaseModel):
    """题目内容"""
    questions: List[Dict[str, Any]]    # [{type, question, options, answer, explanation}]
    total_count: int
    difficulty_distribution: Dict[str, int]


class CodeCaseContent(BaseModel):
    """代码案例内容"""
    language: str
    description: str
    code: str
    explanation: str
    run_command: Optional[str] = None
    expected_output: Optional[str] = None
