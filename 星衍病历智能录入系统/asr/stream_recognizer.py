"""
ASR 流式识别 + 文件转写 + 文本纠错

Phase 6: 流式识别恢复策略
  - 指数退避（exponential backoff）：错误后按 2^n 秒递增等待，上限 60s
  - 熔断器（circuit-breaker）：连续超过 MAX_STREAM_ERRORS 次错误后停止，通过 on_stream_error 通知 UI
  - 用户友好错误信息：USER_MESSAGES dict 提供中文提示
"""
import logging
import os
import re
import tempfile
import time as _time
import wave

import numpy as np

logger = logging.getLogger(__name__)

# ─── 恢复策略常量 ───────────────────────────────────────
MAX_STREAM_ERRORS = 5            # 连续错误上限（熔断阈值）
BACKOFF_BASE_SECONDS = 2.0       # 退避基数（秒），退避时间 = min(base ** n, max)）
MAX_BACKOFF_SECONDS = 60         # 退避上限（秒）

# 用户友好错误信息（中文）
USER_MESSAGES = {
    "stream_error": "语音识别暂时中断，正在重新连接…",
    "circuit_open": "语音识别连续失败，请重启应用或检查麦克风设备",
    "recovered": "语音识别已恢复",
}


class StreamRecognizer:
    """流式识别 + 文件转写"""

    def __init__(self, engine):
        self.engine = engine
        # 流式错误回调（UI 层可传入 on_stream_error 获取恢复状态）
        self._on_stream_error = None

    def transcribe_file(self, engine, audio_path: str) -> str:
        """转写音频文件（供拖拽/导入使用）"""
        if not engine.is_ready():
            return ""
        if not os.path.exists(audio_path):
            return ""
        ext = os.path.splitext(audio_path)[1].lower()
        if ext == ".wav":
            return self._recognize_file(engine, audio_path)
        # 非 wav：尝试用 soundfile 读取并重采样为 16k wav
        try:
            import soundfile as sf
            data, sr = sf.read(audio_path, dtype="float32")
            if data.ndim > 1:
                data = data.mean(axis=1)
            if sr != engine.sample_rate:
                ratio = engine.sample_rate / float(sr)
                new_len = int(len(data) * ratio)
                idx = np.linspace(0, len(data) - 1, new_len)
                data = np.interp(idx, np.arange(len(data)), data)
            tmp_fd, tmp_path = tempfile.mkstemp(suffix=".wav")
            os.close(tmp_fd)
            pcm = (data * 32767).astype(np.int16)
            with wave.open(tmp_path, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(engine.sample_rate)
                wf.writeframes(pcm.tobytes())
            try:
                return self._recognize_file(engine, tmp_path)
            finally:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
        except Exception as e:
            logger.error(f"[ASR] 音频文件转写失败: {e}")
            return ""

    def _recognize_file(self, engine, wav_path: str) -> str:
        """用 Paraformer + VAD 识别音频文件（双层热词 + 纠错 + LM）"""
        if not engine.is_ready():
            return ""
        try:
            kwargs = {
                "input": wav_path,
                "language": "zh",
                "use_itn": True,
            }
            if engine._hotword_file and os.path.exists(engine._hotword_file):
                kwargs["hotword"] = engine._hotword_file
                hw_count = len(engine._current_hotwords.split()) if engine._current_hotwords else 0
                print(f"[ASR] 模型级热词文件: {engine._hotword_file} ({hw_count} 个)")

            result = engine.model.generate(**kwargs)
            print(f"[ASR] 模型返回: {type(result)}, 长度: {len(result) if result else 0}")

            if result and len(result) > 0:
                texts = []
                for item in result:
                    if isinstance(item, dict):
                        t = item.get("text", "") or item.get("sentence", "") or ""
                    elif isinstance(item, str):
                        t = item
                    else:
                        t = ""
                    t = t.strip()
                    if t:
                        texts.append(t)
                text = "".join(texts)
                text = re.sub(r'<\|[^|]*\|>', '', text)
                text = text.strip()

                if engine._postprocess_matcher:
                    before = text
                    result_dict = {"text": text}
                    engine._postprocess_matcher.apply_result(result_dict)
                    text = result_dict["text"]
                    if text != before:
                        print(f"[ASR] 文本纠错: {before} => {text}")

                text = self._apply_corrections(engine, text)
                print(f"[ASR] 识别结果({len(texts)}段): {text[:120]}")
                return text
            else:
                print("[ASR] 模型返回空结果")
            return ""
        except Exception as e:
            logger.error(f"[ASR] 识别失败: {e}")
            import traceback
            traceback.print_exc()
            return ""

    def _recognize_file_fast(self, engine, wav_path: str) -> str:
        """轻量识别（用于流式中间结果，速度优先）"""
        if not engine.is_ready():
            return ""
        try:
            kwargs = {"input": wav_path, "language": "zh", "use_itn": True}
            if engine._hotword_file and os.path.exists(engine._hotword_file):
                kwargs["hotword"] = engine._hotword_file
            result = engine.model.generate(**kwargs)
            if result and len(result) > 0:
                texts = []
                for item in result:
                    if isinstance(item, dict):
                        t = item.get("text", "") or item.get("sentence", "") or ""
                    elif isinstance(item, str):
                        t = item
                    else:
                        t = ""
                    t = t.strip()
                    if t:
                        texts.append(t)
                text = "".join(texts)
                text = re.sub(r'<\|[^|]*\|>', '', text).strip()
                return self._apply_corrections(engine, text)
            return ""
        except Exception:
            return ""

    def _apply_corrections(self, engine, text: str) -> str:
        """对识别文本应用纠错、混淆对、LM 重打分"""
        if not text:
            return text
        try:
            if engine._postprocess_matcher:
                before = text
                result_dict = {"text": text}
                engine._postprocess_matcher.apply_result(result_dict)
                text = result_dict["text"]
                if text != before:
                    print(f"[ASR] 文本纠错: {before} => {text}")
        except Exception as e:
            logger.error(f"[ASR] 文本级纠错失败: {e}")

        try:
            from corrector import post_process_medical
            text = post_process_medical(text)
        except Exception as e:
            logger.error(f"[ASR] 规则纠错失败: {e}")

        try:
            if engine._confusion_pairs:
                for wrong, right in engine._confusion_pairs.items():
                    if wrong in text:
                        text = text.replace(wrong, right)
        except Exception as e:
            logger.error(f"[ASR] 混淆对纠错失败: {e}")

        try:
            if engine._lm and engine._lm.is_ready:
                text = engine._lm.rescore(text, field_context=engine._field_context)
        except Exception as e:
            logger.error(f"[ASR] LM 重打分失败: {e}")

        return text

    def _stream_recognize_loop(self, engine):
        """流式识别监视线程（带指数退避恢复策略）"""
        first_interval = 1.0
        interval = 1.5
        energy_threshold = 0.02
        speech_frames_needed = 3
        last_count = 0
        is_first = True
        speech_streak = 0
        consecutive_errors = 0  # 连续错误计数（用于退避）
        recovery_notified = False  # 防止重复通知 circuit_open

        while engine.is_listening:
            # ── 指数退避：连续错误时按 2^n 递增等待 ──
            if consecutive_errors > 0:
                delay = min(
                    BACKOFF_BASE_SECONDS ** consecutive_errors,
                    MAX_BACKOFF_SECONDS,
                )
                logger.info(f"[ASR] 等待 {delay:.0f}s 后重试（第 {consecutive_errors} 次失败）")
                if self._on_stream_error:
                    # 首次失败通知 UI，之后只通知熔断开启
                    if consecutive_errors == 1:
                        self._on_stream_error(USER_MESSAGES["stream_error"])
                _time.sleep(delay)
                if not engine.is_listening:
                    break
                # 退避期间监听可能已停止
                consecutive_errors = 0
                recovery_notified = False

            wait = first_interval if is_first else interval
            _time.sleep(wait)
            if not engine.is_listening:
                break

            with engine._level_lock:
                current_level = engine._current_level
            if current_level < energy_threshold:
                speech_streak = 0
                if is_first:
                    continue
                with engine._frames_lock:
                    current_count = len(engine._recorded_frames)
                if current_count - last_count < int(interval * engine.sample_rate / 1600):
                    continue
            else:
                speech_streak += 1
                if is_first and speech_streak < speech_frames_needed:
                    continue

            with engine._stream_lock:
                if engine._stream_busy:
                    continue
                engine._stream_busy = True
            try:
                with engine._frames_lock:
                    current_count = len(engine._recorded_frames)
                    frames_snapshot = list(engine._recorded_frames)
                last_count = current_count
                audio = np.concatenate(frames_snapshot, axis=0)
                if audio.ndim == 2:
                    audio = audio.flatten()
                if not is_first and engine.enable_denoise:
                    audio = self._denoise(engine, audio)
                tmp_fd, tmp_path = tempfile.mkstemp(suffix=".wav")
                os.close(tmp_fd)
                try:
                    with wave.open(tmp_path, 'wb') as wf:
                        wf.setnchannels(1)
                        wf.setsampwidth(2)
                        wf.setframerate(engine.sample_rate)
                        wf.writeframes(audio.astype(np.int16).tobytes())
                    text = self._recognize_file_fast(engine, tmp_path)
                finally:
                    try:
                        os.remove(tmp_path)
                    except Exception as e:
                        logger.error(f"[ASR] 清理临时文件失败: {e}")

                if text and engine._on_partial:
                    engine._on_partial(text)
                is_first = False
                # 成功识别：重置错误计数，通知恢复
                if consecutive_errors > 0:
                    consecutive_errors = 0
                    if self._on_stream_error:
                        self._on_stream_error(USER_MESSAGES["recovered"])
            except Exception as e:
                logger.error(f"[ASR] 流式识别异常: {e}")
                is_first = False
                consecutive_errors += 1
                # 熔断：超过阈值停止
                if consecutive_errors >= MAX_STREAM_ERRORS and not recovery_notified:
                    recovery_notified = True
                    engine.is_listening = False
                    if self._on_stream_error:
                        self._on_stream_error(USER_MESSAGES["circuit_open"])
                    if engine._on_result:
                        engine._on_result("", final=True)
                    logger.error(f"[ASR] 流式识别熔断（{MAX_STREAM_ERRORS} 次连续失败），已停止")
            finally:
                with engine._stream_lock:
                    engine._stream_busy = False
