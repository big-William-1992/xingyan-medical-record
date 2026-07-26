"""
模板引擎 - 管理各科室病历模板
"""
import json
import os


class TemplateEngine:
    def __init__(self, templates_dir=None):
        self.templates_dir = templates_dir or os.path.join(
            os.path.dirname(__file__), "templates"
        )
        self.templates = {}
        self.load_templates()

    def load_templates(self):
        """加载所有模板"""
        if not os.path.exists(self.templates_dir):
            os.makedirs(self.templates_dir)
            self._create_default_templates()
            return

        for filename in os.listdir(self.templates_dir):
            if filename.endswith('.json'):
                path = os.path.join(self.templates_dir, filename)
                with open(path, 'r', encoding='utf-8') as f:
                    dept = filename.replace('.json', '')
                    self.templates[dept] = json.load(f)

    def _create_default_templates(self):
        """创建默认模板（贴近真实医院病历格式）"""
        default_templates = {
            "内科": {
                "templates": [
                    {
                        "name": "入院记录",
                        "content": """姓名：    性别：    年龄：    入院时间：
主诉：
现病史：
既往史：
个人史：
婚育史：
家族史：
体格检查：
辅助检查：
初步诊断：
"""
                    },
                    {
                        "name": "首次病程记录",
                        "content": """日期/时间：
病例特点：
诊断依据：
鉴别诊断：
诊疗计划：
"""
                    },
                    {
                        "name": "日常病程记录",
                        "content": """日期：
患者情况：
查体：
辅助检查：
诊疗措施：
"""
                    },
                    {
                        "name": "出院记录",
                        "content": """入院日期：    出院日期：    住院天数：
入院诊断：
出院诊断：
诊疗经过：
出院情况：
出院医嘱：
"""
                    }
                ]
            },
            "外科": {
                "templates": [
                    {
                        "name": "术前记录",
                        "content": """术前诊断：
手术名称：
手术指征：
术前准备：
手术医师：
麻醉方式：
"""
                    },
                    {
                        "name": "手术记录",
                        "content": """手术日期：
手术名称：
术中所见：
手术过程：
术中出血：
术后诊断：
"""
                    },
                    {
                        "name": "术后病程",
                        "content": """术后诊断：
手术情况：
术后第一天：
术后医嘱：
"""
                    }
                ]
            }
        }

        for dept, data in default_templates.items():
            path = os.path.join(self.templates_dir, f"{dept}.json")
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

        self.templates = default_templates

    def get_departments(self):
        """获取所有科室列表"""
        return list(self.templates.keys())

    def get_templates(self, department):
        """获取某科室的所有模板"""
        dept_data = self.templates.get(department, {})
        return dept_data.get("templates", [])

    def get_template(self, department, template_name):
        """获取指定模板内容"""
        templates = self.get_templates(department)
        for t in templates:
            if t["name"] == template_name:
                return t["content"]
        return ""

    def add_template(self, department, name, content):
        """添加自定义模板"""
        if department not in self.templates:
            self.templates[department] = {"templates": []}

        self.templates[department]["templates"].append({
            "name": name,
            "content": content
        })

        path = os.path.join(self.templates_dir, f"{department}.json")
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(self.templates[department], f, ensure_ascii=False, indent=2)
