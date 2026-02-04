import os
import json
import requests
import argparse
from dotenv import load_dotenv
from pathlib import Path

# 加载环境变量
load_dotenv()

# ==================== 配置读取 ====================
FASTGPT_BASE_URL = os.getenv("FASTGPT_BASE_URL", "").strip().rstrip("/")
FASTGPT_API_KEY = os.getenv("FASTGPT_API_KEY", "").strip()
FASTGPT_DATASET_ID = os.getenv("FASTGPT_DATASET_ID", "").strip()

class FastGPTManager:
    def __init__(self):
        # 兼容标准 API 路径
        import re
        match = re.match(r'(https?://[^/]+)', FASTGPT_BASE_URL)
        root = match.group(1) if match else FASTGPT_BASE_URL.rstrip('/')
        self.api_base = f"{root}/api"
        
        # 增强 Header，部分环境需要 apikey 和 datasetId
        self.headers = {
            "Authorization": f"Bearer {FASTGPT_API_KEY}",
            "apikey": FASTGPT_API_KEY,
            "datasetId": FASTGPT_DATASET_ID,
            "Content-Type": "application/json"
        }

    def list_collections(self, search_text=""):
        """
        查询符合名称的集合 ID 列表
        """
        url = f"{self.api_base}/core/dataset/collection/listV2"
        payload = {
            "datasetId": FASTGPT_DATASET_ID,
            "searchText": search_text,
            "pageSize": 100,  # 尽量一次性查出匹配项
            "offset": 0
        }

        try:
            resp = requests.post(url, headers=self.headers, json=payload, timeout=30)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("code") == 200:
                    res_data = data.get("data", {})
                    # 兼容不同版本的返回格式 (list 或 data)
                    items = []
                    if isinstance(res_data, list):
                        items = res_data
                    else:
                        items = res_data.get("data", res_data.get("list", []))
                    
                    # 过滤出名称精确匹配或包含匹配的项
                    matched_ids = []
                    for item in items:
                        if search_text.lower() in item.get("name", "").lower():
                            matched_ids.append({
                                "id": item.get("_id"),
                                "name": item.get("name"),
                                "type": item.get("type")
                            })
                    return matched_ids
            print(f"❌ List API Error: {resp.text[:200]}")
        except Exception as e:
            print(f"❌ Exception during list: {e}")
        return []

    def delete_collections(self, collection_ids):
        """
        执行物理删除操作。
        回退到之前成功验证过的版本：尝试逐个删除，
        因为部分私有化环境对批量删除接口支持不一。
        """
        if not collection_ids:
            return False
            
        success_count = 0
        for cid in collection_ids:
            # 标准用法：DELETE 配合 id 参数
            url = f"{self.api_base}/core/dataset/collection/delete?id={cid}"
            try:
                # 同时尝试 DELETE 和 POST 协议兼容性
                resp = requests.delete(url, headers=self.headers, timeout=30)
                if resp.status_code == 200:
                    success_count += 1
                else:
                    # 尝试用 POST 兼容某些旧版本
                    resp = requests.post(url, headers=self.headers, timeout=30)
                    if resp.status_code == 200:
                        success_count += 1
                    else:
                        print(f"❌ Failed to delete {cid}: {resp.status_code}")
            except Exception as e:
                print(f"❌ Exception deleting {cid}: {e}")
        
        return success_count == len(collection_ids)

def main():
    parser = argparse.ArgumentParser(description="FastGPT Knowledge Base Deletion Tool")
    parser.add_argument("-q", "--query", type=str, required=True, help="Collection name to delete (e.g., 'history', 'zh')")
    parser.add_argument("--force", action="store_true", help="Delete without confirmation")
    args = parser.parse_args()

    manager = FastGPTManager()
    
    print(f"\n🔍 Searching for collections matching: '{args.query}'...")
    matches = manager.list_collections(args.query)
    
    if not matches:
        print("No matching collections found.")
        return

    print(f"\n⚠️  Found {len(matches)} matching collections:")
    print("-" * 60)
    for m in matches:
        print(f"- [{m['type']}] {m['name']} (ID: {m['id']})")
    print("-" * 60)

    if not args.force:
        confirm = input(f"\nAre you SURE you want to delete these {len(matches)} collections? (y/N): ")
        if confirm.lower() != 'y':
            print("Operation cancelled.")
            return

    ids_to_delete = [m['id'] for m in matches]
    print(f"\n🚀 Deleting {len(ids_to_delete)} collections...")
    
    if manager.delete_collections(ids_to_delete):
        print("✅ Successfully deleted.")
    else:
        print("❌ Deletion failed.")

if __name__ == "__main__":
    main()
