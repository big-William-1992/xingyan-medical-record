"""
ASR 模型加载 + 热词管理 + 语言模型
"""
import hashlib
import logging
import os
import re
import threading
from typing import Optional, Dict, List

logger = logging.getLogger(__name__)


class ModelLoader:
    """管理 ASR 模型加载、热词、语言模型等"""

    def __init__(self, engine):
        self.engine = engine
        self.model = None
        self._lm = None
        self._confusion_pairs: Dict[str, str] = {}

    def initialize(self):
        """执行完整的模型初始化序列"""
        self._load_hotwords()
        self._load_user_hotwords()
        self._load_kg_hotwords()
        self._build_postprocess_matcher()
        self._load_language_model()
        self._load_confusion_pairs()
        self._load_model()

    # ─── 热词管理 ─────────────────────────────────────────

    def _load_hotwords(self):
        """加载 hotwords.txt，按 # 注释分隔不同分区"""
        self.engine._hotword_sections = {}
        current_section = "通用"
        path = self.engine._hotwords_path

        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    raw = line.rstrip("\n")
                    stripped = raw.strip()
                    if not stripped:
                        continue
                    if stripped.startswith("#"):
                        current_section = stripped.lstrip("#").strip()
                        self.engine._hotword_sections.setdefault(current_section, [])
                    else:
                        self.engine._hotword_sections.setdefault(current_section, []).append(stripped)
        except Exception as e:
            logger.warning(f"[ASR] 加载热词文件失败: {e}")

    def _load_user_hotwords(self):
        """加载用户自适应热词（从历史病历提取的高频词）"""
        path = self.engine._user_hotwords_path
        self.engine._user_hotwords = []
        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    w = line.strip()
                    if w and not w.startswith("#"):
                        self.engine._user_hotwords.append(w)
        except Exception:
            pass

    def _load_kg_hotwords(self):
        """加载知识图谱热词池（按科室分区）"""
        path = self.engine._kg_hotwords_path
        self.engine._kg_hotwords = {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                current_section = "通用"
                for line in f:
                    raw = line.rstrip("\n")
                    stripped = raw.strip()
                    if not stripped:
                        continue
                    if stripped.startswith("#"):
                        current_section = stripped.lstrip("#").strip()
                    else:
                        self.engine._kg_hotwords.setdefault(current_section, []).append(stripped)
        except Exception:
            pass

    def update_user_hotwords(self, words, max_words=300):
        """更新用户热词（去重，限制数量）"""
        seen = set(self.engine._user_hotwords)
        new_words = [w for w in words if w not in seen]
        self.engine._user_hotwords.extend(new_words)
        if len(self.engine._user_hotwords) > max_words:
            self.engine._user_hotwords = self.engine._user_hotwords[-max_words:]
        try:
            with open(self.engine._user_hotwords_path, "w", encoding="utf-8") as f:
                f.write("\n".join(self.engine._user_hotwords))
        except Exception as e:
            logger.warning(f"[ASR] 保存用户热词失败: {e}")

    def set_hotwords(self, department=""):
        """根据科室组合热词并写入临时文件"""
        all_words = list(self.engine._hotword_sections.get("通用", []))

        # 按科室添加知识图谱热词（预算 100 词）
        if department:
            all_words.extend(self._select_kg_hotwords(department, budget=100))

        # 加入用户自适应热词（预算 50 词）
        all_words.extend(self.engine._user_hotwords[:50])

        # 去重
        seen = set()
        deduped = []
        for w in all_words:
            if w not in seen:
                seen.add(w)
                deduped.append(w)

        self.engine._current_hotwords = " ".join(deduped)
        self._write_hotword_file(deduped)
        return self.engine._current_hotwords

    def _write_hotword_file(self, words):
        """将热词列表写入临时文件（供 FunASR 模型使用）"""
        import tempfile
        try:
            fd, path = tempfile.mkstemp(suffix=".txt", prefix="hotwords_")
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write("\n".join(words))
            self.engine._hotword_file = path
        except Exception as e:
            logger.warning(f"[ASR] 写入热词文件失败: {e}")

    def _select_kg_hotwords(self, department, budget=100):
        """从知识图谱热词池中按科室选取热词"""
        candidates = self.engine._kg_hotwords.get(department, [])
        if not candidates:
            candidates = self.engine._kg_hotwords.get("通用", [])
        return candidates[:budget]

    def _build_postprocess_matcher(self):
        """构建文本级纠错 matcher"""
        try:
            from funasr.utils.postprocess_hotwords import build_postprocess_hotword_matcher
            path = self.engine._postprocess_path
            if os.path.exists(path):
                self.engine._postprocess_matcher = build_postprocess_hotword_matcher(path)
        except Exception as e:
            logger.warning(f"[ASR] 构建 postprocess matcher 失败: {e}")

    def _load_language_model(self):
        """加载医学语言模型（3-gram 重打分）"""
        try:
            from medical_lm import MedicalLM
            self.engine._lm = MedicalLM()
        except Exception as e:
            logger.warning(f"[ASR] 加载医学语言模型失败: {e}")

    def _load_confusion_pairs(self):
        """加载 ASR 高频混淆对（从用户反馈自动提取）"""
        self.engine._confusion_pairs = {}
        try:
            pairs_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "confusion_pairs.json")
            if os.path.exists(pairs_path):
                import json
                with open(pairs_path, "r", encoding="utf-8") as f:
                    self.engine._confusion_pairs = json.load(f)
        except Exception:
            pass

    @staticmethod
    def extract_confusion_pairs(min_count: int = 3) -> dict:
        """从用户反馈语料中提取高频混淆对"""
        try:
            from correction_feedback import CorrectionFeedback
            fb = CorrectionFeedback()
            return fb.extract_confusion_pairs(min_count=min_count)
        except Exception:
            return {}

    def boost_hotwords_for_template(self, template_content: str) -> str:
        """从模板内容中提取关键词加入热词"""
        if not template_content:
            return ""
        keywords = re.findall(r'[一-鿿]{2,8}', template_content)
        keywords = [k for k in keywords if k not in ("如下", "如下所示", "例如", "等")]
        current = set(self.engine._current_hotwords.split())
        current.update(keywords[:30])
        self.engine._current_hotwords = " ".join(current)
        self._write_hotword_file(list(current))
        return self.engine._current_hotwords

    def set_field_context(self, field_name: str):
        """设置当前字段上下文（用于字段级 LM 偏置）"""
        self.engine._field_context = field_name or ""

    def set_prompt_pack(self, prompt_pack):
        """设置 prompt 兼容层（M3 Top-K 术语引擎）"""
        self.engine._prompt_pack = prompt_pack
        self.engine._prompt_terms = []
        self.engine._prompt_pairs = []

    def build_prompt_from_topk(self, topk):
        """从 Top-K 结果构建 prompt 术语"""
        if not topk:
            return
        self.engine._prompt_terms = []
        self.engine._prompt_pairs = []
        for item in topk:
            term = item.get("term", "")
            if term and len(term) >= 2:
                self.engine._prompt_terms.append(term)
                wrong = item.get("wrong", "")
                if wrong:
                    self.engine._prompt_pairs.append((wrong, term))

    def apply_prompt_pack(self):
        """将 prompt 术语应用到当前热词"""
        if not self.engine._prompt_terms:
            return
        current = set(self.engine._current_hotwords.split())
        current.update(self.engine._prompt_terms[:50])
        self.engine._current_hotwords = " ".join(current)
        self._write_hotword_file(list(current))

    # ─── 模型加载 ─────────────────────────────────────────

    def _load_model(self):
        """加载 Paraformer + VAD + 标点模型"""
        try:
            from funasr import AutoModel
            HAS_FUNASR = True
        except ImportError:
            logger.error("[ASR] FunASR 未安装")
            return

        try:
            ft_ckpt = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                   "finetune_ckpt", "paraformer_medical.pt")
            extra_kwargs = {}
            if os.path.exists(ft_ckpt):
                extra_kwargs["init_param"] = ft_ckpt
                logger.info("[ASR] 检测到医学微调权重")

            if not self._check_model_exists():
                print("[ASR] 模型文件不存在，开始自动下载...")
                if not self._download_models():
                    logger.critical("[ASR] 模型下载失败")
                    return

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
            logger.error(f"[ASR] 模型加载失败: {e}")
            import traceback
            traceback.print_exc()

    def _check_model_exists(self) -> bool:
        """检查模型文件是否已下载"""
        try:
            cache_dir = os.path.expanduser("~/.cache/modelscope/hub")
            for model_name in ["paraformer-zh", "fsmn-vad", "ct-punc"]:
                if not os.path.exists(os.path.join(cache_dir, model_name)):
                    return False
            print("[ASR] 模型文件已存在")
            return True
        except Exception as e:
            logger.error(f"[ASR] 检查模型时出错: {e}")
            return False

    def _download_models(self) -> bool:
        """自动下载 FunASR 模型"""
        try:
            print("[ASR] 下载语音识别模型（约 1GB）...")
            from modelscope import snapshot_download
            models = [
                ("paraformer-zh", "iic/speech_paraformer-large_asr_nat-zh-cn-16k-common-vocab8404-pytorch"),
                ("fsmn-vad", "iic/speech_fsmn_vad_zh-cn-16k-common-pytorch"),
                ("ct-punc", "iic/punc_ct-transformer_cn-en-common-vocab471067-large"),
            ]
            for i, (name, mid) in enumerate(models, 1):
                print(f"[ASR] [{i}/{len(models)}] 下载 {name}...")
                snapshot_download(mid, cache_dir=os.path.expanduser("~/.cache/modelscope/hub"))
                print(f"[ASR] {name} 下载完成")
            print("[ASR] 所有模型下载完成")
            return True
        except ImportError:
            logger.error("[ASR] modelscope 未安装")
            return False
        except Exception as e:
            logger.error(f"[ASR] 下载模型时出错: {e}")
            return False
