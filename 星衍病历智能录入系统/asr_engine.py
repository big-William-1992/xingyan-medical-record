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
from medical_lm import MedicalLM


class ASREngine:
    def __init__(self, model_path=None, sample_rate=16000, recording_duration=30):
        self.sample_rate = sample_rate
        self.model_path = model_path
        self.recording_duration = recording_duration
        self.model = None
        self.is_listening = False
        self._recorded_frames = []
        self._frames_lock = threading.Lock()  # 保护 _recorded_frames 的线程安全
        self._result_queue = queue.Queue()
        self._record_thread = None
        self._recording_started = threading.Event()
        self._current_hotwords = ""
        self.input_device = None  # 录音设备 index（None = 系统默认）
        self.enable_denoise = True  # 录音降噪预处理开关
        self._current_level = 0.0  # 实时音量电平（0~1，供波形图轮询）
        self.last_audio_path = None  # 最近一次录音保留的 wav 路径（供回放）

        # 热词文件路径（和 asr_engine.py 同目录）
        base_dir = os.path.dirname(os.path.abspath(__file__))
        self._hotwords_path = os.path.join(base_dir, "hotwords.txt")
        self._postprocess_path = os.path.join(base_dir, "postprocess_hotwords.txt")
        # 用户自适应热词（从历史病历提取的高频词，每行一个）
        self._user_hotwords_path = os.path.join(base_dir, "user_hotwords.txt")
        # 知识图谱热词池（xywy-KG 提取，按科室智能筛选）
        self._kg_hotwords_path = os.path.join(base_dir, "kg_hotwords.txt")
        self._user_hotwords = []
        self._kg_hotwords = {}  # {section: [words]} 知识图谱热词分区
        self._hotword_sections = {}  # {section_name: [words]}
        self._hotword_file = ""  # 当前科室热词临时文件路径
        self._postprocess_matcher = None  # 文本级纠错 matcher
        self._lm = None  # 医学语言模型（3-gram 重打分）
        self._confusion_pairs = {}  # ASR 高频混淆对（从用户反馈自动提取）
        self._field_context = ""  # 当前字段上下文（用于字段级 LM 偏置）
        # prompt 兼容层（M3 Top-K 术语引擎）
        self._prompt_pack = None
        self._prompt_terms = []
        self._prompt_pairs = []
        self._load_hotwords()
        self._load_user_hotwords()
        self._load_kg_hotwords()
        self._build_postprocess_matcher()
        self._load_language_model()
        self._load_confusion_pairs()

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

    def _load_kg_hotwords(self):
        """加载知识图谱热词池（kg_hotwords.txt，分区格式 [知识图谱-XX]）"""
        self._kg_hotwords = {}
        if not os.path.exists(self._kg_hotwords_path):
            return
        try:
            current_section = ""
            with open(self._kg_hotwords_path, "r", encoding="utf-8") as f:
                for line in f:
                    raw = line.strip()
                    if not raw or raw.startswith("#"):
                        continue
                    if raw.startswith("[") and raw.endswith("]"):
                        current_section = raw[1:-1]
                        self._kg_hotwords.setdefault(current_section, [])
                        continue
                    if current_section:
                        self._kg_hotwords[current_section].append(raw)
            total = sum(len(v) for v in self._kg_hotwords.values())
            print(f"[ASR] 知识图谱热词池: {total} 个 ({len(self._kg_hotwords)} 个分区)")
        except Exception as e:
            print(f"[ASR] 加载KG热词失败: {e}")

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

        # 家族史高频表达（所有科室均可加载）
        if "家族史高频" in self._hotword_sections:
            words.extend(self._hotword_sections["家族史高频"])

        # 个人史高频表达（所有科室均可加载）
        if "个人史高频" in self._hotword_sections:
            words.extend(self._hotword_sections["个人史高频"])

        # 主诉高频表达（所有科室均可加载）
        if "主诉高频" in self._hotword_sections:
            words.extend(self._hotword_sections["主诉高频"])

        # 现病史高频表达（所有科室均可加载）
        if "现病史高频" in self._hotword_sections:
            words.extend(self._hotword_sections["现病史高频"])

        # 既往史高频表达（所有科室均可加载）
        if "既往史高频" in self._hotword_sections:
            words.extend(self._hotword_sections["既往史高频"])

        # 体格检查/辅助检查/婚育史/月经史/诊疗计划/出院医嘱高频表达（所有科室均可加载）
        for sec in ("体格检查高频", "辅助检查高频", "婚育史高频", "月经史高频",
                    "诊疗计划高频", "出院医嘱高频"):
            if sec in self._hotword_sections:
                words.extend(self._hotword_sections[sec])

        # 用户自适应热词（从历史病历学到的高频词）
        if self._user_hotwords:
            words.extend(self._user_hotwords)

        # 知识图谱热词（智能筛选，控制总量不超过 3000）
        kg_budget = max(0, 3000 - len(words))
        if kg_budget > 0 and self._kg_hotwords:
            kg_words = self._select_kg_hotwords(department, kg_budget)
            words.extend(kg_words)

        # Top-K 术语引擎热词（记忆库高频词）
        if self._prompt_terms:
            words.extend(self._prompt_terms)

        # 去重（保序）
        words = list(dict.fromkeys(words))

        self._current_hotwords = " ".join(words)

        # 生成热词文件（Paraformer 模型级热词需要 .txt 文件路径）
        self._write_hotword_file(words)
        print(f"[ASR] 热词已切换到 [{department}]：{len(words)} 个热词，文件: {self._hotword_file}")

    def _write_hotword_file(self, words):
        """将热词列表写入临时 .txt 文件（每行一个热词）

        支持 "词:N" 权重写法：FunASR 热词文件不支持冒号权重语法，
        这里把 :N 展开为重复写 N 遍（重复 = 权重提升，与模板热词增强机制一致）。
        """
        try:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            self._hotword_file = os.path.join(base_dir, ".hotwords_current.txt")
            with open(self._hotword_file, "w", encoding="utf-8") as f:
                for w in words:
                    # 解析权重后缀 词:N
                    weight = 1
                    if ":" in w:
                        word, _, suffix = w.rpartition(":")
                        if suffix.isdigit() and word:
                            w = word
                            weight = max(1, min(int(suffix), 5))
                    for _ in range(weight):
                        f.write(w + "\n")
        except Exception as e:
            print(f"[ASR] 写入热词文件失败: {e}")
            self._hotword_file = ""

    def _select_kg_hotwords(self, department, budget):
        """
        从知识图谱热词池中智能筛选，控制总量不超过 budget。
        优先级：药物 > 检查 > 症状 > 科室 > 疾病。
        如果指定了科室，优先加载该科室相关疾病。
        """
        if budget <= 0:
            return []
        selected = []
        # 按优先级加载分区
        priority_order = ["知识图谱-药物", "知识图谱-检查", "知识图谱-症状", "知识图谱-科室"]
        for section in priority_order:
            if len(selected) >= budget:
                break
            pool = self._kg_hotwords.get(section, [])
            remaining = budget - len(selected)
            selected.extend(pool[:remaining])

        # 疾病词：如果指定科室，优先加载科室相关疾病
        disease_pool = self._kg_hotwords.get("知识图谱-疾病", [])
        remaining = budget - len(selected)
        if remaining > 0 and disease_pool:
            if department and department != "通用":
                dept_keyword = department[:2]
                scored = []
                for w in disease_pool:
                    score = 1 if dept_keyword in w else 0
                    if score:
                        scored.append((score, w))
                other = [w for w in disease_pool if w not in {w for _, w in scored}]
                selected.extend([w for _, w in sorted(scored, reverse=True)][:remaining])
                remaining = budget - len(selected)
                if remaining > 0:
                    selected.extend(other[:remaining])
            else:
                selected.extend(disease_pool[:remaining])

        return selected


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

    def _load_language_model(self):
        """加载医学 3-gram 语言模型（用于识别后重打分纠错）"""
        try:
            self._lm = MedicalLM()
            if self._lm.is_ready:
                print("[ASR] 医学语言模型已启用（3-gram 重打分）")
            else:
                self._lm = None
                print("[ASR] 语言模型未就绪，跳过重打分")
        except Exception as e:
            self._lm = None
            print(f"[ASR] 语言模型加载失败: {e}")

    # ─── 混淆对纠错（从用户反馈自动提取） ─────────────

    def _load_confusion_pairs(self):
        """加载 ASR 高频混淆对（asr_confusion_pairs.json）"""
        base_dir = os.path.dirname(os.path.abspath(__file__))
        path = os.path.join(base_dir, "asr_confusion_pairs.json")
        if not os.path.exists(path):
            return
        try:
            import json
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            # 格式: {"错误词": "正确词", ...}
            if isinstance(data, dict):
                self._confusion_pairs = data
                print(f"[ASR] 混淆对纠错表: {len(data)} 对")
        except Exception as e:
            print(f"[ASR] 加载混淆对失败: {e}")

    @staticmethod
    def extract_confusion_pairs(min_count=3):
        """
        从 correction_feedback.jsonl 中提取高频接受的纠错对，
        生成 asr_confusion_pairs.json。
        规则：同一 (original→corrected) 被接受 ≥ min_count 次 → 写入混淆对表。
        """
        import json
        from collections import Counter
        base_dir = os.path.dirname(os.path.abspath(__file__))
        feedback_path = os.path.join(base_dir, "correction_feedback.jsonl")
        output_path = os.path.join(base_dir, "asr_confusion_pairs.json")

        if not os.path.exists(feedback_path):
            print("[Extract] 无反馈数据，跳过")
            return {}

        pair_counter = Counter()
        manual_counter = Counter()  # 手动修正单独计数（阈值更低）
        try:
            with open(feedback_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    # 只统计被接受的纠错
                    if rec.get("status") != "accepted":
                        continue
                    orig = rec.get("original", "").strip()
                    corr = rec.get("corrected", "").strip()
                    if orig and corr and orig != corr and len(orig) <= 10:
                        if rec.get("source") == "user_manual" or rec.get("type") == "manual_edit":
                            manual_counter[(orig, corr)] += 1
                        else:
                            pair_counter[(orig, corr)] += 1
        except Exception as e:
            print(f"[Extract] 读取反馈失败: {e}")
            return {}

        # 筛选高频对（自动纠错≥3次，手动修正≥1次即入表）
        pairs = {orig: corr for (orig, corr), cnt in pair_counter.items() if cnt >= min_count}
        pairs.update({orig: corr for (orig, corr), cnt in manual_counter.items() if cnt >= 1})

        # 合并已有混淆对（保留旧的 + 新增）
        existing = {}
        if os.path.exists(output_path):
            try:
                with open(output_path, 'r', encoding='utf-8') as f:
                    existing = json.load(f)
            except Exception:
                pass
        existing.update(pairs)

        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(existing, f, ensure_ascii=False, indent=2)
            print(f"[Extract] 混淆对已更新: {len(existing)} 对（新增 {len(pairs)}）")
        except Exception as e:
            print(f"[Extract] 写入失败: {e}")
        return existing

    # ─── 模板动态热词增强 ─────────────────────────

    def boost_hotwords_for_template(self, template_content):
        """
        根据当前模板内容提取医学关键词，追加到热词文件（权重×2）。
        录音前调用，让 Paraformer 对模板相关词汇更敏感。
        """
        if not template_content:
            return
        # 提取模板中的医学关键词（2~8 字中文词）
        import re as _re
        # 匹配常见医学词汇模式
        candidates = _re.findall(r'[\u4e00-\u9fff]{2,8}', template_content)
        # 过滤非医学词（去掉常见虚词）
        stopwords = {'患者', '入院', '记录', '日期', '姓名', '性别', '年龄', '科室',
                     '床号', '住院号', '内容', '情况', '处理', '意见', '结果',
                     '正常', '未见', '异常', '检查', '报告', '时间', '天', '年'}
        keywords = [w for w in candidates if w not in stopwords and len(w) >= 2]
        # 去重
        keywords = list(dict.fromkeys(keywords))

        if not keywords:
            return

        # 重建热词文件：原有热词（去重） + 模板关键词（写两遍 = 权重×2）
        # 注意：只去重基础热词，不能整体去重，否则关键词的重复（权重增强）会被抹掉
        base_words = list(dict.fromkeys(
            self._current_hotwords.split() if self._current_hotwords else []
        ))
        boosted = base_words + keywords + keywords
        self._write_hotword_file(boosted)
        print(f"[ASR] 模板热词增强: +{len(keywords)} 个关键词（权重×2）")

    # ─── 字段级 LM 偏置 ─────────────────────────

    def set_field_context(self, field_name):
        """设置当前字段上下文（用于 LM 重打分偏置）"""
        self._field_context = field_name or ""

    # ─── Prompt 兼容层（M3 Top-K）────────────────────────

    def set_prompt_pack(self, prompt_pack):
        """保存 prompt 包，供 apply_prompt_pack() 使用"""
        if not isinstance(prompt_pack, dict):
            self._prompt_pack = None
            self._prompt_terms = []
            self._prompt_pairs = []
            return
        self._prompt_pack = prompt_pack
        self._prompt_terms = [str(term) for term in (prompt_pack.get("hotword_lines") or prompt_pack.get("selected_terms") or prompt_pack.get("top_terms") or []) if term]
        self._prompt_pairs = [list(pair) for pair in (prompt_pack.get("postprocess_hotword_lines") or prompt_pack.get("recent_pairs") or []) if len(pair) == 2]

    def build_prompt_from_topk(self, topk):
        """生成 prompt-like 文本包；topk 可为 TopKEngine 或 prompt_pack dict"""
        if hasattr(topk, "build_prompt_pack"):
            return topk.build_prompt_pack()
        if isinstance(topk, dict) and "top_terms" in topk:
            return topk
        return {}

    def apply_prompt_pack(self):
        """把 prompt 包转化为现有能消费的格式：追加热词、追加混淆对"""
        if not self._prompt_pack:
            return
        try:
            for wrong, right in self._prompt_pairs:
                wrong = str(wrong or "").strip()
                right = str(right or "").strip()
                if wrong and right and wrong != right:
                    self._confusion_pairs.setdefault(wrong, right)
        except Exception as e:
            print(f"[ASR] 应用 prompt 混淆对失败: {e}")

    # ─── 模型加载 ─────────────────────────────────────────

    def _load_model(self):
        """加载 Paraformer + VAD + 标点模型（优先使用医学微调权重）"""
        if not HAS_FUNASR:
            print("[ASR] FunASR 未安装")
            return
        try:
            # 检测医学微调权重（本地微调产物）
            ft_ckpt = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                   "finetune_ckpt", "paraformer_medical.pt")
            extra_kwargs = {}
            if os.path.exists(ft_ckpt):
                extra_kwargs["init_param"] = ft_ckpt
                print("[ASR] 检测到医学微调权重，加载 paraformer_medical.pt")
            print("[ASR] 正在加载 Paraformer + VAD + 标点模型...")
            self.model = AutoModel(
                model="paraformer-zh",
                vad_model="fsmn-vad",
                punc_model="ct-punc",
                device="cpu",
                disable_update=True,
                disable_log=True,
                **extra_kwargs,
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
            with self._frames_lock:
                self._recorded_frames = []

            def audio_callback(indata, frame_count, time_info, status):
                if status:
                    print(f"[ASR] 录音状态: {status}")
                with self._frames_lock:
                    self._recorded_frames.append(indata.copy())
                # 计算实时音量电平（RMS 归一化到 0~1）供波形图使用
                try:
                    arr = np.asarray(indata, dtype=np.float32)
                    rms = float(np.sqrt(np.mean(arr ** 2))) if arr.size else 0.0
                    self._current_level = min(1.0, rms / 3000.0)
                except Exception:
                    self._current_level = 0.0

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
            with self._frames_lock:
                frame_count = len(self._recorded_frames)
            print(f"[ASR] 录音结束，共 {frame_count} 帧")
        except Exception as e:
            self._recording_started.set()  # 确保主线程不会死等
            if self.is_listening and status_callback:
                status_callback(f"录音错误: {e}")
            print(f"[ASR] 录音异常: {e}")

    # ─── 识别 ─────────────────────────────────────────

    def _stream_recognize_loop(self):
        """流式识别监视线程：首次 1.5s 出字，后续每 3s 更新，能量门控避免空跑"""
        import time as _time
        first_interval = 1.0   # 首包等待（秒）
        interval = 1.5         # 后续间隔（秒）
        energy_threshold = 0.02  # 音量门控（RMS 归一化后）
        speech_frames_needed = 3  # 连续 N 帧有声音才触发
        last_count = 0
        is_first = True
        speech_streak = 0  # 连续有声帧计数

        while self.is_listening:
            wait = first_interval if is_first else interval
            _time.sleep(wait)
            if not self.is_listening:
                break

            # 能量门控：检测是否真的有人在说话
            if self._current_level < energy_threshold:
                speech_streak = 0
                if is_first:
                    continue  # 首包必须有声音才触发
                # 后续包：静音时跳过（但不要太久不更新）
                with self._frames_lock:
                    current_count = len(self._recorded_frames)
                if current_count - last_count < int(interval * self.sample_rate / 1600):
                    continue
            else:
                speech_streak += 1
                if is_first and speech_streak < speech_frames_needed:
                    continue  # 首包需连续几帧有声

            # 避免重叠推理
            if self._stream_busy:
                continue
            self._stream_busy = True
            try:
                with self._frames_lock:
                    current_count = len(self._recorded_frames)
                    frames_snapshot = list(self._recorded_frames)
                last_count = current_count
                audio = np.concatenate(frames_snapshot, axis=0)
                if audio.ndim == 2:
                    audio = audio.flatten()
                # 首包跳过降噪（省 ~100ms），后续包正常降噪
                if not is_first and self.enable_denoise:
                    audio = self._denoise(audio)
                # 写临时 wav
                tmp_fd, tmp_path = tempfile.mkstemp(suffix=".wav")
                os.close(tmp_fd)
                try:
                    with wave.open(tmp_path, 'wb') as wf:
                        wf.setnchannels(1)
                        wf.setsampwidth(2)
                        wf.setframerate(self.sample_rate)
                        wf.writeframes(audio.astype(np.int16).tobytes())
                    text = self._recognize_file_fast(tmp_path)
                finally:
                    try:
                        os.remove(tmp_path)
                    except Exception:
                        pass

                if text and self._on_partial:
                    self._on_partial(text)
                is_first = False  # 无论是否识别到文字，首包阶段结束
            except Exception as e:
                print(f"[ASR] 流式识别异常: {e}")
                is_first = False
            finally:
                self._stream_busy = False

    def _recognize_file_fast(self, wav_path):
        """轻量识别（用于流式中间结果，速度优先）"""
        if not self.is_ready():
            return ""
        try:
            kwargs = {"input": wav_path, "language": "zh", "use_itn": True}
            if self._hotword_file and os.path.exists(self._hotword_file):
                kwargs["hotword"] = self._hotword_file
            result = self.model.generate(**kwargs)
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
                text = self._apply_final_text_corrections(text)
                return text
            return ""
        except Exception:
            return ""

    def _apply_final_text_corrections(self, text):
        """对识别文本应用文本级纠错、规则纠错和 LM 重打分"""
        if not text:
            return text
        try:
            if self._postprocess_matcher:
                before = text
                result_dict = {"text": text}
                self._postprocess_matcher.apply_result(result_dict)
                text = result_dict["text"]
                if text != before:
                    print(f"[ASR] 文本纠错: {before} => {text}")
        except Exception as e:
            print(f"[ASR] 文本级纠错失败: {e}")
        try:
            text = post_process_medical(text)
        except Exception as e:
            print(f"[ASR] 规则纠错失败: {e}")
        try:
            if self._confusion_pairs:
                for wrong, right in self._confusion_pairs.items():
                    if wrong in text:
                        text = text.replace(wrong, right)
        except Exception as e:
            print(f"[ASR] 混淆对纠错失败: {e}")
        try:
            if self._lm and self._lm.is_ready:
                text = self._lm.rescore(text, field_context=self._field_context)
        except Exception as e:
            print(f"[ASR] LM 重打分失败: {e}")
        return text


    def get_audio_level(self):
        """返回当前录音音量电平（0~1），供 UI 波形图轮询"""
        return self._current_level

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

                # 混淆对纠错：确定性替换高频误识别词
                if self._confusion_pairs:
                    for wrong, right in self._confusion_pairs.items():
                        if wrong in text:
                            text = text.replace(wrong, right)

                # 语言模型重打分：纠正低概率区域（误识别）
                if self._lm and self._lm.is_ready:
                    # 字段级偏置：当前字段上下文传入 LM，提升字段相关术语权重
                    text = self._lm.rescore(text, field_context=self._field_context)

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

    def transcribe_file(self, audio_path):
        """
        转写音频文件（供拖拽/导入使用）。
        支持 wav；mp3/m4a/flac 等尝试用 soundfile 读取后转 wav。
        返回识别文本（已含热词+纠错+LM重打分）。
        """
        if not self.is_ready():
            return ""
        if not os.path.exists(audio_path):
            return ""
        ext = os.path.splitext(audio_path)[1].lower()
        if ext == ".wav":
            return self._recognize_file(audio_path)
        # 非 wav：尝试用 soundfile 读取并重采样为 16k wav
        try:
            import soundfile as sf
            import numpy as np
            data, sr = sf.read(audio_path, dtype="float32")
            if data.ndim > 1:
                data = data.mean(axis=1)
            if sr != self.sample_rate:
                ratio = self.sample_rate / float(sr)
                new_len = int(len(data) * ratio)
                idx = np.linspace(0, len(data) - 1, new_len)
                data = np.interp(idx, np.arange(len(data)), data)
            tmp_fd, tmp_path = tempfile.mkstemp(suffix=".wav")
            os.close(tmp_fd)
            import wave as _wave
            pcm = (data * 32767).astype(np.int16)
            with _wave.open(tmp_path, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(self.sample_rate)
                wf.writeframes(pcm.tobytes())
            try:
                return self._recognize_file(tmp_path)
            finally:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
        except Exception as e:
            print(f"[ASR] 音频文件转写失败: {e}")
            return ""

    def start_listening(self, on_result=None, on_partial=None):
        """开始录音（支持流式回调：on_partial(text) 边说边出字）"""
        if not self.is_ready():
            return False
        self.is_listening = True
        self._recorded_frames = []
        self._recording_started.clear()
        self._stream_busy = False  # 流式识别锁（避免重叠推理）
        self._on_partial = on_partial
        self._record_thread = threading.Thread(target=self._record_loop, daemon=True)
        self._record_thread.start()
        # 流式识别监视线程：每隔几秒对已录音频做一次快速识别
        self._stream_thread = threading.Thread(
            target=self._stream_recognize_loop, daemon=True
        )
        self._stream_thread.start()
        print("[ASR] 开始录音（流式模式）")
        return True

    def stop_listening(self):
        """停止录音，返回最终识别文本（全量精确识别）"""
        self.is_listening = False
        if self._record_thread:
            self._recording_started.wait(timeout=3)
            if self._record_thread.is_alive():
                self._record_thread.join(timeout=5)
        # 等待流式线程退出
        if hasattr(self, '_stream_thread') and self._stream_thread:
            self._stream_thread.join(timeout=3)
            self._stream_thread = None

        with self._frames_lock:
            has_frames = bool(self._recorded_frames)
        if not has_frames:
            print("[ASR] 没有录音数据")
            return ""

        tmp_fd, tmp_path = tempfile.mkstemp(suffix=".wav")
        os.close(tmp_fd)
        try:
            with self._frames_lock:
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

            # 保留一份录音到 recordings/ 目录（供音文对照回放）
            try:
                rec_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "recordings")
                os.makedirs(rec_dir, exist_ok=True)
                import datetime
                stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                keep_path = os.path.join(rec_dir, f"rec_{stamp}.wav")
                with wave.open(keep_path, 'wb') as wf2:
                    wf2.setnchannels(1)
                    wf2.setsampwidth(2)
                    wf2.setframerate(self.sample_rate)
                    wf2.writeframes(audio_data.tobytes())
                self.last_audio_path = keep_path
                self._cleanup_old_recordings(rec_dir)
            except Exception as e:
                print(f"[ASR] 保留录音文件失败: {e}")

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

    def _cleanup_old_recordings(self, rec_dir, keep=30):
        """只保留最近 keep 份录音，避免磁盘堆积"""
        try:
            files = sorted(
                (os.path.join(rec_dir, f) for f in os.listdir(rec_dir) if f.endswith(".wav")),
                key=os.path.getmtime
            )
            for old in files[:-keep]:
                os.remove(old)
        except Exception:
            pass

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
