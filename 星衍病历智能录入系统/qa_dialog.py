#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""知识问答对话框（全实体二级索引：疾病/药物/症状/检查均可点击展开）"""
import html as _html
import urllib.parse as _up
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                             QLineEdit, QTextEdit, QTextBrowser, QPushButton,
                             QSplitter, QTextEdit as _QTE)
from PyQt5.QtCore import Qt, QUrl
from PyQt5.QtGui import QDesktopServices


class KnowledgeQADialog(QDialog):
    def __init__(self, qa_engine=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("📚 知识问答")
        self.resize(800, 600)
        self.qa = qa_engine
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # 提示语
        hint = QLabel("💬 请输入问题，例如：\n  • 高血压的常见治疗方案\n  • 医师法第九条\n  • 医疗事故怎么鉴定\n  • 医疗事故的经典案例")
        hint.setStyleSheet("color: #99b; background: rgba(255,255,255,0.04); padding: 8px; border-radius: 6px; font-size: 12px;")
        layout.addWidget(hint)

        # 输入区
        inlay = QHBoxLayout()
        self.input_edit = QLineEdit()
        self.input_edit.setPlaceholderText("在此输入问题...")
        self.input_edit.returnPressed.connect(self._ask)
        ask_btn = QPushButton("❓ 提问")
        ask_btn.clicked.connect(self._ask)
        ask_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #00d4ff, stop:1 #007aa0);
                color: #0a0e27; padding: 6px 14px; border-radius: 8px; font-weight: bold;
            }
            QPushButton:hover { background: #00eaff; }
        """)
        inlay.addWidget(self.input_edit, 1)
        inlay.addWidget(ask_btn)
        layout.addLayout(inlay)

        # 回答区
        self.answer_browser = QTextBrowser()
        self.answer_browser.setOpenExternalLinks(False)
        self.answer_browser.setOpenLinks(False)
        self.answer_browser.anchorClicked.connect(self._on_link_clicked)
        self.answer_browser.setStyleSheet("""
            QTextBrowser {
                background: rgba(255,255,255,0.03); border: 1px solid rgba(0,212,255,0.15);
                border-radius: 8px; padding: 10px; font-size: 13px; color: #f0f0f0;
            }
            QTextBrowser a { color: #4dd9ff; text-decoration: none; border-bottom: 1px dashed #4dd9ff; }
        """)
        layout.addWidget(self.answer_browser, 1)

        # 快捷追问
        self.suggest_label = QLabel("")
        self.suggest_label.setStyleSheet("color: #788; font-size: 11px; margin-top: 4px; min-height: 18px;")
        layout.addWidget(self.suggest_label)

        # 取消按钮
        close_btn = QPushButton("✖ 关闭")
        close_btn.clicked.connect(self.reject)
        close_btn.setStyleSheet("QPushButton{padding:6px 12px;border-radius:6px;background:#555;color:#fff;}QPushButton:hover{background:#666;}")
        layout.addWidget(close_btn, 0)

        self.input_edit.setFocus()

    def _ask(self):
        q = (self.input_edit.text() or "").strip()
        if not q:
            self.input_edit.selectAll()
            return
        try:
            r = self.qa.answer(q)
            raw_text = r['text']
            html = self._build_linked_html(raw_text)
            self.answer_browser.setHtml(html)
            self.suggest_label.setText("💡 " + " | ".join(r.get("suggestions", []))[:150])
        except Exception as e:
            self.answer_browser.setHtml(f"⚠ 错误：<br>{str(e)}")
            self.suggest_label.setText("")

    # ─── 全实体链接化（二级索引）─────────────────────

    # 不应被链接的通用词
    _STOPWORDS = frozenset([
        '药物', '检查', '治疗', '手术', '护理', '预防', '诊断', '症状',
        '病因', '血压', '血糖', '血脂', '体温', '脉搏', '呼吸',
        '药物治疗', '支持性治疗', '手术治疗',
    ])

    def _build_linked_html(self, raw_text):
        """在原始文本上标记实体位置，然后统一生成 HTML（先标记后 escape，避免标签污染）"""
        if not self.qa:
            escaped = _html.escape(raw_text)
            return f"<pre style='white-space: pre-wrap; font-family: inherit;'>{escaped}</pre>"

        # 第1步：在原始文本上找所有实体位置
        # marks: [(start, end, scheme, icon)]
        marks = []
        occupied = set()  # 已被占用的字符位置

        # 预计算停用词在文本中的所有位置（用于后续验证）
        _sw_ranges = []
        for sw in self._STOPWORDS:
            idx = 0
            while True:
                idx = raw_text.find(sw, idx)
                if idx < 0:
                    break
                _sw_ranges.append((idx, idx + len(sw)))
                idx += 1

        def _overlaps_stopword(start, end):
            """检查实体匹配是否落在停用词区域内（被包含或重合）"""
            for sw_s, sw_e in _sw_ranges:
                # 实体匹配落在停用词范围内 → 拒绝
                if start >= sw_s and end <= sw_e:
                    return True
            return False

        def _try_mark(word, scheme, icon):
            if len(word) < 2:
                return
            # 过滤含标点/空格的脏数据实体
            if any(c in word for c in '，、。！？；：\n\r\t '):
                return
            if word in self._STOPWORDS:
                return
            idx = raw_text.find(word)
            if idx < 0:
                return
            end = idx + len(word)
            # 拒绝与停用词完全重合的匹配
            if _overlaps_stopword(idx, end):
                return
            span = range(idx, end)
            if any(p in occupied for p in span):
                return
            occupied.update(span)
            marks.append((idx, end, scheme, icon))

        # 按长度降序匹配
        if hasattr(self.qa, '_diseases_by_len'):
            for w in self.qa._diseases_by_len:
                if len(w) >= 3:
                    _try_mark(w, 'disease', '🏥')
        if hasattr(self.qa, '_drugs_by_len'):
            for w in self.qa._drugs_by_len:
                if len(w) >= 3:
                    _try_mark(w, 'drug', '💊')
        if hasattr(self.qa, '_exams_by_len'):
            for w in self.qa._exams_by_len:
                if len(w) >= 3:
                    _try_mark(w, 'exam', '🔬')
        if hasattr(self.qa, '_symptoms_by_len'):
            for w in self.qa._symptoms_by_len:
                if len(w) >= 2:
                    _try_mark(w, 'symptom', '🩺')

        # 第2步：按位置排序，拼接 HTML
        marks.sort(key=lambda x: x[0])
        parts = []
        pos = 0
        for start, end, scheme, icon in marks:
            if start < pos:
                continue  # 跳过重叠
            # escape 链接前的普通文本
            parts.append(_html.escape(raw_text[pos:start]))
            # 生成链接
            word = raw_text[start:end]
            href = f'{scheme}:///{_up.quote(word)}'
            parts.append(f'<a href="{href}">{_html.escape(word)} {icon}</a>')
            pos = end
        # 剩余文本
        parts.append(_html.escape(raw_text[pos:]))

        return f"<pre style='white-space: pre-wrap; font-family: inherit;'>{''.join(parts)}</pre>"

    def _on_link_clicked(self, url):
        """处理链接点击：根据 scheme 弹出对应详情"""
        link = url.toString()
        # 从 path 部分提取实体名（三个斜杠格式：scheme:///encoded_name）
        # QUrl.path() 返回 /encoded_name，去掉前导 /
        path = url.path()
        if path.startswith('/'):
            path = path[1:]
        name = _up.unquote(path).strip()
        if link.startswith('drug:'):
            self._show_drug_insert(name)
        elif link.startswith('disease:'):
            self._show_disease_detail(name)
        elif link.startswith('symptom:'):
            self._show_symptom_detail(name)
        elif link.startswith('exam:'):
            self._show_exam_detail(name)
        else:
            QDesktopServices.openUrl(url)

    # ─── 详情弹窗 ─────────────────────────────

    def _make_detail_dialog(self, title, icon, html_content):
        """通用详情弹窗"""
        dlg = QDialog(self)
        dlg.setWindowTitle(f"{icon} {title}")
        dlg.resize(600, 520)
        lay = QVBoxLayout(dlg)

        title_lbl = QLabel(f"{icon} {title}")
        title_lbl.setStyleSheet("font-size: 18px; font-weight: bold; color: #4dd9ff; margin-bottom: 6px;")
        lay.addWidget(title_lbl)

        body = QTextBrowser()
        body.setOpenExternalLinks(False)
        body.setOpenLinks(False)
        body.anchorClicked.connect(self._on_link_clicked)
        body.setStyleSheet("QTextBrowser{background:rgba(255,255,255,0.04);border:1px solid rgba(0,212,255,0.2);border-radius:8px;padding:10px;font-size:13px;color:#eef;}")
        body.setHtml(html_content)
        lay.addWidget(body, 1)

        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(dlg.accept)
        close_btn.setStyleSheet("QPushButton{padding:6px 16px;border-radius:6px;background:#3a5a6a;color:#fff;}QPushButton:hover{background:#4a7a8a;}")
        lay.addWidget(close_btn, 0, Qt.AlignRight)
        dlg.exec_()

    def _linkify_list(self, items, scheme, icon):
        """把列表中的实体名转为可点击链接"""
        parts = []
        for item in items:
            href = f'{scheme}:///{_up.quote(item)}'
            parts.append(f'<a href="{href}" style="color:#4dd9ff;">{item} {icon}</a>')
        return '、'.join(parts) if parts else '<span style="color:#889;">无</span>'

    def _show_drug_insert(self, drug_name):
        """药品说明书"""
        kg = getattr(self.qa, 'kg', None)
        info = kg.get_drug_info(drug_name) if kg else None
        parts = []
        if info and isinstance(info, dict):
            sections = [
                ("适应症", "🎯"), ("用法用量", "📋"), ("禁忌", "🚫"),
                ("不良反应", "⚠️"), ("注意事项", "📌"), ("主要成份", "🧪"),
                ("药物相互作用", "💫"), ("规格", "📐"), ("贮藏", "📦"),
            ]
            shown = set()
            for key, icon in sections:
                val = info.get(key, "")
                if val:
                    parts.append(f"<p style='color:#4dd9ff;font-weight:bold;margin:10px 0 2px;'>{icon} {key}</p>"
                                 f"<p style='color:#e8e8f0;margin:0 0 8px;'>{_html.escape(str(val))}</p>")
                    shown.add(key)
            for k, v in info.items():
                if k not in shown and v:
                    parts.append(f"<p style='color:#4dd9ff;font-weight:bold;margin:10px 0 2px;'>{k}</p>"
                                 f"<p style='color:#e8e8f0;margin:0 0 8px;'>{_html.escape(str(v))}</p>")
        else:
            parts.append("<p style='color:#aab;'>该药品暂无收录说明书。</p>")
        # 关联疾病（反向查询：疾病→TREATED_BY→药物，所以用 obj 查）
        if kg:
            treats = kg.query_by_obj(drug_name, "TREATED_BY")[:15]
            if not treats:
                treats = kg.query_by_subj(drug_name, "TREATS")[:15]
            if treats:
                parts.append(f"<p style='color:#4dd9ff;font-weight:bold;margin:12px 0 2px;'>🏥 关联疾病</p>"
                             f"<p style='color:#e8e8f0;'>{self._linkify_list(treats, 'disease', '🏥')}</p>")
        self._make_detail_dialog(drug_name, "💊", "".join(parts) or "暂无数据")

    def _show_disease_detail(self, disease_name):
        """疾病详情：简介/症状/检查/用药/并发症/科室/饮食"""
        kg = getattr(self.qa, 'kg', None)
        parts = []
        if kg:
            entity = kg.entities.get(disease_name, {})
            # 疾病简介
            desc = entity.get('描述', '')
            system = entity.get('系统', '')
            if system:
                parts.append(f"<p style='color:#889;font-size:12px;margin:0 0 4px;'>🏷 所属系统：{system}</p>")
            if desc:
                parts.append(f"<p style='color:#e8e8f0;margin:4px 0 10px;line-height:1.6;'>📖 {desc}</p>")

            symptoms = kg.get_symptoms_for_disease(disease_name)
            drugs = kg.get_drugs_for_disease(disease_name)
            exams = kg.get_exams_for_disease(disease_name)
            complicates = kg.query_by_subj(disease_name, "COMPLICATES")[:10]
            dept = kg.query_by_subj(disease_name, "BELONGS_TO")[:3]
            cure_way = entity.get('治疗方式', [])
            diet = kg.get_diet_for_disease(disease_name) if hasattr(kg, 'get_diet_for_disease') else {}

            if dept:
                parts.append(f"<p style='color:#4dd9ff;font-weight:bold;margin:8px 0 2px;'>🏨 就诊科室</p>"
                             f"<p style='color:#e8e8f0;'>{'、'.join(dept)}</p>")
            if cure_way:
                parts.append(f"<p style='color:#4dd9ff;font-weight:bold;margin:8px 0 2px;'>💉 治疗方式</p>"
                             f"<p style='color:#e8e8f0;'>{'、'.join(cure_way)}</p>")
            if symptoms:
                parts.append(f"<p style='color:#4dd9ff;font-weight:bold;margin:8px 0 2px;'>🩺 常见症状</p>"
                             f"<p style='color:#e8e8f0;'>{self._linkify_list(symptoms[:15], 'symptom', '🩺')}</p>")
            if exams:
                parts.append(f"<p style='color:#4dd9ff;font-weight:bold;margin:8px 0 2px;'>🔬 常见检查</p>"
                             f"<p style='color:#e8e8f0;'>{self._linkify_list(exams[:15], 'exam', '🔬')}</p>")
            if drugs:
                parts.append(f"<p style='color:#4dd9ff;font-weight:bold;margin:8px 0 2px;'>💊 常用药物</p>"
                             f"<p style='color:#e8e8f0;'>{self._linkify_list(drugs[:15], 'drug', '💊')}</p>")
            if complicates:
                parts.append(f"<p style='color:#4dd9ff;font-weight:bold;margin:8px 0 2px;'>⚠️ 并发疾病</p>"
                             f"<p style='color:#e8e8f0;'>{self._linkify_list(complicates, 'disease', '🏥')}</p>")
            if diet:
                if diet.get('宜吃'):
                    parts.append(f"<p style='color:#4dd9ff;font-weight:bold;margin:8px 0 2px;'>✅ 宜吃</p>"
                                 f"<p style='color:#e8e8f0;'>{'、'.join(diet['宜吃'][:10])}</p>")
                if diet.get('忌吃'):
                    parts.append(f"<p style='color:#4dd9ff;font-weight:bold;margin:8px 0 2px;'>❌ 忌吃</p>"
                                 f"<p style='color:#e8e8f0;'>{'、'.join(diet['忌吃'][:10])}</p>")
        if not parts:
            parts.append("<p style='color:#aab;'>暂无该疾病的详细信息。</p>")
        self._make_detail_dialog(disease_name, "🏥", "".join(parts))

    def _show_symptom_detail(self, symptom_name):
        """症状详情：解释 + 关联疾病"""
        kg = getattr(self.qa, 'kg', None)
        parts = []
        # 症状解释（模板生成）
        parts.append(f"<p style='color:#e8e8f0;margin:4px 0 10px;line-height:1.6;'>"
                     f"📖 「{symptom_name}」是患者主观感受到的不适表现，"
                     f"可能提示多种疾病，需结合其他症状和检查综合判断。</p>")
        if kg:
            diseases = kg.query_by_subj(symptom_name, "INDICATES")[:20]
            if not diseases:
                diseases = kg.query_by_obj(symptom_name, "HAS_SYMPTOM")[:20]
            if diseases:
                parts.append(f"<p style='color:#4dd9ff;font-weight:bold;margin:8px 0 2px;'>🏥 可能相关疾病（点击查看详情）</p>"
                             f"<p style='color:#e8e8f0;'>{self._linkify_list(diseases, 'disease', '🏥')}</p>")
        if len(parts) == 1:
            parts.append(f"<p style='color:#aab;'>暂无「{symptom_name}」的更多关联信息。</p>")
        self._make_detail_dialog(symptom_name, "🩺", "".join(parts))

    def _show_exam_detail(self, exam_name):
        """检查项目详情：解释 + 关联疾病"""
        kg = getattr(self.qa, 'kg', None)
        parts = []
        # 检查解释（模板生成）
        parts.append(f"<p style='color:#e8e8f0;margin:4px 0 10px;line-height:1.6;'>"
                     f"📖 「{exam_name}」是临床常用的辅助检查手段，"
                     f"用于评估相关器官功能或排查病变，具体结果需结合临床综合判断。</p>")
        if kg:
            diseases = kg.query_by_obj(exam_name, "HAS_EXAM")[:20]
            if diseases:
                parts.append(f"<p style='color:#4dd9ff;font-weight:bold;margin:8px 0 2px;'>🏥 相关疾病（常需此检查）</p>"
                             f"<p style='color:#e8e8f0;'>{self._linkify_list(diseases, 'disease', '🏥')}</p>")
        if len(parts) == 1:
            parts.append(f"<p style='color:#aab;'>暂无「{exam_name}」的更多关联信息。</p>")
        self._make_detail_dialog(exam_name, "🔬", "".join(parts))

    def set_question_and_ask(self, question):
        """设置问题并立即提问（外部可调用）"""
        self.input_edit.setText(question)
        self._ask()
