#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
激活历史导出与统计工具
=======================

生成各种格式的激活历史报告：
1. CSV 表格导出（Excel 兼容）
2. Markdown 报表（适合打印/提交）
3. JSON 原始数据备份
4. 统计分析（按日期/机器码/有效期）

用法：
    python export_licenses.py [选项]
    
选项：
    --csv <输出文件>      导出为 CSV
    --md <输出文件>       导出为 Markdown 报表
    --json <输出文件>     导出为 JSON 备份
    --stats               显示统计信息
    --recent <天数>       显示最近 N 天的记录 (默认 30)
    --expired             只显示过期的
    --all                 显示所有记录（不限制时间）

示例：
    python export_licenses.py --csv activations.csv
    python export_licenses.py --md report.md --stats
    python export_licenses.py --all --csv full_backup.csv --json backup.json
"""
import os
import sys
import json
import argparse
from datetime import datetime, timedelta
from dateutil.parser import parse as parse_date


# ─── 读取数据库 ──────────────────────────────


def load_database(db_path="license_admin_data.json"):
    """加载本地数据库"""
    if not os.path.exists(db_path):
        print(f"⚠️  找不到数据库文件：{db_path}")
        print("💡 请先运行 manage_license.py 生成一些数据")
        return None
    
    try:
        with open(db_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ 读取数据库失败：{e}")
        return None


# ─── 导出函数 ───────────────────────────────


def export_csv(data, output_path):
    """导出为 CSV（Excel 兼容）"""
    if not data or not data.get("activated"):
        print("❌ 没有可导出的数据")
        return False
    
    records = data["activated"]
    if not records:
        print("⚠️  激活记录为空")
        return False
    
    import csv
    
    with open(output_path, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        
        # 表头
        writer.writerow([
            "序号", "机器码", "创建时间", "激活时间", 
            "激活码", "有效期限", "备注"
        ])
        
        # 数据行
        for i, rec in enumerate(records, 1):
            valid_until = rec.get("valid_until", "永久")
            if valid_until != "永久":
                try:
                    dt = parse_date(valid_until)
                    valid_until = dt.strftime("%Y-%m-%d")
                except:
                    pass
            
            writer.writerow([
                i,
                rec.get("machine_id", ""),
                rec.get("created_at", "")[:10],
                rec.get("activated_at", "")[:10],
                rec.get("activation_code", ""),
                valid_until,
                rec.get("status", "")
            ])
    
    print(f"✅ 已导出 {len(records)} 条记录到：{output_path}")
    return True


def export_markdown(data, output_path):
    """导出为 Markdown 报表"""
    if not data or not data.get("activated"):
        print("❌ 没有可导出的数据")
        return False
    
    records = data["activated"]
    
    lines = []
    lines.append("# 📊 星衍病历录入系统 - 激活历史记录报表\n")
    lines.append(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    lines.append("---\n\n")
    
    # 统计表
    lines.append("## 1️⃣ 统计数据\n\n")
    total = len(records)
    permanent = sum(1 for r in records if not r.get("valid_until"))
    expiring_soon = sum(1 for r in records 
                       if r.get("valid_until") and 
                       datetime.fromisoformat(r["valid_until"]) > datetime.now())
    
    lines.append(f"| 项目 | 数量 |\n|------|------|\n")
    lines.append(f"| 总激活数 | {total} |\n")
    lines.append(f"| 永久授权 | {permanent} |\n")
    lines.append(f"| 有期限授权 | {total - permanent} |\n")
    lines.append("\n---\n\n")
    
    # 详细列表
    lines.append("## 2️⃣ 激活详情列表\n\n")
    lines.append("| # | 机器码 | 激活时间 | 有效期限 | 激活码 |\n")
    lines.append("|---|--------|----------|----------|--------|\n")
    
    for i, rec in enumerate(records, 1):
        mid = rec.get("machine_id", "")[:16] + ("..." if len(rec.get("machine_id", "")) > 20 else "")
        activated = rec.get("activated_at", "")[:10]
        
        valid_until = rec.get("valid_until")
        if valid_until:
            try:
                dt = parse_date(valid_until)
                valid_until = dt.strftime("%Y-%m-%d")
            except:
                valid_until = "永久"
        else:
            valid_until = "永久"
        
        code = rec.get("activation_code", "")[:16] + ("..." if len(rec.get("activation_code", "")) > 16 else "")
        
        lines.append(f"| {i} | `{mid}` | {activated} | {valid_until} | `{code}` |\n")
    
    lines.append("\n---\n\n")
    lines.append("*本报告由 `export_licenses.py` 自动生成*\n")
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    
    print(f"✅ 已导出 Markdown 报表到：{output_path}")
    return True


def export_json(data, output_path):
    """导出为 JSON 备份"""
    if not data:
        print("❌ 没有可导出的数据")
        return False
    
    # 添加元数据
    backup = {
        "backup_time": datetime.now().isoformat(),
        "version": "1.0",
        **data
    }
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(backup, f, ensure_ascii=False, indent=2)
    
    print(f"✅ 已导出 JSON 备份到：{output_path}")
    return True


def show_stats(data):
    """显示统计信息"""
    if not data or not data.get("activated"):
        print("❌ 没有统计数据")
        return
    
    records = data["activated"]
    
    print("\n" + "=" * 50)
    print("📊 激活统计信息")
    print("=" * 50)
    
    # 总数
    print(f"\n🔹 总激活数：{len(records)}")
    
    # 永久 vs 限时
    permanent = [r for r in records if not r.get("valid_until")]
    limited = [r for r in records if r.get("valid_until")]
    
    print(f"🔹 永久授权：{len(permanent)}")
    print(f"🔹 限时授权：{len(limited)}")
    
    # 如果有限时授权，分析有效期分布
    if limited:
        print(f"\n├─ 即将过期 (<7 天): {sum(1 for r in limited if parse_date(r['valid_until']) < datetime.now() + timedelta(days=7))}")
        print(f"├─ 未来 1-3 个月：{sum(1 for r in limited if parse_date(r['valid_until']) <= datetime.now() + timedelta(days=90))}")
        print(f"└─ 长期 (>3 个月): {sum(1 for r in limited if parse_date(r['valid_until']) > datetime.now() + timedelta(days=90))}")
    
    # 按月份统计
    from collections import Counter
    months = Counter()
    for rec in records:
        activated = rec.get("activated_at")
        if activated:
            try:
                dt = parse_date(activated)
                months[dt.strftime("%Y-%m")] += 1
            except:
                pass
    
    if months:
        print(f"\n🗓️  按月份分布:")
        for month in sorted(months.keys(), reverse=True)[:6]:
            print(f"   {month}: {months[month]} 个")
    
    print("\n" + "=" * 50)


# ─── 主程序 ──────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="激活历史导出与统计工具")
    parser.add_argument("--csv", help="导出为 CSV 文件")
    parser.add_argument("--md", help="导出为 Markdown 报表")
    parser.add_argument("--json", help="导出为 JSON 备份")
    parser.add_argument("--stats", action="store_true", help="显示统计信息")
    parser.add_argument("--recent", type=int, default=30,
                       help="显示最近 N 天的记录 (默认 30)")
    parser.add_argument("--expired", action="store_true",
                       help="只显示已过期的记录")
    parser.add_argument("--all", action="store_true",
                       help="显示所有记录（不限制时间）")
    
    args = parser.parse_args()
    
    # 加载数据
    data = load_database()
    if not data:
        sys.exit(1)
    
    # 筛选记录
    if args.recent and not args.all:
        cutoff = datetime.now() - timedelta(days=args.recent)
        data["activated"] = [r for r in data.get("activated", [])
                            if r.get("activated_at") and 
                            parse_date(r["activated_at"]) >= cutoff]
    
    # 只显示过期
    if args.expired:
        now = datetime.now()
        data["activated"] = [r for r in data.get("activated", [])
                            if r.get("valid_until") and 
                            parse_date(r["valid_until"]) < now]
    
    # 执行导出
    success = True
    
    if args.csv:
        success = export_csv(data, args.csv) and success
    
    if args.md:
        success = export_markdown(data, args.md) and success
    
    if args.json:
        success = export_json(data, args.json) and success
    
    if args.stats:
        show_stats(data)
    
    if not any([args.csv, args.md, args.json, args.stats]):
        # 默认显示统计信息
        show_stats(data)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    # 检查是否安装了 dateutil
    try:
        from dateutil.parser import parse as parse_date
    except ImportError:
        print("⚠️  缺少依赖：python-dateutil")
        print("💡 安装：pip install python-dateutil")
        sys.exit(1)
    
    main()
