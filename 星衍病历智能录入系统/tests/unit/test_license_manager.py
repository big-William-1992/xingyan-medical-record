"""
单元测试：license_manager.py
- 机器指纹采集
- 激活码生成/验证
- 试用期状态
- 授权文件读写
"""
import os
import tempfile
import time
import pytest


class TestMachineId:
    """机器指纹测试"""

    def test_get_machine_id_returns_16_hex(self):
        from license_manager import LicenseManager
        mid = LicenseManager.get_machine_id()
        assert len(mid) == 16
        assert all(c in "0123456789abcdefABCDEF" for c in mid)

    def test_machine_id_stable(self):
        from license_manager import LicenseManager
        id1 = LicenseManager.get_machine_id()
        id2 = LicenseManager.get_machine_id()
        assert id1 == id2


class TestActivationCode:
    """激活码测试"""

    def test_generate_format(self):
        from license_manager import LicenseManager
        mid = LicenseManager.get_machine_id()
        code = LicenseManager.generate_activation_code(mid)
        assert len(code) == 19  # XXXX-XXXX-XXXX-XXXX
        assert code[4] == code[9] == code[14] == "-"

    def test_verify_correct_code(self):
        from license_manager import LicenseManager
        mid = LicenseManager.get_machine_id()
        code = LicenseManager.generate_activation_code(mid)
        assert LicenseManager.verify_activation_code(mid, code) is True

    def test_verify_wrong_code(self):
        from license_manager import LicenseManager
        mid = LicenseManager.get_machine_id()
        assert LicenseManager.verify_activation_code(mid, "0000-0000-0000-0000") is False

    def test_verify_wrong_machine(self):
        from license_manager import LicenseManager
        code = LicenseManager.generate_activation_code("ABCDEF1234567890")
        assert LicenseManager.verify_activation_code("1234567890ABCDEF", code) is False


class TestLicenseCheck:
    """授权状态测试"""

    def test_first_run_returns_trial(self, tmp_path):
        from license_manager import LicenseManager
        # 使用独立目录
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            lm = LicenseManager.__new__(LicenseManager)
            lm._license_path = os.path.join(d, "license.dat")
            lm._fernet = lm._derive_fernet()
            status = lm.check_license()
            assert status["status"] == "trial"
            assert status["days_remaining"] == 90

    def test_activated_returns_activated(self, tmp_path):
        from license_manager import LicenseManager
        with tempfile.TemporaryDirectory() as d:
            lm = LicenseManager.__new__(LicenseManager)
            lm._license_path = os.path.join(d, "license.dat")
            lm._fernet = lm._derive_fernet()
            # 首次运行创建试用
            lm.check_license()
            # 激活
            mid = lm.get_machine_id()
            code = LicenseManager.generate_activation_code(mid)
            result = lm.activate(code)
            assert result["success"] is True
            status = lm.check_license()
            assert status["status"] == "activated"
