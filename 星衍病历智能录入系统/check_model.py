#!/usr/bin/env python3
"""
模型目录校验脚本 - 检查 FunASR 三个模型是否已正确就位
用法：
  Windows: 双击运行（前提是已安装 Python）
  命令行: python check_model.py

校验通过：启动软件即可使用语音识别
校验失败：按提示下载或解压离线模型包
"""
import os
import sys
import platform

# 三个模型的关键子目录（iic/<模型名>）
REQUIRED_MODELS = [
    ("speech_seaco_paraformer", "Paraformer-zh 语音识别主模型"),
    ("speech_fsmn_vad",       "FSMN-VAD 语音活动检测"),
    ("punc_ct_transformer",   "CT-Punc 标点恢复"),
]


def get_cache_dir():
    """返回 modelscope 模型缓存根目录"""
    if platform.system() == "Windows":
        base = os.environ.get("USERPROFILE") or os.path.expanduser("~")
        return os.path.join(base, ".cache", "modelscope", "models")
    return os.path.join(os.path.expanduser("~"), ".cache", "modelscope", "models")


def find_model_dir(cache_dir, keyword):
    """在 cache_dir/iic/ 下查找以 keyword 开头的目录"""
    iic_dir = os.path.join(cache_dir, "iic")
    if not os.path.isdir(iic_dir):
        return None
    for name in os.listdir(iic_dir):
        if name.startswith(keyword):
            full = os.path.join(iic_dir, name)
            if os.path.isdir(full):
                return full
    return None


def main():
    cache_dir = get_cache_dir()
    print("=" * 60)
    print("  星衍病历录入系统 - 模型目录校验")
    print("=" * 60)
    print(f"模型缓存目录：{cache_dir}")
    print()

    missing = []
    for keyword, desc in REQUIRED_MODELS:
        path = find_model_dir(cache_dir, keyword)
        if path:
            # 粗略检查：目录下至少有文件
            try:
                n = len(os.listdir(path))
                print(f"  ✅ {desc}")
                print(f"     → {path}（{n} 个文件/目录）")
            except Exception as e:
                print(f"  ⚠️  {desc}")
                print(f"     → 目录存在但无法读取：{e}")
                missing.append((keyword, desc))
        else:
            print(f"  ❌ {desc}")
            print(f"     → 未找到（关键字：{keyword}）")
            missing.append((keyword, desc))
        print()

    print("-" * 60)
    if not missing:
        print("🎉 全部模型就位，可以启动软件使用语音识别！")
        print("   启动方式：双击 启动.bat（Windows）或 bash 启动.sh（macOS/Linux）")
        return 0
    else:
        print(f"⚠️  缺少 {len(missing)} 个模型，语音识别无法正常工作。\n")
        print("修复方法（任选其一）：")
        print()
        print("【方法 1】联网自动下载（首次启动时）")
        print("   直接运行软件，FunASR 会自动从 ModelScope 下载缺失模型。")
        print()
        print("【方法 2】离线整包部署（无网络环境）")
        print("   1. 访问 https://github.com/big-William-1992/xingyan-medical-record/releases")
        print("   2. 下载 asr-paraformer.zip / asr-vad.zip / asr-punc.zip")
        print("   3. 解压到以下目录：")
        print(f"      {cache_dir}")
        print("   4. 解压后应形成 <缓存目录>/iic/speech_seaco_paraformer.../ 等结构")
        print()
        print("【方法 3】手动下载单个模型")
        print("   pip install modelscope")
        for keyword, desc in missing:
            if "paraformer" in keyword:
                print("   modelscope download --model iic/speech_seaco_paraformer_large_asr_nat-zh-cn-16k-common-vocab8404-pytorch")
            elif "vad" in keyword:
                print("   modelscope download --model iic/speech_fsmn_vad_zh-cn-16k-common-pytorch")
            elif "transformer" in keyword:
                print("   modelscope download --model iic/punc_ct-transformer_cn-en-common-vocab471067-large")
        return 1


if __name__ == "__main__":
    code = main()
    print()
    input("按回车键退出...")
    sys.exit(code)
