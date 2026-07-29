#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
神农中医药数据集（ShenNong TCM）转换器

数据源：
  HuggingFace: https://huggingface.co/datasets/michaelwzhu/ShenNong_TCM_Dataset
  ModelScope:  https://modelscope.cn/datasets/xiaofengalg/ShenNong_TCM_Dataset
  文件：ChatMed_TCM-v0.2.json（约 110MB，113K 条指令数据）

数据格式：
  [{"instruction": "问题", "input": "", "output": "回答"}, ...]
  由 ChatGPT-3.5 基于中医药知识图谱实体生成，覆盖：
  - 中药材：性味归经、功效主治、用法用量、禁忌
  - 方剂：组成、功效、主治、用法
  - 疾病：辨证论治、治法、推荐方药

本脚本从 QA 对中抽取结构化知识，输出统一 schema：
  {
    "source": "ShenNong TCM",
    "herbs":    {"药材名": {"性味":..., "归经":..., "功效":[...], "主治":[...]}},
    "formulas": {"方剂名": {"组成":[...], "功效":..., "主治":...}},
    "diseases": {"疾病名": {"中医治法":..., "推荐方药":[...], "辨证":...}}
  }

用法：
  python convert_shennong.py ChatMed_TCM-v0.2.json -o kg_data/shennong.json
  python convert_shennong.py ChatMed_TCM-v0.2.json --limit 50000
"""
import argparse
import json
import os
import re
import sys
from collections import defaultdict


# ─── 实体识别模式 ──────────────────────────────────────────
# 中药材问题模式
HERB_PATTERNS = [
    re.compile(r"中药[材]?\s*[「「]?([^\s,，。？?！!」」的]+)[」」]?\s*(?:的|有什么|有何)?(?:性味|功效|作用|主治|归经|用法|禁忌)"),
    re.compile(r"[「「]?([^\s,，。？?！!」」的]{2,12})[」」]?\s*(?:这味药|这味中药|此药|该药)"),
    re.compile(r"(?:请介绍|介绍一下|说说)\s*[「「]?([^\s,，。？?！!」」的]{2,12})[」」]?\s*(?:这味|这味中)?药"),
]

# 方剂问题模式
FORMULA_PATTERNS = [
    re.compile(r"方剂\s*[「「]?([^\s,，。？?！!」」的]+)[」」]?\s*(?:的|有什么|有何)?(?:组成|功效|主治|用法)"),
    re.compile(r"[「「]?([^\s,，。？?！!」」的]{2,15}(?:汤|散|丸|饮|膏|丹|方))[」」]?\s*(?:的|有什么)?(?:组成|功效|主治)"),
    re.compile(r"(?:请介绍|介绍一下)\s*[「「]?([^\s,，。？?！!」」的]{2,15}(?:汤|散|丸|饮|膏|丹|方))[」」]?"),
]

# 疾病辨证模式
DISEASE_PATTERNS = [
    re.compile(r"[「「]?([^\s,，。？?！!」」的]{2,15})[」」]?\s*(?:的|如何|怎么)?(?:中医治疗|辨证论治|治法|中医治法)"),
    re.compile(r"(?:中医|中药)(?:如何|怎么)?治疗\s*[「「]?([^\s,，。？?！!」」的]{2,15})[」」]?"),
]


def extract_entity_name(text, patterns):
    """从问题文本中提取实体名"""
    for pat in patterns:
        m = pat.search(text)
        if m:
            return m.group(1).strip()
    return None


def parse_herb_output(output):
    """从回答中解析中药材属性"""
    info = {}
    # 性味
    m = re.search(r"性味[：:]\s*(.+?)(?:\n|$)", output)
    if m:
        info["性味"] = m.group(1).strip()
    # 归经
    m = re.search(r"归经[：:]\s*(.+?)(?:\n|$)", output)
    if m:
        info["归经"] = m.group(1).strip()
    # 功效
    m = re.search(r"功效[：:]\s*(.+?)(?:\n|$)", output)
    if m:
        info["功效"] = [x.strip() for x in re.split(r"[、,，;；]", m.group(1)) if x.strip()]
    # 主治
    m = re.search(r"主治[：:]\s*(.+?)(?:\n|$)", output)
    if m:
        info["主治"] = [x.strip() for x in re.split(r"[、,，;；]", m.group(1)) if x.strip()]
    return info


def parse_formula_output(output):
    """从回答中解析方剂属性"""
    info = {}
    # 组成
    m = re.search(r"组成[：:]\s*(.+?)(?:\n|$)", output)
    if m:
        info["组成"] = [x.strip() for x in re.split(r"[、,，;；]", m.group(1)) if x.strip()]
    # 功效
    m = re.search(r"功效[：:]\s*(.+?)(?:\n|$)", output)
    if m:
        info["功效"] = m.group(1).strip()
    # 主治
    m = re.search(r"主治[：:]\s*(.+?)(?:\n|$)", output)
    if m:
        info["主治"] = m.group(1).strip()
    return info


def parse_disease_output(output):
    """从回答中解析疾病辨证"""
    info = {}
    # 治法
    m = re.search(r"治法[：:]\s*(.+?)(?:\n|$)", output)
    if m:
        info["中医治法"] = m.group(1).strip()
    # 方药
    m = re.search(r"(?:方药|推荐方|主方)[：:]\s*(.+?)(?:\n|$)", output)
    if m:
        info["推荐方药"] = [x.strip() for x in re.split(r"[、,，;；]", m.group(1)) if x.strip()]
    # 辨证
    m = re.search(r"辨证[：:]\s*(.+?)(?:\n|$)", output)
    if m:
        info["辨证"] = m.group(1).strip()
    return info


def convert(records, limit=0):
    """从 QA 记录中抽取结构化知识"""
    herbs = {}
    formulas = {}
    diseases = {}
    stats = {"herb": 0, "formula": 0, "disease": 0, "skip": 0}

    for i, rec in enumerate(records):
        if limit and i >= limit:
            break
        if not isinstance(rec, dict):
            continue

        instruction = (rec.get("instruction") or "").strip()
        output = (rec.get("output") or "").strip()
        if not instruction or not output:
            stats["skip"] += 1
            continue

        # 尝试识别中药材
        name = extract_entity_name(instruction, HERB_PATTERNS)
        if name and len(name) <= 12:
            info = parse_herb_output(output)
            if info:
                if name in herbs:
                    # 合并
                    for k, v in info.items():
                        if isinstance(v, list):
                            existing = herbs[name].get(k, [])
                            for item in v:
                                if item not in existing:
                                    existing.append(item)
                            herbs[name][k] = existing
                        elif k not in herbs[name]:
                            herbs[name][k] = v
                else:
                    herbs[name] = info
                stats["herb"] += 1
                continue

        # 尝试识别方剂
        name = extract_entity_name(instruction, FORMULA_PATTERNS)
        if name and len(name) <= 20:
            info = parse_formula_output(output)
            if info:
                if name not in formulas:
                    formulas[name] = info
                stats["formula"] += 1
                continue

        # 尝试识别疾病辨证
        name = extract_entity_name(instruction, DISEASE_PATTERNS)
        if name and len(name) <= 15:
            info = parse_disease_output(output)
            if info:
                if name not in diseases:
                    diseases[name] = info
                stats["disease"] += 1
                continue

        stats["skip"] += 1

    return herbs, formulas, diseases, stats


def main():
    ap = argparse.ArgumentParser(description="神农中医药数据集 → 星衍知识 JSON")
    ap.add_argument("input", help="ChatMed_TCM-v0.2.json 路径")
    ap.add_argument("-o", "--output", default=None)
    ap.add_argument("--limit", type=int, default=0,
                    help="最多处理记录数（0=全部）")
    args = ap.parse_args()

    if not os.path.isfile(args.input):
        print(f"找不到输入文件：{args.input}")
        sys.exit(1)

    print("加载数据（文件较大，请稍候）...")
    with open(args.input, "r", encoding="utf-8") as fh:
        records = json.load(fh)
    print(f"读取记录：{len(records)} 条")

    herbs, formulas, diseases, stats = convert(records, args.limit)

    # 转换为统一 schema
    # 将中药材和方剂也映射到 diseases 格式以便知识图谱加载
    disease_out = {}
    for name, info in diseases.items():
        entry = {"type": "疾病"}
        entry.update(info)
        disease_out[name] = entry

    # 中药材 → 药物实体
    drug_out = {}
    for name, info in herbs.items():
        entry = {"type": "中药材"}
        entry.update(info)
        drug_out[name] = entry

    # 方剂 → 药物实体
    for name, info in formulas.items():
        entry = {"type": "方剂"}
        entry.update(info)
        drug_out[name] = entry

    result = {
        "source": "ShenNong TCM (michaelwzhu)",
        "diseases": disease_out,
        "drugs": drug_out,
    }

    out = args.output or os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "kg_data", "shennong.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(result, fh, ensure_ascii=False, indent=2)

    print(f"\n抽取结果：")
    print(f"  中药材：{len(herbs)} 种")
    print(f"  方剂：{len(formulas)} 首")
    print(f"  疾病辨证：{len(diseases)} 种")
    print(f"  跳过：{stats['skip']} 条")
    print(f"输出文件：{out}")


if __name__ == "__main__":
    main()
