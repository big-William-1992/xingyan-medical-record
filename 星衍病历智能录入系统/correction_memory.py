#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统一纠错记忆库（M2）

职责：
- 统一存储纠错/反馈/热词候选/混淆对候选
- 提供按 doctor/dept/field/source/status/time 的查询能力
- 提供 Top-K、recent pairs、stats、导出视图
- 提供 backfill 接口，兼容旧 feedback/rules/confusion/hotword 文件

存储：
- 主数据：data/correction_memory.jsonl
- 索引：data/correction_memory_index.json
- 备份：data/correction_memory_backups/
"""
import copy
import json
import os
import shutil
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path

BASE_DIR = Path(__file__).parent
DEFAULT_MEMORY_PATH = BASE_DIR / "data" / "correction_memory.jsonl"
DEFAULT_INDEX_PATH = BASE_DIR / "data" / "correction_memory_index.json"
DEFAULT_BACKUP_DIR = BASE_DIR / "data" / "correction_memory_backups"
DEFAULT_TIME_FMT = "%Y-%m-%dT%H:%M:%S"
DEFAULT_DOCTOR_ID = "unknown"
DEFAULT_DEPT = "unknown"
DEFAULT_FIELD = "unknown"


def _utcnow():
    return datetime.utcnow()


def _format_dt(value):
    if isinstance(value, datetime):
        return value.strftime(DEFAULT_TIME_FMT)
    return str(value or "")


def _parse_dt(value):
    if not value:
        return _utcnow()
    if isinstance(value, datetime):
        return value
    for fmt in (DEFAULT_TIME_FMT, "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(str(value), fmt)
        except Exception:
            continue
    return _utcnow()


def _normalize_text(value):
    if value is None:
        return ""
    return str(value).strip()


def _dedupe_preserve(items):
    seen = set()
    result = []
    for item in items:
        key = tuple(item)
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result


class CorrectionMemory:
    def __init__(self, memory_path=None, index_path=None, backup_dir=None):
        self.memory_path = Path(memory_path or DEFAULT_MEMORY_PATH)
        self.index_path = Path(index_path or DEFAULT_INDEX_PATH)
        self.backup_dir = Path(backup_dir or DEFAULT_BACKUP_DIR)
        self.memory_path.parent.mkdir(parents=True, exist_ok=True)
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self._memories = []
        self._index = self._load_index()
        self._load_memories()

    # ==================== 持久化 ====================

    def _load_memories(self):
        self._memories = []
        if not self.memory_path.exists():
            return
        with open(self.memory_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    self._memories.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

    def _append_memory(self, record):
        record = copy.deepcopy(record)
        record.setdefault("memory_id", self._next_id())
        record.setdefault("created_at", _format_dt(_utcnow()))
        record.setdefault("updated_at", record["created_at"])
        with open(self.memory_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        self._memories.append(record)
        self._update_index_after_write()
        return record

    def _overwrite_memories(self, records):
        with open(self.memory_path, "w", encoding="utf-8") as f:
            for record in records:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        self._memories = list(records)
        self._update_index_after_write()

    def backup(self):
        if not self.memory_path.exists():
            return None
        stamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        dest = self.backup_dir / f"correction_memory_{stamp}.jsonl"
        shutil.copy2(self.memory_path, dest)
        return dest

    # ==================== 索引 ====================

    def _load_index(self):
        if not self.index_path.exists():
            return self._empty_index()
        try:
            with open(self.index_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                return self._empty_index()
            return data
        except Exception:
            return self._empty_index()

    def _empty_index(self):
        return {
            "stats": {"total": 0, "accepted": 0, "rejected": 0, "pending": 0, "deprecated": 0},
            "top_terms": {},
            "recent_pairs": [],
            "last_updated_at": _format_dt(_utcnow()),
        }

    def _update_index_after_write(self):
        stats = Counter()
        top_terms = defaultdict(int)
        recent_pairs = []
        for record in self._memories:
            stats[record.get("status", "pending")] += 1
            stats["total"] += 1
            term = _normalize_text(record.get("corrected") or record.get("original"))
            if term:
                top_terms[term] += 1
            original = _normalize_text(record.get("original"))
            corrected = _normalize_text(record.get("corrected"))
            if original and corrected and original != corrected:
                recent_pairs.append([original, corrected])
        index = {
            "stats": {
                "total": stats["total"],
                "accepted": stats["accepted"],
                "rejected": stats["rejected"],
                "pending": stats["pending"],
                "deprecated": stats["deprecated"],
            },
            "top_terms": self._top_terms(Counter(top_terms), limit=200),
            "recent_pairs": _dedupe_preserve(recent_pairs)[-200:],
            "last_updated_at": _format_dt(_utcnow()),
        }
        self._index = index
        self._write_index()

    def _write_index(self):
        tmp = self.index_path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self._index, f, ensure_ascii=False, indent=2)
            f.write("\n")
        tmp.replace(self.index_path)

    def _next_id(self):
        base = int(datetime.utcnow().strftime("%Y%m%d%H%M%S%f"))
        return f"mem_{base}"

    # ==================== 写入接口 ====================

    def add_memory(self, record, doctor_id=None, dept=None, field=None):
        original = _normalize_text(record.get("original"))
        corrected = _normalize_text(record.get("corrected"))
        if not original and not corrected:
            return None
        prepared = {
            "doctor_id": _normalize_text(record.get("doctor_id") or doctor_id or DEFAULT_DOCTOR_ID),
            "dept": _normalize_text(record.get("dept") or dept or DEFAULT_DEPT),
            "field": _normalize_text(record.get("field") or field or DEFAULT_FIELD),
            "source": _normalize_text(record.get("source") or "unknown"),
            "status": _normalize_text(record.get("status") or "pending"),
            "category": _normalize_text(record.get("category") or record.get("分类", "")),
            "level": _normalize_text(record.get("level") or record.get("级别", "")),
            "original": original,
            "corrected": corrected,
            "confidence": _default_confidence(record),
            "freq": int(record.get("freq", 0) or 0),
            "accepted_count": int(record.get("accepted_count", 0) or 0),
            "rejected_count": int(record.get("rejected_count", 0) or 0),
            "last_used_at": _format_dt(record.get("last_used_at")),
            "meta": copy.deepcopy(record.get("meta") or {}),
        }
        prepared["meta"].setdefault("type", _normalize_text(record.get("type") or record.get("type_name", "")))
        return self._append_memory(prepared)

    def add_memories(self, records, doctor_id=None, dept=None, field=None):
        added = []
        for record in records or []:
            item = self.add_memory(record, doctor_id=doctor_id, dept=dept, field=field)
            if item:
                added.append(item)
        return added

    def accept_memory(self, memory_id, doctor_id=None):
        return self._update_status(memory_id, "accepted", doctor_id=doctor_id, accepted_delta=1)

    def reject_memory(self, memory_id, doctor_id=None):
        return self._update_status(memory_id, "rejected", doctor_id=doctor_id, rejected_delta=1)

    def touch_memory(self, memory_id):
        updated = False
        now = _format_dt(_utcnow())
        for record in self._memories:
            if record.get("memory_id") == memory_id:
                record["last_used_at"] = now
                record["updated_at"] = now
                record["freq"] = int(record.get("freq", 0) or 0) + 1
                updated = True
                break
        if updated:
            self._overwrite_memories(self._memories)
        return updated

    # ==================== 查询接口 ====================

    def get_memories(self, doctor_id=None, dept=None, field=None, source=None,
                     status=None, category=None, min_confidence=0.0, since=None, memory_id=None, limit=500):
        results = []
        since_dt = _parse_dt(since) if since is not None else None
        for record in self._memories:
            if doctor_id and record.get("doctor_id") != doctor_id:
                continue
            if dept and record.get("dept") != dept:
                continue
            if memory_id and record.get("memory_id") != memory_id:
                continue
            if field and record.get("field") != field:
                continue
            if source and record.get("source") != source:
                continue
            if status and record.get("status") != status:
                continue
            if category and record.get("category") != category:
                continue
            if record.get("confidence", 0.0) < min_confidence:
                continue
            created_at = _parse_dt(record.get("created_at"))
            if since_dt and created_at <= since_dt:
                continue
            results.append(record)
        results.sort(key=lambda r: _parse_dt(r.get("updated_at")), reverse=True)
        return results[: limit]

    def get_stats(self):
        stats = copy.deepcopy(self._index.get("stats", {}))
        stats.setdefault("total", len(self._memories))
        stats["memory_path"] = str(self.memory_path)
        stats["index_path"] = str(self.index_path)
        stats["backup_dir"] = str(self.backup_dir)
        stats["last_updated_at"] = self._index.get("last_updated_at")
        return stats

    def get_top_terms(self, dept=None, doctor_id=None, limit=80):
        counter = Counter()
        for record in self._memories:
            if record.get("status") != "accepted":
                continue
            if dept and record.get("dept") != dept:
                continue
            if doctor_id and record.get("doctor_id") != doctor_id:
                continue
            term = _normalize_text(record.get("corrected") or record.get("original"))
            if not term:
                continue
            score = 1.0 + float(record.get("confidence", 0.0) or 0.0)
            score += min(record.get("accepted_count", 0), 10) * 0.2
            score -= min(record.get("rejected_count", 0), 10) * 0.4
            counter[term] += score
        return [[term, round(score, 3)] for term, score in counter.most_common(limit)]

    def get_recent_pairs(self, limit=80):
        pairs = []
        for record in self._memories:
            original = _normalize_text(record.get("original"))
            corrected = _normalize_text(record.get("corrected"))
            if original and corrected and original != corrected:
                pairs.append((original, corrected))
        deduped = _dedupe_preserve(pairs)
        return deduped[-limit:]

    def get_confusion_pairs(self, min_confidence=0.6, min_count=1):
        pairs = {}
        counter = Counter()
        for record in self._memories:
            if record.get("status") != "accepted":
                continue
            if record.get("confidence", 0.0) < min_confidence:
                continue
            original = _normalize_text(record.get("original"))
            corrected = _normalize_text(record.get("corrected"))
            if not original or not corrected or original == corrected:
                continue
            if len(original) > 20 or len(corrected) > 20:
                continue
            counter[original] += 1
            pairs[original] = corrected
        return {orig: pairs[orig] for orig, _ in counter.most_common() if counter[orig] >= min_count}

    def should_retrain_lm(self, feedback_threshold=20, days_threshold=14):
        stats = self.get_stats()
        accepted = stats.get("accepted", 0)
        last_updated = self._index.get("last_updated_at")
        last_dt = _parse_dt(last_updated)
        if last_dt <= _parse_dt("1970-01-01"):
            return accepted >= feedback_threshold
        return accepted >= feedback_threshold or (_utcnow() - last_dt) >= timedelta(days=days_threshold)

    # ==================== 导出视图 ====================

    def export_hotwords(self, dept=None, doctor_id=None, limit=120):
        return {
            "view": "hotwords",
            "dept": dept or "",
            "doctor_id": doctor_id or "",
            "terms": [{"term": term, "score": score} for term, score in self.get_top_terms(dept=dept, doctor_id=doctor_id, limit=limit)],
        }

    def export_postprocess(self, min_confidence=0.7):
        items = []
        for record in self._memories:
            if record.get("status") != "accepted":
                continue
            original = _normalize_text(record.get("original"))
            corrected = _normalize_text(record.get("corrected"))
            confidence = float(record.get("confidence", 0.0) or 0.0)
            if not original or not corrected or original == corrected:
                continue
            if confidence < min_confidence:
                continue
            items.append({
                "wrong": original,
                "right": corrected,
                "confidence": confidence,
                "freq": record.get("freq", 0),
            })
        items.sort(key=lambda x: x["confidence"], reverse=True)
        return {"view": "postprocess_hotwords", "dept": "", "items": items[:400]}

    def export_prompt_pack(self, dept=None, field=None, doctor_id=None, top_k=24):
        top_terms = [term for term, _ in self.get_top_terms(dept=dept, doctor_id=doctor_id, limit=top_k)]
        recent_pairs = self.get_recent_pairs(limit=top_k)
        return {
            "view": "prompt_pack",
            "dept": dept or "",
            "field": field or "",
            "doctor_id": doctor_id or "",
            "top_terms": top_terms,
            "recent_pairs": recent_pairs,
            "template_context": "",
            "instruction": "优先识别医学专科术语，保持诊断、症状、用药一致。",
        }

    # ==================== 内部更新 ====================

    def _update_status(self, memory_id, status, doctor_id=None, accepted_delta=0, rejected_delta=0):
        updated = False
        now = _format_dt(_utcnow())
        for record in self._memories:
            if record.get("memory_id") == memory_id:
                record["status"] = status
                record["updated_at"] = now
                record["last_used_at"] = now
                record["doctor_id"] = _normalize_text(record.get("doctor_id") or doctor_id or DEFAULT_DOCTOR_ID)
                if accepted_delta:
                    record["accepted_count"] = int(record.get("accepted_count", 0) or 0) + accepted_delta
                if rejected_delta:
                    record["rejected_count"] = int(record.get("rejected_count", 0) or 0) + rejected_delta
                record["confidence"] = min(1.0, max(0.0, float(record.get("accepted_count", 0) - record.get("rejected_count", 0) * 0.5) / 10.0))
                updated = True
                break
        if updated:
            self._overwrite_memories(self._memories)
        return updated

    def _top_terms(self, counter, limit=200):
        return [[term, score] for term, score in counter.most_common(limit)]


def get_memory(memory_path=None, index_path=None, backup_dir=None):
    return CorrectionMemory(memory_path=memory_path, index_path=index_path, backup_dir=backup_dir)


def _default_confidence(record):
    status = _normalize_text(record.get("status") or "pending")
    explicit = record.get("confidence", 0.0)
    try:
        explicit = float(explicit)
    except Exception:
        explicit = 0.0
    if explicit > 0.0:
        return explicit
    if status == "accepted":
        return 0.7
    if status == "rejected":
        return 0.3
    return 0.0


    def accept_memory_by_values(self, original, corrected, doctor_id=None, dept=None):
        original = _normalize_text(original)
        corrected = _normalize_text(corrected)
        if not original or not corrected or original == corrected:
            return False
        for record in self._memories:
            if record.get("original") == original and record.get("corrected") == corrected:
                return self.accept_memory(record.get("memory_id"), doctor_id=doctor_id)
        record = {
            "original": original,
            "corrected": corrected,
            "status": "accepted",
            "confidence": _default_confidence({"status": "accepted"}),
            "freq": 1,
            "accepted_count": 1,
            "rejected_count": 0,
        }
        if doctor_id:
            record["doctor_id"] = _normalize_text(doctor_id)
        if dept:
            record["dept"] = _normalize_text(dept)
        self.add_memory(record)
        return True

    def reject_memory_by_values(self, original, corrected, doctor_id=None, dept=None):
        original = _normalize_text(original)
        corrected = _normalize_text(corrected)
        if not original or not corrected or original == corrected:
            return False
        for record in self._memories:
            if record.get("original") == original and record.get("corrected") == corrected:
                return self.reject_memory(record.get("memory_id"), doctor_id=doctor_id)
        record = {
            "original": original,
            "corrected": corrected,
            "status": "rejected",
            "confidence": _default_confidence({"status": "rejected"}),
            "freq": 1,
            "accepted_count": 0,
            "rejected_count": 1,
        }
        if doctor_id:
            record["doctor_id"] = _normalize_text(doctor_id)
        if dept:
            record["dept"] = _normalize_text(dept)
        self.add_memory(record)
        return True

    def record_final_text(self, final_text, doctor_id=None, dept=None, field=None, record_id=None, snapshot=""):
        final_text = _normalize_text(final_text)
        snapshot = _normalize_text(snapshot)
        if not final_text:
            return []
        if record_id:
            try:
                record_id = int(record_id)
            except Exception:
                record_id = None
        base = {
            "doctor_id": _normalize_text(doctor_id),
            "dept": _normalize_text(dept),
            "field": _normalize_text(field),
            "source": "final_text",
            "status": "accepted",
            "original": snapshot or final_text,
            "corrected": final_text,
            "confidence": 0.95,
            "freq": 1,
            "accepted_count": 1,
            "rejected_count": 0,
            "meta": {"record_id": record_id, "snapshot_id": snapshot or None},
        }
        if snapshot and snapshot != final_text:
            self.add_memory(base)
            return [base]
        return []
