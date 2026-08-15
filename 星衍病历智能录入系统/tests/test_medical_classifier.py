#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
医学分类器测试
"""
import pytest
from medical_classifier import MedicalClassifier


class TestMedicalClassifier:
    """医学分类器测试类"""
    
    @pytest.fixture
    def classifier(self):
        """创建分类器实例"""
        return MedicalClassifier()
    
    def test_classify_chief_complaint(self, classifier):
        """测试主诉分类"""
        text = "发热三天，伴有咳嗽"
        field, confidence = classifier.classify(text)
        assert field == "主诉"
        assert confidence > 0.3
    
    def test_classify_present_illness(self, classifier):
        """测试现病史分类"""
        text = "患者三天前受凉后出现发热，体温最高38.5度，伴有咳嗽咳痰"
        field, confidence = classifier.classify(text)
        assert field == "现病史"
        assert confidence > 0.3
    
    def test_classify_past_history(self, classifier):
        """测试既往史分类"""
        text = "高血压病史五年，糖尿病病史三年"
        field, confidence = classifier.classify(text)
        assert field == "既往史"
        assert confidence > 0.3
    
    def test_classify_physical_exam(self, classifier):
        """测试体格检查分类"""
        text = "体温36.5度，脉搏78次/分，血压120/80mmHg"
        field, confidence = classifier.classify(text)
        assert field == "体格检查"
        assert confidence > 0.3
    
    def test_classify_auxiliary_exam(self, classifier):
        """测试辅助检查分类"""
        text = "血常规：白细胞12×10^9/L，中性粒细胞85%"
        field, confidence = classifier.classify(text)
        assert field == "辅助检查"
        assert confidence > 0.3
    
    def test_classify_diagnosis(self, classifier):
        """测试诊断分类"""
        text = "1. 社区获得性肺炎\n2. 高血压病2级"
        field, confidence = classifier.classify(text)
        assert field == "初步诊断"
        assert confidence > 0.3
    
    def test_extract_basic_fields(self, classifier):
        """测试基本信息提取"""
        text = "张伟，男，53岁，已婚，汉族"
        fields = classifier.extract_basic_fields(text)
        
        assert fields.get("姓名") == "张伟"
        assert fields.get("性别") == "男"
        assert "53" in fields.get("年龄", "")
        assert fields.get("婚姻状况") == "已婚"
        assert fields.get("民族") == "汉族"
    
    def test_incremental_fill(self, classifier):
        """测试增量填充"""
        template = """主诉：
现病史：
既往史：
"""
        text = "主诉发热三天，现病史三天前受凉后出现发热"
        result = classifier.incremental_fill(text, template)
        
        assert "发热三天" in result
        assert "三天前受凉" in result
    
    def test_incremental_fill_no_overwrite(self, classifier):
        """测试增量填充不覆盖已有内容"""
        template = """主诉：发热三天
现病史：
既往史：
"""
        text = "现病史三天前受凉后出现发热"
        result = classifier.incremental_fill(text, template)
        
        # 主诉应保持不变
        assert "主诉：发热三天" in result
        # 现病史应被填充
        assert "三天前受凉" in result
    
    def test_chinese_num_to_int(self, classifier):
        """测试中文数字转换"""
        assert classifier._chinese_num_to_int("五") == 5
        assert classifier._chinese_num_to_int("十五") == 15
        assert classifier._chinese_num_to_int("五十三") == 53
        assert classifier._chinese_num_to_int("一百二十") == 120
    
    def test_extract_chief_complaint(self, classifier):
        """测试主诉提取"""
        text = "2024年7月24日入院，发热三天"
        result = classifier._extract_chief_complaint(text)
        assert "发热三天" in result
        assert "入院" not in result
    
    def test_standardize_field(self, classifier):
        """测试字段标准化"""
        assert classifier._standardize_field("主诉") == "主诉"
        assert classifier._standardize_field("现病史") == "现病史"
        assert classifier._standardize_field("未知字段") == "未知字段"
    
    def test_classify_paragraphs(self, classifier):
        """测试多段落分类"""
        paragraphs = [
            "发热三天",
            "三天前受凉后出现发热",
            "高血压病史五年"
        ]
        results = classifier.classify_paragraphs(paragraphs)
        
        assert len(results) == 3
        assert results[0][0] == "主诉"  # 第一段应为主诉
        assert results[1][0] in ["现病史", "主诉"]  # 第二段可能是现病史
        assert results[2][0] == "既往史"  # 第三段应为既往史


class TestFieldSignals:
    """字段信号测试"""
    
    @pytest.fixture
    def classifier(self):
        return MedicalClassifier()
    
    def test_field_signals_exist(self, classifier):
        """测试字段信号存在"""
        assert "主诉" in classifier.FIELD_SIGNALS
        assert "现病史" in classifier.FIELD_SIGNALS
        assert "既往史" in classifier.FIELD_SIGNALS
        assert "体格检查" in classifier.FIELD_SIGNALS
    
    def test_chief_complaint_keywords(self, classifier):
        """测试主诉关键词"""
        signals = classifier.FIELD_SIGNALS["主诉"]
        assert "发热" in signals["keywords"]
        assert "咳嗽" in signals["keywords"]
        assert "max_chars" in signals
    
    def test_present_illness_keywords(self, classifier):
        """测试现病史关键词"""
        signals = classifier.FIELD_SIGNALS["现病史"]
        assert "发病" in signals["keywords"]
        assert "出现" in signals["keywords"]
        assert "min_chars" in signals


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
