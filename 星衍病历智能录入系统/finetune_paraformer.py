#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Paraformer-large 本地微调脚本（最小化实现）
数据: finetune_data/wav.scp + text.txt
支持 MPS(Apple Silicon) / CPU
用法:
  python finetune_paraformer.py probe      # 10步速度探针
  python finetune_paraformer.py train      # 完整训练(1 epoch)
"""
import os
import sys
import time
import random
import wave
import numpy as np
import torch
from torch.utils.data import Dataset, DataLoader
from funasr.utils.load_utils import extract_fbank

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "finetune_data")
CKPT_DIR = os.path.join(BASE_DIR, "finetune_ckpt")
os.makedirs(CKPT_DIR, exist_ok=True)

BATCH_SIZE = 4          # MPS 内存有限，小 batch
LEARNING_RATE = 5e-6    # 更小的学习率防过拟合/遗忘
MAX_AUDIO_SEC = 15      # 跳过超长音频
LOG_EVERY = 20
SEACO_ID = 8377         # 官方 config.yaml 中的 seaco_id

def log(msg):
    print(msg, flush=True)


def load_pairs():
    """读取 wav.scp + text.txt，切分 train/dev，并对高频模板尾句降采样防幻觉"""
    wav_map = {}
    with open(os.path.join(DATA_DIR, "wav.scp"), encoding="utf-8") as f:
        for line in f:
            parts = line.strip().split(maxsplit=1)
            if len(parts) == 2:
                wav_map[parts[0]] = parts[1]
    texts = {}
    with open(os.path.join(DATA_DIR, "text.txt"), encoding="utf-8") as f:
        for line in f:
            parts = line.strip().split(maxsplit=1)
            if len(parts) == 2:
                texts[parts[0]] = parts[1]
    pairs = [(wav_map[k], texts[k]) for k in wav_map if k in texts]
    random.seed(42)
    random.shuffle(pairs)
    # 降采样：高频模板短语占比上限 5%，防止模型过度记忆产生幻觉
    HALLU_PHRASES = ["为求进一步诊治来我院"]
    MAX_PHRASE_COUNT = len(pairs) * 5 // 100
    phrase_cnt = {p: 0 for p in HALLU_PHRASES}
    balanced = []
    for wav, text in pairs:
        keep = True
        for p in HALLU_PHRASES:
            if p in text:
                if phrase_cnt[p] >= MAX_PHRASE_COUNT:
                    keep = False
                else:
                    phrase_cnt[p] += 1
        if keep:
            balanced.append((wav, text))
    log(f"降采样: {len(pairs)} → {len(balanced)} 条 (高频尾句限 {MAX_PHRASE_COUNT} 条)")
    pairs = balanced
    n_dev = max(50, len(pairs) // 25)
    return pairs[n_dev:], pairs[:n_dev]


def read_wav(path):
    """读取 16k mono wav -> float32 numpy"""
    with wave.open(path) as w:
        n = w.getnframes()
        raw = w.readframes(n)
        rate = w.getframerate()
    audio = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    return audio, rate


class MedicalASRDataset(Dataset):
    def __init__(self, pairs, tokenizer, frontend):
        self.items = []
        self.tokenizer = tokenizer
        self.frontend = frontend
        skipped = 0
        for wav_path, text in pairs:
            if not os.path.exists(wav_path):
                skipped += 1
                continue
            try:
                audio, rate = read_wav(wav_path)
                if rate != 16000 or len(audio) > MAX_AUDIO_SEC * 16000 or len(audio) < 1600:
                    skipped += 1
                    continue
                # 官方流程：text 不加 sos/eos（模型内部 predictor_bias=1 自动加）
                ids = tokenizer.tokens2ids([c for c in text if c != " "])
                if not ids:
                    skipped += 1
                    continue
                self.items.append((wav_path, np.array(ids, dtype=np.int64)))
            except Exception:
                skipped += 1
        log(f"数据集: 有效 {len(self.items)} 条, 跳过 {skipped} 条")

    def __len__(self):
        return len(self.items)

    def __getitem__(self, idx):
        wav_path, ids = self.items[idx]
        audio, _ = read_wav(wav_path)
        audio_t = torch.from_numpy(audio).unsqueeze(0)  # [1, T]
        feats, feats_len = extract_fbank(audio_t, data_type="sound",
                                         frontend=self.frontend, is_final=True)
        # feats: [1, T', d]
        return feats[0], torch.from_numpy(ids)


def sample_hotword_indx(length):
    """复刻官方 AudioDatasetHotword.generate_index 的热词采样"""
    hw_min, hw_max, sample_rate, double_rate = 2, 8, 0.75, 0.1
    if length < hw_min:
        return [-1]
    if random.random() >= sample_rate:
        return [-1]
    if length == hw_min:
        return [0, length - 1]
    if random.random() < double_rate and length > hw_max + hw_min + 2:
        _max_hw = min(hw_max, length // 2)
        s1 = random.randint(0, length // 3)
        e1 = random.randint(s1 + hw_min - 1, s1 + _max_hw - 1)
        s2 = random.randint(e1 + 1, length - hw_min)
        e2 = random.randint(min(length - 1, s2 + hw_min - 1), min(length - 1, s2 + hw_max - 1))
        return [s1, e1, s2, e2]
    start = random.randint(0, length - hw_min)
    end = random.randint(min(length - 1, start + hw_min - 1), min(length - 1, start + hw_max - 1))
    return [start, end]


def collate_fn(batch):
    """复刻官方 AudioDatasetHotword.collator"""
    feats_list, texts = zip(*batch)
    B = len(batch)
    # speech: fbank 特征 pad 0
    f_len = [f.shape[0] for f in feats_list]
    speech = torch.zeros(B, max(f_len), feats_list[0].shape[1])
    for i, f in enumerate(feats_list):
        speech[i, :f.shape[0]] = f
    a_len = f_len
    # text: pad -1（与官方 int_pad_value 一致）
    t_len = [len(t) for t in texts]
    text = torch.full((B, max(t_len)), -1, dtype=torch.long)
    for i, t in enumerate(texts):
        text[i, :len(t)] = t
    # 热词采样 + seaco 标签
    seaco_label_pad = torch.full((B, max(t_len)), -1, dtype=torch.long)
    hotword_list, hotword_lengths = [], []
    for b in range(B):
        L = t_len[b]
        seaco_label_pad[b][:L] = SEACO_ID
        indx = sample_hotword_indx(L)
        if indx[0] != -1:
            s, e = indx[0], indx[1]
            hotword_list.append(text[b][s:e + 1])
            hotword_lengths.append(e - s + 1)
            seaco_label_pad[b][s:e + 1] = text[b][s:e + 1]
            if len(indx) == 4 and indx[2] != -1:
                s2, e2 = indx[2], indx[3]
                hotword_list.append(text[b][s2:e2 + 1])
                hotword_lengths.append(e2 - s2 + 1)
                seaco_label_pad[b][s2:e2 + 1] = text[b][s2:e2 + 1]
    hotword_list.append(torch.tensor([1], dtype=torch.long))  # 哨兵热词
    hotword_lengths.append(1)
    hotword_pad = torch.nn.utils.rnn.pad_sequence(hotword_list, batch_first=True, padding_value=0)
    return {
        "speech": speech,
        "speech_lengths": torch.tensor(a_len, dtype=torch.long),
        "text": text,
        "text_lengths": torch.tensor(t_len, dtype=torch.int32),
        "hotword_pad": hotword_pad,
        "hotword_lengths": torch.tensor(hotword_lengths, dtype=torch.int32),
        "seaco_label_pad": seaco_label_pad,
    }


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "probe"
    device = torch.device("mps" if torch.backends.mps.is_available() else "cpu")
    log(f"设备: {device}")

    from funasr import AutoModel
    t0 = time.time()
    m = AutoModel(model="paraformer-zh", disable_update=True)
    model = m.model
    tokenizer = m.kwargs["tokenizer"]
    log(f"模型加载: {time.time()-t0:.1f}s | vocab: {len(m.kwargs['token_list'])}")

    # frontend 仅用于数据集提特征；model.frontend 保持 None（官方训练时模型直接收 fbank）
    frontend = m.kwargs.get("frontend")
    model.frontend = None
    if getattr(model, "specaug", None) is None:
        model.specaug = m.kwargs.get("specaug")

    train_pairs, dev_pairs = load_pairs()
    log(f"训练集: {len(train_pairs)} | 验证集: {len(dev_pairs)}")

    if mode == "probe":
        train_pairs = train_pairs[:64]  # 探针只用64条
    dataset = MedicalASRDataset(train_pairs, tokenizer, frontend)
    loader = DataLoader(dataset, batch_size=BATCH_SIZE, shuffle=True,
                        collate_fn=collate_fn, num_workers=0)

    model.to(device)
    model.train()
    optimizer = torch.optim.AdamW(model.parameters(), lr=LEARNING_RATE)

    max_steps = 10 if mode == "probe" else 10**9
    step = 0
    t_start = time.time()
    loss_sum, loss_n = 0.0, 0
    for batch in loader:
        batch = {k: v.to(device) for k, v in batch.items()}
        out = model(**batch)
        loss = out[0] if isinstance(out, (tuple, list)) else out
        optimizer.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 5.0)
        optimizer.step()
        loss_sum += loss.item()
        loss_n += 1
        step += 1
        if step % LOG_EVERY == 0 or mode == "probe":
            elapsed = time.time() - t_start
            log(f"step {step} | loss {loss_sum/loss_n:.3f} | {elapsed/step:.1f}s/step")
        # 每 200 步定期保存，防崩溃丢失
        if mode == "train" and step % 200 == 0:
            torch.save(model.state_dict(), os.path.join(CKPT_DIR, "paraformer_medical_latest.pt"))
        if step >= max_steps:
            break

    elapsed = time.time() - t_start
    log(f"\n{'探针' if mode=='probe' else '训练'}完成: {step} 步, 平均 {elapsed/step:.2f}s/step, loss {loss_sum/max(loss_n,1):.3f}")
    if mode == "probe":
        total_steps_full = len(load_pairs()[0]) // BATCH_SIZE
        est = total_steps_full * elapsed / step / 3600
        log(f"全量1 epoch 预计: {total_steps_full} 步 ≈ {est:.1f} 小时")
    else:
        ckpt = os.path.join(CKPT_DIR, "paraformer_medical.pt")
        torch.save(model.state_dict(), ckpt)
        log(f"模型已保存: {ckpt}")


if __name__ == "__main__":
    main()
