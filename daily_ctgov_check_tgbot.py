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

# GeWeChat 配置(个人微信群推送,与 TG 并列)
GEWE_ENABLED = os.getenv("GEWE_ENABLED", "false").strip().lower() in ("true", "1", "yes", "on")
GEWE_API_HOST = os.getenv("GEWE_API_HOST", "api.geweapi.com").strip()
GEWE_APP_ID = os.getenv("GEWE_APP_ID", "").strip()
GEWE_TOKEN = os.getenv("GEWE_TOKEN", "").strip()
# 支持多群,三种写法均兼容:
#   1. JSON 数组: ["group-wxid-1","group-wxid-2"]
#   2. 逗号分隔: group-wxid-1,group-wxid-2
#   3. 单群:     group-wxid-1
GEWE_TO_WXID = os.getenv("GEWE_TO_WXID", "").strip()
def _parse_gewe_wxids(raw):
    """解析 GEWE_TO_WXID,兼容 JSON 数组 / 逗号分隔 / 单群三种写法"""
    import json
    if not raw:
        return []
    s = raw.strip()
    # 优先尝试 JSON 数组解析
    if s.startswith("[") and s.endswith("]"):
        try:
            arr = json.loads(s)
            return [str(w).strip() for w in arr if str(w).strip()]
        except Exception:
            pass  # 解析失败则回退到逗号分隔
    # 逗号分隔(含单群)
    return [w.strip() for w in s.split(",") if w.strip()]
GEWE_TO_WXIDS = _parse_gewe_wxids(GEWE_TO_WXID)
GEWE_CARD_MODE = os.getenv("GEWE_CARD_MODE", "true").strip().lower() in ("true", "1", "yes", "on")
GEWE_MSG_MAX_LEN = int(os.getenv("GEWE_MSG_MAX_LEN", "2000"))
GEWE_PUSH_RETRY_TIMES = int(os.getenv("GEWE_PUSH_RETRY_TIMES", "3"))
GEWE_PUSH_RETRY_DELAY = int(os.getenv("GEWE_PUSH_RETRY_DELAY", "5"))

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

def markdown_to_plain(text):
    """
    将 Markdown 文本转换为公众号友好的纯文本
    保留 emoji 和换行,去除 # 标题/ **加粗** / [链接](url) 等语法
    """
    if not text:
        return text
    import re
    # [文本](url) → 文本
    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'\1(\2)', text)
    # **加粗** 和 __加粗__ → 去掉包裹符
    text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
    text = re.sub(r'__([^_]+)__', r'\1', text)
    # 行首的 # 标题标记 → 去掉(保留标题文字本身)
    text = re.sub(r'^#{1,6}\s*', '', text, flags=re.MULTILINE)
    # 行首的 - / * 列表标记 → 转为 •
    text = re.sub(r'^[\s]*[-*]\s+', '• ', text, flags=re.MULTILINE)
    # 去掉 `代码` 的反引号
    text = re.sub(r'`([^`]+)`', r'\1', text)
    return text

def split_text_by_len(text, max_len):
    """
    按长度分批,优先在换行处切分(复用 TG 的 rfind 逻辑)
    返回分批后的列表,每批自动追加 (续 i/n) 尾标(仅多批时)
    """
    if not text or len(text) <= max_len:
        return [text] if text else []

    parts = []
    temp_text = text
    while len(temp_text) > 0:
        if len(temp_text) <= max_len:
            parts.append(temp_text)
            break
        split_idx = temp_text.rfind('\n', 0, max_len)
        if split_idx == -1 or split_idx == 0:
            split_idx = max_len
        parts.append(temp_text[:split_idx])
        temp_text = temp_text[split_idx:].lstrip()

    # 多批时追加尾标
    if len(parts) > 1:
        total = len(parts)
        parts = [f"{p}\n(续 {i+1}/{total})" for i, p in enumerate(parts)]
    return parts

def _gewe_enabled_check():
    """检查 GeWe 推送前置条件,返回 True 表示可推送"""
    if not GEWE_ENABLED:
        return False
    if not (GEWE_APP_ID and GEWE_TOKEN and GEWE_TO_WXIDS):
        print("⚠️  GEWE_ENABLED=true 但缺少 GEWE_APP_ID/GEWE_TOKEN/GEWE_TO_WXID,跳过微信推送")
        return False
    return True

def _gewe_request(path, payload, to_wxid=None):
    """
    发起 GeWe API 请求,带重试。返回 True/False 表示业务是否成功。
    to_wxid 可选:指定目标群(多群场景);默认用环境变量里的单群值。
    """
    import time
    target = to_wxid or GEWE_TO_WXID
    url = f"https://{GEWE_API_HOST}{path}"
    # 对齐标准代码:仅需 X-GEWE-TOKEN 和 Content-Type 两个 header
    headers = {
        "X-GEWE-TOKEN": GEWE_TOKEN,
        "Content-Type": "application/json"
    }
    body = {
        "appId": GEWE_APP_ID,
        "toWxid": target,
    }
    body.update(payload)

    for attempt in range(GEWE_PUSH_RETRY_TIMES):
        try:
            resp = requests.post(url, headers=headers, json=body, timeout=15)
            if resp.status_code == 200:
                res_data = resp.json()
                # GeWe 成功返回 ret=200, msg="操作成功"(注意不是 0)
                ret = res_data.get("ret")
                if ret == 200:
                    return True
                print(f"⚠️  GeWe API 业务失败 [{target}] (第{attempt+1}次): ret={ret}, {res_data.get('msg')}")
            else:
                print(f"⚠️  GeWe API HTTP {resp.status_code} [{target}] (第{attempt+1}次): {resp.text[:150]}")
        except Exception as e:
            print(f"⚠️  GeWe 请求异常 [{target}] (第{attempt+1}次): {e}")
        if attempt < GEWE_PUSH_RETRY_TIMES - 1:
            time.sleep(GEWE_PUSH_RETRY_DELAY)
    return False

def _gewe_broadcast(path, payload):
    """
    向所有配置的群循环推送(多群场景)。
    每个群独立重试,某个群失败不影响其他群。
    返回成功推送的群数。
    """
    success_count = 0
    total = len(GEWE_TO_WXIDS)
    for idx, wxid in enumerate(GEWE_TO_WXIDS, 1):
        print(f"[{datetime.now()}] GeWe 推送群 {idx}/{total}: {wxid}")
        if _gewe_request(path, payload, to_wxid=wxid):
            success_count += 1
        else:
            print(f"⚠️  群 {wxid} 推送失败,继续推送其他群")
    return success_count

def send_gewe_text(text):
    """
    发送纯文本消息到所有配置的微信群(分批)。
    先 markdown_to_plain 再 split_text_by_len,然后向每个群循环发送。
    """
    if not _gewe_enabled_check():
        return
    plain = markdown_to_plain(text)
    parts = split_text_by_len(plain, GEWE_MSG_MAX_LEN)
    if not parts:
        return
    total_groups = len(GEWE_TO_WXIDS)
    for i, part in enumerate(parts):
        print(f"[{datetime.now()}] GeWe 发送文字 {i+1}/{len(parts)}(向 {total_groups} 个群)...")
        _gewe_broadcast("/gewe/v2/api/message/postText", {"content": part, "ats": ""})

def build_gewe_appmsg(study):
    """
    基于手动测试通过的 appmsg XML 模板生成卡片。
    从完整 study 对象提取所有字段,填入模板。
    返回 (appmsg_xml, nct_id) 元组。
    """
    from xml.sax.saxutils import escape

    protocol = study.get("protocolSection", {})
    ident = protocol.get("identificationModule", {})
    status_module = protocol.get("statusModule", {})
    design_module = protocol.get("designModule", {})
    sponsor_module = protocol.get("sponsorCollaboratorsModule", {})
    conditions_module = protocol.get("conditionsModule", {})
    contacts_locations = protocol.get("contactsLocationsModule", {})

    nct_id = ident.get("nctId", "N/A")
    brief_title = ident.get("briefTitle", "")
    official_title = ident.get("officialTitle", "")
    overall_status = status_module.get("overallStatus", "UNKNOWN")
    phases = design_module.get("phases", []) or []
    conditions = conditions_module.get("conditions", []) or []
    # 申办方
    sponsors = sponsor_module.get("leadSponsor", {})
    sponsor_name = sponsors.get("name", "未知")

    # 更新日期:优先用 statusModule.lastUpdateSubmitDate
    update_date = status_module.get("lastUpdateSubmitDate", "")
    if not update_date:
        update_date = status_module.get("studyFirstSubmitDate", "")

    # 中国中心判断
    locations = contacts_locations.get("locations", [])
    has_china = any(loc.get("country") == "China" for loc in locations)

    # 联系人:优先 centralContacts,其次取第一个 location 的 facility/contact
    contact_name, contact_phone, contact_email, contact_facility = "未知", "未知", "未知", ""
    central_contacts = contacts_locations.get("centralContacts", [])
    if central_contacts:
        c = central_contacts[0]
        contact_name = c.get("name", "未知")
        contact_role = c.get("role", "")
        contact_phone = c.get("phone", "未知")
        contact_email = c.get("email", "未知")
        if contact_role:
            contact_name = f"{contact_name}｜{contact_role}"
    elif locations:
        loc = locations[0]
        facility = loc.get("facility", "")
        contact_facility = facility
        c = loc.get("contacts", []) or []
        if c:
            contact_name = c[0].get("name", contact_name)
            contact_phone = c[0].get("phone", contact_phone)
            contact_email = c[0].get("email", contact_email)
        if facility and not contact_name.startswith(facility):
            contact_name = f"{contact_name}｜{facility}" if contact_name != "未知" else facility

    # 翻译(复用 LLM)
    translated_title = translate_to_chinese(f"{brief_title} ({official_title})") if brief_title else nct_id
    # 标题过长截断(微信 appmsg 标题建议 < 60 字);🇨🇳 前缀让中国试验优先可见
    if has_china:
        translated_title = f"🇨🇳 {translated_title}"
    if len(translated_title) > 56:
        translated_title = translated_title[:56] + "…"

    # 状态中文化
    status_map = {"RECRUITING": "招募中", "NOT_YET_RECRUITING": "尚未招募",
                  "COMPLETED": "已完成", "ACTIVE_NOT_RECRUITING": "活跃但不招募",
                  "TERMINATED": "已终止", "WITHDRAWN": "已撤回"}
    status_cn = status_map.get(overall_status, overall_status)
    phase_cn = translate_to_chinese(", ".join(phases)) if phases else "未知"
    conditions_cn = translate_to_chinese(", ".join(conditions)) if conditions else "未知"

    # 构造描述(对齐你手动测试通过的模板)
    des_lines = [
        f"状态: {status_cn} ({overall_status})",
        f"编号: {nct_id}",
        f"阶段: {phase_cn} ({', '.join(phases) if phases else 'N/A'})",
        f"适应症: {conditions_cn}",
        f"申办方/发起人: {sponsor_name}",
        f"更新日期: {update_date}",
        f"联系人: {contact_name}",
    ]
    if contact_phone and contact_phone != "未知":
        des_lines.append(f"电话: {contact_phone}")
    if contact_email and contact_email != "未知":
        des_lines.append(f"邮箱: {contact_email}")
    if has_china:
        des_lines.append("🇨🇳 中国有中心(优先关注)")
    des_text = "\n".join(des_lines)

    # 固定缩略图(来自标准 sample_gewe_group_card_push.py 模板)
    thumb_url = ("https://mmbiz.qpic.cn/sz_mmbiz_png/vNKhjib61xHKLd8GuyfG6RLTlzuibY4P9e"
                 "JWmhSIiaLgOCWrPeCGYfk4OaTYVNjW4p0OVaJz0LUEevEhOQEGTN3UicqCEUlEtBr8qAWQApXSO0Q"
                 "/640?wx_fmt=png&tp=webp&wxfrom=5")

    # appmsg XML 模板(来自手动测试通过的结构)
    appmsg_xml = (
        '<appmsg appid="" sdkver="0">\n'
        f'\t<title>{escape(translated_title)}</title>\n'
        f'\t<des>{escape(des_text)}</des>\n'
        '\t<action />\n'
        '\t<type>5</type>\n'
        '\t<showtype>0</showtype>\n'
        '\t<soundtype>0</soundtype>\n'
        '\t<mediatagname />\n'
        '\t<messageext />\n'
        '\t<messageaction />\n'
        '\t<content />\n'
        '\t<contentattr>0</contentattr>\n'
        f'\t<url>https://clinicaltrials.gov/study/{escape(nct_id)}</url>\n'
        '\t<lowurl />\n'
        '\t<dataurl />\n'
        '\t<lowdataurl />\n'
        '\t<appattach>\n'
        '\t\t<totallen>0</totallen>\n'
        '\t\t<attachid />\n'
        '\t\t<emoticonmd5 />\n'
        '\t\t<fileext />\n'
        '\t\t<cdnthumburl />\n'
        '\t\t<cdnthumbmd5 />\n'
        '\t\t<cdnthumblength>0</cdnthumblength>\n'
        '\t\t<cdnthumbwidth>1080</cdnthumbwidth>\n'
        '\t\t<cdnthumbheight>459</cdnthumbheight>\n'
        '\t\t<cdnthumbaeskey />\n'
        '\t\t<aeskey />\n'
        '\t\t<encryver>0</encryver>\n'
        '\t</appattach>\n'
        '\t<extinfo />\n'
        '\t<sourceusername />\n'
        '\t<sourcedisplayname>ClinicalTrials.gov</sourcedisplayname>\n'
        f'\t<thumburl>{escape(thumb_url)}</thumburl>\n'
        '\t<md5 />\n'
        '\t<statextstr />\n'
        '\t<mmreadershare>\n'
        '\t\t<itemshowtype>0</itemshowtype>\n'
        '\t</mmreadershare>\n'
        '</appmsg>'
    )
    return appmsg_xml, nct_id

def send_gewe_card(study):
    """
    发送 appmsg 卡片到所有配置的微信群(基于手动测试通过的模板)。
    接收完整 study 对象,内部提取所有字段生成 appmsg XML,向每个群循环发送。
    """
    if not _gewe_enabled_check():
        return
    if not GEWE_CARD_MODE:
        return
    try:
        appmsg_xml, nct_id = build_gewe_appmsg(study)
        print(f"[{datetime.now()}] GeWe 发送卡片: {nct_id}(向 {len(GEWE_TO_WXIDS)} 个群)")
        _gewe_broadcast("/gewe/v2/api/message/postAppMsg", {
            "appmsg": appmsg_xml,
            "ats": ""
        })
    except Exception as e:
        print(f"⚠️  微信卡片生成失败(不影响TG): {e}")

def send_telegram_combined(studies):
    if not studies:
        msg = f"# 🏥 小胰宝临床情报小组日报\n\n今日未发现过去 30 天内更新且符合条件的临床试验。\n更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        send_telegram_msg(msg)
        # 同步推送到微信(空结果)
        try:
            send_gewe_text(msg)
        except Exception as e:
            print(f"⚠️  微信推送失败(不影响TG): {e}")
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

            # 同步推送该试验的微信卡片(基于手动测试通过的 appmsg 模板,内部提取完整字段)
            try:
                send_gewe_card(study)
            except Exception as e:
                print(f"⚠️  微信卡片推送失败 {nct_id}(不影响TG): {e}")
        
        send_telegram_msg(summary_msg)
        # 同步推送汇总清单到微信(纯文字分批)
        try:
            send_gewe_text(summary_msg)
        except Exception as e:
            print(f"⚠️  微信汇总推送失败(不影响TG): {e}")
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
            # 同步推送该组详情到微信(纯文字分批)
            try:
                send_gewe_text(full_detail_group)
            except Exception as e:
                print(f"⚠️  微信详情推送失败(不影响TG): {e}")
            rf.write(full_detail_group + "\n" + "="*50 + "\n\n")
        
        # 结尾感谢
        footer = "** 以上由小胰宝社区志愿者 ❤️ 服务提供，支持公益社区发展，关注“小胰宝助手”公众号，携手推动社区公益发展！"
        send_telegram_msg(footer)
        # 同步推送 footer 到微信
        try:
            send_gewe_text(footer)
        except Exception as e:
            print(f"⚠️  微信 footer 推送失败(不影响TG): {e}")
        rf.write(footer + "\n")
    
    print(f"[{datetime.now()}] Push report saved to: {report_file}")

if __name__ == "__main__":
    print(f"Starting task at {datetime.now()}")
    studies = fetch_clinical_trials()
    print(f"Found {len(studies)} studies.")
    send_telegram_combined(studies)
    print("Task completed.")