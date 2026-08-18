"""
星衍AI智能病历录入系统 - 主程序入口（thin wrapper）

所有类定义已拆分到 gui/ 子包：
  gui/desktop_main.py  → MedVoiceApp
  gui/webview_main.py  → WebViewApp
  gui/dialogs.py       → RuleManagerDialog, FieldWordsPanel, TemplateManagerDialog, SectionDialog

向后兼容：from main import MedVoiceApp 仍可用（通过 gui/__init__.py 重新导出）
"""
import sys
import os

# ─── QtWebEngine 环境变量（必须在任何 Qt 导入前设置） ───
_os_pre = os
_base_dir = _os_pre.path.dirname(_os_pre.path.abspath(__file__))
_venv_lib = _os_pre.path.join(_base_dir, 'venv', 'lib')

# 动态检测 venv 中的 Python 版本（不硬编码 3.11/3.12/3.14）
_py_ver = f"python{sys.version_info.major}.{sys.version_info.minor}"
_venv_qt = _os_pre.path.join(_venv_lib, _py_ver, 'site-packages', 'PyQt5', 'Qt5')
_os_pre.environ['QTWEBENGINE_RESOURCES_PATH'] = _os_pre.path.join(
    _venv_qt, 'lib', 'QtWebEngineCore.framework', 'Resources'
)
_os_pre.environ['QTWEBENGINE_LOCALES_PATH'] = _os_pre.path.join(
    _venv_qt, 'lib', 'QtWebEngineCore.framework', 'Resources', 'qtwebengine_locales'
)
_os_pre.environ.setdefault('QTWEBENGINE_CHROMIUM_FLAGS', '--no-sandbox')
del _os_pre, _base_dir, _venv_lib, _py_ver

# ─── QtWebEngine 可用性检测 ───
try:
    from PyQt5.QtWebEngineWidgets import QWebEngineView  # noqa: F401
    _HAS_WEBENGINE = True
except ImportError:
    _HAS_WEBENGINE = False


def main():
    """应用启动入口"""
    from PyQt5.QtWidgets import QApplication, QDialog
    from PyQt5.QtGui import QFont
    from gui import MedVoiceApp, WebViewApp
    from license_manager import LicenseManager
    from activation_dialog import ActivationDialog, TrialInfoBar
    from database import Database
    from login_dialog import LoginDialog

    app = QApplication(sys.argv)
    app.setStyle('Fusion')

    font = QFont("Microsoft YaHei", 11)
    app.setFont(font)

    license_mgr = LicenseManager()
    status = license_mgr.check_license()

    if status["status"] in ("expired", "tampered"):
        dlg = ActivationDialog(license_mgr, status)
        if dlg.exec_() != QDialog.Accepted:
            sys.exit(0)

    db = Database()
    login = LoginDialog(db)
    if login.exec_() != QDialog.Accepted or not login.current_user:
        sys.exit(0)

    use_webview = '--legacy' not in sys.argv
    if use_webview and _HAS_WEBENGINE:
        try:
            window = WebViewApp(db=db, current_user=login.current_user)
        except Exception as e:
            print(f"[Main] WebView 初始化失败，回退到原生 UI: {e}")
            window = MedVoiceApp(db=db, current_user=login.current_user)
    else:
        window = MedVoiceApp(db=db, current_user=login.current_user)
    window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
