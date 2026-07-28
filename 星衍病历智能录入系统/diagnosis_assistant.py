"""
AI 辅助诊断（基于医学知识图谱，纯规则+图谱推理，离线）
- 症状→疾病推理：按命中症状数加权排序给出可能诊断
- 用药审查：诊断+用药组合校验，提示不匹配用药与推荐用药
- 检查建议：根据疑似诊断列出建议检查，标出尚未记录项
- 风险预警：内置数值阈值规则，从病历文本正则提取数值触发预警
所有输出仅供参考，以医师判断为准。
"""
import re

from knowledge_graph import MedicalKnowledgeGraph


DISCLAIMER = "以上分析由知识图谱规则推理生成，仅供参考，以医师判断为准。"


class DiagnosisAssistant:
    def __init__(self, kg=None):
        self.kg = kg or MedicalKnowledgeGraph()
        # 预取全部实体名，供文本匹配
        self._all_symptoms = [n for n, t in self.kg.entity_types.items() if t == "症状"]
        self._all_drugs = [n for n, t in self.kg.entity_types.items() if t == "药物"]
        self._all_diseases = self.kg.get_all_diseases()
        # 症状同样在疾病"常见症状"中出现但未注册为独立实体的，也纳入匹配
        extra_symptoms = set()
        for d in self._all_diseases:
            for s in self.kg.get_symptoms_for_disease(d):
                extra_symptoms.add(s)
        # 中医证型症状也纳入
        for name, info in self.kg.entities.items():
            if info.get("type") == "证型":
                for s in info.get("症状", []):
                    extra_symptoms.add(s)
        self._symptom_vocab = sorted(set(self._all_symptoms) | extra_symptoms,
                                     key=len, reverse=True)
        # 中医病名词表
        self._tcm_diseases = [n for n, t in self.kg.entity_types.items() if t == "中医病名"]
        # 中医危急证候关键词
        self._tcm_critical_keywords = {
            "亡阳": "亡阳危象，阳气暴脱，需急回阳救逆",
            "亡阴": "亡阴危象，阴液耗竭，需急滋阴固脱",
            "厥脱": "厥脱危象，阴阳气不相顺接，需急固脱回阳",
            "脱证": "脱证危象，正气虚脱，需急益气固脱",
            "闭证": "闭证危象，邪气内闭，需急开窍醒神",
        }

    # ─── 症状提取 ───────────────────────────────────────
    def extract_symptoms(self, text):
        """从病历文本中提取命中的症状实体（去重，保留顺序）"""
        found = []
        for s in self._symptom_vocab:
            if s in text and s not in found:
                found.append(s)
        return found

    def extract_drugs(self, text):
        """从病历文本中提取命中的药物实体"""
        return [d for d in self._all_drugs if d in text]

    def extract_diagnoses(self, text):
        """从病历文本中提取已明确书写的诊断（命中疾病实体名）"""
        return [d for d in self._all_diseases if d in text]

    # ─── 症状→疾病推理 ──────────────────────────────────
    def infer_diseases(self, text, top_n=5):
        """
        根据文本中的症状推理可能疾病。
        对每个候选疾病，按命中的症状数 / 该病总症状数加权打分。
        返回 [{disease, score, matched, total, rationale}] Top N。
        """
        symptoms = self.extract_symptoms(text)
        if not symptoms:
            return []
        symptom_set = set(symptoms)
        scored = []
        for disease in self._all_diseases:
            dz_symptoms = set(self.kg.get_symptoms_for_disease(disease))
            if not dz_symptoms:
                continue
            matched = symptom_set & dz_symptoms
            if not matched:
                continue
            # 加权：命中数为主，命中占该病症状比例为辅
            score = len(matched) + len(matched) / len(dz_symptoms)
            scored.append({
                "disease": disease,
                "score": round(score, 2),
                "matched": sorted(matched),
                "total": len(dz_symptoms),
                "rationale": "命中症状 %d/%d：%s" % (
                    len(matched), len(dz_symptoms), "、".join(sorted(matched))
                ),
            })
        scored.sort(key=lambda x: (x["score"], len(x["matched"])), reverse=True)
        return scored[:top_n]

    # ─── 用药审查 ───────────────────────────────────────
    def review_drugs(self, text, suspected_diseases=None):
        """
        校验文本中的用药与诊断/疑似诊断是否匹配。
        返回 {matched: [...], mismatched: [...], recommended: [...]}
        """
        drugs = self.extract_drugs(text)
        diagnoses = self.extract_diagnoses(text)
        # 参考疾病 = 明确诊断 + 疑似诊断
        ref_diseases = list(diagnoses)
        if suspected_diseases:
            for d in suspected_diseases:
                if d not in ref_diseases:
                    ref_diseases.append(d)

        # 每个参考疾病的推荐用药合集
        recommended = set()
        for d in ref_diseases:
            recommended.update(self.kg.get_drugs_for_disease(d))

        matched, mismatched = [], []
        for drug in drugs:
            treat_diseases = set(self._diseases_treated_by(drug))
            hit = treat_diseases & set(ref_diseases)
            if not ref_diseases:
                # 无诊断参考，无法判定
                continue
            if hit:
                matched.append({"drug": drug, "for": sorted(hit)})
            else:
                mismatched.append({
                    "drug": drug,
                    "note": "未匹配到当前诊断（%s）的适应症" % "、".join(ref_diseases),
                })

        # 推荐但未使用的药物
        used = set(drugs)
        rec_missing = sorted(recommended - used)
        return {
            "diagnoses": diagnoses,
            "drugs": drugs,
            "matched": matched,
            "mismatched": mismatched,
            "recommended": rec_missing,
        }

    def _diseases_treated_by(self, drug):
        """该药物可治疗的疾病列表"""
        results = []
        for subj, rel, obj in self.kg.relations:
            if rel == "TREATS" and subj == drug:
                results.append(obj)
            elif rel == "TREATED_BY" and obj == drug:
                results.append(subj)
        return results

    # ─── 检查建议 ───────────────────────────────────────
    def suggest_exams(self, text, suspected_diseases):
        """
        根据疑似诊断列出建议检查项目，并标出病历中尚未记录的项。
        返回 [{exam, for: [疾病], recorded: bool}]
        """
        exam_map = {}  # exam -> set(diseases)
        for d in suspected_diseases:
            for e in self.kg.get_exams_for_disease(d):
                exam_map.setdefault(e, set()).add(d)
        results = []
        for exam, diseases in exam_map.items():
            results.append({
                "exam": exam,
                "for": sorted(diseases),
                "recorded": exam in text,
            })
        # 未记录的排前面
        results.sort(key=lambda x: (x["recorded"], -len(x["for"])))
        return results

    # ─── 风险预警（数值阈值规则）────────────────────────
    # 规则：(字段正则, 判定函数, 预警文案)
    def risk_alerts(self, text):
        alerts = []

        def _find_num(patterns):
            for p in patterns:
                m = re.search(p, text)
                if m:
                    try:
                        return float(m.group(1))
                    except (ValueError, IndexError):
                        continue
            return None

        # 体温
        temp = _find_num([r'体温[：: ]*([0-9]{2}\.?[0-9]?)', r'T[：: ]*([0-9]{2}\.?[0-9]?)\s*[℃度]'])
        if temp is not None:
            if temp >= 39:
                alerts.append(("高热", "体温 %.1f℃ ≥ 39℃，提示高热，注意物理降温与病因排查" % temp))
            elif temp <= 35:
                alerts.append(("低体温", "体温 %.1f℃ ≤ 35℃，提示低体温" % temp))

        # 收缩压 / 舒张压
        sbp = _find_num([r'收缩压[：: ]*([0-9]{2,3})', r'血压[：: ]*([0-9]{2,3})\s*/'])
        dbp = _find_num([r'舒张压[：: ]*([0-9]{2,3})', r'血压[：: ]*[0-9]{2,3}\s*/\s*([0-9]{2,3})'])
        if sbp is not None and sbp >= 180:
            alerts.append(("高血压危象", "收缩压 %d mmHg ≥ 180，警惕高血压危象" % int(sbp)))
        if dbp is not None and dbp >= 120:
            alerts.append(("高血压危象", "舒张压 %d mmHg ≥ 120，警惕高血压危象" % int(dbp)))
        if sbp is not None and sbp <= 90:
            alerts.append(("低血压/休克", "收缩压 %d mmHg ≤ 90，警惕休克，需评估循环状态" % int(sbp)))

        # 血糖
        glu = _find_num([r'血糖[：: ]*([0-9]{1,2}\.?[0-9]?)'])
        if glu is not None:
            if glu >= 16.7:
                alerts.append(("血糖危急", "血糖 %.1f mmol/L 显著升高，警惕高血糖危象/酮症酸中毒" % glu))
            elif glu <= 2.8:
                alerts.append(("低血糖", "血糖 %.1f mmol/L ≤ 2.8，提示低血糖，需立即处理" % glu))

        # 心率
        hr = _find_num([r'心率[：: ]*([0-9]{2,3})', r'HR[：: ]*([0-9]{2,3})'])
        if hr is not None:
            if hr >= 120:
                alerts.append(("心动过速", "心率 %d 次/分 ≥ 120，提示心动过速" % int(hr)))
            elif hr <= 50:
                alerts.append(("心动过缓", "心率 %d 次/分 ≤ 50，提示心动过缓" % int(hr)))

        # 血氧饱和度
        spo2 = _find_num([r'血氧[饱和度]*[：: ]*([0-9]{2,3})', r'SpO2[：: ]*([0-9]{2,3})'])
        if spo2 is not None and spo2 <= 90:
            alerts.append(("低氧血症", "血氧饱和度 %d%% ≤ 90%%，提示低氧血症，需吸氧" % int(spo2)))

        return alerts

    # ─── 中医辨证推理 ─────────────────────────────────

    def extract_tcm_symptoms(self, text):
        """从文本提取中医症状（舌象、脉象、四诊描述等）"""
        found = []
        for name, info in self.kg.entities.items():
            if info.get("type") != "证型":
                continue
            for s in info.get("症状", []):
                if s in text and s not in found:
                    found.append(s)
        return found

    def infer_syndromes(self, text, top_n=3):
        """
        从文本提取中医症状，推理证型。
        返回 [{syndrome, score, matched, rationale}]
        """
        tcm_symptoms = self.extract_tcm_symptoms(text)
        if not tcm_symptoms:
            return []
        return self.kg.infer_syndrome(tcm_symptoms, top_n=top_n)

    def suggest_treatment(self, syndromes):
        """
        根据证型列表返回治法方药建议。
        返回 {治法, 代表方, 药物: [...]}
        """
        if not syndromes:
            return None
        top = syndromes[0]
        syn_name = top.get("syndrome", "") if isinstance(top, dict) else str(top)
        return self.kg.get_treatment_for_syndrome(syn_name)

    def suggest_tcm_differential(self, text):
        """
        根据中医病名查常见类证，列出各证型鉴别要点。
        返回 [{disease, syndrome, key_points, 治法, 代表方}]
        """
        found_diseases = [d for d in self._tcm_diseases if d in text]
        if not found_diseases:
            return []
        results = []
        for td in found_diseases:
            syndromes = self.kg.get_syndromes_for_disease(td)
            for syn in syndromes:
                info = self.kg.entities.get(syn, {})
                results.append({
                    "disease": td,
                    "syndrome": syn,
                    "key_points": "、".join(info.get("症状", [])[:4]),
                    "治法": info.get("治法", ""),
                    "代表方": info.get("代表方", ""),
                })
        return results

    def tcm_risk_alerts(self, text):
        """中医危急证候识别"""
        alerts = []
        for keyword, msg in self._tcm_critical_keywords.items():
            if keyword in text:
                alerts.append(("中医危急", f"「{keyword}」{msg}"))
        return alerts

    # ─── 综合分析 ───────────────────────────────────────
    def analyze(self, text):
        """
        对病历文本做完整分析，返回结构化结果 dict。
        包含西医诊断 + 中医辨证。
        """
        if not text or not text.strip():
            return {
                "diagnoses": [], "drug_review": None,
                "exam_suggestions": [], "risk_alerts": [],
                "tcm_analysis": None,
                "disclaimer": DISCLAIMER,
            }
        possible = self.infer_diseases(text)
        suspected = [p["disease"] for p in possible]
        drug_review = self.review_drugs(text, suspected)
        exam_suggestions = self.suggest_exams(text, suspected)
        alerts = self.risk_alerts(text)
        # 结合疑似诊断的危急值提示
        for p in possible:
            cv = self.kg.get_critical_value(p["disease"])
            if cv:
                alerts.append((p["disease"], cv))

        # 中医辨证分析
        tcm_syndromes = self.infer_syndromes(text)
        tcm_treatment = self.suggest_treatment(tcm_syndromes) if tcm_syndromes else None
        tcm_differential = self.suggest_tcm_differential(text)
        tcm_alerts = self.tcm_risk_alerts(text)
        alerts.extend(tcm_alerts)

        # 识别中医病名
        tcm_diagnoses = [d for d in self._tcm_diseases if d in text]

        tcm_analysis = None
        if tcm_syndromes or tcm_diagnoses or tcm_differential:
            tcm_analysis = {
                "tcm_diagnoses": tcm_diagnoses,
                "syndromes": tcm_syndromes,
                "treatment": tcm_treatment,
                "differential": tcm_differential,
            }

        return {
            "diagnoses": possible,
            "drug_review": drug_review,
            "exam_suggestions": exam_suggestions,
            "risk_alerts": alerts,
            "tcm_analysis": tcm_analysis,
            "disclaimer": DISCLAIMER,
        }


if __name__ == "__main__":
    da = DiagnosisAssistant()
    demo = ("主诉：发热咳嗽三天。现病史：患者三天前受凉后出现发热，体温39.5℃，伴咳嗽咳痰。"
            "初步诊断：肺炎。用药：氨氯地平。")
    result = da.analyze(demo)
    print("可能诊断：")
    for d in result["diagnoses"]:
        print("  ", d["disease"], d["score"], d["rationale"])
    print("用药审查：", result["drug_review"])
    print("风险预警：", result["risk_alerts"])
    print("中医分析：", result.get("tcm_analysis"))
