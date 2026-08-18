"""
集成测试：database.py - 病历 CRUD、搜索、版本
"""
import pytest


class TestDatabaseCRUD:
    """病历 CRUD 测试"""

    def test_create_user(self, db):
        from database import Database
        uid = db.create_user("testuser", "testpass", "内科", "doctor")
        assert uid is not None
        assert isinstance(uid, int)

    def test_verify_user(self, db):
        uid = db.create_user("testuser", "testpass", "内科", "doctor")
        user = db.verify_user("testuser", "testpass")
        assert user is not None
        assert user["id"] == uid
        assert user["username"] == "testuser"
        assert "password_hash" not in user  # 不返回密码哈希

    def test_verify_user_wrong_password(self, db):
        db.create_user("testuser", "testpass", "内科", "doctor")
        assert db.verify_user("testuser", "wrongpass") is None

    def test_create_record(self, db, sample_user):
        rid = db.create_record(
            user_id=sample_user["id"],
            patient_name="张三",
            department="内科",
            template_name="入院记录",
            content="主诉：发热三天",
            status="草稿",
        )
        assert rid is not None
        assert isinstance(rid, int)

    def test_get_record(self, db, sample_record):
        r = db.get_record(sample_record)
        assert r is not None
        assert r["id"] == sample_record
        assert r["patient_name"] == "测试患者"
        assert "发热三天" in r["content"]

    def test_update_record(self, db, sample_record):
        db.update_record(sample_record, content="主诉：发热三天\n现病史：更新内容")
        r = db.get_record(sample_record)
        assert "更新内容" in r["content"]

    def test_delete_record(self, db, sample_record):
        result = db.delete_record(sample_record)
        assert result is True
        assert db.get_record(sample_record) is None

    def test_list_records(self, db, sample_user):
        db.create_record(sample_user["id"], "患者A", "内科", "", "内容A", "草稿")
        db.create_record(sample_user["id"], "患者B", "外科", "", "内容B", "草稿")
        records = db.list_records(user_id=sample_user["id"])
        assert len(records) >= 2

    def test_search_records_by_keyword(self, db, sample_user):
        db.create_record(sample_user["id"], "发热患者", "内科", "", "主诉：发热三天", "草稿")
        db.create_record(sample_user["id"], "头痛患者", "内科", "", "主诉：剧烈头痛", "草稿")
        results = db.search_records(keyword="发热")
        assert len(results) >= 1
        for r in results:
            assert "发热" in r["patient_name"] or "发热" in r["content"]

    def test_record_versions(self, db, sample_user):
        rid = db.create_record(sample_user["id"], "版本测试", "内科", "", "V1", "草稿")
        db.update_record(rid, content="V2")
        db.update_record(rid, content="V3")
        versions = db.get_record_versions(rid)
        assert len(versions) >= 2

    def test_validate_text_max_length(self, db):
        from database import Database
        with pytest.raises(ValueError):
            Database._validate_text("x" * 1001, "test", 1000)

    def test_status_whitelist(self, db, sample_user):
        """无效状态应被修正为默认值"""
        rid = db.create_record(sample_user["id"], "测试", "内科", "", "内容", "无效状态")
        r = db.get_record(rid)
        assert r["status"] == "草稿"


class TestDatabaseEncryption:
    """字段级加密测试"""

    def test_content_is_encrypted_in_db(self, db, sample_user):
        """content 字段在数据库中应被加密"""
        import sqlite3
        long_content = "患者三天前受凉后发热，体温最高38.5摄氏度"  # > 8 chars
        rid = db.create_record(sample_user["id"], "加密测试", "内科", "", long_content, "草稿")
        # 直接查询数据库，绕过 _record_to_dict
        row = db.conn.execute("SELECT content FROM records WHERE id = ?", (rid,)).fetchone()
        stored = row["content"]
        # 加密后的内容不应等于原始内容
        assert long_content not in stored
        assert len(stored) > 10  # 加密后长度增加（Fernet token 至少 ~40 chars）

    def test_content_decrypted_on_read(self, db, sample_user):
        """读取时应自动解密"""
        original = "患者三天前受凉后发热，体温最高38.5摄氏度"
        rid = db.create_record(sample_user["id"], "解密测试", "内科", "", original, "草稿")
        r = db.get_record(rid)
        assert r["content"] == original

    def test_search_on_encrypted_content(self, db, sample_user):
        """加密字段应可通过关键词搜索"""
        rid = db.create_record(sample_user["id"], "搜索测试", "内科", "", "患者发热三天", "草稿")
        results = db.search_records(keyword="发热")
        assert any(r["id"] == rid for r in results)
