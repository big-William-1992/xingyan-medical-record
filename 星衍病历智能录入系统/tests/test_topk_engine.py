import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from correction_memory import CorrectionMemory
from topk_engine import TopKEngine, _time_decay_score, _score_record


def _write_memory(records):
    tmpdir = Path(tempfile.mkdtemp())
    memory_path = tmpdir / "memory.jsonl"
    with open(memory_path, "w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    memory = CorrectionMemory(memory_path=memory_path, index_path=tmpdir / "index.json")
    return TopKEngine(memory=memory)


class TestTimeDecay(unittest.TestCase):
    def test_recent_decay(self):
        now = datetime.utcnow()
        self.assertEqual(_time_decay_score(now, now), 1.5)
        self.assertEqual(_time_decay_score(now - timedelta(days=15), now), 1.5)
        self.assertEqual(_time_decay_score(now - timedelta(days=40), now), 1.0)
        self.assertEqual(_time_decay_score(now - timedelta(days=100), now), 0.5)


class TestScoreRecord(unittest.TestCase):
    def test_score_with_decay(self):
        now = datetime.utcnow()
        record = {
            "corrected": "发热",
            "original": "发烧",
            "confidence": 0.8,
            "accepted_count": 2,
            "rejected_count": 0,
            "updated_at": (now - timedelta(days=10)).strftime("%Y-%m-%dT%H:%M:%S"),
        }
        term, score = _score_record(record, now)
        self.assertEqual(term, "发热")
        self.assertGreater(score, 2.0)


class TestTopKEngine(unittest.TestCase):
    def test_topk_respects_limit(self):
        engine = _write_memory([
            {"corrected": f"词{i}", "original": f"词{i}", "status": "accepted", "confidence": 0.9, "accepted_count": 1, "rejected_count": 0, "dept": "通用", "updated_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")}
            for i in range(20)
        ])
        terms = engine.get_top_terms(limit=5)
        self.assertEqual(len(terms), 5)

    def test_build_prompt_pack_contains_terms_and_pairs(self):
        engine = _write_memory([
            {"corrected": "发热", "original": "发烧", "status": "accepted", "confidence": 0.9, "accepted_count": 1, "rejected_count": 0, "dept": "内科", "updated_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")},
            {"corrected": "高血压", "original": "高血亚", "status": "accepted", "confidence": 0.8, "accepted_count": 1, "rejected_count": 0, "dept": "内科", "updated_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")},
        ])
        pack = engine.build_prompt_pack(dept="内科", top_k=4)
        self.assertEqual(pack["view"], "prompt_pack")
        self.assertIn("发热", pack["top_terms"])
        self.assertEqual(pack["hotword_lines"], pack["selected_terms"])
        self.assertTrue(any("高血亚 => 高血压" in line for line in pack["postprocess_hotword_lines"]))


if __name__ == "__main__":
    unittest.main()
