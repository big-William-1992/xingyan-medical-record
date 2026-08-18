"""
语音识别引擎 - 向后兼容层（已迁移至 asr/ 包）

本文件保留以兼容旧导入路径：
    from asr_engine import ASREngine

实际实现位于：
    asr/
    ├── engine.py            # ASREngine Facade
    ├── model_loader.py      # 模型加载 + 热词管理
    ├── stream_recognizer.py # 流式识别 + 文件转写
    └── audio_device.py       # 录音 + 降噪 + 设备管理
"""
from asr import ASREngine, get_microphone_list, test_microphone

__all__ = ["ASREngine", "get_microphone_list", "test_microphone"]
