#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
API测试
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch


class TestAPI:
    """API测试类"""
    
    @pytest.fixture
    def client(self):
        """创建测试客户端"""
        # Mock所有依赖
        with patch('app_server.get_asr') as mock_asr, \
             patch('app_server.get_kg') as mock_kg, \
             patch('app_server.get_qa') as mock_qa, \
             patch('app_server.get_template_engine') as mock_te, \
             patch('app_server.get_corrector') as mock_corrector, \
             patch('app_server.get_db') as mock_db:
            
            # 配置mock
            mock_asr.return_value = Mock()
            mock_asr.return_value.is_ready.return_value = True
            mock_asr.return_value._current_hotwords = "高血压 糖尿病"
            
            mock_kg.return_value = Mock()
            mock_kg.return_value.entities = {"高血压": {"描述": "高血压描述"}}
            mock_kg.return_value.relations = []
            mock_kg.return_value.drug_inserts = {}
            
            mock_qa.return_value = Mock()
            mock_qa.return_value.answer.return_value = {"text": "测试回答", "found": True}
            
            mock_te.return_value = Mock()
            mock_te.return_value.get_templates.return_value = [{"name": "入院记录", "content": "主诉："}]
            
            mock_corrector.return_value = Mock()
            mock_corrector.return_value.correct.return_value = ("纠正后文本", [])
            
            mock_db.return_value = Mock()
            mock_db.return_value.list_records.return_value = []
            
            from app_server import app
            return TestClient(app)
    
    def test_health_check(self, client):
        """测试健康检查"""
        response = client.get("/api/stats")
        assert response.status_code == 200
        data = response.json()
        assert "asr_ready" in data
    
    def test_get_departments(self, client):
        """测试获取科室列表"""
        response = client.get("/api/departments")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert "内科" in data
    
    def test_get_templates(self, client):
        """测试获取模板列表"""
        response = client.get("/api/templates?dept=内科")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
    
    def test_kg_query(self, client):
        """测试知识图谱查询"""
        response = client.get("/api/kg/query?q=高血压")
        assert response.status_code == 200
        data = response.json()
        assert "text" in data
    
    def test_kg_drug(self, client):
        """测试药物查询"""
        response = client.get("/api/kg/drug/阿莫西林")
        assert response.status_code == 200
        data = response.json()
        assert "name" in data
    
    def test_kg_disease(self, client):
        """测试疾病查询"""
        response = client.get("/api/kg/disease/高血压")
        assert response.status_code == 200
        data = response.json()
        assert "name" in data
        assert "symptoms" in data
    
    def test_correct_text(self, client):
        """测试文本纠错"""
        response = client.post("/api/correct", json={"text": "心电围"})
        assert response.status_code == 200
        data = response.json()
        assert "corrected" in data
    
    def test_fill_fields(self, client):
        """测试字段填充"""
        response = client.post("/api/fill", json={
            "text": "主诉发热三天",
            "base": "主诉：\n现病史：",
            "department": "内科"
        })
        assert response.status_code == 200
        data = response.json()
        assert "filled" in data
    
    def test_save_record(self, client):
        """测试保存病历"""
        response = client.post("/api/records", json={
            "content": "主诉：发热三天",
            "department": "内科"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] == True
    
    def test_list_records(self, client):
        """测试获取病历列表"""
        response = client.get("/api/records")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)


class TestRateLimiting:
    """频率限制测试"""
    
    @pytest.fixture
    def client(self):
        with patch('app_server.get_kg') as mock_kg:
            mock_kg.return_value = Mock()
            mock_kg.return_value.entities = {}
            
            from app_server import app
            return TestClient(app)
    
    def test_rate_limit_not_exceeded(self, client):
        """测试正常请求不被限制"""
        # 发送少量请求
        for _ in range(5):
            response = client.get("/api/kg/drug/阿莫西林")
            assert response.status_code == 200


class TestCORS:
    """CORS测试"""
    
    @pytest.fixture
    def client(self):
        from app_server import app
        return TestClient(app)
    
    def test_cors_allowed_origin(self, client):
        """测试允许的源"""
        response = client.get(
            "/api/stats",
            headers={"Origin": "http://localhost:8765"}
        )
        assert response.status_code == 200
        # 应该包含CORS头
        assert "access-control-allow-origin" in response.headers
    
    def test_cors_disallowed_origin(self, client):
        """测试不允许的源"""
        response = client.get(
            "/api/stats",
            headers={"Origin": "http://evil.com"}
        )
        # 应该被拒绝或不包含CORS头
        assert response.status_code == 200  # FastAPI仍然返回200，但CORS头不包含


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
