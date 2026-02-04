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

class FastGPTQuery:
    def __init__(self):
        # 兼容标准 API 路径
        import re
        match = re.match(r'(https?://[^/]+)', FASTGPT_BASE_URL)
        root = match.group(1) if match else FASTGPT_BASE_URL.rstrip('/')
        self.api_base = f"{root}/api"
        
        self.headers = {
            "Authorization": f"Bearer {FASTGPT_API_KEY}",
            "Content-Type": "application/json"
        }

    def list_collections(self, parent_id=None, search_text="", page_size=20, offset=0):
        """
        调用 listV2 接口查询知识库集合列表
        """
        url = f"{self.api_base}/core/dataset/collection/listV2"
        
        payload = {
            "datasetId": FASTGPT_DATASET_ID,
            "parentId": parent_id,
            "searchText": search_text,
            "pageSize": page_size,
            "offset": offset
        }

        print(f"\n[QUERY] URL: {url}")
        print(f"[QUERY] DatasetID: {FASTGPT_DATASET_ID}")
        if search_text:
            print(f"[QUERY] Search: '{search_text}'")

        try:
            resp = requests.post(url, headers=self.headers, json=payload, timeout=30)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("code") == 200:
                    return data.get("data", {})
                else:
                    print(f"❌ API Error: {data.get('message')}")
            else:
                print(f"❌ HTTP Error {resp.status_code}: {resp.text[:200]}")
        except Exception as e:
            print(f"❌ Exception: {e}")
        return None

def main():
    parser = argparse.ArgumentParser(description="FastGPT Knowledge Base Query Tool (listV2)")
    parser.add_argument("--search", type=str, default="", help="Search text for collections")
    parser.add_argument("--parent", type=str, default=None, help="Parent collection ID")
    parser.add_argument("--limit", type=int, default=20, help="Page size")
    args = parser.parse_args()

    query_tool = FastGPTQuery()
    result = query_tool.list_collections(
        parent_id=args.parent, 
        search_text=args.search, 
        page_size=args.limit
    )

    if result:
        # 兼容 listV2 返回格式：可能在 result 或 result['data']
        collections = []
        total = 0
        if isinstance(result, list):
            collections = result
            total = len(result)
        elif isinstance(result, dict):
            collections = result.get("data", result.get("list", []))
            total = result.get("total", len(collections))
        
        print(f"\n✅ Found {len(collections)} items (Total: {total}):")
        print("-" * 60)
        print(f"{'Type':<10} {'Name':<30} {'ID'}")
        print("-" * 60)
        
        for item in collections:
            item_type = item.get("type", "unknown")
            name = item.get("name", "N/A")
            item_id = item.get("_id", "N/A")
            print(f"{item_type:<10} {name[:30]:<30} {item_id}")
        print("-" * 60)
    else:
        print("\nNo results found or error occurred.")

if __name__ == "__main__":
    main()
