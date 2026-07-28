"""
激活对话框 UI
- 显示机器码（供用户复制给管理员申请激活码）
- 输入激活码
- 显示授权状态 / 剩余天数
- 试用期提示
"""
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QMessageBox, QFrame, QApplication,
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QPalette, QColor

from license_manager import LicenseManager, TRIAL_DAYS


class ActivationDialog(QDialog):
    """软件激活对话框（试用到期后弹出）"""

    RESULT_ACTIVATED = 1   # 激活成功
    RESULT_EXIT = 0        # 退出

    def __init__(self, license_mgr: LicenseManager, status: dict, parent=None):
        super().__init__(parent)
        self.license_mgr = license_mgr
        self.status = status
        self._result_code = self.RESULT_EXIT
        self._init_ui()
        self._apply_style()

    def _init_ui(self):
        self.setWindowTitle("星衍病历智能录入系统 - 软件授权")
        self.setFixedSize(520, 420)
        self.setModal(True)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(24, 20, 24, 20)

        # ─── 标题 ───
        title = QLabel("🔐 软件授权")
        title.setFont(QFont("", 16, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # ─── 状态信息 ───
        status_text = self.status.get("message", "")
        status_color = "#ff6b6b" if self.status["status"] in ("expired", "tampered") else "#4ecdc4"

        self.status_label = QLabel(status_text)
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet(f"color: {status_color}; font-size: 13px; padding: 8px;")
        layout.addWidget(self.status_label)

        # ─── 分割线 ───
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("color: rgba(255,255,255,0.1);")
        layout.addWidget(line)

        # ─── 机器码区域 ───
        mid_label = QLabel("机器码（请复制发给管理员获取激活码）：")
        mid_label.setStyleSheet("color: #b8c5d6; font-size: 12px;")
        layout.addWidget(mid_label)

        mid_row = QHBoxLayout()
        self.machine_id_edit = QLineEdit(self.license_mgr.get_machine_id_display())
        self.machine_id_edit.setReadOnly(True)
        self.machine_id_edit.setAlignment(Qt.AlignCenter)
        self.machine_id_edit.setStyleSheet("""
            QLineEdit {
                background: rgba(255,255,255,0.05);
                border: 1px solid rgba(0,212,255,0.2);
                border-radius: 4px;
                color: #00d4ff;
                font-size: 15px;
                font-family: Consolas, monospace;
                padding: 6px;
                letter-spacing: 2px;
            }
        """)
        mid_row.addWidget(self.machine_id_edit)

        copy_btn = QPushButton("复制")
        copy_btn.setFixedSize(60, 32)
        copy_btn.setCursor(Qt.PointingHandCursor)
        copy_btn.clicked.connect(self._copy_machine_id)
        mid_row.addWidget(copy_btn)
        layout.addLayout(mid_row)

        # ─── 激活码输入 ───
        code_label = QLabel("激活码：")
        code_label.setStyleSheet("color: #b8c5d6; font-size: 12px;")
        layout.addWidget(code_label)

        self.code_edit = QLineEdit()
        self.code_edit.setPlaceholderText("XXXX-XXXX-XXXX-XXXX")
        self.code_edit.setAlignment(Qt.AlignCenter)
        self.code_edit.setMaxLength(19)  # 16 chars + 3 dashes
        self.code_edit.setStyleSheet("""
            QLineEdit {
                background: rgba(255,255,255,0.08);
                border: 1px solid rgba(0,212,255,0.3);
                border-radius: 4px;
                color: #e0e0e0;
                font-size: 15px;
                font-family: Consolas, monospace;
                padding: 6px;
                letter-spacing: 2px;
            }
            QLineEdit:focus {
                border-color: rgba(0,212,255,0.6);
            }
        """)
        self.code_edit.textChanged.connect(self._format_code)
        self.code_edit.returnPressed.connect(self._activate)
        layout.addWidget(self.code_edit)

        # ─── 激活按钮 ───
        self.activate_btn = QPushButton("🔓 激活")
        self.activate_btn.setCursor(Qt.PointingHandCursor)
        self.activate_btn.clicked.connect(self._activate)
        self.activate_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #00b4d8, stop:1 #00d4ff);
                color: white;
                font-size: 14px;
                font-weight: bold;
                border: none;
                border-radius: 6px;
                padding: 10px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #0096c7, stop:1 #00b4d8);
            }
            QPushButton:pressed {
                background: #0077b6;
            }
        """)
        layout.addWidget(self.activate_btn)

        # ─── 激活 / 退出按钮 ───
        btn_row = QHBoxLayout()

        exit_btn = QPushButton("退出")
        exit_btn.setCursor(Qt.PointingHandCursor)
        exit_btn.clicked.connect(self.reject)
        exit_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255,80,80,0.1);
                color: #ff9b9b;
                font-size: 12px;
                border: 1px solid rgba(255,80,80,0.2);
                border-radius: 6px;
                padding: 8px;
            }
            QPushButton:hover {
                background: rgba(255,80,80,0.2);
            }
        """)
        btn_row.addWidget(exit_btn)
        layout.addLayout(btn_row)

        # ─── 底部提示 ───
        hint = QLabel(f"试用期 {TRIAL_DAYS} 天已到期，请联系管理员获取激活码")
        hint.setAlignment(Qt.AlignCenter)
        hint.setStyleSheet("color: #6b8a9a; font-size: 11px; margin-top: 4px;")
        layout.addWidget(hint)

    def _apply_style(self):
        self.setStyleSheet("""
            QDialog {
                background: #1a1a2e;
            }
            QLabel {
                color: #e0e0e0;
            }
            QPushButton {
                font-family: "Microsoft YaHei", "PingFang SC", sans-serif;
            }
        """)

    def _format_code(self, text):
        """自动格式化激活码输入（每4位加横线）"""
        raw = text.replace("-", "").upper()[:16]
        formatted = "-".join(raw[i:i+4] for i in range(0, len(raw), 4))
        if formatted != text:
            self.code_edit.setText(formatted)

    def _copy_machine_id(self):
        clipboard = QApplication.clipboard()
        clipboard.setText(self.license_mgr.get_machine_id())
        self.status_label.setText("✅ 机器码已复制到剪贴板")
        self.status_label.setStyleSheet("color: #4ecdc4; font-size: 13px; padding: 8px;")

    def _activate(self):
        code = self.code_edit.text().strip()
        if not code or len(code.replace("-", "")) != 16:
            self.status_label.setText("❌ 请输入完整的 16 位激活码")
            self.status_label.setStyleSheet("color: #ff6b6b; font-size: 13px; padding: 8px;")
            return

        result = self.license_mgr.activate(code)
        if result["success"]:
            self.status_label.setText(f"✅ {result['message']}")
            self.status_label.setStyleSheet("color: #4ecdc4; font-size: 13px; padding: 8px;")
            self._result_code = self.RESULT_ACTIVATED
            self.accept()
        else:
            self.status_label.setText(f"❌ {result['message']}")
            self.status_label.setStyleSheet("color: #ff6b6b; font-size: 13px; padding: 8px;")

    def get_result_code(self) -> int:
        return self._result_code


class TrialInfoBar:
    """主窗口中的试用期信息条（嵌入状态栏）"""

    @staticmethod
    def create_label(license_mgr: LicenseManager) -> QLabel:
        """创建显示剩余天数的 QLabel"""
        status = license_mgr.check_license()
        remaining = status.get("days_remaining")

        label = QLabel()
        if status["status"] == "trial" and remaining is not None:
            if remaining <= 7:
                color = "#ff6b6b"
            elif remaining <= 30:
                color = "#ffa94d"
            else:
                color = "#4ecdc4"
            label.setText(f"免费试用 剩余 {remaining} 天")
            label.setStyleSheet(f"color: {color}; font-size: 11px; padding: 0 8px;")
            first_run = status.get("first_run_at", "未知")
            label.setToolTip(
                f"首次运行：{first_run}\n"
                f"试用期 {TRIAL_DAYS} 天\n"
                f"到期后需联系管理员获取激活码"
            )
        elif status["status"] == "activated":
            label.setText("✅ 已激活")
            label.setStyleSheet("color: #4ecdc4; font-size: 11px; padding: 0 8px;")
            label.setToolTip("软件已永久授权")
        else:
            label.setText("")
        return label
