# 语音纠错闭环最小改造计划

> 目标：在现有 `Paraformer + 热词 + 规则纠错 + LM 重打分` 基础上，补上 diff 审阅、统一记忆库、Top-K 术语、prompt 回灌、LM 自动迭代，不改 Whisper 模型栈。

## 1. 现状断点

- 识别后直接纠错并覆盖文本：`main.py:2420`
- 仅记录纠错日志和最终语料，无 doctor/dept/field/confidence 维度：`correction_feedback.py:33`
- 热词/规则/混淆对分散存储，无统一记忆库：`hotwords.txt:1`、`postprocess_hotwords.txt:1`、`correction_rules.json:1`、`asr_confusion_pairs.json:1`
- LM 重训为手动触发，无自动触发和指标闭环：`main.py:3998`、`train_lm.py:1`
- 已有手动修正提取，但缺少稳定 diff 审阅流：`main.py:2960`

## 2. 改造原则

- 最小侵入：先加新模块，再逐步替换旧文件读写。
- 保留现有桌面端主流程：`MedVoiceApp` 仍可用，只在关键节点插入记忆库和 diff 审阅。
- 离线优先：所有新增数据默认存本地 SQLite/JSONL，不引入外部服务。
- 可回滚：每次 LM/微调迭代自动备份旧模型和旧记忆库版本。

## 3. 最小可行闭环顺序

1. diff 审阅 UI + accept/reject/override 结构化落盘
2. 统一记忆库 schema + backfill
3. Top-K 术语引擎
4. prompt 上下文包/initial_prompt 兼容层
5. LM 自动迭代
6. 微调数据集闭环

## 4. 逐文件改造清单

### 4.1 新增 `correction_memory.py`

职责：统一记忆库服务，替代分散文件读写。

核心能力：
- 记忆条目写入：`original / corrected / doctor_id / dept / field / source / status / confidence / freq / created_at`
- 记忆条目查询：按 doctor / dept / field / source / 时间窗口查询
- 统计接口：accepted_rate / top_terms / recent_pairs / feedback_since_last_lm_train
- 版本化导出：可导出 hotwords / postprocess_hotwords / confusion_pairs / prompt_pack

建议存储：
- 主数据：`data/correction_memory.jsonl`
- 索引/统计：`data/correction_memory_index.json`
- 备份目录：`data/correction_memory_backups/`

### 4.2 新增 `diff_review_dialog.py`

职责：医生 diff 审阅弹窗/面板，替代当前“纠错后直接覆盖”行为。

最小字段：
- `original_asr`
- `corrected_asr`
- `final_text`
- `changes`: 每条 diff 的 `original / corrected / source / accepted`
- `snapshot_id`: 关联 ASR 快照，用于训练

UI 行为：
- 打开时自动 diff `original_asr` 和 `corrected_asr`
- 提供：接受单条、接受全部、拒绝单条、手改覆盖
- 确认后写回编辑器，并把 decision 写入记忆库

接入点：
- `main.py:2420` 纠错完成后，先调 `DiffReviewDialog`，不再直接 `setPlainText(corrected)`

### 4.3 新增 `topk_engine.py`

职责：从记忆库生成 Top-K 术语。

核心能力：
- 全局/科室/医生三级 Top-K
- 时间衰减：近 30/90 天权重更高
- 置信度加权：accepted_rate 高者优先
- 预算控制：模板/字段下最多返回 N 个词

输出：
- `selected_terms`
- `prompt_pack`
- `hotword_lines`
- `postprocess_hotword_lines`

接入点：
- `ASREngine.set_hotwords()` 前调用
- 换科室、保存病历、LM 重训后刷新

### 4.4 扩展 `ASREngine` 支持 prompt 兼容层

改造点：`asr_engine.py:164`、`asr_engine.py:690`

新增能力：
- `set_prompt_pack(prompt_pack)`：保存 prompt 包，不一定要传给 Paraformer，但可用来生成 hotword/postprocess/rules
- `build_prompt_from_topk(topk)`：生成 prompt-like 文本包
- `apply_prompt_pack()`：把 prompt 包转化为现有能消费的格式：
  - 追加到 `hotword`
  - 追加到 `postprocess_hotwords`
  - 注入规则/混淆对优先级

保留兼容：
- 不删除现有 `hotword` 文件机制
- 只增加“从记忆库/规则库生成”的入口

### 4.5 扩展 `CorrectionFeedback` 为轻量记忆库适配器

改造点：`correction_feedback.py:33`

新增能力：
- `log_corrections_with_memory(log_items, memory)`：同时写 `correction_feedback.jsonl` 和 `correction_memory`
- `log_accept_all_with_memory(memory)`：批量标记 accepted，并更新 freq/confidence
- `collect_corpus_with_memory(text, memory, doctor_id, dept)`：收集时写入 memory
- `export_to_memory()`：把历史反馈一次性 backfill

目标：不改旧接口的前提下，逐步把反馈流接到统一记忆库。

### 4.6 扩展 `main.py` 闭环控制流

改造点：`main.py:2318`、`main.py:2406`、`main.py:2920`、`main.py:3998`

关键改动：
- `_on_recognized()` 后固定保存 `_last_asr_snapshot`
- `_run_correction()` 改为：
  1. 调 `corrector.correct(text)`
  2. 打开 `DiffReviewDialog`
  3. 医生确认后写回文本
  4. 调用 `memory.log_decision(diff_decision)`
- `_save_record()` 前：
  1. 比较 `_last_asr_snapshot` 和终稿
  2. 生成 manual_edit diff
  3. 写回记忆库
  4. 更新 `user_hotwords`
  5. 刷新 Top-K
- `_retrain_lm()` 改为自动触发 + 手动触发双模式：
  - 自动触发条件：`memory.should_retrain_lm()`
  - 训练前后自动比较模型统计
  - 自动写 `lm_iteration_report.json`

### 4.7 新增 `build_finetune_dataset.py`

职责：把记忆库和录音文件整理成 `finetune_data/wav.scp + text.txt`

核心能力：
- 只选 `accepted + high_confidence + verified_audio`
- 过滤时长过长/过短/文本空/重复
- train/dev 划分
- 生成 `metadata.jsonl`，记录每条来源：`source=memory / manual_edit / accepted_correction`

触发方式：
- 自动：记忆库新增有效样本超过阈值
- 手动：菜单按钮“准备微调数据集”

### 4.8 新增 `memory_dashboard_dialog.py`

职责：看板，帮助医生和管理员看到闭环效果。

核心指标：
- 本周反馈量
- 自动纠错接受率
- 手动修改量
- Top-K 术语变化
- LM 迭代次数和 CER 变化
- 微调候选样本数

接入点：
- 工具栏新增“🧠 记忆库看板”
- 状态栏显示“上次 LM 重训时间 / 当前记忆库条目数”

## 5. 数据流总览

```text
医生口述
  -> ASR 识别 + hotword/postprocess/prompt_pack
  -> original_asr
  -> corrector.correct()
  -> corrected_asr
  -> DiffReviewDialog
  -> 医生 accept/reject/override
  -> final_text
  -> 保存病历
  -> _extract_manual_corrections()
  -> CorrectionMemory
  -> TopKEngine
  -> 更新 hotwords / postprocess / prompt_pack
  -> LM 自动重训判断
  -> 必要时准备 finetune 数据集
```

## 6. 里程碑

- M1：diff 审阅可用，accept/reject 能写入记忆库
- M2：统一记忆库上线，旧文件改为只读或自动 backfill
- M3：Top-K 术语自动刷新，ASR 热词能按科室/医生切换
- M4：LM 自动重训 + 指标报告
- M5：微调数据集自动构建 + eval 报告

## 7. 回滚与兼容

- 所有新增功能默认开关关闭，旧流程继续运行。
- 记忆库写入失败时降级到旧 `correction_feedback.jsonl`。
- LM 重训失败时保留旧 `medical_3gram.pkl`。
- 微调失败时不更新线上模型权重。
