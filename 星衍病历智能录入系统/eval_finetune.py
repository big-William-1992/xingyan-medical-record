#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
微调效果评测：对比原始模型 vs 微调模型
指标: CER（字符错误率）+ 字段关键词命中率
"""
import os
import sys
import random

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "finetune_data")
CKPT = os.path.join(BASE_DIR, "finetune_ckpt", "paraformer_medical.pt")

FIELD_TERMS = ["现病史", "家族史", "民族", "婚育史", "既往史", "主诉", "个人史", "体格检查", "辅助检查", "初步诊断"]

def log(msg):
    print(msg, flush=True)


def load_dev():
    wav_map, texts = {}, {}
    with open(os.path.join(DATA_DIR, "wav.scp"), encoding="utf-8") as f:
        for line in f:
            p = line.strip().split(maxsplit=1)
            if len(p) == 2: wav_map[p[0]] = p[1]
    with open(os.path.join(DATA_DIR, "text.txt"), encoding="utf-8") as f:
        for line in f:
            p = line.strip().split(maxsplit=1)
            if len(p) == 2: texts[p[0]] = p[1]
    pairs = [(wav_map[k], texts[k]) for k in wav_map if k in texts]
    random.seed(42)
    random.shuffle(pairs)
    return pairs[:50]  # 取50条评测（与训练切分一致的前50条≈dev）


def cer(ref, hyp):
    """字符错误率（编辑距离）"""
    ref, hyp = list(ref), list(hyp)
    n, m = len(ref), len(hyp)
    dp = list(range(m + 1))
    for i in range(1, n + 1):
        prev, dp[0] = dp[0], i
        for j in range(1, m + 1):
            cur = dp[j]
            dp[j] = min(dp[j] + 1, dp[j - 1] + 1, prev + (ref[i - 1] != hyp[j - 1]))
            prev = cur
    return dp[m] / max(n, 1)


def evaluate(model, samples, name):
    cers, term_hit, term_total = [], 0, 0
    for wav_path, ref in samples:
        ref_clean = ref.replace(" ", "")
        try:
            res = model.generate(input=wav_path)
            hyp = res[0]["text"].replace(" ", "")
        except Exception as e:
            hyp = ""
        cers.append(cer(ref_clean, hyp))
        # 字段关键词命中
        for t in FIELD_TERMS:
            if t in ref_clean:
                term_total += 1
                if t in hyp:
                    term_hit += 1
    avg_cer = sum(cers) / len(cers)
    log(f"[{name}] CER: {avg_cer*100:.2f}% | 字段关键词命中: {term_hit}/{term_total} ({term_hit*100//max(term_total,1)}%)")
    return avg_cer


def main():
    from funasr import AutoModel
    samples = load_dev()
    log(f"评测样本: {len(samples)} 条")

    log("\n── 原始模型 ──")
    m_base = AutoModel(model="paraformer-zh", disable_update=True)
    base_cer = evaluate(m_base, samples, "原始模型")
    del m_base

    log("\n── 微调模型 ──")
    m_ft = AutoModel(model="paraformer-zh", init_param=CKPT, disable_update=True)
    ft_cer = evaluate(m_ft, samples, "微调模型")

    log("\n═══ 结论 ═══")
    if ft_cer < base_cer:
        log(f"✅ 微调有效: CER {base_cer*100:.2f}% → {ft_cer*100:.2f}% (降低 {(base_cer-ft_cer)*100:.2f} 个百分点)")
    else:
        log(f"⚠️ 微调未见提升: CER {base_cer*100:.2f}% → {ft_cer*100:.2f}%")


if __name__ == "__main__":
    main()
