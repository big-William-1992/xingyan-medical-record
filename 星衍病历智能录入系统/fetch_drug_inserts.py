#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批量下载药品说明书（从 120ask.com）
用法: python fetch_drug_inserts.py [--max-id 220000] [--workers 20]
结果保存到 kg_data/drug_inserts.json
"""
import os, sys, re, json, time, urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT = os.path.join(BASE_DIR, "kg_data", "drug_inserts.json")

# 需要提取的字段
FIELDS = ["商品名称", "通用名称", "主要成份", "适应症", "用法用量",
           "不良反应", "禁忌", "注意事项", "药物相互作用", "药理毒理",
           "药代动力学", "贮藏", "规格", "有效期", "批准文号", "生产企业"]

HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}


def fetch_one(drug_id):
    """抓取单个药品说明书，返回 (drug_name, info_dict) 或 None"""
    url = f"https://yp.120ask.com/manual/{drug_id}.html"
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        html = urllib.request.urlopen(req, timeout=8).read().decode("utf-8", errors="ignore")
    except Exception:
        return None

    idx = html.find("Detailed-instructions")
    if idx < 0:
        return None

    chunk = html[idx:idx + 8000]
    text = re.sub(r"<[^>]+>", "\n", chunk)
    lines = [l.strip() for l in text.split("\n") if l.strip()]

    if len(lines) < 4:
        return None

    # 解析字段：字段名和值交替出现
    info = {}
    i = 1  # 跳过第一行提示语
    while i < len(lines) - 1:
        key = lines[i]
        # 检查是否是已知字段名
        matched_field = None
        for f in FIELDS:
            if key == f or key.startswith(f):
                matched_field = f
                # 如果字段名被截断（如"孕妇及哺乳\n期妇女用药"），合并下一行
                remaining = key[len(f):]
                if remaining:
                    i += 1
                    continue
                break
        if matched_field:
            val = lines[i + 1] if i + 1 < len(lines) else ""
            info[matched_field] = val
            i += 2
        else:
            i += 1

    # 获取药品名称
    name = info.get("通用名称") or info.get("商品名称") or ""
    if not name:
        # 尝试从 title 获取
        title_m = re.search(r"<title>([^<]+?)价格_说明书", html)
        if title_m:
            name = re.sub(r'^.*?\s', '', title_m.group(1)).strip()

    if not name or len(name) < 2:
        return None

    # 至少有适应症或用法用量才算有效
    if not info.get("适应症") and not info.get("用法用量") and not info.get("主要成份"):
        return None

    return (name, info)


def load_existing():
    """加载已有数据"""
    if os.path.exists(OUTPUT):
        try:
            with open(OUTPUT, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_data(data):
    """保存数据"""
    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-id", type=int, default=220000)
    parser.add_argument("--workers", type=int, default=15)
    parser.add_argument("--start", type=int, default=1)
    args = parser.parse_args()

    existing = load_existing()
    print(f"[药品说明书] 已有缓存: {len(existing)} 种")
    print(f"[药品说明书] 扫描范围: {args.start} ~ {args.max_id}, 并发: {args.workers}")

    new_count = 0
    scanned = 0
    batch_save = 0

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {}
        for did in range(args.start, args.max_id + 1):
            fut = pool.submit(fetch_one, did)
            futures[fut] = did

            # 控制内存：每 5000 个提交等待一批完成
            if len(futures) >= 5000:
                for f in as_completed(futures):
                    scanned += 1
                    result = f.result()
                    if result:
                        name, info = result
                        if name not in existing:
                            existing[name] = info
                            new_count += 1
                            batch_save += 1
                futures = {}

                # 每批保存一次
                if batch_save >= 50:
                    save_data(existing)
                    batch_save = 0

                if scanned % 5000 == 0:
                    print(f"  进度: {scanned}/{args.max_id} | 新增: {new_count} | 总计: {len(existing)}")

        # 处理剩余
        for f in as_completed(futures):
            scanned += 1
            result = f.result()
            if result:
                name, info = result
                if name not in existing:
                    existing[name] = info
                    new_count += 1

    save_data(existing)
    print(f"\n✅ 完成! 扫描 {scanned} 页, 新增 {new_count} 种, 总计 {len(existing)} 种药品说明书")
    print(f"   保存至: {OUTPUT}")


if __name__ == "__main__":
    main()
