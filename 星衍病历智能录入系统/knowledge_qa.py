#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
知识库问答引擎（基于医学知识图谱，纯离线）

把自然语言问题（如"慢性支气管炎的常见治疗方案"）解析为
「疾病实体 + 提问意图」，检索知识图谱后生成结构化中文回答。

支持的提问意图：
    治疗 / 方案 / 用药 → 治疗方案（药物 + 治疗方式 + 中医治法方药）
    症状 / 表现 / 临床 → 常见症状
    检查 / 化验 / 诊断 → 建议检查
    药物 / 用药 / 吃什么药 → 常用药物（附说明书）
    说明书 / 用法 / 禁忌 → 药物说明书
    中医 / 辨证 / 证型 → 中医证型与治法
    饮食 / 忌口 / 吃什么 → 饮食宜忌（宜吃/忌吃/食谱）
    鉴别 / 区分 → 鉴别要点（症状组合）
    概述 / 是什么 / 介绍 → 疾病概述
未指明意图时，返回综合概览。

所有回答仅供参考，以医师判断为准。
"""
import re
from difflib import get_close_matches

from knowledge_graph import MedicalKnowledgeGraph


DISCLAIMER = "以上内容由知识图谱检索生成，仅供参考，以医师判断为准。"

# 意图关键词 → 意图标识（按优先级从前到后匹配）
INTENT_KEYWORDS = [
    ("治疗", ["治疗", "方案", "怎么办", "如何治", "怎样治", "怎么治", "处理", "疗法"]),
    ("用药", ["用药", "吃什么药", "用什么药", "开什么药", "药物", "处方", "服药"]),
    ("说明书", ["说明书", "用法用量", "禁忌", "不良反应", "副作用", "适应症"]),
    ("饮食", ["饮食", "忌口", "吃什么", "不能吃什么", "宜吃", "忌吃", "食物", "食疗", "膳食"]),
    ("检查", ["检查", "化验", "做什么检查", "辅助检查", "检测", "筛查"]),
    ("症状", ["症状", "表现", "临床表现", "什么症状", "征兆", "迹象"]),
    ("中医", ["中医", "辨证", "证型", "方剂", "中药", "治法"]),
    ("鉴别", ["鉴别", "区分", "区别", "如何判断", "怎么判断"]),
    ("概述", ["是什么", "什么是", "介绍", "概述", "简介", "定义", "病因", "原因"]),
]

# 常见检查项目词表（图谱检查实体较少，补充高频临床检查）
COMMON_EXAMS = [
    "心电图", "动态心电图", "胸部CT", "头颅CT", "腹部CT", "泌尿系CT",
    "头颅MRI", "腰椎MRI", "膝关节MRI", "胸片", "腹部平片",
    "心脏彩超", "颈部血管彩超", "腹部B超", "泌尿系B超", "甲状腺彩超",
    "血常规", "尿常规", "便常规", "肝功能", "肾功能", "血脂", "血糖",
    "电解质", "凝血功能", "血气分析", "心肌酶", "肌钙蛋白", "BNP",
    "糖化血红蛋白", "甲功五项", "肿瘀标志物", "胃镜", "肠镜",
    "肺功能检查", "骨密度检查", "病理检查", "超声", "B超", "彩超", "CT", "MRI", "X线",
]

# ═══ 法律法规问答（医师法 / 执业医师法 / 医疗事故处理条例 / 医疗纠纷预防和处理条例 / 刑法医疗条款）═══
# 法律名关键词 → 知识库 law key（按优先级从前到后）
# 注意："执业医师法"包含"医师法"子串，匹配时需长词优先
LAW_NAME_KEYWORDS = [
    ("医疗事故案例", ["医疗事故案例", "案例解读", "经典案例", "判例", "案例分享",
                    "案例", "李建雪", "韩杰", "付克荣"]),
    ("医疗事故处理条例", ["医疗事故处理条例", "医疗事故处理", "医疗事故鉴定",
                       "医疗事故技术鉴定", "医疗事故赔偿"]),
    ("医疗纠纷预防和处理条例", ["医疗纠纷预防和处理条例", "医疗纠纷处理条例", "医疗纠纷预防",
                          "医疗纠纷处理", "医疗纠纷", "医疗损害鉴定",
                          "人民调解", "行政调解"]),
    ("执业医师法", ["执业医师法", "执业医师资格法"]),
    ("医师法", ["医师法"]),
    ("刑法医疗条款", ["刑法", "刑事处罚", "刑责"]),
]

# 罪名/医疗犯罪关键词 → 直接定位刑法条文
LAW_CRIME_KEYWORDS = [
    "非法行医", "医疗事故罪", "医疗事故", "组织出卖人体器官", "人体器官",
    "虐待被监护", "非法组织卖血", "强迫卖血", "卖血", "非法采集血液",
    "供应血液", "血液制品", "非法采集人类遗传资源", "遗传资源",
    "基因编辑", "克隆胚胎", "节育复通", "终止妊娠手术", "节育手术",
    "宫内节育器", "拒不救治", "伤病军人", "毁坏尸体", "盗窃、侮辱",
    "尸体", "骨灰", "犯罪",
]

# 法律主题词（用于条文全文检索，命中问题中的词即作为检索条件）
LAW_TOPIC_WORDS = [
    # 执业医师法主题
    "考试", "资格", "注册", "执业", "变更", "注销", "个体行医", "乡村医生",
    "军队", "境外", "职称", "医师协会", "权利", "义务", "诊查", "医学文书",
    "证明文件", "急危", "急救", "药品", "麻醉药品", "精神药品", "放射性药品",
    "毒性药品", "病情", "临床医疗", "财物", "调遣", "传染病", "疫情",
    "伤害事件", "非正常死亡", "助理", "考核", "培训", "继续医学教育",
    "表彰", "奖励", "吊销", "警告", "暂停", "罚款", "赔偿", "行政处分",
    "隐私", "尊重", "人道主义",
    # 医师法新增主题
    "保障", "津贴", "薪酬", "规范化培训", "规培", "多点执业", "互联网",
    "远程医疗", "医联体", "医师节", "义诊", "知情同意", "伦理", "临床试验",
    "不良反应", "假药", "劣药", "处方", "用药", "工伤保险", "带薪休假",
    "医疗责任保险", "医患", "纠纷", "治安管理",
    # 医疗事故/医疗纠纷主题
    "鉴定", "尸检", "封存", "启封", "病历", "复印", "复制", "专家库",
    "人民调解", "调解", "协商", "和解", "诉讼", "投诉", "医疗损害",
    "事故分级", "赔偿", "精神损害抚慰金", "误工费",
    # 案例解读主题
    "判例", "案情", "警示", "启示", "教训", "过错", "因果关系",
    "鉴定结论", "判决", "责任程度", "遗留", "异物", "纱布", "漏诊",
    "宫外孕", "李建雪", "韩杰", "付克荣",
    # 刑法量刑主题
    "有期徒刑", "拘役", "管制", "罚金", "没收", "刑事责任", "处罚",
]

# 医疗纠纷/鉴定语境词：无法律名时优先定位《医疗纠纷预防和处理条例》
LAW_DISPUTE_WORDS = ["纠纷", "鉴定", "调解", "协商", "诉讼", "尸检",
                     "封存", "病历", "投诉", "赔偿"]

# 医疗法律语境词：无法律名时，命中这些词+主题词才触发法律问答
LAW_CONTEXT_WORDS = ["医师", "行医", "法条", "法律", "依法", "罪", "处罚", "刑事责任",
                     "纠纷", "鉴定", "调解", "协商", "诉讼", "尸检", "封存",
                     "病历", "投诉"]

# 中文数字转换表
_CN_DIGITS = {"零": 0, "一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
              "六": 6, "七": 7, "八": 8, "九": 9}
_CN_UNITS = {"十": 10, "百": 100, "千": 1000}


def _cn_num_to_int(s):
    """中文数字 → 整数（支持 一~九千九百九十九）"""
    total, section = 0, 0
    for ch in s:
        if ch in _CN_DIGITS:
            section = section * 10 + _CN_DIGITS[ch]
        elif ch in _CN_UNITS:
            if section == 0:
                section = 1
            total += section * _CN_UNITS[ch]
            section = 0
    return total + section


def _int_to_cn(n):
    """整数 → 中文数字（如 335 → 三百三十五）"""
    digits = "零一二三四五六七八九"
    units = ["", "十", "百", "千"]
    if n == 0:
        return "零"
    if n < 10:
        return digits[n]
    s = str(n)
    length = len(s)
    parts, zero_flag = [], False
    for i, ch in enumerate(s):
        d = int(ch)
        pos = length - i - 1
        if d == 0:
            zero_flag = True
        else:
            if zero_flag:
                parts.append("零")
                zero_flag = False
            parts.append(digits[d])
            if pos > 0:
                parts.append(units[pos])
    result = "".join(parts)
    if result.startswith("一十"):
        result = result[1:]
    return result


class KnowledgeQA:
    def __init__(self, kg=None):
        self.kg = kg or MedicalKnowledgeGraph()
        self._diseases = self.kg.get_all_diseases()
        # 按长度降序，优先匹配更长的标准病名
        self._diseases_by_len = sorted(self._diseases, key=len, reverse=True)
        # 药物词表（用于"XX的说明书"类问题）
        self._drugs = [n for n, t in self.kg.entity_types.items() if t == "药物"]
        self._drugs_by_len = sorted(self._drugs, key=len, reverse=True)
        # 症状 / 检查词表（用于二级索引）
        self._symptoms = [n for n, t in self.kg.entity_types.items() if t == "症状"]
        self._symptoms_by_len = sorted(self._symptoms, key=len, reverse=True)
        self._exams = [n for n, t in self.kg.entity_types.items() if t == "检查"]
        self._exams_by_len = sorted(self._exams, key=len, reverse=True)
        # 药品说明书词表（1万+条，按长度降序用于病历文本扫描）
        self._drug_inserts_by_len = sorted(
            (n for n in self.kg.drug_inserts.keys() if n and len(n.strip()) >= 2),
            key=len, reverse=True
        )
        # 检查词表：图谱检查实体 + 常见临床检查，按长度降序
        self._exam_terms_by_len = sorted(
            set(self._exams) | set(COMMON_EXAMS), key=len, reverse=True
        )
        # 法律知识库（执业医师法 / 刑法医疗条款）
        self.laws = getattr(self.kg, "laws", {}) or {}
        self._law_keys = list(self.laws.keys())

    # ─── 实体识别 ───────────────────────────────────────
    def find_disease(self, question):
        """从问题中识别疾病实体，返回标准病名或 None"""
        q = question.strip()
        # 1. 精确命中
        if q in self.kg.entities and self.kg.entity_types.get(q) == "疾病":
            return q
        # 2. 别名归一
        alias = self.kg.normalize(q)
        if alias != q and self.kg.entity_types.get(alias) == "疾病":
            return alias
        # 3. 问题中包含标准病名（取最长匹配）
        for d in self._diseases_by_len:
            if d in q:
                return d
        # 4. 问题中包含别名
        for alias_name, std in self.kg.aliases.items():
            if alias_name and alias_name in q:
                if self.kg.entity_types.get(std) == "疾病":
                    return std
        # 5. 模糊匹配兜底
        matches = get_close_matches(q, self._diseases, n=1, cutoff=0.6)
        if matches:
            return matches[0]
        return None

    def find_drug(self, question):
        """从问题中识别药物实体（用于说明书查询）"""
        q = question.strip()
        for d in self._drugs_by_len:
            if d in q:
                return d
        alias = self.kg.normalize(q)
        if alias in self.kg.drug_inserts:
            return alias
        return None

    def find_diseases(self, question, max_n=4):
        """识别问题中出现的多个疾病实体（用于对比类问题），保序去重"""
        q = question.strip()
        found = []
        # 先按标准病名最长匹配，命中后从问句中剔除避免重叠
        rest = q
        for d in self._diseases_by_len:
            if d in rest:
                if d not in found:
                    found.append(d)
                rest = rest.replace(d, " ")
        # 再补别名
        for alias_name, std in self.kg.aliases.items():
            if alias_name and alias_name in q and std not in found:
                if self.kg.entity_types.get(std) == "疾病":
                    found.append(std)
        return found[:max_n]

    # ─── 病历文本实体抽取（问答面板提示用） ─────────────────────

    def extract_diseases(self, text, max_n=5):
        """从病历文本中抽取疾病实体（最长优先，命中后剔除避免重叠）"""
        if not text:
            return []
        found, rest = [], text
        for d in self._diseases_by_len:
            if len(d) < 2:  # 单字病名噪声大，跳过
                continue
            if d in rest:
                if d not in found:
                    found.append(d)
                rest = rest.replace(d, ' ')
                if len(found) >= max_n:
                    break
        return found

    def extract_drugs(self, text, max_n=8):
        """从病历文本中抽取药品名（优先药品说明书库，其次图谱药物实体）"""
        if not text:
            return []
        found, rest = [], text
        for d in self._drug_inserts_by_len:
            if d in rest:
                if d not in found:
                    found.append(d)
                rest = rest.replace(d, ' ')
                if len(found) >= max_n:
                    break
        if len(found) < max_n:
            for d in self._drugs_by_len:
                if len(d) >= 2 and d in rest and d not in found:
                    found.append(d)
                    rest = rest.replace(d, ' ')
                    if len(found) >= max_n:
                        break
        return found

    def extract_exams(self, text, max_n=8):
        """从病历文本中抽取检查项目（图谱检查实体 + 常见检查词表）"""
        if not text:
            return []
        found, rest = [], text
        for d in self._exam_terms_by_len:
            if d in rest:
                if d not in found:
                    found.append(d)
                rest = rest.replace(d, ' ')
                if len(found) >= max_n:
                    break
        return found

    def detect_intent(self, question):
        """识别提问意图，返回意图标识"""
        for intent, keywords in INTENT_KEYWORDS:
            for kw in keywords:
                if kw in question:
                    return intent
        return "综合"

    # ─── 答案生成 ───────────────────────────────────────
    def answer(self, question):
        """
        回答一个自然语言问题。
        返回 {found, disease, intent, text, suggestions}
        """
        question = (question or "").strip()
        if not question:
            return {"found": False, "text": "请输入问题，例如：慢性支气管炎的常见治疗方案",
                    "suggestions": []}

        # 法律类问题优先（执业医师法 / 刑法医疗条款）
        law_result = self._answer_law(question)
        if law_result:
            return law_result

        # 药物说明书类问题优先
        drug = self.find_drug(question)
        intent = self.detect_intent(question)
        if intent == "说明书" and drug:
            return self._answer_drug(drug)

        # 对比类问题：识别到多个疾病且意图为鉴别/对比
        if intent == "鉴别":
            multi = self.find_diseases(question)
            if len(multi) >= 2:
                return self._answer_comparison(multi)

        disease = self.find_disease(question)
        if not disease:
            return self._answer_not_found(question)

        handler = {
            "治疗": self._answer_treatment,
            "用药": self._answer_drugs,
            "检查": self._answer_exams,
            "症状": self._answer_symptoms,
            "中医": self._answer_tcm,
            "饮食": self._answer_diet,
            "鉴别": self._answer_differential,
            "概述": self._answer_overview,
        }.get(intent, self._answer_overview_all)

        return handler(disease, intent)

    # ─── 各类回答 ───────────────────────────────────────
    def _drug_brief(self, drug_name):
        """生成药物一句话解释（适应症摘要）"""
        ins = self.kg.get_drug_info(drug_name)
        if not ins:
            return ""
        indication = ins.get("适应症", "")
        if indication:
            # 截取前60字作为摘要
            brief = indication.replace("\n", " ").strip()
            return brief[:60] + ("..." if len(brief) > 60 else "")
        return ""
    
    def _exam_brief(self, exam_name):
        """生成检查一句话解释（关联疾病数）"""
        related = self.kg.query_by_obj(exam_name, "HAS_EXAM")[:5]
        if related:
            return "相关疾病：%s等" % "、".join(related[:3])
        return ""
    
    def _symptom_brief(self, symptom_name):
        """生成症状一句话解释（可能指向的疾病）"""
        diseases = self.kg.query_by_subj(symptom_name, "INDICATES")[:5]
        if not diseases:
            diseases = self.kg.query_by_obj(symptom_name, "HAS_SYMPTOM")[:5]
        if diseases:
            return "可见于：%s等" % "、".join(diseases[:3])
        return ""
    
    def _answer_treatment(self, disease, intent="治疗"):
        info = self.kg.entities.get(disease, {})
        drugs = self.kg.get_drugs_for_disease(disease)
        cure_way = info.get("治疗方式", [])
        lines = ["🩺 【%s】治疗方案" % disease, ""]
        if cure_way:
            lines.append("▪ 治疗方式：%s" % "、".join(cure_way))
        if drugs:
            lines.append("▪ 常用药物：")
            for i, d in enumerate(drugs[:8], 1):
                brief = self._drug_brief(d)
                lines.append("   %d. %s" % (i, d))
                if brief:
                    lines.append("      └ %s" % brief)
        # 中医治法方药
        syndromes = self.kg.get_syndromes_for_disease(disease)
        if syndromes:
            lines.append("▪ 中医辨证：%s" % "、".join(syndromes))
            tr = self.kg.get_treatment_for_syndrome(syndromes[0])
            if tr.get("治法"):
                lines.append("   - 治法：%s 代表方：%s" % (
                    tr["治法"], tr.get("代表方", "")))
        cv = self.kg.get_critical_value(disease)
        if cv:
            lines.append("⚠ 危急值提示：%s" % cv)
        if len(lines) == 2:
            lines.append("（知识库暂无该病的专项治疗数据）")
        lines.extend(["", "⚕ " + DISCLAIMER])
        return {"found": True, "disease": disease, "intent": intent,
                "text": "\n".join(lines), "suggestions": self._related(disease)}

    def _answer_drugs(self, disease, intent="用药"):
        drugs = self.kg.get_drugs_for_disease(disease)
        lines = ["💊 【%s】常用药物" % disease, ""]
        if drugs:
            for i, d in enumerate(drugs, 1):
                cat = self.kg.entities.get(d, {}).get("类别", "")
                suffix = "（%s）" % cat if cat else ""
                lines.append("%d. %s%s" % (i, d, suffix))
                brief = self._drug_brief(d)
                if brief:
                    lines.append("   └ %s" % brief)
        else:
            lines.append("（知识库暂无该病的用药记录）")
        lines.extend(["", "⚕ " + DISCLAIMER])
        return {"found": True, "disease": disease, "intent": intent,
                "text": "\n".join(lines), "suggestions": self._related(disease)}

    def _answer_exams(self, disease, intent="检查"):
        exams = self.kg.get_exams_for_disease(disease)
        lines = ["🔬 【%s】建议检查" % disease, ""]
        if exams:
            for i, e in enumerate(exams, 1):
                lines.append("%d. %s" % (i, e))
                brief = self._exam_brief(e)
                if brief:
                    lines.append("   └ %s" % brief)
        else:
            lines.append("（知识库暂无该病的检查记录）")
        lines.extend(["", "⚕ " + DISCLAIMER])
        return {"found": True, "disease": disease, "intent": intent,
                "text": "\n".join(lines), "suggestions": self._related(disease)}

    def _answer_symptoms(self, disease, intent="症状"):
        symptoms = self.kg.get_symptoms_for_disease(disease)
        lines = ["📋 【%s】常见症状" % disease, ""]
        if symptoms:
            for i, s in enumerate(symptoms, 1):
                lines.append("%d. %s" % (i, s))
                brief = self._symptom_brief(s)
                if brief:
                    lines.append("   └ %s" % brief)
        else:
            lines.append("（知识库暂无该病的症状记录）")
        lines.extend(["", "⚕ " + DISCLAIMER])
        return {"found": True, "disease": disease, "intent": intent,
                "text": "\n".join(lines), "suggestions": self._related(disease)}

    def _answer_tcm(self, disease, intent="中医"):
        syndromes = self.kg.get_syndromes_for_disease(disease)
        lines = ["🌿 【%s】中医辨证" % disease, ""]
        if syndromes:
            for syn in syndromes:
                tr = self.kg.get_treatment_for_syndrome(syn)
                lines.append("▪ %s" % syn)
                if tr.get("治法"):
                    lines.append("   治法：%s　代表方：%s" % (
                        tr["治法"], tr.get("代表方", "")))
                if tr.get("组成"):
                    lines.append("   组成：%s" % "、".join(tr["组成"]))
        else:
            lines.append("（知识库暂无该病的中医证型记录）")
        lines.extend(["", "⚕ " + DISCLAIMER])
        return {"found": True, "disease": disease, "intent": intent,
                "text": "\n".join(lines), "suggestions": self._related(disease)}

    def _answer_differential(self, disease, intent="鉴别"):
        symptoms = self.kg.get_symptoms_for_disease(disease)
        exams = self.kg.get_exams_for_disease(disease)
        lines = ["🔍 【%s】鉴别要点" % disease, ""]
        if symptoms:
            lines.append("▪ 典型症状：%s" % "、".join(symptoms[:8]))
        if exams:
            lines.append("▪ 关键检查：%s" % "、".join(exams[:6]))
        cv = self.kg.get_critical_value(disease)
        if cv:
            lines.append("⚠ 危急值：%s" % cv)
        lines.extend(["", "⚕ " + DISCLAIMER])
        return {"found": True, "disease": disease, "intent": intent,
                "text": "\n".join(lines), "suggestions": self._related(disease)}

    def _answer_diet(self, disease, intent="饮食"):
        """饮食宜忌回答"""
        diet = self.kg.get_diet_for_disease(disease)
        lines = ["🍽️ 【%s】饮食宜忌" % disease, ""]
        if diet:
            if diet.get("宜吃"):
                lines.append("✅ 宜吃：%s" % "、".join(diet["宜吃"]))
            if diet.get("忌吃"):
                lines.append("❌ 忌吃：%s" % "、".join(diet["忌吃"]))
            if diet.get("推荐食谱"):
                lines.append("📋 推荐食谱：%s" % "、".join(diet["推荐食谱"]))
        else:
            lines.append("（知识库暂无该病的饮食宜忌数据，可导入 DiseaseKG 补充）")
        lines.extend(["", "⚕ " + DISCLAIMER])
        return {"found": True, "disease": disease, "intent": intent,
                "text": "\n".join(lines), "suggestions": self._related(disease)}

    def _answer_comparison(self, diseases):
        """多疾病对比回答：并列列出各病的症状/检查/用药供鉴别"""
        lines = ["🔍 【%s】鉴别对比" % " vs ".join(diseases), ""]
        for d in diseases:
            symptoms = self.kg.get_symptoms_for_disease(d)
            exams = self.kg.get_exams_for_disease(d)
            drugs = self.kg.get_drugs_for_disease(d)
            lines.append("◆ %s" % d)
            if symptoms:
                lines.append("   症状：%s" % "、".join(symptoms[:6]))
            if exams:
                lines.append("   检查：%s" % "、".join(exams[:5]))
            if drugs:
                lines.append("   用药：%s" % "、".join(drugs[:5]))
            lines.append("")
        lines.append("⚕ " + DISCLAIMER)
        return {"found": True, "disease": diseases[0], "intent": "鉴别",
                "text": "\n".join(lines),
                "suggestions": ["%s的治疗方案" % diseases[0]]}

    def _answer_overview(self, disease, intent="概述"):
        info = self.kg.entities.get(disease, {})
        lines = ["📖 【%s】概述" % disease, ""]
        if info.get("描述"):
            lines.append(info["描述"])
        if info.get("系统"):
            lines.append("▪ 所属科室/系统：%s" % info["系统"])
        symptoms = self.kg.get_symptoms_for_disease(disease)
        if symptoms:
            lines.append("▪ 常见症状：%s" % "、".join(symptoms[:8]))
        lines.extend(["", "⚕ " + DISCLAIMER])
        return {"found": True, "disease": disease, "intent": intent,
                "text": "\n".join(lines), "suggestions": self._related(disease)}

    def _answer_overview_all(self, disease, intent="综合"):
        """综合概览：概述 + 症状 + 检查 + 治疗"""
        info = self.kg.entities.get(disease, {})
        drugs = self.kg.get_drugs_for_disease(disease)
        symptoms = self.kg.get_symptoms_for_disease(disease)
        exams = self.kg.get_exams_for_disease(disease)
        lines = ["📚 【%s】综合参考" % disease, ""]
        if info.get("描述"):
            lines.append(info["描述"][:120] + ("…" if len(info.get("描述", "")) > 120 else ""))
            lines.append("")
        if symptoms:
            lines.append("▪ 常见症状：%s" % "、".join(symptoms[:8]))
        if exams:
            lines.append("▪ 建议检查：%s" % "、".join(exams[:6]))
        if drugs:
            lines.append("▪ 常用药物：%s" % "、".join(drugs[:8]))
        if info.get("治疗方式"):
            lines.append("▪ 治疗方式：%s" % "、".join(info["治疗方式"]))
        # 饮食宜忌
        diet = self.kg.get_diet_for_disease(disease)
        if diet:
            if diet.get("宜吃"):
                lines.append("✅ 宜吃：%s" % "、".join(diet["宜吃"][:6]))
            if diet.get("忌吃"):
                lines.append("❌ 忌吃：%s" % "、".join(diet["忌吃"][:6]))
        cv = self.kg.get_critical_value(disease)
        if cv:
            lines.append("⚠ 危急值：%s" % cv)
        lines.extend(["", "💡 可追问：治疗方案 / 用药 / 检查 / 症状 / 中医辨证 / 饮食宜忌"])
        lines.append("⚕ " + DISCLAIMER)
        return {"found": True, "disease": disease, "intent": intent,
                "text": "\n".join(lines), "suggestions": self._related(disease)}

    # ─── 法律法规问答（执业医师法 / 刑法医疗条款）─────────────────

    def _extract_article_no(self, question):
        """提取条文号，返回统一中文格式（如“第三百三十五条”）或 None"""
        m = re.search(r'第\s*([0-9]+|[零一二三四五六七八九十百千]+)\s*条', question)
        if not m:
            return None
        num_str = m.group(1)
        if num_str.isdigit():
            return "第" + _int_to_cn(int(num_str)) + "条"
        return "第" + num_str + "条"

    def _law_topics(self, question):
        """提取问题中的法律主题词（去重保序）"""
        topics = []
        for w in LAW_TOPIC_WORDS:
            if w in question and w not in topics:
                topics.append(w)
        return topics

    def _search_law_articles(self, keys, topics):
        """在指定法律（或全库）的条文中按主题词命中检索，返回 Top5。
        标题/条号命中权重更高，同分按条文数字升序。"""
        results = []
        for k in keys or self._law_keys:
            for art in self.laws[k].get("articles_index", []):
                title_no = art["title"] + art["no"]
                title_hits = sum(1 for t in topics if t in title_no)
                content_hits = sum(1 for t in topics if t in art["content"])
                score = title_hits * 3 + content_hits
                if score:
                    results.append((score, art))
        results.sort(key=lambda x: (-x[0], self._article_no_num(x[1]["no"])))
        return [a for _, a in results[:5]]

    @staticmethod
    def _article_no_num(no):
        """条文号 → 数字（如“第三百三十五条”→335），用于排序"""
        m = re.search(r'第([零一二三四五六七八九十百千]+)条', no)
        return _cn_num_to_int(m.group(1)) if m else 0

    def _answer_law_article(self, art):
        """单条法律条文回答"""
        lines = ["⚖ 【%s】" % art["no"], ""]
        lines.append("《%s》" % art["full_name"])
        lines.append(art["chapter"])
        title = art["title"]
        if title:
            lines.append("▪ %s" % title)
        lines.append(art["content"])
        lines.extend(["", "⚕ 条文文本供参考，以国家正式公布的法律文本为准。"])
        return {"found": True, "disease": None, "intent": "法律",
                "text": "\n".join(lines), "suggestions": self._law_suggestions(art)}  

    def _answer_law_search(self, hits, question):
        """主题检索命中多条条文时，逐条列出"""
        lines = ["⚖ 相关法律条文检索结果", ""]
        for art in hits:
            lines.append("《%s》%s（%s）" % (art["full_name"], art["no"], art["title"]))
            lines.append(art["content"])
            lines.append("")
        lines.append("⚕ 条文文本供参考，以国家正式公布的法律文本为准。")
        return {"found": True, "disease": None, "intent": "法律",
                "text": "\n".join(lines), "suggestions": self._law_suggestions(hits[0])}

    def _answer_law_overview(self, key):
        """法律概览：名称、状态、简介、章节目录"""
        info = self.laws[key]
        lines = ["⚖ 《%s》" % info.get("full_name", key), ""]
        status = info.get("status", "")
        if status:
            lines.append("▪ 效力状态：%s" % status)
        if info.get("promulgated"):
            lines.append("▪ 通过日期：%s" % info["promulgated"])
        if info.get("amended"):
            lines.append("▪ 最近修正：%s" % info["amended"])
        if info.get("effective"):
            lines.append("▪ 施行日期：%s" % info["effective"])
        if info.get("note"):
            lines.append("▪ 说明：%s" % info["note"])
        if info.get("summary"):
            lines.extend(["", "📖 简介"])
            lines.append(info["summary"])
        lines.extend(["", "📑 章节目录"])
        for ch in info.get("chapters", []):
            n = len(ch.get("articles", []))
            lines.append("  • %s（%d条）" % (ch.get("title", ""), n))
        lines.extend(["", "💡 可追问：如%s"])
        lines[-1] = lines[-1] % {
            "医师法": "\"医师法第九条\"、\"医师的权利\"",
            "执业医师法": "\"执业医师法第九条\"、\"医师的执业规则\"",
            "医疗事故案例": "\"医疗事故的经典案例\"、\"手术遗留异物的案例\"",
            "医疗事故处理条例": "\"什么是医疗事故\"、\"医疗事故怎么鉴定\"",
            "医疗纠纷预防和处理条例": "\"医疗纠纷怎么解决\"、\"医疗纠纷人民调解\"",
            "刑法医疗条款": "\"医疗事故罪怎么判\"",
        }.get(key, "\"医疗事故罪怎么判\"")
        lines.append("⚕ 条文文本供参考，以国家正式公布的法律文本为准。")
        return {"found": True, "disease": None, "intent": "法律", "law": key,
                "text": "\n".join(lines),
                "suggestions": {
                    "医师法": ["医师法第九条", "医师的权利", "医师法对注册的规定"],
                    "执业医师法": ["执业医师法第九条", "医师的义务", "医师的执业规则"],
                    "医疗事故案例": ["医疗事故的经典案例", "医疗事故罪的案例", "手术遗留异物的案例"],
                    "医疗事故处理条例": ["什么是医疗事故", "医疗事故怎么鉴定", "医疗事故的赔偿标准"],
                    "医疗纠纷预防和处理条例": ["医疗纠纷怎么解决", "医疗纠纷人民调解", "病历可以复印吗"],
                    "刑法医疗条款": ["非法行医罪怎么判", "医疗事故罪怎么判", "刑法中的医疗犯罪"],
                }.get(key, ["医师法第九条", "医师的权利", "医师法对注册的规定"])}

    def _law_suggestions(self, art):
        """法律条文的快捷追问"""
        law = art.get("law", "")
        if law == "刑法医疗条款":
            return ["非法行医罪怎么判", "医疗事故罪怎么判", "刑法中的医疗犯罪"]
        if law == "执业医师法":
            return ["执业医师法第九条", "医师的义务", "医师的执业规则"]
        if law == "医师法":
            return ["医师法第九条", "医师的权利", "医师法对注册的规定"]
        if law == "医疗事故案例":
            return ["医疗事故的经典案例", "医疗事故罪的案例", "手术遗留异物的案例"]
        if law == "医疗事故处理条例":
            return ["什么是医疗事故", "医疗事故怎么鉴定", "医疗事故的赔偿标准"]
        if law == "医疗纠纷预防和处理条例":
            return ["医疗纠纷怎么解决", "医疗纠纷人民调解", "病历可以复印吗"]
        return ["医师法第九条", "医师的权利", "医师法对注册的规定"]

    def _answer_law(self, question):
        """
        法律法规问答：执业医师法 / 刑法医疗条款。
        非法律问题返回 None，走原有疾病问答流程。
        """
        if not self._law_keys:
            return None
        q = question.strip()
        # 1. 法律名匹配（"执业医师法"优先于"医师法"，避免子串误命中）
        law_keys = []
        for k, kws in LAW_NAME_KEYWORDS:
            if not any(w in q for w in kws):
                continue
            if k == "医师法" and "执业医师法" in q:
                continue  # 问的是旧法，跳过新法
            law_keys.append(k)
        # 2. 罪名关键词匹配 → 定位刑法；单独出现"医疗事故"（无"罪"）→ 定位《医疗事故处理条例》
        crime_hits = [w for w in LAW_CRIME_KEYWORDS if w in q]
        if crime_hits:
            target = ("医疗事故处理条例"
                      if crime_hits == ["医疗事故"] and "罪" not in q
                      else "刑法医疗条款")
            if target not in law_keys:
                law_keys.append(target)
        # 3. 条文号
        art_no = self._extract_article_no(q)
        # 4. 主题词提取（先剔除法律名/罪名关键词，避免法律名本身干扰检索）
        rest = q
        for w in sorted({w for _, kws in LAW_NAME_KEYWORDS for w in kws},
                        key=len, reverse=True):
            rest = rest.replace(w, " ")
        for w in LAW_CRIME_KEYWORDS:
            rest = rest.replace(w, " ")
        topics = self._law_topics(rest)
        if not topics:
            # 法律名/罪名词被剔除后无主题词时，用原始问题提取（如“医疗事故怎么鉴定”）
            topics = self._law_topics(q)
        # 5. 无法律名/条文号/罪名时：命中医疗法律语境词+主题词才触发（如“医师的义务”）
        if not law_keys and not art_no:
            if not (topics and any(w in q for w in LAW_CONTEXT_WORDS)):
                return None
            # 纠纷/鉴定语境默认走《医疗纠纷预防和处理条例》，其余走现行《医师法》
            default_law = ("医疗纠纷预防和处理条例"
                           if any(w in q for w in LAW_DISPUTE_WORDS) else "医师法")
            law_keys.append(default_law)

        # 6. 有具体条文号 → 精确查条
        if art_no:
            art = self.kg.get_law_article(law_keys[0] if law_keys else None, art_no)
            if art:
                return self._answer_law_article(art)

        # 7. 主题词检索（有主题词时优先用主题词；否则退回罪名关键词检索）
        topics_all = topics + (crime_hits if not topics else [])
        if topics_all:
            # 仅法律名提问（剔除法律名/罪名词后无实质内容）→ 直接返回概览；
            # 但问题含“罪”（如“非法行医罪”）时仍走条文检索
            stripped = rest.replace(" ", "").strip("，。！？、?!？")
            if not stripped and not art_no and "罪" not in q:
                return self._answer_law_overview(law_keys[0])
            hits = self._search_law_articles(law_keys or self._law_keys, topics_all)
            if hits:
                return self._answer_law_search(hits, q)

        # 8. 仅法律名 / 条文号未命中 → 法律概览
        if law_keys:
            return self._answer_law_overview(law_keys[0])
        return None

    def _answer_drug(self, drug):
        ins = self.kg.drug_inserts.get(drug)
        lines = ["💊 【%s】说明书" % drug, ""]
        cat = self.kg.entities.get(drug, {}).get("类别", "")
        if cat:
            lines.append("▪ 类别：%s" % cat)
        if ins:
            for key in ["适应症", "用法用量", "禁忌", "不良反应", "作用机制"]:
                if ins.get(key):
                    lines.append("▪ %s：%s" % (key, ins[key]))
        else:
            lines.append("（知识库暂无该药的说明书，可导入 DrugBank/NMPA 数据补充）")
        lines.extend(["", "⚕ " + DISCLAIMER])
        return {"found": True, "disease": None, "drug": drug, "intent": "说明书",
                "text": "\n".join(lines), "suggestions": []}

    def _answer_not_found(self, question):
        # 给出最接近的疾病建议
        guesses = get_close_matches(question, self._diseases, n=5, cutoff=0.4)
        lines = ["🤔 未在知识库中找到与「%s」精确匹配的疾病。" % question, ""]
        if guesses:
            lines.append("您是否想问：")
            for g in guesses:
                lines.append("   • %s" % g)
        else:
            lines.append("建议尝试更标准的疾病名称，例如：高血压、2型糖尿病、社区获得性肺炎。")
        return {"found": False, "text": "\n".join(lines), "suggestions": guesses}

    def _related(self, disease):
        """返回与该病相关的快捷追问建议"""
        return ["%s的治疗方案" % disease, "%s用什么药" % disease,
                "%s要做哪些检查" % disease, "%s的中医辨证" % disease,
                "%s的饮食宜忌" % disease]


if __name__ == "__main__":
    qa = KnowledgeQA()
    for q in ["慢性支气管炎的常见治疗方案", "高血压吃什么药", "二甲双胍的说明书",
              "糖尿病", "感冒和流感怎么区分"]:
        print("=" * 50)
        print("Q:", q)
        print(qa.answer(q)["text"])
