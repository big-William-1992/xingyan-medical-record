"""
关键路径单元测试
覆盖：纠错引擎 / 医学语言模型 / 模板引擎 / 后处理函数

运行：cd 星衍病历智能录入系统 && python -m pytest tests/ -v
或：  python -m unittest discover tests -v
"""
import os
import sys
import unittest

# 确保能导入项目模块
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ═══════════════════════════════════════════════════════════
#  纠错引擎测试
# ═══════════════════════════════════════════════════════════

class TestCorrector(unittest.TestCase):
    """Corrector 核心纠错逻辑"""

    @classmethod
    def setUpClass(cls):
        try:
            from corrector import Corrector
            cls.corrector = Corrector()
        except Exception as e:
            raise unittest.SkipTest(f"Corrector 导入失败: {e}")

    def test_term_correction_fever(self):
        """口语'发烧'应纠正为'发热'（通过 post_process_medical）"""
        result = self.corrector.post_process_medical("患者发烧3天")
        self.assertIn("发热", result)
        self.assertNotIn("发烧", result)

    def test_term_correction_headache(self):
        """口语'头疼'应纠正为'头痛'"""
        result = self.corrector.post_process_medical("头疼伴头晕")
        self.assertIn("头痛", result)

    def test_term_correction_diarrhea(self):
        """口语'拉肚子'应纠正为'腹泻'"""
        result = self.corrector.post_process_medical("拉肚子2天")
        self.assertIn("腹泻", result)

    def test_term_correction_wbc(self):
        """'白血胞'应纠正为'白细胞'"""
        result = self.corrector.post_process_medical("白血胞计数升高")
        self.assertIn("白细胞", result)

    def test_term_correction_ecg(self):
        """'心电围'应纠正为'心电图'"""
        result = self.corrector.post_process_medical("心电围示ST段改变")
        self.assertIn("心电图", result)

    def test_term_correction_cephalosporin(self):
        """'头炮'应纠正为'头孢'"""
        result = self.corrector.post_process_medical("给予头炮抗感染")
        self.assertIn("头孢", result)

    def test_no_false_positive_normal_text(self):
        """正常医学文本不应被误纠"""
        normal = "患者因咳嗽、咳痰3天入院，体温38.5℃，双肺呼吸音粗。"
        result = self.corrector.post_process_medical(normal)
        # 核心内容不应改变
        self.assertIn("咳嗽", result)
        self.assertIn("咳痰", result)
        self.assertIn("双肺呼吸音粗", result)

    def test_no_false_positive_suggestion(self):
        """'建议'二字在句中不应触发异常"""
        text = "建议复查血常规"
        result = self.corrector.post_process_medical(text)
        self.assertIn("建议", result)

    def test_empty_input(self):
        """空输入安全"""
        result, log = self.corrector.correct("")
        self.assertEqual(result, "")
        self.assertEqual(log, [])

    def test_format_unit_mmol(self):
        """数字+单位格式化：'10mol' → '10mmol/L'"""
        result, _ = self.corrector.correct("血钾 10mol")
        self.assertIn("mmol/L", result)

    def test_format_repeated_chars(self):
        """重复字清理：'咳咳咳' → '咳咳'"""
        result, _ = self.corrector.correct("患者咳咳咳不止")
        self.assertNotIn("咳咳咳", result)

    def test_correct_returns_tuple(self):
        """correct() 返回 (result, log) 元组"""
        result = self.corrector.correct("测试文本")
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 2)

    def test_log_has_structure(self):
        """纠错日志应包含必要字段"""
        _, log = self.corrector.correct("发烧伴头疼")
        if log:
            item = log[0]
            self.assertIn("原文", item)
            self.assertIn("修正", item)
            self.assertIn("分类", item)


# ═══════════════════════════════════════════════════════════
#  后处理函数测试
# ═══════════════════════════════════════════════════════════

class TestPostProcess(unittest.TestCase):
    """post_process_medical 独立函数"""

    @classmethod
    def setUpClass(cls):
        try:
            from corrector import post_process_medical
            cls.post_process = post_process_medical
        except ImportError:
            cls.post_process = None

    def setUp(self):
        if self.post_process is None:
            self.skipTest("corrector 模块不可用")

    def test_auto_newline_after_period(self):
        """句号后自动换行"""
        from corrector import post_process_medical
        text = "患者头痛3天。伴恶心呕吐。"
        result = post_process_medical(text)
        self.assertIn("\n", result)

    def test_keyword_newline(self):
        """病历关键词前插入换行"""
        from corrector import post_process_medical
        text = "患者头痛3天。现病史：患者3天前出现头痛。"
        result = post_process_medical(text)
        # "现病史"前应有换行
        self.assertIn("\n现病史", result)

    def test_term_corrections_param(self):
        """外部传入的 term_corrections 生效"""
        from corrector import post_process_medical
        text = "自定义错误词测试"
        result = post_process_medical(text, term_corrections={"错误词": "正确词"})
        self.assertIn("正确词", result)
        self.assertNotIn("错误词", result)

    def test_empty_input(self):
        """空输入返回空"""
        from corrector import post_process_medical
        self.assertEqual(post_process_medical(""), "")
        self.assertIsNone(post_process_medical(None))

    def test_no_triple_newline(self):
        """不应出现三个连续换行"""
        from corrector import post_process_medical
        text = "第一段。主诉：头痛。现病史：3天前。"
        result = post_process_medical(text)
        self.assertNotIn("\n\n\n", result)


# ═══════════════════════════════════════════════════════════
#  医学语言模型测试
# ═══════════════════════════════════════════════════════════

try:
    from medical_lm import MedicalLM
    HAS_MEDICAL_LM = True
except ImportError:
    HAS_MEDICAL_LM = False

@unittest.skipUnless(HAS_MEDICAL_LM, "medical_lm 依赖 kenlm，CI 中不可用")
class TestMedicalLM(unittest.TestCase):
    """MedicalLM 3-gram 语言模型"""

    @classmethod
    def setUpClass(cls):
        cls.lm = MedicalLM()

    def test_model_loaded(self):
        """模型文件应成功加载"""
        if not self.lm.is_ready:
            self.skipTest("medical_3gram.pkl 不存在，跳过")
        self.assertTrue(self.lm.is_ready)

    def test_score_normal_text(self):
        """正常医学文本得分应高于乱码"""
        if not self.lm.is_ready:
            self.skipTest("模型未加载")
        normal = "患者因咳嗽咳痰三天入院治疗"
        garbage = "齉齾齉齾齉齾齉齾齉齾齉齾"
        score_normal = self.lm.score(normal)
        score_garbage = self.lm.score(garbage)
        self.assertGreater(score_normal, score_garbage)

    def test_rescore_no_change_for_good_text(self):
        """高质量文本不应被 rescore 修改"""
        if not self.lm.is_ready:
            self.skipTest("模型未加载")
        good = "患者因咳嗽、咳痰三天入院，体温三十八点五度。"
        result = self.lm.rescore(good)
        self.assertIn("咳嗽", result)
        self.assertIn("入院", result)

    def test_rescore_empty_safe(self):
        """空文本 rescore 安全"""
        if not self.lm.is_ready:
            self.skipTest("模型未加载")
        self.assertEqual(self.lm.rescore(""), "")
        self.assertEqual(self.lm.rescore("短"), "短")

    def test_score_region(self):
        """区域评分应返回浮点数"""
        if not self.lm.is_ready:
            self.skipTest("模型未加载")
        text = "患者头痛三天伴恶心"
        score = self.lm.score_region(text, 2, 4)
        self.assertIsInstance(score, float)


# ═══════════════════════════════════════════════════════════
#  模板引擎测试
# ═══════════════════════════════════════════════════════════

class TestTemplateEngine(unittest.TestCase):
    """TemplateEngine 模板加载与查询"""

    @classmethod
    def setUpClass(cls):
        try:
            from template_engine import TemplateEngine
            cls.engine = TemplateEngine()
        except Exception as e:
            raise unittest.SkipTest(f"TemplateEngine 导入失败: {e}")

    def test_departments_not_empty(self):
        """至少有一个科室"""
        depts = self.engine.get_departments()
        self.assertGreater(len(depts), 0)

    def test_templates_for_department(self):
        """每个科室至少有一个模板"""
        for dept in self.engine.get_departments():
            templates = self.engine.get_templates(dept)
            self.assertGreater(len(templates), 0, f"{dept} 没有模板")

    def test_get_template_content(self):
        """获取模板内容非空"""
        depts = self.engine.get_departments()
        dept = depts[0]
        templates = self.engine.get_templates(dept)
        # templates 是 dict 列表，取第一个的 name
        tpl_name = templates[0]["name"]
        content = self.engine.get_template(dept, tpl_name)
        self.assertIsNotNone(content)
        self.assertGreater(len(content), 50)

    def test_get_nonexistent_template(self):
        """不存在的模板返回空字符串"""
        result = self.engine.get_template("不存在的科室", "不存在的模板")
        self.assertEqual(result, "")

    def test_template_has_fields(self):
        """模板内容应包含病历字段关键词"""
        depts = self.engine.get_departments()
        dept = depts[0]
        templates = self.engine.get_templates(dept)
        tpl_name = templates[0]["name"]
        content = self.engine.get_template(dept, tpl_name)
        # 至少包含一个常见字段
        fields = ["主诉", "现病史", "体格检查", "诊断"]
        has_field = any(f in content for f in fields)
        self.assertTrue(has_field, f"模板缺少常见字段: {content[:100]}")


# ═══════════════════════════════════════════════════════════
#  纠错反馈模块测试
# ═══════════════════════════════════════════════════════════

class TestCorrectionFeedback(unittest.TestCase):
    """CorrectionFeedback 反馈收集"""

    def test_import(self):
        """模块可正常导入"""
        from correction_feedback import CorrectionFeedback
        fb = CorrectionFeedback()
        self.assertIsNotNone(fb)

    def test_stats_structure(self):
        """统计信息结构正确"""
        from correction_feedback import CorrectionFeedback
        fb = CorrectionFeedback()
        stats = fb.get_stats()
        self.assertIsInstance(stats, dict)


# ═══════════════════════════════════════════════════════════
#  音频组件测试（无 GUI 显示，需要 PyQt5）
# ═══════════════════════════════════════════════════════════

try:
    from PyQt5.QtWidgets import QApplication
    HAS_PYQT5 = True
except ImportError:
    HAS_PYQT5 = False

# 音频组件测试需要真实图形显示环境（QApplication 在无头/CI 环境会 C 级崩溃），
# 仅在本地有显示器时手动运行：python -m pytest tests/test_core.py -k AudioWidgets
@unittest.skip("音频组件测试需要图形显示环境，请在有显示器的本地环境手动运行")
class TestAudioWidgets(unittest.TestCase):
    """audio_widgets 组件逻辑（需图形环境）"""

    def test_waveform_add_level(self):
        """波形图添加电平"""
        from audio_widgets import WaveformWidget
        wf = WaveformWidget()
        wf.add_level(0.5)
        wf.add_level(1.2)  # 应被 clamp 到 1.0
        wf.add_level(-0.3)  # 应被 clamp 到 0.0
        self.assertEqual(len(wf._levels), 3)
        self.assertLessEqual(wf._levels[1], 1.0)
        self.assertGreaterEqual(wf._levels[2], 0.0)

    def test_waveform_clear_on_stop(self):
        """停止录音时清空波形"""
        from audio_widgets import WaveformWidget
        wf = WaveformWidget()
        wf.add_level(0.8)
        wf.set_active(False)
        self.assertEqual(len(wf._levels), 0)

    def test_audio_player_empty_safe(self):
        """空播放器操作安全"""
        from audio_widgets import AudioPlayer
        ap = AudioPlayer()
        self.assertEqual(ap.duration, 0.0)
        self.assertEqual(ap.position, 0.0)
        self.assertFalse(ap.is_playing)
        ap.play()  # 不应崩溃
        ap.seek(5.0)  # 不应崩溃


if __name__ == "__main__":
    unittest.main(verbosity=2)
