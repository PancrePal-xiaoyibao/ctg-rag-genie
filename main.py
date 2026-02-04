#!/usr/bin/env python3
"""
小胰宝临床试验智能订阅主控台
整合：下载 → 翻译 → 上传 全流程
"""
import os
import sys
import subprocess
from datetime import datetime
from pathlib import Path

# 全局配置
UPLOAD_MODE = "today"  # "today" 或 "all"

def print_banner():
    print("\n" + "="*60)
    print("🏥 小胰宝临床试验智能订阅系统")
    print("="*60)
    print(f"当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60 + "\n")

def run_step(script_name, description, args=None):
    """执行单个流程步骤"""
    print(f"\n{'='*60}")
    print(f"🔄 {description}")
    print(f"{'='*60}")
    
    cmd = ["python3", script_name]
    if args:
        cmd.extend(args)
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=False, text=True)
        print(f"✅ {description} - 完成")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} - 失败: {e}")
        return False
    except Exception as e:
        print(f"❌ {description} - 异常: {e}")
        return False

def auto_pipeline():
    """自动执行完整流程：下载 → 翻译 → 上传"""
    print_banner()
    print("📋 自动流程模式：执行完整订阅链路\n")
    
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

def manual_menu():
    """手动菜单模式：单独执行各个步骤"""
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
        
        # 显示最近 5 条
        recent = sorted(files.items(), 
                       key=lambda x: x[1].get('uploadTime', ''), 
                       reverse=True)[:5]
        
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

def main():
    """主入口"""
    if len(sys.argv) > 1 and sys.argv[1] == "--auto":
        auto_pipeline()
        return
    
    while True:
        print_banner()
        print("请选择运行模式:\n")
        print("1️⃣  自动流程 (下载 → 翻译 → 上传)")
        print("2️⃣  手动菜单 (单独执行各步骤)")
        print("0️⃣  退出系统")
        
        choice = input("\n请选择 [0-2]: ").strip()
        
        if choice == "1":
            auto_pipeline()
            input("\n按回车键返回主菜单...")
        elif choice == "2":
            manual_menu()
        elif choice == "0":
            print("\n👋 感谢使用小胰宝临床试验订阅系统！")
            sys.exit(0)
        else:
            print("❌ 无效选项，请重新选择")
            input("\n按回车键继续...")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  用户中断操作")
        sys.exit(0)
