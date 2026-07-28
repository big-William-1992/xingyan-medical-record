"""
纠错引擎 v2 - 基于医学知识图谱 + NLP
Layer 1: 知识图谱语义纠错
Layer 2: NLP 相似度匹配 + 实体归一化
Layer 3: 规则引擎 + 科室校验
"""
import json
import os
import re
from difflib import SequenceMatcher, get_close_matches

from knowledge_graph import MedicalKnowledgeGraph
from rule_engine import RuleEngine
from functools import lru_cache


class Corrector:
    def __init__(self, dict_path=None, rule_engine=None):
        self.dict_path = dict_path or os.path.join(
            os.path.dirname(__file__), "medical_dict.json"
        )
        self.kg = MedicalKnowledgeGraph()
        self.rule_engine = rule_engine
        self.current_dept = "通用"
        self.active_words = set()
        self.load_dict()

        # 保留少量内置规则（格式化相关，不涉及错别字/逻辑）
        self.format_patterns = [
            # 数字 + 单位
            (r'(\d+)\s*[mMｍ]\s*[oOＯ][lLｌ]', r'\1mmol/L'),
            (r'(\d+)\s*[uUｕ][gGｇ]', r'\1μg'),
            (r'(\d+)\s*[mMｍ][gGｇ]', r'\1mg'),
            (r'(\d+)\s*[gGｇ]', r'\1g'),
            # 空格清理
            ('([ \\t\\n\\r，。！？、；：""''()])\\s+', r'\1'),
            ('\\s+([ \\t\\n\\r，。！？、；：""''()])', r'\1'),
            # 重复字
            (r'(.)\1{2,}', r'\1\1'),
            # "的得地"
            (r'([一-鿿])地([一-鿿])', r'\1的\2'),
        ]

        # 拼音纠错表
        self.pinyin_corrections = {
            "yanzheng": "炎症", "fashao": "发热", "kesou": "咳嗽",
            "toutong": "头痛", "touyun": "头晕", "xiongton": "胸痛",
            "fuzhang": "腹胀", "xueya": "血压", "xinlv": "心率",
            "huxi": "呼吸", "tiwen": "体温", "maibo": "脉搏",
            "feiyan": "肺炎", "zhiqiguan": "支气管", "gaoxueya": "高血压",
            "tangniaobing": "糖尿病", "weiyan": "胃炎", "ganyan": "肝炎",
            "fuxie": "腹泻", "outu": "呕吐", "exin": "恶心",
            "xindiantu": "心电图", "xuechanggui": "血常规", "niaochanggui": "尿常规",
            "baixibao": "白细胞", "hongxibao": "红细胞", "xuexiaoban": "血小板",
            "guansu": "冠脉", "xinjigengsi": "心肌梗死", "naogengsi": "脑梗死",
            "naochuxue": "脑出血", "guanxinbing": "冠心病", "xinjiaotong": "心绞痛",
            "qiguanyan": "气管炎", "biyan": "鼻炎", "yanyan": "咽炎",
            "weikuiyang": "胃溃疡", "jiechangyan": "结肠炎", "dannangyan": "胆囊炎",
            "shenjieshi": "肾结石", "niaoluganran": "尿路感染", "guanjieyan": "关节炎",
        }

        # 医学术语纠错（集中管理，避免 ASR / Corrector 各维护一份）
        self.term_corrections = {
            "发烧": "发热", "头疼": "头痛", "胸口疼": "胸痛",
            "肚子疼": "腹痛", "拉肚子": "腹泻", "喘不上气": "呼吸困难",
            "恶心呕吐": "恶心、呕吐", "咳嗽咳痰": "咳嗽、咳痰",
            "胸闷气短": "胸闷、气短", "白血胞": "白细胞", "血相": "血常规",
            "心电围": "心电图", "肝功": "肝功能", "肾功": "肾功能",
            "焱炎": "炎症", "肺焱": "肺炎", "心肌梗": "心肌梗死",
            "脑梗": "脑梗死", "高血压病": "高血压",
            "头炮": "头孢", "头泡": "头孢", "消炎药": "抗生素",
            "打点滴": "静脉输液", "没劲": "乏力", "不舒服": "不适",
            "拍了CT": "CT", "做CT": "CT", "CT检查": "CT",
            "胸片检查": "胸片", "拍了胸片": "胸片",
            # 常见同音/近音误识别（多字、医疗专属，误伤概率低）
            "白血球": "白细胞", "红血球": "红细胞", "血色素": "血红蛋白",
            "淋巴结肿大": "淋巴结肿大", "甲亢": "甲状腺功能亢进",
            "糖尿": "糖尿病", "冠心": "冠心病",
            "房扑": "心房扑动", "房颤": "心房颤动", "室颤": "心室颤动",
            "早搏": "期前收缩", "传导阻滞": "传导阻滞",
            "血糖高": "血糖升高", "血脂高": "血脂升高", "血压高": "血压升高",
            "转氨酶高": "转氨酶升高", "肌酐高": "肌酐升高",
            "双肺呼吸音粗": "双肺呼吸音粗", "干湿罗音": "干湿性啰音",
            "湿罗音": "湿啰音", "干罗音": "干啰音", "哮鸣音": "哮鸣音",
            "压疼": "压痛", "反跳疼": "反跳痛", "叩击疼": "叩击痛",
            "莫菲氏征": "Murphy征", "墨菲征": "Murphy征",
            "青霉素过敏": "青霉素过敏", "头孢过敏": "头孢菌素过敏",
            "雾化吸入": "雾化吸入", "心慌": "心悸", "憋气": "胸闷",
            "浑身没劲": "全身乏力", "食欲不振": "纳差", "吃不下饭": "纳差",
            "睡不着": "失眠", "尿频尿急": "尿频、尿急",
        }

        # 科室必填字段
        self.dept_rules = {}
        self.rejection_path = os.path.join(
            os.path.dirname(__file__), "rejection_rules.json"
        )
        self.rejections = {}  # (原文, 修正) → True
        self._load_rejections()

    def _load_rejections(self):
        """加载用户拒绝过的纠错"""
        if not os.path.exists(self.rejection_path):
            return
        try:
            with open(self.rejection_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            for key in data:
                parts = key.split("\x00")
                if len(parts) == 2:
                    self.rejections[tuple(parts)] = True
        except Exception:
            pass

    def save_rejection(self, original, corrected):
        """记录用户拒绝的纠错对"""
        key = (original, corrected)
        self.rejections[key] = True
        try:
            serializable = [
                "\x00".join(k) for k in self.rejections.keys()
            ]
            with open(self.rejection_path, 'w', encoding='utf-8') as f:
                json.dump(serializable, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[Corrector] 拒绝规则保存失败: {e}")

    def is_rejected(self, original, corrected):
        """检查某条纠错是否被用户拒绝过"""
        return (original, corrected) in self.rejections

    def load_dict(self):
        """加载词库"""
        if not os.path.exists(self.dict_path):
            return
        try:
            with open(self.dict_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            general = data.get("通用", {})
            for category, words in general.items():
                for word in words:
                    self.active_words.add(word)
            for dept, content in data.items():
                if dept == "通用":
                    continue
                for category, words in content.items():
                    if isinstance(words, list):
                        for word in words:
                            self.active_words.add(word)
                    elif category == "模板要求字段":
                        self.dept_rules[dept] = {"required_fields": words}
        except Exception as e:
            print(f"[Corrector] 词库加载失败: {e}")

    def set_department(self, dept):
        """切换科室词库"""
        self.current_dept = dept
        self.active_words = set()
        # 通用词
        self.active_words.update([
            "发热", "咳嗽", "咳痰", "咯血", "胸痛", "呼吸困难", "喘息",
            "腹痛", "腹泻", "恶心", "呕吐", "便血", "黑便",
            "头痛", "头晕", "意识不清", "抽搐", "昏迷",
            "水肿", "皮疹", "瘙痒", "关节痛", "肌肉酸痛",
            "乏力", "消瘦", "食欲不振", "失眠", "多饮", "多尿",
            "血压", "心率", "呼吸", "体温", "脉搏",
            "血常规", "尿常规", "大便常规", "血生化", "凝血功能",
            "心电图", "胸片", "CT", "MRI", "B超", "彩超",
            "肺炎", "支气管炎", "哮喘", "COPD", "肺气肿",
            "高血压", "冠心病", "心律失常", "心衰",
            "胃炎", "胃溃疡", "十二指肠溃疡", "消化道出血",
            "肝炎", "肝硬化", "肝癌", "胰腺炎",
            "糖尿病", "甲亢", "甲减", "肾病综合征",
            "脑梗死", "脑出血", "蛛网膜下腔出血",
            "骨折", "脱位", "扭伤", "挫伤",
            "阿莫西林", "头孢曲松", "头孢呋辛", "左氧氟沙星",
            "阿司匹林", "氯吡格雷", "阿托伐他汀",
            "氨氯地平", "硝苯地平", "缬沙坦",
            "二甲双胍", "格列美脲", "胰岛素",
            "奥美拉唑", "雷尼替丁", "蒙脱石散",
            "布洛芬", "对乙酰氨基酚", "吗啡", "哌替啶"
        ])

        # 同时从 medical_dict.json 加载通用词 + 当前科室词
        self._load_dict_words()

    def _load_dict_words(self):
        """从 medical_dict.json 加载科室词库"""
        if not os.path.exists(self.dict_path):
            return
        try:
            with open(self.dict_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            # 加载通用词
            general = data.get("通用", {})
            for category, words in general.items():
                if isinstance(words, list):
                    for word in words:
                        self.active_words.add(word)
            # 加载当前科室词
            dept_data = data.get(self.current_dept, {})
            for category, words in dept_data.items():
                if isinstance(words, list):
                    for word in words:
                        self.active_words.add(word)
        except Exception as e:
            print(f"[Corrector] 词库加载失败: {e}")

    def correct(self, text):
        """完整纠错流程"""
        log = []
        result = text

        # Layer 1: 规则引擎 - 自定义错别字规则（用户定义的优先）
        if self.rule_engine:
            result, typo_log = self.rule_engine.apply_typo_rules(result)
            for item in typo_log:
                item.setdefault("分类", "错别字")
            log.extend(typo_log)

        # Layer 2: 知识图谱语义纠错（逻辑错误）
        result, log1 = self._layer1_knowledge_correct(result)
        for item in log1:
            item["分类"] = "逻辑错误"
        log.extend(log1)

        # Layer 3: 规则引擎 - 自定义逻辑错误规则
        if self.rule_engine:
            logic_log = self.rule_engine.apply_logic_rules(result, self.kg)
            for item in logic_log:
                item.setdefault("分类", "逻辑错误")
            log.extend(logic_log)

        # Layer 4: NLP 相似度 + 实体归一化（错别字）
        result, log2 = self._layer2_nlp_correct(result)
        for item in log2:
            item.setdefault("分类", "错别字")
        log.extend(log2)

        # Layer 5: 格式化规则
        result, log3 = self._layer3_format_correct(result)
        log.extend(log3)

        # Layer 6: 科室校验（缺项提醒）
        log4 = self._layer4_dept_check(result)
        for item in log4:
            item["分类"] = "缺项提醒"
        log.extend(log4)

        # 过滤掉用户拒绝过的纠错
        filtered_log = []
        for item in log:
            orig = item.get("原文", "")
            corr = item.get("修正", "")
            if orig and corr and not self.is_rejected(orig, corr):
                filtered_log.append(item)
        # 将拒绝过的纠错反向应用到文本（恢复原文）
        # 修复：只替换第一个匹配，避免 replace 替换所有相同文本导致误伤
        for item in log:
            orig = item.get("原文", "")
            corr = item.get("修正", "")
            if orig and corr and self.is_rejected(orig, corr):
                idx = result.find(corr)
                if idx >= 0:
                    result = result[:idx] + orig + result[idx + len(corr):]

        return result, filtered_log

    def _layer1_knowledge_correct(self, text):
        """
        Layer 1: 基于知识图谱的语义纠错
        - 识别文本中的医疗实体
        - 利用知识图谱关系验证实体组合是否合理
        - 检测语义矛盾（如：诊断为肺癌但用药是降压药）
        """
        log = []
        result = text
        suggestions = []

        # 提取文本中的实体
        found_entities = []
        for entity_name in self.kg.entities:
            if entity_name in text:
                found_entities.append(entity_name)

        if not found_entities:
            return result, log

        # 检查实体间的关系是否合理
        # 例如：检查"疾病"是否配有对应的"药物"
        diseases = [e for e in found_entities if self.kg.get_entity_type(e) == "疾病"]
        drugs = [e for e in found_entities if self.kg.get_entity_type(e) == "药物"]
        exams = [e for e in found_entities if self.kg.get_entity_type(e) == "检查"]

        # 验证疾病-药物关系
        for disease in diseases:
            expected_drugs = self.kg.get_drugs_for_disease(disease)
            if expected_drugs:
                # 检查文本中是否至少有一个合理药物（仅为提示，不强制）
                has_relevant_drug = any(d in drugs for d in expected_drugs)
                if not has_relevant_drug and drugs:
                    # 可能有药物不匹配，给出建议
                    log.append({
                        "type": "知识图谱提示",
                        "原文": f"疾病「{disease}」",
                        "修正": f"常用药物：{', '.join(expected_drugs[:3])}",
                        "级别": "建议"
                    })

        # 验证症状-疾病关系
        symptoms = [e for e in found_entities if self.kg.get_entity_type(e) == "症状"]
        for symptom in symptoms:
            related_diseases = self.kg.get_diseases_with_symptom(symptom)
            if related_diseases and not diseases:
                log.append({
                    "type": "知识图谱提示",
                    "原文": f"症状「{symptom}」",
                    "修正": f"可能相关疾病：{', '.join(related_diseases[:3])}",
                    "级别": "建议"
                })

        # 检查检查项目是否匹配疾病
        for exam in exams:
            related = []
            for s, r, o in self.kg.relations:
                if r == "HAS_EXAM" and o == exam:
                    related.append(s)
            if related and not diseases:
                log.append({
                    "type": "知识图谱提示",
                    "原文": f"检查项目「{exam}」",
                    "修正": f"常用于：{', '.join(related[:3])}",
                    "级别": "建议"
                })

        # 模糊匹配纠错（在知识图谱实体中找最相似的）
        # 用正则提取可能的中文词段
        segments = re.findall(r'[一-鿿]{2,}', result)
        for seg in segments:
            if seg in self.kg.entities:
                continue
            # 在知识图谱中找相似的实体
            similar = self.kg.find_similar_entities(seg, threshold=0.65)
            if similar:
                best_match, score = similar[0]
                suggestions.append({
                    "原文": seg,
                    "修正": best_match,
                    "相似度": f"{score:.0%}",
                    "级别": "建议"
                })

        # 应用高置信度的纠错
        for sug in suggestions:
            try:
                score = float(sug["相似度"].replace('%', '')) / 100
            except (ValueError, TypeError):
                score = 0.0
            if score >= 0.75:
                result = result.replace(sug["原文"], sug["修正"])
                log.append({
                    "type": "知识图谱纠错",
                    "原文": sug["原文"],
                    "修正": sug["修正"],
                    "级别": "建议"
                })
            else:
                log.append(sug)

        return result, log

    def _layer2_nlp_correct(self, text):
        """
        Layer 2: NLP 相似度匹配 + 实体归一化
        - SequenceMatcher 计算字符串相似度
        - 拼音近似匹配
        - 实体类型一致性检查
        """
        log = []
        result = text
        corrections = {}

        # 提取中文词段
        segments = re.findall(r'[一-鿿]{2,}', result)

        for seg in segments:
            if seg in self.kg.entities or seg in self.active_words:
                continue

            # 方法1: 与知识图谱实体做相似度匹配
            best_match = None
            best_score = 0
            for entity_name in self.kg.entities:
                score = SequenceMatcher(None, seg, entity_name).ratio()
                if score > best_score and score >= 0.6:
                    best_score = score
                    best_match = entity_name

            # 方法2: 与通用词库做相似度匹配
            if not best_match:
                matches = get_close_matches(seg, self.active_words, n=1, cutoff=0.7)
                if matches:
                    best_match = matches[0]
                    best_score = SequenceMatcher(None, seg, best_match).ratio()

            if best_match and best_score >= 0.65:
                corrections[seg] = {
                    "correct": best_match,
                    "score": best_score
                }

        # 应用纠错
        for wrong, info in corrections.items():
            result = result.replace(wrong, info["correct"])
            confidence = "自动" if info["score"] >= 0.8 else "建议"
            log.append({
                "type": "NLP纠错",
                "原文": wrong,
                "修正": info["correct"],
                "级别": confidence,
                "相似度": f"{info['score']:.0%}"
            })

        # 拼音纠错
        for pinyin, correct in self.pinyin_corrections.items():
            if pinyin in result.lower():
                result = result.replace(pinyin, correct)
                log.append({
                    "type": "拼音纠错",
                    "原文": pinyin,
                    "修正": correct,
                    "级别": "建议"
                })

        return result, log

    def _layer3_format_correct(self, text):
        """Layer 3: 格式化规则（空格、重复字、的得地等）"""
        log = []
        result = text

        for pattern, replacement in self.format_patterns:
            new_text = re.sub(pattern, replacement, result)
            if new_text != result:
                # 记录实际被替换的内容
                for m in re.finditer(pattern, result):
                    original = m.group(0)
                    fixed = re.sub(pattern, replacement, original)
                    if original != fixed:
                        log.append({
                            "type": "规则修正",
                            "原文": original,
                            "修正": fixed,
                            "级别": "自动"
                        })
                result = new_text

        return result, log

    def _layer4_dept_check(self, text):
        """Layer 4: 科室规则校验"""
        log = []
        if not self.current_dept or self.current_dept not in self.dept_rules:
            return log

        rules = self.dept_rules[self.current_dept]
        for field in rules.get("required_fields", []):
            if field not in text:
                log.append({
                    "type": "缺项提醒",
                    "原文": f"缺少「{field}」",
                    "修正": f"建议补充「{field}」",
                    "级别": "警告"
                })

        return log

    def get_suggestions(self, word):
        """获取纠错建议"""
        if word in self.active_words or word in self.kg.entities:
            return []
        matches = get_close_matches(word, list(self.active_words | set(self.kg.entities.keys())), n=3, cutoff=0.5)
        return matches

    def get_entity_info(self, word):
        """获取实体在知识图谱中的信息"""
        return self.kg.entities.get(word)

    def get_graph_stats(self):
        """获取知识图谱统计信息"""
        types = {}
        for name, info in self.kg.entities.items():
            t = info.get("type", "未知")
            types[t] = types.get(t, 0) + 1
        return {
            "实体总数": len(self.kg.entities),
            "关系总数": len(self.kg.relations),
            "实体类型分布": types
        }

    def post_process_medical(self, text):
        """医学术语后处理（委托给模块级函数，统一管理纠错表）"""
        return post_process_medical(text, self.term_corrections)


def post_process_medical(text, term_corrections=None):
    """医学术语后处理（独立函数，供 ASR 引擎调用）"""
    if not text:
        return text

    if term_corrections:
        for wrong, correct in term_corrections.items():
            if wrong in text:
                text = text.replace(wrong, correct)

    # 自动换行（按标点分段）
    lines = []
    current = ""
    for char in text:
        current += char
        if char in '。！？' or (char == '.' and len(current) > 10):
            lines.append(current.strip())
            current = ""
        elif char in '，,' and len(current) > 30:
            lines.append(current.strip())
            current = ""
    if current.strip():
        lines.append(current.strip())
    text = '\n'.join(lines)

    # 病历结构关键词前加空行（仅在句末标点/文本开头之后才加，避免破坏句中内容）
    keywords = ['主诉', '现病史', '既往史', '体格检查', '辅助检查',
                 '初步诊断', '诊疗经过', '出院情况', '出院医嘱',
                 '术前诊断', '手术名称', '术中情况', '术后诊断',
                 '影像表现', '诊断意见', '建议']
    for kw in keywords:
        # 仅在关键词前面是句号/感叹号/问号/换行时才插入换行，避免把句中的"建议""诊断"等词也断开
        text = re.sub(r'([。！？\n])\s*(' + re.escape(kw) + r')', r'\1\n\2', text)
    # 如果文本以关键词开头，不需要加换行
    while '\n\n\n' in text:
        text = text.replace('\n\n\n', '\n\n')
    return text.strip()
