"""
软件授权管理
- 机器指纹采集（MAC + 计算机名 + 磁盘序列号）
- 激活码生成与验证（HMAC-SHA256，离线校验）
- 首次运行自动开始 90 天免费试用，无需激活
- 试用到期后需激活码才能继续使用（激活后永久有效）
- 防时间回拨 + 加密存储

激活码格式：XXXX-XXXX-XXXX-XXXX（16 位十六进制）
"""
import hashlib
import hmac
import json
import os
import platform
import subprocess
import struct
import time
import uuid
from datetime import datetime, timedelta

try:
    from cryptography.fernet import Fernet
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False

# ─── 常量 ────────────────────────────────────────────
# 授权密钥（32 位 hex → 用于 HMAC 签名 + Fernet 派生）
_LICENSE_SECRET = "x7y9a2e4f6b8c0d1e3f5a7b9c2d4e6f8"
# 试用期天数
TRIAL_DAYS = 90
# 授权文件名
_LICENSE_FILE = "license.dat"


class LicenseManager:
    """软件授权管理器"""

    def __init__(self, base_dir=None):
        self._base_dir = base_dir or os.path.dirname(os.path.abspath(__file__))
        self._license_path = os.path.join(self._base_dir, _LICENSE_FILE)
        self._fernet = self._derive_fernet()
        self._license_data = None  # 缓存已加载的授权信息

    # ─── 机器指纹 ─────────────────────────────────────

    @staticmethod
    def get_machine_id() -> str:
        """
        采集机器指纹（跨平台）。
        Windows：MAC + 计算机名 + 主磁盘序列号
        macOS/Linux：MAC + 计算机名
        返回 16 位十六进制字符串。
        """
        parts = []

        # 1. MAC 地址
        mac = uuid.getnode()
        parts.append(f"{mac:012x}")

        # 2. 计算机名
        parts.append(platform.node().strip().lower())

        # 3. 磁盘序列号（仅 Windows）
        if platform.system() == "Windows":
            serial = LicenseManager._get_windows_disk_serial()
            if serial:
                parts.append(serial)

        raw = "|".join(parts)
        h = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        return h[:16].upper()

    @staticmethod
    def _get_windows_disk_serial() -> str:
        """获取 Windows 主磁盘序列号"""
        try:
            result = subprocess.run(
                ["wmic", "diskdrive", "get", "serialnumber", "/format:list"],
                capture_output=True, text=True, timeout=5,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
            )
            for line in result.stdout.strip().split("\n"):
                line = line.strip()
                if line.startswith("SerialNumber="):
                    serial = line.split("=", 1)[1].strip()
                    if serial:
                        return serial
        except Exception:
            pass
        return ""

    # ─── 激活码生成 / 验证 ─────────────────────────────

    @staticmethod
    def generate_activation_code(machine_id: str) -> str:
        """
        根据机器码生成激活码。
        格式：XXXX-XXXX-XXXX-XXXX
        """
        machine_id = machine_id.strip().upper()
        # HMAC 签名
        sig = hmac.new(
            _LICENSE_SECRET.encode("utf-8"),
            machine_id.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        # 取前 16 位，与机器码前 8 位组合
        code = (machine_id[:8] + sig[:8]).upper()
        # 格式化为 XXXX-XXXX-XXXX-XXXX
        return "-".join(code[i:i+4] for i in range(0, 16, 4))

    @staticmethod
    def verify_activation_code(machine_id: str, code: str) -> bool:
        """验证激活码是否匹配当前机器"""
        machine_id = machine_id.strip().upper()
        code = code.strip().replace("-", "").upper()
        if len(code) != 16:
            return False
        # 前 8 位必须匹配机器码前 8 位
        if code[:8] != machine_id[:8]:
            return False
        # 生成正确激活码对比
        expected = LicenseManager.generate_activation_code(machine_id)
        expected_raw = expected.replace("-", "")
        return code == expected_raw

    # ─── 授权文件读写 ──────────────────────────────────

    def _derive_fernet(self):
        """从密钥派生 Fernet 实例"""
        if not HAS_CRYPTO:
            return None
        import base64
        key = hashlib.sha256(_LICENSE_SECRET.encode()).digest()
        fernet_key = base64.urlsafe_b64encode(key)
        return Fernet(fernet_key)

    def _save_license(self, data: dict):
        """加密保存授权信息"""
        raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
        if self._fernet:
            encrypted = self._fernet.encrypt(raw)
            with open(self._license_path, "wb") as f:
                f.write(encrypted)
        else:
            # fallback: base64 编码（无 cryptography 时）
            import base64
            with open(self._license_path, "wb") as f:
                f.write(base64.b64encode(raw))

    def _load_license(self) -> dict | None:
        """读取并解密授权信息"""
        if not os.path.exists(self._license_path):
            return None
        try:
            with open(self._license_path, "rb") as f:
                raw = f.read()
            if self._fernet:
                decrypted = self._fernet.decrypt(raw)
            else:
                import base64
                decrypted = base64.b64decode(raw)
            return json.loads(decrypted.decode("utf-8"))
        except Exception:
            return None

    # ─── 授权状态检查 ──────────────────────────────────

    def check_license(self) -> dict:
        """
        检查授权状态。
        状态流转：
          首次运行 → 自动创建试用记录 → "trial"
          试用期内（≤90天）→ "trial"
          试用到期（>90天）且未激活 → "expired"
          已输入激活码 → "activated"（永久有效）
        """
        machine_id = self.get_machine_id()
        data = self._load_license()
        now = time.time()

        # ── 首次运行：自动创建试用记录 ──
        if data is None:
            data = {
                "machine_id": machine_id,
                "first_run_time": now,
                "last_run_time": now,
                "run_count": 1,
                "activated": False,
                "activation_code": "",
                "version": 1,
            }
            self._save_license(data)
            return self._trial_status(machine_id, data)

        # ── 机器码校验 ──
        if data.get("machine_id") != machine_id:
            return {
                "status": "tampered",
                "machine_id": machine_id,
                "message": "授权信息与当前计算机不匹配，请联系管理员",
                "days_remaining": None,
                "first_run_at": None,
            }

        # ── 防时间回拨 ──
        last_run = data.get("last_run_time", 0)
        if last_run > now + 3600:
            return {
                "status": "tampered",
                "machine_id": machine_id,
                "message": "检测到系统时间异常（可能回拨），请联系管理员",
                "days_remaining": None,
                "first_run_at": self._fmt_time(data.get("first_run_time")),
            }

        # ── 已激活（永久有效）──
        if data.get("activated"):
            stored_code = data.get("activation_code", "")
            if stored_code and self.verify_activation_code(machine_id, stored_code):
                data["last_run_time"] = now
                data["run_count"] = data.get("run_count", 0) + 1
                self._save_license(data)
                return {
                    "status": "activated",
                    "machine_id": machine_id,
                    "message": "软件已激活，可永久使用",
                    "days_remaining": None,
                    "first_run_at": self._fmt_time(data.get("first_run_time")),
                }

        # ── 试用期计算 ──
        data["last_run_time"] = now
        data["run_count"] = data.get("run_count", 0) + 1
        self._save_license(data)
        return self._trial_status(machine_id, data)

    def _trial_status(self, machine_id: str, data: dict) -> dict:
        """计算试用期状态"""
        first_run = data.get("first_run_time", time.time())
        first_run_dt = datetime.fromtimestamp(first_run)
        # 按日期计算，首日为第 1 天（剩余 90 天）
        expiry_date = (first_run_dt + timedelta(days=TRIAL_DAYS)).date()
        remaining = (expiry_date - datetime.now().date()).days
        first_run_str = first_run_dt.strftime("%Y-%m-%d %H:%M:%S")

        if remaining <= 0:
            return {
                "status": "expired",
                "machine_id": machine_id,
                "message": f"{TRIAL_DAYS} 天免费试用已到期，请输入激活码继续使用",
                "days_remaining": 0,
                "first_run_at": first_run_str,
            }
        return {
            "status": "trial",
            "machine_id": machine_id,
            "message": f"免费试用中，剩余 {remaining} 天",
            "days_remaining": remaining,
            "first_run_at": first_run_str,
        }

    @staticmethod
    def _fmt_time(ts) -> str:
        if not ts:
            return ""
        try:
            return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            return ""

    # ─── 激活 ─────────────────────────────────────────

    def activate(self, activation_code: str) -> dict:
        """
        使用激活码激活软件（试用到期后使用，激活后永久有效）。
        返回 {"success": bool, "message": str}
        """
        machine_id = self.get_machine_id()

        if not self.verify_activation_code(machine_id, activation_code):
            return {"success": False, "message": "激活码无效，请检查机器码与激活码是否匹配"}

        # 加载已有数据（保留 first_run_time）或新建
        data = self._load_license() or {}
        data.update({
            "machine_id": machine_id,
            "activated": True,
            "activation_code": activation_code.replace("-", "").upper(),
            "last_run_time": time.time(),
        })
        if "first_run_time" not in data:
            data["first_run_time"] = time.time()
        self._save_license(data)
        return {
            "success": True,
            "message": "激活成功！软件已永久授权，可继续使用。",
        }

    def reset(self):
        """删除授权文件（用于测试或重新激活）"""
        if os.path.exists(self._license_path):
            os.remove(self._license_path)
        self._license_data = None

    def get_machine_id_display(self) -> str:
        """返回格式化机器码（每 4 位用空格分隔）"""
        mid = self.get_machine_id()
        return " ".join(mid[i:i+4] for i in range(0, len(mid), 4))
