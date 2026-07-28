#!/usr/bin/env python3
"""
管理员激活码生成工具
用法：
  python gen_license.py                    # 交互模式，输入机器码生成激活码
  python gen_license.py <机器码>           # 直接生成
  python gen_license.py --verify <机器码> <激活码>  # 验证激活码

示例：
  python gen_license.py
  请输入用户机器码: C13D 4B3E 061C 39E1
  激活码: C13D-4B3E-D3C6-BA1B

  python gen_license.py C13D4B3E061C39E1
  激活码: C13D-4B3E-D3C6-BA1B

  python gen_license.py --verify C13D4B3E061C39E1 C13D-4B3E-D3C6-BA1B
  验证结果: ✅ 有效
"""
import sys
import os

# 确保能导入同目录模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from license_manager import LicenseManager


def generate(machine_id: str) -> str:
    """根据机器码生成激活码"""
    # 去除空格
    mid = machine_id.strip().replace(" ", "").upper()
    if len(mid) != 16:
        raise ValueError(f"机器码长度错误（应为 16 位十六进制），当前: {len(mid)} 位")
    code = LicenseManager.generate_activation_code(mid)
    return code


def verify(machine_id: str, code: str) -> bool:
    """验证激活码"""
    mid = machine_id.strip().replace(" ", "").upper()
    return LicenseManager.verify_activation_code(mid, code)


def main():
    args = sys.argv[1:]

    if not args:
        # 交互模式
        print("=" * 50)
        print("  星衍病历智能录入系统 - 激活码生成工具")
        print("=" * 50)
        print()
        mid = input("请输入用户机器码（16位，可带空格）: ").strip()
        try:
            code = generate(mid)
            print()
            print(f"  机器码: {mid.replace(' ', '').upper()}")
            print(f"  激活码: {code}")
            print()
            print("  请将激活码发给用户，在软件中输入即可激活。")
            print(f"  试用期 90 天，到期后需重新生成激活码续期。")
        except ValueError as e:
            print(f"\n  ❌ 错误: {e}")
        print()

    elif args[0] == "--verify" and len(args) >= 3:
        # 验证模式
        mid = args[1]
        code = args[2]
        ok = verify(mid, code)
        if ok:
            print(f"  ✅ 激活码有效")
        else:
            print(f"  ❌ 激活码无效")
        sys.exit(0 if ok else 1)

    elif len(args) == 1:
        # 直接生成
        try:
            code = generate(args[0])
            print(code)
        except ValueError as e:
            print(f"错误: {e}", file=sys.stderr)
            sys.exit(1)

    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
