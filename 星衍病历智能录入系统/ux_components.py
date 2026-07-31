"""
UX 增强组件 - Toast 提示 / 新手引导 / 录音动画

独立模块，不依赖业务逻辑，供 main.py 调用。
"""
import json
import os

from PyQt5.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QHBoxLayout,
    QPushButton, QGraphicsOpacityEffect, QFrame
)
from PyQt5.QtCore import (
    Qt, QTimer, QPropertyAnimation, QPoint, QEasingCurve, pyqtProperty, QRectF
)
from PyQt5.QtGui import (
    QFont, QColor, QPainter, QBrush, QPen,
    QSyntaxHighlighter, QTextCharFormat
)

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_GUIDE_FLAG = os.path.join(_BASE_DIR, ".guide_done")


# ═══════════════════════════════════════════════════════════
#  病历字段名语法高亮
# ═══════════════════════════════════════════════════════════

class FieldHighlighter(QSyntaxHighlighter):
    """
    对病历编辑器中的字段名（主诉：、现病史：等）进行着色，
    让结构一目了然。
    """

    # 字段名 → 颜色
    FIELD_COLORS = {
        # 病史类（青绿）
        "主诉": "#4dd0a1", "现病史": "#4dd0a1", "既往史": "#4dd0a1",
        "个人史": "#4dd0a1", "家族史": "#4dd0a1", "婚育史": "#4dd0a1",
        "月经史": "#4dd0a1", "过敏史": "#4dd0a1",
        # 查体/检查类（金黄）
        "体格检查": "#ffd166", "专科检查": "#ffd166",
        "辅助检查": "#ffd166", "实验室检查": "#ffd166",
        # 诊断类（珊瑚红）
        "初步诊断": "#ff8a7a", "入院诊断": "#ff8a7a", "出院诊断": "#ff8a7a",
        "诊断意见": "#ff8a7a", "诊断": "#ff8a7a",
        # 治疗/经过类（淡蓝）
        "诊疗经过": "#6ec6ff", "治疗经过": "#6ec6ff",
        "手术名称": "#6ec6ff", "手术经过": "#6ec6ff",
        "术后诊断": "#6ec6ff", "术前诊断": "#6ec6ff",
        # 医嘱/情况类（淡紫）
        "出院医嘱": "#c792ea", "出院情况": "#c792ea",
        "入院情况": "#c792ea", "病情变化": "#c792ea",
        # 影像类（青绿）
        "影像表现": "#4dd0a1", "影像所见": "#4dd0a1",
        "超声所见": "#4dd0a1", "超声提示": "#ffd166",
        "检查项目": "#ffd166", "检查部位": "#ffd166",
        # 基本信息（灰蓝）
        "姓名": "#8fa3bf", "性别": "#8fa3bf", "年龄": "#8fa3bf",
        "科室": "#8fa3bf", "床号": "#8fa3bf", "住院号": "#8fa3bf",
    }

    def __init__(self, document):
        super().__init__(document)
        self._rules = []
        # 按字段名长度降序（优先匹配长字段，避免“诊断”抢了“初步诊断”）
        for field, color in sorted(self.FIELD_COLORS.items(),
                                   key=lambda kv: -len(kv[0])):
            fmt = QTextCharFormat()
            fmt.setForeground(QColor(color))
            fmt.setFontWeight(QFont.Bold)
            # 匹配 “字段名：” 或 “字段名:”（行首或任意位置）
            import re
            pattern = re.compile(re.escape(field) + r"[：:]")
            self._rules.append((pattern, fmt))

    def highlightBlock(self, text):
        for pattern, fmt in self._rules:
            for m in pattern.finditer(text):
                self.setFormat(m.start(), m.end() - m.start(), fmt)


# ═══════════════════════════════════════════════════════════
#  Toast 非阻断提示（右下角淡入淡出）
# ═══════════════════════════════════════════════════════════

class Toast(QWidget):
    """
    轻量级非阻断提示，显示在父窗口右下角，自动淡出消失。

    用法：
        Toast.show_toast(parent, "✓ 已保存", level="success")
    """

    LEVELS = {
        "success": ("#51cf66", "✓"),
        "info":    ("#00d4ff", "ℹ"),
        "warning": ("#ffdd44", "⚠"),
        "error":   ("#ff6b6b", "✗"),
    }

    def __init__(self, parent, message, level="info", duration=2500):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)

        color, icon = self.LEVELS.get(level, self.LEVELS["info"])

        # 布局
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 10, 16, 10)

        icon_label = QLabel(icon)
        icon_label.setStyleSheet(f"color: {color}; font-size: 16px; font-weight: bold;")
        layout.addWidget(icon_label)

        msg_label = QLabel(message)
        msg_label.setStyleSheet(f"color: #e0e0e0; font-size: 13px;")
        msg_label.setWordWrap(True)
        layout.addWidget(msg_label)

        # 背景样式
        self.setStyleSheet(f"""
            Toast {{
                background: rgba(20, 25, 50, 0.95);
                border: 1px solid {color}44;
                border-radius: 10px;
            }}
        """)
        self.setFixedWidth(min(320, max(200, len(message) * 14 + 60)))

        # 定位到父窗口右下角
        if parent:
            parent_geo = parent.geometry()
            x = parent_geo.right() - self.width() - 20
            y = parent_geo.bottom() - self.height() - 60
            self.move(x, y)

        # 淡入
        self._opacity_fx = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._opacity_fx)
        self._fade_in = QPropertyAnimation(self._opacity_fx, b"opacity")
        self._fade_in.setDuration(200)
        self._fade_in.setStartValue(0.0)
        self._fade_in.setEndValue(1.0)
        self._fade_in.setEasingCurve(QEasingCurve.OutCubic)

        # 淡出
        self._fade_out = QPropertyAnimation(self._opacity_fx, b"opacity")
        self._fade_out.setDuration(400)
        self._fade_out.setStartValue(1.0)
        self._fade_out.setEndValue(0.0)
        self._fade_out.setEasingCurve(QEasingCurve.InCubic)
        self._fade_out.finished.connect(self.close)

        # 自动消失计时器
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._start_fade_out)
        self._timer.start(duration)

    def showEvent(self, event):
        super().showEvent(event)
        self._fade_in.start()

    def _start_fade_out(self):
        self._fade_out.start()

    @staticmethod
    def show_toast(parent, message, level="info", duration=2500):
        """静态方法：快速显示一条 Toast"""
        toast = Toast(parent, message, level, duration)
        toast.show()
        # 保持引用防止被 GC（挂在 parent 上）
        if parent:
            if not hasattr(parent, '_toasts'):
                parent._toasts = []
            parent._toasts.append(toast)
            # 清理已关闭的
            parent._toasts = [t for t in parent._toasts if t.isVisible()]
        return toast


# ═══════════════════════════════════════════════════════════
#  录音状态指示器（脉冲动画标签）
# ═══════════════════════════════════════════════════════════

class RecordingIndicator(QLabel):
    """
    录音中的脉冲动画指示器。
    显示 "🔴 录音中 00:12" 并带有呼吸灯效果。
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._seconds = 0
        self._pulse_on = True
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self.setAlignment(Qt.AlignCenter)
        self._update_text()
        self.hide()

    def start(self):
        """开始录音指示"""
        self._seconds = 0
        self._pulse_on = True
        self._update_text()
        self.show()
        self._timer.start(500)  # 每 500ms 闪烁一次

    def stop(self):
        """停止录音指示"""
        self._timer.stop()
        self.hide()

    def _tick(self):
        self._seconds += 0.5
        self._pulse_on = not self._pulse_on
        self._update_text()

    def _update_text(self):
        elapsed = int(self._seconds)
        mm, ss = divmod(elapsed, 60)
        dot = "🔴" if self._pulse_on else "⚫"
        self.setText(f"  {dot} 录音中 {mm:02d}:{ss:02d}  ")
        opacity = "1.0" if self._pulse_on else "0.6"
        self.setStyleSheet(f"""
            QLabel {{
                color: #ff4444;
                font-size: 13px;
                font-weight: bold;
                opacity: {opacity};
                background: rgba(255, 68, 68, 0.08);
                border: 1px solid rgba(255, 68, 68, 0.3);
                border-radius: 12px;
                padding: 3px 10px;
            }}
        """)


# ═══════════════════════════════════════════════════════════
#  新手引导（首次启动 3 步提示）
# ═══════════════════════════════════════════════════════════

class OnboardingGuide(QWidget):
    """
    首次启动时的半透明引导遮罩，3 步提示核心操作。
    完成后写入 .guide_done 标记，不再显示。
    """

    STEPS = [
        ("① 选择科室和模板", "顶部下拉框选择科室（如内科），再选择病历模板（如入院记录）。\n常见病模板可自动填充占位符。"),
        ("② 点击麦克风开始录音", "点击蓝色「🎤 开始录音」按钮（或按 F2），对着麦克风说病历内容。\n系统会实时识别并自动填入模板。"),
        ("③ 纠错 → 保存 → 导出", "说完后按 F4 一键纠错，Ctrl+S 保存到病历库，\n或点击「💾 导出」生成 Word/txt 文件。"),
    ]

    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self._step = 0

        # 全屏覆盖
        if parent:
            self.setGeometry(0, 0, parent.width(), parent.height())

        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # 半透明背景
        self.setStyleSheet("background: rgba(5, 8, 25, 0.85);")

        # 中央卡片
        self._card = QFrame(self)
        self._card.setFixedSize(480, 260)
        self._card.setStyleSheet("""
            QFrame {
                background: rgba(15, 20, 45, 0.98);
                border: 1px solid rgba(0, 212, 255, 0.3);
                border-radius: 16px;
            }
        """)
        card_layout = QVBoxLayout(self._card)
        card_layout.setContentsMargins(30, 25, 30, 20)
        card_layout.setSpacing(12)

        # 标题
        self._title = QLabel()
        self._title.setStyleSheet("color: #00d4ff; font-size: 20px; font-weight: bold;")
        self._title.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(self._title)

        # 内容
        self._content = QLabel()
        self._content.setStyleSheet("color: #b8c5d6; font-size: 14px; line-height: 1.6;")
        self._content.setAlignment(Qt.AlignCenter)
        self._content.setWordWrap(True)
        card_layout.addWidget(self._content)

        card_layout.addStretch()

        # 按钮行
        btn_row = QHBoxLayout()

        self._skip_btn = QPushButton("跳过引导")
        self._skip_btn.setStyleSheet("""
            QPushButton {
                color: #6b8a9a; background: transparent;
                border: none; font-size: 12px; padding: 5px;
            }
            QPushButton:hover { color: #b8c5d6; }
        """)
        self._skip_btn.clicked.connect(self._finish)
        btn_row.addWidget(self._skip_btn)

        btn_row.addStretch()

        # 步骤指示
        self._dots = QLabel()
        self._dots.setStyleSheet("color: #6b8a9a; font-size: 12px;")
        self._dots.setAlignment(Qt.AlignCenter)
        btn_row.addWidget(self._dots)

        btn_row.addStretch()

        self._next_btn = QPushButton("下一步 →")
        self._next_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 #00d4ff, stop:1 #0066ff);
                color: #0a0e27; font-weight: bold;
                padding: 8px 24px; border-radius: 16px; font-size: 13px;
            }
            QPushButton:hover { background: #00d4ff; }
        """)
        self._next_btn.clicked.connect(self._next_step)
        btn_row.addWidget(self._next_btn)

        card_layout.addLayout(btn_row)

        # 居中放置卡片
        layout.addWidget(self._card, alignment=Qt.AlignCenter)

        self._show_step()

    def _show_step(self):
        title, content = self.STEPS[self._step]
        self._title.setText(title)
        self._content.setText(content)
        dots = "  ".join(
            "●" if i == self._step else "○"
            for i in range(len(self.STEPS))
        )
        self._dots.setText(dots)
        if self._step == len(self.STEPS) - 1:
            self._next_btn.setText("开始使用 ✓")

    def _next_step(self):
        self._step += 1
        if self._step >= len(self.STEPS):
            self._finish()
        else:
            self._show_step()

    def _finish(self):
        """完成引导，写入标记文件"""
        try:
            with open(_GUIDE_FLAG, "w") as f:
                f.write("done")
        except Exception:
            pass
        self.close()

    @staticmethod
    def should_show():
        """是否应显示引导（首次启动）"""
        return not os.path.exists(_GUIDE_FLAG)

    @staticmethod
    def show_if_needed(parent):
        """首次启动时显示引导"""
        if OnboardingGuide.should_show():
            guide = OnboardingGuide(parent)
            guide.show()
            return guide
        return None
