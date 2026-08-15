# 星衍AI智能病历录入系统 - API文档

## 概述

本文档描述了星衍AI智能病历录入系统的REST API接口。

**基础URL**: `http://localhost:8765`

**版本**: 2.0

---

## 认证

当前版本无需认证（开发环境）。生产环境建议添加JWT认证。

---

## 接口列表

### 1. 系统状态

#### GET `/api/stats`

获取系统状态统计信息。

**响应示例**:
```json
{
  "hotwords": 3000,
  "kg_entities": 27947,
  "kg_relations": 535803,
  "drug_inserts": 14047,
  "asr_ready": true
}
```

**频率限制**: 无

---

### 2. 科室管理

#### GET `/api/departments`

获取所有科室列表。

**响应示例**:
```json
["全科", "内科", "外科", "妇产科", "儿科"]
```

---

### 3. 模板管理

#### GET `/api/templates`

获取指定科室的模板列表。

**参数**:
- `dept` (string, 可选): 科室名称，默认"内科"

**响应示例**:
```json
[
  {"name": "入院记录", "content": "主诉：\n现病史：..."},
  {"name": "首次病程", "content": "..."}
]
```

#### GET `/api/templates/{dept}/{name}`

获取指定模板内容。

**参数**:
- `dept` (string): 科室名称
- `name` (string): 模板名称

**响应示例**:
```json
{"content": "主诉：\n现病史：..."}
```

---

### 4. 字段常用词

#### GET `/api/field-words/{field}`

获取指定字段的常用词。

**参数**:
- `field` (string): 字段名称（如"主诉"、"现病史"）

**响应示例**:
```json
{
  "field": "主诉",
  "sections": [
    {"title": "常见症状", "words": ["发热", "咳嗽", "头痛"]}
  ]
}
```

---

### 5. 常用语句

#### GET `/api/presets/{field}`

获取指定字段的常用语句。

**响应示例**:
```json
{
  "field": "现病史",
  "presets": ["患者三天前受凉后出现发热..."]
}
```

#### POST `/api/presets/{field}`

添加常用语句。

**请求体**:
```json
{"sentence": "患者三天前受凉后出现发热"}
```

**响应**:
```json
{"ok": true}
```

---

### 6. 知识图谱查询

#### GET `/api/kg/drug/{name}`

查询药物信息。

**频率限制**: 30次/分钟

**响应示例**:
```json
{
  "name": "阿莫西林",
  "info": {"适应症": "...", "用法用量": "..."},
  "treats": ["肺炎", "支气管炎"]
}
```

#### GET `/api/kg/disease/{name}`

查询疾病信息。

**频率限制**: 30次/分钟

**响应示例**:
```json
{
  "name": "高血压",
  "desc": "高血压描述...",
  "system": "心血管",
  "symptoms": ["头痛", "头晕"],
  "drugs": ["氨氯地平", "硝苯地平"],
  "exams": ["血压", "心电图"],
  "complicates": ["冠心病"],
  "department": ["内科"]
}
```

#### GET `/api/kg/query`

知识图谱智能问答。

**频率限制**: 20次/分钟

**参数**:
- `q` (string, 必填): 问题文本

**响应示例**:
```json
{
  "found": true,
  "disease": "高血压",
  "intent": "治疗",
  "text": "【高血压】治疗方案...",
  "suggestions": ["高血压用什么药"],
  "drug_details": [...]
}
```

---

### 7. 病历管理

#### POST `/api/records`

保存病历。

**请求体**:
```json
{
  "content": "主诉：发热三天\n现病史：...",
  "department": "内科",
  "id": "可选，更新时提供"
}
```

**响应**:
```json
{"ok": true, "id": "record_id"}
```

#### GET `/api/records`

获取病历列表。

**响应示例**:
```json
[
  {
    "id": "1",
    "patient_name": "张伟",
    "department": "内科",
    "updated_at": "2026-08-15 10:30:00"
  }
]
```

---

### 8. 文本纠错

#### POST `/api/correct`

对文本执行纠错。

**请求体**:
```json
{"text": "心电围"}
```

**响应**:
```json
{
  "original": "心电围",
  "corrected": "心电图",
  "log": [{"wrong": "心电围", "correct": "心电图"}]
}
```

---

### 9. 字段填充

#### POST `/api/fill`

将语音识别文本结构化填充到模板字段中。

**请求体**:
```json
{
  "text": "主诉发热三天",
  "base": "主诉：\n现病史：",
  "department": "内科"
}
```

**响应**:
```json
{
  "filled": "主诉：发热三天\n现病史：",
  "changed": true
}
```

---

### 10. WebSocket - 实时语音识别

#### WebSocket `/ws/asr`

实时语音识别接口。

**连接**:
```javascript
const ws = new WebSocket('ws://localhost:8765/ws/asr');
```

**消息格式**:

发送音频数据（二进制）:
```javascript
ws.send(audioBuffer);
```

接收识别结果（JSON）:
```json
{"type": "partial", "text": "发热"}
{"type": "result", "text": "发热三天"}
{"type": "status", "msg": "ready"}
{"type": "error", "msg": "错误信息"}
```

**命令**:
```json
{"cmd": "stop"}  // 停止录音
{"cmd": "ping"}  // 心跳检测
```

---

## 错误处理

所有API在发生错误时返回标准HTTP状态码：

- `400`: 请求参数错误
- `401`: 未认证（未来版本）
- `403`: 禁止访问
- `404`: 资源不存在
- `429`: 请求过于频繁（频率限制）
- `500`: 服务器内部错误

**错误响应格式**:
```json
{"detail": "错误描述"}
```

---

## 频率限制

| 接口 | 限制 |
|------|------|
| `/api/kg/drug/{name}` | 30次/分钟 |
| `/api/kg/disease/{name}` | 30次/分钟 |
| `/api/kg/query` | 20次/分钟 |
| 其他接口 | 无限制 |

超过限制返回 `429` 状态码。

---

## 审计日志

所有API请求都会记录到 `audit.log` 文件，包含：
- 请求方法
- URL路径
- 状态码
- 客户端IP
- 处理时间

---

## CORS配置

允许的源：
- `http://localhost:8765`
- `http://localhost:3000`
- `http://127.0.0.1:8765`
- `http://127.0.0.1:3000`

生产环境请修改 `app_server.py` 中的 `ALLOWED_ORIGINS`。

---

## 示例代码

### Python

```python
import requests

# 查询疾病信息
response = requests.get('http://localhost:8765/api/kg/disease/高血压')
disease = response.json()
print(disease['symptoms'])

# 知识图谱问答
response = requests.get('http://localhost:8765/api/kg/query', params={'q': '高血压怎么治疗'})
answer = response.json()
print(answer['text'])
```

### JavaScript

```javascript
// 查询药物信息
fetch('http://localhost:8765/api/kg/drug/阿莫西林')
  .then(res => res.json())
  .then(data => console.log(data));

// WebSocket实时识别
const ws = new WebSocket('ws://localhost:8765/ws/asr');
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  if (data.type === 'result') {
    console.log('识别结果:', data.text);
  }
};
```

---

## 更新日志

### v2.0 (2026-08-15)
- ✅ 添加频率限制
- ✅ 添加审计日志
- ✅ 限制CORS源
- ✅ 优化错误处理

### v1.0 (2026-07-01)
- 初始版本
