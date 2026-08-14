# Backfill 下一批高置信候选项（收敛版）

生成时间：2026-08-06
口径：`data/correction_memory.jsonl` 中 `accepted + original != corrected + confidence >= 0.75`
排除：已写入 `postprocess_hotwords.txt` 或 `asr_confusion_pairs.json` 的项

## 收敛原则
- 只保留下一批更高频候选项，避免 Top-K 摊得过散
- 优先保留：字段名纠错、高频术语、检查/用药/单位误识别
- 暂缓：测试样例、超长规则描述、低次测试项

## 候选项总表（按频次降序）

| 频次 | 错误词 | 正确词 | 来源 | 建议通道 | 说明 |
| --- | --- | --- | --- | --- | --- |
| 18 | 主诉 | 主诉 | postprocess_hotword | postprocess | 字段名纠错，已有前置映射可覆盖 |
| 15 | 家族史 | 家族史 | postprocess_hotword | postprocess | 字段名纠错，已有前置映射可覆盖 |
| 15 | 既往史 | 既往史 | postprocess_hotword | postprocess | 字段名纠错，已有前置映射可覆盖 |
| 15 | 现病史 | 现病史 | postprocess_hotword | postprocess | 字段名纠错，已有前置映射可覆盖 |
| 12 | 个人史 | 个人史 | postprocess_hotword | postprocess | 字段名纠错，已有前置映射可覆盖 |
| 9 | 出院医嘱 | 出院医嘱 | postprocess_hotword | postprocess | 字段名纠错，已有前置映射可覆盖 |
| 9 | 初步诊断 | 初步诊断 | postprocess_hotword | postprocess | 字段名纠错，已有前置映射可覆盖 |
| 9 | 吸烟 | 吸烟 | postprocess_hotword | postprocess | 字段名纠错，已有前置映射可覆盖 |
| 9 | 婚育史 | 婚育史 | postprocess_hotword | postprocess | 字段名纠错，已有前置映射可覆盖 |
| 9 | 脑梗死 | 脑梗死 | postprocess_hotword | postprocess | 字段名纠错，已有前置映射可覆盖 |
| 6 | 啰音 | 啰音 | postprocess_hotword | postprocess | 高频症状体征词 |
| 6 | 增强特征 | 增强特征 | postprocess_hotword | postprocess | 影像报告高频词 |
| 6 | 影像表现 | 影像表现 | postprocess_hotword | postprocess | 影像报告高频词 |
| 6 | 无明显诱因 | 无明显诱因 | postprocess_hotword | postprocess | 现病史高频词 |
| 6 | 既往 | 既往 | postprocess_hotword | postprocess | 现病史/既往史高频词 |
| 6 | 诊断意见 | 诊断意见 | postprocess_hotword | postprocess | 影像/诊断高频词 |
| 6 | 诱因 | 诱因 | postprocess_hotword | postprocess | 现病史高频词 |
| 6 | 辅助检查 | 辅助检查 | postprocess_hotword | postprocess | 病历结构高频词 |
| 6 | 高血压 | 高血压 | postprocess_hotword | postprocess | 慢病史高频词 |
| 3 | 乏力 | 乏力 | postprocess_hotword | postprocess | 症状高频词 |
| 3 | 二甲双胍 | 二甲双胍 | postprocess_hotword | postprocess | 用药高频词 |
| 3 | 体格检查 | 体格检查 | postprocess_hotword | postprocess | 查体高频词 |
| 3 | 冠心病 | 冠心病 | postprocess_hotword | postprocess | 慢病史高频词 |
| 3 | 双下肢 | 双下肢 | postprocess_hotword | postprocess | 查体高频词 |
| 3 | 双肺 | 双肺 | postprocess_hotword | postprocess | 查体高频词 |
| 3 | 发热 | 发热 | postprocess_hotword | postprocess | 症状高频词 |
| 3 | 呕吐 | 呕吐 | postprocess_hotword | postprocess | 症状高频词 |
| 3 | 呼吸困难 | 呼吸困难 | postprocess_hotword | postprocess | 症状高频词 |
| 3 | 咯血 | 咯血 | postprocess_hotword | postprocess | 症状高频词 |
| 3 | 咳嗽 | 咳嗽 | postprocess_hotword | postprocess | 症状高频词 |
| 3 | 咳痰 | 咳嗽 | postprocess_hotword | postprocess | 症状高频词 |
| 3 | 头晕 | 头晕 | postprocess_hotword | postprocess | 症状高频词 |
| 3 | 头痛 | 头痛 | postprocess_hotword | postprocess | 症状高频词 |
| 3 | 左氧氟沙星 | 左氧氟沙星 | postprocess_hotword | postprocess | 用药高频词 |
| 3 | 已婚 | 已婚 | postprocess_hotword | postprocess | 人口学高频词 |
| 3 | 干性啰音 | 干性啰音 | postprocess_hotword | postprocess | 体征高频词 |
| 3 | 支气管 | 支气管 | postprocess_hotword | postprocess | 诊断/症状高频词 |
| 3 | 支气管炎 | 支气管炎 | postprocess_hotword | postprocess | 诊断高频词 |
| 3 | 未婚 | 未婚 | postprocess_hotword | postprocess | 人口学高频词 |
| 3 | 术中情况 | 术中情况 | postprocess_hotword | postprocess | 手术病历高频词 |
| 3 | 术前诊断 | 术前诊断 | postprocess_hotword | postprocess | 手术病历高频词 |
| 3 | 术后医嘱 | 术后医嘱 | postprocess_hotword | postprocess | 手术病历高频词 |
| 3 | 查体 | 查体 | postprocess_hotword | postprocess | 查体高频词 |
| 3 | 检查部位 | 检查部位 | postprocess_hotword | postprocess | 检查高频词 |
| 3 | 检查项目 | 检查项目 | postprocess_hotword | postprocess | 检查高频词 |
| 3 | 水肿 | 水肿 | postprocess_hotword | postprocess | 症状高频词 |
| 3 | 汉族 | 汉族 | postprocess_hotword | postprocess | 人口学高频词 |
| 3 | 消瘦 | 消瘦 | postprocess_hotword | postprocess | 症状高频词 |
| 3 | 湿性啰音 | 湿性啰音 | postprocess_hotword | postprocess | 体征高频词 |
| 3 | 糖尿病 | 糖尿病 | postprocess_hotword | postprocess | 慢病史高频词 |
| 3 | 胸痛 | 胸痛 | postprocess_hotword | postprocess | 症状高频词 |
| 3 | 腹泻 | 腹泻 | postprocess_hotword | postprocess | 症状高频词 |
| 3 | 腹痛 | 腹痛 | postprocess_hotword | postprocess | 症状高频词 |
| 3 | 诊疗经过 | 诊疗经过 | postprocess_hotword | postprocess | 病历结构高频词 |
| 3 | 超声所见 | 超声所见 | postprocess_hotword | postprocess | 检查高频词 |
| 3 | 超声提示 | 超声提示 | postprocess_hotword | postprocess | 检查高频词 |
| 3 | 阿司匹林 | 阿司匹林 | postprocess_hotword | postprocess | 用药高频词 |
| 3 | 阿莫西林 | 阿莫西林 | postprocess_hotword | postprocess | 用药高频词 |
| 3 | 饮酒 | 饮酒 | postprocess_hotword | postprocess | 人口学高频词 |

## 建议收敛策略

### 阶段 A：字段名闭环（优先）
- 字段名纠错建议保持 postprocess 固定对，不继续膨胀 ASR 混淆对
- 可只保留错误词多样性，不重复补 target 同义词

### 阶段 B：术语收敛到 30~50 个
- 下一批先上：`啰音 / 增强特征 / 影像表现 / 无明显诱因 / 既往 / 诊断意见 / 诱因 / 辅助检查 / 高血压`
- 症状体征批次：`乏力 / 发热 / 呕吐 / 呼吸困难 / 咯血 / 咳嗽 / 咳痰 / 头晕 / 头痛 / 双肺 / 双下肢`
- 用药批次：`二甲双胍 / 左氧氟沙星 / 阿司匹林 / 阿莫西林`

### 阶段 C：ASR 混淆对暂缓扩展
- 当前已上线 15 对高频混淆对，建议先观察召回/误纠
- 下一批 ASR 混淆对建议控制在 5~10 对，且必须满足：
  - backfill 频次 >= 3
  - 不在 postprocess 中已覆盖
  - 属于 ASR 强混淆项（同音/近音/掉字/加词）
