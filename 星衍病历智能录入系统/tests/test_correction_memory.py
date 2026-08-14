import json
import os
from pathlib import Path

from correction_memory import CorrectionMemory


def test_add_and_query_memories(tmp_path):
    memory = CorrectionMemory(memory_path=tmp_path / "memory.jsonl", index_path=tmp_path / "index.json")
    first = memory.add_memory({
        "original": "发烧",
        "corrected": "发热",
        "doctor_id": "d1",
        "dept": "内科",
        "field": "现病史",
        "source": "corrector",
        "status": "accepted",
        "confidence": 0.8,
        "freq": 1,
        "accepted_count": 1,
        "rejected_count": 0,
    })
    second = memory.add_memories([
        {"original": "头孢", "corrected": "头孢", "source": "hotword", "status": "pending"},
        {"original": "肺言", "corrected": "肺炎", "source": "postprocess", "status": "accepted", "confidence": 0.9},
    ], doctor_id="d1", dept="内科")
    assert first is not None
    assert len(second) == 2
    assert memory.get_stats()["total"] == 3
    results = memory.get_memories(dept="内科", status="accepted", min_confidence=0.7)
    assert len(results) == 2
    terms = memory.get_top_terms(dept="内科", limit=2)
    assert terms[0][0] == "发热"
    assert memory.touch_memory(first["memory_id"])
    updated = memory.get_memories(memory_id=first["memory_id"])[0]
    assert updated["freq"] == 2
    assert updated["last_used_at"]


def test_backfill_creates_expected_memories(tmp_path):
    memory = CorrectionMemory(memory_path=tmp_path / "memory.jsonl", index_path=tmp_path / "index.json")
    records = [
        {"original": "发烧", "corrected": "发热", "source": "correction_feedback", "status": "accepted"},
        {"original": "  ", "corrected": " ", "source": "correction_feedback", "status": "pending"},
        {"original": "心电围", "corrected": "心电图"},
        {"original": "高血亚", "corrected": "高血压"},
    ]
    added = memory.add_memories(records)
    assert len(added) == 3
    assert memory.get_stats()["accepted"] == 2
    assert memory.get_confusion_pairs() == {"心电围": "心电图", "高血亚": "高血压"}
    assert memory.get_recent_pairs(limit=2)[0] == ["心电围", "心电图"]


def test_should_retrain_lm_thresholds(tmp_path):
    memory = CorrectionMemory(memory_path=tmp_path / "memory.jsonl", index_path=tmp_path / "index.json")
    assert memory.should_retrain_lm(feedback_threshold=1) is False
    memory.add_memory({"original": "x", "corrected": "y", "status": "accepted"})
    assert memory.should_retrain_lm(feedback_threshold=1) is True


def test_export_views(tmp_path):
    memory = CorrectionMemory(memory_path=tmp_path / "memory.jsonl", index_path=tmp_path / "index.json")
    memory.add_memories([
        {"original": "发烧", "corrected": "发热", "status": "accepted", "confidence": 0.8, "dept": "内科"},
        {"original": "头炮", "corrected": "头孢", "status": "accepted", "confidence": 0.7, "dept": "外科"},
        {"original": "糖尿病", "corrected": "糖尿病", "status": "accepted", "confidence": 0.4, "dept": "内科"},
    ])
    hotwords = memory.export_hotwords(dept="内科", limit=5)
    assert hotwords["view"] == "hotwords"
    assert hotwords["terms"][0]["term"] == "发热"
    post = memory.export_postprocess(min_confidence=0.75)
    assert post["view"] == "postprocess_hotwords"
    assert post["items"][0]["wrong"] == "发烧"
    prompt = memory.export_prompt_pack(dept="内科", field="现病史", top_k=4)
    assert prompt["top_terms"][0] == "发热"
