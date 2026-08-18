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

        # on_stream_error 用于通知 UI 层恢复状态（退避 / 熔断 / 恢复）
        def _on_stream_error(msg):
            if msg and self._recording:
                self.status_changed.emit(msg)

        ok = self.asr.start_listening(on_partial=_stream_partial, on_stream_error=_on_stream_error)
        if not ok:
            self.status_changed.emit("录音启动失败：模型未就绪")
            self.text_ready.emit("")
            self._recording = False
            return

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


def create_listen_thread(asr, on_text_ready=None, on_partial=None, on_status=None, on_stream_error=None):
    """
    统一创建语音识别监听线程并连接信号（MedVoiceApp / WebViewApp 共用）

    Args:
        asr: ASR 引擎实例
        on_text_ready: 最终识别结果回调（str）
        on_partial: 流式中间结果回调（str）
        on_status: 状态变化回调（str）
        on_stream_error: 流式识别恢复状态回调（str），用于通知 UI 层
            可能值：USER_MESSAGES["stream_error"] / USER_MESSAGES["circuit_open"] / USER_MESSAGES["recovered"]

    Returns:
        ListenThread 实例（未启动，需调用 .start()）
    """
    thread = ListenThread(asr)
    if on_text_ready:
        thread.text_ready.connect(on_text_ready)
    if on_partial:
        thread.partial_text.connect(on_partial)
    if on_status:
        thread.status_changed.connect(on_status)
    if on_stream_error:
        thread.status_changed.connect(on_stream_error)
    return thread


def stop_listen_thread(thread, timeout_ms=3000):
    """
    统一停止监听线程（MedVoiceApp / WebViewApp 共用）

    Args:
        thread: ListenThread 实例或 None
        timeout_ms: 等待线程结束的超时时间
    """
    if thread is None:
        return
    try:
        thread.stop()
        thread.wait(timeout_ms)
    except Exception as e:
        print(f"[Thread] 停止监听线程失败: {e}")
