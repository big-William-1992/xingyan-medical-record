"""
病历 CRUD 路由
"""
import re
from fastapi import Request, Body, HTTPException
from server.singletons import get_db, get_feedback
from server.middleware import get_current_user


def register_routes(app):
    """注册病历路由"""

    @app.post("/api/records")
    async def save_record(request: Request, body: dict = Body(...)):
        """保存病历（按当前登录用户隔离）"""
        db = get_db()
        user = get_current_user(request)
        content = body.get("content", "").strip()
        if not content:
            return {"ok": False, "msg": "空内容"}
        m = re.search(r'姓名[：:]\s*([^\s　\n]{1,10})', content)
        patient_name = m.group(1).strip() if m else ""
        dept = body.get("department", "")
        record_id = body.get("id")
        if record_id:
            # 校验病历归属：只能更新自己的病历
            existing = db.get_record(record_id)
            if not existing:
                return {"ok": False, "msg": "病历不存在"}
            if existing.get("user_id") != user["user_id"] and user.get("role") != "admin":
                return {"ok": False, "msg": "无权修改他人的病历"}
            db.update_record(record_id, content=content)
        else:
            record_id = db.create_record(user["user_id"], patient_name, dept, "", content, "草稿")
        try:
            get_feedback().collect_corpus(content)
        except Exception as e:
            print(f"[Server] 语料收集失败: {e}")
        return {"ok": True, "id": record_id}

    @app.get("/api/records")
    async def list_records(request: Request):
        """病历列表（仅返回当前用户的病历）"""
        db = get_db()
        user = get_current_user(request)
        records = db.list_records(user_id=user["user_id"])
        return [{"id": r["id"], "patient_name": r.get("patient_name", ""),
                 "department": r.get("department", ""), "updated_at": r.get("updated_at", "")}
                for r in (records or [])[:50]]
