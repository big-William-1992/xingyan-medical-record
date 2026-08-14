#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
M3 Top-K 术语引擎

职责：
- 从 CorrectionMemory 生成全局/科室/医生级 Top-K 术语
- 时间衰减：近 30/90 天权重更高
- 置信度加权：accepted_rate 高者优先
- 预算控制：模板/字段下最多返回 N 个词

输出：
- selected_terms
- prompt_pack
- hotword_lines
- postprocess_hotword_lines

接入点：
- ASREngine.set_hotwords() 前调用
- 换科室、保存病历、LM 重训后刷新
"""
from collections import Counter, defaultdict
from datetime import datetime, timedelta

from correction_memory import get_memory

DEFAULT_TIME_FMT = "%Y-%m-%dT%H:%M:%S"


def _parse_dt(value):
    if not value:
        return datetime.utcnow()
    if isinstance(value, datetime):
        return value
    for fmt in (DEFAULT_TIME_FMT, "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(str(value), fmt)
        except Exception:
            continue
    return datetime.utcnow()


def _time_decay_score(updated_at, now=None):
    if now is None:
        now = datetime.utcnow()
    try:
        days = (now - _parse_dt(updated_at)).total_seconds() / 86400.0
    except Exception:
        return 1.0
    if days <= 30:
        return 1.5
    if days <= 90:
        return 1.0
    return 0.5


def _score_record(record, now):
    term = (record.get("corrected") or record.get("original") or "").strip()
    if not term:
        return None
    confidence = float(record.get("confidence", 0.0) or 0.0)
    accepted_count = int(record.get("accepted_count", 0) or 0)
    rejected_count = int(record.get("rejected_count", 0) or 0)
    score = 1.0 + confidence
    score += min(accepted_count, 10) * 0.2
    score -= min(rejected_count, 10) * 0.4
    score *= _time_decay_score(record.get("updated_at") or record.get("created_at"), now)
    return term, round(score, 3)


class TopKEngine:
    def __init__(self, memory=None):
        self.memory = memory or get_memory()

    def get_top_terms(self, dept=None, doctor_id=None, limit=80, time_decay=True):
        now = datetime.utcnow()
        counter = Counter()
        for record in self.memory.get_memories(
            doctor_id=doctor_id,
            dept=dept,
            status="accepted",
            limit=5000,
        ):
            scored = _score_record(record, now) if time_decay else _score_record(record, None)
            if not scored:
                continue
            term, score = scored
            counter[term] += score
        return [[term, score] for term, score in counter.most_common(limit)]

    def get_top_terms_by_field(self, field, dept=None, doctor_id=None, limit=40, time_decay=True):
        now = datetime.utcnow()
        counter = Counter()
        for record in self.memory.get_memories(
            doctor_id=doctor_id,
            dept=dept,
            field=field,
            status="accepted",
            limit=5000,
        ):
            scored = _score_record(record, now) if time_decay else _score_record(record, None)
            if not scored:
                continue
            term, score = scored
            counter[term] += score
        return [[term, score] for term, score in counter.most_common(limit)]

    def build_prompt_pack(self, dept=None, field=None, doctor_id=None, top_k=24):
        top_terms = [term for term, _ in self.get_top_terms(dept=dept, doctor_id=doctor_id, limit=top_k, time_decay=True)]
        recent_pairs = []
        seen = set()
        for record in self.memory.get_memories(dept=dept, doctor_id=doctor_id, status="accepted", limit=5000):
            original = (record.get("original") or "").strip()
            corrected = (record.get("corrected") or "").strip()
            if not original or not corrected or original == corrected:
                continue
            key = (original, corrected)
            if key in seen:
                continue
            seen.add(key)
            recent_pairs.append([original, corrected])
        recent_pairs = recent_pairs[-top_k:]
        return {
            "view": "prompt_pack",
            "dept": dept or "",
            "field": field or "",
            "doctor_id": doctor_id or "",
            "top_terms": top_terms,
            "recent_pairs": recent_pairs,
            "template_context": "",
            "instruction": "优先识别医学专科术语，保持诊断、症状、用药一致。",
            "selected_terms": top_terms,
            "hotword_lines": list(top_terms),
            "postprocess_hotword_lines": [f"{p[0]} => {p[1]}" for p in recent_pairs],
        }

    def build_field_prompt_pack(self, field, dept=None, doctor_id=None, top_k=24):
        field_terms = [term for term, _ in self.get_top_terms_by_field(field=field, dept=dept, doctor_id=doctor_id, limit=top_k, time_decay=True)]
        global_terms = [term for term, _ in self.get_top_terms(dept=dept, doctor_id=doctor_id, limit=top_k, time_decay=True)]
        merged = []
        seen = set()
        for term in field_terms + global_terms:
            if term and term not in seen:
                seen.add(term)
                merged.append(term)
            if len(merged) >= top_k:
                break
        recent_pairs = []
        seen = set()
        for record in self.memory.get_memories(dept=dept, doctor_id=doctor_id, field=field, status="accepted", limit=5000):
            original = (record.get("original") or "").strip()
            corrected = (record.get("corrected") or "").strip()
            if not original or not corrected or original == corrected:
                continue
            key = (original, corrected)
            if key in seen:
                continue
            seen.add(key)
            recent_pairs.append([original, corrected])
        recent_pairs = recent_pairs[-top_k:]
        return {
            "view": "prompt_pack",
            "dept": dept or "",
            "field": field or "",
            "doctor_id": doctor_id or "",
            "top_terms": merged,
            "recent_pairs": recent_pairs,
            "template_context": "",
            "instruction": "优先识别当前字段医学术语，保持诊断、症状、用药一致。",
            "selected_terms": merged,
            "hotword_lines": list(merged),
            "postprocess_hotword_lines": [f"{p[0]} => {p[1]}" for p in recent_pairs],
        }

    def get_hotword_lines(self, dept=None, doctor_id=None, limit=120):
        return [term for term, _ in self.get_top_terms(dept=dept, doctor_id=doctor_id, limit=limit, time_decay=True)]

    def get_postprocess_hotword_lines(self, dept=None, doctor_id=None, min_confidence=0.7, limit=200):
        seen = set()
        result = []
        for record in self.memory.get_memories(dept=dept, doctor_id=doctor_id, status="accepted", limit=5000):
            confidence = float(record.get("confidence", 0.0) or 0.0)
            if confidence < min_confidence:
                continue
            original = (record.get("original") or "").strip()
            corrected = (record.get("corrected") or "").strip()
            if not original or not corrected or original == corrected:
                continue
            line = f"{original} => {corrected}"
            if line in seen:
                continue
            seen.add(line)
            result.append(line)
        return result[:limit]

    def refresh_asr_hotwords(self, asr_engine, dept=None, doctor_id=None, term_budget=300, postprocess_budget=100):
        if asr_engine is None:
            return False
        prompt_pack = self.build_prompt_pack(dept=dept, doctor_id=doctor_id, top_k=term_budget)
        asr_engine.set_prompt_pack(prompt_pack)
        asr_engine.apply_prompt_pack()
        return True


def get_topk_engine(memory=None):
    return TopKEngine(memory=memory)
