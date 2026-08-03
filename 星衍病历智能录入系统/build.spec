# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec 文件 — 星衍AI 智能病历录入系统
用法: pyinstaller build.spec
"""
import os
import sys

block_cipher = None

# 项目根目录
BASE = os.path.abspath('.')

# 需要打包的数据文件（HTML前端、模板、知识图谱、模型配置等）
datas = [
    ('frontend', 'frontend'),
    ('templates', 'templates'),
    ('kg_data', 'kg_data'),
    ('model', 'model'),
    ('field_words.json', '.'),
    ('field_presets.json', '.'),
    ('hotwords.txt', '.'),
    ('correction_rules.json', '.'),
    ('medical_dict.json', '.'),
    ('asr_confusion_pairs.json', '.'),
]

# 隐式导入（PyInstaller 可能检测不到的模块）
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
    'webview',
    'webview.platforms',
    'webview.platforms.edgechromium',
    'webview.platforms.cocoa',
    'webview.platforms.gtk',
    'webview.platforms.qt',
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
    # FunASR 相关
    'funasr',
    'torch',
    'torchaudio',
    'numpy',
    'soundfile',
    'scipy',
    'jieba',
    'kenlm',
]

a = Analysis(
    ['gui_launcher.py'],
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
    name='星衍AI病历录入',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,  # 保留控制台窗口（调试用，发布时可改False）
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # 可添加 icon='icon.ico'
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='星衍AI病历录入',
)

# macOS .app 包
if sys.platform == 'darwin':
    app = BUNDLE(
        coll,
        name='星衍AI病历录入.app',
        icon=None,
        bundle_identifier='com.xingyan.medical-voice',
        info_plist={
            'NSMicrophoneUsageDescription': '需要麦克风权限进行语音识别录入病历',
            'NSHighResolutionCapable': True,
        },
    )
