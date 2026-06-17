"""
content_builder - 推送内容生成器(与推送渠道解耦)

核心设计:把"翻译 + 落地 + 生成内容"这一阶段从推送流程中分离出来,
一次性处理所有 studies,返回结构化的内容对象,供各渠道各自消费。

这样实现了两阶段分离:
    阶段1 (本模块): 批量下载→翻译→落地JSON→生成汇总/分组/footer 内容
    阶段2 (各渠道): 从生成好的内容对象中取自己需要的部分推送

返回的 PushContent 结构:
    studies:        原始 study 对象列表(gewe-card/feishu 卡片用)
    summary_msg:    汇总清单 Markdown(TG/gewe-txt 通用)
    detail_groups:  分组详情列表,每组含 header+body(每3个试验一组)
    footer:         结尾文案
    report_file:    本地报告文件路径
    study_details:  每个试验的详情文本列表(供 feishu 字段提取)
"""

import os
from datetime import datetime

from dotenv import load_dotenv

from lib.ctgov_api import has_china_center, get_nct_id
from lib.llm_client import translate_text as translate_to_chinese
from lib.study_data import sanitize_filename, save_study_json
from lib.text_utils import parse_list_config

load_dotenv()

SEARCH_CONDITION = os.getenv("SEARCH_CONDITION", "Pancreatic Cancer")


def format_study_detail(study):
    """
    格式化单个试验的详情文本,并落地 JSON。
    返回 (detail_text, translated_info) 元组。
    """
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

    has_china = has_china_center(study)
    china_tag = "[🇨🇳 中国有中心] " if has_china else ""

    central_contacts = contacts_locations.get("centralContacts", [])
    contact_info = "无"
    if central_contacts:
        c = central_contacts[0]
        contact_info = (f"姓名: {c.get('name', '无')}\n"
                        f"职称: {c.get('role', '无')}\n"
                        f"电话: {c.get('phone', '无')}\n"
                        f"邮箱: {c.get('email', '无')}")

    translated_title = translate_to_chinese(f"{brief_title} ({official_title})")
    translated_status = "招募中" if overall_status == "RECRUITING" else overall_status
    translated_conditions = translate_to_chinese(", ".join(conditions))

    translated_info = {
        "title_cn": translated_title,
        "status_cn": translated_status,
        "conditions_cn": translated_conditions,
        "contact_info": contact_info,
        "has_china": has_china
    }

    # 落地 JSON(auto_save_json 由调用方决定是否调用)
    detail = f"标题: {china_tag}{translated_title}\n"
    detail += f"状态: {translated_status}\n"
    detail += f"研究编号: {nct_id}\n"
    detail += f"试验阶段: {', '.join(phases)}\n"
    detail += f"适应症: {translated_conditions}\n"
    detail += f"主要研究者/联系人:\n{contact_info}\n"
    detail += f"详情链接:\nhttps://clinicaltrials.gov/study/{nct_id}\n"
    return detail, translated_info


def build_push_content(studies, auto_save_json=True):
    """
    阶段1:批量处理所有 studies。
    - 翻译每个试验(标题/状态/适应症)
    - 可选落地 JSON
    - 生成汇总清单、分组详情、footer

    参数:
        studies:        原始 study 对象列表
        auto_save_json: True 时落地每个 study 到 output/{date}-{condition}/{nct}.json

    返回:
        dict,含 studies/summary_msg/detail_groups/footer/report_file/study_details
        studies 为空时返回 None。
    """
    if not studies:
        return None

    # 准备目录和报告文件
    date_str = datetime.now().strftime('%Y-%m-%d')
    folder_name = f"{date_str}-{sanitize_filename(SEARCH_CONDITION)}"
    base_dir = os.path.join("output", folder_name)
    os.makedirs(base_dir, exist_ok=True)
    report_file = os.path.join(base_dir, "telegram_push_report.txt")

    summary_msg = f"# 🏥 小胰宝临床情报小组日报\n\n发现 {len(studies)} 个符合条件的临床试验\n\n## 【汇总清单】\n"
    study_details = []  # 每个试验的 (nct_id, detail_text, translated_info)
    total = len(studies)

    with open(report_file, "w", encoding="utf-8") as rf:
        rf.write(f"# 🏥 小胰宝临床情报小组日报 ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})\n\n")
        rf.write(f"## 🔬 胰腺癌临床试验每日更新\n\n")
        rf.write(f"- 监测日期: 最近30天\n")
        rf.write(f"- 监测要素：#胰腺癌 #KRAS/TP53/ATM/BRCA/PMT5/HER2/ERBB2相关突变\n\n")
        rf.write(f"### 发现 {total} 个符合条件的临床试验\n\n")
        rf.write(f"## 【汇总清单】\n")

        # 汇总清单
        for i, study in enumerate(studies):
            nct_id = get_nct_id(study)
            brief_title = study.get("protocolSection", {}).get("identificationModule", {}).get("briefTitle", "N/A")
            china_marker = "🇨🇳 " if has_china_center(study) else ""

            print(f"[{datetime.now()}] 翻译 {i+1}/{total}: {nct_id}")
            translated_brief = translate_to_chinese(brief_title)

            line = f"- {china_marker}标题：{translated_brief}\n  ❤️ 编号: {nct_id}\n  🔗 链接: https://clinicaltrials.gov/study/{nct_id}\n\n"
            summary_msg += line
            rf.write(line)

        rf.write("\n" + "="*50 + "\n\n")

        # 分组详情(每 3 个一组)
        detail_groups = []
        group_size = 3
        for i in range(0, total, group_size):
            group = studies[i:i+group_size]
            group_num = (i // group_size) + 1
            total_groups = (total + group_size - 1) // group_size

            print(f"[{datetime.now()}] 生成详情组 {group_num}/{total_groups}...")
            detail_header = f"## 🔔 胰腺癌临床试验详情 ({group_num}/{total_groups})\n\n"
            group_details = ""
            for j, study in enumerate(group):
                current_idx = i + j + 1
                nct_id = get_nct_id(study)
                print(f"[{datetime.now()}] 处理详情 {current_idx}/{total}: {nct_id}")
                detail_text, translated_info = format_study_detail(study)
                group_details += f"### --- 临床基本信息 ({current_idx}/{total}) ---\n"
                group_details += detail_text + "\n"
                study_details.append((nct_id, detail_text, translated_info, study))

                # 落地 JSON
                if auto_save_json:
                    save_study_json(study, extra_fields=translated_info)

            full_detail_group = detail_header + group_details
            detail_groups.append(full_detail_group)
            rf.write(full_detail_group + "\n" + "="*50 + "\n\n")

        # footer
        footer = "** 以上由小胰宝社区志愿者 ❤️ 服务提供，支持公益社区发展，关注“小胰宝助手”公众号，携手推动社区公益发展！"
        rf.write(footer + "\n")

    print(f"[{datetime.now()}] 报告已保存: {report_file}")

    return {
        "studies": studies,
        "summary_msg": summary_msg,
        "detail_groups": detail_groups,
        "footer": footer,
        "report_file": report_file,
        "study_details": study_details,
    }
