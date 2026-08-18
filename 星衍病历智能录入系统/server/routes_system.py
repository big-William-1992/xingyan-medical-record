"""
系统状态 + 离线模式路由
"""
import re
import time
import json
from pathlib import Path
from fastapi import Request, Query, Body

from server.singletons import get_asr, get_kg, get_template_engine, get_db
from server.middleware import get_current_user

BASE_DIR = Path(__file__).resolve().parent.parent


def register_routes(app):
    """注册系统路由"""

    @app.get("/api/stats")
    async def stats():
        """系统状态统计"""
        asr = get_asr()
        kg = get_kg()
        hw_count = len(asr._current_hotwords.split()) if asr and asr._current_hotwords else 0
        return {
            "hotwords": hw_count,
            "kg_entities": len(kg.entities),
            "kg_relations": len(kg.relations),
            "drug_inserts": len(kg.drug_inserts),
            "asr_ready": bool(asr) and asr.is_ready(),
        }

    @app.get("/api/departments")
    async def departments():
        return ["全科", "内科", "外科", "妇产科", "儿科"]

    @app.get("/api/offline/package")
    async def offline_package(request: Request, dept: str = Query("内科")):
        """预加载离线数据包"""
        user = get_current_user(request)
        te = get_template_engine()
        templates = te.get_templates(dept)
        template_list = [{"name": t["name"], "content": t["content"]} for t in templates]

        field_words = {}
        try:
            fw_path = BASE_DIR / "field_words.json"
            with open(fw_path, 'r', encoding='utf-8') as f:
                field_words = json.load(f)
        except Exception as e:
            print(f"[Server] 加载 field_words 失败: {e}")

        presets = {}
        try:
            pp_path = BASE_DIR / "field_presets.json"
            with open(pp_path, 'r', encoding='utf-8') as f:
                presets = json.load(f)
        except Exception as e:
            print(f"[Server] 加载 field_presets 失败: {e}")

        db = get_db()
        records = db.list_records(user_id=user["user_id"]) or []
        patients = [{"id": r["id"], "patient_name": r.get("patient_name", ""),
                     "department": r.get("department", ""), "updated_at": r.get("updated_at", ""),
                     "content": r.get("content", "")}
                    for r in records[:50]]

        return {
            "ok": True,
            "timestamp": int(time.time()),
            "department": dept,
            "templates": template_list,
            "field_words": field_words,
            "presets": presets,
            "patients": patients,
        }

    @app.post("/api/offline/sync")
    async def offline_sync(request: Request, body: dict = Body(...)):
        """同步离线记录"""
        user = get_current_user(request)
        records = body.get("records", [])
        if not records or not isinstance(records, list):
            return {"ok": False, "msg": "无同步数据"}

        db = get_db()
        synced = []
        failed = []

        for item in records:
            try:
                content = (item.get("content") or "").strip()
                if not content:
                    continue
                m = re.search(r'姓名[：:]\s*([^\s\n]{1,10})', content)
                patient_name = m.group(1).strip() if m else ""
                dept = item.get("department", "")
                record_id = db.create_record(user["user_id"], patient_name, dept, "", content, "草稿")
                synced.append({"local_id": item.get("local_id", ""), "server_id": record_id, "ok": True})
            except Exception as e:
                failed.append({"local_id": item.get("local_id", ""), "error": str(e)})

        return {"ok": True, "synced": synced, "failed": failed}

