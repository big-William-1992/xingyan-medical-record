"""
ASR 音频设备管理 + 录音 + 降噪
"""
import logging
import os
import tempfile
import wave

import numpy as np

logger = logging.getLogger(__name__)


class AudioDevice:
    """管理录音设备、录音线程、音频处理"""

    def __init__(self, engine):
        self.engine = engine
        self._record_thread = None
        self._stream_thread = None
        self._recording_started = None

    def start_listening(self, on_result=None, on_partial=None, on_stream_error=None):
        """开始录音（支持流式回调 + 恢复状态回调）"""
        import threading
        import queue

        if not self.engine.is_ready():
            return False

        if not self.engine._thread_semaphore.acquire(blocking=False):
            logger.warning("[ASR] 已有录音任务在进行中")
            return False

        try:
            self.engine.is_listening = True
            self.engine._recorded_frames = []
            self.engine._recording_started = threading.Event()
            with self.engine._stream_lock:
                self.engine._stream_busy = False
                self.engine._stream_errors = 0
            self.engine._on_partial = on_partial
            self.engine._on_result = on_result
            # 透传恢复状态回调给 stream_recognizer
            if hasattr(self.engine._stream_recognizer, '_on_stream_error'):
                self.engine._stream_recognizer._on_stream_error = on_stream_error

            self._record_thread = threading.Thread(
                target=self._record_loop, daemon=True
            )
            self._record_thread.start()

            self._stream_thread = threading.Thread(
                target=self.engine._stream_recognizer._stream_recognize_loop,
                args=(self.engine,),
                daemon=True,
            )
            self._stream_thread.start()

            print("[ASR] 开始录音（流式模式）")
            return True
        except Exception:
            self.engine._thread_semaphore.release()
            raise

    def stop_listening(self):
        """停止录音，返回最终识别文本"""
        self.engine.is_listening = False
        if self._record_thread:
            self.engine._recording_started.wait(timeout=3)
            if self._record_thread.is_alive():
                self._record_thread.join(timeout=5)
        if self._stream_thread and self._stream_thread.is_alive():
            self._stream_thread.join(timeout=3)
            if self._stream_thread.is_alive():
                logger.warning("[ASR] 流式识别线程未能在 3 秒内退出")
            self._stream_thread = None
        self.engine._thread_semaphore.release()

        with self.engine._frames_lock:
            has_frames = bool(self.engine._recorded_frames)
        if not has_frames:
            logger.warning("[ASR] 没有录音数据")
            return ""

        tmp_fd, tmp_path = tempfile.mkstemp(suffix=".wav")
        os.close(tmp_fd)
        try:
            with self.engine._frames_lock:
                audio_data = np.concatenate(self.engine._recorded_frames, axis=0)
            if audio_data.ndim == 2 and audio_data.shape[1] == 1:
                audio_data = audio_data.flatten()
            elif audio_data.ndim == 2 and audio_data.shape[0] == 1:
                audio_data = audio_data[0]

            max_val = float(np.max(np.abs(audio_data))) if len(audio_data) > 0 else 0
            print(f"[ASR] 录音数据：{len(audio_data)} 采样点，最大振幅：{max_val}")

            if max_val < 100:
                logger.warning("[ASR] 警告：录音振幅太小")

            if self.engine.enable_denoise:
                audio_data = self._denoise(self.engine, audio_data)

            with wave.open(tmp_path, 'wb') as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(self.engine.sample_rate)
                wf.writeframes(audio_data.astype(np.int16).tobytes())

            # 保留录音文件
            try:
                rec_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "recordings")
                os.makedirs(rec_dir, exist_ok=True)
                import datetime
                stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                keep_path = os.path.join(rec_dir, f"rec_{stamp}.wav")
                with wave.open(keep_path, 'wb') as wf2:
                    wf2.setnchannels(1)
                    wf2.setsampwidth(2)
                    wf2.setframerate(self.engine.sample_rate)
                    wf2.writeframes(audio_data.astype(np.int16).tobytes())
                self.engine.last_audio_path = keep_path
                self._cleanup_old_recordings(rec_dir)
            except Exception as e:
                logger.error(f"[ASR] 保留录音文件失败: {e}")

            text = self.engine._recognize_file(tmp_path)
            print(f"[ASR] 识别完成，返回文本长度：{len(text)}")
            return text
        except Exception as e:
            logger.error(f"[ASR] 识别失败: {e}")
            import traceback
            traceback.print_exc()
            return ""
        finally:
            try:
                os.remove(tmp_path)
            except Exception as e:
                logger.error(f"[ASR] 清理临时文件失败: {e}")

    def get_audio_level(self):
        """返回当前录音音量电平（0~1）"""
        with self.engine._level_lock:
            return self.engine._current_level

    def set_input_device(self, device_index):
        """设置录音输入设备"""
        self.engine.input_device = device_index
        print(f"[ASR] 录音设备已设为: {device_index}")

    def _record_loop(self, status_callback=None):
        """录音线程（流式录音，支持中途停止）"""
        try:
            import sounddevice as sd
            with self.engine._frames_lock:
                self.engine._recorded_frames = []

            def audio_callback(indata, frame_count, time_info, status):
                if status:
                    print(f"[ASR] 录音状态: {status}")
                with self.engine._frames_lock:
                    self.engine._recorded_frames.append(indata.copy())
                try:
                    arr = np.asarray(indata, dtype=np.float32)
                    rms = float(np.sqrt(np.mean(arr ** 2))) if arr.size else 0.0
                    with self.engine._level_lock:
                        self.engine._current_level = min(1.0, rms / 3000.0)
                except Exception:
                    with self.engine._level_lock:
                        self.engine._current_level = 0.0

            stream = sd.InputStream(
                samplerate=self.engine.sample_rate,
                channels=1,
                dtype='int16',
                callback=audio_callback,
                device=self.engine.input_device,
            )
            try:
                stream.start()
            except Exception as start_err:
                stream.close()
                raise RuntimeError(f"录音设备启动失败: {start_err}") from start_err
            self.engine._recording_started.set()

            while self.engine.is_listening:
                sd.sleep(100)

            stream.stop()
            stream.close()
            with self.engine._frames_lock:
                frame_count = len(self.engine._recorded_frames)
            print(f"[ASR] 录音结束，共 {frame_count} 帧")
        except Exception as e:
            self.engine._recording_started.set()
            if self.engine.is_listening and status_callback:
                status_callback(f"录音错误: {e}")
            logger.error(f"[ASR] 录音异常: {e}")

    def _denoise(self, engine, audio_int16):
        """轻量降噪预处理"""
        try:
            if audio_int16 is None or len(audio_int16) == 0:
                return audio_int16
            x = audio_int16.astype(np.float32)
            x -= np.mean(x)
            a = 0.97
            diff = np.empty_like(x)
            diff[0] = 0.0
            diff[1:] = x[1:] - x[:-1]
            y = a * (diff + x * (1 - a))
            frame = 320
            n_frames = len(y) // frame
            if n_frames >= 5:
                trimmed = y[:n_frames * frame].reshape(n_frames, frame)
                energies = np.sqrt(np.mean(trimmed ** 2, axis=1) + 1e-9)
                noise_floor = np.percentile(energies, 10)
                gate_thresh = noise_floor * 1.5
                gains = np.ones(n_frames, dtype=np.float32)
                weak = energies < gate_thresh
                gains[weak] = 0.5
                gain_full = np.repeat(gains, frame)
                y[:len(gain_full)] *= gain_full
            peak = float(np.max(np.abs(y))) if len(y) > 0 else 0
            if peak > 32767:
                y = y * (32767.0 / peak)
            return np.clip(y, -32768, 32767).astype(np.int16)
        except Exception as e:
            logger.warning(f"[ASR] 降噪处理失败: {e}")
            return audio_int16

    @staticmethod
    def _cleanup_old_recordings(rec_dir: str, keep: int = 30):
        """只保留最近 keep 份录音"""
        try:
            files = sorted(
                (os.path.join(rec_dir, f) for f in os.listdir(rec_dir) if f.endswith(".wav")),
                key=os.path.getmtime
            )
            for old in files[:-keep]:
                os.remove(old)
        except Exception as e:
            logger.error(f"[ASR] 清理旧录音失败: {e}")


# 模块级便捷函数（向后兼容）
def get_microphone_list():
    """获取麦克风列表"""
    try:
        import sounddevice as sd
        devices = sd.query_devices()
        return [
            {"index": i, "name": d["name"], "channels": d["max_input_channels"]}
            for i, d in enumerate(devices) if d["max_input_channels"] > 0
        ]
    except Exception as e:
        logger.error(f"[ASR] 获取麦克风列表失败: {e}")
        return []


def test_microphone():
    """麦克风测试"""
    devices = get_microphone_list()
    if not devices:
        print("[ASR] 未检测到麦克风")
        return False
    print(f"[ASR] 检测到 {len(devices)} 个麦克风")
    return True
