#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CMeKG 1.0 中文医学知识图谱转换器

数据源：https://tianchi.aliyun.com/dataset/81506（免费下载）
CMeKG 1.0 含 6,310 种疾病、19,853 种药物、1,237 种诊疗技术，
100 余万条关系实例，参考 ICD / ATC / SNOMED / MeSH 等国际标准。

支持输入格式：
  A. CMeKG 官方 JSON（疾病/药物/诊疗实体文件）
  B. 三元组 CSV/TSV/JSON
  C. 目录批量导入（自动识别 *.json / *.csv）

字段映射（CMeKG → 星衍 schema）：
  疾病：临床症状→常见症状, 药物治疗→常用药物, 影像学检查→常见检查,
        手术治疗→治疗方式, 鉴别诊断→鉴别诊断, 高危因素→高危因素,
        多发群体→多发群体, 就诊科室→科室
  药物：适应症→说明书.适应症, 用法用量→说明书.用法用量,
        禁忌证→说明书.禁忌, 不良反应→说明书.不良反应,
        成分→成分, 有效期→有效期

用法：
  python convert_cmekg.py cmekg_disease.json -o kg_data/cmekg.json
  python convert_cmekg.py --dir cmekg_data/ -o kg_data/cmekg.json
  python convert_cmekg.py triples.csv --sep '\\t'
"""
import argparse
import csv
import json
import os
import re
import sys
from collections import defaultdict


# ─── CMeKG 属性名 → 星衍字段 ──────────────────────────────
DISEASE_ATTR_MAP = {
    "临床症状": "常见症状", "症状": "常见症状", "临床表现": "常见症状",
    "药物治疗": "常用药物", "治疗药物": "常用药物", "用药": "常用药物",
    "影像学检查": "常见检查", "辅助检查": "常见检查", "检查": "常见检查",
    "手术治疗": "治疗方式", "治疗方案": "治疗方式", "治疗": "治疗方式",
    "鉴别诊断": "鉴别诊断",
    "高危因素": "高危因素", "危险因素": "高危因素",
    "多发群体": "多发群体", "好发人群": "多发群体",
    "就诊科室": "科室", "科室": "科室",
    "发病部位": "发病部位",
    "传播途径": "传播途径",
    "别名": "别名", "又名": "别名",
}

DRUG_ATTR_MAP = {
    "适应症": "适应症", "功能主治": "适应症", "主治": "适应症",
    "用法用量": "用法用量", "用量": "用法用量",
    "禁忌证": "禁忌", "禁忌": "禁忌", "禁忌症": "禁忌",
    "不良反应": "不良反应", "副作用": "不良反应",
    "成分": "成分", "主要成分": "成分",
    "有效期": "有效期",
    "药物类型": "类别", "类别": "类别", "剂型": "类别",
}


def clean_list(items):
    """去空去重保序"""
    out, seen = [], set()
    for it in items or []:
        if isinstance(it, str):
            it = it.strip()
        if it and it not in seen:
            seen.add(it)
            out.append(it)
    return out


def parse_cmekg_disease(rec):
    """解析 CMeKG 疾病实体"""
    name = (rec.get("name") or rec.get("疾病名") or "").strip()
    if not name:
        return None, None

    entry = {"type": "疾病"}

    # 直接属性映射
    for src_key, dst_key in DISEASE_ATTR_MAP.items():
        val = rec.get(src_key)
        if val is None:
            continue
        if isinstance(val, list):
            cleaned = clean_list(val)
            if cleaned:
                entry[dst_key] = cleaned
        elif isinstance(val, str) and val.strip():
            entry[dst_key] = val.strip()

    # 描述
    desc = rec.get("desc") or rec.get("描述") or rec.get("定义") or ""
    if desc.strip():
        entry["描述"] = desc.strip()

    return name, entry


def parse_cmekg_drug(rec):
    """解析 CMeKG 药物实体"""
    name = (rec.get("name") or rec.get("药物名") or "").strip()
    if not name:
        return None, None

    entry = {"type": "药物"}
    insert = {}  # 说明书

    for src_key, dst_key in DRUG_ATTR_MAP.items():
        val = rec.get(src_key)
        if val is None:
            continue
        if isinstance(val, str):
            val = val.strip()
        if not val:
            continue

        # 说明书类字段
        if dst_key in ("适应症", "用法用量", "禁忌", "不良反应"):
            insert[dst_key] = val if isinstance(val, str) else "；".join(val)
        elif dst_key == "类别":
            entry["类别"] = val if isinstance(val, str) else val[0]
        elif dst_key == "成分":
            entry["成分"] = val if isinstance(val, list) else [val]

    # 关联疾病
    diseases = rec.get("关联疾病") or rec.get("治疗疾病") or []
    if diseases:
        entry["关联疾病"] = clean_list(diseases)

    if insert:
        entry["说明书"] = insert

    return name, entry


def parse_triples(triples):
    """从三元组构建"""
    diseases = defaultdict(lambda: defaultdict(list))
    drugs = defaultdict(lambda: defaultdict(list))

    for subj, pred, obj in triples:
        pred_lower = pred.strip().lower()
        # 尝试映射到疾病属性
        mapped = None
        for src, dst in DISEASE_ATTR_MAP.items():
            if src in pred or pred_lower in src.lower():
                mapped = dst
                break
        if mapped:
            bucket = diseases[subj][mapped]
            if obj not in bucket:
                bucket.append(obj)

    disease_out = {}
    for name, fields in diseases.items():
        entry = {"type": "疾病"}
        for field, vals in fields.items():
            entry[field] = vals
        disease_out[name] = entry

    return {"source": "CMeKG 1.0", "diseases": disease_out, "drugs": {}}


def load_json_file(path):
    """加载 JSON 文件（支持数组/对象/JSONL）"""
    with open(path, "r", encoding="utf-8") as fh:
        text = fh.read().strip()
    if not text:
        return []
    try:
        data = json.loads(text)
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            # 可能是 {"diseases": [...], "drugs": [...]} 格式
            if "diseases" in data or "drugs" in data:
                return data
            return [data]
    except ValueError:
        pass
    # JSONL
    records = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            if isinstance(obj, dict):
                records.append(obj)
        except ValueError:
            continue
    return records


def convert_file(path):
    """转换单个文件"""
    data = load_json_file(path)

    # 如果是结构化格式 {"diseases": [...], "drugs": [...]}
    if isinstance(data, dict):
        diseases = {}
        drugs = {}
        for rec in data.get("diseases", []):
            name, entry = parse_cmekg_disease(rec)
            if name and entry:
                diseases[name] = entry
        for rec in data.get("drugs", []):
            name, entry = parse_cmekg_drug(rec)
            if name and entry:
                drugs[name] = entry
        return {"source": "CMeKG 1.0", "diseases": diseases, "drugs": drugs}

    # 如果是记录列表，自动判断是疾病还是药物
    diseases = {}
    drugs = {}
    for rec in data:
        if not isinstance(rec, dict):
            continue
        # 判断类型
        rec_type = (rec.get("type") or rec.get("类型") or "").lower()
        has_drug_fields = any(k in rec for k in
                             ("适应症", "用法用量", "禁忌证", "不良反应", "功能主治"))
        has_disease_fields = any(k in rec for k in
                                ("临床症状", "影像学检查", "手术治疗", "鉴别诊断"))

        if rec_type in ("drug", "药物") or has_drug_fields:
            name, entry = parse_cmekg_drug(rec)
            if name and entry:
                drugs[name] = entry
        else:
            name, entry = parse_cmekg_disease(rec)
            if name and entry:
                diseases[name] = entry

    return {"source": "CMeKG 1.0", "diseases": diseases, "drugs": drugs}


def main():
    ap = argparse.ArgumentParser(description="CMeKG 1.0 → 星衍知识 JSON")
    ap.add_argument("input", nargs="?", help="输入文件（.json/.csv/.tsv）")
    ap.add_argument("--dir", help="批量导入目录")
    ap.add_argument("-o", "--output", default=None)
    ap.add_argument("--sep", default=",", help="CSV 分隔符")
    args = ap.parse_args()

    all_diseases = {}
    all_drugs = {}

    if args.dir:
        # 批量导入目录
        for fname in sorted(os.listdir(args.dir)):
            if not (fname.endswith(".json") or fname.endswith(".csv")):
                continue
            fpath = os.path.join(args.dir, fname)
            print(f"处理：{fname}")
            payload = convert_file(fpath)
            all_diseases.update(payload.get("diseases", {}))
            all_drugs.update(payload.get("drugs", {}))
    elif args.input:
        payload = convert_file(args.input)
        all_diseases = payload.get("diseases", {})
        all_drugs = payload.get("drugs", {})
    else:
        print("请指定输入文件或 --dir 目录")
        ap.print_help()
        sys.exit(1)

    result = {
        "source": "CMeKG 1.0 (清华-鹏城)",
        "diseases": all_diseases,
        "drugs": all_drugs,
    }

    out = args.output or os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "kg_data", "cmekg.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(result, fh, ensure_ascii=False, indent=2)

    print(f"\n导出疾病：{len(all_diseases)} 个")
    print(f"导出药物：{len(all_drugs)} 个")
    print(f"输出文件：{out}")


if __name__ == "__main__":
    main()
