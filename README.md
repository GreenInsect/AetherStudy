# AetherStudy AI - 智能学习助手系统

> 基于多智能体AI架构的个性化学习资源生成与路径规划系统

---

## 📁 项目结构

```
AetherStudy/
├── frontend/                   # React 前端
│   ├── src/
│   │   ├── pages/
│   │   │   ├── HomePage.jsx        # 落地页（介绍 + CTA）
│   │   │   ├── ChatPage.jsx        # 智能对话（流式输出 + 画像构建）
│   │   │   ├── ResourcesPage.jsx   # 多智能体资源生成（实时进度）
│   │   │   ├── LearningPathPage.jsx # 个性化学习路径规划
│   │   │   ├── ProfilePage.jsx     # 学生画像（6+维度可视化）
│   │   │   └── AssessmentPage.jsx  # 学习效果评估（测验 + 报告）
│   │   ├── components/
│   │   │   └── Layout.jsx          # 侧边栏 + 顶栏布局
│   │   ├── store/index.js          # 全局状态（Zustand）
│   │   ├── api/index.js            # 后端 API 调用封装
│   │   └── index.css               # 设计系统 CSS
│   └── package.json
│
└── backend/                    # FastAPI 后端
    ├── main.py                     # 应用入口 + 路由注册
    ├── models/
    │   ├── profile.py              # 学生画像数据模型（8个维度）
    │   └── resources.py            # 资源生成模型（8种类型）
    ├── agents/
    │   └── orchestrator.py         # 多智能体系统核心
    │       ├── ProfileAgent        # 画像提取智能体
    │       ├── DocumentAgent       # 课程文档智能体
    │       ├── MindMapAgent        # 思维导图智能体
    │       ├── QuizAgent           # 题库生成智能体
    │       ├── VideoScriptAgent    # 视频脚本智能体
    │       ├── CodeCaseAgent       # 代码案例智能体
    │       ├── ReadingAgent        # 拓展阅读智能体
    │       └── AgentOrchestrator   # 协调器（流式进度推送）
    ├── routers/
    │   ├── chat.py                 # 对话接口（SSE流式输出）
    │   ├── profile.py              # 画像 CRUD
    │   ├── resources.py            # 资源生成（SSE进度推送）
    │   ├── learning_path.py        # 学习路径生成
    │   └── assessment.py           # 学习评估
    └── requirements.txt
```

---

## 🚀 快速启动

### 后端
```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 5000 --reload
# API文档：http://localhost:8000/docs
```

### 前端
```bash
cd frontend
npm install
npm run dev
# 访问：http://localhost:5173
```

---

## 🧠 系统功能

| 功能 | 页面 | 状态 |
|------|------|------|
| 对话式画像构建（6+维度） | ChatPage + ProfilePage | ✅ 结构完成 |
| 多智能体资源生成（5+类型） | ResourcesPage | ✅ 结构完成 |
| 个性化学习路径规划 | LearningPathPage | ✅ 结构完成 |
| 智能辅导（加分项） | ChatPage（tutoring模式） | ✅ 结构完成 |
| 学习效果评估（加分项） | AssessmentPage | ✅ 结构完成 |
| 流式输出 + 生成进度追踪 | 所有生成页面 | ✅ 已实现 |
| Markdown渲染 | ChatPage | ✅ 已实现 |

---

## 🤖 多智能体架构

```
用户请求
    │
    ▼
AgentOrchestrator（协调器）
    │
    ├─── ProfileAgent     → 从对话提取特征，更新画像
    ├─── DocumentAgent    → 生成课程讲解文档（Markdown）
    ├─── MindMapAgent     → 生成思维导图（Mermaid格式）
    ├─── QuizAgent        → 生成多类型练习题
    ├─── VideoScriptAgent → 生成教学视频脚本/Manim动画
    ├─── CodeCaseAgent    → 生成代码实操案例
    └─── ReadingAgent     → 整理拓展阅读资源
         │
         ▼
    SSE 流式推送进度 → 前端实时显示
```

---

## 🔧 待实现（TODO）

1. **LLM接入**：在各 `Agent.generate()` 方法中替换模拟函数为真实 OpenAI/Claude API 调用
2. **画像特征提取**：在 `ProfileAgent.extract_features_from_conversation()` 中实现 LLM 结构化输出
3. **数据库持久化**：将内存存储替换为 PostgreSQL / MongoDB
4. **用户认证**：添加 JWT 认证
5. **防幻觉机制**：添加 RAG + 知识验证层
6. **思维导图渲染**：前端集成 mermaid.js 渲染 MindMapAgent 输出
7. **视频生成**：对接 D-ID / Manim API

---

## 📦 开源依赖声明

| 项目 | 用途 | 协议 |
|------|------|------|
| [React](https://github.com/facebook/react) | 前端框架 | MIT |
| [Vite](https://github.com/vitejs/vite) | 构建工具 | MIT |
| [Zustand](https://github.com/pmndrs/zustand) | 状态管理 | MIT |
| [react-markdown](https://github.com/remarkjs/react-markdown) | Markdown渲染 | MIT |
| [mermaid.js](https://github.com/mermaid-js/mermaid) | 思维导图/流程图渲染 | MIT |
| [lucide-react](https://github.com/lucide-icons/lucide) | 图标库 | ISC |
| [react-router-dom](https://github.com/remix-run/react-router) | 前端路由 | MIT |
| [FastAPI](https://github.com/tiangolo/fastapi) | 后端框架 | MIT |
| [Pydantic](https://github.com/pydantic/pydantic) | 数据验证 | MIT |
| [LangGraph](https://github.com/langchain-ai/langgraph)（推荐） | 多智能体工作流 | MIT |
| [CrewAI](https://github.com/crewAIInc/crewAI)（推荐） | 多智能体框架 | MIT |
| [Manim](https://github.com/ManimCommunity/manim)（推荐） | 数学动画生成 | MIT |
| [Remotion](https://github.com/remotion-dev/remotion)（推荐） | 代码生成视频 | 需确认 |
| [Judge0](https://github.com/judge0/judge0)（推荐） | 在线代码执行沙箱 | AGPL-3.0 |
