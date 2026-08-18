#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
对话框模块
包含：规则管理、模板管理、结构化解析等对话框
"""
import os
import json
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QLineEdit, QTableWidget, QTableWidgetItem, QHeaderView,
    QMessageBox, QTabWidget, QWidget, QFileDialog, QTextEdit,
    QGroupBox, QComboBox, QInputDialog
)
from PyQt5.QtCore import Qt


class RuleManagerDialog(QDialog):
    """纠错规则管理对话框"""
    
    def __init__(self, rule_engine, parent=None):
        super().__init__(parent)
        self.rule_engine = rule_engine
        self.setWindowTitle("📏 纠错规则管理")
        self.resize(800, 600)
        self._init_ui()
    
    def _init_ui(self):
        layout = QVBoxLayout(self)
        
        # 标签页
        tabs = QTabWidget()
        
        # 错别字标签页
        typo_tab = QWidget()
        typo_layout = QVBoxLayout(typo_tab)
        
        # 添加错别字规则
        add_typo = QWidget()
        add_typo_layout = QHBoxLayout(add_typo)
        self.typo_wrong_input = QLineEdit()
        self.typo_wrong_input.setPlaceholderText("错误写法（如：心电围）")
        self.typo_correct_input = QLineEdit()
        self.typo_correct_input.setPlaceholderText("正确写法（如：心电图）")
        add_typo_btn = QPushButton("➕ 添加规则")
        add_typo_btn.clicked.connect(self._add_typo_rule)
        add_typo_layout.addWidget(QLabel("错误："))
        add_typo_layout.addWidget(self.typo_wrong_input)
        add_typo_layout.addWidget(QLabel("正确："))
        add_typo_layout.addWidget(self.typo_correct_input)
        add_typo_layout.addWidget(add_typo_btn)
        typo_layout.addWidget(add_typo)
        
        # 错别字规则列表
        self.typo_table = QTableWidget()
        self.typo_table.setColumnCount(3)
        self.typo_table.setHorizontalHeaderLabels(["错误", "正确", "操作"])
        self.typo_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.typo_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.typo_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Fixed)
        self.typo_table.setColumnWidth(2, 80)
        typo_layout.addWidget(self.typo_table)
        self._refresh_typo_table()
        
        tabs.addTab(typo_tab, "🔤 错别字规则")
        
        # 逻辑错误标签页
        logic_tab = QWidget()
        logic_layout = QVBoxLayout(logic_tab)
        
        # 添加逻辑错误规则
        add_logic = QWidget()
        add_logic_layout = QHBoxLayout(add_logic)
        self.logic_name_input = QLineEdit()
        self.logic_name_input.setPlaceholderText("规则名称（如：疾病与症状不符）")
        self.logic_desc_input = QLineEdit()
        self.logic_desc_input.setPlaceholderText("规则描述")
        add_logic_btn = QPushButton("➕ 添加规则")
        add_logic_btn.clicked.connect(self._add_logic_rule)
        add_logic_layout.addWidget(QLabel("名称："))
        add_logic_layout.addWidget(self.logic_name_input)
        add_logic_layout.addWidget(QLabel("描述："))
        add_logic_layout.addWidget(self.logic_desc_input)
        add_logic_layout.addWidget(add_logic_btn)
        logic_layout.addWidget(add_logic)
        
        # 逻辑错误规则列表
        self.logic_table = QTableWidget()
        self.logic_table.setColumnCount(3)
        self.logic_table.setHorizontalHeaderLabels(["错误模式", "描述", "操作"])
        self.logic_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
        self.logic_table.setColumnWidth(0, 160)
        self.logic_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.logic_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Fixed)
        self.logic_table.setColumnWidth(2, 80)
        logic_layout.addWidget(self.logic_table)
        self._refresh_logic_table()
        
        tabs.addTab(logic_tab, "🧠 逻辑错误规则")
        
        layout.addWidget(tabs)
        
        # 底部按钮
        bottom = QHBoxLayout()
        bottom.addStretch()
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.accept)
        bottom.addWidget(close_btn)
        layout.addLayout(bottom)
    
    def _refresh_typo_table(self):
        """刷新错别字规则列表"""
        rules = self.rule_engine.get_typo_rules()
        self.typo_table.setRowCount(len(rules))
        for i, rule in enumerate(rules):
            self.typo_table.setItem(i, 0, QTableWidgetItem(rule["错误"]))
            self.typo_table.setItem(i, 1, QTableWidgetItem(rule["正确"]))
            del_btn = QPushButton("🗑")
            del_btn.setFixedSize(40, 30)
            del_btn.clicked.connect(lambda _, w=rule["错误"]: self._delete_typo(w))
            self.typo_table.setCellWidget(i, 2, del_btn)
    
    def _refresh_logic_table(self):
        """刷新逻辑错误规则列表"""
        rules = self.rule_engine.get_logic_rules()
        self.logic_table.setRowCount(len(rules))
        for i, rule in enumerate(rules):
            self.logic_table.setItem(i, 0, QTableWidgetItem(rule.get("错误模式", "")))
            self.logic_table.setItem(i, 1, QTableWidgetItem(rule.get("描述", "")))
            del_btn = QPushButton("🗑")
            del_btn.setFixedSize(40, 30)
            del_btn.clicked.connect(lambda _, n=rule["错误模式"]: self._delete_logic(n))
            self.logic_table.setCellWidget(i, 2, del_btn)
    
    def _add_typo_rule(self):
        """添加错别字规则"""
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
        self.parent().status_bar.showMessage(f"📏 {msg}: {wrong} → {correct}")
    
    def _add_logic_rule(self):
        """添加逻辑错误规则"""
        name = self.logic_name_input.text().strip()
        desc = self.logic_desc_input.text().strip()
        if not name or not desc:
            QMessageBox.warning(self, "提示", "请填写规则名称和描述")
            return
        
        self.rule_engine.add_logic_rule(name, desc)
        self.logic_name_input.clear()
        self.logic_desc_input.clear()
        self._refresh_logic_table()
        self.parent().status_bar.showMessage(f"📏 逻辑规则已添加: {name}")
    
    def _delete_typo(self, wrong):
        """删除错别字规则"""
        confirm = QMessageBox.question(
            self, "确认删除",
            f"确定删除规则「{wrong}」吗？",
            QMessageBox.Yes | QMessageBox.No
        )
        if confirm == QMessageBox.Yes:
            self.rule_engine.delete_typo_rule(wrong)
            self._refresh_typo_table()
            self.parent().status_bar.showMessage(f"📏 规则已删除: {wrong}")
    
    def _delete_logic(self, name):
        """删除逻辑错误规则"""
        confirm = QMessageBox.question(
            self, "确认删除",
            f"确定删除规则「{name}」吗？",
            QMessageBox.Yes | QMessageBox.No
        )
        if confirm == QMessageBox.Yes:
            self.rule_engine.delete_logic_rule(name)
            self._refresh_logic_table()
            self.parent().status_bar.showMessage(f"📏 规则已删除: {name}")


class TemplateManagerDialog(QDialog):
    """模板管理对话框"""
    
    def __init__(self, template_engine, parent=None):
        super().__init__(parent)
        self.template_engine = template_engine
        self.setWindowTitle("📝 模板管理")
        self.resize(900, 700)
        self._init_ui()
    
    def _init_ui(self):
        layout = QVBoxLayout(self)
        
        # 科室选择
        dept_layout = QHBoxLayout()
        dept_layout.addWidget(QLabel("科室："))
        self.dept_combo = QComboBox()
        self.dept_combo.addItems(self.template_engine.get_departments())
        self.dept_combo.currentTextChanged.connect(self._load_templates)
        dept_layout.addWidget(self.dept_combo)
        
        add_btn = QPushButton("➕ 新建模板")
        add_btn.clicked.connect(self._add_template)
        dept_layout.addWidget(add_btn)
        
        dept_layout.addStretch()
        layout.addLayout(dept_layout)
        
        # 模板列表
        self.template_list = QTableWidget()
        self.template_list.setColumnCount(4)
        self.template_list.setHorizontalHeaderLabels(["模板名称", "字段数", "创建时间", "操作"])
        self.template_list.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.template_list.horizontalHeader().setSectionResizeMode(1, QHeaderView.Fixed)
        self.template_list.setColumnWidth(1, 80)
        self.template_list.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.template_list.horizontalHeader().setSectionResizeMode(3, QHeaderView.Fixed)
        self.template_list.setColumnWidth(3, 150)
        layout.addWidget(self.template_list)
        
        self._load_templates()
        
        # 底部按钮
        bottom = QHBoxLayout()
        bottom.addStretch()
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.accept)
        bottom.addWidget(close_btn)
        layout.addLayout(bottom)
    
    def _load_templates(self):
        """加载模板列表"""
        dept = self.dept_combo.currentText()
        templates = self.template_engine.get_templates(dept)
        self.template_list.setRowCount(len(templates))
        for i, tpl in enumerate(templates):
            self.template_list.setItem(i, 0, QTableWidgetItem(tpl["name"]))
            field_count = len([l for l in tpl["content"].split("\n") if "：" in l])
            self.template_list.setItem(i, 1, QTableWidgetItem(str(field_count)))
            self.template_list.setItem(i, 2, QTableWidgetItem(tpl.get("created_at", "未知")))
            
            # 操作按钮
            btn_widget = QWidget()
            btn_layout = QHBoxLayout(btn_widget)
            btn_layout.setContentsMargins(0, 0, 0, 0)
            edit_btn = QPushButton("编辑")
            edit_btn.clicked.connect(lambda _, n=tpl["name"]: self._edit_template(n))
            del_btn = QPushButton("删除")
            del_btn.clicked.connect(lambda _, n=tpl["name"]: self._delete_template(n))
            btn_layout.addWidget(edit_btn)
            btn_layout.addWidget(del_btn)
            self.template_list.setCellWidget(i, 3, btn_widget)
    
    def _add_template(self):
        """添加模板"""
        name, ok = QInputDialog.getText(self, "新建模板", "请输入模板名称：")
        if ok and name.strip():
            # 这里应该打开编辑器，简化起见直接创建
            QMessageBox.information(self, "提示", f"模板 '{name}' 创建成功（示例）")
            self._load_templates()
    
    def _edit_template(self, name):
        """编辑模板"""
        QMessageBox.information(self, "提示", f"编辑模板 '{name}'（示例）")
    
    def _delete_template(self, name):
        """删除模板"""
        confirm = QMessageBox.question(
            self, "确认删除",
            f"确定删除模板「{name}」吗？",
            QMessageBox.Yes | QMessageBox.No
        )
        if confirm == QMessageBox.Yes:
            QMessageBox.information(self, "提示", f"模板 '{name}' 已删除（示例）")
            self._load_templates()


class SectionDialog(QDialog):
    """结构化解析对话框"""
    
    def __init__(self, parser, raw_text, parent=None):
        super().__init__(parent)
        self.parser = parser
        self.raw_text = raw_text
        self.setWindowTitle("📋 结构化解析")
        self.resize(800, 600)
        self._init_ui()
    
    def _init_ui(self):
        layout = QVBoxLayout(self)
        
        # 解析结果
        sections = self.parser.parse(self.raw_text)
        
        # 显示解析结果
        for field, content in sections.items():
            group = QGroupBox(field)
            group_layout = QVBoxLayout(group)
            text_edit = QTextEdit()
            text_edit.setPlainText(content)
            text_edit.setReadOnly(True)
            text_edit.setMaximumHeight(100)
            group_layout.addWidget(text_edit)
            layout.addWidget(group)
        
        layout.addStretch()
        
        # 底部按钮
        bottom = QHBoxLayout()
        bottom.addStretch()
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.accept)
        bottom.addWidget(close_btn)
        layout.addLayout(bottom)

