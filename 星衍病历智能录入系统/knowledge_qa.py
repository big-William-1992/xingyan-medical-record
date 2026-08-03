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
