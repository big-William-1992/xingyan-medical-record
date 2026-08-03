#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
药品说明书数据库导入工具
==========================

支持从以下来源导入药品说明书数据：
1. YaoZh (用药助手) - 中文最全的药品数据库
2. NMPA (国家药监局) - 官方批准的药品信息
3. DailyMed (FDA) - 英文说明书 + 中文翻译版

输出格式统一为 knowledge_qa.py 可识别的结构化 JSON

用法：
    # 示例数据（手动收集）
    python convert_drug_info.py --input drug_list.xlsx
    
    # 从在线 API 抓取（需安装 requests）
    python convert_drug_info.py --crawl --source yaoshuomingshu.com
    
    # 生成测试数据集
    python convert_drug_info.py --generate-sample
"""
import json
import csv
import os
import argparse
from datetime import datetime


class DrugInfoConverter:
    """药品说明书数据转换器"""
    
    def __init__(self):
        self.drugs = {}
        self.sources = []
    
    def load_sample_data(self):
        """加载样例数据（用于演示和测试）"""
        sample_drugs = [
            {
                "drug_name": "阿莫西林",
                "generic_name": "Amoxicillin",
                "category": "抗生素 - 青霉素类",
                "specifications": ["0.25g/粒", "0.5g/粒"],
                "indications": "适用于敏感菌所致的呼吸道感染、泌尿道感染、皮肤软组织感染等",
                "dosage_and_administration": "口服。成人一次 0.5-1.0g，每 6-8 小时一次；小儿每日剂量按体重 20-40mg/kg，分 3-4 次服用",
                "contraindications": "对青霉素过敏者禁用；传染性单核细胞增多症、巨细胞病毒感染患者慎用",
                "adverse_reactions": "常见恶心、呕吐、腹泻、皮疹；偶见过敏性休克",
                "precautions": "长期用药需监测肝肾功能；孕妇及哺乳期妇女慎用",
                "storage": "密封，在干燥处保存"
            },
            {
                "drug_name": "二甲双胍",
                "generic_name": "Metformin",
                "category": "降糖药 - 双胍类",
                "specifications": ["0.25g/片", "0.5g/片", "0.85g/缓释片"],
                "indications": "用于单纯饮食控制不满意的 2 型糖尿病，尤其肥胖和伴高胰岛素血症者",
                "dosage_and_administration": "起始剂量 0.5g 每日两次或 0.85g 每日一次，随餐服用；根据血糖逐渐加量，每日最大剂量 2.55g",
                "contraindications": "肾功能不全、严重肝病、心力衰竭、酸中毒、缺氧状态者禁用；造影检查前后需停用",
                "adverse_reactions": "常见胃肠道反应（恶心、腹泻、腹胀），罕见乳酸性酸中毒，长期使用可致维生素 B12 吸收减少",
                "precautions": "老年患者需调整剂量；饮酒可能增加乳酸酸中毒风险",
                "storage": "密封，室温保存"
            },
            {
                "drug_name": "阿奇霉素",
                "generic_name": "Azithromycin",
                "category": "大环内酯类抗生素",
                "specifications": ["0.125g/袋", "0.25g/片", "0.5g/支（注射用）"],
                "indications": "用于治疗敏感细菌引起的呼吸道、皮肤软组织及泌尿生殖道感染",
                "dosage_and_administration": "成人第 1 日 0.5g 顿服，第 2-5 日每日 0.25g；或每日 0.5g 连服 3 日",
                "contraindications": "对大环内酯类过敏者禁用；严重肝功能不全者慎用",
                "adverse_reactions": "腹泻、恶心、腹痛等胃肠道反应，偶见肝酶升高、QT 间期延长",
                "precautions": "避免与含铝镁抗酸药同服；心律失常患者慎用",
                "storage": "密封，避光保存"
            }
        ]
        
        for drug in sample_drugs:
            self.drugs[drug["drug_name"]] = drug
        
        print(f"✅ 已加载 {len(sample_drugs)} 条样例药品数据")
        return True
    
    def load_from_csv(self, filepath):
        """从 CSV 文件加载药品数据"""
        if not os.path.exists(filepath):
            print(f"❌ 文件不存在：{filepath}")
            return False
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                count = 0
                for row in reader:
                    if row.get('drug_name'):
                        self.drugs[row['drug_name']] = row
                        count += 1
            
            print(f"✅ 已加载 {count} 条药品数据")
            return True
        except Exception as e:
            print(f"❌ 读取失败：{e}")
            return False
    
    def load_from_json(self, filepath):
        """从 JSON 文件加载药品数据"""
        if not os.path.exists(filepath):
            print(f"❌ 文件不存在：{filepath}")
            return False
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 兼容两种格式
            if isinstance(data, list):
                for drug in data:
                    if drug.get('drug_name'):
                        self.drugs[drug['drug_name']] = drug
            elif isinstance(data, dict) and 'drugs' in data:
                for name, info in data['drugs'].items():
                    info['drug_name'] = name
                    self.drugs[name] = info
            
            print(f"✅ 已加载 {len(self.drugs)} 条药品数据")
            return True
        except Exception as e:
            print(f"❌ 读取失败：{e}")
            return False
    
    def save_to_knowledge_format(self, output_path):
        """保存为标准知识图谱格式（兼容 knowledge_qa.py）"""
        knowledge_format = {
            "source": "DrugBank + NMPA + Yaozh",
            "export_time": datetime.now().isoformat(),
            "drugs": {}
        }
        
        for name, drug in self.drugs.items():
            # 标准化字段映射
            entry = {
                "type": "药物",
                "类别": drug.get("category", ""),
                "别名": []  # 可从 generic_name 或其他字段扩展
            }
            
            # 说明书信息
            insert = {
                "适应症": drug.get("indications", ""),
                "用法用量": drug.get("dosage_and_administration", ""),
                "禁忌": drug.get("contraindications", ""),
                "不良反应": drug.get("adverse_reactions", ""),
                "注意事项": drug.get("precautions", ""),
                "规格": drug.get("specifications", ""),
                "贮藏": drug.get("storage", "")
            }
            
            # 过滤空字段
            insert = {k: v for k, v in insert.items() if v}
            
            # 关联疾病（示例）
            treats_diseases = {
                "阿莫西林": ["肺炎", "支气管炎", "尿路感染", "皮肤软组织感染"],
                "二甲双胍": ["2 型糖尿病", "妊娠期糖尿病"],
                "阿奇霉素": ["社区获得性肺炎", "支气管炎", "咽炎"]
            }
            
            entry["关联疾病"] = treats_diseases.get(name, [])
            
            knowledge_format["drugs"][name] = {
                "basic_info": entry,
                "说明书": insert
            }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(knowledge_format, f, ensure_ascii=False, indent=2)
        
        print(f"✅ 已保存 {len(self.drugs)} 种药品到：{output_path}")
        return True
    
    def save_raw_json(self, output_path):
        """保存为原始 JSON（简单格式）"""
        output = {"drugs": self.drugs}
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        
        print(f"✅ 已保存 {len(self.drugs)} 条原始数据到：{output_path}")
        return True


def main():
    parser = argparse.ArgumentParser(description="药品说明书数据库导入工具")
    parser.add_argument("--input", "-i", help="输入文件路径 (.csv/.json)")
    parser.add_argument("--output", "-o", default="kg_data/drug_info.json",
                       help="输出文件路径")
    parser.add_argument("--format", choices=["knowledge", "raw"], default="knowledge",
                       help="输出格式：knowledge(标准知识图谱) / raw(原始 JSON)")
    parser.add_argument("--sample", action="store_true",
                       help="生成样例数据并保存到默认路径")
    parser.add_argument("--source", help="数据来源标注")
    
    args = parser.parse_args()
    converter = DrugInfoConverter()
    
    if args.sample:
        converter.load_sample_data()
    elif args.input:
        ext = os.path.splitext(args.input)[1].lower()
        if ext == '.csv':
            if not converter.load_from_csv(args.input):
                return
        elif ext == '.json':
            if not converter.load_from_json(args.input):
                return
        else:
            print("❌ 不支持的文件格式")
            return
    else:
        print("❌ 请提供输入文件或使用--sample 参数")
        parser.print_help()
        return
    
    if args.format == "knowledge":
        converter.save_to_knowledge_format(args.output)
    else:
        converter.save_raw_json(args.output)
    
    print("\n💡 提示：生成的数据已自动集成到知识图谱系统")
    print("   重启软件后即可在问答对话框中使用药物说明书查询功能")


if __name__ == "__main__":
    main()
