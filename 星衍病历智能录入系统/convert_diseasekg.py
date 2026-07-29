#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DiseaseKG 饮食宜忌 + 全实体转换器

数据源：https://github.com/honeyandme/RQGQnASystem（基于 OpenKG DiseaseKG）
原始数据含 8 类实体（Disease/Drug/Food/Check/Department/Producer/Symptom/Cure）
和 11 类关系，其中 do_eat / no_eat / recommand_eat 为饮食宜忌，
是现有 medkg.json 未覆盖的独有数据。

支持两种输入格式：
  A. 实体+关系 CSV 文件组（build_kg 产出）：
     python convert_diseasekg.py --entities entities/ --relations relations/
  B. 单文件三元组 CSV/TSV/JSON：
     python convert_diseasekg.py triples.csv -o kg_data/diseasekg.json

输出统一 schema（放入 kg_data/ 即自动生效）：
  {
    "source": "DiseaseKG (OpenKG)",
    "diseases": {"疾病名": {"宜吃食物":[...], "忌吃食物":[...], "推荐食谱":[...], ...}},
    "foods":    {"食物名": {"类别":..., "关联疾病":[...]}}
  }

用法：
  # 方式A：从实体/关系目录
  python convert_diseasekg.py --entities data/entities --relations data/relations

  # 方式B：从三元组文件
  python convert_diseasekg.py triples.csv --sep ',' -o kg_data/diseasekg.json
"""
import argparse
import csv
import json
import os
import sys
from collections import defaultdict


# ─── 关系映射 ───────────────────────────────────────────────
RELATION_MAP = {
    # 饮食宜忌（核心价值）
    "do_eat": "宜吃食物",
    "recommand_eat": "推荐食谱",
    "no_eat": "忌吃食物",
    # 已有字段（补充）
    "has_symptom": "常见症状",
    "acompany_with": "并发症",
    "belongs_to": "科室",
    "common_drug": "常用药物",
    "recommand_drug": "推荐药物",
    "need_check": "常见检查",
    "cure_way": "治疗方式",
    "drugs_of": "常用药物",
}


def clean(val):
    """去空去重保序"""
    if isinstance(val, str):
        val = val.strip()
    return val if val else None


def load_triples_from_file(path, sep):
    """从 CSV/TSV/JSON 加载三元组"""
    triples = []
    if path.lower().endswith(".json"):
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        for row in data:
            s = row.get("subject") or row.get("head") or row.get("h", "")
            p = row.get("predicate") or row.get("relation") or row.get("r", "")
            o = row.get("object") or row.get("tail") or row.get("t", "")
            if s and p and o:
                triples.append((str(s).strip(), str(p).strip(), str(o).strip()))
    else:
        with open(path, "r", encoding="utf-8") as fh:
            reader = csv.reader(fh, delimiter=sep)
            for row in reader:
                if len(row) >= 3:
                    triples.append((row[0].strip(), row[1].strip(), row[2].strip()))
    return triples


def load_triples_from_dirs(entities_dir, relations_dir):
    """从实体/关系目录加载（DiseaseKG build_kg 产出格式）"""
    triples = []
    # 关系文件：每个文件名为关系类型，内容为 头实体\t尾实体
    if os.path.isdir(relations_dir):
        for fname in os.listdir(relations_dir):
            rel_name = os.path.splitext(fname)[0]
            fpath = os.path.join(relations_dir, fname)
            with open(fpath, "r", encoding="utf-8") as fh:
                for line in fh:
                    parts = line.strip().split("\t")
                    if len(parts) >= 2:
                        triples.append((parts[0].strip(), rel_name, parts[1].strip()))
    return triples


def convert(triples):
    """将三元组转换为统一 schema"""
    diseases = defaultdict(lambda: defaultdict(list))
    foods = defaultdict(lambda: defaultdict(list))
    unmapped = defaultdict(int)
    total = 0

    for subj, pred, obj in triples:
        total += 1
        field = RELATION_MAP.get(pred)
        if field is None:
            unmapped[pred] += 1
            continue

        # 饮食类关系 → 归入疾病
        if pred in ("do_eat", "no_eat", "recommand_eat"):
            bucket = diseases[subj][field]
            if obj not in bucket:
                bucket.append(obj)
            # 同时记录食物的关联疾病
            foods[obj]["关联疾病"].append(subj)
        else:
            bucket = diseases[subj][field]
            if obj not in bucket:
                bucket.append(obj)

    # 整理输出
    disease_out = {}
    for name, fields in diseases.items():
        entry = {"type": "疾病"}
        for field, vals in fields.items():
            entry[field] = vals
        disease_out[name] = entry

    food_out = {}
    for name, fields in foods.items():
        entry = {"type": "食物"}
        for field, vals in fields.items():
            entry[field] = list(set(vals))  # 去重
        food_out[name] = entry

    payload = {
        "source": "DiseaseKG (OpenKG)",
        "diseases": disease_out,
        "foods": food_out,
    }
    return payload, total, unmapped


def main():
    ap = argparse.ArgumentParser(description="DiseaseKG 饮食宜忌 → 星衍知识 JSON")
    ap.add_argument("input", nargs="?", help="三元组文件（.csv/.tsv/.json）")
    ap.add_argument("--entities", help="实体目录（方式A）")
    ap.add_argument("--relations", help="关系目录（方式A）")
    ap.add_argument("-o", "--output", default=None)
    ap.add_argument("--sep", default=",", help="CSV 分隔符")
    args = ap.parse_args()

    # 加载三元组
    if args.relations:
        triples = load_triples_from_dirs(
            args.entities or "", args.relations)
    elif args.input:
        sep = "\t" if args.sep in ("\\t", "\t") else args.sep
        triples = load_triples_from_file(args.input, sep)
    else:
        print("请指定输入文件或 --relations 目录")
        ap.print_help()
        sys.exit(1)

    print(f"读取三元组：{len(triples)} 条")
    payload, total, unmapped = convert(triples)

    out = args.output or os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "kg_data", "diseasekg.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)

    n_dis = len(payload["diseases"])
    n_food = len(payload["foods"])
    print(f"导出疾病：{n_dis} 个（含饮食宜忌）")
    print(f"导出食物：{n_food} 个")
    print(f"输出文件：{out}")
    if unmapped:
        print("\n未映射关系（可在 RELATION_MAP 补充）：")
        for pred, cnt in sorted(unmapped.items(), key=lambda x: -x[1])[:15]:
            print(f"  {pred}  ×{cnt}")


if __name__ == "__main__":
    main()
