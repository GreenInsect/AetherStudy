"""
AetherStudy AI - 智能学习助手系统后端
主入口文件

依赖安装：
    pip install fastapi uvicorn python-dotenv openai httpx websockets pydantic
    pip install passlib[bcrypt] python-jose[cryptography]

运行：
    uvicorn main:app --host 0.0.0.0 --port 5000 --reload
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database.db import init_db
from routers import chat, profile, resources, learning_path, assessment, auth

app = FastAPI(
    title="AetherStudy AI",
    description="智能学习助手系统 API",
    version="1.1.0"
)

# CORS 配置（开发环境）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(auth.router,          prefix="/api/auth",          tags=["用户认证"])
app.include_router(chat.router,          prefix="/api/chat",          tags=["对话"])
app.include_router(profile.router,       prefix="/api/profile",       tags=["学生画像"])
app.include_router(resources.router,     prefix="/api/resources",     tags=["资源生成"])
app.include_router(learning_path.router, prefix="/api/learning-path", tags=["学习路径"])
app.include_router(assessment.router,    prefix="/api/assessment",    tags=["学习评估"])


@app.on_event("startup")
async def startup_event():
    """应用启动时初始化数据库（建表）"""
    init_db()


@app.get("/")
async def root():
    return {"message": "AetherStudy AI API is running", "version": "1.1.0"}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}
