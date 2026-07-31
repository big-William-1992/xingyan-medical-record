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
    QWidget, QHBoxLayout, QPushButton, QSlider, QLabel
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QPainter, QColor, QPen


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
