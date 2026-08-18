"""
对话框模块 —— 从 main.py 拆分

包含：
- RuleManagerDialog：纠错规则管理
- FieldWordsPanel：字段常用词面板
- TemplateManagerDialog：模板增删改查
- SectionDialog：病历结构化编辑
"""
import os
import re
import json

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QWidget,
    QPushButton, QLabel, QTableWidget, QTableWidgetItem,
    QTabWidget, QHeaderView, QLineEdit, QInputDialog,
    QScrollArea, QCheckBox, QGroupBox, QMessageBox,
    QStyle,
)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from PyQt5.QtGui import QFont, QColor, QPalette, QTextCursor, QTextCharFormat


# ==================== 规则管理对话框 ====================

class RuleManagerDialog(QDialog):
    """自定义纠错规则管理界面"""

    def __init__(self, rule_engine, parent=None):
        super().__init__(parent)
        self.rule_engine = rule_engine
        self.setWindowTitle("\U0001f4cf 纠错规则管理")
        self.setModal(True)
        self.resize(700, 500)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        tabs = QTabWidget()

        # ---- 错别字标签页 ----
        typo_tab = QWidget()
        typo_layout = QVBoxLayout(typo_tab)

        add_typo = QWidget()
        add_typo_layout = QHBoxLayout(add_typo)
        add_typo_layout.setContentsMargins(0, 0, 0, 10)
        self.typo_wrong_input = QLineEdit()
        self.typo_wrong_input.setPlaceholderText("错误写法（如：心电围）")
        self.typo_correct_input = QLineEdit()
        self.typo_correct_input.setPlaceholderText("正确写法（如：心电图）")
        add_typo_btn = QPushButton("➕ 添加规则")
        add_typo_btn.clicked.connect(self._add_typo_rule)
        add_typo_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #00d4ff, stop:1 #0066ff);
                color: #0a0e27;
                font-weight: bold;
                padding: 6px 16px;
                border-radius: 15px;
                font-size: 12px;
            }
            QPushButton:hover { padding: 6px 20px; }
        """)
        add_typo_layout.addWidget(QLabel("错误："))
        add_typo_layout.addWidget(self.typo_wrong_input)
        add_typo_layout.addWidget(QLabel("正确："))
        add_typo_layout.addWidget(self.typo_correct_input)
        add_typo_layout.addWidget(add_typo_btn)
        typo_layout.addWidget(add_typo)

        self.typo_table = QTableWidget()
        self.typo_table.setColumnCount(3)
        self.typo_table.setHorizontalHeaderLabels(["错误", "正确", "操作"])
        self.typo_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.typo_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.typo_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Fixed)
        self.typo_table.setColumnWidth(2, 80)
        self.typo_table.setStyleSheet("""
            QTableWidget {
                background: rgba(255,255,255,0.03);
                border: 1px solid rgba(0,212,255,0.1);
                border-radius: 8px;
                color: #e0e0e0;
                font-size: 13px;
            }
            QHeaderView::section {
                background: rgba(0,212,255,0.1);
                color: #00d4ff;
                padding: 6px;
                border: none;
            }
        """)
        typo_layout.addWidget(self.typo_table)
        self._refresh_typo_table()
        tabs.addTab(typo_tab, "\U0001f4e2 错别字规则")

        # ---- 逻辑错误标签页 ----
        logic_tab = QWidget()
        logic_layout = QVBoxLayout(logic_tab)

        add_logic = QWidget()
        add_logic_layout = QHBoxLayout(add_logic)
        add_logic_layout.setContentsMargins(0, 0, 0, 10)
        self.logic_name_input = QLineEdit()
        self.logic_name_input.setPlaceholderText("规则名称（如：疾病与症状不符）")
        self.logic_desc_input = QLineEdit()
        self.logic_desc_input.setPlaceholderText("规则描述")
        add_logic_btn = QPushButton("➕ 添加规则")
        add_logic_btn.clicked.connect(self._add_logic_rule)
        add_logic_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #ff9944, stop:1 #ff6600);
                color: white;
                font-weight: bold;
                padding: 6px 16px;
                border-radius: 15px;
                font-size: 12px;
            }
            QPushButton:hover { padding: 6px 20px; }
        """)
        add_logic_layout.addWidget(QLabel("名称："))
        add_logic_layout.addWidget(self.logic_name_input)
        add_logic_layout.addWidget(QLabel("描述："))
        add_logic_layout.addWidget(self.logic_desc_input)
        add_logic_layout.addWidget(add_logic_btn)
        logic_layout.addWidget(add_logic)

        self.logic_table = QTableWidget()
        self.logic_table.setColumnCount(3)
        self.logic_table.setHorizontalHeaderLabels(["错误模式", "描述", "操作"])
        self.logic_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
        self.logic_table.setColumnWidth(0, 160)
        self.logic_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.logic_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Fixed)
        self.logic_table.setColumnWidth(2, 80)
        self.logic_table.setStyleSheet("""
            QTableWidget {
                background: rgba(255,255,255,0.03);
                border: 1px solid rgba(0,212,255,0.1);
                border-radius: 8px;
                color: #e0e0e0;
                font-size: 13px;
            }
            QHeaderView::section {
                background: rgba(255,153,68,0.1);
                color: #ff9944;
                padding: 6px;
                border: none;
            }
        """)
        logic_layout.addWidget(self.logic_table)
        self._refresh_logic_table()
        tabs.addTab(logic_tab, "\U0001f9e0 逻辑错误规则")

        layout.addWidget(tabs)

        bottom = QHBoxLayout()
        bottom.addStretch()
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.accept)
        close_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255,255,255,0.1);
                color: #b8c5d6;
                padding: 8px 24px;
                border-radius: 15px;
                border: 1px solid rgba(255,255,255,0.1);
            }
            QPushButton:hover { background: rgba(255,255,255,0.15); }
        """)
        bottom.addWidget(close_btn)
        layout.addLayout(bottom)

    def _refresh_typo_table(self):
        rules = self.rule_engine.get_typo_rules()
        self.typo_table.setRowCount(len(rules))
        for i, rule in enumerate(rules):
            self.typo_table.setItem(i, 0, QTableWidgetItem(rule["错误"]))
            self.typo_table.setItem(i, 1, QTableWidgetItem(rule["正确"]))
            del_btn = QPushButton("\U0001f5d1")
            del_btn.setFixedSize(40, 30)
            del_btn.clicked.connect(lambda _, w=rule["错误"]: self._delete_typo(w))
            del_btn.setStyleSheet("""
                QPushButton {
                    background: rgba(255,80,80,0.1);
                    border: 1px solid rgba(255,80,80,0.2);
                    border-radius: 5px;
                    color: #ff6b6b;
                    font-size: 14px;
                }
                QPushButton:hover { background: rgba(255,80,80,0.2); }
            """)
            self.typo_table.setCellWidget(i, 2, del_btn)

    def _refresh_logic_table(self):
        rules = self.rule_engine.get_logic_rules()
        self.logic_table.setRowCount(len(rules))
        for i, rule in enumerate(rules):
            self.logic_table.setItem(i, 0, QTableWidgetItem(rule.get("错误模式", "")))
            self.logic_table.setItem(i, 1, QTableWidgetItem(rule.get("描述", "")))
            del_btn = QPushButton("\U0001f5d1")
            del_btn.setFixedSize(40, 30)
            del_btn.clicked.connect(lambda _, n=rule["错误模式"]: self._delete_logic(n))
            del_btn.setStyleSheet("""
                QPushButton {
                    background: rgba(255,80,80,0.1);
                    border: 1px solid rgba(255,80,80,0.2);
                    border-radius: 5px;
                    color: #ff6b6b;
                    font-size: 14px;
                }
                QPushButton:hover { background: rgba(255,80,80,0.2); }
            """)
            self.logic_table.setCellWidget(i, 2, del_btn)

    def _add_typo_rule(self):
        wrong = self.typo_wrong_input.text().strip()
        correct = self.typo_correct_input.text().strip()
        if not wrong or not correct:
            QMessageBox.warning(self, "提示", "请填写错误写法和正确写法")
            return
        if wrong == correct:
            QMessageBox.warning(self, "提示", "错误写法和正确写法不能相同")
            return
        is_new = self.rule_engine.add_typo_rule(wrong, correct)
        self.typo_wrong_input.clear()
        self.typo_correct_input.clear()
        self._refresh_typo_table()
        msg = "规则已添加" if is_new else "规则已更新"
        parent = self.parent()
        if parent and hasattr(parent, 'status_bar'):
            parent.status_bar.showMessage(f"\U0001f4cf {msg}: {wrong} → {correct}")

    def _add_logic_rule(self):
        name = self.logic_name_input.text().strip()
        desc = self.logic_desc_input.text().strip()
        if not name or not desc:
            QMessageBox.warning(self, "提示", "请填写规则名称和描述")
            return
        self.rule_engine.add_logic_rule(name, desc)
        self.logic_name_input.clear()
        self.logic_desc_input.clear()
        self._refresh_logic_table()
        parent = self.parent()
        if parent and hasattr(parent, 'status_bar'):
            parent.status_bar.showMessage(f"\U0001f4cf 逻辑规则已添加: {name}")

    def _delete_typo(self, wrong):
        confirm = QMessageBox.question(
            self, "确认删除",
            f"确定删除规则「{wrong}」吗？",
            QMessageBox.Yes | QMessageBox.No
        )
        if confirm == QMessageBox.Yes:
            self.rule_engine.delete_typo_rule(wrong)
            self._refresh_typo_table()
            parent = self.parent()
            if parent and hasattr(parent, 'status_bar'):
                parent.status_bar.showMessage(f"\U0001f4cf 规则已删除: {wrong}")

    def _delete_logic(self, name):
        confirm = QMessageBox.question(
            self, "确认删除",
            f"确定删除规则「{name}」吗？",
            QMessageBox.Yes | QMessageBox.No
        )
        if confirm == QMessageBox.Yes:
            self.rule_engine.delete_logic_rule(name)
            self._refresh_logic_table()
            parent = self.parent()
            if parent and hasattr(parent, 'status_bar'):
                parent.status_bar.showMessage(f"\U0001f4cf 规则已删除: {name}")


# ==================== 字段常用词面板 ====================

class FieldWordsPanel(QWidget):
    """字段常用词面板 - 按字段分类展示可点击插入的常用词"""
    term_clicked = pyqtSignal(str)  # (词语)

    # 内置默认常用词（当 field_words.json 不存在时使用）
    DEFAULT_WORDS = {
        "主诉": {
            "label": "主诉",
            "terms": [
                "发热 3 天", "咳嗽 1 周", "胸痛 2 天", "腹痛 1 天",
                "头痛 3 天", "头晕 1 周", "呼吸困难 2 天", "胸闷 1 周",
                "乏力 1 月", "消瘦 2 月", "恶心呕吐 1 天", "腹泻 2 天",
                "便血 1 天", "水肿 1 周", "意识不清 2 小时",
            ]
        },
        "现病史": {
            "label": "现病史",
            "terms": [
                "患者于 X 天前无明显诱因出现",
                "伴发热，体温最高达 38.5℃",
                "无恶心、呕吐、腹泻",
                "自行口服药物后症状无明显缓解",
                "门诊查血常规：白细胞升高",
                "胸片提示右下肺感染",
                "予以抗感染、补液等对症治疗",
                "症状有所缓解，为进一步诊治入院",
            ]
        },
        "既往史": {
            "label": "既往史",
            "terms": [
                "否认高血压、糖尿病、冠心病病史",
                "否认肝炎、结核等传染病史",
                "否认食物及药物过敏史",
                "否认手术史、外伤史、输血史",
                "高血压病史 X 年，口服药物控制可",
                "糖尿病病史 X 年",
                "吸烟史 X 年，约 X 支/日",
                "饮酒史 X 年",
                "父亲患有高血压，母亲患有糖尿病",
            ]
        },
        "体格检查": {
            "label": "体格检查",
            "terms": [
                "T 36.5℃，P 78 次/分，R 20 次/分，BP 128/80 mmHg",
                "神志清楚，精神可，发育正常，营养中等",
                "自主体位，步入病房",
                "全身皮肤黏膜无黄染，未见皮疹、出血点",
                "颈软，无抵抗",
                "胸廓对称，双肺叩诊清音，双肺呼吸音清晰",
                "心前区无隆起，心率 78 次/分，心律齐",
                "腹平坦，腹软，全腹无压痛、反跳痛",
                "肝脾肋下未触及，肠鸣音正常",
                "双下肢无水肿，四肢肌力 V 级",
            ]
        },
        "辅助检查": {
            "label": "辅助检查",
            "terms": [
                "血常规：白细胞 12×10^9/L，中性粒细胞 85%",
                "尿常规：未见明显异常",
                "大便常规：黄色软便，隐血阴性",
                "血生化：谷丙转氨酶 35U/L，肌酐 78μmol/L",
                "凝血功能：PT 12.5s，APTT 30s",
                "血糖：空腹 5.6mmol/L",
                "心电图：窦性心律，心率 75 次/分",
                "胸片：心肺膈未见明显异常",
                "胸部 CT：右肺中叶斑片状高密度影，考虑炎症",
                "头颅 CT：未见出血及占位性病变",
                "腹部 B 超：肝胆胰脾未见明显异常",
            ]
        },
        "初步诊断": {
            "label": "初步诊断",
            "terms": [
                "1. 社区获得性肺炎",
                "2. 高血压病 2 级，很高危",
                "3. 2 型糖尿病",
                "4. 冠状动脉粥样硬化性心脏病",
                "5. 慢性阻塞性肺疾病",
                "6. 急性阑尾炎",
                "7. 急性胆囊炎",
                "8. 脑梗死（急性期）",
                "9. 消化性溃疡伴出血",
                "10. 急性胰腺炎",
            ]
        },
        "诊疗计划": {
            "label": "诊疗计划",
            "terms": [
                "完善血常规、血生化、凝血功能、心电图等检查",
                "抗感染治疗：予头孢曲松钠 2g qd ivgtt",
                "化痰止咳：氨溴索 30mg tid",
                "补液维持水电解质平衡",
                "监测生命体征，定期复查血常规",
                "低盐低脂糖尿病饮食",
                "请示上级医师",
            ]
        },
        "鉴别诊断": {
            "label": "鉴别诊断",
            "terms": [
                "1. 肺结核：需胸片/CT 及结核菌素试验鉴别",
                "2. 支气管肺癌：需 CT 及病理鉴别",
                "3. 支气管扩张：多有反复咳嗽、咳大量脓痰病史",
                "4. 肺脓肿：CT 可见空洞及液平",
            ]
        },
        "专科情况": {
            "label": "专科情况",
            "terms": {
                "呼吸科": [
                    "胸廓对称，双肺叩诊清音",
                    "双肺呼吸音粗，可闻及干湿性啰音",
                    "语音共振无增强或减弱",
                ],
                "心血管内科": [
                    "心前区无隆起，心浊音界正常",
                    "心率 78 次/分，心律齐",
                    "各瓣膜区未闻及病理性杂音",
                    "双下肢无水肿",
                ],
                "神经内科": [
                    "神志清楚，言语流利",
                    "双侧瞳孔等大等圆，对光反射灵敏",
                    "四肢肌力 V 级，肌张力正常",
                    "双侧巴宾斯基征阴性",
                    "颈软，无抵抗",
                ],
                "消化内科": [
                    "腹平坦，未见胃肠型",
                    "腹软，全腹无压痛、反跳痛、肌紧张",
                    "肝脾肋下未触及",
                    "Murphy 征阴性",
                    "肠鸣音正常",
                ],
            }
        },
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self._words_data = {}
        self._presets_data = {}
        self._current_field = ""
        self._load_words()
        self._load_presets()
        self._init_ui()

    def _load_words(self):
        words_path = os.path.join(os.path.dirname(__file__), "..", "field_words.json")
        words_path = os.path.normpath(words_path)
        try:
            with open(words_path, 'r', encoding='utf-8') as f:
                self._words_data = json.load(f)
        except Exception:
            self._words_data = dict(self.DEFAULT_WORDS)

    def _load_presets(self):
        presets_path = os.path.join(os.path.dirname(__file__), "..", "field_presets.json")
        presets_path = os.path.normpath(presets_path)
        try:
            with open(presets_path, 'r', encoding='utf-8') as f:
                self._presets_data = json.load(f)
        except Exception:
            self._presets_data = {}

    def _save_presets(self):
        presets_path = os.path.join(os.path.dirname(__file__), "..", "field_presets.json")
        presets_path = os.path.normpath(presets_path)
        with open(presets_path, 'w', encoding='utf-8') as f:
            json.dump(self._presets_data, f, ensure_ascii=False, indent=2)

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(2)

        # 字段标签栏
        tabs_bar = QWidget()
        tabs_layout = QHBoxLayout(tabs_bar)
        tabs_layout.setContentsMargins(0, 0, 0, 0)
        tabs_layout.setSpacing(2)

        field_order = [
            "主诉", "入院方式", "病史陈述者", "现病史", "既往史", "个人史", "婚育史", "家族史",
            "体格检查", "辅助检查", "初步诊断", "鉴别诊断", "诊疗计划",
            "手术记录", "会诊记录", "抢救记录", "死亡病例讨论", "专科情况"
        ]

        self._tab_buttons = {}
        for field in field_order:
            if field in self._words_data:
                btn = QPushButton(field)
                btn.setCheckable(True)
                btn.setFixedHeight(22)
                btn.setToolTip(self._words_data[field].get("description", ""))
                btn.clicked.connect(lambda checked, f=field: self._on_field_selected(f))
                btn.setStyleSheet("""
                    QPushButton {
                        background: rgba(255,255,255,0.05);
                        color: #b8c5d6;
                        border: 1px solid rgba(0,212,255,0.1);
                        border-radius: 10px;
                        padding: 2px 10px;
                        font-size: 11px;
                    }
                    QPushButton:checked {
                        background: rgba(0,212,255,0.2);
                        color: #00d4ff;
                        border-color: rgba(0,212,255,0.4);
                    }
                    QPushButton:hover {
                        background: rgba(0,212,255,0.1);
                    }
                """)
                tabs_layout.addWidget(btn)
                self._tab_buttons[field] = btn

        tabs_layout.addStretch()
        layout.addWidget(tabs_bar)

        # 常用词滚动区
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setMaximumHeight(280)
        scroll.setStyleSheet("""
            QScrollArea {
                border: 1px solid rgba(0,212,255,0.08);
                border-radius: 6px;
                background: rgba(255,255,255,0.02);
            }
            QScrollBar:vertical {
                background: rgba(0,0,0,0.2);
                width: 6px;
                border-radius: 3px;
            }
            QScrollBar::handle:vertical {
                background: rgba(0,212,255,0.3);
                border-radius: 3px;
            }
        """)

        self._terms_container = QWidget()
        self._terms_layout = QVBoxLayout(self._terms_container)
        self._terms_layout.setContentsMargins(6, 6, 6, 6)
        self._terms_layout.setSpacing(6)

        scroll.setWidget(self._terms_container)
        layout.addWidget(scroll)

        # 默认选中第一个字段
        if self._tab_buttons:
            first_field = list(self._tab_buttons.keys())[0]
            self._tab_buttons[first_field].setChecked(True)
            self._show_field_terms(first_field)

    def _on_field_selected(self, field):
        for f, btn in self._tab_buttons.items():
            btn.setChecked(f == field)
        self._current_field = field
        self._show_field_terms(field)

    def _show_field_terms(self, field):
        while self._terms_layout.count():
            item = self._terms_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        field_data = self._words_data.get(field)
        if not field_data:
            return

        terms = field_data.get("terms", {})

        if isinstance(terms, dict):
            for category, word_list in terms.items():
                cat_label = QLabel(category)
                cat_label.setStyleSheet(
                    "color: #00d4ff; font-size: 11px; font-weight: bold; padding: 2px 0;"
                )
                self._terms_layout.addWidget(cat_label)
                row = self._create_term_row(word_list, field)
                self._terms_layout.addWidget(row)
        else:
            row = self._create_term_row(terms, field)
            self._terms_layout.addWidget(row)

        # ─── 常用句区域 ───
        presets = self._presets_data.get(field, [])
        if presets:
            preset_label = QLabel("\U0001f4dd 常用句（点击插入）")
            preset_label.setStyleSheet(
                "color: #ffa500; font-size: 11px; font-weight: bold; padding: 4px 0 2px;"
            )
            self._terms_layout.addWidget(preset_label)
            for sentence in presets:
                btn = QPushButton(sentence[:30] + ("..." if len(sentence) > 30 else ""))
                btn.setToolTip(sentence)
                btn.setFixedHeight(26)
                btn.setCursor(Qt.PointingHandCursor)
                btn.clicked.connect(lambda checked, s=sentence: self.term_clicked.emit(s))
                btn.setStyleSheet("""
                    QPushButton {
                        background: rgba(255,165,0,0.08);
                        color: #e8d5b0;
                        border: 1px solid rgba(255,165,0,0.2);
                        border-radius: 4px;
                        padding: 3px 8px;
                        font-size: 11px;
                        text-align: left;
                    }
                    QPushButton:hover {
                        background: rgba(255,165,0,0.2);
                        color: #ffa500;
                        border-color: rgba(255,165,0,0.5);
                    }
                """)
                self._terms_layout.addWidget(btn)

        # "+ 添加常用句"按钮
        add_btn = QPushButton("➕ 添加常用句")
        add_btn.setFixedHeight(24)
        add_btn.setCursor(Qt.PointingHandCursor)
        add_btn.clicked.connect(lambda: self._add_preset_for_field(field))
        add_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #788;
                border: 1px dashed rgba(255,255,255,0.15);
                border-radius: 4px;
                padding: 2px 8px;
                font-size: 10px;
            }
            QPushButton:hover { color: #ffa500; border-color: rgba(255,165,0,0.4); }
        """)
        self._terms_layout.addWidget(add_btn)

        self._terms_layout.addStretch()

    def _create_term_row(self, terms, field):
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(4)

        for term in terms:
            if not term:
                continue
            btn = QPushButton(term)
            btn.setFixedHeight(24)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda checked, t=term: self.term_clicked.emit(t))
            btn.setStyleSheet("""
                QPushButton {
                    background: rgba(0,212,255,0.08);
                    color: #c8d6e5;
                    border: 1px solid rgba(0,212,255,0.15);
                    border-radius: 12px;
                    padding: 3px 12px;
                    font-size: 11px;
                }
                QPushButton:hover {
                    background: rgba(0,212,255,0.2);
                    color: #00d4ff;
                    border-color: rgba(0,212,255,0.4);
                }
            """)
            row_layout.addWidget(btn)

        row_layout.addStretch()
        return row

    def _add_preset_for_field(self, field):
        text, ok = QInputDialog.getMultiLineText(
            self, f"添加常用句 — {field}",
            f"请输入「{field}」的常用句：",
            ""
        )
        if ok and text.strip():
            sentence = text.strip()
            if field not in self._presets_data:
                self._presets_data[field] = []
            if sentence not in self._presets_data[field]:
                self._presets_data[field].append(sentence)
                self._save_presets()
                self._show_field_terms(field)

    def set_current_field(self, field):
        if field in self._tab_buttons:
            self._on_field_selected(field)


# ==================== 模板管理对话框 ====================

class TemplateManagerDialog(QDialog):
    """模板增删改查管理界面"""

    def __init__(self, template_engine, current_dept, parent=None):
        super().__init__(parent)
        self.template_engine = template_engine
        self.current_dept = current_dept
        self._editing_index = -1  # -1 = 新增模式，>=0 = 编辑模式
        self.setWindowTitle("\U0001f4dd 模板管理")
        self.setModal(True)
        self.resize(700, 550)
        self._init_ui()
        self._refresh_dept_list()
        self._refresh_template_list()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # 上部：科室选择 + 模板列表
        top_split = QWidget()
        top_layout = QHBoxLayout(top_split)
        top_layout.setContentsMargins(0, 0, 0, 0)

        # 科室列表
        dept_widget = QWidget()
        dept_layout = QVBoxLayout(dept_widget)
        dept_layout.setContentsMargins(0, 0, 0, 0)
        dept_layout.addWidget(QLabel("科室："))
        self.dept_list = QListWidget()
        self.dept_list.setMaximumWidth(120)
        self.dept_list.itemClicked.connect(self._on_dept_selected)
        dept_layout.addWidget(self.dept_list)
        top_layout.addWidget(dept_widget)

        # 模板列表
        tpl_widget = QWidget()
        tpl_layout = QVBoxLayout(tpl_widget)
        tpl_layout.setContentsMargins(0, 0, 0, 0)
        tpl_layout.addWidget(QLabel("模板："))
        self.tpl_list = QListWidget()
        self.tpl_list.itemClicked.connect(self._on_template_selected)
        tpl_layout.addWidget(self.tpl_list)

        # 模板操作按钮
        tpl_btn_bar = QWidget()
        tpl_btn_layout = QHBoxLayout(tpl_btn_bar)
        tpl_btn_layout.setContentsMargins(0, 5, 0, 0)
        add_tpl_btn = QPushButton("➕ 新建")
        add_tpl_btn.clicked.connect(self._add_template)
        del_tpl_btn = QPushButton("\U0001f5d1 删除")
        del_tpl_btn.clicked.connect(self._delete_template)
        tpl_btn_layout.addWidget(add_tpl_btn)
        tpl_btn_layout.addWidget(del_tpl_btn)
        tpl_layout.addWidget(tpl_btn_bar)

        top_layout.addWidget(tpl_widget)
        layout.addWidget(top_split)

        # 中部：模板编辑区
        edit_group = QGroupBox("模板内容编辑")
        edit_layout = QVBoxLayout(edit_group)

        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("模板名称："))
        self.name_edit = QLineEdit()
        name_layout.addWidget(self.name_edit)
        edit_layout.addLayout(name_layout)

        self.content_edit = QTextEdit()
        self.content_edit.setPlaceholderText("在此编辑模板内容...\n用「字段名：」格式定义病历字段")
        self.content_edit.setMinimumHeight(200)
        edit_layout.addWidget(self.content_edit)

        layout.addWidget(edit_group)

        # 底部按钮
        bottom = QHBoxLayout()
        bottom.addStretch()
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        save_btn = QPushButton("✓ 保存")
        save_btn.clicked.connect(self._save_template)
        save_btn.setDefault(True)
        bottom.addWidget(cancel_btn)
        bottom.addWidget(save_btn)
        layout.addLayout(bottom)

    def _refresh_dept_list(self):
        self.dept_list.clear()
        depts = self.template_engine.get_departments()
        for dept in depts:
            self.dept_list.addItem(dept)
        for i in range(self.dept_list.count()):
            if self.dept_list.item(i).text() == self.current_dept:
                self.dept_list.setCurrentRow(i)
                break

    def _refresh_template_list(self):
        self.tpl_list.clear()
        dept = self._get_selected_dept()
        if not dept:
            return
        templates = self.template_engine.get_templates(dept)
        for t in templates:
            self.tpl_list.addItem(t["name"])

    def _get_selected_dept(self):
        item = self.dept_list.currentItem()
        return item.text() if item else ""

    def _on_dept_selected(self, item):
        self._editing_index = -1
        self._refresh_template_list()
        self.name_edit.clear()
        self.content_edit.clear()

    def _on_template_selected(self, item):
        dept = self._get_selected_dept()
        if not dept:
            return
        tpl_name = item.text()
        content = self.template_engine.get_template(dept, tpl_name)
        if content is not None:
            self.name_edit.setText(tpl_name)
            self.content_edit.setPlainText(content)
            self._editing_index = self.tpl_list.currentRow()

    def _add_template(self):
        dept = self._get_selected_dept()
        if not dept:
            QMessageBox.information(self, "提示", "请先选择科室")
            return
        self._editing_index = -1
        self.name_edit.clear()
        self.content_edit.clear()
        self.name_edit.setFocus()

    def _delete_template(self):
        dept = self._get_selected_dept()
        if not dept:
            return
        row = self.tpl_list.currentRow()
        if row < 0:
            QMessageBox.information(self, "提示", "请先选择要删除的模板")
            return
        tpl_name = self.tpl_list.item(row).text()
        confirm = QMessageBox.question(
            self, "确认删除",
            f"确定删除模板「{tpl_name}」吗？",
            QMessageBox.Yes | QMessageBox.No
        )
        if confirm == QMessageBox.Yes:
            templates = self.template_engine.get_templates(dept)
            if row < len(templates):
                templates.pop(row)
                self._save_dept_templates(dept, templates)
                self._refresh_template_list()
                self.name_edit.clear()
                self.content_edit.clear()
                self._editing_index = -1
                parent = self.parent()
                if parent and hasattr(parent, 'status_bar'):
                    parent.status_bar.showMessage(f"\U0001f4dd 模板已删除：{tpl_name}")

    def _save_template(self):
        dept = self._get_selected_dept()
        if not dept:
            QMessageBox.warning(self, "提示", "请选择科室")
            return
        name = self.name_edit.text().strip()
        content = self.content_edit.toPlainText().strip()
        if not name:
            QMessageBox.warning(self, "提示", "请输入模板名称")
            return
        if not content:
            QMessageBox.warning(self, "提示", "请输入模板内容")
            return

        templates = self.template_engine.get_templates(dept)
        if self._editing_index >= 0 and self._editing_index < len(templates):
            templates[self._editing_index] = {"name": name, "content": content}
        else:
            templates.append({"name": name, "content": content})

        self._save_dept_templates(dept, templates)
        self._refresh_template_list()
        for i in range(self.tpl_list.count()):
            if self.tpl_list.item(i).text() == name:
                self.tpl_list.setCurrentRow(i)
                break
        self._editing_index = self.tpl_list.currentRow()
        self.accept()

    def _save_dept_templates(self, dept, templates):
        templates_dir = os.path.join(os.path.dirname(__file__), "..", "templates")
        templates_dir = os.path.normpath(templates_dir)
        path = os.path.join(templates_dir, f"{dept}.json")
        data = {"templates": templates}
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        self.template_engine.load_templates()


# ==================== 病历结构化对话框 ====================

class SectionDialog(QDialog):
    """病历结构化编辑对话框"""

    STANDARD_FIELDS = [
        "主诉", "现病史", "既往史", "体格检查", "辅助检查",
        "初步诊断", "诊疗经过", "出院情况", "出院医嘱",
        "术前诊断", "手术名称", "术中情况", "术后诊断", "术后医嘱",
        # 影像科字段
        "检查项目", "检查部位", "检查方法", "影像表现", "诊断意见",
        "增强特征", "血管描述", "超声所见", "超声提示",
        "建议",
        "急救措施", "用药情况", "效果评估",
        "日期", "患者情况", "处理意见"
    ]

    def __init__(self, parser, raw_text, parent=None):
        super().__init__(parent)
        self.parser = parser
        self.raw_text = raw_text
        self.field_edits = {}
        self.setWindowTitle("\U0001f4cb 病历结构化")
        self.setModal(True)
        self.resize(750, 600)
        self._init_ui()

    def _init_ui(self):
        sections = self.parser.parse(self.raw_text)

        layout = QVBoxLayout(self)

        info = QLabel(f"从语音文本中识别出 {len(sections)} 个病历部分，可逐项编辑")
        info.setStyleSheet("color: #b8c5d6; font-size: 12px; padding: 5px;")
        layout.addWidget(info)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea {
                border: 1px solid rgba(0,212,255,0.1);
                border-radius: 8px;
                background: rgba(255,255,255,0.02);
            }
        """)

        container = QWidget()
        form_layout = QVBoxLayout(container)
        form_layout.setSpacing(8)

        for field in self.STANDARD_FIELDS:
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(8)

            label = QLabel(f"{field}：")
            label.setFixedWidth(70)
            label.setStyleSheet("color: #00d4ff; font-size: 13px; font-weight: bold;")
            row_layout.addWidget(label)

            edit = QLineEdit()
            content = sections.get(field, "")
            edit.setText(content)
            edit.setPlaceholderText(f"请输入{field}...")
            edit.setStyleSheet("""
                QLineEdit {
                    background: rgba(255,255,255,0.05);
                    border: 1px solid rgba(0,212,255,0.15);
                    border-radius: 6px;
                    padding: 6px 10px;
                    color: #e0e0e0;
                    font-size: 13px;
                }
                QLineEdit:focus {
                    border: 1px solid rgba(0,212,255,0.4);
                }
            """)
            row_layout.addWidget(edit)
            self.field_edits[field] = edit

            if content:
                label.setStyleSheet("color: #51cf66; font-size: 13px; font-weight: bold;")

            form_layout.addWidget(row)

        scroll.setWidget(container)
        layout.addWidget(scroll)

        bottom = QHBoxLayout()
        bottom.addStretch()

        clear_btn = QPushButton("\U0001f5d1 清空")
        clear_btn.clicked.connect(self._clear_all)
        clear_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255,80,80,0.1);
                color: #ff6b6b;
                padding: 8px 20px;
                border-radius: 15px;
                border: 1px solid rgba(255,80,80,0.2);
            }
            QPushButton:hover { background: rgba(255,80,80,0.2); }
        """)
        bottom.addWidget(clear_btn)

        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255,255,255,0.1);
                color: #b8c5d6;
                padding: 8px 20px;
                border-radius: 15px;
                border: 1px solid rgba(255,255,255,0.1);
            }
            QPushButton:hover { background: rgba(255,255,255,0.15); }
        """)
        bottom.addWidget(cancel_btn)

        confirm_btn = QPushButton("✓ 确认填充")
        confirm_btn.clicked.connect(self._confirm)
        confirm_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #00d4ff, stop:1 #0066ff);
                color: #0a0e27;
                font-weight: bold;
                padding: 8px 24px;
                border-radius: 15px;
            }
            QPushButton:hover { padding: 8px 28px; }
        """)
        bottom.addWidget(confirm_btn)

        layout.addLayout(bottom)

    def _clear_all(self):
        for edit in self.field_edits.values():
            edit.clear()

    def _confirm(self):
        self.accept()

    def get_result(self):
        lines = []
        for field in self.STANDARD_FIELDS:
            edit = self.field_edits.get(field)
            if edit:
                content = edit.text().strip()
                if content:
                    lines.append(f"{field}：{content}")
        return "\n\n".join(lines)
