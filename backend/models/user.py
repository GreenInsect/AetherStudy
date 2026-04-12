"""
用户相关数据模型（Pydantic）

用于 API 请求体验证和响应序列化，与数据库字段对应但独立定义。
"""

from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional
from datetime import datetime
import re


# ─────────────────────────────────────────────
# 请求模型（Request）
# ─────────────────────────────────────────────

class RegisterRequest(BaseModel):
    """用户注册请求"""
    username: str = Field(..., min_length=3, max_length=32, description="用户名，3-32字符")
    email: EmailStr = Field(..., description="邮箱地址")
    password: str = Field(..., min_length=8, max_length=128, description="密码，至少8位")
    confirm_password: str = Field(..., description="确认密码")

    @field_validator('username')
    @classmethod
    def username_alphanumeric(cls, v: str) -> str:
        """用户名只允许字母、数字、下划线、连字符"""
        if not re.match(r'^[a-zA-Z0-9_\u4e00-\u9fff-]+$', v):
            raise ValueError('用户名只能包含字母、数字、下划线、连字符或中文')
        return v.strip()

    @field_validator('confirm_password')
    @classmethod
    def passwords_match(cls, v: str, info) -> str:
        """校验两次密码是否一致"""
        if 'password' in info.data and v != info.data['password']:
            raise ValueError('两次输入的密码不一致')
        return v

    @field_validator('password')
    @classmethod
    def password_strength(cls, v: str) -> str:
        """简单密码强度检查：至少含一个字母和一个数字"""
        if not re.search(r'[A-Za-z]', v):
            raise ValueError('密码必须包含至少一个字母')
        if not re.search(r'[0-9]', v):
            raise ValueError('密码必须包含至少一个数字')
        return v


class LoginRequest(BaseModel):
    """用户登录请求（支持用户名或邮箱登录）"""
    identifier: str = Field(..., description="用户名或邮箱")
    password: str = Field(..., description="密码")


class ChangePasswordRequest(BaseModel):
    """修改密码请求"""
    old_password: str = Field(..., description="当前密码")
    new_password: str = Field(..., min_length=8, description="新密码")
    confirm_new_password: str = Field(..., description="确认新密码")

    @field_validator('confirm_new_password')
    @classmethod
    def passwords_match(cls, v: str, info) -> str:
        if 'new_password' in info.data and v != info.data['new_password']:
            raise ValueError('两次输入的新密码不一致')
        return v


class UpdateProfileInfoRequest(BaseModel):
    """更新账户基本信息请求（不含密码）"""
    username: Optional[str] = Field(None, min_length=3, max_length=32)
    email: Optional[EmailStr] = None


# ─────────────────────────────────────────────
# 响应模型（Response）
# ─────────────────────────────────────────────

class UserPublic(BaseModel):
    """用户公开信息（不含密码哈希）"""
    id: str
    username: str
    email: str
    is_active: bool
    is_admin: bool
    created_at: str
    last_login: Optional[str] = None


class TokenResponse(BaseModel):
    """登录成功返回的 JWT Token"""
    access_token: str
    token_type: str = "bearer"
    expires_in: int             # 过期秒数
    user: UserPublic


class MessageResponse(BaseModel):
    """通用消息响应"""
    message: str
    success: bool = True


# ─────────────────────────────────────────────
# 内部模型（DB Row → Python）
# ─────────────────────────────────────────────

class UserInDB(BaseModel):
    """数据库中的完整用户记录（含密码哈希，仅内部使用）"""
    id: str
    username: str
    email: str
    hashed_password: str
    is_active: bool
    is_admin: bool
    created_at: str
    updated_at: str
    last_login: Optional[str] = None

    @classmethod
    def from_row(cls, row) -> "UserInDB":
        """从 sqlite3.Row 构建"""
        return cls(
            id=row['id'],
            username=row['username'],
            email=row['email'],
            hashed_password=row['hashed_password'],
            is_active=bool(row['is_active']),
            is_admin=bool(row['is_admin']),
            created_at=row['created_at'],
            updated_at=row['updated_at'],
            last_login=row['last_login'],
        )

    def to_public(self) -> UserPublic:
        return UserPublic(
            id=self.id,
            username=self.username,
            email=self.email,
            is_active=self.is_active,
            is_admin=self.is_admin,
            created_at=self.created_at,
            last_login=self.last_login,
        )
