"""
病历库管理对话框
- 表格列出当前用户病历（管理员可见全部）
- 支持关键词搜索、科室/日期筛选、打开回填、删除、导出为 txt
风格与主程序一致（深色科技风）
"""
import os

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QComboBox, QMessageBox, QTableWidget, QTableWidgetItem, QHeaderView,
    QFileDialog, QDateEdit, QWidget
)
from PyQt5.QtCore import Qt, QDate

from login_dialog import DIALOG_STYLE, PRIMARY_BTN, PLAIN_BTN, DANGER_BTN, DEPARTMENTS


class RecordManagerDialog(QDialog):
    """病历库。选中并"打开"后，self.selected_record 保存待回填病历 dict。"""

    def __init__(self, db, current_user, parent=None):
        super().__init__(parent)
        self.db = db
        self.current_user = current_user
        self.is_admin = current_user.get("role") == "admin"
        self.selected_record = None
        self.setWindowTitle("📚 病历库")
        self.setModal(True)
        self.resize(900, 560)
        self.setStyleSheet(DIALOG_STYLE)
        self._records = []
        self._init_ui()
        self._search()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        # 筛选栏
        filter_box = QWidget()
        f = QHBoxLayout(filter_box)
        f.setContentsMargins(0, 0, 0, 0)
        self.keyword_input = QLineEdit()
        self.keyword_input.setPlaceholderText("搜索患者姓名 / 病历内容")
        self.keyword_input.returnPressed.connect(self._search)

        self.dept_filter = QComboBox()
        self.dept_filter.addItem("全部科室", "")
        for d in DEPARTMENTS:
            self.dept_filter.addItem(d, d)

        self.date_from = QDateEdit()
        self.date_from.setCalendarPopup(True)
        self.date_from.setDisplayFormat("yyyy-MM-dd")
        self.date_from.setDate(QDate.currentDate().addMonths(-1))
        self.date_to = QDateEdit()
        self.date_to.setCalendarPopup(True)
        self.date_to.setDisplayFormat("yyyy-MM-dd")
        self.date_to.setDate(QDate.currentDate())

        search_btn = QPushButton("🔍 搜索")
        search_btn.setStyleSheet(PRIMARY_BTN)
        search_btn.clicked.connect(self._search)
        reset_btn = QPushButton("重置")
        reset_btn.setStyleSheet(PLAIN_BTN)
        reset_btn.clicked.connect(self._reset)

        f.addWidget(self.keyword_input, 3)
        f.addWidget(self.dept_filter, 1)
        f.addWidget(QLabel("从"))
        f.addWidget(self.date_from)
        f.addWidget(QLabel("到"))
        f.addWidget(self.date_to)
        f.addWidget(search_btn)
        f.addWidget(reset_btn)
        layout.addWidget(filter_box)

        # 表格
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(
            ["ID", "患者", "科室", "模板", "状态", "更新时间", "操作"]
        )
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.doubleClicked.connect(lambda _: self._open_selected())
        layout.addWidget(self.table)

        self.count_label = QLabel("")
        self.count_label.setStyleSheet("color: #7f8bc0; font-size: 12px;")
        layout.addWidget(self.count_label)

    def _reset(self):
        self.keyword_input.clear()
        self.dept_filter.setCurrentIndex(0)
        self.date_from.setDate(QDate.currentDate().addMonths(-1))
        self.date_to.setDate(QDate.currentDate())
        self._search()

    def _search(self):
        user_id = None if self.is_admin else self.current_user["id"]
        keyword = self.keyword_input.text().strip() or None
        dept = self.dept_filter.currentData() or None
        date_from = self.date_from.date().toString("yyyy-MM-dd")
        date_to = self.date_to.date().toString("yyyy-MM-dd")
        self._records = self.db.search_records(
            user_id=user_id, keyword=keyword, department=dept,
            date_from=date_from, date_to=date_to
        )
        self._fill_table()

    def _fill_table(self):
        self.table.setRowCount(len(self._records))
        for i, r in enumerate(self._records):
            self.table.setItem(i, 0, QTableWidgetItem(str(r["id"])))
            self.table.setItem(i, 1, QTableWidgetItem(r["patient_name"]))
            self.table.setItem(i, 2, QTableWidgetItem(r["department"]))
            self.table.setItem(i, 3, QTableWidgetItem(r["template_name"]))
            self.table.setItem(i, 4, QTableWidgetItem(r["status"]))
            self.table.setItem(i, 5, QTableWidgetItem(r["updated_at"]))

            op_widget = QWidget()
            op = QHBoxLayout(op_widget)
            op.setContentsMargins(4, 2, 4, 2)
            op.setSpacing(6)
            open_btn = QPushButton("打开")
            open_btn.setStyleSheet(PLAIN_BTN)
            open_btn.clicked.connect(lambda _, rid=r["id"]: self._open_by_id(rid))
            export_btn = QPushButton("导出")
            export_btn.setStyleSheet(PLAIN_BTN)
            export_btn.clicked.connect(lambda _, rid=r["id"]: self._export(rid))
            del_btn = QPushButton("删除")
            del_btn.setStyleSheet(DANGER_BTN)
            del_btn.clicked.connect(lambda _, rid=r["id"]: self._delete(rid))
            op.addWidget(open_btn)
            op.addWidget(export_btn)
            op.addWidget(del_btn)
            self.table.setCellWidget(i, 6, op_widget)
        self.count_label.setText("共 %d 条病历" % len(self._records))

    def _current_row_id(self):
        row = self.table.currentRow()
        if row < 0 or row >= len(self._records):
            return None
        return self._records[row]["id"]

    def _open_selected(self):
        rid = self._current_row_id()
        if rid is not None:
            self._open_by_id(rid)

    def _open_by_id(self, record_id):
        self.selected_record = self.db.get_record(record_id)
        self.accept()

    def _export(self, record_id):
        record = self.db.get_record(record_id)
        if not record:
            return
        default_name = "%s_%s.txt" % (
            record["patient_name"] or "病历", record["template_name"] or ""
        )
        path, _ = QFileDialog.getSaveFileName(
            self, "导出病历", default_name, "文本文件 (*.txt)"
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as fp:
                fp.write(record["content"])
            QMessageBox.information(self, "成功", "已导出到：\n%s" % path)
        except Exception as e:
            QMessageBox.warning(self, "导出失败", str(e))

    def _delete(self, record_id):
        ret = QMessageBox.question(
            self, "确认删除", "确定删除该病历？此操作不可撤销。",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if ret == QMessageBox.Yes:
            self.db.delete_record(record_id)
            self._search()
