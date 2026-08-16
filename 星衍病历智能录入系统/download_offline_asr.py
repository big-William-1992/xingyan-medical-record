#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sherpa-onnx 离线语音识别资源下载脚本
下载 WASM 引擎 + 中文流式模型到 frontend/wasm/ 目录

用法：
    python download_offline_asr.py            # 直连（需能访问 huggingface.co）
    python download_offline_asr.py --mirror   # 镜像（国内网络推荐，hf-mirror.com）

下载内容（sherpa-onnx-wasm-asr-1pass.zip，约 230MB）：
- sherpa-onnx-wasm-main-asr.js / .wasm  — WASM 引擎
- sherpa-onnx-wasm-main-asr.data         — Zipformer 中文流式模型（含 VAD + 标点）
- sherpa-onnx-asr.js / sherpa-onnx-vad.js — ASR/VAD API
- offline-worker.js / sense-voice-ort-worker.js — Worker

依赖：无（纯 urllib + zipfile）
"""
import os
import sys
import zipfile
import urllib.request

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WASM_DIR = os.path.join(BASE_DIR, "frontend", "wasm")

# 模型包（含引擎 + 模型 + VAD + 标点，官方 wasm 演示部署包）
HF_REPO = "anyshu/sherpa-onnx-wasm-main-asr.data"
MODEL_FILE = "sherpa-onnx-wasm-asr-1pass.zip"
MODEL_URL = f"https://huggingface.co/{HF_REPO}/resolve/main/{MODEL_FILE}"
MIRROR_URL = f"https://hf-mirror.com/{HF_REPO}/resolve/main/{MODEL_FILE}"

# 解压后需要保留的文件
REQUIRED = [
    "sherpa-onnx-wasm-main-asr.js",
    "sherpa-onnx-wasm-main-asr.wasm",
    "sherpa-onnx-wasm-main-asr.data",
    "sherpa-onnx-asr.js",
    "sherpa-onnx-vad.js",
]


def download(url, dest, timeout=600):
    """下载文件（带进度与重试）"""
    if os.path.exists(dest) and os.path.getsize(dest) > 1000000:
        print(f"  ✓ 已存在: {os.path.basename(dest)} ({os.path.getsize(dest)//1024//1024}MB)")
        return True

    for attempt in range(1, 4):
        try:
            print(f"  ⏳ 下载模型包 ({'镜像' if 'hf-mirror' in url else '直连'}, 尝试{attempt}/3)...")
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=timeout) as resp, open(dest, "wb") as f:
                total = int(resp.headers.get("Content-Length", 0))
                downloaded = 0
                while True:
                    chunk = resp.read(65536)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total:
                        pct = downloaded * 100 // total
                        mb = downloaded // 1024 // 1024
                        print(f"\r    {pct}% ({mb}MB/{total//1024//1024}MB)", end="")
                        sys.stdout.flush()
            print(f"\n  ✅ 下载完成 ({os.path.getsize(dest)//1024//1024}MB)")
            return True
        except Exception as e:
            print(f"  ❌ 失败: {e}")
            if os.path.exists(dest):
                os.remove(dest)
    return False


def extract_models(zip_path):
    """解压模型包到 frontend/wasm/model-1pass/"""
    out_dir = os.path.join(WASM_DIR, "model-1pass")
    os.makedirs(out_dir, exist_ok=True)

    try:
        print("  解压模型包...")
        with zipfile.ZipFile(zip_path, "r") as zf:
            for member in zf.namelist():
                # 跳过目录项
                if member.endswith("/"):
                    continue
                name = os.path.basename(member)
                if name in REQUIRED or name in ("offline-worker.js", "sense-voice-ort-worker.js"):
                    data = zf.read(member)
                    with open(os.path.join(out_dir, name), "wb") as f:
                        f.write(data)
                    print(f"  ✅ {name} ({len(data)//1024//1024}MB)")
        os.remove(zip_path)
        return True
    except Exception as e:
        print(f"  ❌ 解压失败: {e}")
        return False


def verify():
    """校验文件完整性"""
    out_dir = os.path.join(WASM_DIR, "model-1pass")
    ok = True
    print("\n文件校验:")
    for name in REQUIRED:
        path = os.path.join(out_dir, name)
        size = os.path.getsize(path) if os.path.exists(path) else 0
        status = "✅" if size > 1000 else "❌"
        print(f"  {status} {name} ({size//1024//1024}MB)")
        if size <= 1000:
            ok = False
    return ok


def main():
    mirror = "--mirror" in sys.argv
    os.makedirs(WASM_DIR, exist_ok=True)
    print("=" * 56)
    print(f"下载 sherpa-onnx 离线语音识别资源（{'镜像' if mirror else '直连'}）")
    print(f"来源: {'hf-mirror.com' if mirror else 'huggingface.co'}")
    print(f"输出: {WASM_DIR}/model-1pass/")
    print("=" * 56)

    url = MIRROR_URL if mirror else MODEL_URL
    zip_path = os.path.join(WASM_DIR, MODEL_FILE)

    if download(url, zip_path):
        if extract_models(zip_path) and verify():
            print("\n" + "=" * 56)
            print("✅ 全部就绪！离线语音识别已可用。")
            print("=" * 56)
        else:
            print("\n⚠️ 解压或校验失败，请重试")
    else:
        print("\n⚠️ 下载失败，请检查网络后重试：")
        print("   python download_offline_asr.py --mirror")


if __name__ == "__main__":
    main()
