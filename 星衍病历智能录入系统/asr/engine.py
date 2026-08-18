"""
ASR 引擎主入口（Facade 模式）
- 保持 ASREngine 公开 API 不变
- 内部委托给 model_loader / stream_recognizer / audio_device 子模块
"""
import logging
import os
import re
import threading
import numpy as np

from asr.model_loader import ModelLoader
from asr.stream_recognizer import StreamRecognizer
from asr.audio_device import AudioDevice

logger = logging.getLogger(__name__)


class ASREngine:
    """语音识别引擎（Facade，委托给子模块）"""

    _shared_instance = None
    _init_lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if cls._shared_instance is not None:
            return cls._shared_instance
        with cls._init_lock:
            if cls._shared_instance is None:
                cls._shared_instance = super().__new__(cls)
                cls._shared_instance._initialized = False
            return cls._shared_instance

    def __init__(self, model_path=None, sample_rate=16000, recording_duration=30):
        if getattr(self, "_initialized", False):
            return

        self.sample_rate = sample_rate
        self.model_path = model_path
        self.recording_duration = recording_duration
        self.enable_denoise = True

        # 热词相关
        base_dir = os.path.dirname(os.path.abspath(__file__))
        self._hotwords_path = os.path.join(base_dir, "hotwords.txt")
        self._postprocess_path = os.path.join(base_dir, "postprocess_hotwords.txt")
        self._user_hotwords_path = os.path.join(base_dir, "user_hotwords.txt")
        self._kg_hotwords_path = os.path.join(base_dir, "kg_hotwords.txt")
        self._current_hotwords = ""
        self._hotword_file = ""
        self._hotword_sections = {}
        self._user_hotwords = []
        self._kg_hotwords = {}
        self._postprocess_matcher = None
        self._confusion_pairs = {}
        self._field_context = ""
        self._prompt_pack = None
        self._prompt_terms = []
        self._prompt_pairs = []

        # 子模块（共享 self 引用）
        self._model_loader = ModelLoader(self)
        self._stream_recognizer = StreamRecognizer(self)
        self._audio_device = AudioDevice(self)

        # 初始化子模块
        self._model_loader.initialize()
        self._initialized = True

    # ─── 公共 API ─────────────────────────────────────────

    def is_ready(self):
        ml = getattr(self, '_model_loader', None)
        return ml is not None and ml.model is not None

    # ─── 热词管理（委托 model_loader）─────────────────────

    def _load_hotwords(self):
        self._model_loader._load_hotwords()

    def _load_user_hotwords(self):
        self._model_loader._load_user_hotwords()

    def _load_kg_hotwords(self):
        self._model_loader._load_kg_hotwords()

    def update_user_hotwords(self, words, max_words=300):
        return self._model_loader.update_user_hotwords(words, max_words)

    def set_hotwords(self, department=""):
        return self._model_loader.set_hotwords(department)

    def _write_hotword_file(self, words):
        return self._model_loader._write_hotword_file(words)

    def _select_kg_hotwords(self, department, budget):
        return self._model_loader._select_kg_hotwords(department, budget)

    def _build_postprocess_matcher(self):
        self._model_loader._build_postprocess_matcher()

    def _load_language_model(self):
        self._model_loader._load_language_model()

    def _load_confusion_pairs(self):
        self._model_loader._load_confusion_pairs()

    @staticmethod
    def extract_confusion_pairs(min_count=3):
        return ModelLoader.extract_confusion_pairs(min_count)

    def boost_hotwords_for_template(self, template_content):
        return self._model_loader.boost_hotwords_for_template(template_content)

    def set_field_context(self, field_name):
        return self._model_loader.set_field_context(field_name)

    def set_prompt_pack(self, prompt_pack):
        return self._model_loader.set_prompt_pack(prompt_pack)

    def build_prompt_from_topk(self, topk):
        return self._model_loader.build_prompt_from_topk(topk)

    def apply_prompt_pack(self):
        return self._model_loader.apply_prompt_pack()

    # ─── 录音（委托 audio_device）─────────────────────────

    def start_listening(self, on_result=None, on_partial=None, on_stream_error=None):
        return self._audio_device.start_listening(on_result, on_partial, on_stream_error)

    def stop_listening(self):
        return self._audio_device.stop_listening()

    def get_audio_level(self):
        return self._audio_device.get_audio_level()

    def set_input_device(self, device_index):
        return self._audio_device.set_input_device(device_index)

    def process_audio_file(self, wav_path):
        return self._recognize_file(wav_path)

    # ─── 识别（保留在 engine 层，需访问 model + hotword）──

    def transcribe_file(self, audio_path):
        """转写音频文件（供拖拽/导入使用）"""
        return self._stream_recognizer.transcribe_file(self, audio_path)

    def _recognize_file(self, wav_path):
        """用 Paraformer + VAD 识别音频文件"""
        return self._stream_recognizer._recognize_file(self, wav_path)

    def _recognize_file_fast(self, wav_path):
        """轻量识别（用于流式中间结果）"""
        return self._stream_recognizer._recognize_file_fast(self, wav_path)

    def _apply_final_text_corrections(self, text):
        """对识别文本应用纠错"""
        return self._stream_recognizer._apply_final_text_corrections(self, text)

    def _denoise(self, audio_int16):
        """降噪预处理"""
        return self._audio_device._denoise(self, audio_int16)


# 模块级便捷函数（向后兼容）
def get_microphone_list():
    from asr.audio_device import get_microphone_list
    return get_microphone_list()


def test_microphone():
    from asr.audio_device import test_microphone
    return test_microphone()
