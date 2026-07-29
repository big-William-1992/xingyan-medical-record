#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OpenKG / CMeKG 原始数据 → 星衍统一知识 schema 转换器

OpenKG 上的医学知识图谱（如 CMeKG、面向家庭常见疾病的知识图谱）通常以
「三元组」形式发布：subject, predicate, object。本脚本把这类三元组聚合成
knowledge_graph.py 可直接加载的 JSON（放入 kg_data/ 目录即自动生效）。

支持输入：
  1. CSV/TSV 三元组文件：每行  头实体<sep>关系<sep>尾实体
  2. JSON 三元组数组：[{"subject":..,"predicate":..,"object":..}, ...]

用法：
  python convert_openkg.py 原始三元组.csv -o kg_data/cmekg.json
  python convert_openkg.py 原始三元组.csv --sep '\\t'         # TSV
  python convert_openkg.py triples.json -o kg_data/openkg.json

关系映射（可按数据集在 PREDICATE_MAP 里增减）：把原始 predicate 归一到
  常见症状 / 常见检查 / 常用药物 / 别名 / 关联疾病
未识别的 predicate 会被统计并打印，便于补充映射。
"""
import argparse
import csv
import json
import os
import sys
from collections import defaultdict

# 原始关系词 → 统一字段。key 用小写去空格后匹配（含子串匹配兜底）。
PREDICATE_MAP = {
    "症状": "常见症状", "临床表现": "常见症状", "symptom": "常见症状",
    "hassymptom": "常见症状", "并发症": "常见症状",
    "检查": "常见检查", "诊断检查": "常见检查", "辅助检查": "常见检查",
    "检查项目": "常见检查", "check": "常见检查", "test": "常见检查",
    "药物": "常用药物", "用药": "常用药物", "治疗药物": "常用药物",
    "推荐药物": "常用药物", "drug": "常用药物", "treatment": "常用药物",
    "别名": "别名", "又名": "别名", "俗称": "别名", "alias": "别名",
}


def map_predicate(pred):
    """把原始关系词归一到统一字段名，未命中返回 None"""
    key = pred.strip().lower().replace(" ", "").replace("_", "")
    if key in PREDICATE_MAP:
        return PREDICATE_MAP[key]
    for raw, field in PREDICATE_MAP.items():
        if raw in key:
            return field
    return None


def iter_triples(path, sep):
    """从 CSV/TSV 或 JSON 逐条产出 (subject, predicate, object)"""
    if path.lower().endswith(".json"):
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        for row in data:
            s = row.get("subject") or row.get("head") or row.get("h")
            p = row.get("predicate") or row.get("relation") or row.get("r")
            o = row.get("object") or row.get("tail") or row.get("t")
            if s and p and o:
                yield str(s).strip(), str(p).strip(), str(o).strip()
        return
    with open(path, "r", encoding="utf-8") as fh:
        reader = csv.reader(fh, delimiter=sep)
        for row in reader:
            if len(row) < 3:
                continue
            yield row[0].strip(), row[1].strip(), row[2].strip()


def convert(path, sep, source):
    diseases = defaultdict(lambda: defaultdict(list))
    unmapped = defaultdict(int)
    total = 0
    for subj, pred, obj in iter_triples(path, sep):
        total += 1
        field = map_predicate(pred)
        if field is None:
            unmapped[pred] += 1
            continue
        bucket = diseases[subj][field]
        if obj not in bucket:
            bucket.append(obj)

    payload = {"source": source, "diseases": {
        name: dict(fields) for name, fields in diseases.items()
    }}
    return payload, total, unmapped


def main():
    ap = argparse.ArgumentParser(description="OpenKG/CMeKG 三元组 → 星衍知识 JSON")
    ap.add_argument("input", help="原始三元组文件（.csv/.tsv/.json）")
    ap.add_argument("-o", "--output", default=None,
                    help="输出 JSON 路径，默认 kg_data/<输入名>.json")
    ap.add_argument("--sep", default=",", help="CSV 分隔符，TSV 用 '\\t'")
    ap.add_argument("--source", default=None, help="数据来源标注")
    args = ap.parse_args()

    if not os.path.isfile(args.input):
        print("找不到输入文件：%s" % args.input)
        sys.exit(1)

    sep = "\t" if args.sep in ("\\t", "\t") else args.sep
    source = args.source or os.path.basename(args.input)
    payload, total, unmapped = convert(args.input, sep, source)

    out = args.output
    if out is None:
        base = os.path.splitext(os.path.basename(args.input))[0]
        out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "kg_data", base + ".json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)

    print("读取三元组：%d 条" % total)
    print("生成疾病实体：%d 个" % len(payload["diseases"]))
    print("输出文件：%s" % out)
    if unmapped:
        print("\n未识别的关系（可在 PREDICATE_MAP 中补充映射）：")
        for pred, cnt in sorted(unmapped.items(), key=lambda x: -x[1])[:20]:
            print("  %s  ×%d" % (pred, cnt))


if __name__ == "__main__":
    main()
