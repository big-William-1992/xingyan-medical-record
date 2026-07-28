# 星衍AI智能病历录入系统 v2.0

**内外科专版 — 离线语音识别 + 常见病模板 + 语音一键替换**

- 纯本地运行，无需联网（模型首次需下载）
- 基于 FunASR Paraformer 离线语音识别引擎（中文最优）
- 内置医疗词库 + 双层热词增强 + 三级纠错架构
- 内外科 11 个常见病模板，语音输入核心信息一键替换
- 支持内科/外科/影像科模板管理

> 📦 **离线环境 / 首次下载太慢？** 看 [离线整包部署（GitHub Releases）](#离线整包部署github-releases) 章节，下载预打包模型压缩包，解压即用。

---

## 环境要求

- macOS / Windows / Linux
- Python 3.8 或更高版本（推荐 3.11）
- 麦克风（普通耳麦即可）
- 磁盘空间：约 3GB（模型 + 依赖）

---

## 安装步骤

### 第一步：安装 Python

如果还没装 Python：
1. 访问 https://www.python.org/downloads/
2. 下载 Python 3.8+（推荐 3.11）
3. Windows 安装时勾选 **"Add Python to PATH"**

### 第二步：创建虚拟环境并安装依赖

```bash
cd 星衍病历智能录入系统

# 创建虚拟环境
python3 -m venv venv

# 激活虚拟环境
# macOS/Linux:
source venv/bin/activate
# Windows:
venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt
```

> **说明**：`venv/` 目录约 1.4GB，包含 PyQt5、FunASR、ModelScope 等依赖。
> 该目录不纳入 Git 版本管理，每台机器需独立创建。

### 第三步：下载语音识别模型（约 2GB）

系统使用 FunASR 框架，**首次运行时会自动下载模型**，无需手动操作。

> 💡 **不确定模型是否就位？** 双击运行 `校验模型.bat`（Windows）或 `python check_model.py`（macOS/Linux），会自动检测 3 个模型并给出修复建议。

如需手动下载或离线部署，模型来源如下：

| 模型 | ModelScope 地址 | 大小 | 用途 |
|------|-----------------|------|------|
| Paraformer-zh | [iic/speech_seaco_paraformer_large_asr_nat-zh-cn-16k-common-vocab8404-pytorch](https://modelscope.cn/models/iic/speech_seaco_paraformer_large_asr_nat-zh-cn-16k-common-vocab8404-pytorch) | ~953MB | 语音识别主模型 |
| FSMN-VAD | [iic/speech_fsmn_vad_zh-cn-16k-common-pytorch](https://modelscope.cn/models/iic/speech_fsmn_vad_zh-cn-16k-common-pytorch) | ~4MB | 语音活动检测（自动断句） |
| CT-Punc | [iic/punc_ct-transformer_cn-en-common-vocab471067-large](https://modelscope.cn/models/iic/punc_ct-transformer_cn-en-common-vocab471067-large) | ~1.1GB | 标点符号恢复 |

**手动下载方式**（离线环境）：
```bash
pip install modelscope
modelscope download --model iic/speech_seaco_paraformer_large_asr_nat-zh-cn-16k-common-vocab8404-pytorch
modelscope download --model iic/speech_fsmn_vad_zh-cn-16k-common-pytorch
modelscope download --model iic/punc_ct-transformer_cn-en-common-vocab471067-large
```

模型默认缓存在 `~/.cache/modelscope/models/` 目录下。

#### 离线整包部署（GitHub Releases）

适用场景：目标电脑无法联网，或希望免去首次运行时的在线下载等待。做法是把已下载好的模型缓存打包成压缩包，上传到本仓库的 GitHub Releases 作为附件，新电脑直接下载解压即可。

**A. 打包（在一台已成功运行、模型已下载完成的电脑上操作）**

模型缓存位置：
- Windows：`C:\Users\<你的用户名>\.cache\modelscope\models\`
- macOS/Linux：`~/.cache/modelscope/models/`

> GitHub 单个 Release 附件上限为 2GB，三个模型合计约 2GB，**建议按模型分别打包**成 3 个压缩包，避免超限。

Windows（PowerShell）：
```powershell
cd $env:USERPROFILE\.cache\modelscope\models
Compress-Archive -Path iic\speech_seaco_paraformer* -DestinationPath asr-paraformer.zip
Compress-Archive -Path iic\speech_fsmn_vad*        -DestinationPath asr-vad.zip
Compress-Archive -Path iic\punc_ct-transformer*    -DestinationPath asr-punc.zip
```

macOS/Linux：
```bash
cd ~/.cache/modelscope/models
zip -r asr-paraformer.zip iic/speech_seaco_paraformer*
zip -r asr-vad.zip        iic/speech_fsmn_vad*
zip -r asr-punc.zip       iic/punc_ct-transformer*
```

**B. 上传到 GitHub Releases**

网页方式：仓库首页右侧 **Releases → Draft a new release** → 填 Tag（如 `models-v1`）和标题 → 把 3 个 zip 拖入 *Attach binaries* 区域 → 等上传完成后 **Publish release**。

命令行方式（需先安装 gh CLI 并 `gh auth login`）：
```bash
gh release create models-v1 asr-paraformer.zip asr-vad.zip asr-punc.zip \
  --repo big-William-1992/xingyan-medical-record \
  --title "离线语音模型包 v1" \
  --notes "FunASR 离线模型：Paraformer 主模型 + FSMN-VAD + CT-Punc"
```

**C. 在新电脑上部署**

1. 从本仓库 Releases 页面下载 3 个 zip；
2. 解压到模型缓存目录（不存在则新建），解压后应形成 `...\models\iic\speech_seaco_paraformer.../` 这样的结构：
   - Windows：`C:\Users\<用户名>\.cache\modelscope\models\`
   - macOS/Linux：`~/.cache/modelscope/models/`
3. 启动软件，检测到本地已有模型即不再联网下载。

> **提示**：模型属于大文件，请勿用 `git add` 提交进仓库（GitHub 单文件上限 100MB）；离线分发一律走 Releases 附件或 Git LFS。

> **注意**：项目中的 `model/` 目录为旧版 Vosk 模型（已弃用），当前版本不再使用。

### 第四步：运行

```bash
# macOS/Linux:
source venv/bin/activate
python main.py

# Windows:
venv\Scripts\activate
python main.py
```

或双击 `启动.bat`（Windows）/ `启动.sh`（macOS/Linux）。

---

## 目录结构

```
星衍病历智能录入系统/
├── venv/                  ← Python 虚拟环境（需自建，不纳入 Git）
├── model/                 ← 旧版 Vosk 模型（已弃用，可删除）
├── templates/             ← 科室模板（内科/外科/影像科 JSON）
├── main.py                ← 主程序（PyQt5 GUI）
├── asr_engine.py          ← 语音识别引擎（FunASR Paraformer）
├── section_parser.py      ← 病历字段解析器
├── medical_classifier.py  ← 智能分类 + 增量填充
├── template_engine.py     ← 模板管理
├── corrector.py           ← 三级纠错引擎
├── rule_engine.py         ← 规则引擎
├── knowledge_graph.py     ← 医学知识图谱
├── crash_logger.py        ← 崩溃日志
├── medical_dict.json      ← 医疗词库
├── hotwords.txt           ← ASR 热词（模型级）
├── postprocess_hotwords.txt ← 纠错映射（文本级）
├── field_words.json       ← 字段关键词
├── correction_rules.json  ← 纠错规则
├── requirements.txt       ← Python 依赖
├── check_model.py         ← 模型目录校验脚本
├── 启动.bat               ← Windows 一键启动
├── 启动.sh                ← macOS/Linux 一键启动
└── 校验模型.bat           ← Windows 双击校验模型
```

---

## 使用流程

### 普通模板模式
1. **选择科室** — 顶部下拉框（内科/外科）
2. **选择模板** — 如"入院记录""首次病程""手术记录"
3. **开始录音** — 点击"🎤 开始录音"，对着麦克风说病历内容
4. **自动填充** — 系统自动识别字段并填入模板对应位置
5. **纠错** — 点击"✨ 纠错"修正医疗术语
6. **导出** — 点击"💾 导出"保存为 txt/md 文件

### 常见病模板模式（推荐）
1. **选择科室** → 选择 **【常见病】XX** 模板（如"【常见病】高血压病"）
2. **语音输入核心信息**，例如：
   > "张三，性别男，年龄六十五岁，发现血压升高十年，头晕三天，血压160比100"
3. 系统**自动替换**模板中的 X 占位符（姓名、性别、年龄、时间、血压等）
4. 剩余未替换的占位符可手动编辑，或点击"⚡ 一键套用"弹窗填写
5. 点击"📋 首页→病程"可从入院记录自动生成首次病程记录

---

## 功能说明

### 语音识别
- 基于 FunASR Paraformer（中文离线识别最优模型）
- VAD 自动断句 + CT-Punc 标点恢复
- 双层热词增强：模型级 hotword + 文本级 postprocess 纠错
- 中文数字自动转换（六十五 → 65）

### 常见病模板（11个）

**内科（6个）**：高血压病、2型糖尿病、冠心病、社区获得性肺炎、脑梗死、COPD急性加重

**外科（5个）**：急性阑尾炎、急性胆囊炎/胆囊结石、四肢骨折、腹股沟疝、混合痔

每个模板包含完整首页病程：主诉、现病史、既往史、个人史、婚育史、家族史、体格检查、辅助检查、初步诊断、诊断依据、鉴别诊断、诊疗计划。

### 三级纠错

| 层级 | 类型 | 说明 |
|------|------|------|
| Layer 1 | 词典匹配 | 医疗术语模糊匹配纠错 |
| Layer 2 | 规则引擎 | 常见口误、单位、格式修正 |
| Layer 3 | 科室校验 | 必填项检查、措辞规范 |

---

## 自定义扩展

### 添加新科室

编辑 `medical_dict.json`，添加新的科室词库：

```json
{
  "新科室": {
    "扩展症状": ["症状1", "症状2"],
    "扩展诊断": ["诊断1", "诊断2"],
    "扩展检查": ["检查1", "检查2"],
    "模板要求字段": ["字段1", "字段2"]
  }
}
```

### 添加纠错规则

在 `corrector.py` 的 `error_patterns` 列表中添加：

```python
(self, r'错误模式', '正确写法'),
```

### 添加模板

在软件内点击"📝 模板管理"，选择科室后编辑模板内容保存即可。
或手动编辑 `templates/科室名.json` 文件。

---

## 后续优化方向

- [ ] 收集纠错数据 → 训练自定义语言模型
- [ ] 支持麦克风设备选择
- [ ] 支持语音命令（"换模板""清除""导出"）
- [ ] 病历数据本地加密存储
- [ ] 多用户配置管理
- [ ] 嵌入现有病历系统（剪贴板/热键模式）
- [ ] 扩充更多常见病模板（妇产科、儿科等）

---

## 问题反馈

如有 bug 或建议，请联系星衍医学人工智能有限公司。
