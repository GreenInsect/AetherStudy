"""
学生画像数据模型
包含6+个维度的动态画像定义
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from enum import Enum
from datetime import datetime


class CognitionStyle(str, Enum):
    """认知风格"""
    VISUAL = "visual"        # 视觉型
    AUDITORY = "auditory"    # 听觉型
    READING = "reading"      # 阅读型
    KINESTHETIC = "kinesthetic"  # 动手型


class LearningPace(str, Enum):
    """学习节奏"""
    FAST = "fast"
    MEDIUM = "medium"
    SLOW = "slow"


class StudentProfile(BaseModel):
    """
    学生画像模型 - 包含6个核心维度
    """
    user_id: str
    
    # 维度1：基本信息
    major: Optional[str] = None           # 专业
    grade: Optional[str] = None           # 年级
    school: Optional[str] = None          # 学校
    description: Optional[str] = None     # 个人简介
    
    # 维度2：知识基础
    knowledge_foundation: Dict[str, int] = Field(
        default_factory=dict,
        description="各科目知识掌握程度 0-100"
    )
    
    # 维度3：认知风格
    cognition_style: Optional[CognitionStyle] = None
    
    # 维度4：学习目标
    learning_goals: List[str] = Field(default_factory=list)
    current_courses: List[str] = Field(default_factory=list)
    
    # 维度5：易错点与薄弱点
    weak_points: List[str] = Field(default_factory=list)
    error_prone_areas: Dict[str, List[str]] = Field(default_factory=dict)
    
    # 维度6：学习偏好
    learning_pace: Optional[str] = None
    preferred_resource_types: List[str] = Field(default_factory=list)  # video/doc/quiz/case
    study_time_per_day: Optional[int] = None  # 分钟
    
    # 维度7：学习历史与进度
    completed_topics: List[str] = Field(default_factory=list)
    learning_history: List[Dict[str, Any]] = Field(default_factory=list)
    
    # 维度8：画像完整度
    profile_completeness: float = 0.0   # 0-1
    last_updated: datetime = Field(default_factory=datetime.utcnow)
    
    # 对话提取的原始信息（供AI分析）
    conversation_extractions: List[Dict[str, Any]] = Field(default_factory=list)

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class ProfileUpdateRequest(BaseModel):
    """通过对话更新画像的请求"""
    user_id: str
    conversation_text: str
    extracted_features: Optional[Dict[str, Any]] = None


class ProfileResponse(BaseModel):
    """画像响应"""
    profile: StudentProfile
    completeness_tips: List[str] = []  # 提示用户补充哪些信息
