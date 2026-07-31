#!/usr/bin/env python3
"""
医学 3-gram 语言模型训练脚本

功能：
  合并多源语料 → 训练字符级 3-gram → 输出 medical_3gram.pkl

语料来源（按优先级）：
  1. lm_corpus.txt          — 基础医学语料（73K句，疾病/症状/药物/检查）
  2. user_corpus.txt        — 用户确认的病历终稿（高质量，自动收集）
  3. correction_feedback.jsonl — 纠错反馈（accepted 的修正对作为正例）

用法：
  python train_lm.py              # 训练并输出 medical_3gram.pkl
  python train_lm.py --stats      # 仅显示语料统计，不训练
  python train_lm.py --dry-run    # 模拟训练，显示新三元组增量，不写文件
  python train_lm.py -o out.pkl   # 指定输出路径

输出格式（与 medical_lm.py 兼容）：
  {
    "unigrams": {char: count, ...},
    "bigrams": {(c1,c2): count, ...},
    "trigrams": {(c1,c2,c3): count, ...},
    "total": int,
    "vocab_size": int,
  }
"""
import argparse
import json
import os
import pickle
import sys
import time
from collections import Counter

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 语料文件路径
CORPUS_FILES = [
    os.path.join(_BASE_DIR, "lm_corpus.txt"),        # 基础语料
    os.path.join(_BASE_DIR, "user_corpus.txt"),       # 用户语料
]
FEEDBACK_FILE = os.path.join(_BASE_DIR, "correction_feedback.jsonl")
DEFAULT_OUTPUT = os.path.join(_BASE_DIR, "medical_3gram.pkl")

# 句子起始/结束标记
SENT_START = "<s>"
SENT_END = "</s>"


def load_corpus_lines(paths):
    """加载语料文件，返回句子列表"""
    lines = []
    for path in paths:
        if not os.path.exists(path):
            continue
        count = 0
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and len(line) >= 2:
                    lines.append(line)
                    count += 1
        print(f"  [语料] {os.path.basename(path)}: {count:,} 句")
    return lines


def load_feedback_corrections(path):
    """从纠错反馈中提取 accepted 的修正文本（作为正例语料）"""
    corrections = []
    if not os.path.exists(path):
        return corrections
    accepted = 0
    rejected = 0
    pending = 0
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
                status = rec.get("status", "pending")
                if status == "accepted":
                    accepted += 1
                    # 将修正后的词作为短语句加入语料
                    corrected = rec.get("corrected", "")
                    if corrected and len(corrected) >= 2:
                        corrections.append(corrected)
                elif status == "rejected":
                    rejected += 1
                    # 拒绝的：将原文作为正例（用户认为原文是对的）
                    original = rec.get("original", "")
                    if original and len(original) >= 2:
                        corrections.append(original)
                else:
                    pending += 1
            except json.JSONDecodeError:
                continue
    print(f"  [反馈] accepted={accepted}, rejected={rejected}, pending={pending}")
    print(f"  [反馈] 提取 {len(corrections)} 条短语作为补充语料")
    return corrections


def train_ngram(sentences, verbose=True):
    """
    训练字符级 3-gram 模型。

    Args:
        sentences: 句子列表（每个句子为一行文本）
    Returns:
        dict: {unigrams, bigrams, trigrams, total, vocab_size}
    """
    unigrams = Counter()
    bigrams = Counter()
    trigrams = Counter()

    t0 = time.time()
    for i, sent in enumerate(sentences):
        # 每个句子前加 <s>、后加 </s> 标记
        chars = [SENT_START] + list(sent) + [SENT_END]
        n = len(chars)

        for j in range(n):
            unigrams[chars[j]] += 1
            if j >= 1:
                bigrams[(chars[j-1], chars[j])] += 1
            if j >= 2:
                trigrams[(chars[j-2], chars[j-1], chars[j])] += 1

        if verbose and (i + 1) % 20000 == 0:
            print(f"    处理 {i+1:,}/{len(sentences):,} 句...")

    elapsed = time.time() - t0
    total = sum(unigrams.values())
    vocab_size = len(unigrams)

    if verbose:
        print(f"\n  训练完成 ({elapsed:.1f}s)")
        print(f"    总字符数: {total:,}")
        print(f"    词表大小: {vocab_size:,}")
        print(f"    一元组:   {len(unigrams):,}")
        print(f"    二元组:   {len(bigrams):,}")
        print(f"    三元组:   {len(trigrams):,}")

    return {
        "unigrams": dict(unigrams),
        "bigrams": dict(bigrams),
        "trigrams": dict(trigrams),
        "total": total,
        "vocab_size": vocab_size,
    }


def compare_models(old_path, new_model):
    """对比新旧模型差异"""
    if not os.path.exists(old_path):
        print("\n  [对比] 无旧模型，跳过")
        return
    try:
        with open(old_path, "rb") as f:
            old = pickle.load(f)
        # 结构校验：仅接受本工具生成的合法格式
        if not isinstance(old, dict) or "trigrams" not in old:
            print("\n  [对比] 旧模型格式无效，跳过")
            return
    except Exception:
        return

    old_tri = len(old.get("trigrams", {}))
    new_tri = len(new_model["trigrams"])
    old_total = old.get("total", 0)
    new_total = new_model["total"]

    print(f"\n  [对比] 旧模型 vs 新模型:")
    print(f"    总字符: {old_total:,} → {new_total:,} (+{new_total - old_total:,})")
    print(f"    三元组: {old_tri:,} → {new_tri:,} (+{new_tri - old_tri:,})")
    print(f"    词表:   {old.get('vocab_size', 0):,} → {new_model['vocab_size']:,}")


def main():
    parser = argparse.ArgumentParser(description="医学 3-gram 语言模型训练")
    parser.add_argument("-o", "--output", default=DEFAULT_OUTPUT,
                        help="输出模型路径 (默认: medical_3gram.pkl)")
    parser.add_argument("--stats", action="store_true",
                        help="仅显示语料统计，不训练")
    parser.add_argument("--dry-run", action="store_true",
                        help="模拟训练，显示增量但不写文件")
    args = parser.parse_args()

    print("=" * 60)
    print("  医学 3-gram 语言模型训练器")
    print("=" * 60)

    # 1. 加载语料
    print("\n[1/4] 加载语料...")
    sentences = load_corpus_lines(CORPUS_FILES)

    # 2. 加载纠错反馈
    print("\n[2/4] 加载纠错反馈...")
    feedback_phrases = load_feedback_corrections(FEEDBACK_FILE)
    sentences.extend(feedback_phrases)

    print(f"\n  合计语料: {len(sentences):,} 句/短语")

    if args.stats:
        # 仅统计模式
        print("\n[统计模式] 不执行训练")
        if os.path.exists(DEFAULT_OUTPUT):
            with open(DEFAULT_OUTPUT, "rb") as f:
                old = pickle.load(f)
            print(f"\n  当前模型:")
            print(f"    三元组: {len(old['trigrams']):,}")
            print(f"    词表:   {old['vocab_size']:,}")
            print(f"    总字符: {old['total']:,}")
        return

    # 3. 训练
    print("\n[3/4] 训练 3-gram 模型...")
    model = train_ngram(sentences)

    # 对比旧模型
    compare_models(DEFAULT_OUTPUT, model)

    if args.dry_run:
        print("\n[dry-run] 不写入文件")
        return

    # 4. 保存
    print(f"\n[4/4] 保存模型 → {args.output}")
    # 备份旧模型
    if os.path.exists(args.output):
        backup = args.output + ".bak"
        os.replace(args.output, backup)
        print(f"  旧模型已备份: {os.path.basename(backup)}")

    with open(args.output, "wb") as f:
        pickle.dump(model, f, protocol=pickle.HIGHEST_PROTOCOL)

    file_size = os.path.getsize(args.output) / 1024 / 1024
    print(f"  模型大小: {file_size:.1f} MB")

    # 5. 同步更新混淆对纠错表（从反馈数据提取高频误识别对）
    print("\n[5/5] 更新 ASR 混淆对纠错表...")
    try:
        from asr_engine import ASREngine
        pairs = ASREngine.extract_confusion_pairs(min_count=3)
        print(f"  混淆对: {len(pairs)} 对")
    except Exception as e:
        print(f"  混淆对提取失败: {e}")

    print("\n✅ 训练完成！重启程序后新模型即生效。")


if __name__ == "__main__":
    main()
