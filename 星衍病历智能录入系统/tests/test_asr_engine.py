#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ASR引擎测试
"""
import pytest
import numpy as np
from unittest.mock import Mock, patch, MagicMock
from asr_engine import ASREngine


class TestASREngine:
    """ASR引擎测试类"""
    
    @pytest.fixture
    def asr_engine(self):
        """创建ASR引擎实例（mock模型）"""
        with patch('asr_engine.AutoModel') as mock_model:
            mock_model.return_value = Mock()
            engine = ASREngine()
            engine.model = Mock()
            return engine
    
    def test_init(self, asr_engine):
        """测试初始化"""
        assert asr_engine.sample_rate == 16000
        assert asr_engine.recording_duration == 30
        assert asr_engine.is_listening == False
        assert asr_engine._frames_lock is not None
    
    def test_set_hotwords(self, asr_engine):
        """测试热词设置"""
        asr_engine._hotword_sections = {
            "通用": ["高血压", "糖尿病"],
            "内科": ["心电图", "血常规"]
        }
        asr_engine.set_hotwords("内科")
        assert "高血压" in asr_engine._current_hotwords
        assert "心电图" in asr_engine._current_hotwords
    
    def test_set_field_context(self, asr_engine):
        """测试字段上下文设置"""
        asr_engine.set_field_context("主诉")
        assert asr_engine._field_context == "主诉"
        
        asr_engine.set_field_context("")
        assert asr_engine._field_context == ""
    
    def test_is_ready(self, asr_engine):
        """测试就绪状态"""
        asr_engine.model = Mock()
        assert asr_engine.is_ready() == True
        
        asr_engine.model = None
        assert asr_engine.is_ready() == False
    
    def test_thread_safety(self, asr_engine):
        """测试线程安全"""
        import threading
        
        errors = []
        
        def writer():
            try:
                for i in range(50):
                    with asr_engine._frames_lock:
                        asr_engine._recorded_frames.append(np.array([i], dtype=np.int16))
            except Exception as e:
                errors.append(e)
        
        def reader():
            try:
                for i in range(50):
                    with asr_engine._frames_lock:
                        _ = len(asr_engine._recorded_frames)
            except Exception as e:
                errors.append(e)
        
        threads = []
        for _ in range(3):
            threads.append(threading.Thread(target=writer))
            threads.append(threading.Thread(target=reader))
        
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        assert len(errors) == 0, f"线程安全问题: {errors}"
    
    def test_denoise(self, asr_engine):
        """测试降噪功能"""
        # 创建测试音频数据
        audio = np.random.randint(-1000, 1000, 16000, dtype=np.int16)
        
        # 测试降噪
        denoised = asr_engine._denoise(audio)
        
        assert denoised is not None
        assert len(denoised) == len(audio)
        assert denoised.dtype == np.int16
    
    def test_extract_confusion_pairs(self, tmp_path):
        """测试混淆对提取"""
        import json
        
        # 创建测试反馈文件
        feedback_file = tmp_path / "correction_feedback.jsonl"
        feedback_data = [
            {"original": "心电围", "corrected": "心电图", "status": "accepted", "source": "auto"},
            {"original": "心电围", "corrected": "心电图", "status": "accepted", "source": "auto"},
            {"original": "心电围", "corrected": "心电图", "status": "accepted", "source": "auto"},
        ]
        
        with open(feedback_file, 'w', encoding='utf-8') as f:
            for item in feedback_data:
                f.write(json.dumps(item, ensure_ascii=False) + '\n')
        
        # 测试提取
        with patch('asr_engine.os.path.dirname') as mock_dirname:
            mock_dirname.return_value = str(tmp_path)
            pairs = ASREngine.extract_confusion_pairs(min_count=3)
            
        assert "心电围" in pairs
        assert pairs["心电围"] == "心电图"


class TestASRHotwords:
    """ASR热词管理测试"""
    
    @pytest.fixture
    def asr_engine(self):
        with patch('asr_engine.AutoModel'):
            engine = ASREngine()
            engine.model = Mock()
            return engine
    
    def test_load_hotwords(self, asr_engine, tmp_path):
        """测试热词加载"""
        hotwords_file = tmp_path / "hotwords.txt"
        hotwords_file.write_text("# 通用\n高血压\n糖尿病\n# 内科\n心电图\n", encoding='utf-8')
        
        asr_engine._hotwords_path = str(hotwords_file)
        asr_engine._load_hotwords()
        
        assert "通用" in asr_engine._hotword_sections
        assert "高血压" in asr_engine._hotword_sections["通用"]
        assert "内科" in asr_engine._hotword_sections
    
    def test_write_hotword_file(self, asr_engine, tmp_path):
        """测试热词文件写入"""
        asr_engine._hotword_file = str(tmp_path / "test_hotwords.txt")
        
        words = ["高血压", "糖尿病:3", "心电图:2"]
        asr_engine._write_hotword_file(words)
        
        with open(asr_engine._hotword_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 验证权重展开
        assert content.count("高血压") == 1
        assert content.count("糖尿病") == 3
        assert content.count("心电图") == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
