"""
星衍AI智能病历录入系统 - Demo 版本
无需 Vosk 模型，界面演示版
"""
import sys
import os

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QTextEdit, QComboBox, QLabel, QSplitter,
    QListWidget, QListWidgetItem, QStatusBar, QToolBar,
    QMessageBox, QFileDialog, QProgressBar
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QThread
from PyQt5.QtGui import QFont, QColor, QPalette

# 模拟纠错引擎（不需要 JSON 文件）
class DemoCorrector:
    def __init__(self):
        self.current_dept = "通用"
        self.active_words = set()
        # 内置一些通用词
        self.active_words.update([
            "发热", "咳嗽", "咳痰", "咯血", "胸痛", "呼吸困难",
            "腹痛", "腹泻", "恶心", "呕吐", "头痛", "头晕",
            "血压", "心率", "呼吸", "体温", "脉搏",
            "血常规", "尿常规", "心电图", "胸片", "CT", "MRI", "B超",
            "肺炎", "支气管炎", "哮喘", "高血压", "冠心病",
            "胃炎", "胃溃疡", "糖尿病", "甲亢", "甲减",
            "阿莫西林", "头孢曲松", "左氧氟沙星", "阿司匹林",
            "氯吡格雷", "氨氯地平", "二甲双胍", "奥美拉唑",
            "布洛芬", "对乙酰氨基酚"
        ])

    def set_department(self, dept):
        self.current_dept = dept
        self.active_words = set([
            "发热", "咳嗽", "咳痰", "咯血", "胸痛", "呼吸困难",
            "腹痛", "腹泻", "恶心", "呕吐", "头痛", "头晕",
            "血压", "心率", "呼吸", "体温", "脉搏",
            "血常规", "尿常规", "心电图", "胸片", "CT", "MRI", "B超",
            "肺炎", "支气管炎", "哮喘", "高血压", "冠心病",
            "胃炎", "胃溃疡", "糖尿病", "甲亢", "甲减",
            "阿莫西林", "头孢曲松", "左氧氟沙星", "阿司匹林",
            "氯吡格雷", "氨氯地平", "二甲双胍", "奥美拉唑",
            "布洛芬", "对乙酰氨基酚"
        ])

    def correct(self, text):
        log = []
        result = text
        # 模拟一些纠错
        corrections = {
            "yanzheng": "炎症",
            "3c": "3℃",
            "血相": "血常规",
            "拍个片": "影像学检查",
            "消炎药": "抗生素",
            "打点滴": "静脉输液",
            "头炮": "头孢",
            "心电围": "心电图",
        }
        for wrong, correct in corrections.items():
            if wrong in result:
                result = result.replace(wrong, correct)
                log.append({
                    "type": "词典纠错",
                    "原文": wrong,
                    "修正": correct,
                    "级别": "建议"
                })
        return result, log


# 模拟模板引擎
class DemoTemplateEngine:
    def __init__(self):
        self.templates = {
            "内科": [
                {"name": "入院记录", "content": "主诉：\n现病史：\n既往史：\n体格检查：\n辅助检查：\n初步诊断：\n"},
                {"name": "病程记录", "content": "日期：\n患者情况：\n处理意见：\n"},
                {"name": "出院记录", "content": "入院日期：\n出院日期：\n住院天数：\n入院诊断：\n出院诊断：\n诊疗经过：\n出院情况：\n出院医嘱：\n"},
            ],
            "外科": [
                {"name": "术前记录", "content": "术前诊断：\n手术名称：\n手术指征：\n术前准备：\n手术医师：\n麻醉方式：\n"},
                {"name": "手术记录", "content": "手术日期：\n手术名称：\n术中所见：\n手术过程：\n术中出血：\n术后诊断：\n"},
                {"name": "术后病程", "content": "术后诊断：\n手术情况：\n术后第一天：\n术后医嘱：\n"},
            ],
            "影像科": [
                {"name": "CT检查报告", "content": "检查项目：\n影像表现：\n诊断意见：\n建议：\n"},
                {"name": "MRI检查报告", "content": "检查项目：\n影像表现：\n诊断意见：\n建议：\n"},
            ],
            "急诊": [
                {"name": "急诊病历", "content": "主诉：\n现病史：\n既往史：\n体格检查：\n辅助检查：\n初步诊断：\n急救措施：\n"},
                {"name": "抢救记录", "content": "抢救时间：\n患者情况：\n抢救措施：\n用药情况：\n效果评估：\n"},
            ]
        }

    def get_departments(self):
        return list(self.templates.keys())

    def get_templates(self, department):
        return self.templates.get(department, [])

    def get_template(self, department, template_name):
        templates = self.get_templates(department)
        for t in templates:
            if t["name"] == template_name:
                return t["content"]
        return ""


# ==================== 模拟识别线程 ====================
class MockListenThread(QThread):
    text_ready = pyqtSignal(str)
    partial_text = pyqtSignal(str)
    status_changed = pyqtSignal(str)
    progress = pyqtSignal(int)

    def __init__(self):
        super().__init__()
        self.sample_texts = [
            "患者发热三天，体温最高38.5℃，伴有咳嗽咳痰，痰为白色粘液痰。",
            "胸痛两小时，呈压榨性疼痛，向左肩放射，伴有出汗，心电图提示ST段抬高。",
            "腹痛六小时，呈阵发性绞痛，伴有恶心呕吐，B超提示胆囊结石。",
            "头颅CT示右侧基底节区高密度影，考虑脑出血，建议进一步MRI检查。",
            "患者糖尿病病史十年，现血糖控制不佳，建议调整降糖方案。",
        ]

    def run(self):
        import random
        self.status_changed.emit("正在录音...")
        self.progress.emit(0)

        text = random.choice(self.sample_texts)
        chars = list(text)

        for i, char in enumerate(chars):
            self.msleep(80)
            self.partial_text.emit("".join(chars[:i+1]))
            self.progress.emit(int((i+1) / len(chars) * 100))

        self.text_ready.emit(text)
        self.status_changed.emit("识别完成")


class MockCorrectThread(QThread):
    correction_done = pyqtSignal(str, list)

    def __init__(self, corrector, text):
        super().__init__()
        self.corrector = corrector
        self.text = text

    def run(self):
        import time
        time.sleep(0.5)
        corrected, log = self.corrector.correct(self.text)
        self.correction_done.emit(corrected, log)


# ==================== 主窗口 ====================
class MedVoiceApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("星衍AI智能病历录入系统 v1.0 (Demo)")
        self.setGeometry(100, 100, 1200, 800)

        self.corrector = DemoCorrector()
        self.template_engine = DemoTemplateEngine()
        self.is_listening = False
        self.listen_thread = None
        self.current_dept = "通用"

        self._init_ui()
        self._apply_dark_theme()
        self._load_departments()
        self.corrector.set_department("通用")

    def _init_ui(self):
        toolbar = QToolBar()
        self.addToolBar(toolbar)

        toolbar.addWidget(QLabel("  科室："))
        self.dept_combo = QComboBox()
        self.dept_combo.setMinimumWidth(120)
        self.dept_combo.currentTextChanged.connect(self._on_dept_changed)
        toolbar.addWidget(self.dept_combo)

        toolbar.addSeparator()

        toolbar.addWidget(QLabel("  模板："))
        self.template_combo = QComboBox()
        self.template_combo.setMinimumWidth(160)
        self.template_combo.currentTextChanged.connect(self._on_template_changed)
        toolbar.addWidget(self.template_combo)

        toolbar.addSeparator()

        self.record_btn = QPushButton("🎤 开始录音 (Demo)")
        self.record_btn.setCheckable(True)
        self.record_btn.clicked.connect(self._toggle_recording)
        self.record_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #00d4ff, stop:1 #0066ff);
                color: #0a0e27;
                font-weight: bold;
                padding: 8px 20px;
                border-radius: 20px;
                font-size: 14px;
            }
            QPushButton:checked {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #ff4444, stop:1 #cc0000);
                color: white;
            }
            QPushButton:hover {
                padding: 8px 25px;
            }
        """)
        toolbar.addWidget(self.record_btn)

        toolbar.addSeparator()

        correct_btn = QPushButton("✨ 纠错")
        correct_btn.clicked.connect(self._run_correction)
        toolbar.addWidget(correct_btn)

        clear_btn = QPushButton("🗑 清除")
        clear_btn.clicked.connect(self._clear_text)
        toolbar.addWidget(clear_btn)

        save_btn = QPushButton("💾 导出")
        save_btn.clicked.connect(self._save_text)
        toolbar.addWidget(save_btn)

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        splitter = QSplitter(Qt.Horizontal)

        # 左侧 - 纠错日志
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)

        left_layout.addWidget(QLabel("📋 纠错日志"))
        self.log_list = QListWidget()
        self.log_list.setStyleSheet("""
            QListWidget {
                background: rgba(255,255,255,0.03);
                border: 1px solid rgba(0,212,255,0.1);
                border-radius: 8px;
                padding: 5px;
                font-size: 12px;
            }
            QListWidget::item {
                padding: 6px;
                border-bottom: 1px solid rgba(0,212,255,0.05);
            }
        """)
        left_layout.addWidget(self.log_list)

        splitter.addWidget(left_panel)

        # 右侧 - 编辑区
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)

        # 识别进度
        top_bar = QWidget()
        top_bar_layout = QHBoxLayout(top_bar)
        top_bar_layout.setContentsMargins(0, 0, 0, 5)

        self.partial_label = QLabel("等待输入...")
        self.partial_label.setStyleSheet("""
            color: #00d4ff;
            font-size: 13px;
            padding: 5px 10px;
            background: rgba(0,212,255,0.05);
            border-radius: 5px;
        """)
        self.partial_label.setWordWrap(True)
        top_bar_layout.addWidget(self.partial_label, 1)

        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximumWidth(200)
        self.progress_bar.setMaximumHeight(20)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid rgba(0,212,255,0.2);
                border-radius: 10px;
                text-align: center;
                color: #00d4ff;
                font-size: 11px;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #00d4ff, stop:1 #0066ff);
                border-radius: 10px;
            }
        """)
        self.progress_bar.setValue(0)
        top_bar_layout.addWidget(self.progress_bar)

        right_layout.addWidget(top_bar)

        # 文本区
        self.text_edit = QTextEdit()
        self.text_edit.setPlaceholderText(
            "选择模板开始，或直接输入病历内容。\n"
            "点击「开始录音」用语音输入，系统会自动纠错。\n\n"
            "⚠️ 当前为 Demo 模式，语音识别为模拟数据。\n"
            "部署 Vosk 模型后可启用真实语音识别。"
        )
        self.text_edit.setStyleSheet("""
            QTextEdit {
                background: rgba(255,255,255,0.03);
                border: 1px solid rgba(0,212,255,0.15);
                border-radius: 10px;
                padding: 15px;
                font-size: 14px;
                line-height: 1.8;
                color: #e0e0e0;
            }
            QTextEdit:focus {
                border: 1px solid rgba(0,212,255,0.4);
            }
        """)
        right_layout.addWidget(self.text_edit)

        splitter.addWidget(right_panel)
        splitter.setSizes([300, 900])

        main_layout.addWidget(splitter)

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("就绪 | Demo 模式 | 请先选择科室和模板")

    def _apply_dark_theme(self):
        app = QApplication.instance()
        app.setStyle("Fusion")
        palette = QPalette()
        palette.setColor(QPalette.Window, QColor(10, 14, 39))
        palette.setColor(QPalette.WindowText, QColor(255, 255, 255))
        palette.setColor(QPalette.Base, QColor(15, 20, 50))
        palette.setColor(QPalette.AlternateBase, QColor(20, 25, 60))
        palette.setColor(QPalette.ToolTipBase, QColor(255, 255, 255))
        palette.setColor(QPalette.ToolTipText, QColor(255, 255, 255))
        palette.setColor(QPalette.Text, QColor(220, 220, 220))
        palette.setColor(QPalette.Button, QColor(30, 40, 80))
        palette.setColor(QPalette.ButtonText, QColor(255, 255, 255))
        palette.setColor(QPalette.BrightText, QColor(255, 0, 0))
        palette.setColor(QPalette.Link, QColor(0, 212, 255))
        palette.setColor(QPalette.Highlight, QColor(0, 212, 255))
        palette.setColor(QPalette.HighlightedText, QColor(10, 14, 39))
        app.setPalette(palette)

    def _load_departments(self):
        depts = self.template_engine.get_departments()
        self.dept_combo.clear()
        self.dept_combo.addItems(depts)

    def _on_dept_changed(self, dept):
        self.current_dept = dept
        self.corrector.set_department(dept)
        self.template_combo.clear()
        templates = self.template_engine.get_templates(dept)
        for t in templates:
            self.template_combo.addItem(t["name"])
        self.status_bar.showMessage(f"当前科室：{dept} | Demo 模式")

    def _on_template_changed(self, template_name):
        if not template_name:
            return
        content = self.template_engine.get_template(
            self.current_dept, template_name
        )
        if content:
            self.text_edit.setPlainText(content)
            self.status_bar.showMessage(f"已加载模板：{template_name}")

    def _toggle_recording(self):
        if not self.is_listening:
            self._start_recording()
        else:
            self._stop_recording()

    def _start_recording(self):
        self.record_btn.setText("⏹ 停止录音")
        self.record_btn.setChecked(True)
        self.is_listening = True
        self.text_edit.setFocus()

        self.listen_thread = MockListenThread()
        self.listen_thread.text_ready.connect(self._on_recognized)
        self.listen_thread.partial_text.connect(self._on_partial)
        self.listen_thread.status_changed.connect(self.status_bar.showMessage)
        self.listen_thread.progress.connect(self.progress_bar.setValue)
        self.listen_thread.start()

    def _stop_recording(self):
        self.is_listening = False
        self.record_btn.setText("🎤 开始录音 (Demo)")
        self.record_btn.setChecked(False)

        if self.listen_thread:
            self.listen_thread.terminate()
            self.listen_thread.wait(500)
            self.listen_thread = None

        self.partial_label.setText("等待输入...")
        self.progress_bar.setValue(0)

    def _on_recognized(self, text):
        self.text_edit.setPlainText(text)
        self.partial_label.setText("✓ 识别完成")

    def _on_partial(self, text):
        self.partial_label.setText(f"🔊 识别中：{text}")

    def _run_correction(self):
        text = self.text_edit.toPlainText().strip()
        if not text:
            QMessageBox.information(self, "提示", "请先输入或录制文本")
            return

        self.status_bar.showMessage("正在纠错...")
        QApplication.processEvents()

        self.correct_thread = MockCorrectThread(self.corrector, text)
        self.correct_thread.correction_done.connect(self._on_correction_done)
        self.correct_thread.start()

    def _on_correction_done(self, corrected, log):
        self.text_edit.setPlainText(corrected)
        self.log_list.clear()
        for item in log:
            icon = "⚠️" if item["级别"] == "警告" else "🔧" if item["级别"] == "自动" else "💡"
            self.log_list.addItem(f"{icon} [{item['级别']}] {item['type']}")
            if item.get("原文") != item.get("修正"):
                self.log_list.addItem(f"    {item.get('原文', '')} → {item.get('修正', '')}")
        self.status_bar.showMessage(f"纠错完成，共 {len(log)} 条建议")

    def _clear_text(self):
        self.text_edit.clear()
        self.log_list.clear()
        self.partial_label.setText("等待输入...")
        self.progress_bar.setValue(0)

    def _save_text(self):
        text = self.text_edit.toPlainText()
        if not text:
            QMessageBox.information(self, "提示", "没有内容可导出")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "保存病历",
            os.path.join(os.path.expanduser("~"), "Desktop", "病历记录.txt"),
            "文本文件 (*.txt);;所有文件 (*)"
        )
        if path:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(text)
            self.status_bar.showMessage(f"已保存：{path}")


def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    font = QFont("Microsoft YaHei", 11)
    app.setFont(font)

    window = MedVoiceApp()
    window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
