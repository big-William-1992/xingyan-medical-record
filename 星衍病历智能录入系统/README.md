# 星衍AI智能病历录入系统 v3.0

**全科室版 — 离线语音识别 + 83套模板 + 医学知识图谱 + AI诊断辅助**

- 纯本地运行，无需联网（模型首次需下载）
- 基于 FunASR Paraformer 离线语音识别 + 3-gram 医学语言模型重打分
- 5大科室 83 套模板（内科/外科/妇产科/儿科/影像科 + 4套中医变体）
- 14,669 实体医学知识图谱 + 离线AI问答 + 诊断辅助
- 双层热词增强（27,409条医学术语）+ 三级纠错 + 语言模型重打分
- 语音命令、常用语句库、Word导出、授权管理

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
├── templates/             ← 科室模板（9个 JSON：5科室 + 4中医变体）
├── kg_data/               ← 知识图谱数据（放 *.json 即自动生效）
│   ├── medkg.json         ← 8,806种疾病（11MB）
│   ├── diseasekg.json     ← 5,576种疾病饮食宜忌（6MB）
│   └── herbs880.json      ← 880种中药材（1MB）
│
│─── 核心引擎 ───
├── main.py                ← 主程序（PyQt5 GUI）
├── asr_engine.py          ← 语音识别引擎（FunASR + 热词 + LM重打分）
├── medical_lm.py          ← 3-gram 医学语言模型（重打分纠错）
├── medical_classifier.py  ← 字段分类 + 增量填充 + 基本信息提取
├── section_parser.py      ← 病历段落解析器
├── template_engine.py     ← 模板管理（5科室 83套）
├── corrector.py           ← 医学术语后处理
├── rule_engine.py         ← 质控规则引擎
├── diagnosis_assistant.py ← AI诊断辅助（推断/检查/治疗/中医辨证）
│
│─── 知识图谱 ───
├── knowledge_graph.py     ← 医学知识图谱（14,669实体 + 438K关系）
├── knowledge_qa.py        ← 离线自然语言问答引擎
├── convert_openkg.py      ← OpenKG 三元组转换器
├── convert_medkg.py       ← QASystemOnMedicalKG 转换器
├── convert_diseasekg.py   ← DiseaseKG 饮食宜忌转换器
├── convert_cmekg.py       ← CMeKG 1.0 转换器
├── convert_shennong.py    ← 神农中医药转换器
├── convert_drugbank.py    ← DrugBank 药物说明书转换器
│
│─── 数据文件 ───
├── medical_3gram.pkl      ← 语言模型（651K三元组，15MB）
├── lm_corpus.txt          ← LM训练语料（73,941句）
├── medical_terms_thuocl.txt ← THUOCL医学术语（27,409条）
├── drug_names.txt         ← 药品名词库（65,570条）
├── icd10_codes.json       ← ICD-10诊断编码（43,246条）
├── hotwords.txt           ← ASR 热词（模型级）
├── postprocess_hotwords.txt ← 纠错映射（文本级，150+条）
├── medical_dict.json      ← 医疗词库
├── field_words.json       ← 字段关键词
├── correction_rules.json  ← 质控规则
│
│─── 辅助模块 ───
├── database.py            ← SQLite 本地数据库（用户/病历/版本）
├── license_manager.py     ← 授权管理（试用期 + 机器绑定）
├── voice_command.py       ← 语音命令解析
├── phrase_library.py      ← 常用语句库
├── correction_feedback.py ← 纠错反馈收集（LM迭代数据源）
├── train_lm.py            ← 3-gram 语言模型训练脚本
├── ux_components.py       ← UX增强（Toast提示/录音动画/新手引导）
├── crash_logger.py        ← 崩溃日志
├── login_dialog.py        ← 登录对话框
├── activation_dialog.py   ← 激活对话框
├── phrase_dialog.py       ← 语句库对话框
├── qa_dialog.py           ← 知识问答对话框
├── record_manager_dialog.py ← 病历管理对话框
├── check_model.py         ← 模型校验脚本
├── requirements.txt       ← Python 依赖
├── 启动.bat / 启动.sh     ← 一键启动
└── 校验模型.bat           ← Windows 模型校验
```

---

## 使用流程

### 普通模板模式
1. **选择科室** — 顶部下拉框（内科/外科/妇产科/儿科/影像科）
2. **选择模板** — 如“入院记录”“首次病程”“手术记录”
3. **开始录音** — 点击“🎤 开始录音”，对着麦克风说病历内容
4. **自动填充** — 系统自动识别字段并填入模板对应位置
5. **纠错** — 点击“✨ 纠错”修正医疗术语
6. **导出** — 点击“💾 导出”保存为 Word/txt 文件

### 常见病模板模式（推荐）
1. **选择科室** → 选择 **【常见病】XX** 模板（如“【常见病】高血压病”）
2. **语音输入核心信息**，例如：
   > “张三，性别男，年龄六十五岁，发现血压升高十年，头晕三天，血压160比100”
3. 系统**自动替换**模板中的 X 占位符（姓名、性别、年龄、时间、血压等）
4. 剩余未替换的占位符可手动编辑，或点击“⚡ 一键套用”弹窗填写
5. 点击“📋 首页→病程”可从入院记录自动生成首次病程记录

### 语音命令
录音时可直接说命令词：
- “切换到内科模板” / “使用外科模板”
- “清除内容” / “导出病历” / “保存病历”
- “停止录音” / “复制全文” / “打开病历库”

### 快捷键

| 快捷键 | 功能 |
|--------|------|
| `Ctrl+R` / `F2` | 开始/停止录音 |
| `F4` | 一键纠错 |
| `Ctrl+S` | 保存病历到病历库 |
| `Ctrl+E` | 导出文件 |
| `Ctrl+Shift+C` | 复制全文到剪贴板 |
| `F3` | 打开常用语句库 |
| `F9` | 折叠/展开纠错面板 |
| `F11` | 专注录音模式（隐藏干扰面板） |

### 界面增强

- **字段名高亮**：编辑器中「主诉：」「现病史：」「初步诊断：」等字段名自动着色，病历结构一目了然
- **音频拖入转写**：直接把 wav/mp3/m4a 音频文件拖进窗口，自动转写为文字
- **模板搜索**：模板下拉框可直接输入关键字过滤
- **工具栏收纳**：低频功能（模板管理/规则管理/结构化/崩溃日志）收进「更多」菜单

---

## 功能说明

### 语音识别（四层增强）

| 层级 | 技术 | 说明 |
|------|------|------|
| Layer 1 | FunASR Paraformer + VAD + CT-Punc | 中文离线识别 + 自动断句 + 标点恢复 |
| Layer 2 | 模型级热词（hotwords.txt） | 27,409条医学术语增强解码 |
| Layer 3 | 文本级纠错（postprocess_hotwords.txt） | 150+条 ASR 误识别映射纠正 |
| Layer 4 | 3-gram 语言模型重打分 | 651K三元组，保守纠正低概率区域 |

### 模板体系（5科室 83套）

| 科室 | 模板数 | 含中医变体 | 常见病模板 |
|------|--------|----------|----------|
| 内科 | 22 | ✓ | 高血压/糖尿病/冠心病/肺炎/脑梗/COPD |
| 外科 | 21 | ✓ | 阑尾炎/胆囊炎/四肢骨折/腹股沟疝/混合痔 |
| 妇产科 | 14 | ✓ | 子宫肌瘤/卵巢囊肿/异位妊娠等 |
| 儿科 | 14 | ✓ | 小儿肺炎/手足口病/新生儿黄疸等 |
| 影像科 | 12 | — | CT/MRI/超声报告模板 |

### 医学知识图谱

- **实体总量**：14,669 个（疾病 8,788 + 食物 4,865 + 药物 3,830 + 中药材 860 + 症状 5,571 + 检查 3,362）
- **关系总量**：438,190 条
- **数据源**：内置 60+ 精细疾病 + medkg(8,806) + DiseaseKG(饮食宜忌) + herbs880(中药材)
- **问答引擎**：支持治疗/症状/检查/药物/说明书/中医/饮食/鉴别 8种意图

### AI诊断辅助

- 症状→疾病推断（基于知识图谱匹配）
- 建议检查项目
- 治疗方案推荐（药物 + 中医治法方药）
- 用药审查（药物与诊断匹配校验）
- 中医辨证论治（证型推断 + 方剂推荐）

### 其他功能

- 常用语句库（自定义短语快捷插入）
- 病历本地存储（SQLite）+ 历史版本回溯
- Word 导出
- 授权管理（试用期 + 机器绑定 + 批量管理）
- 录音降噪预处理（高通滤波 + 噪声门）
- 麦克风设备选择
- 中文数字自动转换（六十五 → 65）

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

**方式一：GUI 操作**（推荐）

在软件内点击“✨ 纠错”→“规则管理”，可添加/删除错别字规则和逻辑错误规则。

**方式二：编辑 JSON 文件**

编辑 `correction_rules.json`：

```json
{
  "错别字": [
    {"错误": "心电围", "正确": "心电图"},
    {"错误": "新规则", "正确": "正确写法"}
  ],
  "逻辑错误": [...]
}
```

**方式三：ASR 级纠错**

编辑 `postprocess_hotwords.txt`，添加 ASR 误识别映射（识别后立即纠正）：

```
误识别词 => 正确词
```

### 用户自适应热词

系统会从历史病历中自动提取高频词写入 `user_hotwords.txt`，下次识别时自动加载。也可手动编辑该文件添加专业术语（每行一个）。

### 添加模板

在软件内点击"📝 模板管理"，选择科室后编辑模板内容保存即可。
或手动编辑 `templates/科室名.json` 文件。

### 接入外部医学知识图谱（OpenKG / CMeKG）

系统内置了约 60 个常见疾病的知识图谱（疾病-症状-检查-药物），并支持导入外部开放知识以扩充治疗方案推荐。

**数据来源**（[OpenKG.cn](http://openkg.cn/dataset) 免费开放，需注册下载）：

| 数据集 | 规模 | 适用 |
|--------|------|------|
| 面向家庭常见疾病的知识图谱 | 常见病、症状、治疗手段、常用药物 | 格式最贴合，推荐首选 |
| CMeKG 2.0 | 1万+ 疾病、2万+ 药物、156万三元组 | 规模最大 |
| DiaKG | 糖尿病指南与共识 | 专科深度 |

**接入三步**：

```bash
# 1. 从 OpenKG 下载三元组数据（CSV/TSV/JSON）
# 2. 转换为统一知识 JSON（自动输出到 kg_data/）
python convert_openkg.py cmekg_triples.csv --sep '\t'
# 3. 重启程序即生效（knowledge_graph 启动时自动合并 kg_data/*.json）
```

也可直接手写 `kg_data/*.json`（schema 见 `kg_data/sample_openkg.json`），支持疾病的**别名归一化**和药物**说明书**（适应症/用法用量/禁忌/不良反应）。程序接口：

```python
from knowledge_graph import MedicalKnowledgeGraph
kg = MedicalKnowledgeGraph()
kg.recommend_treatment("2型糖尿病")   # 综合药物+检查+中医证型+说明书
kg.get_drug_info("二甲双胍")           # 药物说明书
kg.normalize("格华止")                 # 别名 → 标准名
```

> ⚠️ 知识图谱仅供医师参考辅助，不构成诊疗决策依据。

### 推荐：QASystemOnMedicalKG（免费直接下载，4.4万疾病）

CMeKG 全量数据需邮件申请、官网不稳定，无法直接下载。**最佳中文替代**是 [QASystemOnMedicalKG](https://github.com/liuhuanyong/QASystemOnMedicalKG) 的 `data/medical.json`（约 4.4 万种疾病，寻医问药网抽取，免费）：

```bash
# 1. 从 GitHub 下载 data/medical.json
# 2. 转换（可过滤信息过少的疾病、限量）
python convert_medkg.py medical.json -o kg_data/medkg.json --min-fields 1
# 3. 重启即生效；kg_data/medkg.json 体积小，可直接提交进 git 随软件离线分发
```

转换后 `recommend_treatment()` 即可覆盖几万个疾病的症状/检查/用药推荐。

### 接入 DrugBank 药物说明书

DrugBank 提供国际权威的药物 monograph（适应症/剂量/毒性/作用机制）。

> ⚠️ **两个前提**：① 完整库需在 [go.drugbank.com](https://go.drugbank.com) 申请免费学术许可后下载（单个约 1.4GB XML，不入 git）；② DrugBank 为英文，转换器内置常用药中英映射（ZH_MAP），可用 `--zh-map` 扩充。

```bash
# 默认只导出命中中文映射的药物（与病历中文药名对齐）
python convert_drugbank.py "full database.xml" -o kg_data/drugbank.json
# 保留未映射的英文药物 / 自定义映射
python convert_drugbank.py db.xml --zh-map mymap.csv --keep-english
```

输出同样写入 `kg_data/`，重启后 `get_drug_info()` / `recommend_treatment()` 即可读到说明书。若同一药物在多个数据源都有说明书，后加载的文件覆盖先前的（文件名字母序）。

> 中文医院如需国内合规说明书，建议以 NMPA（国家药监局）说明书为准，DrugBank 英文内容作为机制/毒性参考。

---

## 后续优化方向

- [x] 收集纠错数据 → 迭代语言模型（已实现，见下方说明）
- [ ] 嵌入现有病历系统（剪贴板/热键模式）
- [ ] 影像征象知识图谱（疾病→影像表现→征象术语）
- [ ] CMeKG 完整版接入（19,853种药物说明书）
- [ ] 神农中医药接入（113K条方剂/药材）
- [ ] 多语言支持（英文病历）

### 语言模型迭代训练

系统会自动收集纠错反馈和用户确认的病历文本，定期重训 3-gram 语言模型以提升识别准确率。

**自动收集（无需手动操作）：**
- 每次纠错后，修正对记录到 `correction_feedback.jsonl`
- 用户拒绝/接受纠错时，自动更新反馈状态
- 保存/导出病历时，终稿文本收集到 `user_corpus.txt`

**手动重训（建议每季度执行一次）：**

```bash
# 查看语料统计
python train_lm.py --stats

# 模拟训练（不写文件，查看增量）
python train_lm.py --dry-run

# 正式训练（自动备份旧模型为 .bak）
python train_lm.py
```

训练完成后重启程序即生效。

---

## 问题反馈

如有 bug 或建议，请联系星衍医学人工智能有限公司。
