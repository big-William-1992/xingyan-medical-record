"""
自定义纠错规则引擎
加载 correction_rules.json 中的规则，支持运行时增删改
"""
import json
import os
import re


class RuleEngine:
    """自定义纠错规则管理"""

    def __init__(self, rules_path=None):
        self.rules_path = rules_path or os.path.join(
            os.path.dirname(__file__), "correction_rules.json"
        )
        self.rules = {"错别字": [], "逻辑错误": []}
        self.load_rules()

    def load_rules(self):
        """从文件加载规则"""
        if not os.path.exists(self.rules_path):
            self._create_default_rules()
            return
        try:
            with open(self.rules_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self.rules = data
        except Exception as e:
            print(f"[RuleEngine] 规则加载失败: {e}")

    def _create_default_rules(self):
        """创建默认规则文件"""
        default = {
            "错别字": [
                {"错误": "心电围", "正确": "心电图"},
                {"错误": "白血球", "正确": "白细胞"},
                {"错误": "血相", "正确": "血常规"},
                {"错误": "肝功", "正确": "肝功能"},
                {"错误": "肾功", "正确": "肾功能"},
                {"错误": "拍了CT", "正确": "CT"},
                {"错误": "做CT", "正确": "CT"},
                {"错误": "消炎药", "正确": "抗生素"},
                {"错误": "打点滴", "正确": "静脉输液"},
                {"错误": "拍片", "正确": "影像学检查"}
            ],
            "逻辑错误": [
                {
                    "错误模式": "疾病与药物不匹配",
                    "描述": "诊断了某疾病但用药不属于该疾病的治疗",
                    "示例": {"疾病": "肺炎", "错误用药": "降压药", "正确用药": "抗生素"}
                },
                {
                    "错误模式": "症状与诊断不符",
                    "描述": "描述的症状与最终诊断不匹配",
                    "示例": {"症状": "胸痛", "错误诊断": "胃炎", "建议": "胸痛更常见于心血管疾病"}
                },
                {
                    "错误模式": "检查与诊断不符",
                    "描述": "所做的检查与诊断疾病不匹配",
                    "示例": {"检查": "胸片", "错误诊断": "脑梗死", "建议": "脑梗死应做头颅CT"}
                },
                {
                    "错误模式": "数值单位错误",
                    "描述": "数值与单位组合不符合规范",
                    "示例": {"数值": "38.5", "错误单位": "c", "正确单位": "℃"}
                },
                {
                    "错误模式": "必填项缺失",
                    "描述": "病历缺少必要组成部分",
                    "示例": {"科室": "内科", "缺失项": "现病史"}
                }
            ]
        }
        self.rules = default
        self.save_rules()

    def save_rules(self):
        """保存规则到文件"""
        try:
            with open(self.rules_path, 'w', encoding='utf-8') as f:
                json.dump(self.rules, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[RuleEngine] 规则保存失败: {e}")

    def get_typo_rules(self):
        """获取所有错别字规则"""
        return self.rules.get("错别字", [])

    def get_logic_rules(self):
        """获取所有逻辑错误规则"""
        return self.rules.get("逻辑错误", [])

    def add_typo_rule(self, wrong, correct):
        """添加错别字规则"""
        # 去重
        for rule in self.rules.get("错别字", []):
            if rule["错误"] == wrong:
                rule["正确"] = correct
                self.save_rules()
                return False  # 已存在，更新了
        self.rules.setdefault("错别字", []).append({"错误": wrong, "正确": correct})
        self.save_rules()
        return True  # 新增

    def add_logic_rule(self, pattern_name, description, example=None):
        """添加逻辑错误规则"""
        rule = {"错误模式": pattern_name, "描述": description}
        if example:
            rule["示例"] = example
        self.rules.setdefault("逻辑错误", []).append(rule)
        self.save_rules()
        return True

    def delete_typo_rule(self, wrong):
        """删除错别字规则"""
        rules = self.rules.get("错别字", [])
        self.rules["错别字"] = [r for r in rules if r["错误"] != wrong]
        self.save_rules()

    def delete_logic_rule(self, pattern_name):
        """删除逻辑错误规则"""
        rules = self.rules.get("逻辑错误", [])
        self.rules["逻辑错误"] = [r for r in rules if r["错误模式"] != pattern_name]
        self.save_rules()

    def apply_typo_rules(self, text):
        """应用所有错别字规则，返回 (修正后文本, 纠错日志列表)"""
        log = []
        result = text
        for rule in self.get_typo_rules():
            wrong = rule["错误"]
            correct = rule["正确"]
            if wrong in result:
                result = result.replace(wrong, correct)
                log.append({
                    "type": f"自定义规则: {wrong} → {correct}",
                    "原文": wrong,
                    "修正": correct,
                    "级别": "自动",
                    "分类": "错别字"
                })
        return result, log

    def apply_logic_rules(self, text, knowledge_graph=None):
        """应用逻辑错误规则，返回纠错日志列表"""
        log = []
        text_lower = text.lower()

        for rule in self.get_logic_rules():
            pattern = rule["错误模式"]
            desc = rule["描述"]
            example = rule.get("示例", {})

            if pattern == "疾病与药物不匹配" and knowledge_graph:
                # 检查文本中的疾病和药物是否匹配
                diseases = []
                drugs = []
                for entity_name, info in knowledge_graph.entities.items():
                    if info.get("type") == "疾病" and entity_name in text:
                        diseases.append(entity_name)
                    if info.get("type") == "药物" and entity_name in text:
                        drugs.append(entity_name)
                for disease in diseases:
                    expected = knowledge_graph.get_drugs_for_disease(disease)
                    if expected:
                        # 检查文本中是否有不匹配的药物
                        for drug in drugs:
                            if drug not in expected:
                                log.append({
                                    "type": f"药物不匹配: {disease} 通常不用 {drug}",
                                    "原文": f"{disease} + {drug}",
                                    "修正": f"建议: {', '.join(expected[:3])}",
                                    "级别": "警告",
                                    "分类": "逻辑错误"
                                })

            elif pattern == "症状与诊断不符" and knowledge_graph:
                symptoms = []
                diseases = []
                for entity_name, info in knowledge_graph.entities.items():
                    if info.get("type") == "症状" and entity_name in text:
                        symptoms.append(entity_name)
                    if info.get("type") == "疾病" and entity_name in text:
                        diseases.append(entity_name)
                for symptom in symptoms:
                    related = knowledge_graph.get_diseases_with_symptom(symptom)
                    if related and diseases:
                        for d in diseases:
                            if d not in related:
                                log.append({
                                    "type": f"症状关联提示: {symptom} 更常见于 {', '.join(related[:3])}",
                                    "原文": f"{symptom} → {d}",
                                    "修正": f"请确认诊断",
                                    "级别": "警告",
                                    "分类": "逻辑错误"
                                })

            elif pattern == "检查与诊断不符" and knowledge_graph:
                exams = []
                diseases = []
                for entity_name, info in knowledge_graph.entities.items():
                    if info.get("type") == "检查" and entity_name in text:
                        exams.append(entity_name)
                    if info.get("type") == "疾病" and entity_name in text:
                        diseases.append(entity_name)
                for exam in exams:
                    for s, r, o in knowledge_graph.relations:
                        if r == "HAS_EXAM" and o == exam and s in diseases:
                            break
                    else:
                        if diseases:
                            related_diseases = []
                            for s, r, o in knowledge_graph.relations:
                                if r == "HAS_EXAM" and o == exam:
                                    related_diseases.append(s)
                            if related_diseases:
                                log.append({
                                    "type": f"检查关联提示: {exam} 常用于 {', '.join(related_diseases[:3])}",
                                    "原文": exam,
                                    "修正": f"当前诊断可能不需要此检查",
                                    "级别": "建议",
                                    "分类": "逻辑错误"
                                })

            elif pattern == "数值单位错误":
                # 检查数值+单位组合
                matches = re.findall(r'(\d+\.?\d*)\s*([cCｃ℃])', text)
                for value, unit in matches:
                    if unit in ['c', 'C', 'ｃ'] and unit != '℃':
                        log.append({
                            "type": "单位错误",
                            "原文": f"{value}{unit}",
                            "修正": f"{value}℃",
                            "级别": "自动",
                            "分类": "逻辑错误"
                        })

            elif pattern == "必填项缺失":
                # 由 caller 传入的科室信息处理
                pass

        return log

    def get_stats(self):
        """获取规则统计"""
        return {
            "错别字规则数": len(self.rules.get("错别字", [])),
            "逻辑错误规则数": len(self.rules.get("逻辑错误", []))
        }
