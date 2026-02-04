import requests
import json
from datetime import datetime, timedelta
import os
from openai import OpenAI
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 配置部分
SEARCH_CONDITION = "Pancreatic Cancer"
# 扩充后的关键词列表
KEYWORDS = ["KRAS", "免疫", "TP53", "ATM", "BRCA", "PMT5", "HER2", "ERBB2"]
STATUS = "RECRUITING"

# Telegram 配置
TG_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TG_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
MAX_TG_MSG_LEN = 4000

# LLM 配置
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "zhipu").lower()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# 智谱配置
ZHIPU_API_KEY = os.getenv("zhipu_api_key")
ZHIPU_BASE_URL = os.getenv("zhipu_base_url", "https://open.bigmodel.cn/api/paas/v4")
ZHIPU_MODEL_NAME = os.getenv("zhipu_model_name", "glm-4-air")

# Gemini 配置
GEMINI_API_KEY = os.getenv("gemini_api_key")
GEMINI_BASE_URL = os.getenv("gemini_base_url")
GEMINI_MODEL_NAME = os.getenv("gemini_model_name", "gemini-3-flash-preview")

# 初始化 LLM 客户端
def get_llm_client():
    if LLM_PROVIDER == "zhipu":
        if not ZHIPU_API_KEY:
            return None
        return OpenAI(api_key=ZHIPU_API_KEY, base_url=ZHIPU_BASE_URL, timeout=30.0)
    elif LLM_PROVIDER == "gemini":
        # Gemini 使用原生 REST 调用，无需 OpenAI 客户端
        return None
    else:
        if not OPENAI_API_KEY:
            return None
        return OpenAI(api_key=OPENAI_API_KEY, timeout=30.0)

client = get_llm_client()

def get_llm_model():
    if LLM_PROVIDER == "zhipu":
        return ZHIPU_MODEL_NAME
    elif LLM_PROVIDER == "gemini":
        return GEMINI_MODEL_NAME
    return "gpt-4o-mini"

def sanitize_filename(filename):
    return "".join([c for c in filename if c.isalnum() or c in (' ', '.', '_', '-')]).strip().replace(' ', '_')

def clean_study_data(data):
    """
    深度递归清理数据：过滤掉 ancestors, conditionBrowseModule, interventionBrowseModule 等冗余模块
    """
    if isinstance(data, dict):
        # 定义需要删除的冗余键名
        keys_to_delete = ["ancestors", "conditionBrowseModule", "interventionBrowseModule", "derivedSection"]
        for key in keys_to_delete:
            if key in data:
                del data[key]
        
        # 递归处理所有剩余子项
        for key in list(data.keys()):
            clean_study_data(data[key])
    elif isinstance(data, list):
        for item in data:
            clean_study_data(item)

def save_study_json(study_raw, translated_info):
    nct_id = study_raw.get("protocolSection", {}).get("identificationModule", {}).get("nctId", "N/A")
    date_str = datetime.now().strftime('%Y-%m-%d')
    folder_name = f"{date_str}-{sanitize_filename(SEARCH_CONDITION)}"
    base_dir = os.path.join("output", folder_name)
    os.makedirs(base_dir, exist_ok=True)
    
    # 深度清理原始数据 (过滤 conditionBrowseModule, ancestors 等)
    import copy
    clean_raw = copy.deepcopy(study_raw)
    clean_study_data(clean_raw)
    
    # 保存 JSON (过滤 translated 块，保留关键 sync_status)
    combined_data = {
        "retrieved_at": datetime.now().isoformat(),
        "sync_status": "pending", # 标记为待深度同步
        "original": clean_raw
    }
    with open(os.path.join(base_dir, f"{nct_id}.json"), "w", encoding="utf-8") as f:
        json.dump(combined_data, f, ensure_ascii=False, indent=2)

def translate_to_chinese(text):
    if not text:
        return text or "无"
    
    # 禁用 SSL 验证警告
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    # 智谱或 OpenAI 协议处理
    if LLM_PROVIDER != "gemini":
        if not client:
            return text
        for _ in range(2): # 增加一次重试
            try:
                model = get_llm_model()
                response = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": "你是一个专业的医学翻译，请将以下临床试验相关文本翻译成准确、专业的中文。只返回翻译结果。"},
                        {"role": "user", "content": text}
                    ]
                )
                return response.choices[0].message.content.strip()
            except Exception as e:
                print(f"Translation error ({LLM_PROVIDER}): {e}")
                import time
                time.sleep(1)
        return text
    
    # Gemini 原生 REST 协议处理
    else:
        if not GEMINI_API_KEY:
            return text
        url = f"{GEMINI_BASE_URL.rstrip('/')}/{GEMINI_MODEL_NAME}:generateContent?key={GEMINI_API_KEY}"
        payload = {
            "contents": [{
                "parts": [{"text": f"你是一个专业的医学翻译，请将以下临床试验相关文本翻译成准确、专业的中文。只返回翻译结果。文本内容如下：\n\n{text}"}]
            }],
            "generationConfig": {
                "temperature": 0.1
            }
        }
        headers = {"Content-Type": "application/json"}
        for _ in range(2): # 增加一次重试
            try:
                response = requests.post(url, json=payload, headers=headers, timeout=30, verify=False)
                response.raise_for_status()
                res_data = response.json()
                return res_data['candidates'][0]['content']['parts'][0]['text'].strip()
            except Exception as e:
                print(f"Translation error (Gemini REST): {e}")
                import time
                time.sleep(1)
        return text

def fetch_clinical_trials():
    base_url = "https://clinicaltrials.gov/api/v2/studies"
    
    # 禁用 SSL 验证警告
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}
    
    # 关键词组合
    keywords_query = " OR ".join(KEYWORDS)
    
    # 计算 30 天前的日期
    date_30_days_ago = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
    
    # API v2 的日期过滤参数较为敏感，此处改为获取后在本地进行精确过滤，以避免 400 错误
    params = {
        "query.cond": SEARCH_CONDITION,
        "query.term": keywords_query,
        "filter.overallStatus": STATUS,
        "pageSize": 50
    }
    
    try:
        response = requests.get(base_url, params=params, headers=headers, verify=False)
        response.raise_for_status()
        all_studies = response.json().get("studies", [])
        
        # 本地过滤 30 天内更新的
        filtered = []
        for s in all_studies:
            last_update = s.get("protocolSection", {}).get("statusModule", {}).get("lastUpdatePostDateStruct", {}).get("date", "")
            if last_update and last_update >= date_30_days_ago:
                filtered.append(s)
        return filtered
    except Exception as e:
        print(f"Error fetching data: {e}")
        return []

def format_study_detail(study):
    protocol = study.get("protocolSection", {})
    identification = protocol.get("identificationModule", {})
    status_module = protocol.get("statusModule", {})
    design_module = protocol.get("designModule", {})
    conditions_module = protocol.get("conditionsModule", {})
    contacts_locations = protocol.get("contactsLocationsModule", {})

    nct_id = identification.get("nctId", "N/A")
    brief_title = identification.get("briefTitle", "N/A")
    official_title = identification.get("officialTitle", "N/A")
    overall_status = status_module.get("overallStatus", "招募中")
    phases = design_module.get("phases", ["N/A"])
    conditions = conditions_module.get("conditions", ["N/A"])
    
    # 检查是否有中国中心
    locations = contacts_locations.get("locations", [])
    has_china = any(loc.get("country") == "China" for loc in locations)
    china_tag = "[🇨🇳 中国有中心] " if has_china else ""

    central_contacts = contacts_locations.get("centralContacts", [])
    contact_info = "无"
    if central_contacts:
        c = central_contacts[0]
        name = c.get("name", "无")
        role = c.get("role", "无")
        phone = c.get("phone", "无")
        email = c.get("email", "无")
        contact_info = f"姓名: {name}\n职称: {role}\n电话: {phone}\n邮箱: {email}"

    translated_title = translate_to_chinese(f"{brief_title} ({official_title})")
    translated_status = "招募中" if overall_status == "RECRUITING" else overall_status
    translated_conditions = translate_to_chinese(", ".join(conditions))
    
    # 落地存储
    translated_info = {
        "title_cn": translated_title,
        "status_cn": translated_status,
        "conditions_cn": translated_conditions,
        "contact_info": contact_info,
        "has_china": has_china
    }
    save_study_json(study, translated_info)
    
    detail = f"标题: {china_tag}{translated_title}\n"
    detail += f"状态: {translated_status}\n"
    detail += f"研究编号: {nct_id}\n"
    detail += f"试验阶段: {', '.join(phases)}\n"
    detail += f"适应症: {translated_conditions}\n"
    detail += f"主要研究者/联系人:\n{contact_info}\n"
    detail += f"详情链接:\nhttps://clinicaltrials.gov/study/{nct_id}\n"
    
    return detail

def send_telegram_msg(text):
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    # 禁用 SSL 验证警告
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    try:
        if len(text) <= MAX_TG_MSG_LEN:
            requests.post(url, json={"chat_id": TG_CHAT_ID, "text": text}, timeout=15, verify=False)
        else:
            parts = []
            temp_text = text
            while len(temp_text) > 0:
                if len(temp_text) <= MAX_TG_MSG_LEN:
                    parts.append(temp_text)
                    break
                split_idx = temp_text.rfind('\n', 0, MAX_TG_MSG_LEN)
                if split_idx == -1:
                    split_idx = MAX_TG_MSG_LEN
                parts.append(temp_text[:split_idx])
                temp_text = temp_text[split_idx:].lstrip()
            for i, part in enumerate(parts):
                suffix = f"\n(续 {i+1}/{len(parts)})" if len(parts) > 1 else ""
                requests.post(url, json={"chat_id": TG_CHAT_ID, "text": part + suffix}, timeout=15, verify=False)
    except Exception as e:
        print(f"Error sending Telegram message: {e}")

def send_telegram_combined(studies):
    if not studies:
        msg = f"# 🏥 小胰宝临床情报小组日报\n\n今日未发现过去 30 天内更新且符合条件的临床试验。\n更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        send_telegram_msg(msg)
        return

    # 准备本地报告记录
    date_str = datetime.now().strftime('%Y-%m-%d')
    folder_name = f"{date_str}-{sanitize_filename(SEARCH_CONDITION)}"
    base_dir = os.path.join("output", folder_name)
    os.makedirs(base_dir, exist_ok=True)
    report_file = os.path.join(base_dir, "telegram_push_report.txt")
    
    with open(report_file, "w", encoding="utf-8") as rf:
        rf.write(f"# 🏥 小胰宝临床情报小组日报 ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})\n\n")
        rf.write(f"## 🔬 胰腺癌临床试验每日更新\n\n")
        rf.write(f"- 监测日期: 最近30天\n")
        rf.write(f"- 监测要素：#胰腺癌 #KRAS/TP53/ATM/BRCA/PMT5/HER2/ERBB2相关突变\n\n")

        # 1. 汇总列表
        print(f"[{datetime.now()}] Preparing summary list for {len(studies)} studies...")
        rf.write(f"### 发现 {len(studies)} 个符合条件的临床试验 (过去 30 天内更新)\n\n")
        rf.write(f"## 【汇总清单】\n")
        
        summary_msg = f"# 🏥 小胰宝临床情报小组日报\n\n发现 {len(studies)} 个符合条件的临床试验\n\n## 【汇总清单】\n"
        for i, study in enumerate(studies):
            protocol = study.get("protocolSection", {})
            ident = protocol.get("identificationModule", {})
            nct_id = ident.get("nctId", "N/A")
            brief_title = ident.get("briefTitle", "N/A")
            
            # 检查中国中心
            loc_mod = protocol.get("contactsLocationsModule", {})
            has_china = any(loc.get("country") == "China" for loc in loc_mod.get("locations", []))
            china_marker = "🇨🇳 " if has_china else ""
            
            print(f"[{datetime.now()}] Translating summary {i+1}/{len(studies)}: {nct_id}")
            translated_brief = translate_to_chinese(brief_title)
            
            line = f"- {china_marker}标题：{translated_brief}\n  ❤️ 编号: {nct_id}\n  🔗 链接: https://clinicaltrials.gov/study/{nct_id}\n\n"
            summary_msg += line
            rf.write(line)
        
        send_telegram_msg(summary_msg)
        rf.write("\n" + "="*50 + "\n\n")

        # 2. 详细信息
        group_size = 3
        for i in range(0, len(studies), group_size):
            group = studies[i:i+group_size]
            group_num = (i // group_size) + 1
            total_groups = (len(studies) + group_size - 1) // group_size
            
            print(f"[{datetime.now()}] Preparing detail group {group_num}/{total_groups}...")
            detail_header = f"## 🔔 胰腺癌临床试验详情 ({group_num}/{total_groups})\n\n"
            group_details = ""
            for j, study in enumerate(group):
                current_idx = i + j + 1
                nct_id = study.get("protocolSection", {}).get("identificationModule", {}).get("nctId", "N/A")
                print(f"[{datetime.now()}] Processing details {current_idx}/{len(studies)}: {nct_id}")
                group_details += f"### --- 临床基本信息 ({current_idx}/{len(studies)}) ---\n"
                group_details += format_study_detail(study) + "\n"
            
            full_detail_group = detail_header + group_details
            send_telegram_msg(full_detail_group)
            rf.write(full_detail_group + "\n" + "="*50 + "\n\n")
        
        # 结尾感谢
        footer = "** 以上由小胰宝社区志愿者 ❤️ 服务提供，支持公益社区发展，关注“小胰宝助手”公众号，携手推动社区公益发展！"
        send_telegram_msg(footer)
        rf.write(footer + "\n")
    
    print(f"[{datetime.now()}] Push report saved to: {report_file}")

if __name__ == "__main__":
    print(f"Starting task at {datetime.now()}")
    studies = fetch_clinical_trials()
    print(f"Found {len(studies)} studies.")
    send_telegram_combined(studies)
    print("Task completed.")