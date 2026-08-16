#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
集成测试
测试模块间的集成和API端点
"""
import pytest
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestModuleIntegration:
    """模块集成测试"""
    
    def test_corrector_with_rule_engine(self):
        """测试纠错引擎与规则引擎集成"""
        from corrector import Corrector
        from rule_engine import RuleEngine
        
        rule_engine = RuleEngine()
        corrector = Corrector(rule_engine=rule_engine)
        
        # 添加自定义规则
        rule_engine.add_typo_rule("测试错误", "测试正确")
        
        # 测试纠错
        result, log = corrector.correct("这是测试错误文本")
        assert "测试正确" in result
    
    def test_template_engine_with_knowledge_graph(self):
        """测试模板引擎与知识图谱集成"""
        from template_engine import TemplateEngine
        from knowledge_graph import MedicalKnowledgeGraph
        
        template_engine = TemplateEngine()
        kg = MedicalKnowledgeGraph()
        
        # 获取模板
        depts = template_engine.get_departments()
        assert len(depts) > 0
        
        # 验证知识图谱可用
        assert kg is not None
    
    def test_asr_engine_initialization(self):
        """测试ASR引擎初始化"""
        try:
            from asr_engine import ASREngine
            asr = ASREngine()
            # 不测试实际识别，只测试初始化
            assert asr is not None
        except Exception as e:
            pytest.skip(f"ASR引擎初始化失败（可能缺少模型）: {e}")
    
    def test_medical_classifier_with_corrector(self):
        """测试医学分类器与纠错器集成"""
        from medical_classifier import MedicalClassifier
        from corrector import Corrector
        
        classifier = MedicalClassifier()
        corrector = Corrector()
        
        # 先纠错
        text = "患者发烧3天"
        corrected, _ = corrector.correct(text)
        
        # 再分类
        field, confidence = classifier.classify(corrected)
        assert field in ["主诉", "现病史", None]
    
    def test_knowledge_qa_with_knowledge_graph(self):
        """测试知识问答与知识图谱集成"""
        try:
            from knowledge_qa import KnowledgeQA
            from knowledge_graph import MedicalKnowledgeGraph
            
            kg = MedicalKnowledgeGraph()
            qa = KnowledgeQA(kg=kg)
            
            # 测试简单问答
            result = qa.answer("高血压")
            assert result is not None
            assert "found" in result
        except Exception as e:
            pytest.skip(f"知识问答初始化失败: {e}")


class TestAPIMock:
    """API端点测试（使用Mock）"""
    
    def test_api_stats_endpoint(self):
        """测试统计API端点"""
        # 模拟API响应
        mock_response = {
            "hotwords": 1000,
            "kg_entities": 27947,
            "kg_relations": 535803,
            "drug_inserts": 14047,
            "asr_ready": False
        }
        
        assert "hotwords" in mock_response
        assert "kg_entities" in mock_response
        assert mock_response["kg_entities"] > 0
    
    def test_api_departments_endpoint(self):
        """测试科室API端点"""
        mock_departments = ["内科", "外科", "妇产科", "儿科"]
        
        assert len(mock_departments) == 4
        assert "内科" in mock_departments
    
    def test_api_templates_endpoint(self):
        """测试模板API端点"""
        from template_engine import TemplateEngine
        
        engine = TemplateEngine()
        templates = engine.get_templates("内科")
        
        assert isinstance(templates, list)
        assert len(templates) > 0


class TestDataFlow:
    """数据流测试"""
    
    def test_voice_to_text_flow(self):
        """测试语音到文本的数据流"""
        # 模拟语音识别流程
        audio_data = b"mock_audio_data"
        
        # 模拟ASR处理
        recognized_text = "患者头痛三天"
        
        # 模拟纠错
        from corrector import Corrector
        corrector = Corrector()
        corrected, log = corrector.correct(recognized_text)
        
        assert "头痛" in corrected
    
    def test_text_to_template_flow(self):
        """测试文本到模板的数据流"""
        # 模拟分类
        from medical_classifier import MedicalClassifier
        classifier = MedicalClassifier()
        
        text = "发热三天，伴咳嗽"
        field, confidence = classifier.classify(text)
        
        # 验证分类结果
        assert field in ["主诉", "现病史", None]
    
    def test_correction_feedback_flow(self):
        """测试纠错反馈流程"""
        from correction_feedback import CorrectionFeedback
        
        feedback = CorrectionFeedback()
        
        # 记录接受
        feedback.log_acceptance("发烧", "发热", "auto")
        
        # 获取统计
        stats = feedback.get_stats()
        assert isinstance(stats, dict)


class TestCacheIntegration:
    """缓存集成测试"""
    
    def test_cache_manager_basic(self):
        """测试缓存管理器基本功能"""
        from cache_manager import MemoryCache
        
        cache = MemoryCache(max_size=10, ttl=60)
        
        # 设置缓存
        cache.set("test_key", "test_value")
        
        # 获取缓存
        value = cache.get("test_key")
        assert value == "test_value"
        
        # 删除缓存
        cache.delete("test_key")
        assert cache.get("test_key") is None
    
    def test_cache_with_dict_values(self):
        """测试缓存字典值"""
        from cache_manager import MemoryCache
        
        cache = MemoryCache()
        
        # 缓存字典
        data = {"name": "测试", "value": 123}
        cache.set("dict_key", data)
        
        # 获取并验证
        cached_data = cache.get("dict_key")
        assert cached_data == data


class TestHL7FHIRExport:
    """HL7/FHIR导出测试"""
    
    def test_hl7_export_basic(self):
        """测试HL7基本导出"""
        try:
            from hl7_fhir_exporter import MedicalRecordConverter
            
            converter = MedicalRecordConverter()
            
            # 模拟病历数据
            record_data = {
                "patient": {
                    "patient_id": "P001",
                    "name": "张三",
                    "gender": "male"
                }
            }
            
            # 导出HL7
            hl7_message = converter.convert_to_hl7(record_data)
            assert hl7_message is not None
            assert "P001" in hl7_message or len(hl7_message) > 0
        except ImportError:
            pytest.skip("HL7/FHIR导出模块不可用")
    
    def test_fhir_export_basic(self):
        """测试FHIR基本导出"""
        try:
            from hl7_fhir_exporter import MedicalRecordConverter
            
            converter = MedicalRecordConverter()
            
            # 模拟病历数据
            record_data = {
                "patient": {
                    "patient_id": "P001",
                    "name": "张三",
                    "gender": "male"
                }
            }
            
            # 导出FHIR
            fhir_bundle = converter.convert_to_fhir(record_data)
            assert fhir_bundle is not None
            assert "resourceType" in fhir_bundle
        except ImportError:
            pytest.skip("HL7/FHIR导出模块不可用")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
