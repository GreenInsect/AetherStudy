"""
认证服务层

职责：
  1. 密码哈希与验证（使用原生 bcrypt）
  2. JWT Token 生成与验证
  3. 当前用户依赖注入（FastAPI Depends）
  4. Token 吊销检查（退出登录）

依赖安装：
    pip install bcrypt python-jose[cryptography]
"""

import os
import uuid
import bcrypt  # <-- 1. 改为导入原生 bcrypt 库
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt

from database.db import get_db
from models.user import UserInDB

# 配置
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "AetherStudy-dev-secret-key-change-in-production-2026")
ALGORITHM  = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "1440"))  # 默认 24 小时

# <-- 2. 删除了原有的 pwd_context = CryptContext(...) 行

# HTTP Bearer Token 提取器
bearer_scheme = HTTPBearer(auto_error=False)


# 密码工具

def hash_password(plain_password: str) -> str:
    """将明文密码哈希为 bcrypt 字符串（改用原生 bcrypt）"""
    # 将字符串转为字节流
    pwd_bytes = plain_password.encode('utf-8')
    # 生成随机盐并计算哈希值
    salt = bcrypt.gensalt()
    hashed_bytes = bcrypt.hashpw(pwd_bytes, salt)
    # 转换为字符串用于数据库存储
    return hashed_bytes.decode('utf-8')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """校验明文密码与哈希是否匹配（改用原生 bcrypt）"""
    try:
        pwd_bytes = plain_password.encode('utf-8')
        hashed_bytes = hashed_password.encode('utf-8')
        # 使用 checkpw 安全对比
        return bcrypt.checkpw(pwd_bytes, hashed_bytes)
    except Exception:
        return False


#  JWT 工具

def create_access_token(user_id: str, username: str) -> tuple[str, int]:
    """
    生成 JWT access token。
    返回 (token字符串, 过期秒数)。
    """
    jti = str(uuid.uuid4())
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    payload = {
        "sub": user_id,
        "usr": username,
        "jti": jti,
        "iat": datetime.now(timezone.utc),
        "exp": expire,
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    return token, ACCESS_TOKEN_EXPIRE_MINUTES * 60


def decode_token(token: str) -> dict:
    """
    解码并验证 JWT token。
    若无效或过期则抛出 HTTPException 401。
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token 无效或已过期",
            headers={"WWW-Authenticate": "Bearer"},
        )


def is_token_revoked(jti: str) -> bool:
    """检查 Token 是否已被吊销（退出登录后加入黑名单）"""
    with get_db() as conn:
        row = conn.execute(
            "SELECT 1 FROM revoked_tokens WHERE jti = ?", (jti,)
        ).fetchone()
        return row is not None


def revoke_token(jti: str, user_id: str):
    """将 Token 加入黑名单（退出登录时调用）"""
    now = datetime.now(timezone.utc).isoformat()
    with get_db() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO revoked_tokens (jti, user_id, revoked_at) VALUES (?, ?, ?)",
            (jti, user_id, now)
        )


# 用户查询工具 

def get_user_by_id(user_id: str) -> Optional[UserInDB]:
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE id = ? AND is_active = 1", (user_id,)
        ).fetchone()
        return UserInDB.from_row(row) if row else None


def get_user_by_identifier(identifier: str) -> Optional[UserInDB]:
    """通过用户名或邮箱查找用户"""
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE (username = ? OR email = ?) AND is_active = 1",
            (identifier, identifier)
        ).fetchone()
        return UserInDB.from_row(row) if row else None


# FastAPI 依赖注入

async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme)
) -> UserInDB:
    """
    FastAPI 依赖：从请求头提取并验证 Bearer Token，返回当前用户对象。
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="缺少认证 Token，请先登录",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_token(credentials.credentials)

    # 检查 token 是否已被吊销
    jti = payload.get("jti")
    if jti and is_token_revoked(jti):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token 已失效，请重新登录",
        )

    user_id = payload.get("sub")
    user = get_user_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在或已被禁用",
        )
    return user


async def get_current_admin(
    current_user: UserInDB = Depends(get_current_user)
) -> UserInDB:
    """依赖：要求当前用户为管理员"""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限",
        )
    return current_user