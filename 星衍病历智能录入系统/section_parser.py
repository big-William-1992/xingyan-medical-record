"""
病历结构解析器
从连续的语音识别文本中，自动识别并拆分出病历的各个部分
"""
import re


class SectionParser:
    """
    病历结构解析
    输入：一段连续的语音识别文本
    输出：按病历结构拆分的 dict
    """

    # 病历各部分的触发关键词
    SECTION_KEYWORDS = {
        "姓名": ["姓名", "姓名:", "姓名：", "名字", "称呼", "名叫"],
        "性别": ["性别", "性别:", "性别：", "男/女", "男性/女性"],
        "年龄": ["年龄", "年龄:", "年龄：", "岁数", "几岁"],
        "民族": ["民族", "民族:", "民族：", "汉族", "回族"],
        "婚姻状况": ["婚姻状况", "婚姻状况:", "婚姻状况：", "婚姻", "婚况"],
        "出生地": ["出生地", "出生地:", "出生地：", "籍贯", "籍贯:" ,"籍贯：", "生于", "老家"],
        "职业": ["职业", "职业:", "职业：", "工作", "从事"],
        "入院时间": ["入院时间", "入院时间:", "入院时间：", "入院日期", "住院时间"],
        "入院方式": ["入院方式", "入院方式:", "入院方式：", "入院途径"],
        "病史陈述者": ["病史陈述者", "病史陈述者:", "病史陈述者：", "陈述者", "讲述者"],
        "可靠程度": ["可靠程度", "可靠程度:", "可靠程度：", "可靠性", "可信度"],
        "主诉": ["主诉", "主诉:", "主诉：", "主要症状", "主要表现"],
        "现病史": ["现病史", "现病史:", "现病史：", "发病经过", "疾病过程"],
        "既往史": ["既往史", "既往史:", "既往史：", "既往病史", "过去病史", "既往"],
        "个人史": ["个人史", "个人史:", "个人史：", "个人病史", "个人"],
        "婚育史": ["婚育史", "婚育史:", "婚育史：", "婚育病史", "婚育"],
        "家族史": ["家族史", "家族史:", "家族史：", "家族病史", "家族遗传"],
        "体格检查": ["体格检查", "体格检查:", "体格检查：", "查体", "体检", "体征", "检查发现"],
        "辅助检查": ["辅助检查", "辅助检查:", "辅助检查：", "实验室检查", "检查结果", "化验", "影像"],
        "初步诊断": ["初步诊断", "初步诊断:", "初步诊断：", "诊断", "诊断意见"],
        "诊疗经过": ["诊疗经过", "诊疗经过:", "诊疗经过：", "治疗经过", "处理"],
        "出院情况": ["出院情况", "出院情况:", "出院情况：", "出院时情况"],
        "出院医嘱": ["出院医嘱", "出院医嘱:", "出院医嘱：", "出院指导", "随访"],
        "日期": ["日期", "日期:", "日期：", "时间"],
        "患者情况": ["患者情况", "患者情况:", "患者情况：", "病情"],
        "处理意见": ["处理意见", "处理意见:", "处理意见：", "治疗方案", "处理"],
        "术前诊断": ["术前诊断", "术前诊断:", "术前诊断："],
        "手术名称": ["手术名称", "手术名称:", "手术名称：", "术式"],
        "术中情况": ["术中情况", "术中情况:", "术中情况：", "术中所见", "手术过程"],
        "术后诊断": ["术后诊断", "术后诊断:", "术后诊断："],
        "术后医嘱": ["术后医嘱", "术后医嘱:", "术后医嘱：", "术后处理"],
        "影像表现": ["影像表现", "影像表现:", "影像表现：", "影像所见", "影像描述"],
        "诊断意见": ["诊断意见", "诊断意见:", "诊断意见：", "报告意见", "印象"],
        "建议": ["建议", "建议:", "建议：", "处理意见", "进一步检查"],
        "急救措施": ["急救措施", "急救措施:", "急救措施：", "抢救措施", "急救"],
        "用药情况": ["用药情况", "用药情况:", "用药情况：", "用药", "药物"],
        "效果评估": ["效果评估", "效果评估:", "效果评估：", "评估", "效果"],
        "麻醉方式": ["麻醉方式", "麻醉方式:", "麻醉方式：", "麻醉"],
        "手术医师": ["手术医师", "手术医师:", "手术医师：", "术者", "主刀"],
        "手术日期": ["手术日期", "手术日期:", "手术日期：", "手术时间"],
        "术中所见": ["术中所见", "术中所见:", "术中所见：", "术中见"],
        "手术过程": ["手术过程", "手术过程:", "手术过程：", "手术步骤"],
        "术中出血": ["术中出血", "术中出血:", "术中出血：", "出血量"],
        # 影像科字段
        "检查项目": ["检查项目", "检查项目:", "检查项目："],
        "检查部位": ["检查部位", "检查部位:", "检查部位："],
        "检查方法": ["检查方法", "检查方法:", "检查方法："],
        "增强特征": ["增强特征", "增强特征:", "增强特征："],
        "血管描述": ["血管描述", "血管描述:", "血管描述："],
        "超声所见": ["超声所见", "超声所见:", "超声所见："],
        "超声提示": ["超声提示", "超声提示:", "超声提示："],
        # 妇产科字段
        "月经史": ["月经史", "月经史:", "月经史："],
        "专科检查": ["专科检查", "专科检查:", "专科检查：", "专科情况"],
        "分娩时间": ["分娩时间", "分娩时间:", "分娩时间："],
        "孕产次": ["孕产次", "孕产次:", "孕产次："],
        "孕周": ["孕周", "孕周:", "孕周："],
        "分娩方式": ["分娩方式", "分娩方式:", "分娩方式："],
        "产程经过": ["产程经过", "产程经过:", "产程经过：", "产程"],
        "胎儿情况": ["胎儿情况", "胎儿情况:", "胎儿情况："],
        "新生儿评分": ["新生儿评分", "新生儿评分:", "新生儿评分：", "阿普加评分"],
        "胎盘胎膜": ["胎盘胎膜", "胎盘胎膜:", "胎盘胎膜："],
        "产后出血量": ["产后出血量", "产后出血量:", "产后出血量："],
        "会阴情况": ["会阴情况", "会阴情况:", "会阴情况："],
        "产后处理": ["产后处理", "产后处理:", "产后处理："],
        # 儿科字段
        "出生史": ["出生史", "出生史:", "出生史：", "出生情况"],
        "喂养史": ["喂养史", "喂养史:", "喂养史：", "喂养情况"],
        "生长发育史": ["生长发育史", "生长发育史:", "生长发育史：", "发育史"],
        "预防接种史": ["预防接种史", "预防接种史:", "预防接种史：", "接种史"],
        "患儿情况": ["患儿情况", "患儿情况:", "患儿情况："],
        # 中医字段
        "中医四诊": ["中医四诊", "中医四诊:", "中医四诊：", "四诊", "四诊合参"],
        "望诊": ["望诊", "望诊:", "望诊："],
        "闻诊": ["闻诊", "闻诊:", "闻诊："],
        "问诊": ["问诊", "问诊:", "问诊："],
        "切诊": ["切诊", "切诊:", "切诊："],
        "舌象": ["舌象", "舌象:", "舌象：", "舌质", "舌苔"],
        "脉象": ["脉象", "脉象:", "脉象：", "脉"],
        "辨证分析": ["辨证分析", "辨证分析:", "辨证分析：", "辨证", "八纲辨证", "脏腑辨证"],
        "证型": ["证型", "证型:", "证型：", "辨证分型"],
        "中医诊断": ["中医诊断", "中医诊断:", "中医诊断："],
        "中医病名": ["中医病名", "中医病名:", "中医病名：", "病名"],
        "治法": ["治法", "治法:", "治法：", "治疗法则", "治则"],
        "方药": ["方药", "方药:", "方药：", "处方", "方剂", "代表方剂"],
        "中医鉴别": ["中医鉴别", "中医鉴别:", "中医鉴别：", "类证鉴别"],
    }

    # 模板字段映射（关键词 → 标准字段名）
    FIELD_ALIASES = {
        "姓名": "姓名",
        "性别": "性别",
        "年龄": "年龄",
        "民族": "民族",
        "婚姻状况": "婚姻状况",
        "出生地": "出生地",
        "职业": "职业",
        "入院时间": "入院时间",
        "入院方式": "入院方式",
        "病史陈述者": "病史陈述者",
        "可靠程度": "可靠程度",
        "主诉": "主诉",
        "现病史": "现病史",
        "既往史": "既往史",
        "个人史": "个人史",
        "婚育史": "婚育史",
        "家族史": "家族史",
        "体格检查": "体格检查",
        "辅助检查": "辅助检查",
        "初步诊断": "初步诊断",
        "诊疗经过": "诊疗经过",
        "出院情况": "出院情况",
        "出院医嘱": "出院医嘱",
        "日期": "日期",
        "患者情况": "患者情况",
        "处理意见": "处理意见",
        "术前诊断": "术前诊断",
        "手术名称": "手术名称",
        "术中情况": "术中情况",
        "术后诊断": "术后诊断",
        "术后医嘱": "术后医嘱",
        "影像表现": "影像表现",
        "诊断意见": "诊断意见",
        "建议": "建议",
        "急救措施": "急救措施",
        "用药情况": "用药情况",
        "效果评估": "效果评估",
        "麻醉方式": "麻醉方式",
        "手术医师": "手术医师",
        "手术日期": "手术日期",
        "术中所见": "术中所见",
        "手术过程": "手术过程",
        "术中出血": "术中出血",
        "检查项目": "检查项目",
        "检查部位": "检查部位",
        "检查方法": "检查方法",
        "增强特征": "增强特征",
        "血管描述": "血管描述",
        "超声所见": "超声所见",
        "超声提示": "超声提示",
        # 妇产科
        "月经史": "月经史",
        "专科检查": "专科检查",
        "分娩时间": "分娩时间",
        "孕产次": "孕产次",
        "孕周": "孕周",
        "分娩方式": "分娩方式",
        "产程经过": "产程经过",
        "胎儿情况": "胎儿情况",
        "新生儿评分": "新生儿评分",
        "胎盘胎膜": "胎盘胎膜",
        "产后出血量": "产后出血量",
        "会阴情况": "会阴情况",
        "产后处理": "产后处理",
        # 儿科
        "出生史": "出生史",
        "喂养史": "喂养史",
        "生长发育史": "生长发育史",
        "预防接种史": "预防接种史",
        "患儿情况": "患儿情况",
        # 中医
        "中医四诊": "中医四诊",
        "望诊": "望诊",
        "闻诊": "闻诊",
        "问诊": "问诊",
        "切诊": "切诊",
        "舌象": "舌象",
        "脉象": "脉象",
        "辨证分析": "辨证分析",
        "证型": "证型",
        "中医诊断": "中医诊断",
        "中医病名": "中医病名",
        "治法": "治法",
        "方药": "方药",
        "中医鉴别": "中医鉴别",
    }

    def __init__(self):
        # 构建关键词 → 标准字段名的反向映射
        self.keyword_to_field = {}
        for field, keywords in self.SECTION_KEYWORDS.items():
            for kw in keywords:
                self.keyword_to_field[kw] = field

        # 按关键词长度降序排列（优先匹配长的关键词）
        self.sorted_keywords = sorted(
            self.keyword_to_field.keys(),
            key=len,
            reverse=True
        )

    def normalize_asr_text(self, text):
        """
        归一化 ASR 文本中的字段标记。
        语音识别结果常缺少冒号分隔符（如"主诉发热三天"而非"主诉：发热三天"），
        此方法在字段关键词后自动插入冒号，使解析器能正确识别字段边界。
        """
        if not text:
            return text
        # 仅对明确的病历字段名做归一化（避免误伤普通词汇如"建议""处理"）
        field_keywords = [
            '姓名', '性别', '年龄', '民族', '婚姻状况', '出生地', '职业',
            '入院时间', '入院方式', '病史陈述者', '可靠程度',
            '主诉', '现病史', '既往史', '个人史', '婚育史', '家族史',
            '体格检查', '辅助检查', '初步诊断', '诊疗经过', '诊疗计划',
            '鉴别诊断', '出院情况', '出院医嘱',
            '术前诊断', '手术名称', '术中情况', '术后诊断', '术后医嘱',
            '影像表现', '诊断意见', '影像所见',
            '检查项目', '检查部位', '检查方法', '增强特征', '血管描述',
            '超声所见', '超声提示',
            '月经史', '专科检查', '分娩时间', '孕产次', '分娩方式',
            '产程经过', '胎儿情况', '新生儿评分', '胎盘胎膜',
            '产后出血量', '会阴情况', '产后处理',
            '出生史', '喂养史', '生长发育史', '预防接种史', '患儿情况',
        ]
        for kw in sorted(field_keywords, key=len, reverse=True):
            # 情况1：字段关键词后面直接跟中文内容（无冒号/空格/换行分隔）时，插入冒号
            text = re.sub(
                re.escape(kw) + r'(?![：:\s，,。])(?=[\u4e00-\u9fff])',
                kw + '：',
                text
            )
            # 情况2：字段关键词后跟逗号/空格再跟内容（如"性别，男"），替换分隔符为冒号
            text = re.sub(
                re.escape(kw) + r'[，,\s]+(?=[\u4e00-\u9fff])',
                kw + '：',
                text
            )
        return text

    def parse(self, text):
        """
        解析病历文本
        返回：dict {字段名: 内容}
        """
        if not text or not text.strip():
            return {}

        # 归一化字段标记（处理 ASR 缺少冒号的情况）
        text = self.normalize_asr_text(text)

        sections = {}
        remaining = text.strip()

        # 在文本中找到所有字段边界
        boundaries = self._find_boundaries(remaining)

        if not boundaries:
            # 没有找到任何字段标记，整段文本作为“主诉”或默认字段
            sections["主诉"] = remaining.strip()
            return sections
        
        # 检查第一个边界之前是否有有意义的内容
        # 如果第一个边界之前只有基本信息（姓名等），不作为主诉
        first_boundary_pos = boundaries[0][1]
        pre_text = remaining[:first_boundary_pos].strip()
        if pre_text:
            # 去掉标点后检查是否只是姓名（2-4个中文字符）
            pre_clean = re.sub(r'[，,。、\s]+', '', pre_text)
            is_name_only = re.match(r'^[\u4e00-\u9fff]{2,4}$', pre_clean)
            if not is_name_only:
                sections["主诉"] = pre_text

        # 按边界拆分
        for i, (field_name, start_pos) in enumerate(boundaries):
            # 找到下一个边界的位置
            if i + 1 < len(boundaries):
                end_pos = boundaries[i + 1][1]
            else:
                end_pos = len(remaining)

            # 用正则精确匹配字段关键词及其后的冒号/空格
            # （修复：原代码用 split('\n')[0] 取关键词，单行文本时会把整段当关键词导致内容为空）
            kw_match = re.match(
                r'(' + '|'.join(re.escape(k) for k in self.sorted_keywords) + r')[：: \t]*',
                remaining[start_pos:end_pos]
            )
            if kw_match:
                content_start = start_pos + kw_match.end()
            else:
                # 回退：用换行分割
                keyword = remaining[start_pos:end_pos].split('\n')[0].strip()
                content_start = start_pos + len(keyword)

            content = remaining[content_start:end_pos].strip()
            # 去掉开头的冒号、空格、逗号等
            content = re.sub(r'^[：:\s，,。、]+', '', content)
            # 去掉尾部的标点
            content = re.sub(r'[，,。、；;]+$', '', content)

            if content:
                # 标准化字段名
                standard_field = self.FIELD_ALIASES.get(field_name, field_name)
                sections[standard_field] = content

        return sections

    def _find_boundaries(self, text):
        """
        在文本中找到所有病历字段的边界位置
        返回：[(字段名, 起始位置), ...]
        """
        boundaries = []
        found_positions = []
        # 记录已被占用的字符区间，避免子串冲突（如“入院时间”和“时间”）
        occupied_ranges = []

        for keyword in self.sorted_keywords:
            # 边界判定：关键词后必须紧跟冒号/空格（normalize_asr_text 已保证标准字段词后补冒号）；
            # 无冒号时要求关键词前有分隔符（行首/换行/空白/逗号），
            # 避免句中出现的词（如"否认家族遗传病史"里的"家族遗传"）被误判为字段边界
            pattern = re.compile(
                r'(?:(?<![\u4e00-\u9fff])' + re.escape(keyword) + r'[：: \t]+'
                r'|(?<![\u4e00-\u9fff])' + re.escape(keyword) + r'[：:]'
                r'|' + re.escape(keyword) + r'[：:])'
            )
            for match in pattern.finditer(text):
                pos = match.start()
                end_pos = match.end()
                # 检查是否与已占用的区间重叠
                overlap = False
                for occ_start, occ_end in occupied_ranges:
                    if pos < occ_end and end_pos > occ_start:
                        overlap = True
                        break
                if not overlap and pos not in found_positions:
                    found_positions.append(pos)
                    field_name = self.keyword_to_field[keyword]
                    boundaries.append((field_name, pos))
                    occupied_ranges.append((pos, end_pos))
                    break  # 每个关键词只匹配一次

        # 按位置排序
        boundaries.sort(key=lambda x: x[1])
        return boundaries

    def fill_template(self, text, template_content):
        """
        将识别文本按模板格式结构化填充
        返回：格式化后的完整病历文本
        """
        # 先尝试解析是否有明确的字段标记
        sections = self.parse(text)

        if sections:
            # 有明确字段标记，按标记填充
            return self._fill_by_sections(template_content, sections)
        else:
            # 没有明确标记，按内容段落智能分配到模板字段
            return self._fill_by_paragraphs(template_content, text)

    def _fill_by_sections(self, template_content, sections):
        """按解析出的字段填充模板"""
        result = template_content
        for field, content in sections.items():
            result = self._replace_field(result, field, content)
        return result

    def _fill_by_paragraphs(self, template_content, text):
        """按段落顺序分配到模板字段（用户没说"主诉""现病史"时用）"""
        # 按换行分段
        paragraphs = [p.strip() for p in text.split('\n') if p.strip()]
        if not paragraphs:
            return template_content

        # 提取模板中的所有字段（按顺序）
        template_fields = self._extract_template_fields(template_content)

        result = template_content
        for i, field in enumerate(template_fields):
            if i < len(paragraphs):
                content = paragraphs[i]
                result = self._replace_field(result, field, content)
            # 如果段落比字段多，剩余的合并到最后一个字段

        return result

    # 预编译字段替换正则
    _FIELD_REPLACE_RE = re.compile(r'([^：:\s]+)[：: \t]*([^\n]*)', re.MULTILINE)

    def _replace_field(self, template_text, field, content):
        """替换模板中指定字段的内容（替换所有匹配位置）"""
        def _replacer(m):
            field_name = m.group(1)
            if field_name == field:
                return f"{field}：{content}"
            return m.group(0)
        return self._FIELD_REPLACE_RE.sub(_replacer, template_text)

    def _extract_template_fields(self, template_content):
        """从模板内容中提取所有字段名（按出现顺序，去重）"""
        fields = []
        seen = set()
        lines = template_content.split('\n')
        for line in lines:
            line = line.strip()
            if not line:
                continue
            match = re.match(r'^([^：:\s]+)[：:\s]', line)
            if match:
                field_name = match.group(1)
                if field_name in self.FIELD_ALIASES and field_name not in seen:
                    seen.add(field_name)
                    fields.append(field_name)
        return fields

    def get_section_headers(self):
        """获取所有支持的病历字段名"""
        return list(self.FIELD_ALIASES.keys())

    def suggest_sections(self, text):
        """
        分析文本，建议可以拆分的病历部分
        返回：检测到的字段列表
        """
        found_sections = []
        text_lower = text.lower()

        for keyword, field in self.keyword_to_field.items():
            if keyword in text and field not in found_sections:
                found_sections.append(field)

        return found_sections


class SmartDictation:
    """
    智能语音录入
    结合 SectionParser，实现边说边结构化
    """

    def __init__(self, section_parser=None):
        self.parser = section_parser or SectionParser()
        self.current_section = None
        self.sections = {}

    def process_chunk(self, chunk_text):
        """
        处理语音识别的一段文本（实时模式）
        自动检测是否提到了新的病历部分
        """
        detected = self.parser.suggest_sections(chunk_text)

        if detected:
            # 如果有新字段被检测到，更新当前字段
            if detected[-1] not in self.sections:
                self.current_section = detected[-1]

        # 将内容累加到当前字段
        if self.current_section:
            if self.current_section not in self.sections:
                self.sections[self.current_section] = ""
            self.sections[self.current_section] += chunk_text

        return self.current_section, self.sections

    def get_structured_text(self):
        """将结构化内容转换为可读的病历文本"""
        lines = []
        for field, content in self.sections.items():
            lines.append(f"{field}：{content}")
        return "\n\n".join(lines)

    def reset(self):
        """重置状态"""
        self.current_section = None
        self.sections = {}
