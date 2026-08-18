"""
WebViewApp —— 基于 QWebEngineView 的新版主界面（从 main.py 拆分）
"""
import os
import re
import sys
import json
import time
import subprocess
import html as _html

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QMessageBox, QToolButton,
    QAction, QMenu, QDialog, QInputDialog, QToolBar,
    QStatusBar,
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QThread
from PyQt5.QtGui import QFont, QColor, QPalette

from corrector import Corrector
from asr_engine import ASREngine
from template_engine import TemplateEngine
from section_parser import SectionParser
from medical_classifier import MedicalClassifier
from knowledge_qa import KnowledgeQA
from correction_feedback import CorrectionFeedback
from crash_logger import CrashLogger
from voice_command import VoiceCommandParser
from diagnosis_assistant import DiagnosisAssistant
from threads import create_listen_thread, stop_listen_thread, DiagnosisThread
from correction_memory import get_memory
from topk_engine import get_topk_engine

from gui.dialogs import TemplateManagerDialog
from webview_bridge import WebViewMain


class WebViewApp(QMainWindow):
    """基于 QWebEngineView 的新版主界面"""

    def __init__(self, db=None, current_user=None):
        super().__init__()
        self.db = db
        self.current_user = current_user or {}
        self.current_record_id = None
        self.current_dept = "通用"
        self._current_field = "主诉"
        self.is_listening = False
        self._record_start_ts = None
        self._auto_stop_timer = None

        uname = self.current_user.get("username", "")
        title = "星衍AI · 智能病历录入"
        if uname:
            title += f"  |  {uname}"
        self.setWindowTitle(title)
        self.setGeometry(80, 60, 1400, 900)

        # 核心引擎
        # 直接初始化所有引擎（WebViewApp 不使用 RuleEngine 对话框）
        from rule_engine import RuleEngine
        self.rule_engine = RuleEngine()
        self.corrector = Corrector(rule_engine=self.rule_engine)
        self.template_engine = TemplateEngine()
        self.parser = SectionParser()
        self.classifier = MedicalClassifier()
        self.qa_engine = KnowledgeQA()
        self.feedback = CorrectionFeedback()
        self.crash_logger = CrashLogger()
        self.crash_logger.log_event("应用启动(WebView)")
        self.voice_command = VoiceCommandParser()

        # ASR
        model_path = os.path.join(os.path.dirname(__file__), "model")
        self.asr = ASREngine(model_path=model_path)
        self.listen_thread = None

        # 常用句
        self._presets_path = os.path.join(os.path.dirname(__file__), "field_presets.json")
        self._presets_data = {}
        self._load_presets()
        self._asr_preview_timer = None

        # WebView
        self.webview = WebViewMain(self)
        self.setCentralWidget(self.webview)

        # 连接桥接信号
        br = self.webview.bridge
        br.sig_rec_toggle.connect(self._toggle_recording)
        br.sig_save.connect(self._save_record)
        br.sig_qa.connect(self._show_qa)
        br.sig_qa_ask.connect(self._on_qa_ask)
        br.sig_qa_close.connect(self.webview.js_close_qa)
        br.sig_template_mgr.connect(self._open_template_manager)
        br.sig_retrain.connect(self._retrain_lm)
        br.sig_dept_changed.connect(self._on_dept_changed)
        br.sig_template_changed.connect(self._on_template_changed)
        br.sig_field_changed.connect(self._on_field_changed)
        br.sig_editor_changed.connect(self._on_editor_changed)
        br.sig_chip_click.connect(self._on_chip_click)
        br.sig_preset_click.connect(self._on_preset_click)
        br.sig_add_preset.connect(self._on_add_preset)
        br.sig_asr_accept.connect(self._on_asr_accept)
        br.sig_asr_reject.connect(self._on_asr_reject)
        br.sig_asr_retry.connect(self._on_asr_retry)

        # 录音计时
        self._duration_timer = QTimer(self)
        self._duration_timer.setInterval(1000)
        self._duration_timer.timeout.connect(self._update_rec_time)
        self._rec_seconds = 0

        # 延迟初始化 UI 数据
        self.webview.set_on_ready(self._init_webview_data)
        self._recent_history_opened = False

    # ─── 初始化 ─────────────────────────────────────────

    def _load_presets(self):
        try:
            with open(self._presets_path, 'r', encoding='utf-8') as f:
                self._presets_data = json.load(f)
        except Exception:
            self._presets_data = {}

    def _save_presets(self):
        with open(self._presets_path, 'w', encoding='utf-8') as f:
            json.dump(self._presets_data, f, ensure_ascii=False, indent=2)

    def _init_webview_data(self):
        depts = ["内科", "外科", "妇产科", "儿科", "全科"]
        self.webview.js_set_depts(depts)
        self._refresh_templates()
        self._on_template_changed("入院记录")
        fields = ["主诉", "现病史", "既往史", "个人史", "婚育史", "家族史",
                  "体格检查", "辅助检查", "初步诊断", "诊疗计划"]
        self.webview.js_set_fields(fields, "主诉")
        try:
            hw = len(self.asr._current_hotwords.split()) if self.asr._current_hotwords else 0
            kg_count = len(self.qa_engine.kg.entities) if self.qa_engine.kg else 0
            drug_count = len(self.qa_engine.kg.drug_inserts) if self.qa_engine.kg else 0
            self.webview.js_set_stats(str(hw), str(kg_count), str(drug_count))
        except Exception as e:
            print(f"[WebView] 状态栏更新失败: {e}")
        try:
            self._show_history()
        except Exception as e:
            print(f"[WebView] 历史加载失败: {e}")
        self.corrector.set_department("通用")
        self.asr.set_hotwords("通用")
        self._update_context_panel("主诉")
        self._show_startup_checks()

    def _dept_for_templates(self):
        dept = self.current_dept
        if dept in ("通用", "全科"):
            return "内科"
        return dept

    def _refresh_templates(self):
        dept = self._dept_for_templates()
        tpls = self.template_engine.get_templates(dept)
        tpl_names = [t["name"] for t in tpls]
        self.webview.js_set_templates(tpl_names)

    def _update_context_panel(self, field):
        fw_path = os.path.join(os.path.dirname(__file__), "..", "field_words.json")
        fw_path = os.path.normpath(fw_path)
        sections = []
        try:
            with open(fw_path, 'r', encoding='utf-8') as f:
                fw = json.load(f)
            field_data = fw.get(field, {})
            terms = field_data.get("terms", {})
            if isinstance(terms, dict):
                for cat, words in terms.items():
                    sections.append({"title": cat, "words": words[:12]})
            elif isinstance(terms, list):
                sections.append({"title": "常用词", "words": terms[:15]})
        except Exception as e:
            print(f"[WebView] 加载 field_words 失败: {e}")
        presets = self._presets_data.get(field, [])
        self.webview.js_set_context_panel(f"常用词 · {field}", sections, presets)

    # ─── 桥接信号处理 ─────────────────────────────────────────

    def _toggle_recording(self):
        if self.is_listening:
            self._stop_recording()
        else:
            self._start_recording()

    def _start_recording(self):
        self.is_listening = True
        self._rec_seconds = 0
        self._record_start_ts = time.time()
        self._duration_timer.start()
        self.webview.js_set_recording(True, "主诉", "00:00")
        self.listen_thread = create_listen_thread(
            self.asr,
            on_text_ready=self._on_recognized,
            on_partial=self._on_partial,
            on_stream_error=self._on_asr_stream_error if hasattr(self, '_on_asr_stream_error') else None,
        )
        self.listen_thread.start()

    def _stop_recording(self):
        self.is_listening = False
        self._duration_timer.stop()
        self.webview.js_set_recording(False)
        stop_listen_thread(self.listen_thread, timeout_ms=3000)
        try:
            QTimer.singleShot(3000, lambda: self.webview.js_set_asr_preview(""))
        except Exception as e:
            print(f"[WebView] 清除预览失败: {e}")

    def _update_rec_time(self):
        self._rec_seconds += 1
        m, s = divmod(self._rec_seconds, 60)
        self.webview.js_set_recording(True, "", f"{m:02d}:{s:02d}")

    def _on_recognized(self, text):
        if not text:
            return
        self._last_asr_preview_text = text
        try:
            self.webview.js_set_asr_preview(text)
            self.webview.js_set_asr_actions(True)
        except Exception as e:
            print(f"[ASR] 预览更新失败: {e}")
        cmd, arg = self.voice_command.parse(text)
        if cmd == "stop_record":
            self._stop_recording()
            return
        if cmd == "save":
            self._save_record()
            return
        self._fill_and_update(text)
        try:
            if self._asr_preview_timer is not None:
                self._asr_preview_timer.stop()
            self._asr_preview_timer = QTimer(self)
            self._asr_preview_timer.setSingleShot(True)
            self._asr_preview_timer.timeout.connect(lambda: self.webview.js_set_asr_preview(""))
            self._asr_preview_timer.timeout.connect(lambda: self.webview.js_set_asr_actions(False))
            self._asr_preview_timer.start(2500)
        except Exception as e:
            print(f"[ASR] 预览延时清空失败: {e}")

    def _on_asr_stream_error(self, msg):
        """ASR 流式识别恢复状态回调"""
        if not msg:
            return
        if "连续失败" in msg or "熔断" in msg:
            self.webview.js_show_toast(msg)
        elif "恢复" in msg:
            self.webview.js_show_toast(msg)
        else:
            self.webview.js_show_toast(msg)

    def _fill_and_update(self, asr_text):
        try:
            base = getattr(self, '_last_editor_text', '') or ''
            if not base:
                dept = self._dept_for_templates()
                tpls = self.template_engine.get_templates(dept)
                if tpls:
                    base = tpls[0].get('content', '')
            if not base:
                print(f"[Fill] 无模板兜底，直接插入: {asr_text[:50]}")
                self.webview.js_insert_text(asr_text)
                return
            inferred = self.classifier.extract_basic_fields(asr_text)
            print(f"[Fill] 识别文本: {asr_text[:80]}")
            print(f"[Fill] base首行: {base.splitlines()[0] if base else '(空)'!r}")
            print(f"[Fill] 推断字段: {inferred}")
            filled = self.classifier.incremental_fill(asr_text, base)
            if filled != base:
                html = self._text_to_editor_html(filled)
                self.webview.js_set_content(html)
                self._last_editor_text = filled
                print("[Fill] ✓ 填充完成，已更新编辑器")
            else:
                print("[Fill] ⚠ 填充无变化，降级为直接插入")
                self.webview.js_insert_text(asr_text)
        except Exception as e:
            import traceback
            print(f"[Fill] error: {e}")
            traceback.print_exc()
            self.webview.js_insert_text(asr_text)

    def _on_partial(self, text):
        if not text:
            return
        try:
            if self._asr_preview_timer is not None:
                self._asr_preview_timer.stop()
                self._asr_preview_timer = None
            self.webview.js_set_asr_preview(text)
        except Exception as e:
            print(f"[ASR] 预览更新失败: {e}")

    def _on_editor_changed(self, text):
        self._last_editor_text = text
        try:
            alerts = self.rule_engine.realtime_checks(text, dept=self.current_dept, field=getattr(self, '_current_field', ''))
            self.webview.js_set_qc_status(len(alerts))
        except Exception as e:
            print(f"[WebView] 实时质控检查失败: {e}")
        print(f"[Editor] 内容同步: {len(text)}字")

    def _save_record(self):
        text = getattr(self, '_last_editor_text', '')
        if not text:
            self.webview.get_editor_text(self._do_save)
        else:
            self._do_save(text)

    def _do_save(self, text):
        if not text or not text.strip():
            self.webview.js_show_toast("没有内容可保存")
            return
        if not self.db or not self.current_user:
            self.webview.js_show_toast("未登录")
            return
        content = text.strip()
        patient_name = ""
        m = re.search(r'姓名[：:]\s*([^\s　\n]{1,10})', content)
        if m:
            patient_name = m.group(1).strip()
        dept = self.current_dept if self.current_dept != "通用" else ""
        if self.current_record_id is None:
            self.current_record_id = self.db.create_record(
                self.current_user["id"], patient_name, dept, "", content, "草稿"
            )
            self.webview.js_show_toast("\U0001f4be 病历已保存")
        else:
            self.db.update_record(self.current_record_id, content=content)
            self.webview.js_show_toast("💾 病历已更新")
        try:
            self.feedback.collect_corpus(content)
        except Exception as e:
            print(f"[WebView] 语料收集失败: {e}")

    def _show_qa(self):
        self._show_qa_for_selection()

    def _on_qa_ask(self, question):
        try:
            question = (question or '').strip()
            if not question:
                return
            result = self.qa_engine.answer(question)
            answer_text = result.get('text', '') if isinstance(result, dict) else str(result)
            html_text = _html.escape(answer_text or '未找到相关知识，请换个问法试试。')
            html_text = html_text.replace('\n', '<br>')
            self.webview.js_set_qa(f'<b>问：{_html.escape(question)}</b><br><br>{html_text}')
            print(f"[QA] 提问: {question[:40]} -> 回答{len(answer_text)}字")
        except Exception as e:
            print(f"[QA] 提问处理失败: {e}")

    def _show_qa_dialog(self):
        try:
            from qa_dialog import KnowledgeQADialog
            dlg = KnowledgeQADialog(self.qa_engine, self)
            dlg.exec_()
        except Exception as e:
            QMessageBox.warning(self, "问答错误", f"知识问答模块加载失败：\n{e}")

    def _show_history(self):
        try:
            if not self.db:
                self.webview.js_set_history('数据库未初始化')
                return
            user_id = self.current_user.get("id") if isinstance(self.current_user, dict) else None
            records = self.db.list_records(user_id=user_id, limit=20)
            if not records:
                self.webview.js_set_history('暂无最近病历')
                return
            lines = []
            for rec in records[:8]:
                title = rec.get('patient_name') or ('病历#' + str(rec.get('record_id')))
                snippet = (rec.get('content') or '').strip().splitlines()[0]
                lines.append(f"{title}：{snippet}")
            self.webview.js_set_history('<br>'.join(lines))
        except Exception as e:
            print(f"[History] 失败: {e}")

    def _show_startup_checks(self):
        try:
            checks = []
            if not self.asr.is_ready():
                checks.append("ASR 模型未就绪，请检查模型目录")
            hw = len(self.asr._current_hotwords.split()) if self.asr._current_hotwords else 0
            if hw < 10:
                checks.append("当前热词较少，建议先做 Top-K 刷新")
            if self.rule_engine.get_stats().get("错别字规则数", 0) < 5:
                checks.append("纠错规则较少，建议补充 postprocess 规则")
            if checks:
                self.webview.js_show_toast("；".join(checks[:3]))
        except Exception as e:
            print(f"[Check] 失败: {e}")

    def _open_template_manager(self):
        dlg = TemplateManagerDialog(self.template_engine, self.current_dept, self)
        if dlg.exec_() == QDialog.Accepted:
            self._refresh_templates()

    def _retrain_lm(self):
        import subprocess
        reply = QMessageBox.question(self, "重训语言模型",
            "将合并用户语料+纠错反馈重训 3-gram 模型。\n开始？",
            QMessageBox.Yes | QMessageBox.No)
        if reply != QMessageBox.Yes:
            return
        script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "train_lm.py")
        try:
            subprocess.run([sys.executable, script], capture_output=True, text=True, timeout=120,
                          cwd=os.path.dirname(os.path.abspath(__file__)))
            self.webview.js_show_toast("\U0001f9e0 语言模型重训完成，重启后生效")
        except Exception as e:
            self.webview.js_show_toast(f"重训失败: {e}")

    def _on_dept_changed(self, dept):
        self.current_dept = dept
        self.corrector.set_department(dept)
        self.asr.set_hotwords(dept)
        self._refresh_templates()

    def _on_template_changed(self, tpl_name):
        dept = self._dept_for_templates()
        content = self.template_engine.get_template(dept, tpl_name)
        if content:
            html = self._text_to_editor_html(content)
            self.webview.js_set_content(html)
            self._last_editor_text = content

    def _on_field_changed(self, field):
        self._current_field = field
        self._update_context_panel(field)
        self.asr.set_field_context(field)
        self._refresh_field_hotwords(field)

    def _refresh_field_hotwords(self, field):
        try:
            topk = self._get_topk_engine()
            if not topk or not field:
                return
            prompt_pack = topk.build_field_prompt_pack(
                field=field, dept=self.current_dept,
                doctor_id=self.current_user.get("id") if isinstance(self.current_user, dict) else None,
                top_k=220
            )
            self.asr.set_prompt_pack(prompt_pack)
            self.asr.apply_prompt_pack()
            self.asr.set_hotwords(self.current_dept)
        except Exception as e:
            print(f"[Main] 刷新字段级热词失败: {e}")

    def _on_chip_click(self, word):
        self.webview.js_insert_text(word)

    def _on_preset_click(self, sentence):
        self.webview.js_insert_text(sentence)

    def _on_add_preset(self):
        text, ok = QInputDialog.getMultiLineText(self, "添加常用句", "请输入常用句：", "")
        if ok and text.strip():
            field = self._current_field
            if field not in self._presets_data:
                self._presets_data[field] = []
            if text.strip() not in self._presets_data[field]:
                self._presets_data[field].append(text.strip())
                self._save_presets()
            self._update_context_panel(field)

    @staticmethod
    def _text_to_editor_html(text):
        fields = ['姓名', '性别', '年龄', '民族', '婚姻状况', '出生地', '职业',
                  '入院时间', '入院方式', '病史陈述者', '可靠程度', '主诉', '现病史',
                  '既往史', '个人史', '婚育史', '家族史', '体格检查', '辅助检查',
                  '初步诊断', '鉴别诊断', '诊疗计划', '诊疗经过', '出院情况', '出院医嘱',
                  '术前诊断', '手术名称', '术中情况', '术后诊断', '术后医嘱']
        escaped = _html.escape(text)
        for f in fields:
            pattern = re.escape(f) + r'[：:]'
            escaped = re.sub(pattern, f'<span class="fl">{f}：</span>', escaped)
        escaped = escaped.replace('\n', '<br>')
        return escaped

    def _on_asr_accept(self):
        try:
            text = getattr(self, '_last_asr_preview_text', '') or ''
            if text:
                self.webview.js_insert_text(text)
            self.webview.js_set_asr_preview('')
            self.webview.js_set_asr_actions(False)
            self._last_asr_preview_text = ''
        except Exception as e:
            print(f"[ASR] 接受预览失败: {e}")

    def _on_asr_reject(self):
        try:
            self.webview.js_set_asr_preview('')
            self.webview.js_set_asr_actions(False)
            self._last_asr_preview_text = ''
        except Exception as e:
            print(f"[ASR] 拒绝预览失败: {e}")

    def _on_asr_retry(self):
        try:
            self._stop_recording()
            self.webview.js_set_asr_preview('')
            self.webview.js_set_asr_actions(False)
            self._last_asr_preview_text = ''
            self._toggle_recording()
        except Exception as e:
            print(f"[ASR] 重试失败: {e}")

    def _show_qa_for_selection(self):
        try:
            text = getattr(self, '_last_editor_text', '') or ''
            if not text:
                self.webview.get_editor_text(lambda t: self._do_show_qa(t or ''))
                return
            self._do_show_qa(text)
        except Exception as e:
            print(f"[QA] 失败: {e}")

    def _do_show_qa(self, text):
        try:
            suggestions = self._build_qa_suggestions(text)
            print(f"[QA] 文本{len(text)}字 -> 提示{len(suggestions)}字")
            self.webview.js_set_qa(suggestions)
        except Exception as e:
            print(f"[QA] 构建提示失败: {e}")

    def _build_qa_suggestions(self, text):
        stripped = text or ''
        for f in self.classifier.STANDARD_FIELDS:
            stripped = stripped.replace(f, '')
        stripped = re.sub(r'[：:\s，,。、；;（）()]+', '', stripped)
        if len(stripped) < 4:
            return ('当前病历还没有实质内容。<br>'
                    '语音或打字填入内容后，这里会自动提示<b>可能疾病、用药、检查、质控提醒</b>。'
                    '<br><br>例：录入"患者男性，56岁，主诉胸痛2小时，'
                    '初步诊断冠心病"后再按 ⌘/ 试试。')
        items = []
        try:
            diseases = self.qa_engine.extract_diseases(text)[:5]
            if diseases:
                items.append('<b>可能疾病</b>：' + '、'.join(diseases))
        except Exception as e:
            print(f"[QA] 疾病提取失败: {e}")
        try:
            drugs = self.qa_engine.extract_drugs(text)[:8]
            if drugs:
                items.append('<b>用药</b>：' + '、'.join(drugs))
        except Exception as e:
            print(f"[QA] 用药提取失败: {e}")
        try:
            exams = self.qa_engine.extract_exams(text)[:8]
            if exams:
                items.append('<b>检查</b>：' + '、'.join(exams))
        except Exception as e:
            print(f"[QA] 检查提取失败: {e}")
        try:
            alerts = self.rule_engine.realtime_checks(text, dept=self.current_dept, field=getattr(self, '_current_field', ''))[:8]
            if alerts:
                items.append('<b>质控提醒</b>：<br>' + '<br>'.join([a.get('message','') for a in alerts]))
        except Exception as e:
            print(f"[QA] 质控检查失败: {e}")
        return '<br><br>'.join(items) if items else '已扫描病历文本，未命中知识图谱中的疾病/药品/检查实体。'

    def _get_memory(self):
        if not hasattr(self, '_memory'):
            self._memory = None
        if self._memory is None:
            try:
                self._memory = get_memory()
            except Exception as e:
                print(f"[Memory] 初始化失败: {e}")
        return self._memory

    def _get_topk_engine(self):
        if not hasattr(self, '_topk_engine'):
            self._topk_engine = None
        if self._topk_engine is None:
            try:
                self._topk_engine = get_topk_engine(memory=self._get_memory())
            except Exception as e:
                print(f"[TopK] 初始化失败: {e}")
        return self._topk_engine

    def closeEvent(self, event):
        if self.is_listening:
            self._stop_recording()
        if hasattr(self, 'asr') and self.asr:
            try:
                self.asr.stop_listening()
            except Exception:
                pass
        super().closeEvent(event)
