# FastGPT 本地知识库同步系统设计文档

## 1. 概述
基于 FastGPT OpenAPI，实现本地知识库文件自动推送到 FastGPT 的完整系统。支持定时全量同步和增量同步。

---

## 2. 目录结构设计

```
output/                                  # 根目录 (FASTGPT_LOCAL_DIR)
├── 2026-01-29-Pancreatic_Cancer/        # 日期课题目录
│   ├── cn/                             # 目标同步目录 (FASTGPT_CN_SUBDIR)
│   │   ├── NCT06330064.md              # 中文精翻文档（含中心、发起方）
│   │   └── NCT07124000.md
│   ├── en/                             # 英文原文目录（忽略）
│   │   └── NCT06330064.md
│   └── NCT06330064.json                # 原始数据存根（忽略）
│
└── 2026-01-26-KRAS_G12D/
    ├── cn/
    │   └── NCT06959615.md
    └── ...
```

**特点：**
- **精准过滤**：仅扫描各课题目录下的 `cn/` 子目录。
- **关联映射**：以课题目录名作为 FastGPT 集合名称。
- **数据纯净**：排除 JSON 和英文 MD，仅推送针对患者优化的中文 MD。

---

## 3. 配置方案

### 3.1 配置参数（适配 .env）

```env
# ==================== FastGPT 知识库同步配置 ====================

# 本地文档扫描根目录
FASTGPT_LOCAL_DIR=/Users/qinxiaoqiang/Downloads/ct_manus_subscribe/output

# 子目录中文文档扫描目录名
FASTGPT_CN_SUBDIR=cn

# 支持的文件扩展名
FASTGPT_FILE_EXTENSIONS=.pdf,.md,.txt,.json,.docx,.html

# 忽略的文件/目录（正则表达式）
FASTGPT_IGNORE_PATTERNS=^\..*,.*\.tmp$,__pycache__

# 同步状态数据库路径
FASTGPT_SYNC_STATE_DB=./data/fastgpt_sync_state.json
```

### 3.2 使用现有参数
- FASTGPT_BASE_URL
- FASTGPT_API_KEY
- FASTGPT_DATASET_ID
- ENABLE_SCHEDULER
- PUSH_RETRY_TIMES、PUSH_RETRY_DELAY_SECONDS

---

## 4. 核心脚本设计

### 4.1 文件扫描和状态跟踪
**脚本：** `fastgpt_sync.py`

```python
class KnowledgeBaseSyncer:
    def __init__(self, config_file='.fastgpt.env')
        # 初始化配置、API客户端、状态数据库
    
    def scan_local_files(self) -> List[FileInfo]
        # 递归扫描 KNOWLEDGE_BASE_DIR
        # 返回：{filepath, filename, hash, size, mtime, type}
    
    def load_sync_state(self) -> Dict
        # 从 SYNC_STATE_DB 读取历史同步记录
        # 返回：{filepath: {hash, collectionId, lastSyncTime}}
    
    def detect_changes(self) -> Dict
        # 对比本地文件和历史记录
        # 返回：{added: [...], modified: [...], deleted: [...]}
    
    def upload_to_fastgpt(self, files: List[FileInfo]) -> Dict
        # 批量上传文件到 FastGPT
        # 调用 API：创建集合 -> 上传文件
    
    def sync(self):
        # 主逻辑：扫描 -> 检测 -> 上传 -> 更新状态
```

### 4.2 定时任务
**脚本：** `scheduler.py`

```python
class SyncScheduler:
    def __init__(self, syncer: KnowledgeBaseSyncer):
        # APScheduler 定时任务
    
    def start(self):
        # 启动定时器，按 SYNC_INTERVAL_MINUTES 执行 sync
    
    def stop(self):
        # 优雅关闭
```

### 4.3 监控和日志
**脚本：** `sync_logger.py`

```python
class SyncLogger:
    def log_sync_result(self, result: SyncResult):
        # 记录：
        # - 处理文件数
        # - 成功/失败统计
        # - 每个文件的状态
        # - API 响应时间
```

---

## 5. API 调用流程

### 5.1 上传单个文件
```
1. 读取本地文件（filepath）
2. 创建或获取目录集合（parentId 基于目录结构）
3. POST /api/core/dataset/collection/file
   - file: 文件内容
   - data: {
       datasetId: FASTGPT_DATASET_ID,
       name: 文件名,
       trainingType: 'chunk',
       chunkSize: CHUNK_SIZE,
       tags: [directory_path],
       createTime: file_mtime
     }
4. 返回 collectionId，更新 sync_state.json
```

### 5.2 目录映射逻辑
```
本地：output/2026-01-29-Pancreatic_Cancer/cn/NCT06330064.md
↓ 映射为
FastGPT:
- 创建集合目录 "2026-01-29-Pancreatic_Cancer"
- 上传文件 "NCT06330064.md" 到该目录下
- 标签自动附带：["Pancreatic_Cancer", "NCT06330064"]
```

---

## 6. 状态管理（sync_state.json）

```json
{
  "lastFullSyncTime": "2025-01-29T10:30:00Z",
  "files": {
    "medical/clinical_trials.pdf": {
      "hash": "abc123def456",
      "size": 2097152,
      "collectionId": "col_xxxxx",
      "parentId": "col_folder_xxxxx",
      "uploadTime": "2025-01-29T10:15:00Z",
      "tags": ["medical"]
    },
    "clinical_data/ct_trial_data.json": {
      "hash": "xyz789",
      "size": 1048576,
      "collectionId": "col_yyyyy",
      "parentId": "col_folder_yyyyy",
      "uploadTime": "2025-01-29T09:45:00Z",
      "tags": ["clinical_data"]
    }
  }
}
```

---

## 7. 实现清单

| 模块 | 文件 | 功能 |
|------|------|------|
| 配置管理 | `config.py` | 读取 .fastgpt.env，校验参数 |
| 文件扫描 | `file_scanner.py` | 递归扫描，文件哈希计算 |
| FastGPT 客户端 | `fastgpt_client.py` | 封装 OpenAPI 调用 |
| 核心同步 | `fastgpt_sync.py` | 主逻辑：扫描->检测->上传 |
| 定时任务 | `scheduler.py` | APScheduler 集成 |
| 状态跟踪 | `sync_state.py` | 持久化同步状态 |
| 日志记录 | `sync_logger.py` | 详细的操作日志 |
| 错误处理 | `error_handler.py` | 重试、降级、告警 |
| 主入口 | `main.py` | CLI 接口 + 后台服务 |

---

## 8. 使用方式

### 8.1 命令行方式（两种模式）
```bash
# 模式1：手动推送（一次性执行）
python fastgpt_sync.py --once

# 模式2：启动后台定时推送（每天执行一次）
python fastgpt_sync.py --daemon

# 显示同步状态和历史
python fastgpt_sync.py --status

# 清除历史同步记录（重新全量推送）
python fastgpt_sync.py --reset
```

### 8.2 使用示例
```bash
# 首次推送
python fastgpt_sync.py --once
# 输出: ✅ Added: 5 files, Modified: 2 files, Skipped: 0 files

# 后续只推送变更文件
python fastgpt_sync.py --once
# 输出: ✅ Added: 0 files, Modified: 1 file, Skipped: 6 files

# 启动每天凌晨2点自动推送
python fastgpt_sync.py --daemon
```

---

## 9. 关键特性

✅ **增量同步** - 基于文件哈希，仅同步新增/修改文件  
✅ **手工推送** - 支持 `--once` 随时推送  
✅ **每日定时推送** - `--daemon` 后台按配置时间推送  
✅ **目录映射** - 本地目录结构自动映射到 FastGPT 集合  
✅ **错误重试** - 失败自动重试（复用现有 PUSH_RETRY_* 配置）  
✅ **状态持久化** - sync_state.json 记录每个文件的上传状态  
✅ **详细日志** - logs/ 目录记录所有操作  

---

## 10. 下一步

1. ✅ 确认设计方案
2. ⏳ 实现 `config.py` 和配置读取
3. ⏳ 实现 `fastgpt_client.py` API 封装
4. ⏳ 实现核心同步逻辑
5. ⏳ 实现定时任务
6. ⏳ 集成测试和文档

---

**作者** | 日期：2025-01-29  
**状态** | 待确认
