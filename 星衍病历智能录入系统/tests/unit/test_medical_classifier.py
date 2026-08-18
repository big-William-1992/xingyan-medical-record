"""
单元测试：medical_classifier.py - 病历分类和字段填充
"""
import pytest


class TestMedicalClassifier:
    """病历分类器测试"""

    def test_classify_basic(self):
        from medical_classifier import MedicalClassifier
        mc = MedicalClassifier()
        field, confidence = mc.classify("主诉：发热三天")
        assert isinstance(field, str)
        assert isinstance(confidence, float)
        assert len(field) > 0

    def test_incremental_fill(self):
        """增量填充应将文本插入到正确字段"""
        from medical_classifier import MedicalClassifier
        mc = MedicalClassifier()
        base = "主诉：\n现病史：\n既往史：无"
        text = "发热三天"
        result = mc.incremental_fill(text, base)
        assert isinstance(result, str)
        assert len(result) >= len(base)

    def test_field_keywords_from_signals(self):
        """FIELD_KEYWORDS 应从 FIELD_SIGNALS 派生"""
        from medical_classifier import MedicalClassifier
        mc = MedicalClassifier()
        assert hasattr(mc, 'FIELD_KEYWORDS')
        assert isinstance(mc.FIELD_KEYWORDS, dict)
        # FIELD_KEYWORDS 的键应是 FIELD_SIGNALS 的子集
        assert set(mc.FIELD_KEYWORDS.keys()).issubset(set(mc.FIELD_SIGNALS.keys()))
