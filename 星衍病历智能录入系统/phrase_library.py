"""
常用语句库 - 医生病历高频短语一键插入
- 按分类组织（体格检查/一般情况/诊疗计划等）
- 内置默认短语 + 用户自定义，持久化到 phrases.json
- 与 asr_engine / corrector 无耦合，纯数据管理
"""
import json
import os


class PhraseLibrary:
    """常用语句库管理。分类 → 短语列表。"""

    def __init__(self, path=None):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        self.path = path or os.path.join(base_dir, "phrases.json")
        # {分类: [短语, ...]}
        self.categories = {}
        self._load()

    # ─── 加载/保存 ────────────────────────────────────────
    def _load(self):
        if os.path.exists(self.path):
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    # 兼容 {"categories": {...}} 或直接 {...}
                    self.categories = data.get("categories", data)
                    return
            except Exception as e:
                print(f"[Phrase] 加载短语库失败: {e}")
        # 加载失败或文件不存在 → 使用默认并落盘
        self.categories = self._default_phrases()
        self.save()

    def save(self):
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump({"categories": self.categories}, f,
                          ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"[Phrase] 保存短语库失败: {e}")
            return False

    # ─── 查询 ─────────────────────────────────────────────
    def get_categories(self):
        return list(self.categories.keys())

    def get_phrases(self, category):
        return list(self.categories.get(category, []))

    def all_phrases(self):
        result = []
        for phrases in self.categories.values():
            result.extend(phrases)
        return result

    # ─── 增删改 ───────────────────────────────────────────
    def add_phrase(self, category, phrase):
        phrase = (phrase or "").strip()
        if not phrase:
            return False
        self.categories.setdefault(category, [])
        if phrase in self.categories[category]:
            return False
        self.categories[category].append(phrase)
        self.save()
        return True

    def remove_phrase(self, category, phrase):
        if category in self.categories and phrase in self.categories[category]:
            self.categories[category].remove(phrase)
            if not self.categories[category]:
                del self.categories[category]
            self.save()
            return True
        return False

    def add_category(self, category):
        category = (category or "").strip()
        if not category or category in self.categories:
            return False
        self.categories[category] = []
        self.save()
        return True

    # ─── 默认短语 ─────────────────────────────────────────
    @staticmethod
    def _default_phrases():
        return {
            "一般情况": [
                "神志清楚，精神可，查体合作。",
                "发育正常，营养中等，自主体位。",
                "神志清楚，精神差，被动体位，查体欠合作。",
                "急性病容，表情痛苦。",
                "慢性病容，消瘦。",
            ],
            "头颈部": [
                "头颅无畸形，双侧瞳孔等大等圆，对光反射灵敏。",
                "巩膜无黄染，睑结膜无苍白。",
                "颈软无抵抗，气管居中，甲状腺无肿大。",
                "颈静脉无怒张，肝颈静脉回流征阴性。",
            ],
            "胸肺": [
                "胸廓对称无畸形，双肺呼吸音清，未闻及干湿性啰音。",
                "双肺呼吸音粗，可闻及散在湿啰音。",
                "语音震颤对称，叩诊呈清音。",
            ],
            "心脏": [
                "心前区无隆起，心界不大，心率齐，各瓣膜听诊区未闻及病理性杂音。",
                "心律不齐，第一心音强弱不等。",
            ],
            "腹部": [
                "腹平软，全腹无压痛及反跳痛，肝脾肋下未触及。",
                "腹部平坦，肠鸣音正常，约4次/分。",
                "肝脾肋下未触及，Murphy征阴性，移动性浊音阴性。",
            ],
            "四肢脊柱": [
                "脊柱四肢无畸形，活动自如，双下肢无水肿。",
                "四肢肌力5级，肌张力正常。",
                "生理反射存在，病理反射未引出。",
            ],
            "诊疗计划": [
                "1.完善相关检查；2.对症支持治疗；3.密切观察病情变化。",
                "完善血常规、生化、心电图等检查。",
                "予以补液、抗感染、对症支持治疗。",
                "向患者及家属交代病情，签署知情同意书。",
            ],
            "医嘱交代": [
                "低盐低脂饮食，注意休息，避免劳累。",
                "如有不适，及时就诊。",
                "定期门诊复查。",
                "遵医嘱按时服药，不适随诊。",
            ],
        }
