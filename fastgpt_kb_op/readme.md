# FastGPT 知识库运维工具

用于管理 FastGPT 知识库集合（Collection）的辅助脚本。

## 📁 脚本说明

### 1. fastgpt_query.py - 集合查询工具

**功能**：查询知识库中的集合列表，支持搜索和分页

**使用方法**：
```bash
# 查询所有集合
python3 fastgpt_query.py

# 搜索特定名称的集合
python3 fastgpt_query.py --search "history"

# 指定父集合 ID
python3 fastgpt_query.py --parent "集合ID"

# 限制返回数量
python3 fastgpt_query.py --limit 50
```

**输出示例**：
```
Type       Name                           ID
------------------------------------------------------------
folder     history                        697b123...
folder     KRAS-2026-01-24                697b456...
```

---

### 2. fastgpt_delete.py - 集合删除工具

**功能**：批量删除知识库中的集合（支持模糊匹配）

**使用场景**：
- 清理重复上传的集合
- 删除错误命名的集合（如 `zh`, `cn` 等技术目录）
- 批量清理历史数据

**使用方法**：
```bash
# 查询并删除匹配的集合（需确认）
python3 fastgpt_delete.py -q "zh"

# 强制删除（跳过确认）
python3 fastgpt_delete.py -q "history" --force
```

**安全机制**：
- 默认需要手动确认（显示将要删除的集合列表）
- 使用 `--force` 参数可跳过确认

**警告**：
⚠️  删除操作不可逆，请谨慎使用！建议先用 `fastgpt_query.py` 确认要删除的集合。

---

## 🔧 配置要求

两个脚本均需要 `.env` 文件中配置以下变量：

```bash
FASTGPT_BASE_URL=https://your-domain.com/api
FASTGPT_API_KEY=openapi-your-key
FASTGPT_DATASET_ID=your_dataset_id
```

---

## 💡 常见使用场景

### 场景 1：清理重复上传的 `zh` 集合
```bash
# 1. 先查询确认
python3 fastgpt_query.py --search "zh"

# 2. 确认无误后删除
python3 fastgpt_delete.py -q "zh"
```

### 场景 2：查看所有历史归档
```bash
python3 fastgpt_query.py --search "history"
```

### 场景 3：批量清理测试数据
```bash
python3 fastgpt_delete.py -q "test" --force
```
