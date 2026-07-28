"""
语音识别引擎 - 基于 FunASR Paraformer + VAD + 热词
- Paraformer: 中文最优离线模型，原生支持热词，准确率高于 SenseVoice
- FSMN-VAD: 语音活动检测，自动过滤静音段
- CT-Punc: 标点恢复，输出带标点的完整句子
- 科室热词: 根据当前科室加载专业词汇，提升识别率
"""
import os
import queue
import re
import threading
import tempfile
import wave
import numpy as np

try:
    from funasr import AutoModel
    HAS_FUNASR = True
except ImportError:
    HAS_FUNASR = False

try:
    from funasr.utils.postprocess_hotwords import build_postprocess_hotword_matcher
    HAS_POSTPROCESS = True
except ImportError:
    HAS_POSTPROCESS = False

from corrector import post_process_medical


class ASREngine:
    def __init__(self, model_path=None, sample_rate=16000, recording_duration=30):
        self.sample_rate = sample_rate
        self.model_path = model_path
        self.recording_duration = recording_duration
        self.model = None
        self.is_listening = False
        self._recorded_frames = []
        self._result_queue = queue.Queue()
        self._record_thread = None
        self._recording_started = threading.Event()
        self._current_hotwords = ""
        self.input_device = None  # 录音设备 index（None = 系统默认）
        self.enable_denoise = True  # 录音降噪预处理开关

        # 热词文件路径（和 asr_engine.py 同目录）
        base_dir = os.path.dirname(os.path.abspath(__file__))
        self._hotwords_path = os.path.join(base_dir, "hotwords.txt")
        self._postprocess_path = os.path.join(base_dir, "postprocess_hotwords.txt")
        # 用户自适应热词（从历史病历提取的高频词，每行一个）
        self._user_hotwords_path = os.path.join(base_dir, "user_hotwords.txt")
        self._user_hotwords = []
        self._hotword_sections = {}  # {section_name: [words]}
        self._hotword_file = ""  # 当前科室热词临时文件路径
        self._postprocess_matcher = None  # 文本级纠错 matcher
        self._load_hotwords()
        self._load_user_hotwords()
        self._build_postprocess_matcher()

        # 加载 Paraformer + VAD + 标点模型
        self._load_model()

    # ─── 热词管理 ─────────────────────────────────────────

    def _load_hotwords(self):
        """加载 hotwords.txt，按 # 注释分隔不同分区"""
        self._hotword_sections = {}
        current_section = "通用"

        try:
            with open(self._hotwords_path, "r", encoding="utf-8") as f:
                for line in f:
                    raw = line.rstrip("\n")
                    stripped = raw.strip()
                    # 空行跳过
                    if not stripped:
                        continue
                    # # 开头视为分区标题
                    if stripped.startswith("#"):
                        section_name = stripped.lstrip("#").strip()
                        if section_name:
                            current_section = section_name
                            if current_section not in self._hotword_sections:
                                self._hotword_sections[current_section] = []
                        continue
                    # 普通热词行
                    self._hotword_sections.setdefault(current_section, []).append(stripped)
        except Exception as e:
            print(f"[ASR] 加载热词文件失败: {e}")

        for section, words in self._hotword_sections.items():
            print(f"[ASR] 热词 [{section}]: {len(words)} 个")

    def _load_user_hotwords(self):
        """加载用户自适应热词（user_hotwords.txt，每行一个）"""
        self._user_hotwords = []
        if not os.path.exists(self._user_hotwords_path):
            return
        try:
            with open(self._user_hotwords_path, "r", encoding="utf-8") as f:
                for line in f:
                    w = line.strip()
                    if w and not w.startswith("#"):
                        self._user_hotwords.append(w)
            print(f"[ASR] 用户自适应热词: {len(self._user_hotwords)} 个")
        except Exception as e:
            print(f"[ASR] 加载用户热词失败: {e}")

    def update_user_hotwords(self, words, max_words=300):
        """写入/合并用户自适应热词并重新加载。words: 词语列表。"""
        merged = list(dict.fromkeys(
            [w.strip() for w in (self._user_hotwords + list(words)) if w and w.strip()]
        ))
        # 保留最新的 max_words 个（新词在后，优先保留）
        if len(merged) > max_words:
            merged = merged[-max_words:]
        try:
            with open(self._user_hotwords_path, "w", encoding="utf-8") as f:
                f.write("# 用户自适应热词（从历史病历自动提取，可手动编辑）\n")
                for w in merged:
                    f.write(w + "\n")
            self._user_hotwords = merged
            print(f"[ASR] 用户热词已更新: {len(merged)} 个")
            return True
        except Exception as e:
            print(f"[ASR] 写入用户热词失败: {e}")
            return False

    def set_hotwords(self, department=""):
        """根据科室设置热词（通用 + 科室专用），生成热词文件供模型使用"""
        # 科室名 → 热词分区名映射
        dept_map = {
            "影像科": "影像科专用",
            "内科": "内科专用",
            "外科": "外科专用",
            "妇产科": "妇产科专用",
            "儿科": "儿科专用",
        }

        # 通用热词
        words = list(self._hotword_sections.get("通用", []))

        # 科室热词
        section = dept_map.get(department, "")
        if section and section in self._hotword_sections:
            words.extend(self._hotword_sections[section])

        # 中医通用热词（所有科室均可加载）
        if "中医通用" in self._hotword_sections:
            words.extend(self._hotword_sections["中医通用"])

        # 用户自适应热词（从历史病历学到的高频词）
        if self._user_hotwords:
            words.extend(self._user_hotwords)

        # 去重（保序）
        words = list(dict.fromkeys(words))

        self._current_hotwords = " ".join(words)

        # 生成热词文件（Paraformer 模型级热词需要 .txt 文件路径）
        self._write_hotword_file(words)
        print(f"[ASR] 热词已切换到 [{department}]：{len(words)} 个热词，文件: {self._hotword_file}")

    def _write_hotword_file(self, words):
        """将热词列表写入临时 .txt 文件（每行一个热词）"""
        try:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            self._hotword_file = os.path.join(base_dir, ".hotwords_current.txt")
            with open(self._hotword_file, "w", encoding="utf-8") as f:
                for w in words:
                    f.write(w + "\n")
        except Exception as e:
            print(f"[ASR] 写入热词文件失败: {e}")
            self._hotword_file = ""

    def _build_postprocess_matcher(self):
        """构建文本级纠错 matcher（识别后纠正误识别词）"""
        if not HAS_POSTPROCESS:
            print("[ASR] postprocess_hotwords 模块不可用，跳过文本级纠错")
            return
        if not os.path.exists(self._postprocess_path):
            print(f"[ASR] 纠错文件不存在: {self._postprocess_path}")
            return
        try:
            self._postprocess_matcher = build_postprocess_hotword_matcher(
                postprocess_hotwords=None,
                postprocess_hotword_file=self._postprocess_path,
                postprocess_hotword_threshold=0.80,
                enable_fuzzy=True,
            )
            print(f"[ASR] 文本级纠错 matcher 构建成功")
        except Exception as e:
            print(f"[ASR] 构建纠错 matcher 失败: {e}")
            self._postprocess_matcher = None

    # ─── 模型加载 ─────────────────────────────────────────

    def _load_model(self):
        """加载 Paraformer + VAD + 标点模型"""
        if not HAS_FUNASR:
            print("[ASR] FunASR 未安装")
            return
        try:
            print("[ASR] 正在加载 Paraformer + VAD + 标点模型...")
            self.model = AutoModel(
                model="paraformer-zh",
                vad_model="fsmn-vad",
                punc_model="ct-punc",
                device="cpu",
                disable_update=True,
                disable_log=True,
            )
            print("[ASR] 模型加载成功")
        except Exception as e:
            print(f"[ASR] 模型加载失败: {e}")
            import traceback
            traceback.print_exc()

    def is_ready(self):
        return self.model is not None

    # ─── 录音 ─────────────────────────────────────────────

    def _record_loop(self, status_callback=None):
        """录音线程（流式录音，支持中途停止）"""
        try:
            import sounddevice as sd
            self._recorded_frames = []

            def audio_callback(indata, frame_count, time_info, status):
                if status:
                    print(f"[ASR] 录音状态: {status}")
                self._recorded_frames.append(indata.copy())

            stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=1,
                dtype='int16',
                callback=audio_callback,
                device=self.input_device,
            )
            stream.start()
            self._recording_started.set()  # 通知主线程：录音已开始

            while self.is_listening:
                sd.sleep(100)

            stream.stop()
            stream.close()
            print(f"[ASR] 录音结束，共 {len(self._recorded_frames)} 帧")
        except Exception as e:
            self._recording_started.set()  # 确保主线程不会死等
            if self.is_listening and status_callback:
                status_callback(f"录音错误: {e}")
            print(f"[ASR] 录音异常: {e}")

    # ─── 识别 ─────────────────────────────────────────────

    def _denoise(self, audio_int16):
        """轻量降噪预处理（纯 numpy，无额外依赖）：
        1) 去直流偏置；2) 一阶高通滤波去低频嗡嗡声；3) 温和噪声门。
        输入/输出均为 int16 一维数组。降噪保守，避免损伤语音。
        """
        try:
            if audio_int16 is None or len(audio_int16) == 0:
                return audio_int16
            x = audio_int16.astype(np.float32)

            # 1) 去直流偏置
            x -= np.mean(x)

            # 2) 一阶高通滤波：y[n] = a*(y[n-1] + x[n] - x[n-1])
            #    a≈0.97 对应约 80Hz 截止（16k 采样），去除低频背景嗡鸣
            a = 0.97
            y = np.empty_like(x)
            y[0] = x[0]
            # 向量化 IIR 不易；样本量为数十万级，循环可接受但慢，
            # 用差分近似高通：x[n]-x[n-1] 再叠加衰减，避免逐样本 Python 循环
            diff = np.empty_like(x)
            diff[0] = 0.0
            diff[1:] = x[1:] - x[:-1]
            # 用指数加权累积近似 IIR 反馈
            y = a * (diff + x * (1 - a))

            # 3) 温和噪声门：估计噪声底噪（最小 10% 能量帧），
            #    低于阈值的样本按比例衰减而非置零，避免断音
            frame = 320  # 20ms @16k
            n_frames = len(y) // frame
            if n_frames >= 5:
                trimmed = y[:n_frames * frame].reshape(n_frames, frame)
                energies = np.sqrt(np.mean(trimmed ** 2, axis=1) + 1e-9)
                noise_floor = np.percentile(energies, 10)
                gate_thresh = noise_floor * 1.5
                gains = np.ones(n_frames, dtype=np.float32)
                weak = energies < gate_thresh
                gains[weak] = 0.5  # 弱帧衰减一半而非静音
                gain_full = np.repeat(gains, frame)
                y[:len(gain_full)] *= gain_full

            # 防止溢出并转回 int16
            peak = np.max(np.abs(y)) if len(y) else 0
            if peak > 32767:
                y = y * (32767.0 / peak)
            return np.clip(y, -32768, 32767).astype(np.int16)
        except Exception as e:
            print(f"[ASR] 降噪处理失败，使用原始音频: {e}")
            return audio_int16

    def _recognize_file(self, wav_path):
        """用 Paraformer + VAD 识别音频文件（双层热词：模型级 + 文本级）"""
        if not self.is_ready():
            return ""

        try:
            kwargs = {
                "input": wav_path,
                "language": "zh",
                "use_itn": True,
            }

            # 模型级热词：传 .txt 文件路径（解码时增强识别）
            if self._hotword_file and os.path.exists(self._hotword_file):
                kwargs["hotword"] = self._hotword_file
                hw_count = len(self._current_hotwords.split()) if self._current_hotwords else 0
                print(f"[ASR] 模型级热词文件: {self._hotword_file} ({hw_count} 个)")

            result = self.model.generate(**kwargs)

            print(f"[ASR] 模型返回: {type(result)}, 长度: {len(result) if result else 0}")
            if result and len(result) > 0:
                texts = []
                for item in result:
                    if isinstance(item, dict):
                        t = item.get("text", "") or item.get("sentence", "") or ""
                        t = t.strip()
                    elif isinstance(item, str):
                        t = item.strip()
                    else:
                        t = ""
                    if t:
                        texts.append(t)
                text = "".join(texts)
                # 安全清除（Paraformer 一般不会有 SenseVoice 的标记）
                text = re.sub(r'<\|[^|]*\|>', '', text)
                text = text.strip()

                # 文本级纠错：用 postprocess matcher 纠正误识别词
                if self._postprocess_matcher:
                    before = text
                    result_dict = {"text": text}
                    self._postprocess_matcher.apply_result(result_dict)
                    text = result_dict["text"]
                    if text != before:
                        print(f"[ASR] 文本纠错: {before} => {text}")

                text = post_process_medical(text)
                print(f"[ASR] 识别结果({len(texts)}段): {text[:120]}")
                return text
            else:
                print("[ASR] 模型返回空结果")
            return ""

        except Exception as e:
            print(f"[ASR] 识别失败: {e}")
            import traceback
            traceback.print_exc()
            return ""

    # ─── 生命周期 ─────────────────────────────────────────

    def start_listening(self, on_result=None, on_partial=None):
        """开始录音"""
        if not self.is_ready():
            return False
        self.is_listening = True
        self._recorded_frames = []
        self._recording_started.clear()
        self._record_thread = threading.Thread(target=self._record_loop, daemon=True)
        self._record_thread.start()
        print("[ASR] 开始录音")
        return True

    def stop_listening(self):
        """停止录音，返回识别文本"""
        self.is_listening = False
        if self._record_thread:
            self._recording_started.wait(timeout=3)
            if self._record_thread.is_alive():
                self._record_thread.join(timeout=5)

        if not self._recorded_frames:
            print("[ASR] 没有录音数据")
            return ""

        tmp_path = tempfile.mktemp(suffix=".wav")
        try:
            audio_data = np.concatenate(self._recorded_frames, axis=0)
            if audio_data.ndim == 2 and audio_data.shape[1] == 1:
                audio_data = audio_data.flatten()
            elif audio_data.ndim == 2 and audio_data.shape[0] == 1:
                audio_data = audio_data[0]

            max_val = np.max(np.abs(audio_data)) if len(audio_data) > 0 else 0
            print(f"[ASR] 录音数据：{len(audio_data)} 采样点，最大振幅：{max_val}")

            if max_val < 100:
                print("[ASR] 警告：录音振幅太小，可能没有采集到声音")

            # 降噪预处理（高通滤波 + 噪声门），提升嘈杂环境识别率
            if self.enable_denoise:
                audio_data = self._denoise(audio_data)

            with wave.open(tmp_path, 'wb') as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(self.sample_rate)
                wf.writeframes(audio_data.tobytes())

            text = self._recognize_file(tmp_path)
            print(f"[ASR] 识别完成，返回文本长度：{len(text)}")
            return text
        except Exception as e:
            print(f"[ASR] 识别失败: {e}")
            import traceback
            traceback.print_exc()
            return ""
        finally:
            try:
                os.remove(tmp_path)
            except Exception:
                pass

    def process_audio_file(self, wav_path):
        """处理已有的音频文件"""
        return self._recognize_file(wav_path)

    def set_input_device(self, device_index):
        """设置录音输入设备 index（None 为系统默认）"""
        self.input_device = device_index
        print(f"[ASR] 录音设备已设为: {device_index}")


def get_microphone_list():
    try:
        import sounddevice as sd
        devices = sd.query_devices()
        return [
            {"index": i, "name": d["name"], "channels": d["max_input_channels"]}
            for i, d in enumerate(devices) if d["max_input_channels"] > 0
        ]
    except Exception as e:
        print(f"[ASR] 获取麦克风列表失败: {e}")
        return []


def test_microphone():
    try:
        devices = get_microphone_list()
        if not devices:
            print("[ASR] 未检测到麦克风")
            return False
        print(f"[ASR] 检测到 {len(devices)} 个麦克风")
        return True
    except Exception as e:
        print(f"[ASR] 麦克风测试失败: {e}")
        return False
