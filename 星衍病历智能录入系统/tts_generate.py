#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TTS 医学语料生成器
从病历模板 + 知识图谱三元组生成训练句子，用 edge-tts 合成语音
输出: finetune_data/wav.scp + finetune_data/text.txt
"""
import os
import sys
import json
import asyncio
import random
import subprocess
import edge_tts

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "finetune_data")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# 多种声音模拟不同医生
VOICES = [
    "zh-CN-YunxiNeural",    # 男声1
    "zh-CN-YunyangNeural",  # 男声2（新闻播报风格）
    "zh-CN-YunxiaNeural",   # 男声3
    "zh-CN-XiaoxiaoNeural", # 女声1
    "zh-CN-XiaoyiNeural",   # 女声2
]

# ─── 从模板生成句子 ───
def generate_template_sentences():
    """从病历模板生成口述风格的训练句子"""
    sentences = []
    
    # 基本信息组合
    surnames = ["张", "李", "王", "刘", "陈", "杨", "赵", "黄", "周", "吴"]
    given_names = ["伟", "芳", "强", "敏", "静", "丽", "磊", "洋", "勇", "艳",
                   "建国", "秀英", "志强", "桂英", "文华", "玉兰", "国强", "淑珍"]
    genders = ["男", "女"]
    ages = [str(random.randint(25, 85)) + "岁" for _ in range(50)]
    nations = ["汉族", "回族", "满族", "壮族", "苗族", "蒙古族"]
    
    # 主诉模板
    chief_complaints = [
        "反复头痛头晕{t1}，加重{t2}",
        "咳嗽咳痰{t1}，伴发热{t2}",
        "反复胸闷胸痛{t1}，加重{t2}",
        "发现血糖升高{t1}，口干多饮{t2}",
        "反复上腹痛{t1}，加重{t2}",
        "活动后气短{t1}，加重{t2}",
        "反复心悸{t1}，伴胸闷{t2}",
        "双下肢水肿{t1}，加重{t2}",
        "反复腰背痛{t1}",
        "头晕伴视物旋转{t2}",
        "突发右侧肢体无力{t2}",
        "反复腹泻{t1}，伴消瘦{t2}",
        "皮肤黄染{t2}",
        "反复关节肿痛{t1}",
        "尿频尿急尿痛{t2}",
    ]
    time1 = ["半年", "一年", "两年", "三年", "五年", "十年", "数月", "一个月"]
    time2 = ["一天", "两天", "三天", "五天", "一周", "两周", "一个月"]
    
    # 现病史模板
    history_templates = [
        "患者{t1}前无明显诱因出现{symptom}，呈{nature}，伴{companion}，无{negative}，为求进一步诊治来我院",
        "患者{t1}前因{cause}后出现{symptom}，自行口服{drug}，症状无明显缓解，为求进一步诊治来我院",
        "患者{t1}前体检发现{finding}，当时无不适，未予重视，{t2}前{symptom}加重，来我院就诊",
    ]
    symptoms_list = ["头痛", "头晕", "胸闷", "胸痛", "咳嗽", "腹痛", "腹泻", "发热",
                     "心悸", "气短", "水肿", "腰痛", "关节痛", "尿频", "黄疸"]
    natures = ["持续性胀痛", "阵发性绞痛", "隐痛", "钝痛", "刺痛", "烧灼样痛"]
    companions = ["恶心呕吐", "视物模糊", "肢体麻木", "出冷汗", "呼吸困难", "乏力"]
    negatives = ["意识丧失", "抽搐", "咯血", "黑便", "大小便失禁", "胸痛胸闷"]
    causes = ["受凉", "劳累", "情绪激动", "饮酒", "饮食不洁", "外伤"]
    drugs_list = ["止痛药", "降压药", "抗生素", "胃药", "退烧药"]
    findings = ["血压升高", "血糖升高", "肝功能异常", "肺部结节", "甲状腺结节"]
    
    # 既往史模板
    past_history = [
        "否认肝炎结核等传染病史，否认手术外伤史，否认输血史，否认食物及药物过敏史",
        "高血压病史{t1}，最高血压{bp}，目前口服{drug}，血压控制可",
        "糖尿病病史{t1}，口服{drug}降糖，血糖控制尚可",
        "冠心病病史{t1}，口服阿司匹林和他汀类药物治疗",
        "否认高血压糖尿病冠心病等慢性病史",
        "有青霉素过敏史，否认其他药物过敏史",
    ]
    bps = ["一百五十 九十五", "一百六十 一百", "一百七十 一百一十", "一百八十 一百一十"]
    
    # 家族史模板
    family_history = [
        "父亲有高血压病史，否认家族遗传病",
        "母亲有糖尿病病史，否认其他家族遗传病",
        "父母均有高血压病史，否认家族遗传病及传染病史",
        "否认家族遗传病及传染病史",
        "父亲有冠心病病史，母亲体健",
    ]
    
    # 体格检查模板
    physical_exam = [
        "体温三十六点五摄氏度，脉搏七十八次每分，呼吸十八次每分，血压{bp}毫米汞柱",
        "神志清楚，精神可，发育正常，营养中等，自主体位，查体合作",
        "全身皮肤黏膜无黄染，浅表淋巴结未触及肿大",
        "双肺呼吸音清，未闻及干湿性啰音",
        "心率七十八次每分，律齐，各瓣膜听诊区未闻及病理性杂音",
        "腹平软，无压痛及反跳痛，肝脾肋下未触及",
        "脊柱四肢无畸形，双下肢无水肿",
    ]
    
    # 生成句子
    random.seed(42)
    
    # 1. 基本信息句
    for _ in range(500):
        name = random.choice(surnames) + random.choice(given_names)
        gender = random.choice(genders)
        age = random.choice(ages)
        nation = random.choice(nations)
        sentences.append(f"姓名 {name} 性别 {gender} 年龄 {age} 民族 {nation}")
    
    # 2. 主诉句
    for _ in range(800):
        tpl = random.choice(chief_complaints)
        s = tpl.format(t1=random.choice(time1), t2=random.choice(time2))
        sentences.append(f"主诉 {s}")
    
    # 3. 现病史句
    for _ in range(1200):
        tpl = random.choice(history_templates)
        s = tpl.format(
            t1=random.choice(time1), t2=random.choice(time2),
            symptom=random.choice(symptoms_list), nature=random.choice(natures),
            companion=random.choice(companions), negative=random.choice(negatives),
            cause=random.choice(causes), drug=random.choice(drugs_list),
            finding=random.choice(findings)
        )
        sentences.append(f"现病史 {s}")
    
    # 4. 既往史句
    for _ in range(600):
        tpl = random.choice(past_history)
        s = tpl.format(t1=random.choice(time1), bp=random.choice(bps),
                       drug=random.choice(drugs_list))
        sentences.append(f"既往史 {s}")
    
    # 5. 家族史句
    for _ in range(400):
        sentences.append(f"家族史 {random.choice(family_history)}")
    
    # 6. 体格检查句
    for _ in range(800):
        tpl = random.choice(physical_exam)
        s = tpl.format(bp=random.choice(bps))
        sentences.append(f"体格检查 {s}")
    
    # 7. 婚育史/个人史
    marriage = ["已婚已育，配偶及子女体健", "未婚未育", "已婚，育有一子一女，配偶及子女体健"]
    personal = ["生于原籍，否认疫区居住史，否认粉尘及放射性物质接触史",
                "吸烟二十年，约十支每日，饮酒十年，约二两每日",
                "否认吸烟饮酒史"]
    for _ in range(300):
        sentences.append(f"婚育史 {random.choice(marriage)}")
    for _ in range(300):
        sentences.append(f"个人史 {random.choice(personal)}")
    
    # 8. 从知识图谱三元组生成
    kg_path = os.path.join(BASE_DIR, "kg_data", "xywy_kg.json")
    if os.path.exists(kg_path):
        with open(kg_path, 'r', encoding='utf-8') as f:
            kg = json.load(f)
        triples = kg.get("triples", [])
        # 生成 "XX的常用药物有YY" 等句子
        disease_drugs = {}
        disease_symptoms = {}
        for tri in triples:
            s, p, o = tri.get("s", ""), tri.get("p", ""), tri.get("o", "")
            if p == "推荐药物" and s and o:
                disease_drugs.setdefault(s, []).append(o)
            elif p == "症状" and s and o:
                disease_symptoms.setdefault(s, []).append(o)
        
        for disease, drugs in list(disease_drugs.items())[:500]:
            if len(drugs) >= 2:
                d = random.sample(drugs, min(3, len(drugs)))
                sentences.append(f"{disease}的常用药物有{'、'.join(d)}")
        
        for disease, syms in list(disease_symptoms.items())[:500]:
            if len(syms) >= 2:
                s = random.sample(syms, min(3, len(syms)))
                sentences.append(f"{disease}的常见症状包括{'、'.join(s)}")
    
    return sentences


def log(msg):
    print(msg, flush=True)


async def synthesize(sentences, output_dir):
    """批量 TTS 合成"""
    wav_scp = []
    text_txt = []
    
    sem = asyncio.Semaphore(5)  # 并发限制
    
    async def gen_one(idx, text, voice):
        async with sem:
            utt_id = f"utt{idx:05d}"
            wav_path = os.path.join(output_dir, f"{utt_id}.wav")
            # 断点续传：已存在且有效的 wav 直接跳过
            if os.path.exists(wav_path) and os.path.getsize(wav_path) > 1000:
                return utt_id, wav_path, text
            try:
                communicate = edge_tts.Communicate(text, voice, rate="+0%")
                # edge-tts 输出 mp3，需要转 wav
                mp3_path = wav_path.replace('.wav', '.mp3')
                await asyncio.wait_for(communicate.save(mp3_path), timeout=30)
                # 用 ffmpeg 转 16kHz mono wav
                subprocess.run(['ffmpeg', '-y', '-i', mp3_path, '-ar', '16000', '-ac', '1', '-sample_fmt', 's16', wav_path, '-loglevel', 'quiet'], capture_output=True)
                if os.path.exists(mp3_path):
                    os.remove(mp3_path)
                if os.path.exists(wav_path) and os.path.getsize(wav_path) > 1000:
                    return utt_id, wav_path, text
            except Exception as e:
                pass
            return None
    
    log(f"开始合成 {len(sentences)} 条语音...")
    batch_size = 50
    total = len(sentences)
    
    for batch_start in range(0, total, batch_size):
        batch = sentences[batch_start:batch_start + batch_size]
        tasks = []
        for i, text in enumerate(batch):
            idx = batch_start + i
            voice = random.choice(VOICES)
            tasks.append(gen_one(idx, text, voice))
        
        try:
            results = await asyncio.wait_for(asyncio.gather(*tasks), timeout=300)
        except asyncio.TimeoutError:
            log(f"  ⚠️ 批次 {batch_start}-{batch_start+len(batch)} 超时，跳过卡住的条目")
            results = []
            # 回收已完成的条目
            for t in tasks:
                if t.done() and not t.cancelled():
                    try:
                        results.append(t.result())
                    except Exception:
                        pass
        for r in results:
            if r:
                wav_scp.append(f"{r[0]} {r[1]}")
                text_txt.append(f"{r[0]} {r[2]}")
        
        done = min(batch_start + batch_size, total)
        log(f"  进度: {done}/{total} ({done*100//total}%) | 成功: {len(wav_scp)}")
    
    # 写入文件
    scp_path = os.path.join(output_dir, "wav.scp")
    txt_path = os.path.join(output_dir, "text.txt")
    with open(scp_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(wav_scp) + '\n')
    with open(txt_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(text_txt) + '\n')
    
    log(f"\n✅ 完成！成功合成 {len(wav_scp)} 条")
    log(f"  wav.scp: {scp_path}")
    log(f"  text.txt: {txt_path}")
    return len(wav_scp)


def main():
    print("═" * 50)
    print("  TTS 医学语料生成器")
    print("═" * 50)
    
    # 生成句子（固定随机种子，保证断点续传时索引一致）
    random.seed(42)
    sentences = generate_template_sentences()
    log(f"生成训练句子: {len(sentences)} 条")
    random.shuffle(sentences)
    
    # 限制数量（默认5000条）
    max_count = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
    sentences = sentences[:max_count]
    log(f"截取前 {len(sentences)} 条进行合成")
    
    # 合成语音
    count = asyncio.run(synthesize(sentences, OUTPUT_DIR))
    log(f"\n 最终训练数据: {count} 条")
    log(f"预计音频时长: ~{count * 4 / 3600:.1f} 小时")


if __name__ == "__main__":
    main()
