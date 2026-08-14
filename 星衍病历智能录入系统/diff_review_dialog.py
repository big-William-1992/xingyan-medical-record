#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
最小 diff 审阅对话框（M1）

职责：
- 接收 original_text / corrected_text / log_items
- 展示逐条可审阅的修改建议
- 支持逐条接受/拒绝、接受全部、拒绝全部
- 返回最终文本和决策记录

接入点：
- main.py:_on_correction_done() 不再直接 setPlainText(corrected)
- 改为先打开 DiffReviewDialog，再按医生决策写回
"""
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QLabel, QWidget, QDialogButtonBox, QMessageBox
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor


class DiffReviewDialog(QDialog):
    def __init__(self, original_text, corrected_text, log_items, parent=None):
        super().__init__(parent)
        self.setWindowTitle("纠错审阅")
        self.resize(720, 460)
        self.original_text = original_text or ""
        self.corrected_text = corrected_text or ""
        self.log_items = [dict(item) for item in (log_items or [])]
        self._decisions = {}

        self._build_ui()
        self._load_changes()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        hint = QLabel("请审阅自动纠错建议，接受或拒绝后点击「确认应用」")
        hint.setStyleSheet("color: #8fa3bf; font-size: 12px;")
        root.addWidget(hint)

        self.change_list = QListWidget()
        self.change_list.setStyleSheet("""
            QListWidget {
                background: rgba(255,255,255,0.03);
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 8px;
                padding: 6px;
                font-size: 12px;
            }
        """)
        root.addWidget(self.change_list)

        action_bar = QWidget()
        bar = QHBoxLayout(action_bar)
        bar.setContentsMargins(0, 0, 0, 0)
        bar.setSpacing(8)

        self.accept_btn = QPushButton("接受当前")
        self.accept_all_btn = QPushButton("全部接受")
        self.reject_btn = QPushButton("拒绝当前")
        self.reject_all_btn = QPushButton("全部拒绝")
        for btn in (self.accept_btn, self.accept_all_btn, self.reject_btn, self.reject_all_btn):
            btn.setMinimumWidth(90)

        bar.addWidget(self.accept_btn)
        bar.addWidget(self.accept_all_btn)
        bar.addWidget(self.reject_btn)
        bar.addWidget(self.reject_all_btn)
        bar.addStretch()
        root.addWidget(action_bar)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.ok_button = buttons.button(QDialogButtonBox.Ok)
        self.ok_button.setText("确认应用")
        root.addWidget(buttons)

        self.accept_btn.clicked.connect(self._accept_current)
        self.accept_all_btn.clicked.connect(self._accept_all)
        self.reject_btn.clicked.connect(self._reject_current)
        self.reject_all_btn.clicked.connect(self._reject_all)
        buttons.accepted.connect(self._on_confirm)
        buttons.rejected.connect(self.reject)
        self.change_list.itemClicked.connect(self._on_item_clicked)

    def _load_changes(self):
        self.change_list.clear()
        self._decisions = {}
        for idx, item in enumerate(self.log_items):
            orig = item.get("原文", "")
            corr = item.get("修正", "")
            cat = item.get("分类", "")
            type_name = item.get("type", "")
            if not orig and not corr:
                continue
            line = f"<b>{type_name or '文本修改'}</b>"
            if cat:
                line += f" <span style='color:#6b8a9a;'>[{cat}]</span>"
            detail = ""
            if orig != corr:
                detail = f"<span style='color:#ff6b6b;'>{orig}</span> → <span style='color:#51cf66;'>{corr}</span>"
            elif orig:
                detail = f"<span style='color:#e0e0e0;'>{orig}</span>"
            full = line + ("<br>" + detail if detail else "")
            list_item = QListWidgetItem(full)
            list_item.setData(Qt.UserRole, idx)
            self.change_list.addItem(list_item)
            self._decisions[idx] = None

    def _on_item_clicked(self, item):
        idx = item.data(Qt.UserRole)
        self._update_buttons(idx)

    def _current_index(self):
        item = self.change_list.currentItem()
        return item.data(Qt.UserRole) if item else None

    def _update_buttons(self, idx):
        decision = self._decisions.get(idx)
        self.accept_btn.setEnabled(decision is not True)
        self.reject_btn.setEnabled(decision is not False)

    def _item_for_index(self, idx):
        for i in range(self.change_list.count()):
            if self.change_list.item(i).data(Qt.UserRole) == idx:
                return self.change_list.item(i)
        return None

    def _set_decision(self, idx, decision):
        if idx is None or idx not in self._decisions:
            return
        self._decisions[idx] = decision
        item = self._item_for_index(idx)
        if not item:
            return
        prefix = "✓ " if decision else "✗ "
        color = QColor("#51cf66" if decision else "#ff6b6b")
        text = item.text()
        for p in ("✓ ", "✗ "):
            if text.startswith(p):
                text = text[len(p):]
                break
        item.setText(prefix + text)
        item.setForeground(color)
        self._update_buttons(idx)

    def _accept_current(self):
        idx = self._current_index()
        if idx is not None:
            self._set_decision(idx, True)

    def _accept_all(self):
        for idx in self._decisions:
            self._set_decision(idx, True)

    def _reject_current(self):
        idx = self._current_index()
        if idx is not None:
            self._set_decision(idx, False)

    def _reject_all(self):
        for idx in self._decisions:
            self._set_decision(idx, False)

    def _apply_decisions(self):
        text = self.corrected_text
        for idx, decision in self._decisions.items():
            item = self.log_items[idx]
            orig = item.get("原文", "")
            corr = item.get("修正", "")
            if not orig or not corr or orig == corr:
                continue
            if decision is False:
                # reject：用原文回滚修正结果
                text = text.replace(corr, orig, 1)
        return text

    def _on_confirm(self):
        undecided = [idx for idx, d in self._decisions.items() if d is None]
        if undecided:
            reply = QMessageBox.question(
                self,
                "未审阅完成",
                f"还有 {len(undecided)} 条建议未审阅，是否全部拒绝后应用？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                for idx in undecided:
                    self._set_decision(idx, False)
            else:
                return
        self.result_text = self._apply_decisions()
        self.accept()

    def decisions(self):
        return dict(self._decisions)
