# API 文档使用指南

## 自动生成 Swagger 文档

FastAPI 自动生成交互式 API 文档，无需额外配置。

### 访问方式

启动服务后，访问以下地址：

1. **Swagger UI**（交互式文档）
   ```
   http://localhost:8765/docs
   ```

2. **ReDoc**（另一种文档视图）
   ```
   http://localhost:8765/redoc
   ```

3. **OpenAPI JSON**（原始 OpenAPI 规范）
   ```
   http://localhost:8765/openapi.json
   ```

## API 端点概览

### 系统信息

| 端点 | 方法 | 描述 |
|------|------|------|
| `/api/stats` | GET | 获取系统统计信息 |
| `/api/health` | GET | 健康检查 |

### 科室管理

| 端点 | 方法 | 描述 |
|------|------|------|
| `/api/departments` | GET | 获取所有科室列表 |

### 模板管理

| 端点 | 方法 | 描述 |
|------|------|------|
| `/api/templates` | GET | 获取指定科室的模板列表 |
| `/api/templates/{dept}/{name}` | GET | 获取指定模板内容 |

### 字段常用词

| 端点 | 方法 | 描述 |
|------|------|------|
| `/api/field-words/{field}` | GET | 获取字段常用词 |
| `/api/presets/{field}` | GET | 获取字段常用句 |
| `/api/presets/{field}` | POST | 添加字段常用句 |

### 知识图谱

| 端点 | 方法 | 描述 |
|------|------|------|
| `/api/kg/drug/{name}` | GET | 查询药物信息 |
| `/api/kg/disease/{name}` | GET | 查询疾病信息 |
| `/api/kg/query` | GET | 知识图谱智能问答 |

### 病历管理

| 端点 | 方法 | 描述 |
|------|------|------|
| `/api/records` | GET | 获取病历列表 |
| `/api/records` | POST | 保存病历 |
| `/api/records/{id}` | GET | 获取单个病历 |
| `/api/records/{id}` | PUT | 更新病历 |
| `/api/records/{id}` | DELETE | 删除病历 |

### 文本处理

| 端点 | 方法 | 描述 |
|------|------|------|
| `/api/correct` | POST | 文本纠错 |
| `/api/fill` | POST | 结构化填充 |

### HL7/FHIR 导出

| 端点 | 方法 | 描述 |
|------|------|------|
| `/api/records/{id}/export/hl7` | GET | 导出为 HL7 格式 |
| `/api/records/{id}/export/fhir` | GET | 导出为 FHIR 格式 |

## 使用示例

### Python

```python
import requests

# 获取系统统计
response = requests.get("http://localhost:8765/api/stats")
stats = response.json()
print(f"知识图谱实体数: {stats['kg_entities']}")

# 查询疾病信息
response = requests.get("http://localhost:8765/api/kg/disease/高血压")
disease = response.json()
print(f"症状: {disease['symptoms']}")

# 知识问答
response = requests.get("http://localhost:8765/api/kg/query?q=高血压怎么治疗")
answer = response.json()
print(f"回答: {answer['text']}")
```

### JavaScript

```javascript
// 获取科室列表
fetch('http://localhost:8765/api/departments')
  .then(response => response.json())
  .then(departments => {
    console.log('科室列表:', departments);
  });

// 知识问答
fetch('http://localhost:8765/api/kg/query?q=高血压')
  .then(response => response.json())
  .then(result => {
    console.log('回答:', result.text);
  });
```

### cURL

```bash
# 获取系统统计
curl http://localhost:8765/api/stats

# 查询药物信息
curl http://localhost:8765/api/kg/drug/阿莫西林

# 文本纠错
curl -X POST http://localhost:8765/api/correct \
  -H "Content-Type: application/json" \
  -d '{"text": "患者发烧3天"}'
```

## 认证（未来版本）

### JWT Token 认证

```python
import requests

# 登录获取 Token
login_response = requests.post("http://localhost:8765/api/auth/login", json={
    "username": "admin",
    "password": "password"
})
token = login_response.json()["token"]

# 使用 Token 访问受保护的 API
headers = {"Authorization": f"Bearer {token}"}
response = requests.get("http://localhost:8765/api/protected", headers=headers)
```

## 错误处理

所有 API 端点返回标准 HTTP 状态码：

| 状态码 | 描述 |
|--------|------|
| 200 | 成功 |
| 400 | 请求参数错误 |
| 401 | 未认证 |
| 403 | 权限不足 |
| 404 | 资源不存在 |
| 500 | 服务器内部错误 |

错误响应格式：

```json
{
  "detail": "错误描述信息"
}
```

## 频率限制

| 端点 | 限制 |
|------|------|
| `/api/kg/drug/{name}` | 30次/分钟 |
| `/api/kg/disease/{name}` | 30次/分钟 |
| `/api/kg/query` | 20次/分钟 |

超过限制返回 `429 Too Many Requests`。

## WebSocket

### 实时语音识别

```javascript
const ws = new WebSocket('ws://localhost:8765/ws/asr');

ws.onopen = () => {
  console.log('WebSocket 连接已建立');
};

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  if (data.type === 'partial') {
    console.log('部分识别结果:', data.text);
  } else if (data.type === 'result') {
    console.log('最终识别结果:', data.text);
  }
};

// 发送音频数据
ws.send(audioBuffer);

// 停止识别
ws.send(JSON.stringify({cmd: 'stop'}));
```

## 更多信息

- [完整 API 文档](http://localhost:8765/docs)
- [部署指南](DEPLOYMENT.md)
- [用户手册](USER_MANUAL.md)
