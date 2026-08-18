#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
星衍AI · 前后端分离后端服务 — 向后兼容层

实际实现已迁移至 server/ 包：
    server/
    ├── __init__.py          # FastAPI app 创建、CORS、路由注册
    ├── singletons.py        # 单例惰性初始化
    ├── middleware.py        # 认证、限流、审计
    ├── routes_auth.py       # 登录路由
    ├── routes_records.py    # 病历 CRUD
    ├── routes_qa.py         # 知识图谱 + 纠错
    ├── routes_templates.py  # 模板管理
    ├── routes_system.py     # 系统状态 + 离线模式
    └── routes_static.py     # 静态文件

启动方式：
    python -m server          # 推荐
    python app_server.py      # 向后兼容（本文件）
"""
from server import app

__all__ = ["app"]
