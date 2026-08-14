"""
音频可视化与回放组件

- WaveformWidget   实时录音波形图（滚动柱状，纯 QPainter，无额外依赖）
- AudioPlayer      基于 sounddevice 的音频播放引擎（支持暂停/定位/进度回调）
- AudioPlayerWidget 播放器 UI（播放/暂停 + 进度条 + 时间），用于音文对照回放
"""
import os
import wave

import numpy as np

from PyQt5.QtWidgets import (
    QWidget, QHBoxLayout, QPushButton, QSlider, QLabel,
    QFrame, QVBoxLayout, QTextBrowser, QGraphicsOpacityEffect
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QPropertyAnimation, QEasingCurve
from PyQt5.QtGui import QPainter, QColor, QPen


# ═══════════════════════════════════════════════════════════
#  悬浮识别预览面板
# ═══════════════════════════════════════════════════════════

class AsrPreviewPanel(QFrame):
    """
    悬浮识别预览面板（PyQt5 原生版）
    - 录音中：show_partial() 实时刷新识别文本（红色指示灯，无按钮）
    - 识别完成：show_result() 显示最终文本 + 接受/拒绝/重听按钮
    确认后发出 accepted / rejected / retried 信号，由主窗口处理。
    """
    accepted = pyqtSignal()
    rejected = pyqtSignal()
    retried = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedWidth(620)
        self.setVisible(False)
        self._build_ui()
        # 淡入淡出动画
        self._effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._effect)
        self._effect.setOpacity(1.0)
        self._anim = None

    def _build_ui(self):
        # 外层容器：半透明玻璃背景 + 圆角边框
        outer = QFrame(self)
        outer.setObjectName("asrPreviewPanel")
        outer.setStyleSheet("""
            #asrPreviewPanel {
                background: rgba(16, 22, 42, 0.94);
                border: 1px solid rgba(0, 212, 255, 0.35);
                border-radius: 14px;
            }
        """)
        outer.setGeometry(0, 0, 620, 0)
        lay = QVBoxLayout(outer)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(8)

        # 标题行：指示灯 + 标题 + 关闭按钮
        hd = QHBoxLayout()
        hd.setSpacing(6)
        self.dot = QLabel("●")
        self.dot.setStyleSheet("color: #ff5f6d; font-size: 10px;")
        self.title_label = QLabel("实时识别预览")
        self.title_label.setStyleSheet("color: #7f8fb2; font-size: 11px; font-weight: bold; letter-spacing: 1px;")
        hd.addWidget(self.dot)
        hd.addWidget(self.title_label)
        hd.addStretch()
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(22, 22)
        close_btn.setToolTip("关闭预览")
        close_btn.setStyleSheet("""
            QPushButton { color: #7f8fb2; background: transparent; border: none;
                           font-size: 12px; border-radius: 11px; }
            QPushButton:hover { color: #fff; background: rgba(255,95,109,0.25); }
        """)
        close_btn.clicked.connect(self.rejected)
        hd.addWidget(close_btn)
        lay.addLayout(hd)

        # 识别文本区（只读，自动滚动到最新）
        self.text_browser = QTextBrowser()
        self.text_browser.setStyleSheet("""
            QTextBrowser {
                background: rgba(255,255,255,0.04);
                border: 1px solid rgba(0,212,255,0.15);
                border-radius: 8px;
                padding: 8px 10px;
                font-size: 13px;
                color: #eef2ff;
            }
        """)
        self.text_browser.setOpenExternalLinks(False)
        self.text_browser.setOpenLinks(False)
        self.text_browser.setMaximumHeight(220)
        lay.addWidget(self.text_browser)

        # 操作按钮行（识别完成后显示）
        self.actions_bar = QWidget()
        ab = QHBoxLayout(self.actions_bar)
        ab.setContentsMargins(0, 0, 0, 0)
        ab.setSpacing(8)
        accept_btn = QPushButton("✓ 接受")
        accept_btn.setStyleSheet("""
            QPushButton { background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #00d4ff, stop:1 #007aa0);
                          color: #0a0e27; padding: 6px 18px; border-radius: 8px; font-weight: bold; }
            QPushButton:hover { background: #00eaff; }
        """)
        reject_btn = QPushButton("✗ 拒绝")
        reject_btn.setStyleSheet("""
            QPushButton { background: rgba(255,95,109,0.15); color: #ff8a95; padding: 6px 14px;
                          border: 1px solid rgba(255,95,109,0.4); border-radius: 8px; }
            QPushButton:hover { background: rgba(255,95,109,0.3); }
        """)
        retry_btn = QPushButton("↻ 重听")
        retry_btn.setStyleSheet("""
            QPushButton { background: rgba(255,196,0,0.12); color: #ffc44d; padding: 6px 14px;
                          border: 1px solid rgba(255,196,0,0.4); border-radius: 8px; }
            QPushButton:hover { background: rgba(255,196,0,0.25); }
        """)
        accept_btn.clicked.connect(self.accepted)
        reject_btn.clicked.connect(self.rejected)
        retry_btn.clicked.connect(self.retried)
        ab.addWidget(accept_btn)
        ab.addWidget(reject_btn)
        ab.addWidget(retry_btn)
        ab.addStretch()
        self.actions_bar.setVisible(False)
        lay.addWidget(self.actions_bar)

    # ─── 状态切换 ───────────────────────────────

    def _fade(self, show):
        """淡入/淡出动画"""
        if self._anim is not None:
            self._anim.stop()
        self._anim = QPropertyAnimation(self._effect, b"opacity", self)
        self._anim.setDuration(160)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self._anim.setStartValue(self._effect.opacity())
        self._anim.setEndValue(1.0 if show else 0.0)
        if show:
            self.setVisible(True)
            self.raise_()
        self._anim.start()
        if not show:
            self._anim.finished.connect(lambda: self.setVisible(False))

    def show_partial(self, text):
        """录音中：实时刷新识别文本（无按钮）"""
        if text:
            self.title_label.setText("实时识别预览")
            self.dot.setStyleSheet("color: #ff5f6d; font-size: 10px;")
            self.actions_bar.setVisible(False)
            self.text_browser.setPlainText(text)
            self.text_browser.verticalScrollBar().setValue(
                self.text_browser.verticalScrollBar().maximum())
            if not self.isVisible():
                self.reposition()
                self._fade(True)

    def show_result(self, text):
        """识别完成：显示最终文本 + 接受/拒绝/重听按钮"""
        if not text:
            return
        self.title_label.setText("识别结果 · 请确认")
        self.dot.setStyleSheet("color: #00d4ff; font-size: 10px;")
        self.actions_bar.setVisible(True)
        self.text_browser.setPlainText(text)
        self.text_browser.verticalScrollBar().setValue(0)
        self.reposition()
        if not self.isVisible():
            self._fade(True)
        self.raise_()

    def reset(self):
        """开始新一次录音前重置面板"""
        self._pending = ""
        self.actions_bar.setVisible(False)
        self.text_browser.clear()

    def hide_panel(self):
        """隐藏面板"""
        if self.isVisible():
            self._fade(False)
        else:
            self.setVisible(False)

    def reposition(self):
        """定位到主窗口底部居中（避开状态栏）"""
        parent = self.parent()
        if parent is None:
            return
        g = parent.geometry()
        x = g.center().x() - self.width() // 2
        y = g.bottom() - self.height() - 46
        self.move(x, y)



# ═══════════════════════════════════════════════════════════
#  实时波形图
# ═══════════════════════════════════════════════════════════

class WaveformWidget(QWidget):
    """
    滚动柱状波形图。录音时由外部以 ~30fps 调用 add_level(0~1) 喂数据。
    新柱从右侧进入，旧柱向左滚动淡出。
    """

    def __init__(self, parent=None, max_bars=80):
        super().__init__(parent)
        self._levels = []          # 历史电平列表
        self._max_bars = max_bars
        self._active = False       # 是否处于录音状态
        self.setMinimumHeight(48)
        self.setMaximumHeight(70)
        self.setStyleSheet("background: transparent;")

    def add_level(self, level):
        """添加一个电平值（0~1）"""
        level = max(0.0, min(1.0, float(level)))
        self._levels.append(level)
        if len(self._levels) > self._max_bars:
            self._levels.pop(0)
        self.update()

    def set_active(self, active):
        """设置录音状态（停止时渐隐清空）"""
        self._active = active
        if not active:
            self._levels = []
        self.update()

    def clear(self):
        self._levels = []
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w, h = self.width(), self.height()
        mid = h / 2.0

        # 背景中线
        painter.setPen(QPen(QColor(0, 212, 255, 40), 1))
        painter.drawLine(0, int(mid), w, int(mid))

        if not self._levels:
            painter.end()
            return

        n = len(self._levels)
        # 柱宽与间距
        gap = 2
        bar_w = max(2, (w - gap * self._max_bars) / self._max_bars)
        step = bar_w + gap
        # 从右往左排列（最新在右）
        start_x = w - n * step

        for i, lv in enumerate(self._levels):
            x = start_x + i * step
            # 越靠右越亮（新数据）
            alpha = int(80 + 175 * (i / max(1, n - 1)))
            bar_h = max(2, lv * (h * 0.9))
            color = QColor(0, 212, 255, alpha)
            painter.setPen(Qt.NoPen)
            painter.setBrush(color)
            y = mid - bar_h / 2.0
            painter.drawRoundedRect(int(x), int(y), int(bar_w), int(bar_h), 1, 1)

        painter.end()


# ═══════════════════════════════════════════════════════════
#  音频播放引擎（sounddevice）
# ═══════════════════════════════════════════════════════════

class AudioPlayer:
    """
    轻量音频播放器：加载 wav → play/pause/stop/seek。
    通过 sounddevice OutputStream 回调送数据，线程安全。
    """

    def __init__(self):
        self._data = None          # float32 一维数组（-1~1）
        self._sr = 16000
        self._frame = 0            # 当前播放帧位置
        self._playing = False
        self._stream = None
        self._lock = __import__("threading").Lock()
        self.on_finished = None    # 播放结束回调

    def load(self, wav_path):
        """加载 wav 文件，返回时长（秒）；失败返回 0"""
        self.stop()
        try:
            with wave.open(wav_path, "rb") as wf:
                self._sr = wf.getframerate()
                n_frames = wf.getnframes()
                raw = wf.readframes(n_frames)
            pcm = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
            self._data = pcm
            self._frame = 0
            return len(pcm) / float(self._sr)
        except Exception as e:
            print(f"[AudioPlayer] 加载失败: {e}")
            self._data = None
            return 0.0

    @property
    def duration(self):
        if self._data is None:
            return 0.0
        return len(self._data) / float(self._sr)

    @property
    def position(self):
        return self._frame / float(self._sr)

    @property
    def is_playing(self):
        return self._playing

    def play(self):
        """从头或当前位置开始播放"""
        if self._data is None or self._playing:
            return
        try:
            import sounddevice as sd
        except Exception as e:
            print(f"[AudioPlayer] sounddevice 不可用: {e}")
            return

        def _callback(outdata, frames, time_info, status):
            with self._lock:
                start = self._frame
                end = start + frames
                if start >= len(self._data):
                    outdata[:] = 0
                    self._playing = False
                    return
                chunk = self._data[start:end]
                if len(chunk) < frames:
                    outdata[:len(chunk), 0] = chunk
                    outdata[len(chunk):] = 0
                    self._frame = len(self._data)
                    self._playing = False
                else:
                    outdata[:, 0] = chunk
                    self._frame = end

        try:
            self._stream = sd.OutputStream(
                samplerate=self._sr, channels=1, dtype="float32",
                callback=_callback, finished_callback=self._on_stream_finished
            )
            self._stream.start()
            self._playing = True
        except Exception as e:
            print(f"[AudioPlayer] 播放启动失败: {e}")

    def pause(self):
        """暂停（停止流但保留位置）"""
        self._playing = False
        if self._stream:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None

    def stop(self):
        """停止并回到开头"""
        self.pause()
        self._frame = 0

    def seek(self, seconds):
        """定位到指定秒数"""
        if self._data is None:
            return
        with self._lock:
            self._frame = int(max(0, min(seconds, self.duration)) * self._sr)

    def _on_stream_finished(self):
        if self.on_finished:
            try:
                self.on_finished()
            except Exception:
                pass


# ═══════════════════════════════════════════════════════════
#  播放器 UI 组件
# ═══════════════════════════════════════════════════════════

class AudioPlayerWidget(QWidget):
    """音文对照播放器：播放/暂停 + 进度条 + 时间显示"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.player = AudioPlayer()
        self._duration = 0.0
        self._dragging = False
        self._build_ui()

        # 进度刷新定时器
        self._timer = QTimer(self)
        self._timer.setInterval(200)
        self._timer.timeout.connect(self._refresh_progress)

        self.player.on_finished = self._on_finished

    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(8)

        self.play_btn = QPushButton("▶ 播放")
        self.play_btn.setFixedWidth(72)
        self.play_btn.setEnabled(False)
        self.play_btn.clicked.connect(self._toggle_play)
        self.play_btn.setStyleSheet("""
            QPushButton {
                background: rgba(0,212,255,0.15);
                color: #00d4ff;
                border: 1px solid rgba(0,212,255,0.3);
                border-radius: 12px;
                padding: 4px;
                font-size: 12px;
            }
            QPushButton:hover { background: rgba(0,212,255,0.25); }
            QPushButton:disabled { color: #555; border-color: #333; }
        """)
        layout.addWidget(self.play_btn)

        self.time_label = QLabel("00:00 / 00:00")
        self.time_label.setStyleSheet("color: #8fa3bf; font-size: 11px;")
        self.time_label.setFixedWidth(86)
        layout.addWidget(self.time_label)

        self.slider = QSlider(Qt.Horizontal)
        self.slider.setEnabled(False)
        self.slider.setRange(0, 1000)
        self.slider.sliderPressed.connect(lambda: setattr(self, "_dragging", True))
        self.slider.sliderReleased.connect(self._on_slider_released)
        layout.addWidget(self.slider)

        self.hint_label = QLabel("录音后可回放校对")
        self.hint_label.setStyleSheet("color: #6b8a9a; font-size: 10px;")
        layout.addWidget(self.hint_label)

        self.setStyleSheet("""
            AudioPlayerWidget {
                background: rgba(255,255,255,0.03);
                border: 1px solid rgba(0,212,255,0.12);
                border-radius: 8px;
            }
            QSlider::groove:horizontal {
                height: 4px; background: rgba(0,212,255,0.15); border-radius: 2px;
            }
            QSlider::handle:horizontal {
                width: 12px; height: 12px; margin: -4px 0;
                background: #00d4ff; border-radius: 6px;
            }
            QSlider::sub-page:horizontal { background: rgba(0,212,255,0.5); border-radius: 2px; }
        """)

    def load(self, wav_path):
        """加载音频文件"""
        if not wav_path or not os.path.exists(wav_path):
            return
        self._duration = self.player.load(wav_path)
        if self._duration > 0:
            self.play_btn.setEnabled(True)
            self.slider.setEnabled(True)
            self.hint_label.setText(os.path.basename(wav_path))
            self.time_label.setText(f"00:00 / {self._fmt(self._duration)}")
            self.slider.setValue(0)

    def _toggle_play(self):
        if self.player.is_playing:
            self.player.pause()
            self.play_btn.setText("▶ 播放")
            self._timer.stop()
        else:
            self.player.play()
            self.play_btn.setText("⏸ 暂停")
            self._timer.start()

    def _on_slider_released(self):
        self._dragging = False
        if self._duration > 0:
            sec = self.slider.value() / 1000.0 * self._duration
            self.player.seek(sec)

    def _refresh_progress(self):
        if self._dragging:
            return
        pos = self.player.position
        if self._duration > 0:
            self.slider.setValue(int(pos / self._duration * 1000))
        self.time_label.setText(f"{self._fmt(pos)} / {self._fmt(self._duration)}")
        if not self.player.is_playing:
            self._timer.stop()
            self.play_btn.setText("▶ 播放")

    def _on_finished(self):
        # 在定时器中复位 UI（避免跨线程操作控件）
        QTimer.singleShot(0, self._reset_after_finish)

    def _reset_after_finish(self):
        self._timer.stop()
        self.play_btn.setText("▶ 播放")
        self.slider.setValue(1000 if self._duration > 0 else 0)
        self.time_label.setText(f"{self._fmt(self._duration)} / {self._fmt(self._duration)}")

    @staticmethod
    def _fmt(seconds):
        seconds = int(max(0, seconds))
        m, s = divmod(seconds, 60)
        return f"{m:02d}:{s:02d}"
