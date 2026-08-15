# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec 文件 — 星衍AI 智能病历录入系统（简化版）
仅打包 Web 后端，不包含桌面 GUI
用法: pyinstaller build-web.spec
"""
import os
import sys

block_cipher = None

# 项目根目录
BASE = os.path.abspath('.')

# 需要打包的数据文件
datas = [
    ('frontend', 'frontend'),
    ('templates', 'templates'),
    ('kg_data', 'kg_data'),
    ('field_words.json', '.'),
    ('field_presets.json', '.'),
    ('hotwords.txt', '.'),
    ('correction_rules.json', '.'),
    ('medical_dict.json', '.'),
    ('asr_confusion_pairs.json', '.'),
]

# 可选数据文件
if os.path.exists('model'):
    datas.append(('model', 'model'))
    print("✅ 包含 model 目录")
else:
    print("⚠️  model 目录不存在，跳过")

# FunASR 数据文件（修复打包后 version.txt 缺失问题）
funasr_path = None
try:
    import funasr
    funasr_path = os.path.dirname(funasr.__file__)
    funasr_version_file = os.path.join(funasr_path, 'version.txt')
    if os.path.exists(funasr_version_file):
        datas.append((funasr_version_file, 'funasr'))
        print(f"✅ 包含 funasr/version.txt")
    else:
        print(f"⚠️  funasr/version.txt 不存在")
except ImportError:
    print("⚠️  funasr 未安装，跳过")

# 隐式导入
hiddenimports = [
    'uvicorn',
    'uvicorn.logging',
    'uvicorn.loops',
    'uvicorn.loops.auto',
    'uvicorn.protocols',
    'uvicorn.protocols.http',
    'uvicorn.protocols.http.auto',
    'uvicorn.protocols.websockets',
    'uvicorn.protocols.websockets.auto',
    'uvicorn.lifespan',
    'uvicorn.lifespan.on',
    'fastapi',
    'starlette',
    'starlette.routing',
    'starlette.responses',
    'starlette.staticfiles',
    'starlette.middleware',
    'starlette.middleware.cors',
    'multipart',
    'pydantic',
    'pydantic_core',
    'annotated_types',
    'anyio',
    'anyio._backends',
    'anyio._backends._asyncio',
    'httpx',
    'httpcore',
    'h11',
    'certifi',
    'sniffio',
    'idna',
    'slowapi',  # 添加 slowapi
    'limits',   # slowapi 依赖
    # 业务模块
    'app_server',
    'asr_engine',
    'corrector',
    'template_engine',
    'rule_engine',
    'section_parser',
    'medical_classifier',
    'knowledge_graph',
    'knowledge_qa',
    'correction_feedback',
    'database',
    'voice_command',
    'phrase_library',
    # 新增模块
    'cache_manager',
    'hl7_fhir_exporter',
    # FunASR 相关
    'funasr',
    'modelscope',  # 模型自动下载
    'torch',
    'torchaudio',
    'numpy',
    'soundfile',
    'scipy',
    'jieba',
]

a = Analysis(
    ['app_server.py'],  # 直接打包 app_server
    pathex=[BASE],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'matplotlib',
        'PIL',
        'IPython',
        'notebook',
        'pytest',
        'PyQt5',  # 排除 PyQt5
        'pywebview',  # 排除 pywebview
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='星衍AI-Web服务',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='星衍AI-Web服务',
)
