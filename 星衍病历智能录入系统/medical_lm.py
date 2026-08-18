"""
医学 3-gram 语言模型 - 用于 ASR 识别后重打分/纠错

原理：
  ASR 声学模型输出文本后，用医学领域语言模型评估文本的"医学合理性"。
  对低概率区域（可能是误识别），尝试用医学词库替换，选择 LM 得分更高的候选。

使用：
  from medical_lm import MedicalLM
  lm = MedicalLM()
  # 整体评分
  score = lm.score("患者既往有高血压病史")
  # 纠错重打分
  corrected = lm.rescore("患者既望有高血压病史")  # → "患者既往有高血压病史"
"""
import os
import math
import pickle
from collections import Counter

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_MODEL_PATH = os.path.join(_BASE_DIR, "medical_3gram.pkl")
_DRUG_NAMES_PATH = os.path.join(_BASE_DIR, "drug_names.txt")
_TERMS_PATH = os.path.join(_BASE_DIR, "medical_terms_thuocl.txt")


class MedicalLM:
    """字符级 3-gram 医学语言模型"""

    def __init__(self, model_path=None):
        self.unigrams = {}
        self.bigrams = {}
        self.trigrams = {}
        self.total = 0
        self.vocab_size = 0
        self._loaded = False

        # 医学词库（用于生成候选替换）
        self._terms = set()
        self._term_chars = {}  # char → [terms containing it]

        self._load(model_path or _MODEL_PATH)
        self._load_terms()

    def _load(self, path):
        """加载预训练的 n-gram 模型（仅限本地训练生成的 .pkl）"""
        if not os.path.exists(path):
            print(f"[LM] 模型文件不存在: {path}")
            return
        try:
            with open(path, "rb") as f:
                data = pickle.load(f)
            # 结构验证：确保是本工具生成的合法模型文件
            if not isinstance(data, dict):
                raise ValueError("模型格式无效")
            required_keys = {"unigrams", "bigrams", "trigrams", "total", "vocab_size"}
            if not required_keys.issubset(data.keys()):
                raise ValueError(f"模型缺少必要字段: {required_keys - set(data.keys())}")
            if not isinstance(data["unigrams"], dict) or not isinstance(data["total"], int):
                raise ValueError("模型字段类型错误")
            self.unigrams = data["unigrams"]
            self.bigrams = data["bigrams"]
            self.trigrams = data["trigrams"]
            self.total = data["total"]
            self.vocab_size = data["vocab_size"]
            self._loaded = True
            print(f"[LM] 语言模型已加载: {self.vocab_size} 词表, "
                  f"{len(self.trigrams)} 三元组")
        except Exception as e:
            print(f"[LM] 加载失败: {e}")

    def _load_terms(self):
        """加载医学术语词库（用于候选生成）"""
        for path in [_TERMS_PATH, _DRUG_NAMES_PATH]:
            if not os.path.exists(path):
                continue
            try:
                with open(path, "r", encoding="utf-8") as f:
                    for line in f:
                        w = line.strip()
                        if len(w) >= 2:
                            self._terms.add(w)
            except Exception as e:
                print(f"[LM] 加载医学术语失败 ({path}): {e}")
        # 建立字符索引（加速查找包含某字的词）
        for term in self._terms:
            for ch in term:
                self._term_chars.setdefault(ch, []).append(term)
        print(f"[LM] 医学术语词库: {len(self._terms)} 条")

    @property
    def is_ready(self):
        return self._loaded

    # ─── 概率计算（带 Add-k 平滑）─────────────────────────

    def _log_prob_unigram(self, c):
        """P(c) with add-1 smoothing"""
        count = self.unigrams.get(c, 0)
        return math.log((count + 0.1) / (self.total + self.vocab_size * 0.1))

    def _log_prob_bigram(self, c1, c2):
        """P(c2|c1) with backoff to unigram"""
        bi_count = self.bigrams.get((c1, c2), 0)
        uni_count = self.unigrams.get(c1, 0)
        if uni_count == 0:
            return self._log_prob_unigram(c2)
        if bi_count > 0:
            return math.log(bi_count / uni_count)
        # backoff
        return self._log_prob_unigram(c2) - 2.0  # backoff penalty

    def _log_prob_trigram(self, c1, c2, c3):
        """P(c3|c1,c2) with backoff to bigram"""
        tri_count = self.trigrams.get((c1, c2, c3), 0)
        bi_count = self.bigrams.get((c1, c2), 0)
        if bi_count == 0:
            return self._log_prob_bigram(c2, c3)
        if tri_count > 0:
            return math.log(tri_count / bi_count)
        # backoff
        return self._log_prob_bigram(c2, c3) - 1.5  # backoff penalty

    # ─── 文本评分 ─────────────────────────────────────────

    def score(self, text):
        """计算文本的平均 log 概率（越高越合理）"""
        if not text or not self._loaded:
            return 0.0
        chars = list(text)
        if len(chars) < 2:
            return self._log_prob_unigram(chars[0]) if chars else 0.0

        total_log = 0.0
        # 前两个字符用低阶
        total_log += self._log_prob_unigram(chars[0])
        total_log += self._log_prob_bigram(chars[0], chars[1])
        for i in range(2, len(chars)):
            total_log += self._log_prob_trigram(chars[i-2], chars[i-1], chars[i])
        return total_log / len(chars)

    def score_region(self, text, start, end):
        """计算文本 [start:end] 区间的局部 LM 得分"""
        if not text or not self._loaded:
            return 0.0
        chars = list(text)
        region = chars[max(0, start-2):min(len(chars), end+2)]
        if len(region) < 2:
            return 0.0
        total_log = 0.0
        total_log += self._log_prob_unigram(region[0])
        total_log += self._log_prob_bigram(region[0], region[1])
        for i in range(2, len(region)):
            total_log += self._log_prob_trigram(region[i-2], region[i-1], region[i])
        return total_log / len(region)

    # ─── 重打分纠错 ───────────────────────────────────────

    def rescore(self, text, max_corrections=3, field_context=""):
        """
        对 ASR 输出进行语言模型纠错（保守策略，短语级替换）：
        1. 滑窗计算局部得分，找到极低分区域
        2. 对低分区域，尝试用已知医学术语替换同长度片段
        3. 仅当替换后得分显著优于原始时才采纳
        field_context: 当前字段名（如"现病史"），有值时降低纠错阈值、更积极替换
        """
        if not text or not self._loaded or len(text) < 6:
            return text

        n = len(text)
        corrections = 0
        result = text

        # 字段偏置：有上下文时阈值更敏感（2.0σ → 1.7σ）
        sigma_factor = 1.7 if field_context else 2.0

        # 第1步：计算每个位置的 trigram 得分
        pos_scores = self._compute_pos_scores(result)
        if not pos_scores:
            return text

        mean_s = sum(pos_scores) / len(pos_scores)
        var_s = sum((s - mean_s) ** 2 for s in pos_scores) / len(pos_scores)
        std_s = var_s ** 0.5
        threshold = mean_s - sigma_factor * std_s

        # 第2步：找连续低分区域（窗口 2~6 字）
        low_positions = [i for i, s in enumerate(pos_scores) if s < threshold]
        if not low_positions:
            return text

        # 合并相邻低分位置为区域
        regions = self._merge_low_regions(low_positions, n)

        # 第3步：对每个低分区域尝试术语替换
        for start, end in regions:
            if corrections >= max_corrections:
                break
            region_len = end - start
            if region_len < 2 or region_len > 8:
                continue
            original_segment = result[start:end]
            original_score = self.score_region(result, start, end)

            # 查找同长度的医学术语候选
            candidates = self._find_similar_terms(original_segment)
            if not candidates:
                continue

            best_replacement = None
            best_score = original_score
            # 字段偏置：有上下文时降低采纳门槛（1.0 → 0.7）
            adopt_margin = 0.7 if field_context else 1.0
            for cand in candidates:
                test_text = result[:start] + cand + result[end:]
                cand_score = self.score_region(test_text, start, end)
                if cand_score > best_score + adopt_margin:
                    best_score = cand_score
                    best_replacement = cand

            if best_replacement:
                result = result[:start] + best_replacement + result[end:]
                corrections += 1

        if corrections > 0 and result != text:
            print(f"[LM] 重打分纠错: {corrections} 处修正")
            print(f"[LM]   原始: {text[:80]}")
            print(f"[LM]   修正: {result[:80]}")
        return result

    def _compute_pos_scores(self, text):
        """计算每个位置的 trigram 得分"""
        chars = list(text)
        n = len(chars)
        scores = []
        for i in range(n):
            if i == 0:
                s = self._log_prob_unigram(chars[0])
            elif i == 1:
                s = self._log_prob_bigram(chars[0], chars[1])
            else:
                s = self._log_prob_trigram(chars[i-2], chars[i-1], chars[i])
            scores.append(s)
        return scores

    def _merge_low_regions(self, low_positions, text_len):
        """合并相邻低分位置为区域 [(start, end), ...]"""
        if not low_positions:
            return []
        regions = []
        start = low_positions[0]
        end = low_positions[0] + 1
        for pos in low_positions[1:]:
            if pos <= end + 1:  # 相邻或间隔1
                end = pos + 1
            else:
                regions.append((start, end))
                start = pos
                end = pos + 1
        regions.append((start, end))
        # 过滤太短的区域（单字不改）
        return [(s, e) for s, e in regions if e - s >= 2]

    def _find_similar_terms(self, segment):
        """查找与 segment 近长度且相似的医学术语"""
        seg_len = len(segment)
        if seg_len < 2 or seg_len > 8:
            return []
        candidates = []
        # 从包含 segment 中任一字的术语中筛选近长度候选
        seen = set()
        for ch in segment:
            for term in self._term_chars.get(ch, []):
                if abs(len(term) - seg_len) > 1 or term == segment or term in seen:
                    continue
                seen.add(term)
                # 至少有一个字不同（且不是完全不同）
                common = sum(1 for a, b in zip(segment, term) if a == b)
                if 0 < common < seg_len:  # 部分匹配
                    candidates.append(term)
        return candidates[:50]  # 限制候选数


    def _find_term_spans(self, text):
        """找出文本中所有已知医学术语的位置"""
        protected = set()
        n = len(text)
        for length in range(2, 9):
            for i in range(n - length + 1):
                substr = text[i:i+length]
                if substr in self._terms:
                    for j in range(i, i + length):
                        protected.add(j)
        return protected

    def _local_score(self, chars, pos):
        """计算 pos 位置及其前后的局部得分（窗口 ±2）"""
        total = 0.0
        count = 0
        for i in range(max(0, pos-2), min(len(chars), pos+3)):
            if i == 0:
                total += self._log_prob_unigram(chars[0])
            elif i == 1:
                total += self._log_prob_bigram(chars[0], chars[1])
            else:
                total += self._log_prob_trigram(chars[i-2], chars[i-1], chars[i])
            count += 1
        return total / count if count else 0.0

    # ─── 短语级重打分（N-best 选择）──────────────────────

    def rescore_nbest(self, candidates):
        """
        从多个候选文本中选择 LM 得分最高的。
        candidates: list of str
        返回: (best_text, best_score)
        """
        if not candidates:
            return "", 0.0
        if len(candidates) == 1:
            return candidates[0], self.score(candidates[0])

        best_text = candidates[0]
        best_score = -float("inf")
        for text in candidates:
            s = self.score(text)
            if s > best_score:
                best_score = s
                best_text = text
        return best_text, best_score

    # ─── 术语验证 ─────────────────────────────────────────

    def is_medical_term(self, word):
        """检查是否为已知医学术语"""
        return word in self._terms

    def suggest_term(self, partial):
        """根据前缀建议医学术语"""
        suggestions = []
        for term in self._terms:
            if term.startswith(partial) and term != partial:
                suggestions.append(term)
            if len(suggestions) >= 10:
                break
        return suggestions