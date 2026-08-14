#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
backfill 旧数据到统一纠错记忆库（M2）

来源：
- correction_feedback.jsonl
- correction_rules.json
- postprocess_hotwords.txt
- asr_confusion_pairs.json
- hotwords.txt / user_hotwords.txt / kg_hotwords.txt

输出：
- data/correction_memory.jsonl
- data/correction_memory_backups/<timestamp>.jsonl  # 若已有记忆库则先备份
- stdout 报告
"""
import json
import os
import re
import shutil
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from correction_memory import _default_confidence

BASE_DIR = Path(__file__).resolve().parent.parent
MEMORY_PATH = BASE_DIR / "data" / "correction_memory.jsonl"
BACKUP_DIR = BASE_DIR / "data" / "correction_memory_backups"
SOURCE_FILES = {
    "feedback": BASE_DIR / "correction_feedback.jsonl",
    "rules": BASE_DIR / "correction_rules.json",
    "postprocess": BASE_DIR / "postprocess_hotwords.txt",
    "confusion": BASE_DIR / "asr_confusion_pairs.json",
    "hotwords": BASE_DIR / "hotwords.txt",
    "user_hotwords": BASE_DIR / "user_hotwords.txt",
    "kg_hotwords": BASE_DIR / "kg_hotwords.txt",
}
TIME_FMT = "%Y-%m-%dT%H:%M:%S"


def _utcnow():
    return datetime.utcnow()


def _parse_time(value):
    if not value:
        return _utcnow()
    if isinstance(value, datetime):
        return value
    for fmt in (TIME_FMT, "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(str(value), fmt)
        except Exception:
            continue
    return _utcnow()


def _text(value):
    if value is None:
        return ""
    return str(value).strip()


def _dedupe(items):
    seen = set()
    result = []
    for item in items:
        key = tuple(item)
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result


def _memory_id(prefix="mem"):
    return f"{prefix}_{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}"


def _backup_existing_memory(path):
    if not path.exists():
        return None
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    dest = BACKUP_DIR / f"correction_memory_{stamp}.jsonl"
    shutil.copy2(path, dest)
    return dest


def _write_jsonl(path, records):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


def backfill_feedback(path, doctor_id="unknown", dept="unknown"):
    if not path.exists():
        return []
    records = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            original = _text(rec.get("original") or rec.get("原文"))
            corrected = _text(rec.get("corrected") or rec.get("修正"))
            status = _text(rec.get("status", "pending"))
            if status == "pending" and not original and not corrected:
                continue
            source = _text(rec.get("source", "correction_feedback"))
            source = source or "correction_feedback"
            confidence = _default_confidence({"status": status})
            if source == "user_manual":
                confidence = 0.9
            if status == "accepted":
                confidence = max(confidence, 0.8)
            elif status == "rejected":
                confidence = min(confidence, 0.4)
            record = {
                "memory_id": _memory_id("fb"),
                "doctor_id": doctor_id,
                "dept": dept,
                "field": "unknown",
                "source": source,
                "status": status or "pending",
                "original": original,
                "corrected": corrected,
                "category": _text(rec.get("category") or rec.get("分类")),
                "level": _text(rec.get("level") or rec.get("级别")),
                "type": _text(rec.get("type") or rec.get("type_name")),
                "similarity": rec.get("相似度"),
                "confidence": confidence,
                "freq": 1,
                "accepted_count": 1 if status == "accepted" else 0,
                "rejected_count": 1 if status == "rejected" else 0,
                "last_used_at": _format_time(rec.get("timestamp") or rec.get("time")),
                "created_at": _format_time(rec.get("timestamp") or rec.get("time")),
                "updated_at": _format_time(_utcnow()),
                "meta": {
                    "source_file": str(path.name),
                    "source_type": "correction_feedback_jsonl",
                },
            }
            records.append(record)
    return records


def _format_time(value):
    if not value:
        return _utcnow().strftime(TIME_FMT)
    if isinstance(value, datetime):
        return value.strftime(TIME_FMT)
    try:
        return _parse_time(value).strftime(TIME_FMT)
    except Exception:
        return _utcnow().strftime(TIME_FMT)


def backfill_rules(path):
    if not path.exists():
        return []
    records = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return []
    if not isinstance(data, dict):
        return []
    for category, rules in data.items():
        if not isinstance(rules, list):
            continue
        for rule in rules:
            original = _text(rule.get("错误") or rule.get("错误模式"))
            corrected = _text(rule.get("正确") or rule.get("描述"))
            if not original or not corrected:
                continue
            if category == "错别字":
                records.append({
                    "memory_id": _memory_id("rule"),
                    "doctor_id": "system",
                    "dept": "通用",
                    "field": "通用",
                    "source": "correction_rule",
                    "status": "accepted",
                    "original": original,
                    "corrected": corrected,
                    "category": "错别字",
                    "level": "自动",
                    "type": _text(rule.get("规则")),
                    "confidence": 0.8,
                    "freq": 3,
                    "accepted_count": 3,
                    "rejected_count": 0,
                    "last_used_at": _format_time(_utcnow()),
                    "created_at": _format_time(_utcnow()),
                    "updated_at": _format_time(_utcnow()),
                    "meta": {"source_file": str(path.name), "rule_category": category},
                })
            else:
                # 逻辑规则只记规则摘要，不生成直接替换对
                records.append({
                    "memory_id": _memory_id("rule"),
                    "doctor_id": "system",
                    "dept": "通用",
                    "field": "通用",
                    "source": "correction_rule",
                "original": original,
                "corrected": corrected,
                "category": category,
                "level": "建议",
                "type": "逻辑规则",
                "status": "accepted",
                "confidence": 0.6,
                    "freq": 1,
                    "accepted_count": 1,
                    "rejected_count": 0,
                    "last_used_at": _format_time(_utcnow()),
                    "created_at": _format_time(_utcnow()),
                    "updated_at": _format_time(_utcnow()),
                    "meta": {"source_file": str(path.name), "rule_category": category},
                })
    return records


def backfill_postprocess(path):
    if not path.exists():
        return []
    records = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=>" not in line:
                continue
            original, corrected = [part.strip() for part in line.split("=>", 1)]
            if not original or not corrected or original == corrected:
                continue
            records.append({
                "memory_id": _memory_id("post"),
                "doctor_id": "system",
                "dept": "通用",
                "field": "通用",
                "source": "postprocess_hotword",
                "status": "accepted",
                "original": original,
                "corrected": corrected,
                "category": "术语替换",
                "level": "自动",
                "type": "postprocess_hotword",
                "confidence": 0.78,
                "freq": 2,
                "accepted_count": 2,
                "rejected_count": 0,
                "last_used_at": _format_time(_utcnow()),
                "created_at": _format_time(_utcnow()),
                "updated_at": _format_time(_utcnow()),
                "meta": {"source_file": str(path.name)},
            })
    return records


def backfill_confusion(path):
    if not path.exists():
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return []
    if not isinstance(data, dict):
        return []
    records = []
    for original, corrected in data.items():
        original = _text(original)
        corrected = _text(corrected)
        if not original or not corrected or original == corrected:
            continue
        confidence = 0.8
        status = "accepted"
        records.append({
            "memory_id": _memory_id("conf"),
            "doctor_id": "system",
            "dept": "通用",
            "field": "通用",
            "source": "confusion_pair",
            "status": status,
            "original": original,
            "corrected": corrected,
            "category": "术语替换",
            "level": "自动",
            "type": "confusion_pair",
            "confidence": confidence,
            "freq": 3,
            "accepted_count": 3,
            "rejected_count": 0,
            "last_used_at": _format_time(_utcnow()),
            "created_at": _format_time(_utcnow()),
            "updated_at": _format_time(_utcnow()),
            "meta": {"source_file": str(path.name)},
        })
    return records


def backfill_term_pool(path, source_name, dept="通用", doctor_id="system", category="术语候选", freq=1):
    if not path.exists():
        return []
    records = []
    seen = set()
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            term = _text(line)
            if not term:
                continue
            if term.startswith("#") or term.startswith("["):
                continue
            if term in seen:
                continue
            seen.add(term)
            records.append({
                "memory_id": _memory_id(source_name[:4]),
                "doctor_id": doctor_id,
                "dept": dept,
                "field": "通用",
                "source": source_name,
                "status": "accepted",
                "original": term,
                "corrected": term,
                "category": category,
                "level": "自动",
                "type": "term_pool",
                "confidence": 0.4,
                "freq": freq,
                "accepted_count": 0,
                "rejected_count": 0,
                "last_used_at": _format_time(_utcnow()),
                "created_at": _format_time(_utcnow()),
                "updated_at": _format_time(_utcnow()),
                "meta": {"source_file": str(path.name)},
            })
    return records


def analyze(records):
    stats = Counter()
    dept_stats = defaultdict(Counter)
    source_stats = defaultdict(Counter)
    changed_pairs = 0
    for record in records:
        stats[record.get("status", "pending")] += 1
        stats["total"] += 1
        dept_stats[record.get("dept", "unknown")]["total"] += 1
        source_stats[record.get("source", "unknown")]["total"] += 1
        if record.get("original") != record.get("corrected"):
            changed_pairs += 1
    top_terms = Counter()
    for record in records:
        if record.get("status") != "accepted":
            continue
        term = _text(record.get("corrected") or record.get("original"))
        if term:
            top_terms[term] += 1
    return {
        "stats": dict(stats),
        "changed_pairs": changed_pairs,
        "top_terms": top_terms.most_common(20),
        "dept_stats": {k: dict(v) for k, v in dept_stats.items()},
        "source_stats": {k: dict(v) for k, v in source_stats.items()},
    }


def main():
    print("=" * 60)
    print("  backfill memory -> correction_memory.jsonl")
    print("=" * 60)
    MEMORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    BACKUP_DEST = _backup_existing_memory(MEMORY_PATH)
    if BACKUP_DEST:
        print(f"\n[备份] 旧记忆库已备份: {BACKUP_DEST}")

    records = []
    records.extend(backfill_feedback(SOURCE_FILES["feedback"]))
    records.extend(backfill_rules(SOURCE_FILES["rules"]))
    records.extend(backfill_postprocess(SOURCE_FILES["postprocess"]))
    records.extend(backfill_confusion(SOURCE_FILES["confusion"]))
    records.extend(backfill_term_pool(SOURCE_FILES["hotwords"], "hotword_pool", dept="通用"))
    records.extend(backfill_term_pool(SOURCE_FILES["user_hotwords"], "user_hotword_pool", dept="通用"))
    records.extend(backfill_term_pool(SOURCE_FILES["kg_hotwords"], "kg_hotword_pool", dept="通用", freq=2))

    before = []
    if MEMORY_PATH.exists():
        with open(MEMORY_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        before.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
    merged = before + records
    _write_jsonl(MEMORY_PATH, merged)

    report = analyze(merged)
    print("\n[统计]")
    for key in ("total", "accepted", "rejected", "pending", "deprecated"):
        print(f"  {key}: {report['stats'].get(key, 0)}")
    print(f"  changed_pairs: {report['changed_pairs']}")
    print(f"\n[Top terms]")
    for term, count in report["top_terms"]:
        print(f"  {term}: {count}")
    print(f"\n[dept_stats]")
    for dept, counts in sorted(report["dept_stats"].items())[:10]:
        print(f"  {dept}: {counts}")
    print(f"\n[source_stats]")
    for source, counts in sorted(report["source_stats"].items())[:10]:
        print(f"  {source}: {counts}")
    print(f"\n✅ 记忆库已写入: {MEMORY_PATH}")
    print(f"   总条数: {len(merged)} (本次新增 {len(records)})")


if __name__ == "__main__":
    main()
