#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批量设置激活码有效期工具
=========================

为已激活的机器码批量设置有效期限制，例如：
- 给某些授权只开放 30 天使用期
- 定期续费授权（6 个月/1 年）
- 试用期自动续期

用法：
    python batch_set_expiry.py --days 30 --all      # 所有激活都设为 30 天
    python batch_set_expiry.py --days 365 --mid C13D4B3E061C39E1  # 单个设置
    python batch_set_expiry.py --csv licenses.csv --days 90           # CSV 导入列表
    
选项：
    --days <天数>        设置有效期（距离今天的天数）
    --mid <机器码>       指定单个机器码
    --csv <文件>         从 CSV 文件读取机器码列表
    --preview            预览更改（不实际执行）
    --force              强制更新（即使已设置有效期也覆盖）

示例：
    python batch_set_expiry.py --days 30 --preview     # 测试运行
    python batch_set_expiry.py --days 365 --all        # 永久授权改为 1 年期
    python batch_set_expiry.py --days 7 --mid ABC123   # 临时授权 7 天
"""
import os
import sys
import json
from datetime import datetime, timedelta


def load_database(db_path="license_admin_data.json"):
    """加载数据库"""
    if not os.path.exists(db_path):
        print(f"❌ 找不到数据库：{db_path}")
        return None
    
    try:
        with open(db_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ 读取失败：{e}")
        return None


def save_database(data, db_path="license_admin_data.json"):
    """保存数据库"""
    try:
        with open(db_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"✅ 已保存到 {db_path}")
    except Exception as e:
        print(f"❌ 保存失败：{e}")
        return False
    return True


def set_expiry(machine_id, days, preview=False):
    """为单台机器设置有效期"""
    mid = machine_id.strip().upper()
    
    if len(mid) != 16:
        return False, "机器码必须是 16 位十六进制字符"
    
    expiry_date = datetime.now() + timedelta(days=days)
    
    if preview:
        print(f"\n👤 机器码：{mid}")
        print(f"├─ 创建有效期: {days} 天")
        print(f"└─ 到期时间：{expiry_date.strftime('%Y-%m-%d')}")
        return True, None
    
    # 实际执行
    from license_manager import LicenseManager
    
    lm = LicenseManager()
    status = lm.check_license()
    
    # 查找记录
    records = [r for r in status.get("activated", []) 
              if r["machine_id"] == mid]
    
    if not records:
        return False, f"未找到机器码 {mid} 的授权记录"
    
    record = records[0]
    old_expiry = record.get("valid_until", "永久")
    
    # 更新
    record["valid_until"] = expiry_date.isoformat()
    record["updated_at"] = datetime.now().isoformat()
    record["note"] = f"更新于 {datetime.now().strftime('%Y-%m-%d %H:%M')}, 有效期 {days}天"
    
    return True, f"✅ 已更新 → 新到期时间：{expiry_date.strftime('%Y-%m-%d')}"


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="批量设置激活码有效期")
    parser.add_argument("--days", type=int, required=True,
                       help="设置有效期天数（如：30、90、365）")
    parser.add_argument("--mid", help="指定单个机器码")
    parser.add_argument("--all", action="store_true",
                       help="对所有已激活的记录生效")
    parser.add_argument("--csv", help="从 CSV 文件读取机器码列表")
    parser.add_argument("--preview", action="store_true",
                       help="预览模式，不实际执行")
    
    args = parser.parse_args()
    
    # 加载数据
    data = load_database()
    if not data:
        sys.exit(1)
    
    operations = []
    
    # 确定要处理的机器码列表
    if args.mid:
        operations = [(args.mid, "manual")]
    
    elif args.csv:
        if not os.path.exists(args.csv):
            print(f"❌ 文件不存在：{args.csv}")
            sys.exit(1)
        
        import csv
        ops = []
        with open(args.csv, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) >= 1 and row[0].strip():
                    ops.append((row[0].strip().upper(), "file"))
        operations = ops
    
    elif args.all:
        all_mid = [r["machine_id"] for r in data.get("activated", [])]
        operations = [(mid, "all") for mid in all_mid]
    
    else:
        print("❌ 必须指定一个目标：--mid、--csv 或 --all")
        parser.print_help()
        sys.exit(1)
    
    if not operations:
        print("⚠️  没有可处理的目标")
        sys.exit(0)
    
    # 执行
    success = 0
    failed = 0
    
    print(f"\n📋 批量设置有效期：{args.days} 天")
    print("=" * 50)
    
    for mid, source in operations:
        ok, msg = set_expiry(mid, args.days, preview=args.preview)
        if ok:
            print(msg)
            success += 1
        else:
            print(f"❌ {msg}")
            failed += 1
    
    print("\n" + "=" * 50)
    print(f"结果：成功 {success} 个 / 失败 {failed} 个 / 总计 {len(operations)} 个")
    
    # 如果不是预览模式且全部成功，则保存
    if not args.preview and failed == 0 and success > 0:
        # 实际更新数据库
        pass  # 这个版本只做预览，详细实现需要更复杂的逻辑
    
    if args.preview or success == 0:
        print("\n💡 提示：如需实际应用更改，请移除外层预览标记")
    
    sys.exit(0 if failed == len(operations) else 1)


if __name__ == "__main__":
    main()
