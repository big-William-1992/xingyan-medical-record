"""
常用语句库对话框
- 左侧分类列表，右侧短语列表；双击/插入按钮把短语发回主编辑器
- 支持新增/删除分类与短语（写入 phrases.json）
风格与主程序一致（深色科技风）
"""
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QMessageBox, QInputDialog, QWidget
)
from PyQt5.QtCore import Qt, pyqtSignal

from login_dialog import DIALOG_STYLE, PRIMARY_BTN, PLAIN_BTN, DANGER_BTN


class PhraseDialog(QDialog):
    """常用语句库。选中短语后通过 phrase_selected 信号发回，或读取 self.selected_phrase。"""

    phrase_selected = pyqtSignal(str)

    def __init__(self, phrase_lib, parent=None):
        super().__init__(parent)
        self.lib = phrase_lib
        self.selected_phrase = None
        self.setWindowTitle("💬 常用语句库")
        self.resize(720, 480)
        self.setStyleSheet(DIALOG_STYLE + """
            QListWidget {
                background: #141a3a; color: #e6ecff;
                border: 1px solid #2a3566; border-radius: 8px;
                padding: 4px; font-size: 13px;
            }
            QListWidget::item { padding: 6px; }
            QListWidget::item:selected { background: rgba(0,212,255,0.25); }
        """)
        self._init_ui()
        self._reload_categories()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        tip = QLabel("双击短语即可插入到病历光标处，也可选中后点「插入」。")
        tip.setStyleSheet("color: #7f8bc0; font-size: 12px;")
        layout.addWidget(tip)

        body = QHBoxLayout()
        body.setSpacing(10)

        # 左：分类
        left = QVBoxLayout()
        left.addWidget(QLabel("分类"))
        self.cat_list = QListWidget()
        self.cat_list.setMaximumWidth(180)
        self.cat_list.currentTextChanged.connect(self._on_category_changed)
        left.addWidget(self.cat_list)
        cat_btns = QHBoxLayout()
        add_cat_btn = QPushButton("+ 分类")
        add_cat_btn.setStyleSheet(PLAIN_BTN)
        add_cat_btn.clicked.connect(self._add_category)
        left.addLayout(cat_btns)
        cat_btns.addWidget(add_cat_btn)
        body.addLayout(left)

        # 右：短语
        right = QVBoxLayout()
        right.addWidget(QLabel("短语"))
        self.phrase_list = QListWidget()
        self.phrase_list.itemDoubleClicked.connect(lambda _: self._insert())
        right.addWidget(self.phrase_list)
        body.addLayout(right, 1)

        layout.addLayout(body)

        # 底部操作
        btn_bar = QHBoxLayout()
        add_btn = QPushButton("+ 新增短语")
        add_btn.setStyleSheet(PLAIN_BTN)
        add_btn.clicked.connect(self._add_phrase)
        del_btn = QPushButton("删除短语")
        del_btn.setStyleSheet(DANGER_BTN)
        del_btn.clicked.connect(self._del_phrase)
        insert_btn = QPushButton("↩ 插入")
        insert_btn.setStyleSheet(PRIMARY_BTN)
        insert_btn.clicked.connect(self._insert)
        close_btn = QPushButton("关闭")
        close_btn.setStyleSheet(PLAIN_BTN)
        close_btn.clicked.connect(self.reject)

        btn_bar.addWidget(add_btn)
        btn_bar.addWidget(del_btn)
        btn_bar.addStretch()
        btn_bar.addWidget(insert_btn)
        btn_bar.addWidget(close_btn)
        layout.addLayout(btn_bar)

    # ─── 数据刷新 ─────────────────────────────────────────
    def _reload_categories(self):
        self.cat_list.clear()
        cats = self.lib.get_categories()
        self.cat_list.addItems(cats)
        if cats:
            self.cat_list.setCurrentRow(0)

    def _on_category_changed(self, category):
        self.phrase_list.clear()
        if category:
            self.phrase_list.addItems(self.lib.get_phrases(category))

    def _current_category(self):
        item = self.cat_list.currentItem()
        return item.text() if item else None

    # ─── 操作 ─────────────────────────────────────────────
    def _insert(self):
        item = self.phrase_list.currentItem()
        if not item:
            QMessageBox.information(self, "提示", "请先选中一条短语")
            return
        self.selected_phrase = item.text()
        self.phrase_selected.emit(self.selected_phrase)

    def _add_category(self):
        name, ok = QInputDialog.getText(self, "新增分类", "分类名称：")
        if ok and name.strip():
            if self.lib.add_category(name.strip()):
                self._reload_categories()
            else:
                QMessageBox.warning(self, "提示", "分类已存在或名称无效")

    def _add_phrase(self):
        category = self._current_category()
        if not category:
            QMessageBox.information(self, "提示", "请先选择或新增一个分类")
            return
        text, ok = QInputDialog.getMultiLineText(
            self, "新增短语", "短语内容："
        )
        if ok and text.strip():
            if self.lib.add_phrase(category, text.strip()):
                self._on_category_changed(category)
            else:
                QMessageBox.warning(self, "提示", "短语已存在或内容为空")

    def _del_phrase(self):
        category = self._current_category()
        item = self.phrase_list.currentItem()
        if not category or not item:
            QMessageBox.information(self, "提示", "请先选中要删除的短语")
            return
        ret = QMessageBox.question(
            self, "确认删除", "确定删除该短语？",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if ret == QMessageBox.Yes:
            self.lib.remove_phrase(category, item.text())
            self._reload_categories()
