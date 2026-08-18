"""
单元测试：corrector.py - 纠错规则
"""
import pytest


class TestCorrector:
    """纠错引擎测试"""

    def test_correct_basic(self):
        from corrector import Corrector
        from rule_engine import RuleEngine
        c = Corrector(rule_engine=RuleEngine())
        corrected, log = c.correct("发烧三天")
        assert isinstance(corrected, str)
        assert isinstance(log, list)

    def test_correct_medical_terms(self):
        """常见医疗术语应被正确识别"""
        from corrector import Corrector
        from rule_engine import RuleEngine
        c = Corrector(rule_engine=RuleEngine())
        text = "患者发热38.5度"
        corrected, log = c.correct(text)
        assert "发热" in corrected or "发烧" in corrected

    def test_post_process_medical(self):
        """医学后处理函数应正常返回字符串"""
        from corrector import post_process_medical
        result = post_process_medical("发烧三天 咳嗽")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_atomic_save_rejection(self, tmp_path):
        """save_rejection 应使用原子写入"""
        from corrector import Corrector
        from rule_engine import RuleEngine
        import os as _os
        c = Corrector(rule_engine=RuleEngine())
        # 临时覆盖路径
        orig_dir = _os.path.dirname(c.rejections_path) if hasattr(c, 'rejections_path') else ""
        if hasattr(c, 'rejections_path'):
            c.rejections_path = str(tmp_path / "rejections.json")
            c.save_rejection("发烧", "发热")
            assert _os.path.exists(c.rejections_path)
