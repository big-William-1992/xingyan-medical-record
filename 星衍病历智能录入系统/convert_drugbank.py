#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DrugBank XML → 星衍统一知识 schema 转换器

DrugBank 完整库以单个大 XML 发布（full database.xml，约 1.4GB，需在
https://go.drugbank.com 申请免费学术许可后下载）。本脚本用流式解析
（iterparse，低内存）抽取每个药物的说明书字段，输出为 knowledge_graph.py
可直接加载的 JSON（放入 kg_data/ 即自动生效）。

字段映射（DrugBank → 说明书）：
    适应症   ← <indication>
    用法用量 ← <dosages>（剂型/给药途径/规格拼接）
    不良反应 ← <toxicity>
    作用机制 ← <mechanism-of-action>
    类别     ← <categories>
    别名     ← <synonyms> + <international-brands>

DrugBank 为英文，中文病历需中英映射才能对上药名。内置 ZH_MAP 覆盖常用药；
可用 --zh-map 传入 CSV（英文名,中文名）扩充。命中映射的药以中文名为主键、
英文名转入别名；未命中的默认跳过（--keep-english 保留英文名药物）。

用法：
  python convert_drugbank.py "full database.xml" -o kg_data/drugbank.json
  python convert_drugbank.py db.xml --zh-map mymap.csv --keep-english
"""
import argparse
import csv
import json
import os
import sys
import xml.etree.ElementTree as ET

# 常用药英文名 → 中文名（覆盖内置图谱中的高频药物）
ZH_MAP = {
    "amoxicillin": "阿莫西林", "ceftriaxone": "头孢曲松",
    "levofloxacin": "左氧氟沙星", "azithromycin": "阿奇霉素",
    "cefuroxime": "头孢呋辛", "metronidazole": "甲硝唑",
    "aspirin": "阿司匹林", "clopidogrel": "氯吡格雷",
    "amlodipine": "氨氯地平", "nifedipine": "硝苯地平",
    "valsartan": "缬沙坦", "atorvastatin": "阿托伐他汀",
    "metoprolol": "美托洛尔", "amiodarone": "胺碘酮",
    "warfarin": "华法林", "furosemide": "呋塞米",
    "spironolactone": "螺内酯", "metformin": "二甲双胍",
    "glimepiride": "格列美脲", "acarbose": "阿卡波糖",
    "insulin": "胰岛素", "omeprazole": "奥美拉唑",
    "ibuprofen": "布洛芬", "diazepam": "地西泮",
    "valproic acid": "丙戊酸钠", "colchicine": "秋水仙碱",
    "allopurinol": "别嘌醇", "isoniazid": "异烟肼",
    "rifampicin": "利福平", "rifampin": "利福平",
    "salbutamol": "沙丁胺醇", "albuterol": "沙丁胺醇",
    "budesonide": "布地奈德",
}


def localname(tag):
    """去掉 XML 命名空间前缀"""
    return tag.split("}")[-1] if "}" in tag else tag


def child_text(elem, name):
    """返回第一个 localname 匹配的直接子元素文本"""
    for c in list(elem):
        if localname(c.tag) == name:
            return (c.text or "").strip()
    return ""


def child_elem(elem, name):
    for c in list(elem):
        if localname(c.tag) == name:
            return c
    return None


def collect_texts(elem, container, item, field=None):
    """从 <container><item><field> 收集文本列表"""
    box = child_elem(elem, container)
    if box is None:
        return []
    out = []
    for it in list(box):
        if localname(it.tag) != item:
            continue
        val = child_text(it, field) if field else (it.text or "").strip()
        if val:
            out.append(val)
    return out


def format_dosages(elem):
    """把结构化 dosages 拼成一句用法用量"""
    box = child_elem(elem, "dosages")
    if box is None:
        return ""
    parts = []
    for d in list(box):
        if localname(d.tag) != "dosage":
            continue
        form = child_text(d, "form")
        route = child_text(d, "route")
        strength = child_text(d, "strength")
        seg = "；".join(x for x in (form, route, strength) if x)
        if seg:
            parts.append(seg)
    return " / ".join(parts)


def load_zh_map(path):
    m = dict(ZH_MAP)
    if not path:
        return m
    with open(path, "r", encoding="utf-8") as fh:
        for row in csv.reader(fh):
            if len(row) >= 2 and row[0].strip():
                m[row[0].strip().lower()] = row[1].strip()
    return m


def convert(path, zh_map, keep_english, limit):
    drugs = {}
    processed = 0
    context = ET.iterparse(path, events=("end",))
    for _event, elem in context:
        if localname(elem.tag) != "drug":
            continue
        # 仅处理顶层药物（含 primary drugbank-id）
        has_id = any(localname(c.tag) == "drugbank-id" for c in list(elem))
        name_en = child_text(elem, "name")
        if not has_id or not name_en:
            elem.clear()
            continue

        key_en = name_en.strip().lower()
        zh = zh_map.get(key_en)
        if zh is None and not keep_english:
            elem.clear()
            continue
        key = zh or name_en

        aliases = [name_en] if zh else []
        aliases += collect_texts(elem, "synonyms", "synonym")
        aliases += collect_texts(elem, "international-brands",
                                 "international-brand", "name")
        categories = collect_texts(elem, "categories", "category", "category")

        insert = {}
        indication = child_text(elem, "indication")
        dosage = format_dosages(elem)
        toxicity = child_text(elem, "toxicity")
        moa = child_text(elem, "mechanism-of-action")
        if indication:
            insert["适应症"] = indication
        if dosage:
            insert["用法用量"] = dosage
        if toxicity:
            insert["不良反应"] = toxicity
        if moa:
            insert["作用机制"] = moa

        entry = {"type": "药物"}
        if categories:
            entry["类别"] = categories[0]
        # 别名去重保序
        seen, alias_out = set(), []
        for a in aliases:
            if a and a not in seen:
                seen.add(a)
                alias_out.append(a)
        if alias_out:
            entry["别名"] = alias_out
        if insert:
            entry["说明书"] = insert
        drugs[key] = entry

        processed += 1
        elem.clear()
        if limit and processed >= limit:
            break

    return {"source": "DrugBank", "drugs": drugs}, processed


def main():
    ap = argparse.ArgumentParser(description="DrugBank XML → 星衍知识 JSON")
    ap.add_argument("input", help="DrugBank full database.xml 路径")
    ap.add_argument("-o", "--output", default=None,
                    help="输出 JSON，默认 kg_data/drugbank.json")
    ap.add_argument("--zh-map", default=None,
                    help="补充中英映射 CSV（英文名,中文名）")
    ap.add_argument("--keep-english", action="store_true",
                    help="保留未命中中文映射的药物（以英文名为键）")
    ap.add_argument("--limit", type=int, default=0,
                    help="最多导出药物数（0=不限）")
    args = ap.parse_args()

    if not os.path.isfile(args.input):
        print("找不到输入文件：%s" % args.input)
        sys.exit(1)

    zh_map = load_zh_map(args.zh_map)
    payload, processed = convert(args.input, zh_map, args.keep_english,
                                 args.limit)

    out = args.output or os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "kg_data", "drugbank.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)

    print("导出药物：%d 个" % len(payload["drugs"]))
    print("输出文件：%s" % out)
    if not payload["drugs"]:
        print("提示：无药物命中中文映射，可加 --keep-english 或用 --zh-map 扩充映射")


if __name__ == "__main__":
    main()
