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
import time
import fcntl
import uuid
from datetime import datetime, timedelta

try:
    from cryptography.fernet import Fernet
except ImportError:
    raise ImportError("cryptography 包是必须的，请运行: pip install cryptography")

# ─── 常量 ────────────────────────────────────────────
# 授权密钥最小长度
LICENSE_SECRET_MIN_LEN = 32
# 授权密钥：必须通过环境变量注入，缺失则禁用激活功能
_LICENSE_SECRET = os.environ.get("XINGYAN_LICENSE_SECRET")
if not _LICENSE_SECRET:
    raise RuntimeError("XINGYAN_LICENSE_SECRET 环境变量未设置，激活功能不可用")
if len(_LICENSE_SECRET) < LICENSE_SECRET_MIN_LEN:
    raise RuntimeError(f"XINGYAN_LICENSE_SECRET 至少需要 {LICENSE_SECRET_MIN_LEN} 字符")
# 试用期天数
TRIAL_DAYS = 90
# 时钟回拨检测阈值（秒）；超过此值视为异常
CLOCK_ROLLBACK_THRESHOLD_SECONDS = 3600
# 授权文件存放路径（用户配置目录，非程序目录）
def _get_license_path() -> str:
    base = os.environ.get("XDG_DATA_HOME", os.path.join(os.path.expanduser("~"), ".local", "share"))
    lic_dir = os.path.join(base, "xingyan")
    os.makedirs(lic_dir, exist_ok=True)
    return os.path.join(lic_dir, "license.dat")
_LICENSE_FILE = None  # 延迟初始化（需要时调用 _get_license_path()）


class LicenseManager:
    """软件授权管理器"""

    def __init__(self, base_dir=None):
        self._base_dir = base_dir or os.path.dirname(os.path.abspath(__file__))
        if _LICENSE_FILE is None:
            self._license_path = _get_license_path()
        else:
            self._license_path = os.path.join(self._base_dir, _LICENSE_FILE)
        self._fernet = self._derive_fernet()
        self._license_data = None

    # ─── 机器指纹 ─────────────────────────────────────

    @staticmethod
    def get_machine_id() -> str:
        """
        采集机器指纹（跨平台，多硬件因子）。
        Windows：MAC + CPU 序列号 + 主磁盘序列号 + 计算机名
        macOS：MAC + 磁盘 UUID + 计算机名
        Linux：MAC + CPU 序列号 + 磁盘 UUID + 主机名
        返回 16 位十六进制字符串。
        """
        parts = []

        # 1. MAC 地址
        mac = uuid.getnode()
        if mac and mac != 0 and mac != (2**48 - 1):
            parts.append(f"mac:{mac:012x}")

        # 2. CPU 序列号/标识符
        cpu_id = LicenseManager._get_cpu_id()
        if cpu_id:
            parts.append(f"cpu:{cpu_id}")

        # 3. 磁盘序列号 / UUID
        disk_id = LicenseManager._get_disk_id()
        if disk_id:
            parts.append(f"disk:{disk_id}")

        # 4. 计算机名
        hostname = platform.node().strip().lower()
        if hostname:
            parts.append(f"host:{hostname}")

        raw = "|".join(parts)
        h = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        return h[:16].upper()

    @staticmethod
    def _get_cpu_id() -> str:
        """获取 CPU 标识符"""
        try:
            system = platform.system()
            if system == "Windows":
                result = subprocess.run(
                    ["wmic", "cpu", "get", "ProcessorId", "/format:list"],
                    capture_output=True, text=True, timeout=5,
                    creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
                )
                for line in result.stdout.strip().split("\n"):
                    line = line.strip()
                    if line.startswith("ProcessorId="):
                        return line.split("=", 1)[1].strip()
            elif system == "Darwin":  # macOS
                result = subprocess.run(
                    ["sysctl", "-n", "machdep.cpu.brand_string"],
                    capture_output=True, text=True, timeout=5,
                )
                brand = result.stdout.strip()
                if brand:
                    return hashlib.md5(brand.encode()).hexdigest()[:16]
            elif system == "Linux":
                for path in ["/proc/cpuinfo", "/sys/devices/virtual/dmi/id/product_uuid"]:
                    if os.path.exists(path):
                        with open(path, "r") as f:
                            content = f.read()
                        for line in content.split("\n"):
                            if "Serial" in line or "Processor" in line or "model name" in line:
                                val = line.split(":", 1)[1].strip() if ":" in line else ""
                                if val:
                                    return hashlib.md5(val.encode()).hexdigest()[:16]
        except Exception:
            pass
        return ""

    @staticmethod
    def _get_disk_id() -> str:
        """获取磁盘序列号 / UUID"""
        try:
            system = platform.system()
            if system == "Windows":
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
            elif system == "Darwin":  # macOS
                result = subprocess.run(
                    ["diskutil", "info", "/", "-plist"],
                    capture_output=True, text=True, timeout=5,
                )
                for line in result.stdout.split("\n"):
                    if "VolumeUUID" in line or "DiskUUID" in line:
                        val = line.split("=", 1)[1].strip().strip('"')
                        if val:
                            return val
            elif system == "Linux":
                result = subprocess.run(
                    ["lsblk", "-d", "-o", "NAME,SERIAL", "-n"],
                    capture_output=True, text=True, timeout=5,
                )
                first = result.stdout.strip().split("\n")[0]
                if first:
                    parts = first.split()
                    if len(parts) >= 2:
                        return parts[1].strip()
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

    def _derive_fernet(self) -> Fernet:
        """从密钥派生 Fernet 实例"""
        import base64
        key = hashlib.sha256(_LICENSE_SECRET.encode()).digest()
        fernet_key = base64.urlsafe_b64encode(key)
        return Fernet(fernet_key)

    def _save_license(self, data: dict) -> None:
        """加密保存授权信息（Fernet 强加密 + 文件锁）"""
        raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
        encrypted = self._fernet.encrypt(raw)
        lock_path = self._license_path + ".lock"
        with open(lock_path, "w") as lock_file:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            try:
                with open(self._license_path, "wb") as f:
                    f.write(encrypted)
            finally:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

    def _load_license(self) -> dict | None:
        """读取并解密授权信息"""
        if not os.path.exists(self._license_path):
            return None
        lock_path = self._license_path + ".lock"
        try:
            with open(lock_path, "w") as lock_file:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_SH)
                try:
                    with open(self._license_path, "rb") as f:
                        raw = f.read()
                    if self._fernet:
                        decrypted = self._fernet.decrypt(raw)
                    else:
                        import base64
                        decrypted = base64.b64decode(raw)
                    return json.loads(decrypted.decode("utf-8"))
                finally:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
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
        if last_run > now + CLOCK_ROLLBACK_THRESHOLD_SECONDS:
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
        """计算试用期状态（防时间回拨：以 last_run_time 为下界）"""
        first_run = data.get("first_run_time", time.time())
        last_run = data.get("last_run_time", first_run)
        # 取系统时间与上次记录时间的较大值，防止用户回拨时钟延长试用
        effective_now = max(time.time(), last_run)
        first_run_dt = datetime.fromtimestamp(first_run)
        # 试用期按 first_run 起算 90 天
        expiry_date = (first_run_dt + timedelta(days=TRIAL_DAYS)).date()
        current_date = datetime.fromtimestamp(effective_now).date()
        remaining = (expiry_date - current_date).days
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

    def reset(self) -> None:
        """删除授权文件（用于测试或重新激活）"""
        if os.path.exists(self._license_path):
            os.remove(self._license_path)
        self._license_data = None

    def get_machine_id_display(self) -> str:
        """返回格式化机器码（每 4 位用空格分隔）"""
        mid = self.get_machine_id()
        return " ".join(mid[i:i+4] for i in range(0, len(mid), 4))
