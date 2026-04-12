"""
学生画像路由（已接入 SQLite 持久化 + JWT 鉴权）
"""
import json
from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from models.profile import StudentProfile, ProfileUpdateRequest, ProfileResponse
from models.user import UserInDB
from services.auth_service import get_current_user
from database.db import get_db

router = APIRouter()


def _load_profile(user_id: str) -> StudentProfile:
    """从数据库加载画像，不存在则返回空画像"""
    with get_db() as conn:
        row = conn.execute(
            "SELECT profile_json FROM student_profiles WHERE user_id = ?", (user_id,)
        ).fetchone()
    if row:
        data = json.loads(row["profile_json"])
        data["user_id"] = user_id
        return StudentProfile(**data)
    return StudentProfile(user_id=user_id)


def _save_profile(profile: StudentProfile):
    """将画像持久化到数据库"""
    now = datetime.now(timezone.utc).isoformat()
    data = profile.dict(exclude={"user_id"})
    with get_db() as conn:
        conn.execute(
            """INSERT INTO student_profiles (user_id, profile_json, updated_at)
               VALUES (?, ?, ?)
               ON CONFLICT(user_id) DO UPDATE SET profile_json=excluded.profile_json, updated_at=excluded.updated_at""",
            (profile.user_id, json.dumps(data, default=str), now)
        )


@router.get("/me", response_model=ProfileResponse)
async def get_my_profile(current_user: UserInDB = Depends(get_current_user)):
    """获取当前用户的学生画像"""
    profile = _load_profile(current_user.id)
    tips = []
    if not profile.major:
        tips.append("请告诉我你的专业方向")
    if not profile.learning_goals:
        tips.append("设定学习目标有助于个性化推荐")
    if not profile.cognition_style:
        tips.append("了解你的认知风格可以优化学习资源类型")
    if not profile.weak_points:
        tips.append("告诉我你的薄弱点，我可以针对性地生成资源")
    return ProfileResponse(profile=profile, completeness_tips=tips)


@router.get("/{user_id}", response_model=ProfileResponse)
async def get_profile(user_id: str, current_user: UserInDB = Depends(get_current_user)):
    """获取指定用户画像（普通用户只能查自己，管理员可查所有）"""
    target_id = user_id if current_user.is_admin else current_user.id
    profile = _load_profile(target_id)
    return ProfileResponse(profile=profile, completeness_tips=[])


@router.post("/update", response_model=ProfileResponse)
async def update_profile(
    request: ProfileUpdateRequest,
    current_user: UserInDB = Depends(get_current_user)
):
    """通过对话提取的特征更新画像"""
    profile = _load_profile(current_user.id)
    if request.extracted_features:
        f = request.extracted_features
        if f.get("major"): profile.major = f["major"]
        if f.get("grade"): profile.grade = f["grade"]
        if f.get("cognition_style"): profile.cognition_style = f["cognition_style"]
        if f.get("learning_pace"): profile.learning_pace = f["learning_pace"]
        if f.get("learning_goals"): profile.learning_goals = list(set(profile.learning_goals + f["learning_goals"]))
        if f.get("weak_points"): profile.weak_points = list(set(profile.weak_points + f["weak_points"]))
        if f.get("current_courses"): profile.current_courses = list(set(profile.current_courses + f["current_courses"]))
        if f.get("knowledge_foundation"): profile.knowledge_foundation.update(f["knowledge_foundation"])
    _save_profile(profile)
    return ProfileResponse(profile=profile, completeness_tips=[])


@router.delete("/me", response_model=dict)
async def reset_profile(current_user: UserInDB = Depends(get_current_user)):
    """重置当前用户画像"""
    now = datetime.now(timezone.utc).isoformat()
    with get_db() as conn:
        conn.execute(
            "UPDATE student_profiles SET profile_json='{}', updated_at=? WHERE user_id=?",
            (now, current_user.id)
        )
    return {"status": "reset", "user_id": current_user.id}
