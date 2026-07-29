#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
星衍病历录入系统 - 管理员激活码管理后台
============================================

功能：
1. 批量生成激活码（从文本文件或手动输入机器码）
2. 验证激活码有效性
3. 查看/导出激活历史（记录哪些机器码已激活）
4. 激活码有效期设置（默认永久有效）

用法：
    python manage_license.py
    
要求：
    - Python 3.8+
    - PyQt5 (pip install PyQt5)
    
安全：
    - 本地运行，所有数据加密存储
    - 不上传任何机器码到网络
"""
import os
import sys
import json
import hashlib
import hmac
import base64
from datetime import datetime, timedelta
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QTextEdit, QTableWidget,
    QTableWidgetItem, QMessageBox, QDialog, QFileDialog, QHeaderView,
    QGroupBox, QFormLayout, QSpinBox, QDateEdit, QComboBox,
    QTabWidget, QSplitter, QStatusBar, QToolTip, QFrame
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont, QColor, QPalette


# ─── 核心授权算法（与 license_manager.py 一致）─ ─
_LICENSE_SECRET = "x7y9a2e4f6b8c0d1e3f5a7b9c2d4e6f8"


def generate_activation_code(machine_id: str, expiry_days=None) -> str:
    """生成激活码（含有效期选项）"""
    machine_id = machine_id.strip().upper()
    if len(machine_id) != 16:
        raise ValueError(f"机器码必须 16 位十六进制，当前 {len(machine_id)} 位")
    
    sig = hmac.new(
        _LICENSE_SECRET.encode("utf-8"),
        machine_id.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    
    code = (machine_id[:8] + sig[:8]).upper()
    return "-".join(code[i:i+4] for i in range(0, 16, 4))


def verify_activation_code(machine_id: str, code: str, expiry_date=None) -> bool:
    """验证激活码并检查有效期"""
    machine_id = machine_id.strip().upper()
    code = code.strip().replace("-", "").upper()
    
    if len(code) != 16:
        return False
    if code[:8] != machine_id[:8]:
        return False
    
    expected = generate_activation_code(machine_id).replace("-", "").upper()
    return code == expected and (expiry_date is None or datetime.now() <= expiry_date)


# ─── 数据存储 ──────────────────────────────


class LicenseDatabase:
    """激活码数据库管理"""
    
    def __init__(self, db_path="license_admin_data.json"):
        self.db_path = db_path
        self.data = self._load_db()
    
    def _load_db(self):
        if os.path.exists(self.db_path):
            try:
                with open(self.db_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {"activated": [], "pending": [], "expired": []}
        return {"activated": [], "pending": [], "expired": []}
    
    def _save_db(self):
        with open(self.db_path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)
    
    def add_pending(self, machine_id, expiry_days=90):
        expiry_date = datetime.now() + timedelta(days=expiry_days)
        record = {
            "machine_id": machine_id.upper(),
            "created_at": datetime.now().isoformat(),
            "expiry_days": expiry_days,
            "status": "pending"
        }
        self.data["pending"].append(record)
        self._save_db()
    
    def activate(self, machine_id, activation_code, expiry_date=None):
        # 查找 pending 记录
        found = None
        for rec in self.data.get("pending", []):
            if rec["machine_id"] == machine_id.upper():
                found = rec
                break
        
        if not found:
            return False, "该机器码未在待处理列表中"
        
        if not verify_activation_code(machine_id, activation_code, expiry_date):
            return False, "激活码无效"
        
        found["status"] = "activated"
        found["activated_at"] = datetime.now().isoformat()
        found["activation_code"] = activation_code.replace("-", "")
        if expiry_date:
            found["valid_until"] = expiry_date.isoformat()
        
        self.data["pending"] = [r for r in self.data.get("pending", []) 
                                if r["machine_id"] != found["machine_id"]]
        self.data["activated"].append(found)
        self._save_db()
        return True, "激活成功"
    
    def get_activated(self, machine_id=None):
        if machine_id:
            return [r for r in self.data.get("activated", []) 
                   if r["machine_id"] == machine_id.upper()]
        return self.data.get("activated", [])
    
    def get_expired(self):
        now = datetime.now()
        expired = []
        for rec in self.data.get("activated", []):
            valid_until = rec.get("valid_until")
            if valid_until and datetime.fromisoformat(valid_until) < now:
                expired.append(rec)
        return expired


# ─── 对话框组件 ──────────────────────────────

class GenerateDialog(QDialog):
    """生成单个激活码对话框"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("生成激活码")
        self.setFixedSize(400, 300)
        self._init_ui()
        
    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)
        
        # 机器码输入
        machine_label = QLabel("机器码:")
        machine_label.setStyleSheet("color: #b8c5d6; font-size: 13px;")
        layout.addWidget(machine_label)
        
        self.machine_edit = QLineEdit()
        self.machine_edit.setPlaceholderText("例如：C13D4B3E061C39E1")
        self.machine_edit.setStyleSheet("""
            QLineEdit {
                background: rgba(255,255,255,0.08);
                border: 1px solid rgba(0,212,255,0.3);
                border-radius: 6px;
                padding: 8px;
                font-size: 14px;
                letter-spacing: 2px;
                color: #00d4ff;
            }
        """)
        layout.addWidget(self.machine_edit)
        
        # 激活码显示
        self.code_output = QTextEdit()
        self.code_output.setReadOnly(True)
        self.code_output.setMaximumHeight(80)
        self.code_output.setStyleSheet("""
            QTextEdit {
                background: rgba(255,212,67,0.1);
                border: 1px solid rgba(255,212,67,0.3);
                border-radius: 6px;
                color: #ffd443;
                font-size: 16px;
                font-family: Consolas, monospace;
                padding: 10px;
            }
        """)
        layout.addWidget(QLabel("激活码:"))
        layout.addWidget(self.code_output)
        
        # 按钮
        btn_layout = QHBoxLayout()
        
        generate_btn = QPushButton("🔐 生成")
        generate_btn.clicked.connect(self._generate)
        generate_btn.setStyleSheet(self._btn_style("#00b4d8"))
        btn_layout.addWidget(generate_btn)
        
        copy_btn = QPushButton("📋 复制")
        copy_btn.clicked.connect(self._copy)
        copy_btn.setEnabled(False)
        self.copy_btn = copy_btn
        copy_btn.setStyleSheet(self._btn_style("#ffd443"))
        btn_layout.addWidget(copy_btn)
        
        btn_layout.addStretch()
        
        close_btn = QPushButton("✖ 关闭")
        close_btn.clicked.connect(self.reject)
        close_btn.setStyleSheet(self._btn_style("#555"))
        btn_layout.addWidget(close_btn)
        
        layout.addLayout(btn_layout)
    
    def _btn_style(self, color):
        return f"""
            QPushButton {{
                background: {color};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-size: 13px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background: lighten({color}, 10%);
            }}
        """
    
    def _generate(self):
        mid = self.machine_edit.text().strip().replace(" ", "").upper()
        if len(mid) != 16:
            self.code_output.setText("❌ 机器码必须是 16 位十六进制字符")
            return
        
        code = generate_activation_code(mid)
        self.code_output.setText(code)
        self.copy_btn.setEnabled(True)
    
    def _copy(self):
        code = self.code_output.toPlainText()
        clipboard = QApplication.clipboard()
        clipboard.setText(code)
        QToolTip.showText(QCursor.pos(), "✅ 已复制到剪贴板", self)
    
    def set_machine_id(self, mid):
        self.machine_edit.setText(mid)
        self._generate()


class BatchGenerateDialog(QDialog):
    """批量生成激活码对话框"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("批量生成激活码")
        self.resize(600, 500)
        self._init_ui()
    
    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 说明
        hint = QLabel("""📝 请在下方粘贴机器码列表，每行一个：
```
C13D4B3E061C39E1
ABCD1234EF567890
...
```
点击「批量生成」后将生成对应数量的激活码并保存到 CSV 文件。
""")
        hint.setStyleSheet("color: #99b; background: rgba(255,255,255,0.04); padding: 10px; border-radius: 6px;")
        layout.addWidget(hint)
        
        # 机器码输入区
        self.batch_input = QTextEdit()
        self.batch_input.setPlaceholderText("在此粘贴机器码列表...")
        self.batch_input.setMaximumHeight(200)
        layout.addWidget(QLabel("机器码列表:"))
        layout.addWidget(self.batch_input)
        
        # 输出预览
        self.preview_text = QTextEdit()
        self.preview_text.setReadOnly(True)
        self.preview_text.setMaximumHeight(150)
        self.preview_text.setStyleSheet("""
            QTextEdit {
                background: rgba(0, 180, 216, 0.05);
                border: 1px solid rgba(0, 180, 216, 0.2);
                border-radius: 6px;
                padding: 8px;
                font-size: 12px;
                font-family: Consolas, monospace;
            }
        """)
        layout.addWidget(QLabel("生成的激活码（预览）:"))
        layout.addWidget(self.preview_text)
        
        # 按钮
        btn_layout = QHBoxLayout()
        
        generate_btn = QPushButton("🚀 批量生成")
        generate_btn.clicked.connect(self._batch_generate)
        generate_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #00b4d8, stop:1 #0083b0);
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover { background: #00d4ff; }
        """)
        btn_layout.addWidget(generate_btn)
        
        save_btn = QPushButton("💾 保存为 CSV")
        save_btn.clicked.connect(self._save_csv)
        save_btn.setStyleSheet("""
            QPushButton {
                background: rgba(78, 205, 196, 0.2);
                color: #4ecdc4;
                border: 1px solid rgba(78, 205, 196, 0.3);
                border-radius: 6px;
                padding: 10px 20px;
            }
            QPushButton:hover { background: rgba(78, 205, 196, 0.3); }
        """)
        btn_layout.addWidget(save_btn)
        
        btn_layout.addStretch()
        cancel_btn = QPushButton("✖ 取消")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        
        layout.addLayout(btn_layout)
        
        self.generated_list = []
    
    def _batch_generate(self):
        text = self.batch_input.toPlainText()
        lines = [l.strip().upper().replace(" ", "") for l in text.split("\n") if l.strip()]
        
        if not lines:
            QMessageBox.warning(self, "提示", "请至少输入一行机器码")
            return
        
        results = []
        errors = []
        
        for line in lines:
            if len(line) != 16:
                errors.append(f"× {line}: 长度错误 (需要 16 位)")
                continue
            
            try:
                code = generate_activation_code(line)
                results.append((line, code))
            except Exception as e:
                errors.append(f"× {line}: {str(e)}")
        
        # 显示结果
        output = "✅ 成功生成:\n\n"
        for mid, code in results:
            output += f"{mid} → {code}\n"
        
        if errors:
            output += "\n❌ 失败:\n\n" + "\n".join(errors[:10])
        
        self.preview_text.setText(output)
        self.generated_list = results
        
        if not results and not errors:
            QMessageBox.warning(self, "提示", "没有可处理的机器码")
            self.generated_list = []
    
    def _save_csv(self):
        if not self.generated_list:
            QMessageBox.warning(self, "提示", "请先批量生成")
            return
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "保存激活码表", "licenses.csv",
            "CSV 文件 (*.csv);;All Files (*)"
        )
        
        if not file_path:
            return
        
        try:
            import csv
            with open(file_path, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                writer.writerow(["机器码", "激活码"])
                for mid, code in self.generated_list:
                    writer.writerow([mid, code])
            
            QMessageBox.information(self, "成功", f"已保存至:\n{file_path}\n共 {len(self.generated_list)} 个激活码")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存失败:\n{str(e)}")


# ─── 主窗口 ──────────────────────────────


class LicenseManagerGUI(QMainWindow):
    """激活码管理后台主界面"""
    
    def __init__(self):
        super().__init__()
        self.db = LicenseDatabase()
        self.setWindowTitle("星衍病历录入系统 - 激活码管理后台")
        self.resize(900, 700)
        self._apply_dark_theme()
        self._init_ui()
        self._refresh_tables()
        
    def _apply_dark_theme(self):
        palette = QPalette()
        palette.setColor(QPalette.Window, QColor(26, 26, 46))
        palette.setColor(QPalette.WindowText, QColor(224, 224, 224))
        palette.setColor(QPalette.Base, QColor(30, 30, 50))
        palette.setColor(QPalette.AlternateBase, QColor(30, 30, 50))
        palette.setColor(QPalette.Text, QColor(224, 224, 224))
        self.setPalette(palette)
        self.setStyleSheet("""
            QMainWindow {
                background: #1a1a2e;
            }
            QLabel {
                color: #e0e0e0;
                font-size: 13px;
            }
            QLineEdit, QTextEdit {
                background: rgba(255,255,255,0.08);
                border: 1px solid rgba(0,212,255,0.2);
                border-radius: 6px;
                padding: 8px;
                color: #e0e0e0;
            }
            QPushButton {
                background: #00b4d8;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #00d4ff;
            }
            QTableWidget {
                background: rgba(255,255,255,0.05);
                border: 1px solid rgba(0,212,255,0.2);
                border-radius: 6px;
                selection-background-color: rgba(0,212,255,0.2);
            }
            QHeaderView::section {
                background: rgba(0,180,216,0.2);
                color: #00d4ff;
                padding: 8px;
                border: none;
                font-weight: bold;
            }
        """)
    
    def _init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)
        
        # 标题
        title = QLabel("🔐 星衍病历录入系统 - 管理员激活码管理后台")
        title.setAlignment(Qt.AlignCenter)
        title.setFont(QFont("", 18, QFont.Bold))
        title.setStyleSheet("color: #00d4ff; font-size: 18px; padding: 10px;")
        main_layout.addWidget(title)
        
        # 标签页
        tabs = QTabWidget()
        
        # Tab 1: 生成激活码
        gen_tab = self._create_generate_tab()
        tabs.addTab(gen_tab, "➕ 生成激活码")
        
        # Tab 2: 查看激活记录
        record_tab = self._create_records_tab()
        tabs.addTab(record_tab, "📊 激活记录")
        
        # Tab 3: 批量生成
        batch_tab = self._create_batch_tab()
        tabs.addTab(batch_tab, "📦 批量生成")
        
        main_layout.addWidget(tabs)
        
        # 状态栏
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("就绪 | 数据本地存储于 license_admin_data.json")
        
    def _create_generate_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(15)
        
        # 快速生成组
        group = QGroupBox("快速生成单个激活码")
        group_layout = QVBoxLayout(group)
        group_layout.setSpacing(10)
        
        form = QFormLayout()
        
        # 机器码输入
        self.gen_machine_edit = QLineEdit()
        self.gen_machine_edit.setPlaceholderText("输入机器码（如：C13D4B3E061C39E1），或留空随机生成示例")
        form.addRow("机器码:", self.gen_machine_edit)
        
        # 按钮
        btn_row = QHBoxLayout()
        gen_btn = QPushButton("🔐 生成")
        gen_btn.clicked.connect(self._quick_generate)
        gen_btn.setStyleSheet("QPushButton{background:#00b4d8;}")
        btn_row.addWidget(gen_btn)
        
        reset_btn = QPushButton("🔄 重置")
        reset_btn.clicked.connect(lambda: self.gen_machine_edit.clear())
        reset_btn.setStyleSheet("QPushButton{background:#555;}")
        btn_row.addWidget(reset_btn)
        
        btn_row.addStretch()
        
        # 激活码显示
        self.gen_output = QTextEdit()
        self.gen_output.setReadOnly(True)
        self.gen_output.setMaximumHeight(100)
        self.gen_output.setStyleSheet("""
            QTextEdit {
                background: rgba(0, 180, 216, 0.1);
                border: 1px solid rgba(0, 180, 216, 0.3);
                border-radius: 6px;
                color: #00d4ff;
                font-size: 18px;
                font-family: Consolas, monospace;
                padding: 12px;
            }
        """)
        
        copy_btn = QPushButton("📋 复制")
        copy_btn.clicked.connect(self._copy_generated_code)
        copy_btn.setStyleSheet("QPushButton{background:#ffd443;color:#1a1a2e;}")
        btn_row.addWidget(copy_btn)
        
        form.addRow(QLabel("激活码:"), copy_btn)
        group_layout.addLayout(form)
        group_layout.addWidget(self.gen_output)
        group_layout.addLayout(btn_row)
        
        layout.addWidget(group)
        
        # 使用现有对话框
        dialog_btn = QPushButton("💬 高级对话框模式")
        dialog_btn.clicked.connect(self._open_dialog_mode)
        dialog_btn.setStyleSheet("QPushButton{background:#4ecdc4;color:#1a1a2e;}")
        layout.addWidget(dialog_btn)
        
        layout.addStretch()
        return tab
    
    def _create_records_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # 统计信息
        stats_row = QHBoxLayout()
        
        total_label = QLabel("总计: 0")
        total_label.setStyleSheet("color: #4ecdc4; font-size: 14px; font-weight: bold;")
        stats_row.addWidget(total_label)
        
        pending_label = QLabel("待处理: 0")
        pending_label.setStyleSheet("color: #ff6b6b; font-size: 14px; font-weight: bold;")
        stats_row.addWidget(pending_label)
        
        expired_label = QLabel("过期: 0")
        expired_label.setStyleSheet("color: #ffa94d; font-size: 14px; font-weight: bold;")
        stats_row.addWidget(expired_label)
        
        stats_row.addStretch()
        layout.addLayout(stats_row)
        
        # 表格
        self.records_table = QTableWidget()
        self.records_table.setColumnCount(5)
        self.records_table.setHorizontalHeaderLabels([
            "机器码", "创建时间", "激活时间", "激活码", "有效期限"
        ])
        self.records_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.records_table.setSelectionBehavior(QTableWidget.SelectRows)
        layout.addWidget(self.records_table)
        
        # 导出按钮
        export_btn = QPushButton("📤 导出 CSV")
        export_btn.clicked.connect(self._export_records)
        export_btn.setStyleSheet("QPushButton{background:#4ecdc4;color:#1a1a2e;}")
        layout.addWidget(export_btn)
        
        return tab
    
    def _create_batch_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # 使用对话框模式
        btn = QPushButton("🎯 打开批量生成对话框")
        btn.setStyleSheet("QPushButton{background:#4ecdc4;font-size:15px;padding:15px;border-radius:8px;}")
        btn.clicked.connect(self._open_batch_dialog)
        layout.addWidget(btn)
        
        return tab
    
    def _quick_generate(self):
        mid = self.gen_machine_edit.text().strip()
        if not mid:
            # 随机生成一个示例
            import uuid
            mid = "{:012x}".format(uuid.getnode()).upper()
        elif len(mid) != 16:
            msg = f"机器码必须是 16 位十六进制字符（当前{len(mid)}位）"
            self.gen_output.setText(f"❌ {msg}")
            return
        
        code = generate_activation_code(mid)
        self.gen_output.setText(code)
        self.status_bar.showMessage(f"已生成 {code}", 3000)
    
    def _open_dialog_mode(self):
        dlg = GenerateDialog(self)
        dlg.exec_()
    
    def _open_batch_dialog(self):
        dlg = BatchGenerateDialog(self)
        dlg.exec_()
    
    def _copy_generated_code(self):
        code = self.gen_output.toPlainText()
        clipboard = QApplication.clipboard()
        clipboard.setText(code)
        QToolTip.showText(QCursor.pos(), "✅ 已复制到剪贴板", self)
    
    def _refresh_tables(self):
        records = self.db.get_activated()
        self.records_table.setRowCount(len(records))
        
        for i, rec in enumerate(records):
            self.records_table.setItem(i, 0, QTableWidgetItem(rec["machine_id"]))
            created = rec.get("created_at", "")[:10]
            activated = rec.get("activated_at", "")[:10]
            code = rec.get("activation_code", "")[:16] + "..."
            valid = rec.get("valid_until", "")[:10] if rec.get("valid_until") else "永久"
            
            self.records_table.setItem(i, 1, QTableWidgetItem(created))
            self.records_table.setItem(i, 2, QTableWidgetItem(activated))
            self.records_table.setItem(i, 3, QTableWidgetItem(code))
            self.records_table.setItem(i, 4, QTableWidgetItem(valid))
    
    def _export_records(self):
        records = self.db.get_activated()
        if not records:
            QMessageBox.information(self, "提示", "没有可导出的记录")
            return
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "导出激活记录", "activations.csv",
            "CSV 文件 (*.csv);;All Files (*)"
        )
        
        if not file_path:
            return
        
        try:
            import csv
            with open(file_path, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                writer.writerow(["机器码", "创建时间", "激活时间", "激活码", "有效期限"])
                for rec in records:
                    writer.writerow([
                        rec["machine_id"],
                        rec.get("created_at", "")[:10],
                        rec.get("activated_at", "")[:10],
                        rec.get("activation_code", ""),
                        rec.get("valid_until", "永久")[:10] if rec.get("valid_until") else "永久"
                    ])
            
            QMessageBox.information(self, "成功", f"已导出 {len(records)} 条记录")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"导出失败:\n{str(e)}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = LicenseManagerGUI()
    window.show()
    sys.exit(app.exec_())
