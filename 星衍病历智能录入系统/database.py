"""
数据库封装（SQLite，本地离线）
- 单例模式，数据文件存放于 data/records.db
- 表：users（用户）、records（病历）、record_versions（病历历史版本）
- 密码采用 sha256 + 随机 salt 哈希存储，不保存明文
"""
import os
import sqlite3
import hashlib
import secrets
import threading
from datetime import datetime


class Database:
    """SQLite 数据访问层（单例）"""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self, db_path=None):
        if getattr(self, "_initialized", False):
            return
        base_dir = os.path.dirname(os.path.abspath(__file__))
        data_dir = os.path.join(base_dir, "data")
        os.makedirs(data_dir, exist_ok=True)
        self.db_path = db_path or os.path.join(data_dir, "records.db")
        # check_same_thread=False：允许 Qt 后台线程访问；用锁保证串行
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self._op_lock = threading.Lock()
        self._create_tables()
        self._initialized = True

    # ==================== 建表 ====================
    def _create_tables(self):
        with self._op_lock:
            cur = self.conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    username     TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    salt         TEXT NOT NULL,
                    department   TEXT DEFAULT '',
                    role         TEXT DEFAULT 'doctor',
                    created_at   TEXT NOT NULL
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS records (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id      INTEGER NOT NULL,
                    patient_name TEXT DEFAULT '',
                    department   TEXT DEFAULT '',
                    template_name TEXT DEFAULT '',
                    content      TEXT DEFAULT '',
                    status       TEXT DEFAULT '草稿',
                    created_at   TEXT NOT NULL,
                    updated_at   TEXT NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS record_versions (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    record_id    INTEGER NOT NULL,
                    content      TEXT DEFAULT '',
                    created_at   TEXT NOT NULL,
                    FOREIGN KEY (record_id) REFERENCES records(id) ON DELETE CASCADE
                )
            """)
            self.conn.commit()

    # ==================== 密码哈希 ====================
    @staticmethod
    def _hash_password(password, salt):
        return hashlib.sha256((salt + password).encode("utf-8")).hexdigest()

    # ==================== 用户 CRUD ====================
    def has_any_user(self):
        with self._op_lock:
            row = self.conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()
            return row["c"] > 0

    def create_user(self, username, password, department="", role="doctor"):
        """创建用户，返回新用户 id；用户名重复返回 None"""
        salt = secrets.token_hex(16)
        pwd_hash = self._hash_password(password, salt)
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._op_lock:
            try:
                cur = self.conn.execute(
                    "INSERT INTO users (username, password_hash, salt, department, role, created_at)"
                    " VALUES (?, ?, ?, ?, ?, ?)",
                    (username, pwd_hash, salt, department, role, now),
                )
                self.conn.commit()
                return cur.lastrowid
            except sqlite3.IntegrityError:
                return None

    def verify_user(self, username, password):
        """校验登录，成功返回用户 dict，失败返回 None"""
        with self._op_lock:
            row = self.conn.execute(
                "SELECT * FROM users WHERE username = ?", (username,)
            ).fetchone()
        if row is None:
            return None
        if self._hash_password(password, row["salt"]) == row["password_hash"]:
            return self._user_to_dict(row)
        return None

    def get_user(self, user_id):
        with self._op_lock:
            row = self.conn.execute(
                "SELECT * FROM users WHERE id = ?", (user_id,)
            ).fetchone()
        return self._user_to_dict(row) if row else None

    def list_users(self):
        with self._op_lock:
            rows = self.conn.execute(
                "SELECT * FROM users ORDER BY id ASC"
            ).fetchall()
        return [self._user_to_dict(r) for r in rows]

    def update_password(self, user_id, new_password):
        salt = secrets.token_hex(16)
        pwd_hash = self._hash_password(new_password, salt)
        with self._op_lock:
            self.conn.execute(
                "UPDATE users SET password_hash = ?, salt = ? WHERE id = ?",
                (pwd_hash, salt, user_id),
            )
            self.conn.commit()
        return True

    def update_user(self, user_id, department=None, role=None):
        sets, params = [], []
        if department is not None:
            sets.append("department = ?")
            params.append(department)
        if role is not None:
            sets.append("role = ?")
            params.append(role)
        if not sets:
            return False
        params.append(user_id)
        with self._op_lock:
            self.conn.execute(
                "UPDATE users SET %s WHERE id = ?" % ", ".join(sets), params
            )
            self.conn.commit()
        return True

    def delete_user(self, user_id):
        with self._op_lock:
            self.conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
            self.conn.commit()
        return True

    @staticmethod
    def _user_to_dict(row):
        return {
            "id": row["id"],
            "username": row["username"],
            "department": row["department"],
            "role": row["role"],
            "created_at": row["created_at"],
        }

    # ==================== 病历 CRUD ====================
    def create_record(self, user_id, patient_name="", department="",
                      template_name="", content="", status="草稿"):
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._op_lock:
            cur = self.conn.execute(
                "INSERT INTO records (user_id, patient_name, department, template_name,"
                " content, status, created_at, updated_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (user_id, patient_name, department, template_name, content, status, now, now),
            )
            record_id = cur.lastrowid
            self.conn.execute(
                "INSERT INTO record_versions (record_id, content, created_at)"
                " VALUES (?, ?, ?)",
                (record_id, content, now),
            )
            self.conn.commit()
        return record_id

    def update_record(self, record_id, patient_name=None, department=None,
                      template_name=None, content=None, status=None):
        """更新病历；若 content 变化则写入新版本"""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sets, params = [], []
        if patient_name is not None:
            sets.append("patient_name = ?")
            params.append(patient_name)
        if department is not None:
            sets.append("department = ?")
            params.append(department)
        if template_name is not None:
            sets.append("template_name = ?")
            params.append(template_name)
        if content is not None:
            sets.append("content = ?")
            params.append(content)
        if status is not None:
            sets.append("status = ?")
            params.append(status)
        if not sets:
            return False
        sets.append("updated_at = ?")
        params.append(now)
        params.append(record_id)
        with self._op_lock:
            self.conn.execute(
                "UPDATE records SET %s WHERE id = ?" % ", ".join(sets), params
            )
            if content is not None:
                self.conn.execute(
                    "INSERT INTO record_versions (record_id, content, created_at)"
                    " VALUES (?, ?, ?)",
                    (record_id, content, now),
                )
            self.conn.commit()
        return True

    def get_record(self, record_id):
        with self._op_lock:
            row = self.conn.execute(
                "SELECT * FROM records WHERE id = ?", (record_id,)
            ).fetchone()
        return self._record_to_dict(row) if row else None

    def delete_record(self, record_id):
        with self._op_lock:
            self.conn.execute("DELETE FROM records WHERE id = ?", (record_id,))
            self.conn.commit()
        return True

    def list_records(self, user_id=None):
        sql = "SELECT * FROM records"
        params = []
        if user_id is not None:
            sql += " WHERE user_id = ?"
            params.append(user_id)
        sql += " ORDER BY updated_at DESC"
        with self._op_lock:
            rows = self.conn.execute(sql, params).fetchall()
        return [self._record_to_dict(r) for r in rows]

    def search_records(self, user_id=None, keyword=None, department=None,
                       date_from=None, date_to=None):
        """
        关键词搜索 + 筛选。
        keyword 对患者名/内容做 LIKE 模糊匹配；
        department 精确筛选；date_from/date_to 按 created_at 日期范围（YYYY-MM-DD）。
        """
        sql = "SELECT * FROM records WHERE 1=1"
        params = []
        if user_id is not None:
            sql += " AND user_id = ?"
            params.append(user_id)
        if keyword:
            sql += " AND (patient_name LIKE ? OR content LIKE ?)"
            like = "%" + keyword + "%"
            params.extend([like, like])
        if department:
            sql += " AND department = ?"
            params.append(department)
        if date_from:
            sql += " AND date(created_at) >= date(?)"
            params.append(date_from)
        if date_to:
            sql += " AND date(created_at) <= date(?)"
            params.append(date_to)
        sql += " ORDER BY updated_at DESC"
        with self._op_lock:
            rows = self.conn.execute(sql, params).fetchall()
        return [self._record_to_dict(r) for r in rows]

    def get_record_versions(self, record_id):
        with self._op_lock:
            rows = self.conn.execute(
                "SELECT * FROM record_versions WHERE record_id = ? ORDER BY id DESC",
                (record_id,),
            ).fetchall()
        return [
            {"id": r["id"], "record_id": r["record_id"],
             "content": r["content"], "created_at": r["created_at"]}
            for r in rows
        ]

    @staticmethod
    def _record_to_dict(row):
        return {
            "id": row["id"],
            "user_id": row["user_id"],
            "patient_name": row["patient_name"],
            "department": row["department"],
            "template_name": row["template_name"],
            "content": row["content"],
            "status": row["status"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def close(self):
        try:
            self.conn.close()
        except Exception:
            pass

    # ==================== 备份 / 恢复 ====================
    def backup_to(self, dest_path):
        """将数据库完整备份到 dest_path（使用 SQLite 在线备份 API，安全一致）。"""
        with self._op_lock:
            dest = sqlite3.connect(dest_path)
            try:
                self.conn.backup(dest)
            finally:
                dest.close()
        return dest_path

    def auto_backup(self, backup_dir=None, keep=10):
        """自动备份到 data/backups/records_YYYYMMDD_HHMMSS.db，仅保留最近 keep 份。"""
        if backup_dir is None:
            backup_dir = os.path.join(os.path.dirname(self.db_path), "backups")
        os.makedirs(backup_dir, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dest = os.path.join(backup_dir, "records_%s.db" % stamp)
        self.backup_to(dest)
        # 清理旧备份
        try:
            backups = sorted(
                f for f in os.listdir(backup_dir)
                if f.startswith("records_") and f.endswith(".db")
            )
            for old in backups[:-keep]:
                os.remove(os.path.join(backup_dir, old))
        except Exception:
            pass
        return dest

    def restore_from(self, src_path):
        """从备份文件恢复（覆盖当前数据库）。调用方应先确认并重启。"""
        if not os.path.exists(src_path):
            raise FileNotFoundError(src_path)
        with self._op_lock:
            src = sqlite3.connect(src_path)
            try:
                src.backup(self.conn)
                self.conn.commit()
            finally:
                src.close()
        return True


# 便捷单例获取
def get_db():
    return Database()


if __name__ == "__main__":
    # 简单自测
    db = Database()
    if not db.has_any_user():
        uid = db.create_user("admin", "admin123", "全科", "admin")
        print("创建管理员 id =", uid)
    user = db.verify_user("admin", "admin123")
    print("登录校验:", user)
    rid = db.create_record(user["id"], "张三", "内科", "入院记录", "主诉：发热三天", "草稿")
    print("新建病历 id =", rid)
    db.update_record(rid, content="主诉：发热三天\n现病史：患者三天前受凉后发热")
    print("搜索'发热':", len(db.search_records(keyword="发热")), "条")
    print("版本数:", len(db.get_record_versions(rid)))
