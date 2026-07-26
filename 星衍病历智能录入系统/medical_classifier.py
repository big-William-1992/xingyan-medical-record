"""
病历内容分类器
根据语音识别的文本内容，自动判断属于病历的哪个部分
"""
import re


class MedicalClassifier:
    """
    基于规则和关键词的病历内容分类
    把连续语音文本自动分配到主诉、现病史、既往史等字段
    """

    # 标准字段名列表
    STANDARD_FIELDS = [
        # 基本信息
        "姓名", "性别", "年龄", "民族", "婚姻状况", "出生地", "职业",
        "入院方式", "入院时间", "病史陈述者", "可靠程度",
        # 病史
        "主诉", "现病史", "既往史", "个人史", "婚育史", "家族史",
        # 检查诊断
        "体格检查", "辅助检查", "初步诊断", "诊断依据", "鉴别诊断",
        # 诊疗
        "诊疗计划", "诊疗经过", "手术名称", "术前诊断", "术中情况",
        "术后诊断", "术后医嘱",
        # 影像
        "影像表现", "诊断意见", "建议",
        "检查项目", "检查部位", "检查方法", "增强特征", "血管描述",
        "超声所见", "超声提示", "序列", "对比剂", "BI-RADS分级",
        # 其他
        "出院情况", "出院医嘱", "住院天数",
        "急救措施", "用药情况", "效果评估",
    ]

    # 各字段的关键词特征
    FIELD_SIGNALS = {
        "主诉": {
            "keywords": [
                "主要症状", "主要表现", "不舒服", "来看病", "主要原因",
                "最主要", "最突出", "感到", "觉得", "出现",
                # 症状词作为主诉信号
                "发热", "咳嗽", "咳痰", "胸痛", "腹痛", "头痛", "头晕",
                "呼吸困难", "恶心", "呕吐", "腹泻", "水肿", "乏力", "消瘦"
            ],
            "patterns": [
                r'[一二三四五六七八九十]+\s*[天小时分钟年月日]',  # 时间描述
                r'[两三三四五六七八九十]+[天小时分钟]',  # 持续时间
                r'[前后左右上下]+\s*[天小时]',  # 时间范围
            ],
            "not_signals": ["之前", "以前", "既往", "过去", "去年", "前年", "既往史"],
            "max_chars": 100,  # 主诉通常较短
        },
        "现病史": {
            "keywords": [
                "发病", "开始", "出现", "持续", "加重", "缓解",
                "曾去", "就诊", "检查", "治疗", "用药", "效果",
                "过程", "经过", "发展", "变化", "加重", "反复",
                "起初", "当时", "当时", "随后", "之后", "接着"
            ],
            "patterns": [
                r'[前后左右上下]+\s*[天小时]',  # 时间线
                r'[一二三四五六七八九十]+\s*[天小时分钟]',  # 持续时间
            ],
            "not_signals": ["之前", "以前", "既往", "过去", "去年", "前年"],
            "min_chars": 20,  # 现病史通常较长
        },
        "既往史": {
            "keywords": [
                # 时间信号词
                "之前", "以前", "过去", "曾有", "曾患", "既往",
                "去年", "前年", "小时候", "多年", "长期", "年间",
                "病史", "病史", "慢性", "常年",
                # 疾病名（出现这些通常暗示既往史）
                "高血压", "糖尿病", "心脏病", "手术", "过敏",
                "脑梗", "心梗", "肝炎", "结核", "肿瘤",
                # 否定词
                "否认", "无", "否认", "没有过敏", "没有家族",
                # 生活习惯
                "吸烟", "饮酒", "喝酒", "抽烟", "长期饮酒",
                # 家族史
                "家族", "遗传", "父亲", "母亲", "爷爷", "奶奶",
            ],
            "patterns": [
                r'[高血压糖尿病冠心病脑梗心梗]+\s*[二三三四五六七八九十]+\s*[年月]',  # 慢性病+时间
                r'[二三三四五六七八九十]+\s*[年月日]\s*[前以]',  # "三年前"
                r'[否认无]+\s*[过敏家族传染病]',  # "否认过敏史"
                r'[吸烟饮酒]+\s*[二三三四五六七八九十]+\s*[年月日年]',  # "吸烟十年"
            ],
            "not_signals": ["主要", "来看", "感到", "出现", "发热", "咳嗽咳痰", "胸痛", "腹痛"],
            "boost_if_alone": True,  # 单独的疾病名+时间，即使没有"既往"也归既往史
        },
        "体格检查": {
            "keywords": [
                "体温", "脉搏", "呼吸", "血压", "神志", "精神",
                "面色", "皮肤", "巩膜", "淋巴结", "甲状腺",
                "肺部", "心脏", "腹部", "肝脏", "脾脏",
                "神经系统", "查体", "体检", "体征", "检查发现",
                "双肺", "心率", "心律", "腹软", "压痛",
                "反跳痛", "肌紧张", "病理征"
            ],
            "patterns": [
                r'\d+[\.\d]*\s*[℃度]',  # 体温数值
                r'\d+\s*[次\/]分钟',  # 脉搏/呼吸
                r'\d+\s*\/\s*\d+\s*mmHg',  # 血压
            ],
        },
        "辅助检查": {
            "keywords": [
                "血常规", "尿常规", "大便常规", "血生化", "凝血功能",
                "心电图", "胸片", "CT", "MRI", "B超", "彩超",
                "检查结果", "化验", "影像", "实验室",
                "提示", "回报", "结果显示", "未见异常",
                "白细胞", "血红蛋白", "血小板", "血糖", "血脂"
            ],
            "patterns": [
                r'\d+\s*[×xX]\s*\d+',  # 数值范围（如 12×10^9）
                r'[上下][下限]',  # 正常范围
                r'[阳阴]性',  # 检验结果
            ],
        },
        "初步诊断": {
            "keywords": [
                "诊断", "考虑", "初步", "印象", "认为",
                "肺炎", "支气管炎", "哮喘", "高血压", "冠心病",
                "胃炎", "胃溃疡", "糖尿病", "脑梗死", "脑出血",
                "阑尾炎", "胆囊炎", "胰腺炎", "骨折"
            ],
            "patterns": [
                r'[一二三四五六七八九十]\s*[\.、）)]\s*\w+',  # 编号诊断
            ],
            "not_signals": ["体温", "脉搏", "血压", "呼吸"],  # 体征不算诊断
        },
        "诊疗经过": {
            "keywords": [
                "治疗", "用药", "处理", "给予", "予以",
                "输液", "口服", "手术", "介入", "转科",
                "好转", "加重", "稳定", "缓解", "治愈"
            ],
        },
        "出院情况": {
            "keywords": [
                "出院", "好转", "治愈", "症状消失", "恢复",
                "出院时", "出院前"
            ],
        },
        "出院医嘱": {
            "keywords": [
                "医嘱", "出院后", "随访", "复查", "注意",
                "避免", "坚持", "继续"
            ],
        },
        "急救措施": {
            "keywords": [
                "抢救", "急救", "心肺复苏", "除颤", "气管插管",
                "升压", "降压", "止血", "吸氧"
            ],
        },
        "用药情况": {
            "keywords": [
                "用药", "服药", "给予", "使用", "点滴",
                "静脉", "肌肉", "口服", "外用"
            ],
        },

        # 基本信息字段
        "姓名": {
            "keywords": ["姓名", "叫", "名字"],
            "patterns": [r'姓\s*名\s*[：:]\s*\S'],
            "max_chars": 15,
        },
        "性别": {
            "keywords": ["性别", "男", "女"],
            "patterns": [r'性\s*别\s*[：:]\s*[男女]'],
            "max_chars": 10,
        },
        "年龄": {
            "keywords": ["年龄", "岁", "year"],
            "patterns": [r'年\s*龄\s*[：:]\s*\d+'],
            "max_chars": 15,
        },
        "民族": {
            "keywords": ["民族", "汉族", "回族", "藏族", "满族", "蒙古族"],
            "patterns": [r'民\s*族\s*[：:]\s*\S'],
            "max_chars": 10,
        },
        "入院方式": {
            "keywords": ["入院方式", "步行", "轮椅", "抬入", "急诊", "门诊"],
            "patterns": [r'入\s*院\s*方\s*式\s*[：:]'],
            "max_chars": 20,
        },
        "个人史": {
            "keywords": ["个人史", "吸烟", "饮酒", "过敏", "药物过敏", "食物过敏"],
            "patterns": [],
            "not_signals": ["家族", "遗传"],
        },

        # 影像科字段
        "影像表现": {
            "keywords": [
                "影像表现", "影像所见", "CT表现", "MRI表现", "超声所见",
                "高密度影", "低密度影", "等密度影", "混杂密度",
                "高信号", "低信号", "等信号", "混杂信号",
                "强化", "均匀强化", "不均匀强化", "环形强化",
                "结节", "肿块", "占位", "钙化", "囊变", "坏死",
                "积液", "肿大", "狭窄", "梗阻",
                "未见明显异常", "未见明显占位",
                "边界清楚", "边界不清", "形态规则", "形态不规则",
                "双肺纹理", "脑实质", "肝脏", "胆囊", "胰腺", "双肾",
            ],
            "patterns": [
                r'[左右双]\s*[肺肝肾脑]',  # 部位描述
                r'\d+\s*mm',  # 尺寸描述
                r'[Tt]\d+[Ww][Ii]',  # MRI 序列
            ],
        },
        "诊断意见": {
            "keywords": [
                "诊断意见", "报告意见", "印象", "超声提示",
                "考虑", "不除外", "建议复查", "建议进一步检查",
                "性质待定", "未见明显异常",
            ],
            "patterns": [
                r'[一二三四五六七八九十]\s*[\.、）)]',  # 编号诊断
            ],
        },
        "检查项目": {
            "keywords": [
                "检查项目", "CT平扫", "CT增强", "MRI平扫", "MRI增强",
                "DWI", "MRA", "CTA", "彩超", "钼靶", "骨密度",
                "胃肠造影", "超声检查",
            ],
            "max_chars": 50,
        },
    }

    # 字段关键词映射（用于从连续文本中提取字段内容）
    FIELD_KEYWORDS = {
        "姓名": ["姓名", "叫啥", "名字"],
        "性别": ["性别"],
        "年龄": ["年龄"],
        "民族": ["民族"],
        "婚姻状况": ["婚姻", "婚否", "已婚", "未婚"],
        "出生地": ["出生地", "籍贯"],
        "职业": ["职业"],
        "入院方式": ["入院方式", "怎么来的", "怎么入院"],
        "入院时间": ["入院时间", "什么时候来的", "哪天来的", "入院日期"],
        "病史陈述者": ["病史陈述者", "谁说的", "谁告诉"],
        "主诉": ["主诉", "主要症状", "主要表现", "不舒服", "来看病"],
        "现病史": ["现病史", "发病", "开始出现", "怎么得的"],
        "既往史": ["既往史", "以前", "过去", "曾有", "慢性"],
        "个人史": ["个人史", "吸烟", "饮酒", "过敏史"],
        "婚育史": ["婚育史", "结婚", "生育", "怀孕"],
        "家族史": ["家族史", "家族", "遗传", "父亲", "母亲"],
        "体格检查": ["体格检查", "查体", "体检", "体征"],
        "辅助检查": ["辅助检查", "做了检查", "检查结果", "化验"],
        "初步诊断": ["初步诊断", "诊断", "考虑是"],
        "诊疗经过": ["诊疗经过", "治疗经过", "怎么治的"],
        "出院情况": ["出院情况", "出院时", "恢复怎么样"],
        "出院医嘱": ["出院医嘱", "出院后", "出院注意"],
        "急救措施": ["急救措施", "抢救", "急救"],
        "用药情况": ["用药情况", "用了什么药", "用药"],
        "效果评估": ["效果评估", "效果怎么样", "效果"],
        "手术名称": ["手术名称", "做了什么手术", "手术"],
        "术前诊断": ["术前诊断"],
        "术后诊断": ["术后诊断"],
        "影像表现": ["影像表现", "片子", "CT表现", "MRI表现", "超声所见", "影像所见"],
        "诊断意见": ["诊断意见", "报告意见", "印象", "超声提示"],
        "建议": ["建议", "随访", "注意事项", "复查"],
        "检查项目": ["检查项目", "做了什么检查", "哪个部位"],
        "检查部位": ["检查部位", "哪个位置"],
        "检查方法": ["检查方法", "怎么做的"],
    }

    def __init__(self):
        # 预编译正则
        self.compiled_patterns = {}
        for field, info in self.FIELD_SIGNALS.items():
            self.compiled_patterns[field] = {
                "keywords": set(info["keywords"]),
                "patterns": [re.compile(p) for p in info.get("patterns", [])],
                "not_signals": set(info.get("not_signals", [])),
                "max_chars": info.get("max_chars", 999),
                "min_chars": info.get("min_chars", 0),
            }

    def classify(self, text):
        """
        对一段文本进行字段分类
        返回：(字段名, 置信度)
        """
        if not text or not text.strip():
            return None, 0.0

        text = text.strip()
        scores = {}

        for field, patterns in self.compiled_patterns.items():
            score = self._calculate_score(text, field, patterns)
            scores[field] = score

        # 返回得分最高的字段
        if not scores:
            return "主诉", 0.5

        best_field = max(scores, key=scores.get)
        best_score = scores[best_field]

        # 如果最高分太低，默认归为主诉
        if best_score < 0.3:
            return "主诉", best_score

        return best_field, best_score

    def _calculate_score(self, text, field, patterns):
        """计算文本属于某字段的得分"""
        score = 0.0
        keywords = patterns["keywords"]
        not_signals = patterns["not_signals"]

        # 1. 关键词匹配得分
        matched_keywords = 0
        for kw in keywords:
            if kw in text:
                matched_keywords += 1
        if matched_keywords > 0:
            score += min(matched_keywords * 0.15, 0.6)

        # 2. 正则模式匹配
        for pattern in patterns["patterns"]:
            if pattern.search(text):
                score += 0.2

        # 3. 排除信号（命中排除词扣分）
        for ns in not_signals:
            if ns in text:
                score -= 0.3

        # 4. 特殊规则：既往史加强
        boost_if_alone = patterns.get("boost_if_alone", False)
        if boost_if_alone and field == "既往史":
            # 慢性病 + 时间 直接加分
            chronic_diseases = ["高血压", "糖尿病", "冠心病", "脑梗", "心梗",
                                "心脏病", "肝炎", "结核", "肿瘤", "慢性"]
            for disease in chronic_diseases:
                if disease in text and re.search(r'[二三三四五六七八九十\d]+\s*[年月日年]', text):
                    score += 0.4
                    break
            # 有"否认""无"等词加分
            if any(w in text for w in ["否认", "否认", "无过敏", "无家族", "没有过敏"]):
                score += 0.3
        max_chars = patterns["max_chars"]
        min_chars = patterns["min_chars"]
        text_len = len(text)
        if text_len > max_chars:
            score -= 0.2
        if min_chars > 0 and text_len < min_chars:
            score -= 0.1

        # 短文本加分：主诉等短字段，纯症状描述应优先归类
        if max_chars <= 100 and 5 <= text_len <= max_chars:
            score += min(0.25, (max_chars - text_len) / max_chars * 0.3)

        # 5. 位置特征（出现在模板中的顺序）
        field_order = [
            "主诉", "现病史", "既往史", "体格检查", "辅助检查",
            "初步诊断", "诊疗经过", "出院情况", "出院医嘱",
            "急救措施", "用药情况", "效果评估"
        ]
        if field in field_order:
            position_score = (len(field_order) - field_order.index(field)) / len(field_order) * 0.1
            score += position_score

        return max(0.0, score)

    def classify_paragraphs(self, paragraphs):
        """
        对多段文本分别分类
        返回：[(字段名, 段落内容, 置信度), ...]
        """
        results = []
        for para in paragraphs:
            field, confidence = self.classify(para)
            results.append((field, para, confidence))
        return results

    def _extract_field_content(self, text, field):
        """
        从连续文本中提取指定字段的内容
        例：text="姓名张山，性别男，年龄53岁" → field="姓名" → 返回 "张山"
        """
        keywords = self.FIELD_KEYWORDS.get(field, [field])
        keywords_sorted = sorted(set(keywords), key=len, reverse=True)

        kw_pattern = '|'.join(re.escape(k) for k in keywords_sorted)
        # 字段结束边界：下一个字段关键词、句子结束、或文本结束
        boundary = r'(?=[，。！？；\n]|$)|(?=' + kw_pattern + r')'

        pattern = re.compile(kw_pattern + r'(.*?)' + boundary, re.DOTALL)
        matches = list(pattern.finditer(text))

        if not matches:
            return None

        # 取最后一个有实际内容的匹配（排除零宽度的 lookahead-only 匹配）
        for match in reversed(matches):
            content = match.group(1)
            if content is not None:
                content = content.strip()
                content = re.sub(r'^[：:是\s]+', '', content).strip()
                return content if content else None

        return None

    @staticmethod
    def _chinese_num_to_int(text):
        """将中文数字转换为整数（支持 0-999）"""
        cn_map = {'零': 0, '一': 1, '二': 2, '三': 3, '四': 4,
                  '五': 5, '六': 6, '七': 7, '八': 8, '九': 9,
                  '两': 2, '〇': 0}
        # 先尝试阿拉伯数字
        if text.isdigit():
            return int(text)
        result = 0
        current = 0
        for ch in text:
            if ch in cn_map:
                current = cn_map[ch]
            elif ch == '十':
                if current == 0:
                    current = 1
                result += current * 10
                current = 0
            elif ch == '百':
                if current == 0:
                    current = 1
                result += current * 100
                current = 0
            elif ch == '千':
                if current == 0:
                    current = 1
                result += current * 1000
                current = 0
        result += current
        return result

    def extract_basic_fields(self, text):
        """
        从连续语音文本中推断基础字段值（不需要用户明确说"姓名""性别"）
        利用中文说话习惯推断：
          - "我叫/我是/名字叫" → 姓名
          - "男/女/男性/女性" → 性别
          - "X岁/X年" → 年龄
          - "X族" → 民族
          - "已婚/未婚/离婚/丧偶" → 婚姻状况
          - "步行/轮椅/急诊入院" → 入院方式
          - "出生在X / 籍贯X" → 出生地
          - "X月X日/X月X号/X年X月X日入院" → 入院时间
        """
        result = {}

        # 姓名：我叫X / 名字叫X / 我是X / 患者叫X / 患者名叫X / 姓名：X
        # 先尝试显式字段（归一化后的文本）
        name_match = re.search(
            r'(?:姓名[：:\s]*|我叫|名字叫|名字是|患者名?叫|患者是)\s*([一-鿿]{2,4}?)(?=\s*[，,。]?\s*(?:性别|年龄|民族|婚姻|出生地|职业|入院|病史|主诉|现病史|[，,。\s]|$))',
            text
        )
        if name_match:
            result['姓名'] = name_match.group(1)
        else:
            # 启发式：文本开头是2-4个中文字符，后面紧跟字段关键词，可能是姓名
            head_name = re.match(
                r'^([\u4e00-\u9fff]{2,4})\s*[，,]?\s*(?=性别|年龄|民族|婚姻|出生地|职业|入院|病史|主诉|现病史)',
                text
            )
            if head_name:
                result['姓名'] = head_name.group(1)

        # 性别：男/女性，或"性别男/女"，或"男性/女性患者"
        gender_match = re.search(
            r'(?:性别\s*)?(男|女)(?:性|的)?(?:\s*患?者|,|，|。|$|\s)',
            text
        )
        if gender_match:
            result['性别'] = gender_match.group(1)

        # 年龄：X岁 / X年 / 中文数字+岁
        age_match = re.search(
            r'(\d{1,3})\s*(?:岁|年\s*[龄纪]|周\s*岁)',
            text
        )
        if age_match:
            result['年龄'] = age_match.group(1) + '岁'
        else:
            # 中文数字年龄：五十三岁、六十八岁
            cn_age_match = re.search(
                r'([零一二两三四五六七八九十百千]+)\s*岁',
                text
            )
            if cn_age_match:
                age_val = self._chinese_num_to_int(cn_age_match.group(1))
                if 0 < age_val <= 150:
                    result['年龄'] = str(age_val) + '岁'

        # 民族：X族
        ethnic_match = re.search(
            r'(汉|回|藏|满|蒙古|壮|维吾尔|苗|彝|土家|朝鲜|侗|瑶|白|土家|哈尼|哈萨克|黎|傈僳|佤|畲|高山|拉祜|水|东乡|纳西|景颇|柯尔克孜|土|达斡尔|仫佬|羌|布朗|撒拉|毛南|仡佬|锡伯|阿昌|普米|塔吉克|怒|乌孜别克|俄罗斯|鄂温克|德昂|保安|裕固|京|塔塔尔|独龙|鄂伦春|赫哲|门巴|珞巴|基诺)族',
            text
        )
        if ethnic_match:
            result['民族'] = ethnic_match.group(1) + '族'

        # 婚姻状况：已婚/未婚/离婚/丧偶
        marriage_match = re.search(
            r'(已婚|未婚|离婚|丧偶|再婚)',
            text
        )
        if marriage_match:
            result['婚姻状况'] = marriage_match.group(1)

        # 入院方式：必须是"关键词+入院"格式，避免把单独的"入院"误匹配
        # 使用捕获组提取关键词，确保是"XXX入院"而非单独的"入院"
        admission_match = re.search(
            r'(步行|轮椅|抬入|担架|急诊|门诊|转入)(入院|入\s*院)',
            text
        )
        if admission_match:
            result['入院方式'] = admission_match.group(1)

        # 出生地：出生在X / 籍贯X / 出生地X / 来自X / 老家X
        birth_match = re.search(
            r'(?:出生在|出生于|出生地[：:\s]*|籍贯|老家是|老家\s*|来自)\s*([一-鿿]{2,6}?)(?=[，,。\s]|$|职业|入院|婚姻|年龄|性别|民族|姓名|病史|主诉|现病)',
            text
        )
        if birth_match:
            result['出生地'] = birth_match.group(1)

        # 入院时间：X月X日/X月X号/X年X月X日 + 入院/住院
        # 模式1: "入院时间2024年7月24日" / "入院时间为7月24日" / "入院时间：2024年7月24日"
        admission_time_match = re.search(
            r'(?:入院\s*时间\s*[是为]?\s*[：:]?\s*|入院\s*[是为]?\s*)'
            r'(?:(\d{4})\s*年\s*)?(\d{1,2})\s*月\s*(\d{1,2})\s*[日号]',
            text
        )
        if admission_time_match:
            year = admission_time_match.group(1)
            month = admission_time_match.group(2)
            day = admission_time_match.group(3)
            if year:
                result['入院时间'] = f'{year}年{month}月{day}日'
            else:
                result['入院时间'] = f'{month}月{day}日'

        # 另一种模式：日期在前，入院在后
        # 如 "2024年7月24日入院" "7月24号住院"
        alt_match = re.search(
            r'(?:(\d{4})\s*年\s*)?(\d{1,2})\s*月\s*(\d{1,2})\s*[日号]'
            r'\s*(?:入院|住院|来院)',
            text
        )
        if alt_match and '入院时间' not in result:
            year = alt_match.group(1)
            month = alt_match.group(2)
            day = alt_match.group(3)
            if year:
                result['入院时间'] = f'{year}年{month}月{day}日'
            else:
                result['入院时间'] = f'{month}月{day}日'

        return result

    def fill_template(self, text, template_content):
        """
        智能填充模板
        1. 用上下文推断基础字段值（姓名、性别、年龄等）
        2. 分段并分类病历经度
        3. 基础字段从推断结果中取值，病历经度用分类内容
        4. 按模板字段顺序填充
        如果没有任何字段被填充，返回原文
        """
        paragraphs = [p.strip() for p in re.split(r'[。\n]+', text) if p.strip()]
        if not paragraphs:
            return template_content

        classified = self.classify_paragraphs(paragraphs)
        template_fields = self._extract_fields(template_content)

        # 第一步：用上下文推断基础字段
        inferred = self.extract_basic_fields(text)

        result = template_content
        field_filled = set()

        # 第二步：先用推断的基础字段填充
        BASIC_FIELDS = {"姓名", "性别", "年龄", "民族", "婚姻状况", "出生地", "职业",
                        "入院方式", "入院时间", "病史陈述者", "可靠程度"}
        for field in BASIC_FIELDS:
            if field in inferred and field in template_fields and field not in field_filled:
                result = self._replace_field(result, field, inferred[field])
                field_filled.add(field)

        # 第三步：病历经度用分类器结果填充
        for field, content, confidence in classified:
            if confidence < 0.2:
                continue
            std_field = self._standardize_field(field)
            if std_field in template_fields and std_field not in field_filled:
                # 主诉只填症状部分，去掉日期、入院等已由基础字段处理的内容
                if std_field == "主诉" and ('入院' in content or re.search(r'\d{4}\s*年', content)):
                    content = self._extract_chief_complaint(content)
                result = self._replace_field(result, std_field, content)
                field_filled.add(std_field)

        # 第四轮：关键词直接匹配（兜底）
        for template_field in template_fields:
            if template_field in field_filled:
                continue
            extracted = self._extract_field_content(text, template_field)
            if extracted:
                result = self._replace_field(result, template_field, extracted)
                field_filled.add(template_field)

        if not field_filled:
            return text

        return result

    def incremental_fill(self, new_text, template_content):
        """
        增量填充模板 —— 只填充空字段，不覆盖已有内容。
        用于多次录音场景：每次只处理新的 ASR 文本，保留已填好的字段。
        """
        from section_parser import SectionParser
        parser = SectionParser()

        # 归一化 ASR 文本（补全缺失的字段冒号）
        new_text = parser.normalize_asr_text(new_text)

        result = template_content
        template_fields = self._extract_fields(template_content)
        empty_fields = [f for f in template_fields if self._is_field_empty(result, f)]

        if not empty_fields:
            return result

        filled = set()
        BASIC_FIELDS = {"姓名", "性别", "年龄", "民族", "婚姻状况", "出生地", "职业",
                        "入院方式", "入院时间", "病史陈述者", "可靠程度"}

        # 1. 基础字段优先推断（姓名、性别、年龄等）—— 先于 parse，避免中文数字未转换
        inferred = self.extract_basic_fields(new_text)
        for field in BASIC_FIELDS:
            if field in inferred and field in empty_fields:
                result = self._replace_field(result, field, inferred[field])
                filled.add(field)

        # 2. 解析新文本中的显式字段标记（如"主诉：发热三天"）
        sections = parser.parse(new_text)
        for field, content in sections.items():
            std_field = self._standardize_field(field)
            if std_field in empty_fields and std_field not in filled and content.strip():
                result = self._replace_field(result, std_field, content.strip())
                filled.add(std_field)

        # 2. 分类器：对无显式标记的段落做智能分类
        # 移除已被 parser.parse 处理的文本片段，只对真正剩余的内容做分类
        remaining_text = new_text
        for field, content in sections.items():
            if content:
                remaining_text = remaining_text.replace(content, "")
        # 也移除字段关键词本身
        for kw in parser.sorted_keywords:
            remaining_text = remaining_text.replace(kw, "")
        # 清理标点和空白
        remaining_text = re.sub(r'[：:\s，,。、]+', ' ', remaining_text).strip()

        paragraphs = [p.strip() for p in re.split(r'[。\n]+', remaining_text) if p.strip()]
        if paragraphs:
            classified = self.classify_paragraphs(paragraphs)
            for field, content, confidence in classified:
                if confidence < 0.2:
                    continue
                std_field = self._standardize_field(field)
                if std_field in empty_fields and std_field not in filled:
                    if std_field == "主诉" and ('入院' in content or re.search(r'\d{4}\s*年', content)):
                        content = self._extract_chief_complaint(content)
                    if content.strip():
                        result = self._replace_field(result, std_field, content.strip())
                        filled.add(std_field)

        # 4. 关键词直接匹配（兜底，仅填空字段）
        for field in empty_fields:
            if field in filled:
                continue
            extracted = self._extract_field_content(new_text, field)
            if extracted:
                result = self._replace_field(result, field, extracted)
                filled.add(field)

        return result

    def _is_field_empty(self, template_text, field):
        """检查模板中某字段是否为空（无实际内容），支持同行多字段"""
        pattern = re.compile(
            re.escape(field) + r'[：: \t]*([^：:\n]*?)(?=\s*[\u4e00-\u9fff]{1,10}[：:]|\s*[\n]|\s*$)',
            re.MULTILINE
        )
        match = pattern.search(template_text)
        if not match:
            return True  # 字段不存在，视为空
        content = match.group(1).strip()
        return len(content) == 0

    def _extract_chief_complaint(self, text):
        """
        从 ASR 文本中提取纯症状内容（去除日期、入院等已由基础字段处理的部分）
        例：'2024年7月24日入院，发热咳嗽三天' → '发热咳嗽三天'
        """
        # 先去掉"日期+入院/住院"模式
        cleaned = re.sub(
            r'\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*[日号]\s*(?:入院|住院|来院)',
            '', text
        )
        # 再去掉"入院时间"前缀
        cleaned = re.sub(r'入院\s*时间\s*[是为：:]?\s*', '', cleaned)
        # 清理分隔符和空白
        cleaned = re.sub(r'^[，,、\s]+', '', cleaned)
        cleaned = re.sub(r'[，,、\s]+$', '', cleaned)
        return cleaned.strip()

    def _standardize_field(self, field):
        """标准化字段名"""
        aliases = {
            # 基本信息
            "姓名": "姓名", "性别": "性别", "年龄": "年龄",
            "民族": "民族", "婚姻状况": "婚姻状况", "出生地": "出生地",
            "职业": "职业", "入院方式": "入院方式", "入院时间": "入院时间",
            "病史陈述者": "病史陈述者", "可靠程度": "可靠程度",
            # 病史
            "主诉": "主诉", "现病史": "现病史", "既往史": "既往史",
            "个人史": "个人史", "婚育史": "婚育史", "家族史": "家族史",
            # 检查诊断
            "体格检查": "体格检查", "辅助检查": "辅助检查",
            "初步诊断": "初步诊断", "诊断依据": "诊断依据",
            "鉴别诊断": "鉴别诊断",
            # 诊疗
            "诊疗计划": "诊疗计划", "诊疗经过": "诊疗经过",
            "手术名称": "手术名称", "术前诊断": "术前诊断",
            "术中情况": "术中情况", "术后诊断": "术后诊断",
            "术后医嘱": "术后医嘱",
            # 影像
            "影像表现": "影像表现", "诊断意见": "诊断意见", "建议": "建议",
            "检查项目": "检查项目", "检查部位": "检查部位", "检查方法": "检查方法",
            "增强特征": "增强特征", "血管描述": "血管描述",
            "超声所见": "超声所见", "超声提示": "超声提示",
            "序列": "序列", "对比剂": "对比剂", "BI-RADS分级": "BI-RADS分级",
            # 其他
            "出院情况": "出院情况", "出院医嘱": "出院医嘱",
            "急救措施": "急救措施", "用药情况": "用药情况",
            "效果评估": "效果评估",
        }
        return aliases.get(field, field)

    def _extract_fields(self, template_content):
        """提取模板中的所有字段名（支持同行多个字段）"""
        fields = []
        seen = set()
        # 用 finditer 查找文本中所有"字段名："模式（支持同行多字段）
        for match in re.finditer(r'([^：:\s]{1,10})[：:\s]', template_content):
            field = match.group(1)
            if field in self.STANDARD_FIELDS and field not in seen:
                fields.append(self._standardize_field(field))
                seen.add(field)
        return fields

    def _replace_field(self, template_text, field, content):
        """替换模板字段（支持同行多字段）"""
        pattern = re.compile(
            r'(' + re.escape(field) + r'[：: \t]*)([^：:\n]*?)(?=\s*[\u4e00-\u9fff]{1,10}[：:]|\s*[\n]|\s*$)',
            re.MULTILINE
        )
        match = pattern.search(template_text)
        if match:
            # 检查是否是同行多字段（后面还有字段）
            after = template_text[match.end():]
            is_same_line = bool(re.match(r'\s*[\u4e00-\u9fff]{1,10}[：:]', after))
            
            if is_same_line:
                # 同行多字段：字段名：内容  + 间距
                replacement = f'{field}：{content}  '
                tail = after
            else:
                # 独占一行
                tail = template_text[match.end():]
                if tail.startswith('\n'):
                    tail = tail[1:]
                replacement = f'{field}：{content}\n'
            return template_text[:match.start()] + replacement + tail
        return template_text
