"""
测试夹具和共享配置
"""
import os
import sys
import pytest
import tempfile
import shutil

# 确保项目根目录在 sys.path 中
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

# 设置测试环境变量
os.environ.setdefault("XINGYAN_LICENSE_SECRET", "test_secret_1234567890abcdef12345678")
os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_1234567890abcdef123456")


@pytest.fixture
def tmp_db(tmp_path):
    """创建临时数据库路径"""
    db_path = str(tmp_path / "test.db")
    yield db_path
    # 清理
    import glob
    for f in glob.glob(db_path + "*"):
        try:
            os.remove(f)
        except OSError:
            pass


@pytest.fixture
def db(tmp_db):
    """创建并返回 Database 实例（独立实例，非单例）"""
    from database import Database as DBClass
    import threading
    # 重置单例，确保测试隔离
    DBClass._instance = None
    db = DBClass(db_path=tmp_db)
    return db


@pytest.fixture
def sample_user(db):
    """创建测试用户"""
    user_id = db.create_user("testuser", "testpass123", "内科", "doctor")
    assert user_id is not None
    return {"id": user_id, "username": "testuser", "password": "testpass123"}


@pytest.fixture
def sample_record(db, sample_user):
    """创建测试病历"""
    rid = db.create_record(
        user_id=sample_user["id"],
        patient_name="测试患者",
        department="内科",
        template_name="入院记录",
        content="主诉：发热三天\n现病史：患者三天前受凉后发热，体温最高38.5摄氏度",
        status="草稿",
    )
    return rid
