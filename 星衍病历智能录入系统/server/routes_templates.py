"""
模板、常用词、常用句路由
"""
import json
from fastapi import Request, Query, Body

from server.singletons import get_template_engine
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def register_routes(app):
    """注册模板相关路由"""

    @app.get("/api/templates")
    async def templates(dept: str = Query("内科")):
        te = get_template_engine()
        tpls = te.get_templates(dept)
        return [{"name": t["name"], "content": t["content"]} for t in tpls]

    @app.get("/api/templates/{dept}/{name}")
    async def template_content(dept: str, name: str):
        te = get_template_engine()
        content = te.get_template(dept, name)
        return {"content": content or ""}

    @app.get("/api/field-words/{field}")
    async def field_words(field: str):
        """获取字段的常用词"""
        fw_path = BASE_DIR / "field_words.json"
        try:
            with open(fw_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            field_data = data.get(field, {})
            terms = field_data.get("terms", {})
            if isinstance(terms, dict):
                sections = [{"title": k, "words": v[:15]} for k, v in terms.items()]
            elif isinstance(terms, list):
                sections = [{"title": "常用词", "words": terms[:15]}]
            else:
                sections = []
            return {"field": field, "sections": sections}
        except Exception:
            return {"field": field, "sections": []}

    @app.get("/api/presets/{field}")
    async def get_presets(field: str):
        presets_path = BASE_DIR / "field_presets.json"
        try:
            with open(presets_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return {"field": field, "presets": data.get(field, [])}
        except Exception:
            return {"field": field, "presets": []}

    @app.post("/api/presets/{field}")
    async def add_preset(field: str, body: dict = Body(...)):
        sentence = body.get("sentence", "").strip()
        if not sentence:
            return {"ok": False, "msg": "空内容"}
        presets_path = BASE_DIR / "field_presets.json"
        try:
            with open(presets_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception:
            data = {}
        if field not in data:
            data[field] = []
        if sentence not in data[field]:
            data[field].append(sentence)
        with open(presets_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return {"ok": True}
