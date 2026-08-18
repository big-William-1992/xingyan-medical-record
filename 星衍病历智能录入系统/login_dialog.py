"""
登录 / 用户管理对话框
- LoginDialog：启动时登录；首次运行（无任何用户）自动进入创建管理员流程
- UserManagerDialog：管理员可增删用户、重置密码、修改科室/角色
风格与主程序一致（深色科技风 #0a0e27 / #00d4ff）
"""
import re
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QComboBox, QMessageBox, QTableWidget, QTableWidgetItem, QHeaderView,
    QWidget, QInputDialog
)
from PyQt5.QtCore import Qt

DEPARTMENTS = ["全科", "外科", "妇产科", "儿科"]
ROLES = [("doctor", "医生"), ("admin", "管理员")]

# 输入校验规则
_USERNAME_RE = re.compile(r'^[a-zA-Z0-9_一-鿿]{3,30}$')  # 3-30 字符，中英文/数字/下划线
_PASSWORD_MIN_LEN = 8  # 最少 8 字符（医疗系统要求更高安全）


def _validate_username(username: str) -> str | None:
    """校验用户名格式，返回错误信息或 None"""
    username = username.strip()
    if not username:
        return "用户名不能为空"
    if len(username) < 3:
        return "用户名至少 3 个字符"
    if len(username) > 30:
        return "用户名最多 30 个字符"
    if not _USERNAME_RE.match(username):
        return "用户名只能包含中文、英文、数字、下划线"
    return None


def _validate_password(password: str, is_admin: bool = False) -> str | None:
    """校验密码复杂度，返回错误信息或 None"""
    if not password:
        return "密码不能为空"
    min_len = _PASSWORD_MIN_LEN + 4 if is_admin else _PASSWORD_MIN_LEN
    if len(password) < _PASSWORD_MIN_LEN:
        return f"密码至少 {_PASSWORD_MIN_LEN} 个字符"
    # 至少包含字母或数字中的一种
    if not any(c.isalpha() or c.isdigit() for c in password):
        return "密码需包含字母或数字"
    return None

DIALOG_STYLE = """
    QDialog { background: #0a0e27; }
    QLabel { color: #c9d6ff; font-size: 13px; }
    QLineEdit, QComboBox {
        background: #141a3a; color: #ffffff; border: 1px solid #2a3566;
        border-radius: 8px; padding: 8px 10px; font-size: 13px;
    }
    QLineEdit:focus, QComboBox:focus { border: 1px solid #00d4ff; }
    QTableWidget {
        background: #141a3a; color: #e6ecff; gridline-color: #2a3566;
        border: 1px solid #2a3566; border-radius: 8px;
    }
    QHeaderView::section {
        background: #1c244e; color: #00d4ff; border: none;
        padding: 6px; font-weight: bold;
    }
"""

PRIMARY_BTN = """
    QPushButton {
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
            stop:0 #00d4ff, stop:1 #0066ff);
        color: #0a0e27; font-weight: bold; padding: 8px 20px;
        border-radius: 16px; font-size: 13px;
    }
    QPushButton:hover { padding: 8px 24px; }
"""

PLAIN_BTN = """
    QPushButton {
        background: #1c244e; color: #c9d6ff; padding: 8px 18px;
        border-radius: 16px; font-size: 13px; border: 1px solid #2a3566;
    }
    QPushButton:hover { background: #263066; }
"""

DANGER_BTN = """
    QPushButton {
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
            stop:0 #ff5566, stop:1 #cc2233);
        color: #ffffff; font-weight: bold; padding: 4px 12px;
        border-radius: 12px; font-size: 12px;
    }
    QPushButton:hover { padding: 4px 16px; }
"""


class LoginDialog(QDialog):
    """登录对话框。成功后 self.current_user 保存登录用户 dict。"""

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.current_user = None
        self.setWindowTitle("星衍病历系统 - 登录")
        self.setModal(True)
        self.resize(380, 260)
        self.setStyleSheet(DIALOG_STYLE)
        self._first_run = not self.db.has_any_user()
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 26, 30, 26)
        layout.setSpacing(14)

        title = QLabel("🩺 星衍 AI 病历录入系统")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("color: #00d4ff; font-size: 18px; font-weight: bold;")
        layout.addWidget(title)

        if self._first_run:
            hint = QLabel("首次运行，请创建管理员账号")
            hint.setAlignment(Qt.AlignCenter)
            hint.setStyleSheet("color: #ffcc66; font-size: 12px;")
            layout.addWidget(hint)

        self.user_input = QLineEdit()
        self.user_input.setPlaceholderText("用户名")
        layout.addWidget(self.user_input)

        self.pwd_input = QLineEdit()
        self.pwd_input.setPlaceholderText("密码")
        self.pwd_input.setEchoMode(QLineEdit.Password)
        self.pwd_input.returnPressed.connect(self._on_submit)
        layout.addWidget(self.pwd_input)

        # 首次运行时增加科室选择
        self.dept_combo = None
        if self._first_run:
            self.dept_combo = QComboBox()
            self.dept_combo.addItems(DEPARTMENTS)
            layout.addWidget(self.dept_combo)

        btn_row = QHBoxLayout()
        self.submit_btn = QPushButton("创建并登录" if self._first_run else "登录")
        self.submit_btn.setStyleSheet(PRIMARY_BTN)
        self.submit_btn.clicked.connect(self._on_submit)
        cancel_btn = QPushButton("退出")
        cancel_btn.setStyleSheet(PLAIN_BTN)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(self.submit_btn)
        layout.addLayout(btn_row)

    def _on_submit(self):
        username = self.user_input.text().strip()
        password = self.pwd_input.text()
        if not username or not password:
            QMessageBox.warning(self, "提示", "请输入用户名和密码")
            return

        # 校验用户名格式
        username_err = _validate_username(username)
        if username_err:
            QMessageBox.warning(self, "输入错误", username_err)
            return

        is_admin = self._first_run
        pwd_err = _validate_password(password, is_admin=is_admin)
        if pwd_err:
            QMessageBox.warning(self, "输入错误", pwd_err)
            return

        if self._first_run:
            dept = self.dept_combo.currentText() if self.dept_combo else "全科"
            uid = self.db.create_user(username, password, dept, "admin")
            if uid is None:
                QMessageBox.warning(self, "错误", "创建失败，用户名已存在")
                return
            self.current_user = self.db.get_user(uid)
            QMessageBox.information(self, "成功", "管理员账号创建成功，已登录")
            self.accept()
            return

        try:
            user = self.db.verify_user(username, password)
        except Exception as e:
            QMessageBox.critical(self, "登录异常", f"验证失败：{e}")
            self.pwd_input.clear()
            return
        if user is None:
            QMessageBox.warning(self, "登录失败", "用户名或密码错误")
            self.pwd_input.clear()
            return
        self.current_user = user
        self.accept()


class UserManagerDialog(QDialog):
    """用户管理（仅管理员）：增删用户、重置密码、修改科室/角色"""

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.setWindowTitle("👥 用户管理")
        self.setModal(True)
        self.resize(720, 460)
        self.setStyleSheet(DIALOG_STYLE)
        self._init_ui()
        self._reload()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        # 新增用户区
        add_box = QWidget()
        add_row = QHBoxLayout(add_box)
        add_row.setContentsMargins(0, 0, 0, 0)
        self.new_user = QLineEdit()
        self.new_user.setPlaceholderText("新用户名")
        self.new_pwd = QLineEdit()
        self.new_pwd.setPlaceholderText("初始密码")
        self.new_dept = QComboBox()
        self.new_dept.addItems(DEPARTMENTS)
        self.new_role = QComboBox()
        for val, label in ROLES:
            self.new_role.addItem(label, val)
        add_btn = QPushButton("➕ 添加用户")
        add_btn.setStyleSheet(PRIMARY_BTN)
        add_btn.clicked.connect(self._add_user)
        add_row.addWidget(self.new_user)
        add_row.addWidget(self.new_pwd)
        add_row.addWidget(self.new_dept)
        add_row.addWidget(self.new_role)
        add_row.addWidget(add_btn)
        layout.addWidget(add_box)

        # 用户表格
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["ID", "用户名", "科室", "角色", "创建时间", "操作"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.table)

        close_btn = QPushButton("关闭")
        close_btn.setStyleSheet(PLAIN_BTN)
        close_btn.clicked.connect(self.accept)
        bottom = QHBoxLayout()
        bottom.addStretch()
        bottom.addWidget(close_btn)
        layout.addLayout(bottom)

    def _reload(self):
        users = self.db.list_users()
        self.table.setRowCount(len(users))
        role_map = dict(ROLES)
        for i, u in enumerate(users):
            self.table.setItem(i, 0, QTableWidgetItem(str(u["id"])))
            self.table.setItem(i, 1, QTableWidgetItem(u["username"]))
            self.table.setItem(i, 2, QTableWidgetItem(u["department"]))
            self.table.setItem(i, 3, QTableWidgetItem(role_map.get(u["role"], u["role"])))
            self.table.setItem(i, 4, QTableWidgetItem(u["created_at"]))

            op_widget = QWidget()
            op_layout = QHBoxLayout(op_widget)
            op_layout.setContentsMargins(4, 2, 4, 2)
            op_layout.setSpacing(6)
            reset_btn = QPushButton("重置密码")
            reset_btn.setStyleSheet(PLAIN_BTN)
            reset_btn.clicked.connect(lambda _, uid=u["id"], name=u["username"]: self._reset_pwd(uid, name))
            del_btn = QPushButton("删除")
            del_btn.setStyleSheet(DANGER_BTN)
            del_btn.clicked.connect(lambda _, uid=u["id"], name=u["username"]: self._delete_user(uid, name))
            op_layout.addWidget(reset_btn)
            op_layout.addWidget(del_btn)
            self.table.setCellWidget(i, 5, op_widget)

    def _add_user(self):
        username = self.new_user.text().strip()
        password = self.new_pwd.text()
        if not username or not password:
            QMessageBox.warning(self, "提示", "请输入用户名和初始密码")
            return
        uid = self.db.create_user(
            username, password,
            self.new_dept.currentText(),
            self.new_role.currentData(),
        )
        if uid is None:
            QMessageBox.warning(self, "错误", "用户名已存在")
            return
        self.new_user.clear()
        self.new_pwd.clear()
        self._reload()

    def _reset_pwd(self, uid, name):
        new_pwd, ok = QInputDialog.getText(
            self, "重置密码", "为用户 %s 设置新密码：" % name, QLineEdit.Password
        )
        if ok and new_pwd:
            self.db.update_password(uid, new_pwd)
            QMessageBox.information(self, "成功", "密码已重置")

    def _delete_user(self, uid, name):
        if len(self.db.list_users()) <= 1:
            QMessageBox.warning(self, "禁止", "至少保留一个用户")
            return
        ret = QMessageBox.question(
            self, "确认删除",
            "确定删除用户 %s？其名下病历也将一并删除。" % name,
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if ret == QMessageBox.Yes:
            self.db.delete_user(uid)
            self._reload()
