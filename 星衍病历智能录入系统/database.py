"""
数据库封装（SQLite，本地离线）
- 单例模式，数据文件存放于 data/records.db
- 表：users（用户）、records（病历）、record_versions（病历历史版本）
- 密码采用 sha256 + 随机 salt 哈希存储，不保存明文
"""
import atexit
import os
import sqlite3
import hashlib
import threading
from datetime import datetime

try:
    import bcrypt
    HAS_BCRYPT = True
except ImportError:
    bcrypt = None
    HAS_BCRYPT = False

try:
    from cryptography.fernet import Fernet
    HAS_FERNET = True
except ImportError:
    Fernet = None
    HAS_FERNET = False

# 敏感字段（需加密后存储）
_FIELD_ENC_MIN_LEN = 8   # 加密字段最短长度（避免对空值做无用加密）
_ENCRYPTED_FIELDS = {"content"}  # 需要加密的字段集合


class Database:
    """SQLite 数据访问层（单例）"""

    # ─── 常量 ─────────────────────────────────────────
    MAX_NAME_LEN = 100       # patient_name, template_name 最大长度
    MAX_DEPT_LEN = 50        # department 最大长度
    MAX_CONTENT_LEN = 20000  # content 最大长度

    _instance = None
    _lock = threading.Lock()
    _upgrade_failures: dict = {}  # {user_id: count} 密码升级失败次数

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
        # 二次锁：防止多线程同时进入初始化
        with Database._lock:
            if getattr(self, "_initialized", False):
                return
            base_dir = os.path.dirname(os.path.abspath(__file__))
            data_dir = os.path.join(base_dir, "data")
            os.makedirs(data_dir, exist_ok=True)
            self.db_path = db_path or os.path.join(data_dir, "records.db")
            # check_same_thread=False：允许 Qt 后台线程访问；用锁保证串行
            self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self.conn.row_factory = sqlite3.Row
            self.conn.execute("PRAGMA journal_mode=WAL")       # WAL：多线程读写不互相阻塞
            self.conn.execute("PRAGMA synchronous=NORMAL")     # 性能与安全平衡
            self.conn.execute("PRAGMA foreign_keys = ON")
            self._op_lock = threading.Lock()
            self._create_tables()
            self._fernet = self._derive_fernet() if HAS_FERNET else None
            self._initialized = True
            # 注册进程退出时的清理钩子
            atexit.register(self._atexit_cleanup)

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

    # ==================== 字段加密 ====================
    @staticmethod
    def _derive_fernet():
        """从机器指纹派生 Fernet 密钥（与 license_manager 一致的可移植机器 ID）"""
        if not HAS_FERNET:
            return None
        import hashlib
        import base64
        try:
            # 延迟导入避免循环依赖
            from license_manager import LicenseManager
            machine_raw = LicenseManager.get_machine_id()  # 16 hex chars
        except Exception:
            machine_raw = "xingyan-db-enc"
        key = hashlib.sha256(machine_raw.encode("utf-8")).digest()
        fernet_key = base64.urlsafe_b64encode(key)
        return Fernet(fernet_key)

    @staticmethod
    def _encrypt_field(value: str) -> str:
        """加密字符串；空值/过短值直接返回"""
        if not value or len(value) < _FIELD_ENC_MIN_LEN:
            return value
        db_instance = get_db()
        if not db_instance or not db_instance._fernet:
            return value
        try:
            return db_instance._fernet.encrypt(value.encode("utf-8")).decode("utf-8")
        except Exception:
            return value

    @staticmethod
    def _decrypt_field(value: str) -> str:
        """解密字符串；非加密格式直接返回"""
        if not value or len(value) < _FIELD_ENC_MIN_LEN:
            return value
        db_instance = get_db()
        if not db_instance or not db_instance._fernet:
            return value
        try:
            return db_instance._fernet.decrypt(value.encode("utf-8")).decode("utf-8")
        except Exception:
            return value

    # ==================== 密码哈希 ====================
    # bcrypt 格式: $2b$<cost>$<22-char-salt><31-char-hash> (60 chars)
    # 旧 SHA256 格式: 64 hex chars (无前缀)
    _BCRYPT_PREFIX = "$2b$"

    @staticmethod
    def _is_bcrypt_hash(h):
        """检测是否为 bcrypt 哈希格式"""
        return isinstance(h, str) and h.startswith(Database._BCRYPT_PREFIX) and len(h) == 60

    @staticmethod
    def _hash_password(password):
        """使用 bcrypt 哈希密码（自动生成 salt）"""
        if not HAS_BCRYPT:
            raise RuntimeError("bcrypt 未安装，请运行: pip install bcrypt")
        return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    @staticmethod
    def _verify_password(password, stored_hash):
        """验证密码，自动兼容旧 SHA256 哈希（迁移时自动升级为 bcrypt）"""
        if Database._is_bcrypt_hash(stored_hash):
            # 新格式：bcrypt
            return bcrypt.checkpw(password.encode("utf-8"), stored_hash.encode("utf-8"))
        elif len(stored_hash) == 64 and all(c in "0123456789abcdef" for c in stored_hash.lower()):
            # 旧格式：SHA256(salt + password)，需用原始 salt 验证
            # 但 hash_password 已改为 bcrypt，salt 不再单独存储
            # 这里只能做 SHA256(password) 的兼容（注意：旧逻辑是 salt+password）
            # 由于旧逻辑 salt 存在数据库的 salt 字段，此函数不接收 salt
            # 因此旧用户首次登录时需要走下面的降级逻辑
            # 实际验证由 verify_user 处理，这里只做 bcrypt 验证
            return False
        return False

    @staticmethod
    def _verify_password_legacy(password, salt, stored_hash):
        """验证旧 SHA256(salt + password) 哈希（仅用于迁移）"""
        return hashlib.sha256((salt + password).encode("utf-8")).hexdigest() == stored_hash

    # ==================== 用户 CRUD ====================
    def has_any_user(self) -> bool:
        with self._op_lock:
            row = self.conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()
            return row["c"] > 0

    def create_user(self, username: str, password: str, department: str = "", role: str = "doctor") -> int | None:
        """创建用户，返回新用户 id；用户名重复返回 None"""
        pwd_hash = self._hash_password(password)
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._op_lock:
            try:
                cur = self.conn.execute(
                    "INSERT INTO users (username, password_hash, salt, department, role, created_at)"
                    " VALUES (?, ?, ?, ?, ?, ?)",
                    (username, pwd_hash, "", department, role, now),
                )
                self.conn.commit()
                return cur.lastrowid
            except sqlite3.IntegrityError:
                return None

    def verify_user(self, username: str, password: str) -> dict | None:
        """校验登录，成功返回用户 dict，失败返回 None。"""
        with self._op_lock:
            row = self.conn.execute(
                "SELECT * FROM users WHERE username = ?", (username,)
            ).fetchone()
        if row is None:
            return None

        pwd_hash = row["password_hash"]
        salt = row["salt"]
        verified = False

        if self._is_bcrypt_hash(pwd_hash):
            # 新 bcrypt 格式
            verified = self._verify_password(password, pwd_hash)
        elif salt and len(pwd_hash) == 64:
            # 旧 SHA256(salt + password) 格式，自动迁移
            verified = self._verify_password_legacy(password, salt, pwd_hash)
            if verified:
                # 透明升级为 bcrypt
                self._upgrade_password(row["id"], password)

        if verified:
            return self._user_to_dict(row)
        return None

    def _upgrade_password(self, user_id: int, password: str) -> None:
        """将用户密码从 SHA256 升级为 bcrypt（静默，不阻塞登录）"""
        try:
            new_hash = self._hash_password(password)
            with self._op_lock:
                self.conn.execute(
                    "UPDATE users SET password_hash = ?, salt = ? WHERE id = ?",
                    (new_hash, "", user_id),
                )
                self.conn.commit()
            print(f"[DB] 用户 #{user_id} 密码已自动升级为 bcrypt")
            self._upgrade_failures.pop(user_id, None)
        except Exception as e:
            count = self._upgrade_failures.get(user_id, 0) + 1
            self._upgrade_failures[user_id] = count
            print(f"[DB] 密码升级失败 (第{count}次): {e}")
            if count >= 3:
                print(f"[DB] ⚠ 用户 #{user_id} 密码升级连续失败 {count} 次，"
                      f"建议联系管理员重置密码")

    def get_user(self, user_id: int) -> dict | None:
        with self._op_lock:
            row = self.conn.execute(
                "SELECT * FROM users WHERE id = ?", (user_id,)
            ).fetchone()
        return self._user_to_dict(row) if row else None

    def list_users(self) -> list[dict]:
        with self._op_lock:
            rows = self.conn.execute(
                "SELECT * FROM users ORDER BY id ASC"
            ).fetchall()
        return [self._user_to_dict(r) for r in rows]

    def update_password(self, user_id: int, new_password: str) -> bool:
        pwd_hash = self._hash_password(new_password)
        with self._op_lock:
            self.conn.execute(
                "UPDATE users SET password_hash = ?, salt = ? WHERE id = ?",
                (pwd_hash, "", user_id),
            )
            self.conn.commit()
        return True

    def update_user(self, user_id: int, department: str | None = None,
                     role: str | None = None) -> bool:
        """更新用户信息（显式列名，避免 SQL 格式化）"""
        fields, params = [], []
        if department is not None:
            fields.append(("department", department))
        if role is not None:
            fields.append(("role", role))
        if not fields:
            return False
        params.append(user_id)
        set_clause = ", ".join(f"{col} = ?" for col, _ in fields)
        params = [v for _, v in fields] + params
        with self._op_lock:
            self.conn.execute(
                f"UPDATE users SET {set_clause} WHERE id = ?", params
            )
            self.conn.commit()
        return True

    def delete_user(self, user_id: int) -> bool:
        with self._op_lock:
            self.conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
            self.conn.commit()
        return True

    @staticmethod
    def _user_to_dict(row) -> dict:
        return {
            "id": row["id"],
            "username": row["username"],
            "department": row["department"],
            "role": row["role"],
            "created_at": row["created_at"],
        }

    # ==================== 病历 CRUD ====================
    @staticmethod
    def _validate_text(value, field: str, max_len: int) -> str:
        if value is None:
            return ""
        v = str(value)
        if len(v) > max_len:
            raise ValueError(f"{field} 超出最大长度 {max_len}，当前 {len(v)} 字符")
        return v

    def create_record(self, user_id: int, patient_name: str = "", department: str = "",
                      template_name: str = "", content: str = "", status: str = "草稿") -> int:
        """创建病历，返回新记录 id"""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        patient_name = self._validate_text(patient_name, "patient_name", self.MAX_NAME_LEN)
        department = self._validate_text(department, "department", self.MAX_DEPT_LEN)
        template_name = self._validate_text(template_name, "template_name", self.MAX_NAME_LEN)
        content = self._validate_text(content, "content", self.MAX_CONTENT_LEN)
        # 敏感字段加密
        enc_content = self._encrypt_field(content)
        if status not in ("草稿", "已提交", "已审核"):
            status = "草稿"
        with self._op_lock:
            try:
                cur = self.conn.execute(
                    "INSERT INTO records (user_id, patient_name, department, template_name,"
                    " content, status, created_at, updated_at)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (user_id, patient_name, department, template_name, enc_content, status, now, now),
                )
                record_id = cur.lastrowid
                self.conn.execute(
                    "INSERT INTO record_versions (record_id, content, created_at)"
                    " VALUES (?, ?, ?)",
                    (record_id, enc_content, now),
                )
                self.conn.commit()
            except Exception:
                self.conn.rollback()
                raise
        return record_id

    def update_record(self, record_id: int, patient_name: str | None = None,
                      department: str | None = None,
                      template_name: str | None = None, content: str | None = None,
                      status: str | None = None) -> bool:
        """更新病历；若 content 变化则写入新版本（敏感字段自动解密返回）"""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        fields, params = [], []
        if patient_name is not None:
            fields.append(("patient_name", self._validate_text(patient_name, "patient_name", self.MAX_NAME_LEN)))
        if department is not None:
            fields.append(("department", self._validate_text(department, "department", self.MAX_DEPT_LEN)))
        if template_name is not None:
            fields.append(("template_name", self._validate_text(template_name, "template_name", self.MAX_NAME_LEN)))
        if content is not None:
            validated_content = self._validate_text(content, "content", self.MAX_CONTENT_LEN)
            fields.append(("content", self._encrypt_field(validated_content)))
        if status is not None:
            if status not in ("草稿", "已提交", "已审核"):
                status = "草稿"
            fields.append(("status", status))
        if not fields:
            return False
        set_clause = ", ".join(f"{col} = ?" for col, _ in fields)
        params = [v for _, v in fields] + [now, record_id]
        with self._op_lock:
            try:
                self.conn.execute(
                    f"UPDATE records SET {set_clause}, updated_at = ? WHERE id = ?", params
                )
                if content is not None:
                    self.conn.execute(
                        "INSERT INTO record_versions (record_id, content, created_at)"
                        " VALUES (?, ?, ?)",
                        (record_id, fields[-1][1], now),
                    )
                self.conn.commit()
            except Exception:
                self.conn.rollback()
                raise
        return True

    def get_record(self, record_id: int) -> dict | None:
        with self._op_lock:
            row = self.conn.execute(
                "SELECT * FROM records WHERE id = ?", (record_id,)
            ).fetchone()
        return self._record_to_dict(row) if row else None

    def delete_record(self, record_id: int) -> bool:
        with self._op_lock:
            self.conn.execute("DELETE FROM records WHERE id = ?", (record_id,))
            self.conn.commit()
        return True

    def list_records(self, user_id: int | None = None) -> list[dict]:
        sql = "SELECT * FROM records"
        params = []
        if user_id is not None:
            sql += " WHERE user_id = ?"
            params.append(user_id)
        sql += " ORDER BY updated_at DESC"
        with self._op_lock:
            rows = self.conn.execute(sql, params).fetchall()
        return [self._record_to_dict(r) for r in rows]

    def search_records(self, user_id: int | None = None, keyword: str | None = None,
                       department: str | None = None,
                       date_from: str | None = None, date_to: str | None = None) -> list[dict]:
        """
        关键词搜索 + 筛选（content 字段加密存储，关键词匹配在解密后 Python 层完成）。
        keyword 对患者名做 LIKE 匹配，对 content 做解密后内存匹配。
        department 精确筛选；date_from/date_to 按 created_at 日期范围（YYYY-MM-DD）。
        """
        sql = "SELECT * FROM records WHERE 1=1"
        params = []
        if user_id is not None:
            sql += " AND user_id = ?"
            params.append(user_id)
        if keyword:
            # content 加密后 SQL LIKE 无效，全部取回后在 Python 层解密过滤
            pass
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
        records = [self._record_to_dict(r) for r in rows]
        # Python 层对解密后的 content 做关键词过滤（SQL 无法对密文做 LIKE）
        if keyword:
            kw = keyword.lower()
            records = [r for r in records
                       if kw in r.get("patient_name", "").lower()
                       or kw in r.get("content", "").lower()]
        return records

    def get_record_versions(self, record_id: int) -> list[dict]:
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
    def _record_to_dict(row) -> dict:
        return {
            "id": row["id"],
            "user_id": row["user_id"],
            "patient_name": row["patient_name"],
            "department": row["department"],
            "template_name": row["template_name"],
            "content": Database._decrypt_field(row["content"]),
            "status": row["status"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def _atexit_cleanup(self) -> None:
        """进程退出时清理资源"""
        try:
            if hasattr(self, 'conn') and self.conn:
                self.conn.close()
        except Exception:
            pass

    def close(self):
        try:
            self.conn.close()
        except Exception as e:
            print(f"[DB] 关闭连接失败: {e}")

    # ==================== 备份 / 恢复 ====================
    def backup_to(self, dest_path: str) -> str:
        """将数据库完整备份到 dest_path（使用 SQLite 在线备份 API，安全一致）。"""
        with self._op_lock:
            dest = sqlite3.connect(dest_path)
            try:
                self.conn.backup(dest)
            finally:
                dest.close()
        return dest_path

    def auto_backup(self, backup_dir: str | None = None, keep: int = 10) -> str:
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
                try:
                    os.remove(os.path.join(backup_dir, old))
                except OSError:
                    pass  # 文件被占用或已删除，静默跳过
        except Exception as e:
            print(f"[DB] 清理旧备份失败: {e}")
        return dest

    def restore_from(self, src_path: str) -> bool:
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


# 退出时自动关闭数据库连接（释放文件描述符）
import atexit as _atexit
_db_instance = None

def _close_db_on_exit():
    global _db_instance
    if _db_instance is not None:
        try:
            _db_instance.close()
        except Exception:
            pass
    _db_instance = None

_atexit.register(_close_db_on_exit)


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
