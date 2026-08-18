"""
单元测试：section_parser.py - 字段解析
"""
import pytest


class TestSectionParser:
    """字段解析测试"""

    def test_parse_basic(self):
        from section_parser import SectionParser
        sp = SectionParser()
        text = "主诉：发热三天\n现病史：患者三天前受凉\n既往史：无特殊"
        result = sp.parse(text)
        assert isinstance(result, dict)

    def test_extract_template_fields(self):
        from section_parser import SectionParser
        sp = SectionParser()
        template = "主诉：{主诉}\n现病史：{现病史}\n既往史：{既往史}"
        fields = sp._extract_template_fields(template)
        assert "主诉" in fields
        assert "现病史" in fields
        assert "既往史" in fields

    def test_replace_field_replaces_all(self):
        """_replace_field 应替换所有匹配"""
        from section_parser import SectionParser
        sp = SectionParser()
        # 模板格式：字段名：内容
        template = "主诉：{主诉}\n现病史：{现病史}\n主诉：{主诉}"
        result = sp._replace_field(template, "主诉", "发热三天")
        assert result.count("发热三天") == 2

    def test_fill_template(self):
        """fill_template 应将文本填入模板"""
        from section_parser import SectionParser
        sp = SectionParser()
        template = "主诉：{主诉}\n现病史：{现病史}"
        text = "发热三天，咳嗽两天"
        result = sp.fill_template(text, template)
        assert isinstance(result, str)
        assert "发热三天" in result

    def test_get_section_headers(self):
        from section_parser import SectionParser
        sp = SectionParser()
        headers = sp.get_section_headers()
        assert isinstance(headers, list)

