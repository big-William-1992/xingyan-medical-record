"""
服务端单例惰性初始化（模块级变量 + 双检锁）
- 所有 get_* 函数线程安全，可安全 import
- 子模块通过 from server.singletons import get_asr 等获取实例
"""
import threading
from typing import Optional

# 模块级变量（惰性初始化）
_asr = None
_kg = None
_qa = None
_template_engine = None
_corrector = None
_feedback = None
_db = None
_classifier = None

# 全局锁（保护模块级单例初始化）
_singleton_lock = threading.Lock()


def get_asr():
    global _asr
    if _asr is None:
        with _singleton_lock:
            if _asr is None:
                import os
                if os.environ.get("XINGYAN_SKIP_ASR") == "1":
                    return None
                from asr_engine import ASREngine
                from pathlib import Path
                _asr = ASREngine(model_path=str(Path(__file__).resolve().parent.parent / "model"))
    return _asr


def get_kg():
    return get_qa().kg


def get_qa():
    global _qa, _kg
    if _qa is None:
        with _singleton_lock:
            if _qa is None:
                from knowledge_qa import KnowledgeQA
                _qa = KnowledgeQA()
                _kg = _qa.kg
    return _qa


def get_template_engine():
    global _template_engine
    if _template_engine is None:
        with _singleton_lock:
            if _template_engine is None:
                from template_engine import TemplateEngine
                _template_engine = TemplateEngine()
    return _template_engine


def get_corrector():
    global _corrector
    if _corrector is None:
        with _singleton_lock:
            if _corrector is None:
                from corrector import Corrector
                from rule_engine import RuleEngine
                _corrector = Corrector(rule_engine=RuleEngine())
    return _corrector


def get_feedback():
    global _feedback
    if _feedback is None:
        with _singleton_lock:
            if _feedback is None:
                from correction_feedback import CorrectionFeedback
                _feedback = CorrectionFeedback()
    return _feedback


def get_db():
    global _db
    if _db is None:
        with _singleton_lock:
            if _db is None:
                from database import Database
                _db = Database()
    return _db


def get_classifier():
    global _classifier
    if _classifier is None:
        with _singleton_lock:
            if _classifier is None:
                from medical_classifier import MedicalClassifier
                _classifier = MedicalClassifier()
    return _classifier
