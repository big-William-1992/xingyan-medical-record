#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
放射科术语数据库导入工具
===========================

数据来源：
1. Radiopaedia (中文) - 放射影像案例库
2. CheXpert/NIH Chest X-Ray - AI 标注数据中的诊断术语
3. RSNA RadLex - 放射学术语标准体系
4. Fetzer Report - 结构化报告模板

注意：本模块仅收录放射科诊断术语和影像表现描述，不生成完整放射科报告模板。
"""
import json
from datetime import datetime


class RadiologyTermsConverter:
    """放射科术语转换器"""
    
    def __init__(self):
        self.terms = {
            "CT_征象": [],
            "MRI_信号": [],
            "Xray_表现": [],
            "超声_术语": [],
            "影像诊断_常用语": []
        }
    
    def load_sample_terms(self):
        """加载样例放射科术语"""
        
        # CT 征象（从 Radiopaedia 及临床实践整理）
        ct_signs = [
            {
                "term": "毛刺征",
                "description": "肺结节边缘呈不规则突起，类似毛刺状",
                "clinical_significance": "高度提示周围型肺癌可能",
                "sensitivity": "约 70-80%",
                "specificity": "高，尤其是短毛刺 (<5mm)",
                "differentiation": "需与炎性假瘤、结核球鉴别"
            },
            {
                "term": "分叶征",
                "description": "肺结节轮廓呈波浪状凸起，形似花瓣",
                "clinical_significance": "见于多数周围型肺癌及部分良性病变",
                "sensitivity": "约 60-70%",
                "specificity": "中等"
            },
            {
                "term": "胸膜凹陷征",
                "description": "肿瘤牵拉邻近胸膜形成线样阴影向结节集中",
                "clinical_significance": "常见于腺癌，也可见于部分良性病变",
                "mechanism": "肿瘤内纤维组织收缩或促纤维增生反应"
            },
            {
                "term": "支气管充气征",
                "description": "实变肺组织中可见含气的支气管影",
                "clinical_significance": "见于肺炎、肺癌、肺泡蛋白沉积症等",
                "key_point": "管壁光滑规则多为炎性；破坏中断考虑恶性"
            },
            {
                "term": "血管集束征",
                "description": "多支血管向病灶集中并进入其中",
                "clinical_significance": "高度怀疑恶性肿块",
                "characteristics": "血管增粗、扭曲、截断"
            },
            {
                "term": "空气支气管征",
                "description": "肺实变区域内可见透亮支气管影",
                "clinical_significance": "典型见于大叶性肺炎",
                "differential": "肺癌也可出现但较少见"
            }
        ]
        
        # MRI 信号描述
        mri_signals = [
            {
                "term": "T1 低信号",
                "description": "在 T1WI 序列上低于正常脑组织的灰度值",
                "common_causes": ["水肿", "囊肿", "梗死急性期", "脱髓鞘"],
                "tissue_characteristics": "通常提示水分增加或脂肪减少"
            },
            {
                "term": "T2 高信号",
                "description": "在 T2WI 序列上高于正常组织的亮白色影",
                "common_causes": ["水肿", "炎症", "肿瘤", "梗死亚急性期"],
                "tissue_characteristics": "提示含水量增高"
            },
            {
                "term": "DWI 受限",
                "description": "弥散加权成像上呈现高信号，ADC 值降低",
                "significance": "细胞毒性水肿表现",
                "diagnostic_value": "急性脑梗死（发病数分钟内即阳性）",
                "differential": "癫痫持续状态、脑脓肿、高级别胶质瘤"
            },
            {
                "term": "环形强化",
                "description": "增强扫描病灶中央低密度，周边环状高密度影",
                "differential_diagnosis": [
                    {"condition": "脑脓肿", "features": "环形薄而均匀，DWI 高信号"},
                    {"condition": "胶质母细胞瘤", "features": "厚薄不均，内壁不光整"},
                    {"condition": "转移瘤", "features": "多发，环形强化明显"}
                ]
            }
        ]
        
        # X 光常用表现
        xray_findings = [
            {
                "term": "骨质疏松",
                "description": "骨密度普遍降低，骨小梁稀疏变细",
                "radiographic_signs": ["椎体双凹变形", "骨皮质变薄", "椎间隙相对增宽"],
                "clinical_correlation": "易发压缩性骨折"
            },
            {
                "term": "骨赘形成",
                "description": "骨质增生性突起，多见于关节边缘",
                "location": "颈椎、腰椎最常见",
                "significance": "退行性变的标志之一"
            },
            {
                "term": "关节间隙变窄",
                "description": "关节两侧骨端之间的透亮间隙小于正常范围",
                "causes": ["软骨磨损", "半月板损伤", "类风湿关节炎"],
                "measurement": "正常膝关节间隙约 3-5mm"
            },
            {
                "term": "胸腔积液",
                "description": "肋膈角变钝或消失，外高内低的弧形致密影",
                "volume_estimation": "侧位胸片肋膈角变钝提示积液≥200ml",
                "distribution": ["少量：肋膈角变钝", "中量：致密影至肺门下部", "大量：整个胸腔致密"]
            },
            {
                "term": "心影增大",
                "description": "心胸比率 (>0.5)",
                "types": [{
                    "type": "普大型", 
                    "differential": ["全心扩大", "心包积液"]
                }, {
                    "type": "靴形心", 
                    "differential": ["左心室扩大", "肺动脉高压"]
                }, {
                    "type": "梨形心", 
                    "differential": ["右心室扩大", "二尖瓣病变"]
                }]
            }
        ]
        
        # 超声常用术语
        ultrasound_terms = [
            {
                "term": "无回声区",
                "description": "超声显示完全黑色区域",
                "meaning": "液体结构，如囊肿、胆道、血管",
                "posterior_enhancement": true,
                "examples": ["肝囊肿", "肾囊肿", "胆囊"]
            },
            {
                "term": "强回声伴声影",
                "description": "明亮高回声后方伴有黑色声影",
                "meaning": "高密度物质，反射+ 吸收声波",
                "examples": ["胆囊结石", "肾结石", "骨皮质"]
            },
            {
                "term": "血流信号丰富",
                "description": "彩色多普勒显示丰富血流信号",
                "significance": "提示血供丰富的占位（恶性肿瘤可能性大）",
                "differential": "需结合形态学特征综合判断"
            }
        ]
        
        # 影像诊断常用结论用语
        diagnostic_phrases = [
            {
                "phrase": "符合...表现",
                "usage": "影像学改变与某种疾病典型表现一致",
                "example": "两肺下叶斑片状高密度影，符合社区获得性肺炎表现"
            },
            {
                "phrase": "待排/可疑",
                "usage": "有异常发现但证据不足，建议进一步检查",
                "example": "左肺上叶小结节，性质待定，建议随访或增强 CT 检查"
            },
            {
                "phrase": "建议结合临床",
                "usage": "影像学不能确诊，需要结合症状体征和其他检查",
                "example": "肝脏稍低密度灶，建议结合肿瘤标志物及增强检查进一步明确"
            },
            {
                "phrase": "定期随访",
                "usage": "发现异常但不紧急，需要观察变化趋势",
                "example": "甲状腺微小结节，建议 6-12 个月后复查超声"
            },
            {
                "phrase": "建议进一步检查",
                "usage": "当前检查不足以明确诊断",
                "example": "消化道出血待查，胃镜未见明显出血点，建议结肠镜检查"
            }
        ]
        
        # 整合到术语字典
        self.terms["CT_征象"] = ct_signs
        self.terms["MRI_信号"] = mri_signals
        self.terms["Xray_表现"] = xray_findings
        self.terms["超声_术语"] = ultrasound_terms
        self.terms["影像诊断_常用语"] = diagnostic_phrases
        
        total_terms = sum(len(v) for v in self.terms.values())
        print(f"✅ 已加载 {total_terms} 条放射科术语")
        return True
    
    def save_to_json(self, output_path="kg_data/radiology_terms.json"):
        """保存为标准 JSON 格式"""
        output = {
            "source": "Radiopaedia + CheXpert + RSNA RadLex",
            "export_time": datetime.now().isoformat(),
            **self.terms
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        
        print(f"✅ 已保存至：{output_path}")
        return True
    
    def convert_to_kg_format(self):
        """转换为知识图谱格式（术语→关联疾病/症状）"""
        kg_relations = []
        entity_types = {}
        
        # CT 征象 → 疾病
        for sign in self.terms.get("CT_征象", []):
            term = sign["term"]
            entity_types[term] = "放射征象"
            
            # 根据临床意义建立关联
            if "肺癌" in sign.get("clinical_significance", ""):
                kg_relations.append((term, "SUGGESTS_DISEASE", "肺癌"))
            
            if "肺炎" in sign.get("clinical_significance", ""):
                kg_relations.append((term, "SUGGESTS_DISEASE", "社区获得性肺炎"))
            
            # 征象 → 相关症状
            if "呼吸困难" in sign.get("clinical_significance", ""):
                kg_relations.append((term, "ASSOCIATED_SYMPTOM", "呼吸困难"))
        
        # MRI 信号 → 病变类型
        for signal in self.terms.get("MRI_信号", []):
            term = signal["term"]
            entity_types[term] = "MRI 信号特征"
            
            if "脑梗死" in str(signal):
                kg_relations.append((term, "SUGGESTS_PATHOLOGY", "急性脑梗死"))
            
            if "脑脓肿" in str(signal):
                kg_relations.append((term, "DIFFERENTIAL_DIAGNOSIS", "脑脓肿"))
        
        # 诊断用语 → 临床场景
        for phrase in self.terms.get("影像诊断_常用语", []):
            term = phrase["phrase"]
            entity_types[term] = "诊断结论用语"
            
            if "待排" in term or "可疑" in term:
                kg_relations.append((term, "REQUIRES_FOLLOWUP", "yes"))
            
            if "定期随访" in term:
                kg_relations.append((term, "FOLLOWUP_REQUIRED", "yes"))
        
        return {
            "relations": kg_relations,
            "entity_types": entity_types,
            "terminology_catalogue": list(self.terms.keys())
        }


def main():
    import argparse
    parser = argparse.ArgumentParser(description="放射科术语数据库导入工具")
    parser.add_argument("--sample", action="store_true", help="使用样例数据")
    parser.add_argument("--format", choices=["json", "kg"], default="json",
                       help="输出格式：JSON / 知识图谱三元组")
    args = parser.parse_args()
    
    converter = RadiologyTermsConverter()
    if args.sample:
        converter.load_sample_terms()
        
        if args.format == "json":
            converter.save_to_json()
        else:
            kg_format = converter.convert_to_kg_format()
            with open("kg_data/radiology_kg_relations.json", 'w', encoding='utf-8') as f:
                json.dump(kg_format, f, ensure_ascii=False, indent=2)
            print("✅ 已保存知识图谱三元组到：kg_data/radiology_kg_relations.json")
    else:
        print("💡 提示：目前仅支持样例数据模式")


if __name__ == "__main__":
    main()
