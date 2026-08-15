# 模型自动下载功能说明

## 概述

系统现已支持**首次启动自动下载模型**功能，无需手动操作！

## 工作原理

### 启动流程

```
1. 启动程序
   ↓
2. 检测模型是否存在（~/.cache/modelscope/hub/）
   ↓
3. 如果不存在 → 自动下载（约 1GB）
   ↓
4. 下载完成 → 自动加载模型
   ↓
5. 语音识别就绪 ✅
```

### 下载的模型

系统会自动下载以下 3 个模型：

| 模型 | 用途 | 大小 |
|------|------|------|
| **paraformer-zh** | 语音识别主模型 | ~880MB |
| **fsmn-vad** | 语音活动检测 | ~60MB |
| **ct-punc** | 标点恢复 | ~1GB |

**总大小**: 约 2GB  
**下载时间**: 5-15 分钟（取决于网速）

### 存储位置

模型下载到用户目录：
```
~/.cache/modelscope/hub/
├── paraformer-zh/
├── fsmn-vad/
└── ct-punc/
```

## 使用方式

### 方式一：开发模式

```bash
cd 星衍病历智能录入系统
source venv/bin/activate
python app_server.py
```

首次启动时会自动下载模型：
```
[ASR] 模型不存在，开始自动下载...
[ASR] 📥 开始下载语音识别模型（约 1GB）...
[ASR] 这可能需要几分钟，请耐心等待...
[ASR] [1/3] 下载 paraformer-zh...
[ASR] ✅ paraformer-zh 下载完成
[ASR] [2/3] 下载 fsmn-vad...
[ASR] ✅ fsmn-vad 下载完成
[ASR] [3/3] 下载 ct-punc...
[ASR] ✅ ct-punc 下载完成
[ASR] ✅ 所有模型下载完成！
[ASR] ✅ 模型加载成功
```

### 方式二：打包后使用

```bash
# 打包
bash build.sh

# 运行
./dist/星衍AI-Web服务/星衍AI-Web服务
```

首次运行会自动下载模型，后续启动直接使用。

## 常见问题

### Q1: 下载失败怎么办？

**原因**: 网络问题或 modelscope 服务不可用

**解决**:
```bash
# 手动安装 modelscope
pip install modelscope

# 手动下载模型
python -c "from modelscope import snapshot_download; snapshot_download('iic/speech_paraformer-large_asr_nat-zh-cn-16k-common-vocab8404-pytorch')"
python -c "from modelscope import snapshot_download; snapshot_download('iic/speech_fsmn_vad_zh-cn-16k-common-pytorch')"
python -c "from modelscope import snapshot_download; snapshot_download('iic/punc_ct-transformer_cn-en-common-vocab471067-large')"
```

### Q2: 模型下载后还是无法使用？

**检查**:
```bash
# 查看模型目录
ls ~/.cache/modelscope/hub/

# 应该看到：
# paraformer-zh/
# fsmn-vad/
# ct-punc/
```

如果目录不存在，说明下载失败，重新运行程序。

### Q3: 如何更换模型存储位置？

设置环境变量：
```bash
export MODELSCOPE_CACHE=/path/to/custom/cache
python app_server.py
```

### Q4: 下载太慢怎么办？

**方案1**: 使用代理
```bash
export HTTP_PROXY=http://proxy:port
export HTTPS_PROXY=http://proxy:port
python app_server.py
```

**方案2**: 手动下载后复制
从其他电脑下载模型，复制到 `~/.cache/modelscope/hub/` 目录。

### Q5: 如何删除模型重新下载？

```bash
# 删除模型缓存
rm -rf ~/.cache/modelscope/hub/

# 重新启动程序，会自动重新下载
python app_server.py
```

## 技术细节

### 代码实现

**asr_engine.py**:
```python
def _check_model_exists(self):
    """检查模型文件是否已下载"""
    cache_dir = os.path.expanduser("~/.cache/modelscope/hub")
    models = ["paraformer-zh", "fsmn-vad", "ct-punc"]
    
    for model_name in models:
        model_path = os.path.join(cache_dir, model_name)
        if not os.path.exists(model_path):
            return False
    return True

def _download_models(self):
    """自动下载 FunASR 模型"""
    from modelscope import snapshot_download
    
    models = [
        ("paraformer-zh", "iic/speech_paraformer-large_asr_nat-zh-cn-16k-common-vocab8404-pytorch"),
        ("fsmn-vad", "iic/speech_fsmn_vad_zh-cn-16k-common-pytorch"),
        ("ct-punc", "iic/punc_ct-transformer_cn-en-common-vocab471067-large"),
    ]
    
    for model_name, model_id in models:
        snapshot_download(model_id, cache_dir=os.path.expanduser("~/.cache/modelscope/hub"))
```

### 依赖

**requirements.txt**:
```txt
funasr>=1.0.0
modelscope>=1.9.0  # 模型自动下载
torch>=2.0.0
torchaudio>=2.0.0
```

## 用户体验优化

### 进度显示

下载过程中会实时显示进度：
```
[ASR] [1/3] 下载 paraformer-zh...
Downloading: 100%|████████████████████| 10/10 [05:23<00:00, 32.3s/file]
[ASR] ✅ paraformer-zh 下载完成
```

### 错误处理

如果下载失败，会给出明确提示：
```
[ASR] ❌ paraformer-zh 下载失败: Connection timeout
[ASR] ❌ 模型下载失败，语音识别功能不可用
[ASR] 请检查网络连接后重试
```

## 总结

✅ **零配置**: 首次启动自动下载，无需手动操作  
✅ **智能检测**: 只在模型不存在时下载  
✅ **进度可见**: 实时显示下载进度  
✅ **错误友好**: 下载失败时给出明确提示  
✅ **跨平台**: 支持 macOS/Linux/Windows  

现在你可以直接运行程序，系统会自动处理模型下载！🎉
