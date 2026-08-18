# 星衍AI智能病历录入系统 - 部署指南

## 系统要求

### 硬件要求

**最低配置**:
- CPU: 4核 2.0GHz
- 内存: 8GB RAM
- 硬盘: 20GB 可用空间
- 麦克风: 必需

**推荐配置**:
- CPU: 8核 2.5GHz+
- 内存: 16GB RAM
- 硬盘: 50GB SSD
- 麦克风: 高质量USB麦克风

### 软件要求

**操作系统**:
- ✅ macOS 10.15+
- ✅ Ubuntu 20.04+
- ✅ Windows 10/11
- ⚠️ 其他Linux发行版（需测试）

**Python版本**:
- Python 3.10+
- 推荐 Python 3.14

---

## 快速开始

### 1. 克隆仓库

```bash
git clone https://github.com/big-William-1992/xingyan-medical-record.git
cd xingyan-medical-record
```

### 2. 创建虚拟环境

```bash
# macOS/Linux
python3 -m venv venv
source venv/bin/activate

# Windows
python -m venv venv
venv\Scripts\activate
```

### 3. 安装依赖

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. 下载模型（首次运行自动下载）

系统会自动下载以下模型：
- FunASR Paraformer（语音识别）
- FSMN-VAD（语音活动检测）
- CT-Punc（标点恢复）

模型大小约 1GB，下载时间取决于网络速度。

### 5. 启动系统

#### 方式一：桌面应用（推荐）

```bash
# PyQt5原生版
python main.py --legacy

# WebView版（默认）
python main.py
```

#### 方式二：Web服务

```bash
python app_server.py
```

然后在浏览器访问：`http://localhost:8765`

---

## 详细配置

### 环境变量

```bash
# ASR模型路径（可选）
export ASR_MODEL_PATH=/path/to/model

# 数据库路径（可选）
export DATABASE_PATH=/path/to/database.db

# 日志级别（可选）
export LOG_LEVEL=INFO

# ─── JWT 认证（生产环境推荐）───
# 启用强制认证：所有 API（除登录外）必须携带 Token，否则返回 401
export XINGYAN_JWT_ENFORCE=1

# JWT 签名密钥（务必改为随机长字符串！）
export JWT_SECRET_KEY=$(openssl rand -hex 32)

# JWT 有效期（小时，默认 24）
export JWT_EXPIRATION_HOURS=24

# ─── 测试/CI（可选）───
# 跳过 ASR 引擎加载（避免触发 1GB 模型下载，CI 环境使用）
export XINGYAN_SKIP_ASR=1
```

> **安全提示**：`JWT_SECRET_KEY` 必须使用强随机值，切勿使用代码默认值。
> 强制认证模式下，前端需先调用 `POST /api/auth/login` 获取 Token，
> 并在后续请求头携带 `Authorization: Bearer <token>`。

### 配置文件

#### `hotwords.txt` - 热词配置

```
# 通用
高血压
糖尿病

# 内科
心电图
血常规
```

#### `field_words.json` - 字段常用词

```json
{
  "主诉": {
    "terms": ["发热", "咳嗽", "头痛"]
  }
}
```

#### `field_presets.json` - 字段常用句

```json
{
  "现病史": [
    "患者三天前受凉后出现发热..."
  ]
}
```

---

## 生产环境部署

### 1. 安全配置

#### 修改CORS配置

编辑 `app_server.py`:

```python
ALLOWED_ORIGINS = [
    "https://your-domain.com",  # 修改为实际域名
]
```

#### 添加HTTPS

使用Nginx反向代理：

```nginx
server {
    listen 443 ssl;
    server_name your-domain.com;
    
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    
    location / {
        proxy_pass http://localhost:8765;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
    
    location /ws/ {
        proxy_pass http://localhost:8765;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

#### 添加认证

建议添加JWT认证：

```python
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

security = HTTPBearer()

@app.get("/api/protected")
async def protected_route(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    # 验证token
    ...
```

### 2. 数据库配置

#### SQLite（默认）

数据存储在 `data/records.db`，适合单机使用。

#### PostgreSQL（生产推荐）

修改 `database.py`:

```python
import psycopg2

class Database:
    def __init__(self):
        self.conn = psycopg2.connect(
            host="localhost",
            database="medical_records",
            user="postgres",
            password="password"
        )
```

### 3. 进程管理

#### 使用systemd（Linux）

创建 `/etc/systemd/system/medical-record.service`:

```ini
[Unit]
Description=Medical Record System
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/path/to/星衍病历智能录入系统
Environment="PATH=/path/to/venv/bin"
ExecStart=/path/to/venv/bin/python app_server.py
Restart=always

[Install]
WantedBy=multi-user.target
```

启动服务：

```bash
sudo systemctl enable medical-record
sudo systemctl start medical-record
sudo systemctl status medical-record
```

#### 使用Docker

创建 `Dockerfile`:

```dockerfile
FROM python:3.14-slim

WORKDIR /app
COPY . /app

RUN pip install -r requirements.txt

EXPOSE 8765
CMD ["python", "app_server.py"]
```

构建和运行：

```bash
docker build -t medical-record .
docker run -p 8765:8765 -v $(pwd)/data:/app/data medical-record
```

### 4. 负载均衡

使用Nginx负载均衡：

```nginx
upstream medical_record {
    server localhost:8765;
    server localhost:8766;
}

server {
    listen 80;
    
    location / {
        proxy_pass http://medical_record;
    }
}
```

---

## 数据备份

### 自动备份

系统每天自动备份数据库到 `data/backups/` 目录。

### 手动备份

```bash
# 备份数据库
cp data/records.db data/backups/records_$(date +%Y%m%d).db

# 备份配置文件
tar -czf config_backup_$(date +%Y%m%d).tar.gz \
    hotwords.txt \
    field_words.json \
    field_presets.json \
    templates/
```

### 恢复数据

```bash
# 恢复数据库
cp data/backups/records_20260815.db data/records.db

# 恢复配置
tar -xzf config_backup_20260815.tar.gz
```

---

## 性能优化

### 1. 缓存配置

安装Redis：

```bash
# macOS
brew install redis

# Ubuntu
sudo apt install redis-server
```

修改 `app_server.py`:

```python
from redis import Redis

redis_client = Redis(host='localhost', port=6379)

@app.get("/api/kg/disease/{name}")
async def kg_disease(name: str):
    # 尝试从缓存获取
    cached = redis_client.get(f"disease:{name}")
    if cached:
        return json.loads(cached)
    
    # 从数据库查询
    kg = get_kg()
    result = {...}
    
    # 缓存结果（1小时）
    redis_client.setex(f"disease:{name}", 3600, json.dumps(result))
    
    return result
```

### 2. 数据库优化

```sql
-- 添加索引
CREATE INDEX idx_records_department ON records(department);
CREATE INDEX idx_records_updated_at ON records(updated_at);
CREATE INDEX idx_records_patient_name ON records(patient_name);
```

### 3. ASR优化

调整VAD参数：

```python
# asr_engine.py
self.vad_params = {
    "speech_noise_threshold": 0.7,  # 降低阈值提高灵敏度
    "max_speech_duration": 60,       # 最大语音时长
}
```

---

## 监控和日志

### 1. 应用监控

使用Prometheus + Grafana：

```python
from prometheus_fastapi_instrumentator import Instrumentator

Instrumentator().instrument(app).expose(app)
```

访问指标：`http://localhost:8765/metrics`

### 2. 日志管理

日志文件：
- `audit.log` - API审计日志
- `crash.log` - 崩溃日志
- `asr.log` - ASR识别日志

日志轮转配置（logrotate）：

```
/var/log/medical-record/*.log {
    daily
    rotate 30
    compress
    missingok
    notifempty
}
```

---

## 故障排查

### 问题1：ASR模型加载失败

**症状**: `ASR模型加载失败`

**解决**:
```bash
# 清除缓存重新下载
rm -rf ~/.cache/modelscope/
python -c "from asr_engine import ASREngine; ASREngine()"
```

### 问题2：麦克风无法使用

**症状**: `未检测到麦克风`

**解决**:
```bash
# macOS：检查权限
# 系统偏好设置 -> 安全性与隐私 -> 麦克风

# Linux：检查设备
arecord -l

# Windows：检查设备管理器
```

### 问题3：数据库锁定

**症状**: `database is locked`

**解决**:
```bash
# 关闭所有连接
pkill -f app_server.py

# 清理锁文件
rm -f data/records.db-journal
```

### 问题4：内存不足

**症状**: `MemoryError`

**解决**:
```bash
# 减少知识图谱加载量
# 编辑 knowledge_graph.py，注释掉部分数据加载

# 或增加swap空间
sudo fallocate -l 4G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
```

---

## 升级指南

### 从v1.0升级到v2.0

1. 备份数据：
```bash
cp -r data/ data_backup/
```

2. 拉取新代码：
```bash
git pull origin main
```

3. 更新依赖：
```bash
pip install -r requirements.txt --upgrade
```

4. 运行迁移脚本（如有）：
```bash
python scripts/migrate_v2.py
```

5. 重启服务：
```bash
sudo systemctl restart medical-record
```

---

## 技术支持

- **GitHub Issues**: https://github.com/big-William-1992/xingyan-medical-record/issues
- **文档**: https://github.com/big-William-1992/xingyan-medical-record/wiki
- **邮箱**: support@xingyan.ai

---

## 许可证

MIT License

Copyright (c) 2026 星衍AI
