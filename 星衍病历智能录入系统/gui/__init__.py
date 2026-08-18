"""
gui 包 —— 桌面端与 WebView 界面模块。

向后兼容导入路径：
    from gui import MedVoiceApp, WebViewApp
    from gui import RuleManagerDialog, FieldWordsPanel, TemplateManagerDialog, SectionDialog
"""
from gui.dialogs import (
    RuleManagerDialog,
    FieldWordsPanel,
    TemplateManagerDialog,
    SectionDialog,
)
from gui.desktop_main import MedVoiceApp

try:
    from gui.webview_main import WebViewApp
except ImportError:
    WebViewApp = None  # PyQt5-WebEngine 未安装

__all__ = [
    "MedVoiceApp",
    "WebViewApp",
    "RuleManagerDialog",
    "FieldWordsPanel",
    "TemplateManagerDialog",
    "SectionDialog",
]
