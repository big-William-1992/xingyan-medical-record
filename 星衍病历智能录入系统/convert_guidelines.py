#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
临床诊疗指南数据导入工具
===========================

支持从以下来源导入诊疗指南：
1. 中华医学会系列期刊指南
2. 国家卫健委诊疗规范
3. UpToDate 中文摘要（需授权）
4. 各科专家共识

输出格式统一为结构化 JSON，支持按证据等级分类
"""
import json
import os
from datetime import datetime


class GuidelineConverter:
    """诊疗指南转换器"""
    
    def __init__(self):
        self.guidelines = []
    
    def load_sample_guidelines(self):
        """加载样例指南数据"""
        sample_guidelines = [
            {
                "disease": "社区获得性肺炎",
                "source": "中华医学会呼吸病学分会 2016",
                "version": "CSP 2016",
                "evidence_level": "A",
                "first_line_treatment": {
                    "description": "一线治疗方案（证据等级 A/B）",
                    "antibiotics": ["阿莫西林", "阿莫西林 - 克拉维酸钾", "头孢曲松", "左氧氟沙星"],
                    "duration": "5-7 天",
                    "route": "口服或静脉滴注"
                },
                "second_line_treatment": {
                    "description": "二线治疗方案（证据等级 B/C）",
                    "antibiotics": ["阿奇霉素", "多西环素", "莫西沙星"],
                    "indication": "对青霉素过敏或一线治疗失败"
                },
                "supportive_care": [
                    "保持呼吸道通畅",
                    "吸氧维持 SpO2 ≥ 90%",
                    "充分补液",
                    "营养支持"
                ],
                "monitoring": [
                    "体温、呼吸频率、心率",
                    "血氧饱和度",
                    "白细胞计数、CRP、PCT",
                    "胸片复查（48-72 小时）"
                ],
                "discharge_criteria": [
                    "体温正常 48 小时以上",
                    "呼吸平稳，不需要吸氧",
                    "能进食药物",
                    "血流动力学稳定"
                ]
            },
            {
                "disease": "高血压病",
                "source": "中国高血压防治指南 2018",
                "version": "修订版",
                "evidence_level": "A",
                "diagnostic_criteria": "诊室血压≥140/90mmHg，或居家血压≥135/85mmHg",
                "treatment_goals": {
                    "general_patients": "<140/90mmHg",
                    "diabetes": "<130/80mmHg",
                    "elderly": "<150/90mmHg (≥65 岁)",
                    "complicated": "<130/80mmHg (合并心脑肾病)"
                },
                "first_line_drugs": [
                    {
                        "name": "钙通道阻滞剂 (CCB)",
                        "examples": ["氨氯地平", "硝苯地平控释片", "非洛地平缓释片"],
                        "suitable_for": ["老年高血压", "单纯收缩期高血压"]
                    },
                    {
                        "name": "血管紧张素转换酶抑制剂 (ACEI)",
                        "examples": ["培哚普利", "贝那普利", "依那普利"],
                        "suitable_for": ["糖尿病", "慢性肾病", "心力衰竭"]
                    },
                    {
                        "name": "血管紧张素Ⅱ受体拮抗剂 (ARB)",
                        "examples": ["缬沙坦", "厄贝沙坦", "替米沙坦"],
                        "suitable_for": ["不能耐受 ACEI 咳嗽患者"]
                    }
                ],
                "lifestyle_interventions": [
                    "限制钠盐摄入 (<5g/天)",
                    "减轻体重 (BMI <24)",
                    "适量运动 (每周≥150 分钟)",
                    "戒烟限酒",
                    "心理平衡"
                ]
            },
            {
                "disease": "2 型糖尿病",
                "source": "中国 2 型糖尿病防治指南 2020",
                "version": "最新版",
                "evidence_level": "A",
                "diagnostic_criteria": "空腹血糖≥7.0mmol/L，或 OGTT2hPG≥11.1mmol/L，或 HbA1c≥6.5%",
                "treatment_hierarchy": {
                    "first_line": {
                        "drug": "二甲双胍",
                        "target_HbA1c": "<7.0%",
                        "contraindications": ["eGFR<45ml/min", "严重肝病", "缺氧状态"]
                    },
                    "add_on_therapy": [
                        {"drug": "SGLT2 抑制剂", "benefit": ["降糖", "减重", "心血管保护"]},
                        {"drug": "DPP-4 抑制剂", "benefit": ["低血糖风险低", "中性体重"]},
                        {"drug": "胰岛素促泌剂", "benefit": ["降糖效果强", "价格低廉"]}
                    ]
                },
                "complications_screening": [
                    {"item": "眼底检查", "frequency": "每年 1 次"},
                    {"item": "尿白蛋白/肌酐比值", "frequency": "每年至少 1 次"},
                    {"item": "足部检查", "frequency": "每次就诊"},
                    {"item": "血脂检测", "frequency": "每年 1 次"}
                ]
            }
        ]
        
        self.guidelines = sample_guidelines
        print(f"✅ 已加载 {len(sample_guidelines)} 条指南数据")
        return True
    
    def save_to_json(self, output_path="kg_data/guidelines.json"):
        """保存为标准 JSON 格式"""
        output = {
            "source": "Clinical Guidelines Database",
            "export_time": datetime.now().isoformat(),
            "guidelines": self.guidelines
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        
        print(f"✅ 已保存至：{output_path}")
        return True
    
    def integrate_with_knowledge_graph(self, kg_format_output="kg_data/guidelines_kg.json"):
        """转换为知识图谱格式，与现有 KG 数据融合"""
        kg_format = {}
        
        for guideline in self.guidelines:
            disease = guideline["disease"]
            kg_format[disease] = {
                "指南来源": guideline.get("source", ""),
                "证据等级": guideline.get("evidence_level", ""),
                "诊断标准": guideline.get("diagnostic_criteria", ""),
                "治疗方案": {
                    "一线方案": guideline.get("first_line_treatment", guideline.get("first_line_drugs", "")),
                    "二线方案": guideline.get("second_line_treatment", ""),
                    "辅助治疗": guideline.get("supportive_care", [])
                },
                "随访监测": guideline.get("monitoring", guideline.get("complications_screening", [])),
                "治愈标准": guideline.get("discharge_criteria", [])
            }
        
        with open(kg_format_output, 'w', encoding='utf-8') as f:
            json.dump({"guidelines": kg_format}, f, ensure_ascii=False, indent=2)
        
        print(f"✅ 已保存知识图谱格式至：{kg_format_output}")
        return True


def main():
    import argparse
    parser = argparse.ArgumentParser(description="临床诊疗指南导入工具")
    parser.add_argument("--sample", action="store_true", help="使用样例数据")
    parser.add_argument("--format", choices=["json", "kg"], default="json",
                       help="输出格式：JSON / 知识图谱格式")
    args = parser.parse_args()
    
    converter = GuidelineConverter()
    if args.sample:
        converter.load_sample_guidelines()
        
        if args.format == "json":
            converter.save_to_json()
        else:
            converter.integrate_with_knowledge_graph()
    else:
        print("💡 提示：目前仅支持样例数据模式，如需添加真实指南数据请联系管理员")


if __name__ == "__main__":
    main()
