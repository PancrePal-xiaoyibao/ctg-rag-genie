# FastGPT 文件库快速开始指南

**5 分钟快速搭建本地文件库 → FastGPT 同步服务**

---

## 前置条件

```bash
✓ Python 3.10+
✓ FastGPT 账户（云版或自部署）
✓ 本地文件目录（待同步）
```

---

## Step 1: 创建项目目录 (1 min)

```bash
mkdir fastgpt-file-sync && cd fastgpt-file-sync

# 创建虚拟环境
python3 -m venv venv
source venv/bin/activate  # Linux/Mac 或 venv\Scripts\activate (Windows)
```

---

## Step 2: 安装依赖 (1 min)

```bash
# 创建 requirements.txt
cat > requirements.txt << 'EOF'
fastapi==0.104.1
uvicorn==0.24.0
python-dotenv==1.0.0
watchdog==3.0.0
apscheduler==3.10.4
EOF

pip install -r requirements.txt
```

---

## Step 3: 创建配置文件 (1 min)

```bash
cat > .env << 'EOF'
# 本地文件目录路径
LOCAL_DIR=/Users/qinxiaoqiang/Downloads/report_mess

# API 认证 Token（生成方式：openssl rand -hex 32）
API_TOKEN=a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3x4y5z6

# 服务端口
PORT=8000
EOF
```

---

## Step 4: 创建应用代码 (1 min)

```bash
cat > main.py << 'EOF'
from fastapi import FastAPI, Header, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, List
from pathlib import Path
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

LOCAL_DIR = Path(os.getenv("LOCAL_DIR", "/data/documents"))
API_TOKEN = os.getenv("API_TOKEN", "test-token")

# ==================== 数据模型 ====================

class FileListItem(BaseModel):
    id: str
    parentId: Optional[str]
    type: str
    name: str
    updateTime: datetime
    createTime: datetime

# ==================== 认证 ====================

def verify_token(authorization: str = Header(None)) -> bool:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401)
    if authorization.replace("Bearer ", "") != API_TOKEN:
        raise HTTPException(status_code=403)
    return True

# ==================== 工具函数 ====================

def get_file_tree(parent_id: Optional[str] = None) -> List[dict]:
    items = []
    if parent_id is None:
        search_dir = LOCAL_DIR
    else:
        search_dir = LOCAL_DIR / parent_id
    
    if not search_dir.exists():
        return items
    
    for item in search_dir.iterdir():
        if item.name.startswith('.'):
            continue
        items.append({
            "id": str(item.relative_to(LOCAL_DIR)),
            "parentId": parent_id,
            "type": "folder" if item.is_dir() else "file",
            "name": item.name,
            "updateTime": datetime.fromtimestamp(item.stat().st_mtime).isoformat(),
            "createTime": datetime.fromtimestamp(item.stat().st_ctime).isoformat()
        })
    return items

def read_file_content(file_id: str) -> Optional[str]:
    file_path = LOCAL_DIR / file_id
    if not file_path.exists() or file_path.is_dir():
        return None
    try:
        return file_path.read_text(encoding='utf-8')
    except:
        return None

# ==================== API 端点 ====================

@app.post("/v1/file/list")
async def list_files(
    parentId: Optional[str] = None,
    searchKey: str = "",
    authorization: str = Header(None)
):
    verify_token(authorization)
    items = get_file_tree(parentId)
    return {
        "code": 200,
        "success": True,
        "data": items
    }

@app.get("/v1/file/content")
async def get_file_content(
    id: str = Query(...),
    authorization: str = Header(None)
):
    verify_token(authorization)
    content = read_file_content(id)
    return {
        "code": 200,
        "success": True,
        "data": {
            "title": Path(id).name,
            "content": content,
            "previewUrl": None
        }
    }

@app.get("/v1/file/read")
async def get_file_read_link(
    id: str = Query(...),
    authorization: str = Header(None)
):
    verify_token(authorization)
    return {
        "code": 200,
        "success": True,
        "data": {
            "url": f"http://localhost:8000/files/{id}"
        }
    }

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
EOF
```

---

## Step 5: 启动服务 (1 min)

```bash
python main.py
# 输出：
# INFO:     Uvicorn running on http://0.0.0.0:8000
# 按 Ctrl+C 停止
```

---

## Step 6: 在 FastGPT 中创建 API 文件库

### 6.1 登录 FastGPT

访问你的 FastGPT 实例（e.g., https://your-fastgpt.com）

### 6.2 创建知识库

1. 点击 **"创建知识库"**
2. 选择 **"API 文件库"** 类型
3. 填入配置：

```
名称: 本地文件库
描述: 本地文件同步服务
baseURL: http://localhost:8000
authorization: a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3x4y5z6
```

### 6.3 测试连接

点击 **"测试连接"** → 应该看到 ✅ 成功

### 6.4 导入文件

1. 点击 **"同步文件"**
2. FastGPT 会显示你本地目录的文件列表
3. 选择要导入的文件
4. 点击 **"导入"**

---

## Step 7: 验证

### 在 FastGPT 中测试对话

```
用户: 这个文件的内容是什么？
FastGPT: [根据导入的文件内容回答]
```

### 测试 API

```bash
# 获取文件列表
curl -X POST http://localhost:8000/v1/file/list \
  -H "Authorization: Bearer a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3x4y5z6" \
  -H "Content-Type: application/json" \
  -d '{"parentId": null}'

# 预期输出
{
  "code": 200,
  "success": true,
  "data": [
    {"id": "file1.md", "name": "file1.md", "type": "file", ...},
    {"id": "folder1", "name": "folder1", "type": "folder", ...}
  ]
}
```

---

## ✅ 完成！

现在你有了一个工作的本地文件库同步服务 🎉

### 后续可选优化

#### 1️⃣ 添加文件监控（实时同步）

```bash
pip install watchdog

# 修改 main.py，添加以下代码：
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class FileChangeHandler(FileSystemEventHandler):
    def on_modified(self, event):
        if not event.is_directory:
            print(f"文件变化: {event.src_path}")
            # 这里可以触发 FastGPT 同步

observer = Observer()
observer.schedule(FileChangeHandler(), str(LOCAL_DIR), recursive=True)
observer.start()
```

#### 2️⃣ 添加定时任务

```bash
pip install apscheduler

# 在 main.py 中添加：
from apscheduler.schedulers.background import BackgroundScheduler

def sync_job():
    print("定时同步任务运行中...")

scheduler = BackgroundScheduler()
scheduler.add_job(sync_job, 'cron', hour=0)  # 每天午夜运行
scheduler.start()
```

#### 3️⃣ Docker 部署

```bash
# 创建 Dockerfile
cat > Dockerfile << 'EOF'
FROM python:3.10-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY main.py .
COPY .env .
CMD ["python", "main.py"]
EOF

# 构建并运行
docker build -t fastgpt-sync .
docker run -d -p 8000:8000 \
  -e LOCAL_DIR=/data/documents \
  -v /path/to/documents:/data/documents:ro \
  fastgpt-sync
```

---

## 常见问题

### Q: 如何生成安全的 API Token？

```bash
# 方式 1: OpenSSL
openssl rand -hex 32

# 方式 2: Python
python3 -c "import secrets; print(secrets.token_hex(32))"
```

### Q: 文件权限不足怎么办？

```bash
# 检查文件权限
ls -la /Users/qinxiaoqiang/Downloads/report_mess

# 如果需要，修改权限
chmod -R 755 /Users/qinxiaoqiang/Downloads/report_mess
```

### Q: 如何更改监听端口？

编辑 `.env` 文件，修改 `PORT=8000` 为其他端口，然后重启服务

### Q: 如何配置 HTTPS？

使用 Nginx 反向代理加 SSL 证书（见完整设计文档）

---

## 需要帮助？

- 📖 查看完整设计文档: `FASTGPT_LOCAL_FILE_SYNC_DESIGN.md`
- 🐛 检查日志: `python main.py` 的输出
- 🔗 测试 API 连接: `curl http://localhost:8000/health`

---

**祝你使用愉快！** 🚀
