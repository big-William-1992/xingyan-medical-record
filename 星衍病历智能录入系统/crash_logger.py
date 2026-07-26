"""
崩溃日志记录器
将所有未捕获异常写入日志文件，便于排查问题
"""
import os
import sys
import json
import traceback
import datetime
import threading

LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")
MAX_LOG_SIZE = 5 * 1024 * 1024  # 5MB


class CrashLogger:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._log_file = None
        self._ensure_log_dir()
        self._open_log_file()
        # 全局异常钩子
        sys.excepthook = self._global_exception_handler
        # Qt 消息处理
        try:
            from PyQt5.QtCore import qInstallMessageHandler
            qInstallMessageHandler(self._qt_message_handler)
        except Exception:
            pass

    def _ensure_log_dir(self):
        if not os.path.exists(LOG_DIR):
            try:
                os.makedirs(LOG_DIR)
            except Exception:
                pass

    def _open_log_file(self):
        try:
            log_path = os.path.join(LOG_DIR, "crash.log")
            # 检查文件大小，超过限制则轮转
            if os.path.exists(log_path) and os.path.getsize(log_path) > MAX_LOG_SIZE:
                backup = os.path.join(LOG_DIR, "crash.log.1")
                try:
                    if os.path.exists(backup):
                        os.remove(backup)
                    os.rename(log_path, backup)
                except Exception:
                    pass
            self._log_file = open(log_path, 'a', encoding='utf-8')
        except Exception:
            self._log_file = None

    def _global_exception_handler(self, exc_type, exc_value, exc_tb):
        """全局未捕获异常处理器"""
        self.log_exception(exc_type, exc_value, exc_tb, context="全局未捕获异常")

        # 尝试显示错误对话框
        try:
            from PyQt5.QtWidgets import QApplication, QMessageBox
            if QApplication.instance():
                msg = str(exc_value)
                if len(msg) > 200:
                    msg = msg[:200] + "..."
                QMessageBox.critical(
                    None, "程序异常",
                    f"程序遇到未预期的错误：\n{msg}\n\n"
                    f"详细日志已保存到：\n{os.path.join(LOG_DIR, 'crash.log')}"
                )
        except Exception:
            pass

    def _qt_message_handler(self, msg_type, context, message):
        """Qt 消息处理器"""
        self.log("Qt", f"[{context.category}] {message}")
        # 让 Qt 默认处理也执行
        try:
            from PyQt5.QtCore import QtMsgType
            if msg_type in (QtMsgType.QtCriticalMsg, QtMsgType.QtFatalMsg):
                print(f"[Qt {context.category}] {message}", file=sys.stderr)
        except Exception:
            pass

    def log(self, source, message):
        """记录普通日志"""
        if not self._log_file:
            return
        try:
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self._log_file.write(f"[{timestamp}] [{source}] {message}\n")
            self._log_file.flush()
        except Exception:
            pass

    def log_exception(self, exc_type, exc_value, exc_tb, context="异常"):
        """记录异常详情"""
        if not self._log_file:
            return
        try:
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            tb_str = ''.join(traceback.format_tb(exc_tb))
            self._log_file.write(f"\n{'='*60}\n")
            self._log_file.write(f"[{timestamp}] [{context}] {exc_type.__name__}: {exc_value}\n")
            self._log_file.write(f"{tb_str}\n")
            self._log_file.write(f"{'='*60}\n\n")
            self._log_file.flush()
        except Exception:
            pass

    def log_event(self, event_name, data=None):
        """记录业务事件（如录音开始、识别完成等）"""
        if not self._log_file:
            return
        try:
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            data_str = ""
            if data:
                data_str = f" | {json.dumps(data, ensure_ascii=False)}"
            self._log_file.write(f"[{timestamp}] [EVENT] {event_name}{data_str}\n")
            self._log_file.flush()
        except Exception:
            pass

    def get_log_path(self):
        """获取日志文件路径"""
        return os.path.join(LOG_DIR, "crash.log")

    def get_recent_logs(self, lines=100):
        """读取最近的日志"""
        log_path = os.path.join(LOG_DIR, "crash.log")
        if not os.path.exists(log_path):
            return []
        try:
            with open(log_path, 'r', encoding='utf-8') as f:
                all_lines = f.readlines()
            return all_lines[-lines:] if len(all_lines) > lines else all_lines
        except Exception:
            return []
