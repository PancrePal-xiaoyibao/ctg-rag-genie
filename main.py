#!/usr/bin/env python3
"""
小胰宝临床试验智能订阅主控台
统一 CLI:抓取过滤 + 多渠道推送编排

核心能力已抽取到 lib/ 公共模块:
- lib.ctgov_api:      抓取(支持 china/top/latest 过滤)
- lib.channels.*:     推送渠道(telegram/gewe/feishu/fastgpt 独立可复用)

用法示例:
    # 10 个最近中国试验,卡片推送微信
    python3 main.py --10 --china --send-gewe-card

    # 等价简写
    python3 main.py --top 10 --china --channels gewe_card

    # 全渠道推送当天试验
    python3 main.py --all-channels

    # 向后兼容:完整自动流程(抓取→翻译→FastGPT)
    python3 main.py --auto

    # 无参数:交互菜单
    python3 main.py
"""
import argparse
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# 全局配置
UPLOAD_MODE = "today"  # "today" 或 "all"

# 所有支持的渠道名
ALL_CHANNELS = ["tg", "gewe_card", "gewe_txt", "feishu", "fastgpt"]


def print_banner():
    print("\n" + "="*60)
    print("🏥 小胰宝临床试验智能订阅系统")
    print("="*60)
    print(f"当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60 + "\n")


# ============ 向后兼容:subprocess 调用(保留原有 run_step)============
def run_step(script_name, description, args=None):
    """通过 subprocess 调用脚本(向后兼容,供 auto_pipeline 和交互菜单使用)"""
    print(f"\n{'='*60}")
    print(f"▶️  {description}")
    print(f"{'='*60}\n")
    cmd = ["python3", script_name] + (args or [])
    try:
        subprocess.run(cmd, check=True, capture_output=False, text=True)
        print(f"\n✅ {description} - 完成\n")
        return True
    except subprocess.CalledProcessError as e:
        print(f"\n❌ {description} - 失败 (退出码: {e.returncode})\n")
        return False
    except Exception as e:
        print(f"\n❌ {description} - 异常: {e}\n")
        return False


def auto_pipeline():
    """自动执行完整流程:下载 → 翻译 → 上传(向后兼容 --auto)"""
    print_banner()
    print("📋 自动流程模式:执行完整订阅链路\n")

    steps = [
        ("daily_ctgov_check_tgbot.py", "步骤 1/3: 从 ClinicalTrials.gov 下载最新试验数据"),
        ("ctgov_full_sync_rag.py", "步骤 2/3: 全文翻译并生成 RAG 语料"),
        ("fastgpt_sync.py", f"步骤 3/3: 同步到 FastGPT (模式: {UPLOAD_MODE})", ["--once", f"--mode={UPLOAD_MODE}"])
    ]

    success_count = 0
    for script, desc, *extra_args in steps:
        args = extra_args[0] if extra_args else None
        if run_step(script, desc, args):
            success_count += 1
        else:
            print(f"\n⚠️  流程中断于: {desc}")
            break

    print(f"\n{'='*60}")
    print(f"📊 流程完成: {success_count}/{len(steps)} 步骤成功")
    print(f"{'='*60}\n")


# ============ CLI 参数解析 ============
def build_parser():
    """构建统一 CLI 参数解析器"""
    parser = argparse.ArgumentParser(
        description="小胰宝临床试验智能订阅系统 - 统一 CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
示例:
  %(prog)s --10 --china --send-gewe-card          10 个最近中国试验,卡片推送微信
  %(prog)s --top 20 --china --channels tg,gewe_card   简写:多渠道
  %(prog)s --all-channels                          全渠道推送当天试验
  %(prog)s --china --top 20                        仅抓取不推送(落地 JSON)
  %(prog)s --auto                                  完整自动流程(向后兼容)
  %(prog)s                                         无参数 → 交互菜单
""")

    # ---- 抓取过滤器 ----
    fetch_group = parser.add_argument_group("抓取过滤器")
    fetch_group.add_argument("--china", action="store_true",
                             help="仅抓取含中国中心的试验")
    fetch_group.add_argument("--latest", action="store_true", default=True,
                             help="按最近更新排序(默认开启)")
    fetch_group.add_argument("--top", type=int, metavar="N",
                             help="取前 N 个试验")
    # 支持 --10 / --20 这种简写(argparse 会解析为负数,需特殊处理)
    fetch_group.add_argument("--condition", type=str, default=None,
                             help="疾病条件(默认 Pancreatic Cancer)")
    fetch_group.add_argument("--status", type=str, default=None,
                             help="试验状态(默认 RECRUITING)")
    fetch_group.add_argument("--days-back", type=int, default=None,
                             help="时间窗天数(默认 30,0=不过滤)")

    # ---- 推送开关(正交)----
    push_group = parser.add_argument_group("推送开关(可组合)")
    push_group.add_argument("--send-tg", action="store_true", help="推送到 Telegram")
    push_group.add_argument("--send-gewe-card", action="store_true", help="推送 GeWe 卡片")
    push_group.add_argument("--send-gewe-txt", action="store_true", help="推送 GeWe 文字")
    push_group.add_argument("--send-feishu", action="store_true", help="推送到飞书")
    push_group.add_argument("--send-fastgpt", action="store_true", help="同步到 FastGPT")

    # ---- 多渠道简写 ----
    short_group = parser.add_argument_group("多渠道简写")
    short_group.add_argument("--channels", type=str, default=None,
                             help="逗号分隔的多渠道,如 tg,gewe_card,feishu")
    short_group.add_argument("--no-channels", type=str, default=None,
                             help="排除的渠道(逗号分隔),用于 --all-channels 时排除")
    short_group.add_argument("--all-channels", action="store_true",
                             help="开启所有渠道")

    # ---- 完整流程 ----
    parser.add_argument("--auto", action="store_true",
                        help="完整自动流程(抓取→翻译→FastGPT,向后兼容)")
    return parser


def resolve_channels(args):
    """合并 --send-* / --channels / --all-channels / --no-channels,返回最终渠道列表"""
    channels = set()

    # 1. --send-* 开关
    if args.send_tg:
        channels.add("tg")
    if args.send_gewe_card:
        channels.add("gewe_card")
    if args.send_gewe_txt:
        channels.add("gewe_txt")
    if args.send_feishu:
        channels.add("feishu")
    if args.send_fastgpt:
        channels.add("fastgpt")

    # 2. --channels 简写
    if args.channels:
        for ch in args.channels.split(","):
            ch = ch.strip()
            if ch:
                channels.add(ch)

    # 3. --all-channels
    if args.all_channels:
        channels.update(ALL_CHANNELS)

    # 4. --no-channels 排除
    if args.no_channels:
        for ch in args.no_channels.split(","):
            channels.discard(ch.strip())

    return sorted(channels)


def has_fetch_filters(args):
    """判断是否指定了任何抓取过滤器或推送渠道(用于区分 CLI 模式 vs 交互菜单)"""
    return (args.china or args.top is not None or args.condition or
            args.status or args.days_back is not None or args.channels or
            args.all_channels or args.send_tg or args.send_gewe_card or
            args.send_gewe_txt or args.send_feishu or args.send_fastgpt)


# ============ 推送调度 ============
def dispatch_push(channel, studies):
    """将 studies 分发到指定渠道"""
    print(f"\n📤 推送到渠道: {channel}({len(studies)} 个试验)")
    try:
        if channel == "tg":
            from lib.channels.telegram import send_msg
            from daily_ctgov_check_tgbot import send_telegram_combined
            # TG 用完整的编排(汇总+分组+footer)
            send_telegram_combined(studies)
        elif channel == "gewe_card":
            from lib.channels.gewe import send_cards_batch
            ok = send_cards_batch(studies)
            print(f"   GeWe 卡片: {ok}/{len(studies)} 发送成功")
        elif channel == "gewe_txt":
            from lib.channels.gewe import send_text
            # 文字模式:发一条汇总
            summary = f"# 🏥 临床试验日报\n\n发现 {len(studies)} 个试验\n"
            for i, s in enumerate(studies[:10], 1):
                from lib.ctgov_api import get_nct_id, has_china_center
                nct = get_nct_id(s)
                marker = "🇨🇳 " if has_china_center(s) else ""
                summary += f"\n{i}. {marker}{nct}"
            send_text(summary)
        elif channel == "feishu":
            from lib.channels.feishu import send_cards_batch
            ok = send_cards_batch(studies)
            print(f"   飞书卡片: {ok}/{len(studies)*1} 发送成功")
        elif channel == "fastgpt":
            from lib.channels.fastgpt import run_rag_translation, send_to_fastgpt
            print("   步骤 1/2: 全文翻译(RAG)...")
            run_rag_translation()
            print("   步骤 2/2: 同步到 FastGPT...")
            send_to_fastgpt(mode=UPLOAD_MODE)
        else:
            print(f"   ⚠️  未知渠道: {channel}")
    except Exception as e:
        print(f"   ❌ 渠道 {channel} 推送失败: {e}")


# ============ CLI 主流程 ============
def run_cli_mode(args):
    """CLI 模式:抓取 + 推送"""
    from lib.ctgov_api import fetch_studies, get_nct_id, has_china_center

    print_banner()

    # 抓取
    sort = "LastUpdatePostDate:desc" if args.latest else None
    print(f"🔍 抓取试验: condition={args.condition or '默认'}, china={args.china}, top={args.top}, days_back={args.days_back}")
    studies = fetch_studies(
        condition=args.condition,
        status=args.status,
        china_only=args.china,
        sort=sort,
        top=args.top,
        days_back=args.days_back
    )
    print(f"   抓取到 {len(studies)} 个试验")

    if not studies:
        print("⚠️  未找到符合条件的试验")
        return

    # 显示抓取结果概要
    for i, s in enumerate(studies[:5], 1):
        nct = get_nct_id(s)
        marker = "🇨🇳 " if has_china_center(s) else ""
        title = s.get("protocolSection", {}).get("identificationModule", {}).get("briefTitle", "")[:40]
        print(f"   {i}. {marker}{nct} | {title}")
    if len(studies) > 5:
        print(f"   ... 共 {len(studies)} 个")

    # 落地 JSON(无论是否推送,都落地供后续 RAG 使用)
    from lib.study_data import save_study_json
    print(f"\n💾 落地 JSON...")
    for s in studies:
        save_study_json(s, extra_fields={"fetch_mode": "cli", "china_only": args.china})
    print(f"   已落地 {len(studies)} 个 JSON")

    # 推送
    channels = resolve_channels(args)
    if not channels:
        print("\n📋 未指定推送渠道(仅抓取+落地完成)。如需推送,加 --send-* 或 --channels 参数")
        return

    print(f"\n📤 推送到 {len(channels)} 个渠道: {', '.join(channels)}")
    for ch in channels:
        dispatch_push(ch, studies)

    print(f"\n{'='*60}")
    print(f"✅ 全部完成:抓取 {len(studies)} 个,推送 {len(channels)} 个渠道")
    print(f"{'='*60}")


# ============ 交互菜单(向后兼容)============
def show_sync_status():
    """显示 FastGPT 同步状态"""
    print(f"\n{'='*60}")
    print("📊 FastGPT 同步状态")
    print(f"{'='*60}\n")

    state_file = Path("data/fastgpt_sync_state.json")
    if not state_file.exists():
        print("⚠️  状态文件不存在")
        return

    try:
        import json
        with open(state_file, 'r', encoding='utf-8') as f:
            state = json.load(f)
        files = state.get("files", {})
        print(f"✅ 已同步文件数: {len(files)}")
        recent = sorted(files.items(), key=lambda x: x[1].get('uploadTime', ''), reverse=True)[:5]
        if recent:
            print("\n最近同步:")
            for nct_id, info in recent:
                filename = info.get('filename', nct_id)
                upload_time = info.get('uploadTime', 'N/A')
                print(f"  - {filename}")
                print(f"    NCT: {nct_id}, 时间: {upload_time}")
    except Exception as e:
        print(f"❌ 读取状态失败: {e}")


def toggle_upload_mode():
    """切换上传模式"""
    global UPLOAD_MODE
    if UPLOAD_MODE == "today":
        UPLOAD_MODE = "all"
        print("\n✅ 已切换到: 全部含历史")
    else:
        UPLOAD_MODE = "today"
        print("\n✅ 已切换到: 仅当天")


def manual_menu():
    """手动菜单模式:单独执行各个步骤(向后兼容)"""
    while True:
        print_banner()
        print("📋 手动菜单模式\n")
        print(f"当前上传模式: {UPLOAD_MODE} ({'仅当天' if UPLOAD_MODE == 'today' else '全部含历史'})\n")
        print("1️⃣  下载最新临床试验 (daily_ctgov_check_tgbot.py)")
        print("2️⃣  全文翻译生成 RAG (ctgov_full_sync_rag.py)")
        print("3️⃣  同步到 FastGPT (fastgpt_sync.py --once)")
        print("4️⃣  查看 FastGPT 同步状态")
        print("5️⃣  切换上传模式 (当天/全部)")
        print("6️⃣  返回主菜单")
        print("0️⃣  退出系统")

        choice = input("\n请选择操作 [0-6]: ").strip()

        if choice == "1":
            run_step("daily_ctgov_check_tgbot.py", "下载最新临床试验")
        elif choice == "2":
            run_step("ctgov_full_sync_rag.py", "全文翻译生成 RAG")
        elif choice == "3":
            run_step("fastgpt_sync.py", f"同步到 FastGPT (模式: {UPLOAD_MODE})", ["--once", f"--mode={UPLOAD_MODE}"])
        elif choice == "4":
            show_sync_status()
        elif choice == "5":
            toggle_upload_mode()
        elif choice == "6":
            break
        elif choice == "0":
            print("\n👋 感谢使用小胰宝临床试验订阅系统！")
            sys.exit(0)
        else:
            print("❌ 无效选项，请重新选择")

        input("\n按回车键继续...")


def interactive_menu():
    """顶层交互菜单(向后兼容,无参数时进入)"""
    print_banner()
    print("📋 主菜单\n")
    print("1️⃣  自动流程 (抓取 → 翻译 → 上传)")
    print("2️⃣  手动菜单 (单独执行各步骤)")
    print("3️⃣  快捷推送: 10 个最近中国试验 → 微信卡片")
    print("0️⃣  退出")

    choice = input("\n请选择 [0-3]: ").strip()
    if choice == "1":
        auto_pipeline()
    elif choice == "2":
        manual_menu()
    elif choice == "3":
        # 快捷入口:复用 CLI 模式
        args = argparse.Namespace(
            china=True, latest=True, top=10, condition=None, status=None, days_back=0,
            send_tg=False, send_gewe_card=True, send_gewe_txt=False,
            send_feishu=False, send_fastgpt=False,
            channels=None, no_channels=None, all_channels=False
        )
        run_cli_mode(args)
    elif choice == "0":
        print("\n👋 感谢使用小胰宝临床试验订阅系统！")
        sys.exit(0)
    else:
        print("❌ 无效选项")


def parse_short_top(argv):
    """预处理 sys.argv:把 --10/--20 等转为 --top 10/--top 20"""
    processed = []
    i = 0
    while i < len(argv):
        arg = argv[i]
        # 匹配 --<数字> 如 --10 --20
        if arg.startswith("--") and arg[2:].isdigit():
            processed.extend(["--top", arg[2:]])
        else:
            processed.append(arg)
        i += 1
    return processed


def main():
    """主入口:解析参数,路由到 CLI 模式 / 自动流程 / 交互菜单"""
    # 向后兼容:--auto 直接进自动流程
    if len(sys.argv) > 1 and sys.argv[1] == "--auto":
        auto_pipeline()
        return

    # 预处理 --10 等简写
    argv = parse_short_top(sys.argv[1:])

    # 无参数 → 交互菜单
    if not argv:
        interactive_menu()
        return

    parser = build_parser()
    args = parser.parse_args(argv)

    # --auto 标志
    if args.auto:
        auto_pipeline()
        return

    # 有任何过滤器或推送参数 → CLI 模式
    if has_fetch_filters(args):
        run_cli_mode(args)
    else:
        # 有参数但无实际操作(如只传 --latest)→ 显示帮助
        parser.print_help()


if __name__ == "__main__":
    main()
