#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
录音事件处理器
从 main.py 提取：录音开始/停止、识别结果处理、预览确认
"""
import os
import time

from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QMessageBox
from threads import ListenThread


class RecordingHandler:
    """录音与识别事件处理（组合进 MedVoiceApp）"""

    def __init__(self, app):
        """绑定主窗口实例"""
        self.app = app
        self.asr = app.asr

    # ─── 录音流程 ───

    def start_recording(self):
        """开始录音"""
        app = self.app
        if not self.asr.is_ready():
            QMessageBox.warning(
                app, "提示",
                "语音识别引擎未就绪。\n"
                "请确认已安装 FunASR 模型。\n\n"
                "运行：pip install funasr modelscope\n"
                "模型会自动下载到 ~/.cache/modelscope/"
            )
            return

        mode = app.record_mode_combo.currentText()
        if "60" in mode:
            self.asr.recording_duration = 60
        elif "120" in mode:
            self.asr.recording_duration = 120
        else:
            self.asr.recording_duration = 30

        app.record_btn.setText("⏹ 停止录音")
        app.record_btn.setChecked(True)
        app.is_listening = True
        app.partial_text = ""
        app.text_edit.setFocus()

        # 重置悬浮预览面板
        app.asr_preview.reset()
        app.asr_preview.hide_panel()
        app._pending_asr_text = ''

        # 保存录音前的编辑器内容
        app._stream_base_text = app.text_edit.toPlainText()
        app._stream_has_partial = False
        app.partial_label.setText("▍正在聆听，请开始说话...")

        app._record_start_ts = time.time()
        app._duration_timer.start()
        app.recording_indicator.start()

        app.waveform.setVisible(True)
        app.waveform.set_active(True)
        app._wave_timer.start()

        # 模板热词增强
        template_name = app.template_combo.currentText()
        if template_name and app.current_dept:
            tpl_content = app.template_engine.get_template(app.current_dept, template_name)
            if tpl_content:
                self.asr.boost_hotwords_for_template(tpl_content)

        app._update_field_context()

        app.listen_thread = ListenThread(self.asr)
        app.listen_thread.text_ready.connect(app._on_recognized)
        app.listen_thread.partial_text.connect(app._on_partial)
        app.listen_thread.status_changed.connect(app.status_bar.showMessage)
        app.listen_thread.start()

        # 连续模式自动停止
        mode = app.record_mode_combo.currentText()
        if "连续" in mode:
            app._auto_stop_timer = QTimer()
            app._auto_stop_timer.setSingleShot(True)
            app._auto_stop_timer.timeout.connect(app._stop_recording)
            app._auto_stop_timer.start(self.asr.recording_duration * 1000)

    def stop_recording(self):
        """停止录音"""
        app = self.app
        app.is_listening = False
        app.record_btn.setText("🎤 开始录音")
        app.record_btn.setChecked(False)
        app.crash_logger.log_event("录音停止")

        app._duration_timer.stop()
        app._record_start_ts = None
        app.recording_indicator.stop()

        app._wave_timer.stop()
        app.waveform.set_active(False)
        app.waveform.setVisible(False)

        if hasattr(app, '_auto_stop_timer') and app._auto_stop_timer:
            app._auto_stop_timer.stop()
            app._auto_stop_timer = None

        if app.listen_thread:
            app.listen_thread.stop()
            app.listen_thread.wait(2000)
            app.listen_thread = None

        # 无待确认结果时隐藏预览
        if not getattr(app, '_pending_asr_text', ''):
            app.asr_preview.hide_panel()

        app.partial_label.setText("等待输入...")
        app.status_bar.showMessage("录音结束")

    def toggle_recording(self):
        """切换录音状态"""
        if not self.app.is_listening:
            self.start_recording()
        else:
            self.stop_recording()

    # ─── 识别结果处理 ───

    def on_partial(self, text):
        """流式识别中间结果"""
        if not text:
            return
        app = self.app
        app._stream_has_partial = True
        if len(text) > 200:
            text = "…" + text[-200:]
        app.partial_label.setText(f"🔊 识别中：{text}")
        app.asr_preview.show_partial(text)

    def on_recognized(self, text):
        """识别完成：显示预览等待确认"""
        app = self.app
        if not text:
            app.partial_label.setText("⚠️ 未识别到文字，请重试")
            app.status_bar.showMessage("识别完成，但未获取到文字内容")
            app.asr_preview.hide_panel()
            return

        # 语音命令立即执行
        if app._handle_voice_command(text):
            app.partial_label.setText("✓ 已执行语音命令")
            app.asr_preview.hide_panel()
            return

        # 显示预览 + 确认按钮
        app._pending_asr_text = text
        app.asr_preview.show_result(text)
        app.partial_label.setText("✓ 识别完成，请确认预览结果")
        app.status_bar.showMessage("识别完成，点击「接受」填入病历，或拒绝 / 重听")
        app.text_edit.setFocus()

        app._load_last_audio()

    # ─── 预览确认 ───

    def on_preview_accept(self):
        """接受预览：执行填充"""
        app = self.app
        text = getattr(app, '_pending_asr_text', '') or ''
        app._pending_asr_text = ''
        app.asr_preview.hide_panel()
        if text:
            app._apply_asr_result(text)
        else:
            app.partial_label.setText("等待输入...")

    def on_preview_reject(self):
        """拒绝预览：丢弃结果"""
        self.app._pending_asr_text = ''
        self.app.asr_preview.hide_panel()
        self.app.partial_label.setText("已拒绝本次识别结果")
        self.app.status_bar.showMessage("已丢弃识别结果")

    def on_preview_retry(self):
        """重听：重新录音"""
        self.app._pending_asr_text = ''
        self.app.asr_preview.hide_panel()
        if self.app.is_listening:
            self.stop_recording()
        self.toggle_recording()
