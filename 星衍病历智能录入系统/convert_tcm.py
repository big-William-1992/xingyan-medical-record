#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
中医辨证论治数据库导入工具
============================

数据来源：
1. 《中医内科学》教材（第 9 版）
2. ICD-11 中医病证分类与代码
3. 国家中医药管理局标准
4. 名老中医医案库

输出格式符合知识图谱规范，支持证型→治法→方药→药味的完整链条
"""
import json
from datetime import datetime


class TCMConverter:
    """中医数据转换器"""
    
    def __init__(self):
        self.tcm_data = {}
    
    def load_sample_tcm_data(self):
        """加载样例中医数据"""
        sample_data = {
            "高血压病": {
                "tcm_name": "眩晕/头痛",
                "common_syndromes": [
                    {
                        "syndrome_name": "肝阳上亢",
                        "key_symptoms": ["眩晕耳鸣", "面红目赤", "急躁易怒", "口苦", "舌红苔黄", "脉弦数"],
                        "pattern_characteristics": "本虚标实，肝肾阴虚为本，肝阳上亢为标",
                        "therapeutic_method": "平肝潜阳",
                        "representative_formula": "天麻钩藤饮加减",
                        "formula_composition": [
                            {"herb": "天麻", "dosage": "10g"},
                            {"herb": "钩藤", "dosage": "15g (后下)"},
                            {"herb": "石决明", "dosage": "20g (先煎)"},
                            {"herb": "栀子", "dosage": "10g"},
                            {"herb": "黄芩", "dosage": "10g"},
                            {"herb": "杜仲", "dosage": "12g"},
                            {"herb": "桑寄生", "dosage": "15g"},
                            {"herb": "牛膝", "dosage": "12g"}
                        ],
                        "modification_principles": [
                            {"scenario": "便秘", "add": "大黄、芒硝"},
                            {"scenario": "痰多", "add": "胆南星、竹茹"},
                            {"scenario": "失眠", "add": "夜交藤、珍珠母"}
                        ],
                        "lifestyle_advice": ["忌食辛辣燥热之品", "保持情绪稳定", "避免过度劳累"]
                    },
                    {
                        "syndrome_name": "痰湿中阻",
                        "key_symptoms": ["眩晕头重如蒙", "胸闷恶心", "食少多寐", "舌苔白腻", "脉濡滑"],
                        "pattern_characteristics": "脾失健运，痰湿内生，上蒙清窍",
                        "therapeutic_method": "燥湿化痰",
                        "representative_formula": "半夏白术天麻汤加减",
                        "formula_composition": [
                            {"herb": "半夏", "dosage": "10g"},
                            {"herb": "白术", "dosage": "15g"},
                            {"herb": "天麻", "dosage": "10g"},
                            {"herb": "陈皮", "dosage": "10g"},
                            {"herb": "茯苓", "dosage": "15g"},
                            {"herb": "甘草", "dosage": "6g"},
                            {"herb": "生姜", "dosage": "3 片"},
                            {"herb": "大枣", "dosage": "3 枚"}
                        ],
                        "modification_principles": [
                            {"scenario": "眩晕甚", "add": "僵蚕、磁石"},
                            {"scenario": "呕恶", "add": "代赭石、旋覆花"}
                        ]
                    }
                ]
            },
            "冠心病": {
                "tcm_name": "胸痹/心痛",
                "common_syndromes": [
                    {
                        "syndrome_name": "心血瘀阻",
                        "key_symptoms": ["胸痛如刺", "痛处固定", "入夜尤甚", "舌质紫暗", "脉涩"],
                        "pattern_characteristics": "气滞血瘀，心脉痹阻",
                        "therapeutic_method": "活血化瘀，通脉止痛",
                        "representative_formula": "血府逐瘀汤加减",
                        "formula_composition": [
                            {"herb": "桃仁", "dosage": "10g"},
                            {"herb": "红花", "dosage": "10g"},
                            {"herb": "当归", "dosage": "12g"},
                            {"herb": "生地黄", "dosage": "12g"},
                            {"herb": "川芎", "dosage": "10g"},
                            {"herb": "赤芍", "dosage": "10g"},
                            {"herb": "牛膝", "dosage": "12g"},
                            {"herb": "柴胡", "dosage": "10g"},
                            {"herb": "枳壳", "dosage": "10g"}
                        ]
                    },
                    {
                        "syndrome_name": "气阴两虚",
                        "key_symptoms": ["胸闷隐痛", "心悸气短", "倦怠乏力", "口干盗汗", "舌红少苔", "脉细弱或结代"],
                        "pattern_characteristics": "心气不足，心阴亏虚",
                        "therapeutic_method": "益气养阴",
                        "representative_formula": "生脉散合炙甘草汤加减",
                        "formula_composition": [
                            {"herb": "人参", "dosage": "10g (或党参 15g)"},
                            {"herb": "麦冬", "dosage": "15g"},
                            {"herb": "五味子", "dosage": "6g"},
                            {"herb": "炙甘草", "dosage": "10g"},
                            {"herb": "桂枝", "dosage": "10g"},
                            {"herb": "阿胶", "dosage": "10g (烊化)"},
                            {"herb": "麻仁", "dosage": "15g"}
                        ]
                    }
                ]
            },
            "慢性支气管炎": {
                "tcm_name": "咳嗽/喘证",
                "common_syndromes": [
                    {
                        "syndrome_name": "风寒袭肺",
                        "key_symptoms": ["咳嗽声重", "咳痰稀白", "鼻塞流涕", "恶寒发热", "无汗", "舌苔薄白", "脉浮紧"],
                        "therapeutic_method": "疏风散寒，宣肺止咳",
                        "representative_formula": "三拗汤合止嗽散加减",
                        "formula_composition": [
                            {"herb": "麻黄", "dosage": "6g"},
                            {"herb": "杏仁", "dosage": "10g"},
                            {"herb": "甘草", "dosage": "6g"},
                            {"herb": "桔梗", "dosage": "10g"},
                            {"herb": "荆芥", "dosage": "10g"},
                            {"herb": "紫菀", "dosage": "10g"},
                            {"herb": "百部", "dosage": "10g"},
                            {"herb": "陈皮", "dosage": "10g"}
                        ]
                    },
                    {
                        "syndrome_name": "痰热郁肺",
                        "key_symptoms": ["咳嗽气粗", "痰多黄稠", "胸闷烦热", "口渴欲饮", "舌红苔黄腻", "脉滑数"],
                        "therapeutic_method": "清热化痰，宣肺止咳",
                        "representative_formula": "清金化痰汤加减",
                        "formula_composition": [
                            {"herb": "黄芩", "dosage": "10g"},
                            {"herb": "栀子", "dosage": "10g"},
                            {"herb": "知母", "dosage": "10g"},
                            {"herb": "桑白皮", "dosage": "15g"},
                            {"herb": "瓜蒌仁", "dosage": "15g"},
                            {"herb": "桔梗", "dosage": "10g"},
                            {"herb": "麦冬", "dosage": "12g"},
                            {"herb": "贝母", "dosage": "10g"},
                            {"herb": "橘红", "dosage": "10g"},
                            {"herb": "茯苓", "dosage": "15g"}
                        ]
                    }
                ]
            }
        }
        
        self.tcm_data["tcm_diseases"] = sample_data
        print(f"✅ 已加载 {len(sample_data)} 种疾病的中医辨证数据")
        return True
    
    def save_to_json(self, output_path="kg_data/tcm_data.json"):
        """保存为标准 JSON 格式"""
        output = {
            "source": "TCM Internal Medicine Textbook + ICD-11 TCM",
            "export_time": datetime.now().isoformat(),
            **self.tcm_data
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        
        print(f"✅ 已保存至：{output_path}")
        return True
    
    def convert_to_knowledge_graph_format(self):
        """转换为知识图谱三元组格式"""
        kg_relations = []
        entity_types = {}
        
        for disease, info in self.tcm_data.get("tcm_diseases", {}).items():
            # 注册中医病名实体
            entity_types[disease] = "中医病名"
            
            for syndrome_info in info.get("common_syndromes", []):
                syndrome_name = syndrome_info["syndrome_name"]
                
                # 关系 1: 中医病名 HAS_SYNDROME 证型
                kg_relations.append((disease, "HAS_SYNDROME", syndrome_name))
                entity_types[syndrome_name] = "证型"
                
                # 关系 2: 证型 INDICATES_SYMPTOMS 症状
                for symptom in syndrome_info.get("key_symptoms", []):
                    kg_relations.append((syndrome_name, "INDICATES_SYMPTOM", symptom))
                    entity_types[symptom] = "症状"
                
                # 关系 3: 证型 HAS_TREATMENT 治法
                if syndrome_info.get("therapeutic_method"):
                    kg_relations.append((syndrome_name, "HAS_THERAPEUTIC_METHOD", 
                                        syndrome_info["therapeutic_method"]))
                
                # 关系 4: 证型 HAS_FORMULA 代表方
                if syndrome_info.get("representative_formula"):
                    kg_relations.append((syndrome_name, "HAS_REPRESENTATIVE_FORMULA",
                                        syndrome_info["representative_formula"]))
                    
                    # 关系 5: 方剂 CONTAINS_HERB 中药
                    for herb_info in syndrome_info.get("formula_composition", []):
                        herb_name = herb_info["herb"]
                        kg_relations.append((syndrome_info["representative_formula"],
                                            "CONTAINS_HERB", herb_name))
                        entity_types[herb_name] = "中药"
        
        return {
            "relations": kg_relations,
            "entity_types": entity_types
        }


def main():
    import argparse
    parser = argparse.ArgumentParser(description="中医辨证论治数据库导入工具")
    parser.add_argument("--sample", action="store_true", help="使用样例数据")
    parser.add_argument("--format", choices=["json", "kg"], default="json",
                       help="输出格式：JSON / 知识图谱三元组")
    args = parser.parse_args()
    
    converter = TCMConverter()
    if args.sample:
        converter.load_sample_tcm_data()
        
        if args.format == "json":
            converter.save_to_json()
        else:
            kg_format = converter.convert_to_knowledge_graph_format()
            with open("kg_data/tcm_relations.json", 'w', encoding='utf-8') as f:
                json.dump(kg_format, f, ensure_ascii=False, indent=2)
            print("✅ 已保存知识图谱三元组到：kg_data/tcm_relations.json")
    else:
        print("💡 提示：目前仅支持样例数据模式")


if __name__ == "__main__":
    main()
