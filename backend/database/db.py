"""
SQLite 数据库初始化与连接管理

使用 Python 内置 sqlite3 模块，无需额外安装依赖。
数据库文件默认存储在 backend/AetherStudy.db。

表结构：
  - users        : 用户账户信息
  - student_profiles : 学生画像数据（JSON 存储）
  - learning_paths   : 学习路径记录
  - assessment_records: 评估历史记录
"""

import sqlite3
import os
from contextlib import contextmanager

# 数据库文件路径（相对于 backend/ 目录）
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "AetherStudy.db")


def get_connection() -> sqlite3.Connection:
    """获取数据库连接，启用 WAL 模式提升并发性能"""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row          # 让查询结果支持按列名访问
    conn.execute("PRAGMA journal_mode=WAL") # 写前日志，提升并发读性能
    conn.execute("PRAGMA foreign_keys=ON")  # 启用外键约束
    return conn


@contextmanager
def get_db():
    """上下文管理器：自动提交/回滚事务，自动关闭连接"""
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """
    初始化数据库，创建所有表（如果不存在）。
    在应用启动时调用一次即可。
    """
    with get_db() as conn:
        conn.executescript("""
            -- ============================================================
            -- 用户表
            -- ============================================================
            CREATE TABLE IF NOT EXISTS users (
                id          TEXT PRIMARY KEY,           -- UUID
                username    TEXT UNIQUE NOT NULL,       -- 用户名（唯一）
                email       TEXT UNIQUE NOT NULL,       -- 邮箱（唯一）
                hashed_password TEXT NOT NULL,          -- bcrypt 哈希密码
                is_active   INTEGER NOT NULL DEFAULT 1, -- 1=激活 0=禁用
                is_admin    INTEGER NOT NULL DEFAULT 0, -- 1=管理员
                created_at  TEXT NOT NULL,              -- ISO8601 时间戳
                updated_at  TEXT NOT NULL,
                last_login  TEXT                        -- 最后登录时间
            );

            -- ============================================================
            -- 用户会话表（存储已吊销的 token，用于退出登录）
            -- ============================================================
            CREATE TABLE IF NOT EXISTS revoked_tokens (
                jti         TEXT PRIMARY KEY,           -- JWT ID（唯一标识）
                user_id     TEXT NOT NULL,
                revoked_at  TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            -- ============================================================
            -- 学生画像表（将原来内存字典持久化）
            -- ============================================================
            CREATE TABLE IF NOT EXISTS student_profiles (
                user_id     TEXT PRIMARY KEY,
                profile_json TEXT NOT NULL DEFAULT '{}', -- JSON 序列化的画像数据
                updated_at  TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            -- ============================================================
            -- 学习路径表
            -- ============================================================
            CREATE TABLE IF NOT EXISTS learning_paths (
                id          TEXT PRIMARY KEY,
                user_id     TEXT NOT NULL,
                course      TEXT NOT NULL,
                path_json   TEXT NOT NULL DEFAULT '{}',
                created_at  TEXT NOT NULL,
                updated_at  TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            -- ============================================================
            -- 评估记录表
            -- ============================================================
            CREATE TABLE IF NOT EXISTS assessment_records (
                id          TEXT PRIMARY KEY,
                user_id     TEXT NOT NULL,
                score       REAL NOT NULL,
                report_json TEXT NOT NULL DEFAULT '{}',
                created_at  TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            -- ============================================================
            -- 索引
            -- ============================================================
            CREATE INDEX IF NOT EXISTS idx_users_email    ON users(email);
            CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
            CREATE INDEX IF NOT EXISTS idx_revoked_tokens_user ON revoked_tokens(user_id);
            CREATE INDEX IF NOT EXISTS idx_learning_paths_user ON learning_paths(user_id);
            CREATE INDEX IF NOT EXISTS idx_assessments_user    ON assessment_records(user_id);
        """)
    print(f"[DB] 数据库初始化完成: {DB_PATH}")
