#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI 辅助诊断增强模块
提供智能诊断建议、鉴别诊断、治疗方案推荐等功能
"""
import json
from typing import List, Dict, Optional
from knowledge_graph import MedicalKnowledgeGraph


class AIDiagnosisAssistant:
    """AI 辅助诊断助手"""
    
    def __init__(self, kg: Optional[MedicalKnowledgeGraph] = None):
        self.kg = kg or MedicalKnowledgeGraph()
    
    def analyze_symptoms(self, symptoms: List[str]) -> Dict:
        """
        症状分析与诊断建议
        
        Args:
            symptoms: 症状列表，如 ["发热", "咳嗽", "头痛"]
        
        Returns:
            诊断建议字典
        """
        if not symptoms:
            return {"error": "未提供症状"}
        
        # 查找可能的疾病
        possible_diseases = []
        disease_scores = {}
        
        for symptom in symptoms:
            # 从知识图谱查找关联疾病
            diseases = self.kg.get_diseases_with_symptom(symptom)
            for disease in diseases:
                if disease not in disease_scores:
                    disease_scores[disease] = 0
                disease_scores[disease] += 1
        
        # 按匹配度排序
        sorted_diseases = sorted(disease_scores.items(), key=lambda x: x[1], reverse=True)
        
        for disease, score in sorted_diseases[:10]:
            disease_info = self.kg.entities.get(disease, {})
            possible_diseases.append({
                "name": disease,
                "match_score": score,
                "match_ratio": score / len(symptoms),
                "system": disease_info.get("系统", "未知"),
                "common_symptoms": disease_info.get("常见症状", [])[:5]
            })
        
        return {
            "input_symptoms": symptoms,
            "possible_diseases": possible_diseases,
            "recommendation": self._generate_recommendation(possible_diseases)
        }
    
    def suggest_differential_diagnosis(self, primary_diagnosis: str) -> List[Dict]:
        """
        鉴别诊断建议
        
        Args:
            primary_diagnosis: 主要诊断
        
        Returns:
            鉴别诊断列表
        """
        # 获取主要诊断的症状
        primary_info = self.kg.entities.get(primary_diagnosis, {})
        primary_symptoms = set(primary_info.get("常见症状", []))
        
        if not primary_symptoms:
            return []
        
        # 查找有相似症状的其他疾病
        differential_diagnoses = []
        
        for disease_name, disease_info in self.kg.entities.items():
            if disease_name == primary_diagnosis:
                continue
            
            if disease_info.get("type") != "疾病":
                continue
            
            disease_symptoms = set(disease_info.get("常见症状", []))
            overlap = primary_symptoms & disease_symptoms
            
            if len(overlap) >= 2:  # 至少2个共同症状
                similarity = len(overlap) / len(primary_symptoms | disease_symptoms)
                differential_diagnoses.append({
                    "name": disease_name,
                    "similarity": similarity,
                    "common_symptoms": list(overlap),
                    "distinguishing_features": list(disease_symptoms - primary_symptoms)[:3]
                })
        
        # 按相似度排序
        differential_diagnoses.sort(key=lambda x: x["similarity"], reverse=True)
        
        return differential_diagnoses[:5]
    
    def recommend_treatment(self, diagnosis: str) -> Dict:
        """
        治疗方案推荐
        
        Args:
            diagnosis: 诊断名称
        
        Returns:
            治疗方案字典
        """
        disease_info = self.kg.entities.get(diagnosis, {})
        
        if not disease_info:
            return {"error": f"未找到诊断: {diagnosis}"}
        
        # 获取常用药物
        drugs = self.kg.get_drugs_for_disease(diagnosis)
        drug_details = []
        
        for drug_name in drugs[:5]:
            drug_info = self.kg.drug_inserts.get(drug_name, {})
            drug_details.append({
                "name": drug_name,
                "indication": drug_info.get("适应症", ""),
                "dosage": drug_info.get("用法用量", ""),
                "contraindication": drug_info.get("禁忌", "")
            })
        
        # 获取中医治疗方案
        syndromes = self.kg.get_syndromes_for_disease(diagnosis)
        tcm_treatment = []
        
        for syndrome in syndromes[:3]:
            treatment = self.kg.get_treatment_for_syndrome(syndrome)
            tcm_treatment.append({
                "syndrome": syndrome,
                "treatment": treatment.get("治法", ""),
                "formula": treatment.get("代表方", "")
            })
        
        return {
            "diagnosis": diagnosis,
            "western_medicine": {
                "drugs": drug_details,
                "treatment_principles": disease_info.get("治疗方式", [])
            },
            "tcm": {
                "syndromes": tcm_treatment
            },
            "recommendations": self._generate_treatment_recommendations(diagnosis, disease_info)
        }
    
    def predict_severity(self, symptoms: List[str]) -> Dict:
        """
        病情严重程度预测
        
        Args:
            symptoms: 症状列表
        
        Returns:
            严重程度评估
        """
        # 危险症状列表
        critical_symptoms = [
            "意识不清", "呼吸困难", "胸痛", "剧烈头痛",
            "大量出血", "昏迷", "休克", "心跳骤停"
        ]
        
        # 统计危险症状
        critical_count = sum(1 for s in symptoms if s in critical_symptoms)
        
        if critical_count >= 2:
            severity = "危重"
            urgency = "立即就医"
        elif critical_count == 1:
            severity = "严重"
            urgency = "尽快就医"
        elif len(symptoms) >= 5:
            severity = "中等"
            urgency = "建议就医"
        else:
            severity = "轻微"
            urgency = "可观察"
        
        return {
            "severity": severity,
            "urgency": urgency,
            "critical_symptoms": [s for s in symptoms if s in critical_symptoms],
            "total_symptoms": len(symptoms),
            "recommendation": self._generate_severity_recommendation(severity, symptoms)
        }
    
    def _generate_recommendation(self, possible_diseases: List[Dict]) -> str:
        """生成诊断建议"""
        if not possible_diseases:
            return "未找到匹配的疾病，建议进一步检查"
        
        top_disease = possible_diseases[0]
        confidence = top_disease["match_ratio"]
        
        if confidence >= 0.8:
            return f"高度怀疑 {top_disease['name']}，建议立即就医确诊"
        elif confidence >= 0.5:
            return f"可能为 {top_disease['name']}，建议就医检查"
        else:
            return "症状不典型，建议详细检查"
    
    def _generate_treatment_recommendations(self, diagnosis: str, disease_info: Dict) -> List[str]:
        """生成治疗建议"""
        recommendations = []
        
        # 基础建议
        recommendations.append("请遵医嘱用药")
        recommendations.append("注意休息，保持良好作息")
        
        # 根据疾病类型添加特定建议
        system = disease_info.get("系统", "")
        
        if system == "呼吸":
            recommendations.append("保持室内空气流通")
            recommendations.append("避免吸烟和二手烟")
        elif system == "心血管":
            recommendations.append("低盐低脂饮食")
            recommendations.append("适量运动，避免剧烈运动")
        elif system == "消化":
            recommendations.append("清淡饮食，避免辛辣刺激")
            recommendations.append("规律进餐，细嚼慢咽")
        
        recommendations.append("定期复查，监测病情变化")
        
        return recommendations
    
    def _generate_severity_recommendation(self, severity: str, symptoms: List[str]) -> str:
        """生成严重程度建议"""
        if severity == "危重":
            return "⚠️ 病情危重，请立即拨打120或前往急诊！"
        elif severity == "严重":
            return "⚠️ 病情较重，建议尽快就医，不要延误！"
        elif severity == "中等":
            return "建议尽快就医，进行详细检查"
        else:
            return "症状较轻，可先观察，如加重请就医"


# 便捷函数
def create_diagnosis_assistant(kg=None):
    """创建诊断助手实例"""
    return AIDiagnosisAssistant(kg)


if __name__ == "__main__":
    # 测试
    assistant = AIDiagnosisAssistant()
    
    print("=== 症状分析测试 ===")
    symptoms = ["发热", "咳嗽", "咳痰"]
    result = assistant.analyze_symptoms(symptoms)
    print(f"输入症状: {symptoms}")
    print(f"可能疾病: {result['possible_diseases'][:3]}")
    print(f"建议: {result['recommendation']}")
    
    print("\n=== 鉴别诊断测试 ===")
    primary = "肺炎"
    differentials = assistant.suggest_differential_diagnosis(primary)
    print(f"主要诊断: {primary}")
    print(f"鉴别诊断: {differentials[:3]}")
    
    print("\n=== 治疗方案推荐测试 ===")
    diagnosis = "高血压"
    treatment = assistant.recommend_treatment(diagnosis)
    print(f"诊断: {diagnosis}")
    print(f"西药: {treatment['western_medicine']['drugs'][:2]}")
    print(f"建议: {treatment['recommendations']}")
    
    print("\n=== 严重程度预测测试 ===")
    symptoms = ["发热", "咳嗽", "呼吸困难", "胸痛"]
    severity = assistant.predict_severity(symptoms)
    print(f"症状: {symptoms}")
    print(f"严重程度: {severity['severity']}")
    print(f"紧急程度: {severity['urgency']}")
    print(f"建议: {severity['recommendation']}")
