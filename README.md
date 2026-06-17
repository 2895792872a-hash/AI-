#  AI 浏览器自动化助手

> AI Browser Automation Assistant — 基于 **Claude API + LangGraph + Playwright** 的四阶段智能 Agent

[![Python](https://img.shields.io/badge/Python-3.14-blue)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-green)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-18-61dafb)](https://react.dev/)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ed)](https://docs.docker.com/compose/)

---

##  项目简介

AI 浏览器自动化助手是一个智能 Agent，能理解用户的自然语言任务，自动操控浏览器完成网页搜索、信息提取、表单填写等操作，并实时流式返回执行进度和结果。

### 核心流程

```
用户任务 → [阶段1: 任务解析] → [阶段2: 浏览器操作] → [阶段3: 信息提取] → [阶段4: 结果总结] → 用户
```

| 阶段 | 说明 | 技术 |
|------|------|------|
|  任务解析 | Claude 将自然语言拆解为浏览器操作步骤序列 | Claude API |
|  浏览器操作 | Playwright 自动执行每一步（导航/点击/输入/提取） | Playwright |
|  信息提取 | 从抓取的网页内容中提取结构化数据 | Claude API |
|  结果总结 | 生成自然语言结果摘要返回给用户 | Claude API |

---

##  技术架构

```
┌─────────────┐     ┌──────────────────┐     ┌──────────┐
│  React 前端  │────▶│  FastAPI (SSE)    │────▶│  Redis    │
│  (Vite)     │◀────│  后台 Agent 执行   │◀────│  状态/缓存 │
└─────────────┘     └────────┬─────────┘     └──────────┘
                             │
                             ▼
                    ┌──────────────────┐
                    │  Playwright      │
                    │  (浏览器自动化)    │
                    └──────────────────┘
```

### 技术栈

- **Agent 编排**: LangGraph（四阶段状态图 + 断点恢复）
- **AI 模型**: Claude API (Anthropic)
- **浏览器自动化**: Playwright (Chromium)
- **后端**: FastAPI + SSE 流式推送
- **状态管理**: Redis（任务状态 + 会话缓存 + Pub/Sub）
- **安全**: AST 语法检查 + 黑名单机制
- **前端**: React 18 + TypeScript + Vite
- **部署**: Docker Compose 一键编排

---

##  快速开始

### 前置条件

- Python 3.14+
- Node.js 18+
- Redis（可选，无 Redis 时也能运行但无持久化）
- Claude API Key（[获取地址](https://console.anthropic.com/)）

### 1. 克隆仓库

```bash
git clone https://github.com/2895792872a-hash/ai-browser-assistant.git
cd ai-browser-assistant
```

### 2. 配置环境变量

```bash
cp backend/.env.example backend/.env
# 编辑 backend/.env，填入你的 ANTHROPIC_API_KEY
```

### 3. 安装依赖

```bash
# 后端
cd backend
pip install -r requirements.txt
python -m playwright install chromium

# 前端
cd ../frontend
npm install
```

### 4. 启动服务

```bash
# 终端1: 启动后端
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 终端2: 启动前端
cd frontend
npm run dev
```

### 5. 打开浏览器

访问 **http://localhost:5173**，输入任务开始使用！

### Docker 部署

```bash
# 构建并启动所有服务
docker compose up -d

# 访问 http://localhost:3000
```

---

##  API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/tasks` | 创建新任务，返回 task_id |
| `GET` | `/api/tasks/{id}` | 查询任务状态 |
| `GET` | `/api/tasks/{id}/stream` | SSE 实时进度流 |
| `GET` | `/api/health` | 健康检查 |

### 创建任务

```bash
curl -X POST http://localhost:8000/api/tasks \
  -H "Content-Type: application/json" \
  -d '{"user_task": "在百度搜索今天的天气"}'
```

### 监听实时进度

```javascript
const es = new EventSource("/api/tasks/{task_id}/stream");
es.addEventListener("stage_change", (e) => console.log("Stage:", JSON.parse(e.data)));
es.addEventListener("done", (e) => console.log("Done:", JSON.parse(e.data)));
```

---

## 📁 项目结构

```
├── backend/
│   ├── app/
│   │   ├── main.py                 # FastAPI 入口
│   │   ├── config.py               # 配置管理
│   │   ├── api/                    # 路由 + SSE
│   │   ├── agent/                  # LangGraph Agent
│   │   │   ├── graph.py            # 四阶段状态图
│   │   │   ├── state.py            # 共享状态定义
│   │   │   ├── nodes/              # 四个工作流节点
│   │   │   └── tools/              # 浏览器工具 + 安全模块
│   │   ├── services/               # Claude / Redis / SSE
│   │   └── core/                   # 日志 / 异常
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/                       # React 前端
│   ├── src/
│   │   ├── App.tsx
│   │   ├── components/             # TaskInput / ProgressStream / ResultDisplay
│   │   ├── hooks/useSSE.ts        # SSE 订阅 Hook
│   │   └── api/client.ts          # API 客户端
│   └── vite.config.ts
├── worker/                         # Playwright Worker
├── docker-compose.yml
└── README.md
```

---

##  安全机制

- **黑名单校验**: 禁止危险 URL（file://、localhost）、危险 selector（路径穿越）、危险操作
- **AST 静态分析**: 对 Agent 可能生成的代码做 AST 检查，禁止 import / exec / eval 等
- **双重验证**: 在任务解析和浏览器执行两个阶段分别进行安全审查

---

