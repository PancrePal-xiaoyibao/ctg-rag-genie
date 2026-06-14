# FastGPT 本地文件库定时同步方案设计文档

**版本**: 1.0.0  
**日期**: 2026-01-26  
**作者**: AI Development Team  
**状态**: 待评审

---

## 目录

1. [概述](#概述)
2. [需求分析](#需求分析)
3. [技术方案对比](#技术方案对比)
4. [推荐方案详设](#推荐方案详设)
5. [API 接口设计](#api-接口设计)
6. [实现步骤](#实现步骤)
7. [部署与运维](#部署与运维)
8. [常见问题](#常见问题)

---

## 概述

### 问题背景

在使用 FastGPT 知识库系统时，用户常需要将本地目录的文件定期同步到 FastGPT 知识库中。但 FastGPT 本身**不提供**以下功能：
- ❌ 定时拉取本地文件
- ❌ 自动同步本地文件变化
- ❌ 本地目录的直接挂载

### 解决方案

本文档提出一套完整的**本地文件库 → FastGPT 知识库**的定时同步解决方案，包含：
- ✅ 自定义 API 文件库服务
- ✅ 文件变化监控与推送
- ✅ 定时同步机制
- ✅ 完整的部署与运维方案

### 核心价值

```
本地文件目录
    ↓ (监控 + 变化检测)
你的 API 服务 (FastAPI)
    ↓ (标准接口)
FastGPT 知识库
    ↓ (智能问答)
用户查询
```

---

## 需求分析

### 功能需求

#### 基础需求（F1）

| 需求 | 描述 | 优先级 |
|------|------|--------|
| F1.1 | 扫描本地目录，获取文件树 | P0 |
| F1.2 | 读取单个文件内容 | P0 |
| F1.3 | 生成文件预览链接 | P1 |
| F1.4 | 支持文件搜索和过滤 | P1 |

#### 同步需求（F2）

| 需求 | 描述 | 优先级 |
|------|------|--------|
| F2.1 | 监控本地文件变化（创建/修改/删除） | P1 |
| F2.2 | 定时扫描本地目录 | P1 |
| F2.3 | 增量更新（只同步变化的文件） | P2 |
| F2.4 | 冲突检测与解决 | P2 |

#### 非功能需求（NF）

| 需求 | 描述 | 优先级 |
|------|------|--------|
| NF1 | 认证安全（Bearer Token） | P0 |
| NF2 | 性能（支持 1000+ 文件） | P1 |
| NF3 | 可靠性（失败重试） | P1 |
| NF4 | 日志追踪 | P2 |

### 非功能指标

```
目标指标                     目标值
─────────────────────────────────────
文件列表获取 (100 files)    < 500ms
单文件内容读取 (1MB)         < 100ms
API 可用性                   > 99.9%
文件同步延迟                 < 5min
并发支持                     >= 10 req/s
```

---

## 技术方案对比

### 方案 A: 被动拉取（Passive Pull）

```
FastGPT 主动调用 API
    ↓
你的 API 返回最新文件列表
    ↓
FastGPT 选择性导入
```

**优点**：
- ✅ 实现简单
- ✅ 无需复杂监控逻辑
- ✅ 减少同步冲突

**缺点**：
- ❌ FastGPT 需要主动拉取（依赖 UI 操作或定时任务）
- ❌ 实时性一般（每次拉取时获取最新）

**适用场景**：
- 文件更新不频繁
- 可接受较长的同步延迟 (1-24 小时)

**成本**：⭐ 低

---

### 方案 B: 主动推送（Active Push）

```
本地文件变化检测
    ↓ (watchdog)
触发事件
    ↓
调用 FastGPT API 推送文件
    ↓
知识库实时更新
```

**优点**：
- ✅ 实时性好（秒级同步）
- ✅ 自动化程度高
- ✅ 减少不必要的 API 调用

**缺点**：
- ❌ 需要集成 FastGPT 上传 API
- ❌ 需要处理并发和失败重试
- ❌ 复杂度更高

**适用场景**：
- 文件更新频繁
- 需要近实时的知识库更新
- 有较强的开发能力

**成本**：⭐⭐ 中等

---

### 方案 C: 混合方案（Hybrid）

```
本地文件变化
    ├─ 实时推送 (watchdog)
    └─ 定时全量同步 (cron, 1h)
        
FastGPT API 文件库
    └─ 定时拉取 (cron, 6h)
```

**优点**：
- ✅ 既有实时性，又有容错机制
- ✅ 既有被动拉取，又有主动推送
- ✅ 最高的可靠性

**缺点**：
- ❌ 实现复杂度最高
- ❌ 需要处理去重和冲突
- ❌ 维护成本较高

**适用场景**：
- 生产环境，对可靠性要求高
- 大规模文件库（1000+ 文件）
- 关键业务

**成本**：⭐⭐⭐ 较高

---

## 推荐方案详设

### 推荐方案：方案 B + 方案 A 的混合

**理由**：
- 成本与收益平衡
- 实时性好
- 有一定的容错机制
- 适合大多数使用场景

### 架构图

```
┌─────────────────────────────────────────────────┐
│         本地文件系统                              │
│  /path/to/local/dir/                            │
│  ├── doc1.md                                    │
│  ├── doc2.pdf                                   │
│  └── subfolder/                                 │
└──────────┬──────────────────────────────────────┘
           │
           ├──→ [File System Watcher]
           │         (watchdog)
           │         实时监控创建/修改/删除
           │
           └──→ [Scheduled Task]
                   (APScheduler)
                   定时全量扫描 (每1小时)
                   
           ↓
┌─────────────────────────────────────────────────┐
│  你的 FastAPI 服务                               │
│  ┌───────────────────────────────────────────┐  │
│  │ API 文件库接口 (FastGPT 标准)               │  │
│  ├─ GET  /v1/file/list         获取文件树     │  │
│  ├─ GET  /v1/file/content      获取文件内容   │  │
│  └─ GET  /v1/file/read         获取预览链接   │  │
│  ┌───────────────────────────────────────────┐  │
│  │ 主动推送接口 (可选)                        │  │
│  └─ POST /api/sync/push        推送到 FGP    │  │
│  ┌───────────────────────────────────────────┐  │
│  │ 监控与管理接口                             │  │
│  └─ GET  /api/status           同步状态      │  │
│  ┌───────────────────────────────────────────┐  │
│  │ 存储                                       │  │
│  ├─ SQLite/PostgreSQL: 文件元数据             │  │
│  └─ Redis: 同步状态缓存                       │  │
└──────────┬──────────────────────────────────────┘
           │ (HTTP + Bearer Token)
           ↓
┌─────────────────────────────────────────────────┐
│       FastGPT 知识库                             │
│  ├─ API 文件库数据源                            │
│  └─ 知识库集合                                  │
└─────────────────────────────────────────────────┘
```

### 技术栈

```
语言/框架        FastAPI (Python 3.10+)
Web 服务器      Uvicorn
文件监控         watchdog
定时任务         APScheduler
数据库          SQLite (开发) / PostgreSQL (生产)
缓存            Redis (可选)
部署            Docker + Docker Compose
```

---

## API 接口设计

### 1. FastGPT 标准接口

#### 1.1 获取文件树

```http
POST /v1/file/list HTTP/1.1
Host: your-api-service.com
Authorization: Bearer <your-token>
Content-Type: application/json

{
  "parentId": null,
  "searchKey": ""
}
```

**响应** (200 OK):
```json
{
  "code": 200,
  "success": true,
  "message": "",
  "data": [
    {
      "id": "file_123",
      "parentId": null,
      "type": "file",
      "name": "document.md",
      "updateTime": "2026-01-26T10:30:00Z",
      "createTime": "2026-01-25T08:00:00Z"
    },
    {
      "id": "folder_456",
      "parentId": null,
      "type": "folder",
      "name": "reports",
      "updateTime": "2026-01-26T10:30:00Z",
      "createTime": "2026-01-20T00:00:00Z"
    }
  ]
}
```

---

#### 1.2 获取单个文件内容

```http
GET /v1/file/content?id=file_123 HTTP/1.1
Host: your-api-service.com
Authorization: Bearer <your-token>
```

**响应** (200 OK):
```json
{
  "code": 200,
  "success": true,
  "message": "",
  "data": {
    "title": "document.md",
    "content": "# FastGPT\n\n这是一个基于 LLM 的知识库...",
    "previewUrl": null
  }
}
```

> **说明**:
> - `content`: 直接返回文件内容（优先级高）
> - `previewUrl`: 返回可访问的文件链接（当 content 为空时使用）
> - 二选一返回

---

#### 1.3 获取文件阅读链接

```http
GET /v1/file/read?id=file_123 HTTP/1.1
Host: your-api-service.com
Authorization: Bearer <your-token>
```

**响应** (200 OK):
```json
{
  "code": 200,
  "success": true,
  "message": "",
  "data": {
    "url": "https://your-service.com/files/document.md"
  }
}
```

---

### 2. 扩展接口（推荐）

#### 2.1 同步状态查询

```http
GET /api/sync/status HTTP/1.1
Host: your-api-service.com
Authorization: Bearer <your-token>
```

**响应**:
```json
{
  "code": 200,
  "success": true,
  "data": {
    "lastSyncTime": "2026-01-26T10:30:00Z",
    "totalFiles": 145,
    "pendingFiles": 5,
    "failedFiles": 2,
    "syncMode": "hybrid",
    "nextScheduledSync": "2026-01-26T11:30:00Z"
  }
}
```

---

#### 2.2 手动触发同步

```http
POST /api/sync/trigger HTTP/1.1
Host: your-api-service.com
Authorization: Bearer <your-token>
Content-Type: application/json

{
  "syncType": "full|incremental",
  "targetDatasetId": "dataset_xxx"
}
```

**响应**:
```json
{
  "code": 200,
  "success": true,
  "data": {
    "taskId": "sync_task_123",
    "status": "running",
    "filesProcessed": 0,
    "totalFiles": 145
  }
}
```

---

### 3. 认证方案

所有接口使用 **Bearer Token** 认证：

```python
Authorization: Bearer <your-custom-token>
```

**生成 Token 示例**:
```bash
# 使用 OpenSSL 生成 32 字节的随机 token
openssl rand -hex 32
# 输出: a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3x4y5z6

# 或使用 Python
python3 -c "import secrets; print(secrets.token_hex(32))"
```

---

## 实现步骤

### 第一阶段：基础 API 服务（Phase 1）

#### Step 1.1: 项目初始化

```bash
# 创建项目目录
mkdir fastgpt-file-sync && cd fastgpt-file-sync

# 创建虚拟环境
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# 或 venv\Scripts\activate  # Windows

# 创建 requirements.txt
cat > requirements.txt << EOF
fastapi==0.104.1
uvicorn==0.24.0
pydantic==2.5.0
python-dotenv==1.0.0
watchdog==3.0.0
apscheduler==3.10.4
sqlalchemy==2.0.23
requests==2.31.0
EOF

pip install -r requirements.txt
```

---

#### Step 1.2: 核心应用代码

```python
# main.py
from fastapi import FastAPI, Header, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, List
from pathlib import Path
import os
import json
from datetime import datetime

app = FastAPI(title="FastGPT File Sync Service")

# ==================== 配置 ====================

class Config:
    LOCAL_DIR = Path(os.getenv("LOCAL_DIR", "/data/documents"))
    API_TOKEN = os.getenv("API_TOKEN", "your-secret-token")
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# ==================== 数据模型 ====================

class FileListItem(BaseModel):
    id: str
    parentId: Optional[str]
    type: str  # 'file' | 'folder'
    name: str
    updateTime: datetime
    createTime: datetime

class FileContent(BaseModel):
    title: str
    content: Optional[str] = None
    previewUrl: Optional[str] = None

class ApiResponse(BaseModel):
    code: int = 200
    success: bool = True
    message: str = ""
    data: dict

# ==================== 认证中间件 ====================

def verify_token(authorization: str = Header(None)) -> bool:
    """验证 Bearer Token"""
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing authorization header")
    
    parts = authorization.split(" ")
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="Invalid authorization format")
    
    token = parts[1]
    if token != Config.API_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid token")
    
    return True

# ==================== 工具函数 ====================

def get_file_id(path: Path) -> str:
    """生成文件 ID（相对路径）"""
    return str(path.relative_to(Config.LOCAL_DIR))

def get_file_tree(parent_id: Optional[str] = None, search_key: str = "") -> List[FileListItem]:
    """获取文件树"""
    items = []
    
    if parent_id is None:
        # 获取根目录
        search_dir = Config.LOCAL_DIR
    else:
        # 获取子目录
        search_dir = Config.LOCAL_DIR / parent_id
    
    if not search_dir.exists():
        return items
    
    for item in search_dir.iterdir():
        if item.name.startswith('.'):
            continue
        
        # 搜索过滤
        if search_key and search_key.lower() not in item.name.lower():
            continue
        
        file_id = get_file_id(item)
        items.append(FileListItem(
            id=file_id,
            parentId=parent_id,
            type="folder" if item.is_dir() else "file",
            name=item.name,
            updateTime=datetime.fromtimestamp(item.stat().st_mtime),
            createTime=datetime.fromtimestamp(item.stat().st_ctime)
        ))
    
    return items

def read_file_content(file_id: str) -> str:
    """读取文件内容"""
    file_path = Config.LOCAL_DIR / file_id
    
    if not file_path.exists():
        raise ValueError(f"File not found: {file_id}")
    
    # 仅支持文本文件
    if file_path.is_dir():
        raise ValueError(f"Path is a directory: {file_id}")
    
    # 支持的文本格式
    supported_exts = {'.txt', '.md', '.json', '.py', '.js', '.html', '.css'}
    if file_path.suffix.lower() not in supported_exts:
        # 如果是二进制文件，返回链接而不是内容
        return None
    
    try:
        return file_path.read_text(encoding='utf-8')
    except UnicodeDecodeError:
        return None

# ==================== API 端点 ====================

@app.post("/v1/file/list")
async def list_files(
    parentId: Optional[str] = None,
    searchKey: str = "",
    authorization: str = Header(None)
):
    """获取文件树"""
    verify_token(authorization)
    
    try:
        items = get_file_tree(parentId, searchKey)
        return ApiResponse(
            data=[item.dict() for item in items]
        )
    except Exception as e:
        return ApiResponse(
            code=500,
            success=False,
            message=str(e)
        )

@app.get("/v1/file/content")
async def get_file_content(
    id: str = Query(...),
    authorization: str = Header(None)
):
    """获取单个文件内容"""
    verify_token(authorization)
    
    try:
        content = read_file_content(id)
        title = Path(id).name
        
        return ApiResponse(
            data={
                "title": title,
                "content": content,
                "previewUrl": None
            }
        )
    except Exception as e:
        return ApiResponse(
            code=404,
            success=False,
            message=str(e)
        )

@app.get("/v1/file/read")
async def get_file_read_link(
    id: str = Query(...),
    authorization: str = Header(None)
):
    """获取文件阅读链接"""
    verify_token(authorization)
    
    try:
        file_path = Config.LOCAL_DIR / id
        if not file_path.exists():
            raise ValueError(f"File not found: {id}")
        
        # 这里返回一个可访问的 URL
        # 实际部署时需要配置 Web 服务器或对象存储
        read_url = f"http://your-domain.com/files/{id}"
        
        return ApiResponse(
            data={"url": read_url}
        )
    except Exception as e:
        return ApiResponse(
            code=404,
            success=False,
            message=str(e)
        )

@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

---

#### Step 1.3: 环境配置

```bash
# .env
LOCAL_DIR=/Users/qinxiaoqiang/Downloads/report_mess
API_TOKEN=your-secret-token-here-a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6
LOG_LEVEL=INFO
PORT=8000

# FastGPT 配置
FASTGPT_BASE_URL=https://your-fastgpt.com
FASTGPT_API_KEY=your-fastgpt-api-key
```

---

#### Step 1.4: 运行服务

```bash
# 方式 1: 直接运行
python main.py

# 方式 2: 使用 uvicorn
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# 方式 3: 使用 Docker
docker build -t fastgpt-file-sync .
docker run -d -p 8000:8000 \
  -e LOCAL_DIR=/data/documents \
  -e API_TOKEN=your-token \
  -v /path/to/documents:/data/documents \
  fastgpt-file-sync
```

---

### 第二阶段：文件监控与推送（Phase 2）

#### Step 2.1: 文件监控实现

```python
# monitor.py
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from pathlib import Path
import logging
import asyncio
from datetime import datetime

logger = logging.getLogger(__name__)

class FileChangeHandler(FileSystemEventHandler):
    """文件系统变化处理器"""
    
    def __init__(self, callback):
        super().__init__()
        self.callback = callback
    
    def on_created(self, event):
        if not event.is_directory:
            logger.info(f"File created: {event.src_path}")
            self.callback("created", event.src_path)
    
    def on_modified(self, event):
        if not event.is_directory:
            logger.info(f"File modified: {event.src_path}")
            self.callback("modified", event.src_path)
    
    def on_deleted(self, event):
        if not event.is_directory:
            logger.info(f"File deleted: {event.src_path}")
            self.callback("deleted", event.src_path)

def start_file_watcher(watch_dir: Path, callback):
    """启动文件监控"""
    observer = Observer()
    event_handler = FileChangeHandler(callback)
    observer.schedule(event_handler, path=str(watch_dir), recursive=True)
    observer.start()
    return observer

# 使用示例
async def on_file_change(event_type: str, file_path: str):
    """文件变化回调"""
    logger.info(f"Event: {event_type}, File: {file_path}")
    # 这里可以调用推送到 FastGPT 的逻辑
    # await push_to_fastgpt(file_path)

if __name__ == "__main__":
    watch_dir = Path("/path/to/documents")
    observer = start_file_watcher(watch_dir, on_file_change)
    
    try:
        while True:
            pass
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
```

---

#### Step 2.2: 定时任务配置

```python
# scheduler.py
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class SyncScheduler:
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
    
    def add_full_sync_task(self, callback, interval_hours: int = 1):
        """添加全量同步任务"""
        self.scheduler.add_job(
            callback,
            CronTrigger(minute=0),  # 每小时的第 0 分钟
            id="full_sync",
            name="Full file synchronization",
            replace_existing=True
        )
        logger.info(f"Added full sync task every {interval_hours} hour(s)")
    
    def add_incremental_sync_task(self, callback, interval_minutes: int = 5):
        """添加增量同步任务"""
        from apscheduler.triggers.interval import IntervalTrigger
        self.scheduler.add_job(
            callback,
            IntervalTrigger(minutes=interval_minutes),
            id="incremental_sync",
            name="Incremental file synchronization",
            replace_existing=True
        )
        logger.info(f"Added incremental sync task every {interval_minutes} minute(s)")
    
    def start(self):
        """启动调度器"""
        self.scheduler.start()
        logger.info("Scheduler started")
    
    def stop(self):
        """停止调度器"""
        self.scheduler.shutdown()
        logger.info("Scheduler stopped")

# 使用示例
async def sync_callback():
    logger.info(f"Sync task triggered at {datetime.now()}")
    # 执行同步逻辑

scheduler = SyncScheduler()
scheduler.add_full_sync_task(sync_callback, interval_hours=1)
# scheduler.start()
```

---

### 第三阶段：与 FastGPT 集成（Phase 3）

#### Step 3.1: 在 FastGPT 中创建 API 文件库

1. **登录 FastGPT 控制台**
2. **创建知识库 → 选择"API 文件库"类型**
3. **填入配置**:
   ```
   baseURL: https://your-api-service.com
   authorization: Bearer <your-token>
   ```
4. **保存并同步**

#### Step 3.2: 验证连接

```bash
# 测试文件列表接口
curl -X POST https://your-api-service.com/v1/file/list \
  -H "Authorization: Bearer <your-token>" \
  -H "Content-Type: application/json" \
  -d '{"parentId": null, "searchKey": ""}'

# 预期响应
{
  "code": 200,
  "success": true,
  "data": [...]
}
```

---

## 部署与运维

### Docker 部署

#### Dockerfile

```dockerfile
FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

#### docker-compose.yml

```yaml
version: '3.8'

services:
  fastgpt-file-sync:
    build: .
    container_name: fastgpt-file-sync
    ports:
      - "8000:8000"
    environment:
      LOCAL_DIR: /data/documents
      API_TOKEN: ${API_TOKEN}
      FASTGPT_BASE_URL: ${FASTGPT_BASE_URL}
      FASTGPT_API_KEY: ${FASTGPT_API_KEY}
      LOG_LEVEL: INFO
    volumes:
      - /Users/qinxiaoqiang/Downloads/report_mess:/data/documents:ro
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  # 可选: Nginx 反向代理
  nginx:
    image: nginx:latest
    container_name: fastgpt-sync-nginx
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - ./certs:/etc/nginx/certs:ro
    depends_on:
      - fastgpt-file-sync
    restart: unless-stopped
```

---

#### 部署命令

```bash
# 1. 创建 .env 文件
cat > .env << EOF
API_TOKEN=your-secret-token
FASTGPT_BASE_URL=https://your-fastgpt.com
FASTGPT_API_KEY=your-key
EOF

# 2. 启动服务
docker-compose up -d

# 3. 查看日志
docker-compose logs -f fastgpt-file-sync

# 4. 测试服务
curl http://localhost:8000/health

# 5. 停止服务
docker-compose down
```

---

### 监控与日志

#### 日志配置

```python
# logging_config.py
import logging
from logging.handlers import RotatingFileHandler
import os

def setup_logging(log_level=logging.INFO):
    """配置日志"""
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    # 控制台日志
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    console_handler.setFormatter(console_formatter)
    
    # 文件日志（日志轮转）
    file_handler = RotatingFileHandler(
        log_dir / "app.log",
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5
    )
    file_handler.setLevel(log_level)
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    file_handler.setFormatter(file_formatter)
    
    # 配置根日志
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)
    
    return root_logger
```

---

#### 监控指标

```python
# metrics.py
from datetime import datetime
from typing import Dict, Any

class SyncMetrics:
    """同步指标收集"""
    
    def __init__(self):
        self.last_sync_time: datetime = None
        self.total_files: int = 0
        self.synced_files: int = 0
        self.failed_files: int = 0
        self.sync_duration: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典（用于 API 响应）"""
        return {
            "lastSyncTime": self.last_sync_time.isoformat() if self.last_sync_time else None,
            "totalFiles": self.total_files,
            "syncedFiles": self.synced_files,
            "failedFiles": self.failed_files,
            "syncDuration": f"{self.sync_duration:.2f}s",
            "successRate": f"{(self.synced_files / self.total_files * 100):.1f}%" if self.total_files > 0 else "0%"
        }
```

---

## 常见问题

### Q1: FastGPT 不提供"上传文件"API 吗？

**A**: 
- FastGPT **没有标准的"上传文件"OpenAPI**
- 但 FastGPT 本身支持通过 Web UI 上传文件
- 目前主要的方式是：
  1. 使用 **API 文件库**（本文档推荐）
  2. 使用 FastGPT 的内置 SDK（仅限开源版本）

---

### Q2: 如何在生产环境中保护 API Token？

**A**:
```python
# 使用环境变量存储敏感信息
import os
from dotenv import load_dotenv

load_dotenv()
API_TOKEN = os.getenv("API_TOKEN")  # 从 .env 或环境变量读取

# 不要在代码中硬编码 token
# ❌ API_TOKEN = "abc123"  # 错误！
```

**部署时**:
```bash
# Docker: 使用 --env-file
docker-compose --env-file .env.prod up

# Kubernetes: 使用 Secret
kubectl create secret generic fastgpt-token --from-literal=token=your-token
```

---

### Q3: 如何处理大文件（> 100MB）？

**A**:
```python
# 对大文件返回 previewUrl 而不是 content
def read_file_content(file_id: str) -> Optional[str]:
    file_path = Config.LOCAL_DIR / file_id
    
    # 如果文件过大，返回 None（触发 previewUrl 逻辑）
    if file_path.stat().st_size > 100 * 1024 * 1024:  # 100MB
        return None
    
    return file_path.read_text(encoding='utf-8')
```

**配置流程**:
1. 返回 `previewUrl`: `https://your-cdn.com/files/{file_id}`
2. FastGPT 会访问该 URL 获取文件内容
3. 使用 CDN 加速大文件传输

---

### Q4: 如何处理文件编码问题？

**A**:
```python
import chardet

def read_file_with_auto_detection(file_path: Path) -> str:
    """自动检测文件编码"""
    with open(file_path, 'rb') as f:
        raw_data = f.read()
    
    # 检测编码
    detected = chardet.detect(raw_data)
    encoding = detected.get('encoding', 'utf-8')
    
    try:
        return raw_data.decode(encoding)
    except (UnicodeDecodeError, TypeError):
        # 如果失败，尝试用 utf-8 with ignore
        return raw_data.decode('utf-8', errors='ignore')
```

---

### Q5: 如何实现增量同步（只同步变化的文件）？

**A**:
```python
# 方案 1: 使用数据库记录文件时间戳
from sqlalchemy import create_engine, Column, String, DateTime
from sqlalchemy.orm import declarative_base, Session

Base = declarative_base()

class FileRecord(Base):
    __tablename__ = "files"
    id = Column(String, primary_key=True)
    path = Column(String)
    file_hash = Column(String)  # SHA256 哈希
    last_sync_time = Column(DateTime)
    sync_status = Column(String)  # 'synced', 'pending', 'failed'

# 方案 2: 使用文件哈希检测变化
import hashlib

def get_file_hash(file_path: Path) -> str:
    """计算文件 SHA256 哈希"""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

# 对比新旧哈希，只同步变化的文件
old_hash = get_record_hash(file_id)  # 从数据库读取
new_hash = get_file_hash(file_path)  # 计算当前哈希

if old_hash != new_hash:
    # 文件已变化，需要同步
    sync_file(file_path)
```

---

### Q6: 如何处理多人并发访问的冲突？

**A**:
```python
# 使用文件锁防止并发冲突
import fcntl
from contextlib import contextmanager

@contextmanager
def file_lock(file_path: Path):
    """文件锁上下文管理器"""
    with open(file_path, 'a') as f:
        try:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            yield
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)

# 使用
with file_lock(file_path):
    content = file_path.read_text()
    # 安全地处理文件
```

---

### Q7: 如何监控同步失败并重试？

**A**:
```python
from tenacity import retry, stop_after_attempt, wait_exponential
import logging

logger = logging.getLogger(__name__)

@retry(
    stop=stop_after_attempt(3),  # 最多重试 3 次
    wait=wait_exponential(multiplier=1, min=2, max=10),  # 指数退避
)
async def push_to_fastgpt_with_retry(file_id: str):
    """带重试的推送"""
    try:
        await push_to_fastgpt(file_id)
        logger.info(f"Successfully pushed {file_id}")
    except Exception as e:
        logger.error(f"Failed to push {file_id}: {e}")
        raise  # 重新抛出异常以触发重试
```

---

### Q8: 如何备份和恢复数据？

**A**:
```bash
#!/bin/bash
# backup.sh - 定期备份

BACKUP_DIR="/backups"
LOCAL_DIR="/data/documents"
DATE=$(date +%Y%m%d_%H%M%S)

# 备份文件
tar -czf "${BACKUP_DIR}/documents_${DATE}.tar.gz" "${LOCAL_DIR}"

# 保留最近 7 天的备份
find "${BACKUP_DIR}" -name "documents_*.tar.gz" -mtime +7 -delete

echo "Backup completed: ${BACKUP_DIR}/documents_${DATE}.tar.gz"
```

**恢复**:
```bash
# 恢复备份
tar -xzf /backups/documents_20260126_100000.tar.gz -C /
```

---

## 参考资源

### 官方文档
- [FastGPT 文档 - API 文件库](https://doc.fastgpt.io/docs/introduction/guide/knowledge_base/api_dataset)
- [FastAPI 官方文档](https://fastapi.tiangolo.com/)
- [Watchdog 文档](https://watchdog.readthedocs.io/)
- [APScheduler 文档](https://apscheduler.readthedocs.io/)

### 相关项目
- [FastGPT GitHub](https://github.com/labring/FastGPT)
- [FastAPI 项目模板](https://github.com/tiangolo/full-stack-fastapi-template)

---

## 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| 1.0.0 | 2026-01-26 | 初始版本 |

---

## 附录：完整代码模板

详见项目仓库：`/Users/qinxiaoqiang/Downloads/ct_manus_subscribe/examples/`

```
examples/
├── basic/
│   ├── main.py               # 基础 API 服务
│   ├── requirements.txt       # 依赖列表
│   └── .env.example          # 配置模板
├── advanced/
│   ├── main.py               # 完整实现（含监控、调度）
│   ├── monitor.py            # 文件监控模块
│   ├── scheduler.py          # 定时任务模块
│   └── database.py           # 数据库模块
└── deployment/
    ├── Dockerfile            # Docker 镜像
    ├── docker-compose.yml    # 容器编排
    └── nginx.conf           # 反向代理配置
```

---

## 关键建议

✅ **推荐做法**:
- 使用环境变量存储敏感信息
- 实施定期备份机制
- 使用数据库记录文件元数据
- 实现监控和告警
- 定期测试灾难恢复流程

❌ **避免**:
- 在代码中硬编码 API Token
- 直接暴露文件系统路径
- 忽视日志和监控
- 跳过错误处理和重试
- 在生产环境使用 SQLite（改用 PostgreSQL）

---

**文档完成** | 待评审 | 联系: team@your-org.com
