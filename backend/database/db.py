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
            -- 用户 LLM 配置（用户端动态配置模型与 API）
            -- ============================================================
            CREATE TABLE IF NOT EXISTS user_llm_settings (
                user_id       TEXT PRIMARY KEY,
                provider      TEXT NOT NULL DEFAULT 'OpenAI',
                model         TEXT NOT NULL DEFAULT 'gpt-5.4',
                review_model  TEXT NOT NULL DEFAULT 'gpt-5.5',
                base_url      TEXT NOT NULL DEFAULT 'https://api.dstopology.com/v1',
                api_key       TEXT NOT NULL DEFAULT '',
                wire_api      TEXT NOT NULL DEFAULT 'responses',
                reasoning_effort TEXT NOT NULL DEFAULT 'xhigh',
                disable_response_storage INTEGER NOT NULL DEFAULT 1,
                network_access TEXT NOT NULL DEFAULT 'enabled',
                context_window INTEGER NOT NULL DEFAULT 400000,
                auto_compact_token_limit INTEGER NOT NULL DEFAULT 360000,
                updated_at    TEXT NOT NULL,
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
            -- 学科与本地资料库（RAG 文档来源）
            -- ============================================================
            CREATE TABLE IF NOT EXISTS study_subjects (
                id          TEXT PRIMARY KEY,
                user_id     TEXT NOT NULL,
                name        TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                created_at  TEXT NOT NULL,
                updated_at  TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                UNIQUE(user_id, name)
            );

            CREATE TABLE IF NOT EXISTS study_documents (
                id          TEXT PRIMARY KEY,
                subject_id  TEXT NOT NULL,
                user_id     TEXT NOT NULL,
                filename    TEXT NOT NULL,
                file_type   TEXT NOT NULL,
                char_count  INTEGER NOT NULL DEFAULT 0,
                content     TEXT NOT NULL,
                storage_path TEXT NOT NULL DEFAULT '',
                stored_filename TEXT NOT NULL DEFAULT '',
                chunk_count INTEGER NOT NULL DEFAULT 0,
                vector_index_ready INTEGER NOT NULL DEFAULT 0,
                created_at  TEXT NOT NULL,
                FOREIGN KEY (subject_id) REFERENCES study_subjects(id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS study_document_chunks (
                id          TEXT PRIMARY KEY,
                document_id TEXT NOT NULL,
                subject_id  TEXT NOT NULL,
                user_id     TEXT NOT NULL,
                chunk_index INTEGER NOT NULL,
                content     TEXT NOT NULL,
                embedding_json TEXT NOT NULL DEFAULT '{}',
                embedding_provider TEXT NOT NULL DEFAULT 'lightweight_hash',
                embedding_model TEXT NOT NULL DEFAULT 'local_hash_96',
                embedding_dim INTEGER NOT NULL DEFAULT 96,
                token_count INTEGER NOT NULL DEFAULT 0,
                created_at  TEXT NOT NULL,
                FOREIGN KEY (document_id) REFERENCES study_documents(id) ON DELETE CASCADE,
                FOREIGN KEY (subject_id) REFERENCES study_subjects(id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            -- ============================================================
            -- 管理员持久知识库（服务器目录资料，供所有用户 RAG 使用）
            -- ============================================================
            CREATE TABLE IF NOT EXISTS study_admin_documents (
                id          TEXT PRIMARY KEY,
                subject_name TEXT NOT NULL,
                filename    TEXT NOT NULL,
                file_type   TEXT NOT NULL,
                char_count  INTEGER NOT NULL DEFAULT 0,
                content     TEXT NOT NULL,
                storage_path TEXT UNIQUE NOT NULL,
                content_hash TEXT NOT NULL DEFAULT '',
                file_mtime  REAL NOT NULL DEFAULT 0,
                chunk_count INTEGER NOT NULL DEFAULT 0,
                vector_index_ready INTEGER NOT NULL DEFAULT 0,
                embedding_provider TEXT NOT NULL DEFAULT 'lightweight_hash',
                embedding_model TEXT NOT NULL DEFAULT 'local_hash_96',
                embedding_dim INTEGER NOT NULL DEFAULT 96,
                created_at  TEXT NOT NULL,
                updated_at  TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS study_admin_document_chunks (
                id          TEXT PRIMARY KEY,
                document_id TEXT NOT NULL,
                subject_name TEXT NOT NULL,
                chunk_index INTEGER NOT NULL,
                content     TEXT NOT NULL,
                embedding_json TEXT NOT NULL DEFAULT '{}',
                embedding_provider TEXT NOT NULL DEFAULT 'lightweight_hash',
                embedding_model TEXT NOT NULL DEFAULT 'local_hash_96',
                embedding_dim INTEGER NOT NULL DEFAULT 96,
                token_count INTEGER NOT NULL DEFAULT 0,
                created_at  TEXT NOT NULL,
                FOREIGN KEY (document_id) REFERENCES study_admin_documents(id) ON DELETE CASCADE
            );

            -- ============================================================
            -- 本地题库历史
            -- ============================================================
            CREATE TABLE IF NOT EXISTS quiz_sets (
                id             TEXT PRIMARY KEY,
                user_id        TEXT NOT NULL,
                subject_id     TEXT NOT NULL,
                title          TEXT NOT NULL,
                topic          TEXT NOT NULL,
                question_type  TEXT NOT NULL,
                count          INTEGER NOT NULL,
                difficulty     TEXT NOT NULL,
                local_sources  TEXT NOT NULL DEFAULT '[]',
                web_sources    TEXT NOT NULL DEFAULT '[]',
                created_at     TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (subject_id) REFERENCES study_subjects(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS quiz_questions (
                id             TEXT PRIMARY KEY,
                quiz_set_id    TEXT NOT NULL,
                seq_no         INTEGER NOT NULL,
                question_type  TEXT NOT NULL,
                prompt         TEXT NOT NULL,
                options_json   TEXT NOT NULL DEFAULT '[]',
                answer_json    TEXT NOT NULL DEFAULT 'null',
                explanation    TEXT NOT NULL DEFAULT '',
                local_citation TEXT NOT NULL DEFAULT '',
                web_citation   TEXT NOT NULL DEFAULT '',
                FOREIGN KEY (quiz_set_id) REFERENCES quiz_sets(id) ON DELETE CASCADE
            );
            -- 聊天会话表
            CREATE TABLE IF NOT EXISTS chat_sessions (
                id          TEXT PRIMARY KEY,
                user_id     TEXT NOT NULL,
                title       TEXT NOT NULL DEFAULT '新对话',
                mode        TEXT NOT NULL DEFAULT 'general',
                created_at  TEXT NOT NULL,
                updated_at  TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            -- 聊天消息表
            CREATE TABLE IF NOT EXISTS chat_messages (
                id          TEXT PRIMARY KEY,
                session_id  TEXT NOT NULL,
                role        TEXT NOT NULL,
                content     TEXT NOT NULL,
                created_at  TEXT NOT NULL,
                FOREIGN KEY (session_id) REFERENCES chat_sessions(id) ON DELETE CASCADE
            );

            -- ============================================================
            -- 索引
            -- ============================================================
            CREATE INDEX IF NOT EXISTS idx_users_email    ON users(email);
            CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
            CREATE INDEX IF NOT EXISTS idx_revoked_tokens_user  ON revoked_tokens(user_id);
            CREATE INDEX IF NOT EXISTS idx_user_llm_settings_user ON user_llm_settings(user_id);
            CREATE INDEX IF NOT EXISTS idx_learning_paths_user  ON learning_paths(user_id);
            CREATE INDEX IF NOT EXISTS idx_assessments_user     ON assessment_records(user_id);
            CREATE INDEX IF NOT EXISTS idx_subjects_user        ON study_subjects(user_id);
            CREATE INDEX IF NOT EXISTS idx_documents_subject    ON study_documents(subject_id);
            CREATE INDEX IF NOT EXISTS idx_document_chunks_doc  ON study_document_chunks(document_id);
            CREATE INDEX IF NOT EXISTS idx_document_chunks_subject ON study_document_chunks(subject_id);
            CREATE INDEX IF NOT EXISTS idx_admin_documents_subject ON study_admin_documents(subject_name);
            CREATE INDEX IF NOT EXISTS idx_admin_documents_path ON study_admin_documents(storage_path);
            CREATE INDEX IF NOT EXISTS idx_admin_chunks_doc ON study_admin_document_chunks(document_id);
            CREATE INDEX IF NOT EXISTS idx_admin_chunks_subject ON study_admin_document_chunks(subject_name);
            CREATE INDEX IF NOT EXISTS idx_quiz_sets_user       ON quiz_sets(user_id);
            CREATE INDEX IF NOT EXISTS idx_quiz_sets_subject    ON quiz_sets(subject_id);
            CREATE INDEX IF NOT EXISTS idx_quiz_questions_set   ON quiz_questions(quiz_set_id);
            CREATE INDEX IF NOT EXISTS idx_chat_sessions_user   ON chat_sessions(user_id);
            CREATE INDEX IF NOT EXISTS idx_chat_sessions_updated ON chat_sessions(updated_at);
            CREATE INDEX IF NOT EXISTS idx_chat_messages_session ON chat_messages(session_id);
            CREATE INDEX IF NOT EXISTS idx_chat_messages_created ON chat_messages(created_at);
        """)

        # 兼容已存在的本地数据库：CREATE TABLE IF NOT EXISTS 不会自动补列。
        existing_document_columns = {
            row["name"] for row in conn.execute("PRAGMA table_info(study_documents)").fetchall()
        }
        for column_name, column_sql in {
            "storage_path": "TEXT NOT NULL DEFAULT ''",
            "stored_filename": "TEXT NOT NULL DEFAULT ''",
            "chunk_count": "INTEGER NOT NULL DEFAULT 0",
            "vector_index_ready": "INTEGER NOT NULL DEFAULT 0",
        }.items():
            if column_name not in existing_document_columns:
                conn.execute(f"ALTER TABLE study_documents ADD COLUMN {column_name} {column_sql}")

        conn.execute("UPDATE study_documents SET stored_filename = filename WHERE stored_filename = ''")
        duplicate_document_groups = conn.execute(
            """SELECT user_id, subject_id, stored_filename, COUNT(*) AS duplicate_count
               FROM study_documents
               GROUP BY user_id, subject_id, stored_filename
               HAVING duplicate_count > 1"""
        ).fetchall()
        for group in duplicate_document_groups:
            duplicate_rows = conn.execute(
                """SELECT id
                   FROM study_documents
                   WHERE user_id = ? AND subject_id = ? AND stored_filename = ?
                   ORDER BY created_at DESC""",
                (group["user_id"], group["subject_id"], group["stored_filename"]),
            ).fetchall()
            for duplicate in duplicate_rows[1:]:
                conn.execute("DELETE FROM study_document_chunks WHERE document_id = ?", (duplicate["id"],))
                conn.execute("DELETE FROM study_documents WHERE id = ?", (duplicate["id"],))
        conn.execute(
            """CREATE UNIQUE INDEX IF NOT EXISTS idx_documents_unique_filename
               ON study_documents(user_id, subject_id, stored_filename)"""
        )

        existing_chunk_columns = {
            row["name"] for row in conn.execute("PRAGMA table_info(study_document_chunks)").fetchall()
        }
        for column_name, column_sql in {
            "embedding_provider": "TEXT NOT NULL DEFAULT 'lightweight_hash'",
            "embedding_model": "TEXT NOT NULL DEFAULT 'local_hash_96'",
            "embedding_dim": "INTEGER NOT NULL DEFAULT 96",
        }.items():
            if column_name not in existing_chunk_columns:
                conn.execute(f"ALTER TABLE study_document_chunks ADD COLUMN {column_name} {column_sql}")
    print(f"[DB] 数据库初始化完成: {DB_PATH}")
