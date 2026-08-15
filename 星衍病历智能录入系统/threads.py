#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
线程管理模块
提取自 main.py 的线程类
"""
from PyQt5.QtCore import QThread, pyqtSignal


class ListenThread(QThread):
    """语音识别监听线程"""
    text_ready = pyqtSignal(str)
    partial_text = pyqtSignal(str)
    status_changed = pyqtSignal(str)

    def __init__(self, asr_engine):
        super().__init__()
        self.asr = asr_engine
        self.final_text = ""
        self._polling = True
        self._recording = False

    def run(self):
        self.status_changed.emit("正在录音...")
        self._recording = True

        def _stream_partial(text):
            if text and self._recording:
                self.partial_text.emit(text)

        self.asr.start_listening(on_partial=_stream_partial)

        while self._recording and self.asr.is_listening:
            self.msleep(100)

        self.status_changed.emit("正在识别...")
        text = self.asr.stop_listening()
        self.final_text = text
        self.text_ready.emit(text)
        self.status_changed.emit("识别完成")

    def stop(self):
        self._recording = False


class CorrectThread(QThread):
    """纠错线程"""
    correction_done = pyqtSignal(str, list)

    def __init__(self, corrector, text):
        super().__init__()
        self.corrector = corrector
        self.text = text

    def run(self):
        try:
            corrected, log = self.corrector.correct(self.text)
            self.correction_done.emit(corrected, log)
        except Exception as e:
            self.correction_done.emit(self.text, [{"error": str(e)}])


class DiagnosisThread(QThread):
    """AI辅助诊断线程"""
    analysis_done = pyqtSignal(dict)

    def __init__(self, assistant, text):
        super().__init__()
        self.assistant = assistant
        self.text = text

    def run(self):
        try:
            result = self.assistant.analyze(self.text)
        except Exception as e:
            result = {"error": str(e)}
        self.analysis_done.emit(result)
