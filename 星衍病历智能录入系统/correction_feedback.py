"""
纠错反馈收集器 - 用于语言模型迭代训练

功能：
  1. 记录每次纠错的修正对（原文→修正）到 correction_feedback.jsonl
  2. 记录用户对纠错的接受/拒绝决策
  3. 收集用户最终确认的病历文本到 user_corpus.txt（高质量语料）

数据流：
  纠错完成 → log_corrections() → correction_feedback.jsonl
  用户拒绝 → log_rejection()   → 更新对应记录 status="rejected"
  保存/导出 → collect_corpus()  → user_corpus.txt

训练时使用：
  python train_lm.py  # 读取所有语料 + 反馈，重训 medical_3gram.pkl
"""
import json
import os
import time
from datetime import datetime

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FEEDBACK_PATH = os.path.join(_BASE_DIR, "correction_feedback.jsonl")
USER_CORPUS_PATH = os.path.join(_BASE_DIR, "user_corpus.txt")

# 语料去重：记录已收集文本的哈希（避免重复写入）
_CORPUS_HASH_PATH = os.path.join(_BASE_DIR, ".corpus_hashes.json")


class CorrectionFeedback:
    """纠错反馈收集器（轻量、无阻塞、线程安全）"""

    def __init__(self, feedback_path=None, corpus_path=None):
        self.feedback_path = feedback_path or FEEDBACK_PATH
        self.corpus_path = corpus_path or USER_CORPUS_PATH
        self._corpus_hashes = self._load_corpus_hashes()

    # ─── 纠错日志记录 ─────────────────────────────────────

    def log_corrections(self, log_items, source="corrector"):
        """
        记录一批纠错日志。

        Args:
            log_items: 纠错日志列表，每项含 {原文, 修正, type, 级别, 分类}
            source: 来源标识（corrector / lm_rescore / rule_engine）
        """
        if not log_items:
            return
        records = []
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for item in log_items:
            orig = item.get("原文", "")
            corr = item.get("修正", "")
            if not orig or not corr or orig == corr:
                continue
            records.append({
                "original": orig,
                "corrected": corr,
                "type": item.get("type", ""),
                "category": item.get("分类", ""),
                "level": item.get("级别", ""),
                "source": source,
                "status": "pending",  # pending → accepted / rejected
                "time": ts,
            })
        if records:
            self._append_jsonl(records)

    def log_rejection(self, original, corrected):
        """
        记录用户拒绝某条纠错（将最近的 pending 记录标记为 rejected）。
        """
        self._update_status(original, corrected, "rejected")

    def log_accept_all(self):
        """
        用户未做任何拒绝即保存/导出 → 将所有 pending 标记为 accepted。
        """
        self._batch_update_status("pending", "accepted")

    # ─── 高质量语料收集 ───────────────────────────────────

    def collect_corpus(self, text, min_length=20):
        """
        收集用户最终确认的病历文本作为训练语料。

        Args:
            text: 最终病历全文
            min_length: 最短长度（过短的跳过）
        Returns:
            bool: 是否成功收集（False 表示重复或过短）
        """
        if not text or len(text.strip()) < min_length:
            return False

        # 简单哈希去重（避免同一份病历反复写入）
        text_hash = str(hash(text.strip()))
        if text_hash in self._corpus_hashes:
            return False

        # 按句切分写入（每句一行，与 lm_corpus.txt 格式一致）
        sentences = self._split_sentences(text)
        if not sentences:
            return False

        try:
            with open(self.corpus_path, "a", encoding="utf-8") as f:
                for sent in sentences:
                    sent = sent.strip()
                    if len(sent) >= 4:  # 至少4个字符
                        f.write(sent + "\n")
            # 记录哈希
            self._corpus_hashes[text_hash] = datetime.now().strftime("%Y-%m-%d")
            self._save_corpus_hashes()
            return True
        except Exception as e:
            print(f"[Feedback] 语料收集失败: {e}")
            return False

    # ─── 统计信息 ─────────────────────────────────────────

    def get_stats(self):
        """获取反馈统计"""
        stats = {
            "feedback_file": self.feedback_path,
            "corpus_file": self.corpus_path,
            "total_corrections": 0,
            "accepted": 0,
            "rejected": 0,
            "pending": 0,
            "corpus_sentences": 0,
            "corpus_collected": len(self._corpus_hashes),
        }
        # 统计反馈条数
        if os.path.exists(self.feedback_path):
            try:
                with open(self.feedback_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        stats["total_corrections"] += 1
                        try:
                            rec = json.loads(line)
                            status = rec.get("status", "pending")
                            if status in stats:
                                stats[status] += 1
                        except json.JSONDecodeError:
                            pass
            except Exception:
                pass
        # 统计语料行数
        if os.path.exists(self.corpus_path):
            try:
                with open(self.corpus_path, "r", encoding="utf-8") as f:
                    stats["corpus_sentences"] = sum(1 for _ in f)
            except Exception:
                pass
        return stats

    # ─── 内部方法 ─────────────────────────────────────────

    def _append_jsonl(self, records):
        """追加写入 JSONL 文件"""
        try:
            with open(self.feedback_path, "a", encoding="utf-8") as f:
                for rec in records:
                    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        except Exception as e:
            print(f"[Feedback] 写入失败: {e}")

    def _update_status(self, original, corrected, new_status):
        """更新最近一条匹配的 pending 记录状态"""
        if not os.path.exists(self.feedback_path):
            return
        try:
            lines = []
            updated = False
            with open(self.feedback_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            # 从后往前找匹配的 pending 记录
            for i in range(len(lines) - 1, -1, -1):
                line = lines[i].strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                    if (rec.get("original") == original and
                            rec.get("corrected") == corrected and
                            rec.get("status") == "pending"):
                        rec["status"] = new_status
                        rec["resolved_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        lines[i] = json.dumps(rec, ensure_ascii=False) + "\n"
                        updated = True
                        break
                except json.JSONDecodeError:
                    continue
            if updated:
                with open(self.feedback_path, "w", encoding="utf-8") as f:
                    f.writelines(lines)
        except Exception as e:
            print(f"[Feedback] 状态更新失败: {e}")

    def _batch_update_status(self, old_status, new_status):
        """批量更新所有 old_status 记录为 new_status"""
        if not os.path.exists(self.feedback_path):
            return
        try:
            lines = []
            changed = False
            with open(self.feedback_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            for i, line in enumerate(lines):
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    rec = json.loads(stripped)
                    if rec.get("status") == old_status:
                        rec["status"] = new_status
                        rec["resolved_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        lines[i] = json.dumps(rec, ensure_ascii=False) + "\n"
                        changed = True
                except json.JSONDecodeError:
                    continue
            if changed:
                with open(self.feedback_path, "w", encoding="utf-8") as f:
                    f.writelines(lines)
        except Exception as e:
            print(f"[Feedback] 批量更新失败: {e}")

    def _split_sentences(self, text):
        """将病历文本按句切分（适配 LM 训练格式）"""
        import re
        # 按句号、感叹号、问号、换行切分
        parts = re.split(r'[。！？\n]+', text)
        sentences = []
        for p in parts:
            p = p.strip()
            if p and len(p) >= 4:
                sentences.append(p)
        return sentences

    def _load_corpus_hashes(self):
        """加载已收集的文本哈希"""
        if not os.path.exists(_CORPUS_HASH_PATH):
            return {}
        try:
            with open(_CORPUS_HASH_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _save_corpus_hashes(self):
        """保存文本哈希"""
        try:
            with open(_CORPUS_HASH_PATH, "w", encoding="utf-8") as f:
                json.dump(self._corpus_hashes, f, ensure_ascii=False)
        except Exception:
            pass
