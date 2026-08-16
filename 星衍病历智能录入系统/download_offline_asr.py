#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sherpa-onnx 离线语音识别模型下载脚本
下载 WASM 引擎 + 中文流式模型到 frontend/wasm/ 目录

用法：
    python download_offline_asr.py            # 默认（GitHub 直连）
    python download_offline_asr.py --mirror   # 使用镜像源（国内网络推荐）

依赖：无（纯 urllib）
"""
import os
import sys
import tarfile
import urllib.request

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WASM_DIR = os.path.join(BASE_DIR, "frontend", "wasm")

# ─── 下载源配置 ───
# 国内网络建议 --mirror：GitHub 用 ghproxy 代理，HuggingFace 用 hf-mirror
GH_MIRROR = "https://ghproxy.com/"
HF_MIRROR = "https://hf-mirror.com"

# 1) sherpa-onnx WASM 引擎（npm 包内包含 sherpa-onnx-wasm.js / .wasm）
#    也可手动从 npm 安装：npm install sherpa-onnx-wasm 后复制文件
WASM_FILES = {
    "sherpa-onnx-wasm.js": "https://unpkg.com/sherpa-onnx-wasm@1.10.36/sherpa-onnx-wasm.js",
    "sherpa-onnx-wasm.wasm": "https://unpkg.com/sherpa-onnx-wasm@1.10.36/sherpa-onnx-wasm.wasm",
}

# 2) 中文流式 Zipformer 模型（14M，文件名为 encoder.onnx/decoder.onnx/joiner.onnx/tokens.txt）
MODEL_TARBALL = "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/sherpa-onnx-streaming-zipformer-zh-14M-2023-02-20.tar.bz2"
MODEL_SUBDIR = "sherpa-onnx-streaming-zipformer-zh-14M-2023-02-20"


def _mirror_url(url):
    """转换为镜像 URL"""
    if url.startswith("https://github.com/"):
        return GH_MIRROR + url
    if url.startswith("https://huggingface.co/"):
        return url.replace("https://huggingface.co/", HF_MIRROR + "/")
    return url


def download(url, dest, mirror=False):
    """下载文件（带进度与重试）"""
    if os.path.exists(dest) and os.path.getsize(dest) > 1000:
        print(f"  ✓ 已存在: {os.path.basename(dest)} ({os.path.getsize(dest)//1024}KB)")
        return True

    real_url = _mirror_url(url) if mirror else url
    for attempt in range(1, 4):
        try:
            print(f"  ⏳ {os.path.basename(dest)} ... ({'镜像' if mirror else '直连'}, 尝试{attempt}/3)")
            req = urllib.request.Request(real_url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=120) as resp, open(dest, "wb") as f:
                while True:
                    chunk = resp.read(65536)
                    if not chunk:
                        break
                    f.write(chunk)
            print(f"  ✅ {os.path.basename(dest)} ({os.path.getsize(dest)//1024}KB)")
            return True
        except Exception as e:
            print(f"  ❌ 失败: {e}")
            if os.path.exists(dest):
                os.remove(dest)
    return False


def main():
    mirror = "--mirror" in sys.argv
    os.makedirs(WASM_DIR, exist_ok=True)
    print("=" * 56)
    print(f"下载 sherpa-onnx 离线语音识别资源（{'镜像模式' if mirror else '直连模式'}）")
    print(f"输出目录: {WASM_DIR}")
    print("=" * 56)

    ok = True

    # 1. WASM 引擎（js + wasm）
    print("\n[1/3] sherpa-onnx WASM 引擎")
    for name, url in WASM_FILES.items():
        ok &= download(url, os.path.join(WASM_DIR, name), mirror)

    # 2. 中文流式模型（tar.bz2 压缩包）
    print("\n[2/3] 中文流式 Zipformer 模型")
    tarball = os.path.join(WASM_DIR, "model.tar.bz2")
    if download(MODEL_TARBALL, tarball, mirror):
        try:
            print("  解压模型...")
            with tarfile.open(tarball, "r:bz2") as tf:
                for member in tf.getmembers():
                    # 只提取模型文件到 wasm 根目录
                    name = os.path.basename(member.name)
                    if name in ("encoder.onnx", "decoder.onnx", "joiner.onnx", "tokens.txt"):
                        f = tf.extractfile(member)
                        if f:
                            with open(os.path.join(WASM_DIR, name), "wb") as out:
                                out.write(f.read())
                            print(f"  ✅ {name}")
            os.remove(tarball)
        except Exception as e:
            print(f"  ❌ 解压失败: {e}")
            ok = False
    else:
        ok = False

    # 3. 校验
    print("\n[3/3] 文件校验")
    required = ["sherpa-onnx-wasm.js", "sherpa-onnx-wasm.wasm",
                "encoder.onnx", "decoder.onnx", "joiner.onnx", "tokens.txt"]
    for name in required:
        path = os.path.join(WASM_DIR, name)
        size = os.path.getsize(path) if os.path.exists(path) else 0
        status = "✅" if size > 1000 else "❌"
        print(f"  {status} {name} ({size//1024}KB)")
        if size <= 1000:
            ok = False

    print("\n" + "=" * 56)
    if ok:
        print("✅ 全部就绪！离线语音识别已可用。")
    else:
        print("⚠️ 部分文件缺失，请检查网络后重试：")
        print("   python download_offline_asr.py --mirror")
        print("   或手动下载模型放入 frontend/wasm/ 目录")
    print("=" * 56)


if __name__ == "__main__":
    main()
