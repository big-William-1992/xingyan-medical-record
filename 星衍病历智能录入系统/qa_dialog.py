#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""知识问答对话框"""
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                             QLineEdit, QTextEdit, QPushButton, QSplitter)
from PyQt5.QtCore import Qt


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
        hint = QLabel("💬 请输入问题，例如：\n  • 高血压的常见治疗方案\n  • 二甲双胍说明书\n  • 高血压和糖尿病的区别")
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
        self.answer_browser.setOpenExternalLinks(True)
        self.answer_browser.setStyleSheet("""
            QTextBrowser {
                background: rgba(255,255,255,0.03); border: 1px solid rgba(0,212,255,0.15);
                border-radius: 8px; padding: 10px; font-size: 13px; color: #f0f0f0;
            }
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
            html = f"<pre style='white-space: pre-wrap;'>{r['text']}</pre>"
            self.answer_browser.setHtml(html)
            self.suggest_label.setText("💡 " + " | ".join(r.get("suggestions", []))[:150])
        except Exception as e:
            self.answer_browser.setHtml(f"⚠ 错误：<br>{str(e)}")
            self.suggest_label.setText("")

    def set_question_and_ask(self, question):
        """设置问题并立即提问（外部可调用）"""
        self.input_edit.setText(question)
        self._ask()
