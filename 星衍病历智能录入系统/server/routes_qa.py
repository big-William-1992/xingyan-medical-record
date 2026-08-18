"""
知识图谱 + 纠错 + 填充路由
"""
from fastapi import Request, Body
from fastapi.responses import JSONResponse

from server.singletons import (
    get_asr, get_kg, get_qa, get_template_engine,
    get_corrector, get_classifier, get_db,
)
from cache_manager import get_cache


def register_routes(app, limiter):
    """注册知识图谱和纠错路由"""

    @app.post("/api/correct")
    async def correct_text(body: dict = Body(...)):
        """对文本执行纠错"""
        text = (body.get("text") or "").strip()
        if not text:
            return {"original": "", "corrected": "", "log": []}
        corrector = get_corrector()
        corrected, log = corrector.correct(text)
        return {"original": text, "corrected": corrected, "log": log}

    @app.post("/api/fill")
    async def fill_fields(body: dict = Body(...)):
        """将语音识别文本结构化填充到模板字段"""
        asr_text = body.get("text", "").strip()
        base_content = body.get("base", "").strip()
        dept = body.get("department", "内科")
        if not asr_text:
            return {"filled": base_content, "changed": False}
        if not base_content:
            te = get_template_engine()
            tpls = te.get_templates(dept)
            if tpls:
                base_content = tpls[0].get("content", "")
        if not base_content:
            return {"filled": asr_text, "changed": False}
        try:
            classifier = get_classifier()
            filled = classifier.incremental_fill(asr_text, base_content)
            return {"filled": filled, "changed": filled != base_content}
        except Exception as e:
            return {"filled": base_content + "\n" + asr_text, "changed": True, "error": str(e)}

    # ── 知识图谱路由（带限流）────────────────────────────

    @app.get("/api/kg/drug/{name}")
    @limiter.limit("30/minute")
    async def kg_drug(request: Request, name: str):
        """查询药物信息"""
        cache = get_cache()
        cache_key = f"drug:{name}"
        cached = cache.get(cache_key)
        if cached:
            return cached
        kg = get_kg()
        info = kg.get_drug_info(name)
        treats = kg.query_by_obj(name, "TREATED_BY")[:10] if info else []
        result = {"name": name, "info": info, "treats": treats}
        cache.set(cache_key, result, ttl=3600)
        return result

    @app.get("/api/kg/disease/{name}")
    @limiter.limit("30/minute")
    async def kg_disease(request: Request, name: str):
        """查询疾病信息"""
        cache = get_cache()
        cache_key = f"disease:{name}"
        cached = cache.get(cache_key)
        if cached:
            return cached
        kg = get_kg()
        entity = kg.entities.get(name, {})
        symptoms = kg.get_symptoms_for_disease(name)[:15]
        drugs = kg.get_drugs_for_disease(name)[:15]
        exams = kg.get_exams_for_disease(name)[:10]
        complicates = kg.query_by_subj(name, "COMPLICATES")[:10]
        dept = kg.query_by_subj(name, "BELONGS_TO")[:3]
        result = {
            "name": name,
            "desc": entity.get("描述", ""),
            "system": entity.get("系统", ""),
            "symptoms": symptoms,
            "drugs": drugs,
            "exams": exams,
            "complicates": complicates,
            "department": dept,
        }
        cache.set(cache_key, result, ttl=3600)
        return result

    @app.get("/api/kg/query")
    @limiter.limit("20/minute")
    async def kg_query(request: Request, q: str = ""):
        """知识图谱查询"""
        qa = get_qa()
        result = qa.answer(q)
        kg = qa.kg
        text = result.get("text", "")
        drug_details = []
        drug_names = [
            n for n, t in kg.entity_types.items()
            if t == "药物" and n in text and len(n) >= 3
        ]
        drug_names = sorted(set(drug_names), key=len, reverse=True)[:8]
        for name in drug_names:
            info = kg.get_drug_info(name)
            if info:
                drug_details.append({
                    "name": name,
                    "brand": info.get("商品名称", ""),
                    "generic": info.get("通用名称", ""),
                    "composition": info.get("主要成份", ""),
                    "indication": info.get("适应症", ""),
                    "dosage": info.get("用法用量", ""),
                    "contraindication": info.get("禁忌", ""),
                    "adverse": info.get("不良反应", ""),
                    "precaution": info.get("注意事项", ""),
                    "interaction": info.get("药物相互作用", ""),
                })
        result["drug_details"] = drug_details
        return result
