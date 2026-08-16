# 微服务架构升级方案

## 概述

本文档描述星衍AI智能病历录入系统从单体架构向微服务架构升级的方案。

## 当前架构（单体）

```
┌─────────────────────────────────────┐
│         星衍AI 单体应用              │
│  ┌──────────────────────────────┐  │
│  │  FastAPI + Vue + ASR + KG    │  │
│  │  + 纠错 + 模板 + 数据库      │  │
│  └──────────────────────────────┘  │
│         SQLite Database            │
└─────────────────────────────────────┘
```

**优点**：
- 部署简单
- 开发快速
- 调试方便

**缺点**：
- 扩展性差
- 技术栈锁定
- 单点故障
- 团队协作困难

## 目标架构（微服务）

```
                    ┌──────────────┐
                    │   API 网关   │
                    │   (Kong)     │
                    └──────┬───────┘
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
        ▼                  ▼                  ▼
┌───────────────┐  ┌───────────────┐  ┌───────────────┐
│  用户服务     │  │  病历服务     │  │  ASR 服务     │
│  (FastAPI)    │  │  (FastAPI)    │  │  (FastAPI)    │
│  - 认证       │  │  - CRUD       │  │  - 语音识别   │
│  - 权限       │  │  - 模板       │  │  - 流式处理   │
│  - 会话       │  │  - 导出       │  │  - 模型管理   │
└───────┬───────┘  └───────┬───────┘  └───────┬───────┘
        │                  │                  │
        └──────────────────┼──────────────────┘
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
        ▼                  ▼                  ▼
┌───────────────┐  ┌───────────────┐  ┌───────────────┐
│  知识图谱服务 │  │  纠错服务     │  │  通知服务     │
│  (FastAPI)    │  │  (FastAPI)    │  │  (FastAPI)    │
│  - 查询       │  │  - 规则引擎   │  │  - 邮件       │
│  - 问答       │  │  - NLP        │  │  - WebSocket  │
│  - 缓存       │  │  - 学习       │  │  - 推送       │
└───────┬───────┘  └───────┬───────┘  └───────┬───────┘
        │                  │                  │
        └──────────────────┼──────────────────┘
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
        ▼                  ▼                  ▼
┌───────────────┐  ┌───────────────┐  ┌───────────────┐
│  PostgreSQL   │  │    Redis      │  │  RabbitMQ     │
│  (主数据库)   │  │   (缓存)      │  │  (消息队列)   │
└───────────────┘  └───────────────┘  └───────────────┘
```

## 服务拆分

### 1. 用户服务 (User Service)

**职责**：
- 用户注册/登录
- JWT Token 管理
- 权限控制
- 会话管理

**API 端点**：
```
POST   /api/auth/register    # 注册
POST   /api/auth/login       # 登录
POST   /api/auth/logout      # 登出
GET    /api/auth/me          # 获取当前用户
PUT    /api/auth/password    # 修改密码
```

**数据库表**：
```sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(20) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 2. 病历服务 (Record Service)

**职责**：
- 病历 CRUD
- 模板管理
- 病历导出
- 版本控制

**API 端点**：
```
GET    /api/records           # 列表
POST   /api/records           # 创建
GET    /api/records/{id}      # 详情
PUT    /api/records/{id}      # 更新
DELETE /api/records/{id}      # 删除
GET    /api/records/{id}/export/hl7   # 导出 HL7
GET    /api/records/{id}/export/fhir  # 导出 FHIR
```

**数据库表**：
```sql
CREATE TABLE records (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    patient_name VARCHAR(100),
    department VARCHAR(50),
    content TEXT,
    version INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE templates (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    department VARCHAR(50) NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 3. ASR 服务 (ASR Service)

**职责**：
- 语音识别
- 流式处理
- 模型管理
- 热词管理

**API 端点**：
```
POST   /api/asr/transcribe   # 文件转写
WS     /api/asr/stream       # 流式识别
GET    /api/asr/models       # 模型列表
POST   /api/asr/hotwords     # 更新热词
```

**技术栈**：
- FunASR Paraformer
- WebSocket 流式处理
- GPU 加速（可选）

### 4. 知识图谱服务 (KG Service)

**职责**：
- 知识图谱查询
- 智能问答
- 实体识别
- 关系推理

**API 端点**：
```
GET    /api/kg/disease/{name}     # 疾病查询
GET    /api/kg/drug/{name}        # 药物查询
GET    /api/kg/query              # 智能问答
POST   /api/kg/entities           # 实体识别
```

**技术栈**：
- Neo4j（图数据库）或 PostgreSQL + 索引
- Redis 缓存
- 向量数据库（可选）

### 5. 纠错服务 (Correction Service)

**职责**：
- 文本纠错
- 规则引擎
- NLP 处理
- 学习反馈

**API 端点**：
```
POST   /api/correct          # 文本纠错
GET    /api/correct/rules    # 规则列表
POST   /api/correct/rules    # 添加规则
POST   /api/correct/feedback # 反馈学习
```

### 6. 通知服务 (Notification Service)

**职责**：
- WebSocket 实时通知
- 邮件通知
- 推送通知
- 消息队列消费

**API 端点**：
```
WS     /ws/notifications     # WebSocket 连接
POST   /api/notifications/email  # 发送邮件
```

## 技术选型

### API 网关
- **Kong** 或 **Traefik**
- 负载均衡
- 认证授权
- 限流熔断

### 服务注册与发现
- **Consul** 或 **etcd**
- 服务健康检查
- 动态路由

### 消息队列
- **RabbitMQ** 或 **Kafka**
- 异步通信
- 事件驱动

### 数据库
- **PostgreSQL**（主数据库）
- **Redis**（缓存）
- **Neo4j**（图数据库，可选）

### 容器编排
- **Docker Compose**（开发环境）
- **Kubernetes**（生产环境）

## 迁移步骤

### 阶段 1：准备（1-2周）
1. 代码模块化
2. 数据库拆分设计
3. API 网关搭建
4. 消息队列部署

### 阶段 2：拆分核心服务（2-4周）
1. 用户服务拆分
2. 病历服务拆分
3. ASR 服务拆分
4. 集成测试

### 阶段 3：拆分辅助服务（2-3周）
1. 知识图谱服务
2. 纠错服务
3. 通知服务
4. 端到端测试

### 阶段 4：优化与监控（1-2周）
1. 性能优化
2. 监控告警
3. 日志聚合
4. 文档完善

## 优势

### 扩展性
- 独立扩展每个服务
- 水平扩展能力
- 负载均衡

### 技术灵活性
- 每个服务可选择最适合的技术栈
- 独立部署和升级
- 降低技术债务

### 团队协作
- 团队独立开发不同服务
- 减少代码冲突
- 加快开发速度

### 可靠性
- 服务隔离，故障不扩散
- 熔断降级
- 快速恢复

## 挑战

### 复杂性增加
- 分布式系统调试困难
- 网络通信开销
- 数据一致性

### 运维成本
- 需要容器编排平台
- 监控和日志系统
- 服务治理

### 开发门槛
- 需要理解微服务架构
- 分布式事务处理
- 服务间通信

## 建议

### 何时迁移
- 团队规模 > 10人
- 用户量 > 10000
- 需要独立扩展某些功能
- 需要多技术栈支持

### 何时保持单体
- 团队规模 < 5人
- 用户量 < 1000
- 功能相对简单
- 快速迭代阶段

## 总结

微服务架构升级是一个长期过程，需要根据实际情况逐步推进。建议：

1. **先模块化**：在单体架构内实现模块化
2. **逐步拆分**：从最独立的服务开始拆分
3. **充分测试**：每个阶段都要充分测试
4. **监控先行**：先建立监控体系再拆分
5. **团队培训**：确保团队理解微服务架构

当前阶段建议先完成模块化，为未来微服务化做准备。
