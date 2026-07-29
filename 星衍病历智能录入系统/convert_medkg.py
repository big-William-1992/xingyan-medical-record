#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
QASystemOnMedicalKG medical.json → 星衍统一知识 schema 转换器

数据源：https://github.com/liuhuanyong/QASystemOnMedicalKG
其 data/medical.json 含约 4.4 万种疾病（寻医问药网抽取），免费直接下载，
是 CMeKG 全量数据无法直接获取时的最佳中文替代。

字段映射（medical.json 疾病节点 → 星衍 schema）：
    name             → 疾病名（主键）
    symptom          → 常见症状
    check            → 常见检查
    common_drug      → 常用药物
    recommand_drug   → 常用药物（并入）
    cure_way         → 治疗方式
    desc             → 描述
    cure_department  → 科室 / 系统

用法：
  python convert_medkg.py medical.json -o kg_data/medkg.json
  python convert_medkg.py medical.json --min-fields 1 --limit 5000
"""
import argparse
import json
import os
import sys


def load_records(path):
    """兼容 JSON 数组 与 JSONL（每行一个对象）两种格式"""
    with open(path, "r", encoding="utf-8") as fh:
        text = fh.read().strip()
    if not text:
        return []
    # 优先按整体 JSON 解析（数组或单对象）
    try:
        data = json.loads(text)
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return [data]
    except ValueError:
        pass
    # 回退：JSONL 逐行解析
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


def clean_list(items):
    """去空、去重、保序"""
    out, seen = [], set()
    for it in items or []:
        if isinstance(it, str):
            it = it.strip()
        if it and it not in seen:
            seen.add(it)
            out.append(it)
    return out


# 源数据（寻医问药网）常见噪声：医生署名被误抓进 symptom 字段
DOCTOR_NOISE = {
    "毓卓", "张树立", "李华强", "于飞", "陈嘉诚", "刘业广",
    "李占军", "王竟", "赵乐", "张延丽", "孙广运", "李树生",
}

# 罗马数字（药品名后缀被单独切分产生的噪声，如“硝苯地平缓释片Ⅰ”拆出“Ⅰ”）
_ROMAN = set("ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩⅪⅫⅰⅱⅲⅳⅴⅵⅶⅷⅸⅹⅺⅻIVX")


def _is_noise(token):
    """判定是否为噪声 token：空/单字符/纯数字/罗马数字/医生署名"""
    if not token:
        return True
    if token in DOCTOR_NOISE:
        return True
    if len(token) < 2:
        return True
    if token.isdigit():
        return True
    if all(ch in _ROMAN for ch in token):
        return True
    return False


def clean_symptoms(items):
    """清洗症状列表：去医生署名、纯数字、单字符等噪声"""
    out, seen = [], set()
    for it in items or []:
        if not isinstance(it, str):
            continue
        it = it.strip()
        if it in seen or _is_noise(it):
            continue
        seen.add(it)
        out.append(it)
    return out


def clean_terms(items):
    """清洗药物/检查/治疗方式等列表：去空、去重、去噪声"""
    out, seen = [], set()
    for it in items or []:
        if not isinstance(it, str):
            continue
        it = it.strip()
        if it in seen or _is_noise(it):
            continue
        seen.add(it)
        out.append(it)
    return out


def convert(records, min_fields, limit):
    diseases = {}
    skipped = 0
    for rec in records:
        if not isinstance(rec, dict):
            continue
        name = (rec.get("name") or "").strip()
        if not name:
            skipped += 1
            continue

        symptoms = clean_symptoms(rec.get("symptom"))
        checks = clean_terms(rec.get("check"))
        drugs = clean_terms((rec.get("common_drug") or []) +
                            (rec.get("recommand_drug") or []))
        cure_way = clean_terms(rec.get("cure_way"))
        desc = (rec.get("desc") or "").strip()
        dept = clean_list(rec.get("cure_department"))

        # 过滤信息量过低的疾病
        filled = sum(1 for x in (symptoms, checks, drugs) if x)
        if filled < min_fields:
            skipped += 1
            continue

        entry = {"type": "疾病"}
        if dept:
            entry["系统"] = dept[0]
        if symptoms:
            entry["常见症状"] = symptoms
        if checks:
            entry["常见检查"] = checks
        if drugs:
            entry["常用药物"] = drugs
        if cure_way:
            entry["治疗方式"] = cure_way
        if desc:
            entry["描述"] = desc
        diseases[name] = entry

        if limit and len(diseases) >= limit:
            break

    return {"source": "QASystemOnMedicalKG (liuhuanyong)",
            "diseases": diseases}, skipped


def main():
    ap = argparse.ArgumentParser(
        description="QASystemOnMedicalKG medical.json → 星衍知识 JSON")
    ap.add_argument("input", help="medical.json 路径")
    ap.add_argument("-o", "--output", default=None,
                    help="输出 JSON，默认 kg_data/medkg.json")
    ap.add_argument("--min-fields", type=int, default=1,
                    help="疾病至少需有几类信息(症状/检查/药物)，默认1")
    ap.add_argument("--limit", type=int, default=0,
                    help="最多导出疾病数（0=不限）")
    args = ap.parse_args()

    if not os.path.isfile(args.input):
        print("找不到输入文件：%s" % args.input)
        sys.exit(1)

    records = load_records(args.input)
    print("读取记录：%d 条" % len(records))
    payload, skipped = convert(records, args.min_fields, args.limit)

    out = args.output or os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "kg_data", "medkg.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)

    print("导出疾病：%d 个（过滤 %d 个）" % (len(payload["diseases"]), skipped))
    print("输出文件：%s" % out)


if __name__ == "__main__":
    main()
