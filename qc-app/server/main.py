#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
星衍AI · 放射质控系统 - FastAPI 后端
提供报告数据 REST API
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import json
import os

app = FastAPI(title="星衍AI · 放射质控 API", version="1.0.0")

# CORS：允许前端跨域访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],      # 生产环境改为具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── 数据模型 ───

class QCItem(BaseModel):
    key: str
    label: str
    group: str

class Issue(BaseModel):
    rule: str
    severity: str
    detail: str

class Report(BaseModel):
    id: str
    patientName: str
    patientId: str
    patientAge: int
    patientSex: str
    modality: str
    bodyPart: str
    accession: str
    studyDate: str
    reportDate: str
    status: str
    priority: str
    description: str
    diagnosis: str
    issues: List[Issue]
    score: int
    reviewer: str
    reviewComment: str
    qcChecks: Dict[str, Optional[bool]]

class Stats(BaseModel):
    today: Dict[str, int]
    week: Dict[str, int]
    avgScore: float
    commonIssues: List[Dict[str, Any]]

# ─── 模拟数据 ───

REPORTS: List[Report] = [
    Report(
        id="RPT-20260801-001", patientName="王某", patientId="P20230815",
        patientAge=58, patientSex="男", modality="CT", bodyPart="胸部",
        accession="CT20260801001", studyDate="2026-08-01", reportDate="2026-08-01",
        status="pending", priority="normal",
        description="胸部CT平扫，肺窗示双肺纹理增多，右肺上叶可见一枚约5mm小结节影，边界清晰。纵隔内未见明显肿大淋巴结。心影大小形态正常。双侧胸膜未见明显增厚。",
        diagnosis="1. 右肺上叶小结节影（约5mm），建议3个月后复查CT随访。\n2. 双肺纹理增多。",
        issues=[
            Issue(rule="检查部位与申请单不符", severity="error", detail="申请单标注「胸部CT」，实际扫描包含上腹部"),
            Issue(rule="放射学表现描述缺失", severity="error", detail="未见肺纹理、纵隔等结构描述"),
            Issue(rule="漏诊提示", severity="warning", detail="右肺上叶小结节（约5mm），建议随访"),
        ],
        score=62, reviewer="", reviewComment="",
        qcChecks={
            "patient_info": True, "modality_match": False, "study_quality": True,
            "contrast_record": None, "tech_params": True, "findings_desc": False,
            "structures_named": False, "findings_accurate": True, "diagnosis_match": True,
            "followup": True, "critical_value": None, "comparison": None,
        },
    ),
    Report(
        id="RPT-20260801-002", patientName="李某", patientId="P20230922",
        patientAge=42, patientSex="女", modality="MR", bodyPart="头颅",
        accession="MR20260801002", studyDate="2026-08-01", reportDate="2026-08-01",
        status="passed", priority="normal",
        description="头颅MRI平扫+增强扫描，双侧大脑半球对称，灰白质分界清晰。脑室系统未见扩张。中线结构居中。增强后未见明显异常强化灶。",
        diagnosis="头颅MRI平扫+增强扫描未见明显异常。",
        issues=[],
        score=95, reviewer="张医生", reviewComment="报告规范，无异常",
        qcChecks={
            "patient_info": True, "modality_match": True, "study_quality": True,
            "contrast_record": True, "tech_params": True, "findings_desc": True,
            "structures_named": True, "findings_accurate": True, "diagnosis_match": True,
            "followup": True, "critical_value": True, "comparison": True,
        },
    ),
    Report(
        id="RPT-20260801-003", patientName="赵某", patientId="P20231005",
        patientAge=65, patientSex="男", modality="CR", bodyPart="胸部正位",
        accession="CR20260801003", studyDate="2026-08-01", reportDate="2026-08-01",
        status="rejected", priority="high",
        description="胸部正位X线片，双肺纹理增多，心影增大。",
        diagnosis="双肺纹理增多，心影增大。",
        issues=[
            Issue(rule="关键结构未标注", severity="error", detail="心影增大未提及，建议测量心胸比"),
            Issue(rule="结论与表现矛盾", severity="error", detail="描述提及「肺纹理增多」，结论写「未见异常」"),
        ],
        score=45, reviewer="张医生", reviewComment="请补充心胸比测量，修正结论",
        qcChecks={
            "patient_info": True, "modality_match": True, "study_quality": True,
            "contrast_record": None, "tech_params": False, "findings_desc": True,
            "structures_named": False, "findings_accurate": True, "diagnosis_match": False,
            "followup": False, "critical_value": None, "comparison": None,
        },
    ),
    Report(
        id="RPT-20260801-004", patientName="刘某", patientId="P20231118",
        patientAge=35, patientSex="女", modality="CT", bodyPart="腹部",
        accession="CT20260801004", studyDate="2026-08-01", reportDate="2026-08-01",
        status="pending", priority="normal",
        description="腹部CT平扫+增强扫描，肝脏大小形态正常，密度均匀。胆囊壁不增厚。胰腺未见明显异常。双肾大小正常，未见明显结石。",
        diagnosis="1. 腹部CT平扫+增强扫描未见明显异常。\n2. 建议定期复查。",
        issues=[
            Issue(rule="对比剂使用记录缺失", severity="warning", detail="增强扫描但未记录对比剂类型和剂量"),
        ],
        score=78, reviewer="", reviewComment="",
        qcChecks={
            "patient_info": True, "modality_match": True, "study_quality": True,
            "contrast_record": False, "tech_params": True, "findings_desc": True,
            "structures_named": True, "findings_accurate": True, "diagnosis_match": True,
            "followup": True, "critical_value": True, "comparison": None,
        },
    ),
    Report(
        id="RPT-20260801-005", patientName="陈某", patientId="P20231201",
        patientAge=72, patientSex="男", modality="DX", bodyPart="腰椎侧位",
        accession="DX20260801005", studyDate="2026-08-01", reportDate="2026-08-01",
        status="pending", priority="urgent",
        description="腰椎侧位X线片，L1椎体楔形变，高度压缩约1/3，侧弯畸形。",
        diagnosis="L1椎体压缩性骨折（约1/3）。",
        issues=[
            Issue(rule="危急值未上报", severity="critical", detail="椎体压缩性骨折（约1/3），属危急值，需立即通知临床"),
        ],
        score=35, reviewer="", reviewComment="",
        qcChecks={
            "patient_info": True, "modality_match": True, "study_quality": True,
            "contrast_record": None, "tech_params": True, "findings_desc": True,
            "structures_named": True, "findings_accurate": True, "diagnosis_match": True,
            "followup": False, "critical_value": False, "comparison": None,
        },
    ),
    Report(
        id="RPT-20260731-006", patientName="周某", patientId="P20230709",
        patientAge=30, patientSex="女", modality="US", bodyPart="腹部超声",
        accession="US20260731006", studyDate="2026-07-31", reportDate="2026-07-31",
        status="passed", priority="normal",
        description="腹部超声检查，肝脏大小形态正常，回声均匀。胆囊壁不增厚，内无结石。胰腺大小正常。双肾大小正常，无结石。",
        diagnosis="腹部超声未见明显异常。",
        issues=[],
        score=92, reviewer="李医生", reviewComment="规范",
        qcChecks={
            "patient_info": True, "modality_match": True, "study_quality": True,
            "contrast_record": None, "tech_params": True, "findings_desc": True,
            "structures_named": True, "findings_accurate": True, "diagnosis_match": True,
            "followup": True, "critical_value": True, "comparison": True,
        },
    ),
    Report(
        id="RPT-20260731-007", patientName="吴某", patientId="P20230615",
        patientAge=55, patientSex="男", modality="PT", bodyPart="全身PET-CT",
        accession="PT20260731007", studyDate="2026-07-31", reportDate="2026-07-31",
        status="pending", priority="normal",
        description="全身PET-CT显像，脑、甲状腺、心肌代谢未见明显异常。肺部SUVmax升高区域（左上肺 8.2），大小约2.1cm。肝、脾、肾等腹部脏器代谢未见明显异常。",
        diagnosis="1. 左上肺代谢异常增高灶（SUVmax 8.2），性质待查，建议活检。\n2. 建议补充 TNM 分期评估。",
        issues=[
            Issue(rule="代谢异常区域未描述", severity="warning", detail="SUVmax 升高区域（左上肺 8.2）未纳入描述"),
            Issue(rule="分期建议缺失", severity="warning", detail="建议补充 TNM 分期或疗效评估"),
        ],
        score=68, reviewer="", reviewComment="",
        qcChecks={
            "patient_info": True, "modality_match": True, "study_quality": True,
            "contrast_record": True, "tech_params": True, "findings_desc": False,
            "structures_named": True, "findings_accurate": True, "diagnosis_match": True,
            "followup": False, "critical_value": None, "comparison": None,
        },
    ),
    Report(
        id="RPT-20260731-008", patientName="郑某", patientId="P20230520",
        patientAge=48, patientSex="女", modality="CT", bodyPart="头颅平扫",
        accession="CT20260731008", studyDate="2026-07-31", reportDate="2026-07-31",
        status="passed", priority="normal",
        description="头颅CT平扫，脑实质内未见明显异常密度灶。脑室系统未见扩张。脑沟脑池未见明显增宽。中线结构居中。",
        diagnosis="头颅CT平扫未见明显异常。",
        issues=[],
        score=88, reviewer="张医生", reviewComment="",
        qcChecks={
            "patient_info": True, "modality_match": True, "study_quality": True,
            "contrast_record": None, "tech_params": True, "findings_desc": True,
            "structures_named": True, "findings_accurate": True, "diagnosis_match": True,
            "followup": True, "critical_value": True, "comparison": True,
        },
    ),
]

STATS = Stats(
    today={"total": 45, "passed": 32, "rejected": 8, "pending": 5},
    week={"total": 312, "passed": 268, "rejected": 28, "pending": 16},
    avgScore=82.5,
    commonIssues=[
        {"rule": "放射学表现描述缺失", "count": 12},
        {"rule": "结论与表现矛盾", "count": 8},
        {"rule": "检查部位与申请单不符", "count": 5},
        {"rule": "漏诊提示", "count": 4},
        {"rule": "对比剂记录缺失", "count": 3},
    ],
)

QC_CHECK_ITEMS = [
    QCItem(key="patient_info", label="患者基本信息完整", group="基础信息"),
    QCItem(key="modality_match", label="检查部位与申请单一致", group="基础信息"),
    QCItem(key="study_quality", label="影像质量合格", group="影像质量"),
    QCItem(key="contrast_record", label="对比剂使用记录完整", group="影像质量"),
    QCItem(key="tech_params", label="技术参数标注正确", group="影像质量"),
    QCItem(key="findings_desc", label="放射学表现描述完整", group="影像描述"),
    QCItem(key="structures_named", label="正常结构逐一描述", group="影像描述"),
    QCItem(key="findings_accurate", label="异常发现描述准确", group="影像描述"),
    QCItem(key="diagnosis_match", label="诊断结论与表现一致", group="影像诊断"),
    QCItem(key="followup", label="建议/随访意见合理", group="影像诊断"),
    QCItem(key="critical_value", label="危急值已上报", group="影像诊断"),
    QCItem(key="comparison", label="与旧片对比有记录", group="影像诊断"),
]

SEVERITY_MAP = {
    "critical": {"label": "危急值", "type": "danger", "icon": "WarningFilled"},
    "error": {"label": "错误", "type": "danger", "icon": "CircleCloseFilled"},
    "warning": {"label": "警告", "type": "warning", "icon": "Warning"},
    "info": {"label": "提示", "type": "info", "icon": "InfoFilled"},
}

# ─── API 路由 ───

@app.get("/api/reports")
def get_reports():
    """获取所有报告列表"""
    return [r.model_dump() for r in REPORTS]

@app.get("/api/reports/{report_id}")
def get_report(report_id: str):
    """获取单个报告详情"""
    for r in REPORTS:
        if r.id == report_id:
            return r.model_dump()
    raise HTTPException(status_code=404, detail="报告未找到")

@app.get("/api/stats")
def get_stats():
    """获取统计数据"""
    return STATS.model_dump()

@app.get("/api/qc-items")
def get_qc_items():
    """获取质控检查项列表"""
    return [item.model_dump() for item in QC_CHECK_ITEMS]

@app.get("/api/severity-map")
def get_severity_map():
    """获取严重程度映射"""
    return SEVERITY_MAP

@app.patch("/api/reports/{report_id}")
def update_report(report_id: str, updates: Dict[str, Any]):
    """更新报告（审核操作）"""
    for i, r in enumerate(REPORTS):
        if r.id == report_id:
            data = r.model_dump()
            data.update(updates)
            REPORTS[i] = Report(**data)
            return REPORTS[i].model_dump()
    raise HTTPException(status_code=404, detail="报告未找到")

# ─── 启动 ───
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
