"""
ASR 语音识别引擎包（向后兼容层）

旧导入路径仍可用：
    from asr_engine import ASREngine, get_microphone_list, test_microphone

新模块结构：
    asr/
    ├── __init__.py          # 本文件：重新导出
    ├── engine.py            # ASREngine Facade（公开 API 不变）
    ├── model_loader.py      # 模型加载 + 热词 + LM
    ├── stream_recognizer.py  # 流式识别 + 文件转写
    └── audio_device.py       # 录音 + 降噪 + 设备管理
"""
from asr.engine import ASREngine, get_microphone_list, test_microphone

__all__ = ["ASREngine", "get_microphone_list", "test_microphone"]
