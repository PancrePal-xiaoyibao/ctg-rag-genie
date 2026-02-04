#!/usr/bin/env python3
"""
Daily Clinical Trials Update Script
获取ClinicalTrials.gov上胰腺癌相关的最新临床试验信息
支持邮件、Telegram、微信和多个飞书机器人群推送，采用精美卡片格式
"""

import requests
import json
import smtplib
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formatdate
import os
import sys
import time
from dotenv import load_dotenv
from openai import OpenAI

# 加载环境变量
load_dotenv()

# 配置
API_URL = "https://clinicaltrials.gov/api/v2/studies"
OUTPUT_DIR = "output"
EMAIL_RECIPIENT = os.getenv("EMAIL_RECIPIENT")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
WECHAT_APP_ID = os.getenv("WECHAT_APP_ID")
WECHAT_APP_SECRET = os.getenv("WECHAT_APP_SECRET")
WECHAT_NICKNAME = os.getenv("WECHAT_NICKNAME")

# 飞书机器人配置
FEISHU_APP_ID = os.getenv("FEISHU_APP_ID")
FEISHU_APP_SECRET = os.getenv("FEISHU_APP_SECRET")
# 飞书群ID列表
FEISHU_CHAT_IDS = [i for i in os.getenv("FEISHU_CHAT_IDS", "").split(",") if i]

KEYWORDS = [i for i in os.getenv("KEYWORDS", "").split(",") if i]
DAYS_BACK = int(os.getenv("DAYS_BACK", 30))

# LLM 配置
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai").lower()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ZHIPU_API_KEY = os.getenv("zhipu_api_key")
ZHIPU_BASE_URL = os.getenv("zhipu_base_url", "https://open.bigmodel.cn/api/paas/v4")
ZHIPU_MODEL_NAME = os.getenv("zhipu_model_name", "glm-4-air")

# 初始化 LLM 客户端
def get_llm_client():
    if LLM_PROVIDER == "zhipu":
        if not ZHIPU_API_KEY:
            return None
        return OpenAI(api_key=ZHIPU_API_KEY, base_url=ZHIPU_BASE_URL)
    else:
        if not OPENAI_API_KEY:
            return None
        return OpenAI(api_key=OPENAI_API_KEY)

client = get_llm_client()

def get_llm_model():
    if LLM_PROVIDER == "zhipu":
        return ZHIPU_MODEL_NAME
    return "gpt-4o-mini"

def get_feishu_access_token():
    """
    获取飞书 tenant_access_token
    """
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    payload = {
        "app_id": FEISHU_APP_ID,
        "app_secret": FEISHU_APP_SECRET
    }
    try:
        response = requests.post(url, json=payload, timeout=10)
        data = response.json()
        if data.get("code") == 0:
            return data.get("tenant_access_token")
        else:
            print(f"[{datetime.now()}] Feishu token error: {data.get('msg')}")
            return None
    except Exception as e:
        print(f"[{datetime.now()}] Feishu token exception: {e}")
        return None

def get_study_details_with_llm(study_data):
    """
    使用LLM提取并翻译研究详情，返回结构化数据
    """
    if not client:
        # 如果没有配置客户端，返回模拟数据进行流程测试
        return {
            "title_cn": f"【测试翻译】{study_data['title']}",
            "title_en": study_data['title'],
            "nct_id": study_data['nct_id'],
            "status": "招募中 (RECRUITING)",
            "phase": study_data['phase'],
            "conditions": ", ".join(study_data['conditions']),
            "sponsor": study_data['sponsor'],
            "contact_name": study_data['contact'].get('name', '未提供'),
            "contact_role": study_data['contact'].get('role', '未提供'),
            "contact_facility": study_data['facility'],
            "contact_phone": study_data['contact'].get('phone', '未提供'),
            "contact_email": study_data['contact'].get('email', '未提供')
        }

    prompt = f"""
    请将以下临床试验的原始数据翻译并提取为结构化的中文信息。
    
    原始数据:
    {json.dumps(study_data, indent=2, ensure_ascii=False)}
    
    请严格按照以下JSON格式返回（不要有任何其他文字）：
    {{
        "title_cn": "中文翻译标题",
        "title_en": "英文原标题",
        "nct_id": "NCT编号",
        "status": "招募中 (RECRUITING)",
        "phase": "试验阶段",
        "conditions": "中文翻译适应症",
        "sponsor": "申办方/发起人名称",
        "contact_name": "主要研究者/联系人姓名",
        "contact_role": "职称",
        "contact_facility": "单位名称",
        "contact_phone": "电话",
        "contact_email": "邮箱"
    }}
    """
    
    try:
        model = get_llm_model()
        print(f"[{datetime.now()}] [{LLM_PROVIDER.upper()}] Translating study {study_data['nct_id']} using model {model}...")
        
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "你是一个专业的医学翻译助手。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            response_format={ "type": "json_object" }
        )
        result = json.loads(response.choices[0].message.content)
        print(f"[{datetime.now()}] [{LLM_PROVIDER.upper()}] 翻译 ok: {study_data['nct_id']}")
        return result
    except Exception as e:
        print(f"[{datetime.now()}] [{LLM_PROVIDER.upper()}] 翻译报错: {study_data['nct_id']} - Error: {e}")
        return None

def save_to_local(study_raw, structured_data, search_query):
    """
    将原文和翻译保存到本地 output 目录
    """
    try:
        # 创建基础目录
        date_str = datetime.now().strftime('%Y-%m-%d')
        folder_name = f"{date_str}-{search_query.replace(' ', '_')}"
        target_dir = os.path.join(OUTPUT_DIR, folder_name)

        if not os.path.exists(target_dir):
            os.makedirs(target_dir)
            
        # 组合数据
        combined_data = {
            "retrieved_at": datetime.now().isoformat(),
            "original": study_raw,
            "translated": structured_data
        }
        
        # 文件路径
        file_path = os.path.join(target_dir, f"{study_raw['nct_id']}.json")
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(combined_data, f, ensure_ascii=False, indent=2)
            
        print(f"[{datetime.now()}] Data saved to: {file_path}")
    except Exception as e:
        print(f"[{datetime.now()}] Error saving to local: {e}")

def get_clinical_trials(search_query):
    """
    从ClinicalTrials.gov API获取指定关键词相关的临床试验并提取详细信息
    """
    try:
        # 计算日期过滤
        date_limit = (datetime.now() - timedelta(days=DAYS_BACK)).strftime('%Y-%m-%d')
        
        params = {
            "query.cond": search_query,
            "filter.overallStatus": "RECRUITING",
            "pageSize": 5,
            "format": "json"
        }
        
        print(f"[{datetime.now()}] Search query: {search_query}")
        print(f"[{datetime.now()}] Params: {params}")
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}
        # 禁用 SSL 验证警告并使用 verify=False 以避免某些环境下的证书问题
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        print(f"[{datetime.now()}] Sending request to ClinicalTrials.gov...")
        try:
            response = requests.get(API_URL, params=params, headers=headers, timeout=20, verify=False)
            print(f"[{datetime.now()}] Response received, status: {response.status_code}")
        except Exception as e:
            print(f"[{datetime.now()}] Request failed: {e}")
            return []
        
        data = response.json()
        studies = data.get('studies', [])
        print(f"[{datetime.now()}] Found {len(studies)} studies initially")
        
        results = []
        for study in studies:
            protocol = study.get('protocolSection', {})
            id_info = protocol.get('identificationModule', {})
            status_module = protocol.get('statusModule', {})
            
            # 日期过滤
            last_update_date_str = status_module.get('lastUpdatePostDateStruct', {}).get('date', '')
            if last_update_date_str:
                try:
                    # API 返回的日期格式可能是 YYYY-MM-DD 或 YYYY-MM
                    if len(last_update_date_str) == 7: # YYYY-MM
                        last_update_date = datetime.strptime(last_update_date_str, '%Y-%m')
                    else:
                        last_update_date = datetime.strptime(last_update_date_str, '%Y-%m-%d')
                    
                    if last_update_date < datetime.strptime(date_limit, '%Y-%m-%d'):
                        continue
                except Exception:
                    pass
            
            conditions_module = protocol.get('conditionsModule', {})
            design_module = protocol.get('designModule', {})
            contacts_locations = protocol.get('contactsLocationsModule', {})
            sponsor_module = protocol.get('sponsorCollaboratorsModule', {})
            
            nct_id = id_info.get('nctId', '')
            title = id_info.get('officialTitle') or id_info.get('briefTitle', '')
            status = status_module.get('overallStatus', '')
            
            if status != 'RECRUITING':
                continue
            
            # 关键词过滤
            conditions = conditions_module.get('conditions', [])
            keywords_text = (title + ' ' + ' '.join(conditions)).lower()
            if not any(kw.lower() in keywords_text for kw in KEYWORDS):
                continue
            
            # 提取基础信息
            phases = design_module.get('phases', [])
            phase_str = ', '.join(phases) if phases else "未提供"
            
            # 提取申办方
            sponsor = sponsor_module.get('leadSponsor', {}).get('name', '未提供')
            
            # 提取联系人信息
            central_contacts = contacts_locations.get('centralContacts', [])
            contact_info = {}
            if central_contacts:
                contact = central_contacts[0]
                contact_info = {
                    "name": contact.get('name', '未提供'),
                    "role": contact.get('role', '未提供'),
                    "phone": contact.get('phone', '未提供'),
                    "email": contact.get('email', '未提供')
                }
            
            # 提取第一个地点作为单位信息
            locations = contacts_locations.get('locations', [])
            facility = locations[0].get('facility', '未提供') if locations else "未提供"
            
            study_raw = {
                "nct_id": nct_id,
                "title": title,
                "status": status,
                "phase": phase_str,
                "conditions": conditions,
                "sponsor": sponsor,
                "contact": contact_info,
                "facility": facility
            }
            
            print(f"[{datetime.now()}] Processing details for {nct_id}...")
            structured_data = get_study_details_with_llm(study_raw)
            if structured_data:
                save_to_local(study_raw, structured_data, search_query)
                results.append(structured_data)
            
        return results
        
    except Exception as e:
        print(f"[{datetime.now()}] Error fetching trials: {e}")
        return []

def build_feishu_card(data):
    """
    构建飞书交互式卡片 JSON
    """
    return {
        "config": {
            "wide_screen_mode": True
        },
        "header": {
            "title": {
                "tag": "plain_text",
                "content": "🔬 胰腺癌临床试验每日更新"
            },
            "template": "orange"
        },
        "elements": [
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"**标题:** {data['title_cn']}\n*({data['title_en']})*"
                }
            },
            {
                "tag": "div",
                "fields": [
                    {
                        "is_short": True,
                        "text": {
                            "tag": "lark_md",
                            "content": f"**状态:** {data['status']}\n**编号:** {data['nct_id']}"
                        }
                    },
                    {
                        "is_short": True,
                        "text": {
                            "tag": "lark_md",
                            "content": f"**阶段:** {data['phase']}\n**适应症:** {data['conditions']}"
                        }
                    }
                ]
            },
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"**申办方/发起人:** {data['sponsor']}"
                }
            },
            {
                "tag": "hr"
            },
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"**主要研究者/联系人:**\n👤 **姓名:** {data['contact_name']} ({data['contact_role']})\n🏢 **单位:** {data['contact_facility']}\n📞 **电话:** {data['contact_phone']}\n📧 **邮箱:** {data['contact_email']}"
                }
            },
            {
                "tag": "action",
                "actions": [
                    {
                        "tag": "button",
                        "text": {
                            "tag": "plain_text",
                            "content": "查看详情链接"
                        },
                        "url": f"https://clinicaltrials.gov/study/{data['nct_id']}",
                        "type": "primary"
                    }
                ]
            }
        ]
    }

def send_feishu_group_card(token, chat_id, data):
    """
    使用飞书机器人 API 向指定群组发送交互式卡片
    """
    url = "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id"
    card = build_feishu_card(data)
    payload = {
        "receive_id": chat_id,
        "msg_type": "interactive",
        "content": json.dumps(card)
    }
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json; charset=utf-8"
    }
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        res_data = response.json()
        if res_data.get("code") == 0:
            print(f"[{datetime.now()}] Feishu card sent successfully to {chat_id}: {data['nct_id']}")
            return True
        else:
            print(f"[{datetime.now()}] Feishu card error for {chat_id}: {res_data.get('msg')} (Code: {res_data.get('code')})")
            return False
    except Exception as e:
        print(f"[{datetime.now()}] Feishu card exception for {chat_id}: {e}")
        return False

def send_telegram_message(data):
    """
    发送Telegram消息
    """
    try:
        content = f"""🔔 胰腺癌临床试验每日更新

临床基本信息

标题: {data['title_cn']} ({data['title_en']})
状态: {data['status']}
研究编号: {data['nct_id']}
试验阶段: {data['phase']}
适应症: {data['conditions']}
申办方/发起人: {data['sponsor']}

主要研究者/联系人:
姓名: {data['contact_name']}
职称: {data['contact_role']}
单位: {data['contact_facility']}
电话: {data['contact_phone']}
邮箱: {data['contact_email']}

详情链接:
https://clinicaltrials.gov/study/{data['nct_id']}
"""
        telegram_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": content
        }
        requests.post(telegram_url, json=payload, timeout=10)
    except Exception as e:
        print(f"[{datetime.now()}] Telegram error: {e}")

def main():
    # 支持命令行参数输入或交互式输入
    if len(sys.argv) > 1:
        search_query = " ".join(sys.argv[1:])
    else:
        search_query = input("请输入临床试验搜索关键词 (例如: pancreatic cancer): ").strip()
    
    if not search_query:
        print("未输入关键词，程序退出。")
        return

    print(f"[{datetime.now()}] Starting clinical trials update for: {search_query}...")
    
    feishu_token = get_feishu_access_token()
    results = get_clinical_trials(search_query)
    
    if not results:
        print(f"[{datetime.now()}] No new trials found.")
        return

    for data in results:
        # 向所有配置的飞书群发送卡片
        if feishu_token:
            for chat_id in FEISHU_CHAT_IDS:
                send_feishu_group_card(feishu_token, chat_id, data)
        
        # 发送 Telegram
        send_telegram_message(data)
        
    print(f"[{datetime.now()}] Clinical trials update completed")

if __name__ == "__main__":
    main()