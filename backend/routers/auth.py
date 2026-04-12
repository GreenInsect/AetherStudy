"""
用户认证路由

接口列表：
  POST   /api/auth/register          注册新账户
  POST   /api/auth/login             登录（返回 JWT）
  POST   /api/auth/logout            退出登录（吊销 Token）
  GET    /api/auth/me                获取当前用户信息
  PATCH  /api/auth/me                更新当前用户基本信息
  PATCH  /api/auth/me/password       修改密码
  DELETE /api/auth/me                注销当前账户（删除自己）
  GET    /api/auth/users             [管理员] 获取所有用户列表
  GET    /api/auth/users/{user_id}   [管理员] 获取指定用户信息
  PATCH  /api/auth/users/{user_id}/status  [管理员] 启用/禁用用户
  DELETE /api/auth/users/{user_id}   [管理员] 删除指定用户
"""

import uuid
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from database.db import get_db
from models.user import (
    RegisterRequest, LoginRequest, ChangePasswordRequest,
    UpdateProfileInfoRequest, UserPublic, TokenResponse, MessageResponse, UserInDB
)
from services.auth_service import (
    hash_password, verify_password, create_access_token, decode_token,
    revoke_token, get_current_user, get_current_admin, get_user_by_identifier
)

router = APIRouter()
bearer_scheme = HTTPBearer(auto_error=False)


# ══════════════════════════════════════════════════════════════════════
# 公开接口（无需登录）
# ══════════════════════════════════════════════════════════════════════

@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(req: RegisterRequest):
    """
    注册新账户。
    - 用户名和邮箱唯一，重复注册返回 409
    - 注册成功后直接返回 JWT Token，无需再次登录
    """
    now = datetime.now(timezone.utc).isoformat()
    user_id = str(uuid.uuid4())

    with get_db() as conn:
        # 检查用户名是否已存在
        existing = conn.execute(
            "SELECT id FROM users WHERE username = ? OR email = ?",
            (req.username, req.email)
        ).fetchone()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="用户名或邮箱已被注册"
            )

        # 插入新用户
        conn.execute(
            """INSERT INTO users
               (id, username, email, hashed_password, is_active, is_admin, created_at, updated_at)
               VALUES (?, ?, ?, ?, 1, 0, ?, ?)""",
            (user_id, req.username, req.email, hash_password(req.password), now, now)
        )

        # 初始化空画像
        conn.execute(
            "INSERT INTO student_profiles (user_id, profile_json, updated_at) VALUES (?, '{}', ?)",
            (user_id, now)
        )

    # 生成 Token
    token, expires_in = create_access_token(user_id, req.username)
    user_public = UserPublic(
        id=user_id, username=req.username, email=req.email,
        is_active=True, is_admin=False, created_at=now, last_login=None
    )
    return TokenResponse(access_token=token, expires_in=expires_in, user=user_public)


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest):
    """
    登录接口，支持用户名或邮箱登录。
    返回 JWT access_token 及用户信息。
    """
    user = get_user_by_identifier(req.identifier)
    if not user or not verify_password(req.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名/邮箱或密码错误"
        )

    # 更新最后登录时间
    now = datetime.now(timezone.utc).isoformat()
    with get_db() as conn:
        conn.execute(
            "UPDATE users SET last_login = ? WHERE id = ?", (now, user.id)
        )

    token, expires_in = create_access_token(user.id, user.username)
    return TokenResponse(
        access_token=token,
        expires_in=expires_in,
        user=user.to_public()
    )


# ══════════════════════════════════════════════════════════════════════
# 当前用户接口（需要登录）
# ══════════════════════════════════════════════════════════════════════

@router.post("/logout", response_model=MessageResponse)
async def logout(
    credentials=Depends(bearer_scheme),
    current_user: UserInDB = Depends(get_current_user)
):
    """
    退出登录。
    将当前 Token 的 jti 加入黑名单，后续携带该 Token 的请求将被拒绝。
    前端还应同时清除本地存储的 Token。
    """
    if credentials:
        payload = decode_token(credentials.credentials)
        jti = payload.get("jti")
        if jti:
            revoke_token(jti, current_user.id)
    return MessageResponse(message="已成功退出登录")


@router.get("/me", response_model=UserPublic)
async def get_me(current_user: UserInDB = Depends(get_current_user)):
    """获取当前登录用户的基本信息"""
    return current_user.to_public()


@router.patch("/me", response_model=UserPublic)
async def update_me(
    req: UpdateProfileInfoRequest,
    current_user: UserInDB = Depends(get_current_user)
):
    """更新当前用户的用户名或邮箱"""
    now = datetime.now(timezone.utc).isoformat()

    with get_db() as conn:
        # 检查新用户名/邮箱是否与他人冲突
        if req.username and req.username != current_user.username:
            clash = conn.execute(
                "SELECT id FROM users WHERE username = ? AND id != ?",
                (req.username, current_user.id)
            ).fetchone()
            if clash:
                raise HTTPException(status_code=409, detail="用户名已被使用")

        if req.email and req.email != current_user.email:
            clash = conn.execute(
                "SELECT id FROM users WHERE email = ? AND id != ?",
                (req.email, current_user.id)
            ).fetchone()
            if clash:
                raise HTTPException(status_code=409, detail="邮箱已被使用")

        # 构建动态 UPDATE 语句
        updates = {"updated_at": now}
        if req.username:
            updates["username"] = req.username
        if req.email:
            updates["email"] = req.email

        set_clause = ", ".join(f"{k} = ?" for k in updates)
        conn.execute(
            f"UPDATE users SET {set_clause} WHERE id = ?",
            (*updates.values(), current_user.id)
        )

        row = conn.execute("SELECT * FROM users WHERE id = ?", (current_user.id,)).fetchone()
        return UserInDB.from_row(row).to_public()


@router.patch("/me/password", response_model=MessageResponse)
async def change_password(
    req: ChangePasswordRequest,
    current_user: UserInDB = Depends(get_current_user)
):
    """修改密码。需要提供当前密码验证身份。"""
    if not verify_password(req.old_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="当前密码错误")

    now = datetime.now(timezone.utc).isoformat()
    with get_db() as conn:
        conn.execute(
            "UPDATE users SET hashed_password = ?, updated_at = ? WHERE id = ?",
            (hash_password(req.new_password), now, current_user.id)
        )
    return MessageResponse(message="密码修改成功，请重新登录")


@router.delete("/me", response_model=MessageResponse)
async def delete_me(
    credentials=Depends(bearer_scheme),
    current_user: UserInDB = Depends(get_current_user)
):
    """
    注销当前账户。
    会级联删除：student_profiles、learning_paths、assessment_records、revoked_tokens。
    操作不可撤销，前端应提示确认。
    """
    # 先吊销当前 Token
    if credentials:
        payload = decode_token(credentials.credentials)
        jti = payload.get("jti")
        if jti:
            revoke_token(jti, current_user.id)

    with get_db() as conn:
        conn.execute("DELETE FROM users WHERE id = ?", (current_user.id,))

    return MessageResponse(message="账户已成功注销，所有数据已删除")


# ══════════════════════════════════════════════════════════════════════
# 管理员接口（需要 is_admin = 1）
# ══════════════════════════════════════════════════════════════════════

@router.get("/users", response_model=List[UserPublic])
async def list_users(
    skip: int = 0,
    limit: int = 50,
    _admin: UserInDB = Depends(get_current_admin)
):
    """[管理员] 获取用户列表，支持分页"""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM users ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, skip)
        ).fetchall()
        return [UserInDB.from_row(r).to_public() for r in rows]


@router.get("/users/{user_id}", response_model=UserPublic)
async def get_user(user_id: str, _admin: UserInDB = Depends(get_current_admin)):
    """[管理员] 获取指定用户信息"""
    with get_db() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="用户不存在")
        return UserInDB.from_row(row).to_public()


@router.patch("/users/{user_id}/status", response_model=UserPublic)
async def toggle_user_status(
    user_id: str,
    is_active: bool,
    admin: UserInDB = Depends(get_current_admin)
):
    """[管理员] 启用或禁用指定用户账户（不删除数据）"""
    if user_id == admin.id:
        raise HTTPException(status_code=400, detail="不能修改自己的账户状态")

    now = datetime.now(timezone.utc).isoformat()
    with get_db() as conn:
        result = conn.execute(
            "UPDATE users SET is_active = ?, updated_at = ? WHERE id = ?",
            (1 if is_active else 0, now, user_id)
        )
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="用户不存在")
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return UserInDB.from_row(row).to_public()


@router.delete("/users/{user_id}", response_model=MessageResponse)
async def delete_user(
    user_id: str,
    admin: UserInDB = Depends(get_current_admin)
):
    """[管理员] 强制删除指定用户及其所有关联数据"""
    if user_id == admin.id:
        raise HTTPException(status_code=400, detail="不能删除自己的账户")

    with get_db() as conn:
        result = conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="用户不存在")

    return MessageResponse(message=f"用户 {user_id} 已被删除")
