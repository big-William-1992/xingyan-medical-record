#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
星衍AI · 前后端分离后端服务
FastAPI + WebSocket，提供 ASR / KG / 模板 / 病历 CRUD
启动: python app_server.py
前端: http://localhost:8765
"""
import os
import sys
import json
import time
import tempfile
import wave
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query, Body, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from cache_manager import get_cache

# ─── 项目路径 ───
BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR))

# ─── 延迟导入业务模块（避免启动时加载过慢）───
_asr = None
_kg = None
_qa = None
_template_engine = None
_corrector = None
_feedback = None
_db = None

def get_asr():
    global _asr
    if _asr is None:
        from asr_engine import ASREngine
        _asr = ASREngine(model_path=str(BASE_DIR / "model"))
    return _asr

def get_kg():
    # 复用 get_qa() 的实例，避免知识图谱被加载两遍
    return get_qa().kg

def get_qa():
    global _qa, _kg
    if _qa is None:
        from knowledge_qa import KnowledgeQA
        _qa = KnowledgeQA()
        _kg = _qa.kg
    return _qa

def get_template_engine():
    global _template_engine
    if _template_engine is None:
        from template_engine import TemplateEngine
        _template_engine = TemplateEngine()
    return _template_engine

def get_corrector():
    global _corrector
    if _corrector is None:
        from corrector import Corrector
        from rule_engine import RuleEngine
        _corrector = Corrector(rule_engine=RuleEngine())
    return _corrector

def get_feedback():
    global _feedback
    if _feedback is None:
        from correction_feedback import CorrectionFeedback
        _feedback = CorrectionFeedback()
    return _feedback

def get_db():
    global _db
    if _db is None:
        from database import Database
        _db = Database()
    return _db

# ─── FastAPI App ───
import logging
from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# 配置日志审计
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('audit.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('medical_record_audit')

# 请求频率限制
limiter = Limiter(key_func=get_remote_address)

app = FastAPI(title="星衍AI · 智能病历录入", version="2.0")
app.state.limiter = limiter

# CORS 配置：支持本机和局域网访问
ALLOWED_ORIGINS = [
    "http://localhost:8765",
    "http://localhost:3000",
    "http://127.0.0.1:8765",
    "http://127.0.0.1:3000",
]

# 动态添加局域网 IP 段（192.168.x.x, 10.x.x.x, 172.16-31.x.x）
def get_lan_origins():
    """生成局域网允许的源"""
    origins = []
    # 常见局域网段
    for i in range(1, 255):
        origins.append(f"http://192.168.{i}.1:8765")  # 路由器网关
        origins.append(f"http://192.168.1.{i}:8765")   # 常见家庭网络
        origins.append(f"http://10.0.0.{i}:8765")      # 常见企业网络
    return origins

# 合并所有允许的源
ALL_ALLOWED_ORIGINS = ALLOWED_ORIGINS + get_lan_origins()

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALL_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    logger.warning(f"Rate limit exceeded: {request.client.host}")
    return JSONResponse(
        status_code=429,
        content={"detail": "请求过于频繁，请稍后再试"}
    )

@app.middleware("http")
async def audit_middleware(request: Request, call_next):
    """审计中间件：记录所有API请求"""
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    
    logger.info(
        f"{request.method} {request.url.path} - "
        f"Status: {response.status_code} - "
        f"Client: {request.client.host} - "
        f"Time: {process_time:.3f}s"
    )
    return response

# 静态文件（前端）
FRONTEND_DIR = BASE_DIR / "frontend"
FRONTEND_DIR.mkdir(exist_ok=True)

@app.get("/audio-processor.js")
async def serve_audio_processor():
    """AudioWorklet 处理器文件"""
    return FileResponse(FRONTEND_DIR / "audio-processor.js", media_type="application/javascript")

# ═══════════════════════════════════════════════════
# REST API
# ═══════════════════════════════════════════════════

@app.get("/")
async def index():
    return FileResponse(FRONTEND_DIR / "index.html")

@app.get("/api/stats")
async def stats():
    """系统状态统计"""
    asr = get_asr()
    kg = get_kg()
    hw_count = len(asr._current_hotwords.split()) if asr._current_hotwords else 0
    return {
        "hotwords": hw_count,
        "kg_entities": len(kg.entities),
        "kg_relations": len(kg.relations),
        "drug_inserts": len(kg.drug_inserts),
        "asr_ready": asr.is_ready(),
    }

@app.get("/api/departments")
async def departments():
    return ["全科", "内科", "外科", "妇产科", "儿科"]

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

@app.get("/api/kg/drug/{name}")
@limiter.limit("30/minute")
async def kg_drug(request: Request, name: str):
    """查询药物信息（限制：30次/分钟）"""
    cache = get_cache()
    cache_key = f"drug:{name}"
    
    # 尝试从缓存获取
    cached_result = cache.get(cache_key)
    if cached_result:
        return cached_result
    
    # 查询数据库
    kg = get_kg()
    info = kg.get_drug_info(name)
    treats = kg.query_by_obj(name, "TREATED_BY")[:10] if info else []
    result = {"name": name, "info": info, "treats": treats}
    
    # 缓存结果（1小时）
    cache.set(cache_key, result, ttl=3600)
    
    return result

@app.get("/api/kg/disease/{name}")
@limiter.limit("30/minute")
async def kg_disease(request: Request, name: str):
    """查询疾病信息（限制：30次/分钟）"""
    cache = get_cache()
    cache_key = f"disease:{name}"
    
    # 尝试从缓存获取
    cached_result = cache.get(cache_key)
    if cached_result:
        return cached_result
    
    # 查询数据库
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
    
    # 缓存结果（1小时）
    cache.set(cache_key, result, ttl=3600)
    
    return result

@app.get("/api/kg/query")
@limiter.limit("20/minute")
async def kg_query(request: Request, q: str = Query(...)):
    """知识图谱查询（限制：20次/分钟）"""
    qa = get_qa()
    result = qa.answer(q)
    # 从回答文本中提取药物名，查询说明书（使用同一个qa实例的kg）
    kg = qa.kg
    text = result.get("text", "")
    drug_details = []
    # 用知识图谱药物词表匹配回答中出现的药名
    drug_names = [n for n, t in kg.entity_types.items() if t == "药物" and n in text and len(n) >= 3]
    # 去重，按长度降序（优先长名）
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

@app.post("/api/records")
async def save_record(body: dict = Body(...)):
    db = get_db()
    content = body.get("content", "").strip()
    if not content:
        return {"ok": False, "msg": "空内容"}
    import re
    m = re.search(r'姓名[：:]\s*([^\s　\n]{1,10})', content)
    patient_name = m.group(1).strip() if m else ""
    dept = body.get("department", "")
    record_id = body.get("id")
    if record_id:
        db.update_record(record_id, content=content)
    else:
        record_id = db.create_record(1, patient_name, dept, "", content, "草稿")
    # 收集语料
    try:
        get_feedback().collect_corpus(content)
    except Exception:
        pass
    return {"ok": True, "id": record_id}

@app.get("/api/records")
async def list_records():
    db = get_db()
    records = db.list_records(user_id=1)
    return [{"id": r["id"], "patient_name": r.get("patient_name", ""),
             "department": r.get("department", ""), "updated_at": r.get("updated_at", "")}
            for r in (records or [])[:50]]

@app.get("/api/records/{record_id}/export/{format}")
async def export_record(record_id: str, format: str):
    """导出病历为HL7/FHIR格式"""
    from hl7_fhir_exporter import MedicalRecordConverter
    
    db = get_db()
    record = db.get_record(record_id)
    if not record:
        return {"ok": False, "msg": "病历不存在"}
    
    # 解析病历内容为结构化数据（简化示例）
    content = record.get("content", "")
    import re
    
    # 提取基本信息
    patient_data = {
        "patient_id": record_id,
        "name": "",
        "gender": "unknown",
        "birth_date": "",
        "phone": "",
        "address": ""
    }
    
    # 尝试提取姓名
    name_match = re.search(r'姓名[：:]\s*([^\s\n]+)', content)
    if name_match:
        patient_data["name"] = name_match.group(1).strip()
    
    # 尝试提取性别
    gender_match = re.search(r'性别[：:]\s*([男女])', content)
    if gender_match:
        patient_data["gender"] = "male" if gender_match.group(1) == "男" else "female"
    
    # 尝试提取年龄
    age_match = re.search(r'年龄[：:]\s*(\d+)', content)
    if age_match:
        patient_data["age"] = age_match.group(1)
    
    # 构建病历数据结构
    record_data = {
        "patient": patient_data,
        "encounter": {
            "encounter_id": record_id,
            "patient_id": record_id,
            "inpatient": False,
            "admit_date": record.get("created_at", ""),
            "doctor_name": ""
        },
        "conditions": [],
        "medications": []
    }
    
    # 尝试提取诊断
    diagnosis_match = re.search(r'初步诊断[：:]\s*([^\n]+)', content)
    if diagnosis_match:
        record_data["conditions"].append({
            "condition_id": f"C{record_id}",
            "patient_id": record_id,
            "encounter_id": record_id,
            "diagnosis": diagnosis_match.group(1).strip(),
            "recorded_date": record.get("created_at", "")
        })
    
    # 导出
    converter = MedicalRecordConverter()
    
    if format == "hl7":
        hl7_message = converter.convert_to_hl7(record_data)
        return {"ok": True, "format": "hl7", "content": hl7_message}
    
    elif format == "fhir":
        fhir_bundle = converter.convert_to_fhir(record_data)
        return {"ok": True, "format": "fhir", "content": fhir_bundle}
    
    else:
        return {"ok": False, "msg": f"不支持的格式: {format}"}

@app.post("/api/correct")
async def correct_text(body: dict = Body(...)):
    """对文本执行纠错"""
    text = body.get("text", "")
    corrector = get_corrector()
    corrected, log = corrector.correct(text)
    return {"original": text, "corrected": corrected, "log": log}


@app.post("/api/fill")
async def fill_fields(body: dict = Body(...)):
    """将语音识别文本结构化填充到模板字段中"""
    asr_text = body.get("text", "").strip()
    base_content = body.get("base", "").strip()
    dept = body.get("department", "内科")

    if not asr_text:
        return {"filled": base_content, "changed": False}

    # 获取模板内容作为 base
    if not base_content:
        te = get_template_engine()
        tpls = te.get_templates(dept)
        if tpls:
            base_content = tpls[0].get("content", "")

    if not base_content:
        return {"filled": asr_text, "changed": False}

    # 使用 MedicalClassifier 做增量填充
    try:
        classifier = get_classifier()
        filled = classifier.incremental_fill(asr_text, base_content)
        return {"filled": filled, "changed": filled != base_content}
    except Exception as e:
        return {"filled": base_content + "\n" + asr_text, "changed": True, "error": str(e)}


def get_classifier():
    global _classifier
    if _classifier is None:
        from medical_classifier import MedicalClassifier
        _classifier = MedicalClassifier()
    return _classifier

_classifier = None


# ═══════════════════════════════════════════════════
# WebSocket — 实时语音识别
# ═══════════════════════════════════════════════════

@app.websocket("/ws/asr")
async def ws_asr(websocket: WebSocket):
    """
    接收浏览器端录音的 PCM/WAV 数据，返回识别结果。
    支持流式中间识别：每累积约2秒音频发送一次 partial 结果。
    """
    await websocket.accept()
    asr = get_asr()
    audio_buffer = bytearray()
    last_partial_len = 0
    # 每 2 秒音频做一次中间识别 (16000Hz * 2bytes * 2s = 64000 bytes)
    PARTIAL_THRESHOLD = 64000
    # 缓冲区大小限制：10MB（约 5 分钟音频）
    MAX_BUFFER_SIZE = 10 * 1024 * 1024

    try:
        await websocket.send_json({"type": "status", "msg": "ready"})

        while True:
            msg = await websocket.receive()

            if msg.get("type") == "websocket.disconnect":
                break

            if "bytes" in msg and msg["bytes"]:
                audio_buffer.extend(msg["bytes"])
                
                # 检查缓冲区大小限制
                if len(audio_buffer) > MAX_BUFFER_SIZE:
                    await websocket.send_json({
                        "type": "error", 
                        "msg": "录音时间过长，请分段录音"
                    })
                    audio_buffer.clear()
                    last_partial_len = 0
                    continue
                
                # 流式中间识别：每累积 2 秒新音频做一次快速识别
                if len(audio_buffer) - last_partial_len >= PARTIAL_THRESHOLD:
                    partial_text = await _quick_recognize(asr, bytes(audio_buffer))
                    if partial_text:
                        await websocket.send_json({"type": "partial", "text": partial_text})
                    last_partial_len = len(audio_buffer)

            elif "text" in msg and msg["text"]:
                data = json.loads(msg["text"])
                cmd = data.get("cmd", "")

                if cmd == "stop":
                    # 录音结束，最终识别
                    if len(audio_buffer) > 3200:  # 至少 100ms
                        final_text = await _quick_recognize(asr, bytes(audio_buffer))
                        await websocket.send_json({"type": "result", "text": final_text or ""})
                    else:
                        await websocket.send_json({"type": "result", "text": ""})
                    audio_buffer.clear()
                    last_partial_len = 0

                elif cmd == "ping":
                    await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_json({"type": "error", "msg": str(e)})
        except Exception:
            pass


async def _quick_recognize(asr, pcm_data: bytes) -> str:
    """在线程池中执行 ASR 识别（避免阻塞事件循环）"""
    import asyncio
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    try:
        with wave.open(tmp.name, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(16000)
            wf.writeframes(pcm_data)
        tmp.close()
        # 在线程池中运行 CPU 密集型识别
        text = await asyncio.get_running_loop().run_in_executor(None, asr.transcribe_file, tmp.name)
        return text or ""
    except Exception:
        return ""
    finally:
        try:
            os.unlink(tmp.name)
        except Exception:
            pass


# ═══════════════════════════════════════════════════
# 启动
# ═══════════════════════════════════════════════════

if __name__ == "__main__":
    print("""
    ╔══════════════════════════════════════════╗
    ║  星衍AI · 智能病历录入  后端服务          ║
    ║  http://localhost:8765                   ║
    ╚══════════════════════════════════════════╝
    """)
    uvicorn.run(app, host="0.0.0.0", port=8765, log_level="info")
