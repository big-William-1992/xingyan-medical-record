# 统一纠错记忆库 schema 草案

> 用于替代分散的 `hotwords.txt`、`postprocess_hotwords.txt`、`correction_rules.json`、`asr_confusion_pairs.json`、`correction_feedback.jsonl` 的分散存储。

## 1. 存储方案

建议双格式：
- 主存储：`data/correction_memory.jsonl`
- 索引/统计：`data/correction_memory_index.json`
- 备份：`data/correction_memory_backups/YYYYMMDD_HHMMSS.jsonl`

SQLite 可选，但如果你们想保持轻量和可人工审计，JSONL 先够用；后面数据量超过 50 万条再切 SQLite。

## 2. 记忆条目 schema

```json
{
  "memory_id": "uuid",
  "record_id": null,
  "doctor_id": "user_id",
  "dept": "内科",
  "field": "现病史",
  "source": "corrector",
  "status": "accepted",
  "original": "原文本",
  "corrected": "修正文本",
  "category": "错别字",
  "level": "自动",
  "similarity": 0.92,
  "confidence": 0.85,
  "freq": 3,
  "accepted_count": 2,
  "rejected_count": 0,
  "last_used_at": "2026-08-05T12:00:00",
  "created_at": "2026-08-05T12:00:00",
  "updated_at": "2026-08-05T12:00:00",
  "meta": {
    "template_name": "",
    "audio_path": "recordings/rec_20260805_120000.wav",
    "snapshot_id": "asr_20260805_120000",
    "model_version": "paraformer-zh-v1",
    "lm_version": "medical_3gram-20260805",
    "note": ""
  }
}
```

字段说明：
- `source`: `corrector / lm_rescore / rule_engine / manual_edit / asr_snapshot_diff / user_override`
- `status`: `pending / accepted / rejected / deprecated`
- `confidence`: 0~1，用于 Top-K 加权和自动训练样本筛选
- `freq`: 该记忆条目被命中的次数
- `category`: `错别字 / 逻辑错误 / 缺项提醒 / 术语替换 / 句式优化`
- `level`: `自动 / 建议 / 警告`
- `meta.note`: 可记录医生备注，用于后续规则优化

## 3. 导出视图 schema

统一记忆库最终要导出为现有系统能消费的视图：

### 3.1 hotwords 视图

```json
{
  "view": "hotwords",
  "dept": "内科",
  "doctor_id": "1",
  "terms": [
    {"term": "冠状动脉造影", "score": 0.97},
    {"term": "降压药", "score": 0.94}
  ]
}
```

### 3.2 postprocess_hotwords 视图

```json
{
  "view": "postprocess_hotwords",
  "dept": "内科",
  "items": [
    {"wrong": "心机梗死", "right": "心肌梗死", "confidence": 0.96, "freq": 8}
  ]
}
```

### 3.3 confusion_pairs 视图

```json
{
  "view": "confusion_pairs",
  "dept": "通用",
  "pairs": {
    "心机梗死": "心肌梗死",
    "高血药": "降压药"
  }
}
```

### 3.4 prompt_pack 视图

```json
{
  "view": "prompt_pack",
  "dept": "内科",
  "field": "现病史",
  "top_terms": ["心肌梗死", "冠状动脉造影", "硝苯地平"],
  "recent_pairs": [["心机梗死", "心肌梗死"]],
  "template_context": "患者因胸闷入院，需重点关注心血管系统。",
  "instruction": "请优先识别心血管相关术语，并注意药物与症状一致性。"
}
```

## 4. Backfill 策略

### 4.1 来源映射

- `correction_feedback.jsonl:1` -> memory
  - 直接映射 `original / corrected / source / status`
  - 缺失字段补默认值：`doctor_id=unknown / dept=unknown / field=unknown / confidence=0.7`
- `asr_confusion_pairs.json:1` -> memory
  - 每条生成两条候选记忆：
    - accepted 候选：`status=accepted, source=confusion_pair`
    - rejected 候选：`status=pending, source=confusion_pair`
- `hotwords.txt:1`、`user_hotwords.txt:1`、`kg_hotwords.txt:1`
  - 不作为纠错记忆条目，而是作为 `prompt_pack.view=hotwords` 的 seed 数据
- `postprocess_hotwords.txt:1`
  - 解析为 memory 条目，source=`postprocess_hotword`

### 4.2 Backfill 脚本输出

建议新增 `scripts/backfill_memory.py`，输出：
- `data/correction_memory.jsonl`
- `data/correction_memory_index.json`
- `docs/correction_memory_backfill_report.md`

## 5. 索引设计

`correction_memory_index.json` 最小应包含：

```json
{
  "stats": {
    "total": 1024,
    "accepted": 860,
    "rejected": 120,
    "pending": 44
  },
  "top_terms": {
    "global": [["心肌梗死", 10], ["冠状动脉造影", 8]],
    "内科": [["心肌梗死", 7], ["硝苯地平", 5]],
    "doctor_1": [["心肌梗死", 4], ["胸痛", 3]]
  },
  "last_lm_train": "2026-08-01T10:00:00",
  "last_finetune": "2026-07-20T08:30:00",
  "version": "2026-08-05"
}
```

## 6. 访问控制建议

- `memory_id` 全局唯一
- 支持按 `doctor_id` 私有和按 `dept` 共享
- 管理员可标记 `deprecated`，但不删除原始记录
- 所有写操作都写 append-only JSONL，避免覆盖历史证据

## 7. 下一步

- 先落 `correction_memory.py` 最小实现
- 再做 `backfill_memory.py`
- 然后改 `main.py` 的 accept/reject/save 流程接入 memory
- 最后接 `topk_engine.py` 和 prompt 视图导出
