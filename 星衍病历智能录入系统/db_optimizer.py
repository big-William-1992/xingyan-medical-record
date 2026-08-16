#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据库性能优化模块
提供数据库查询优化、连接池、缓存等功能
"""
import sqlite3
import threading
import time
from functools import lru_cache
from contextlib import contextmanager


class DatabaseOptimizer:
    """数据库优化器"""
    
    def __init__(self, db_path):
        self.db_path = db_path
        self._connection_pool = []
        self._pool_size = 5
        self._lock = threading.Lock()
        self._init_pool()
    
    def _init_pool(self):
        """初始化连接池"""
        for _ in range(self._pool_size):
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            # 启用WAL模式（写优化）
            conn.execute('PRAGMA journal_mode=WAL')
            # 启用外键约束
            conn.execute('PRAGMA foreign_keys=ON')
            # 设置缓存大小（10MB）
            conn.execute('PRAGMA cache_size=10000')
            # 启用内存映射（读优化）
            conn.execute('PRAGMA mmap_size=268435456')
            self._connection_pool.append(conn)
    
    @contextmanager
    def get_connection(self):
        """从连接池获取连接"""
        with self._lock:
            if self._connection_pool:
                conn = self._connection_pool.pop()
            else:
                conn = sqlite3.connect(self.db_path, check_same_thread=False)
                conn.row_factory = sqlite3.Row
                conn.execute('PRAGMA journal_mode=WAL')
                conn.execute('PRAGMA foreign_keys=ON')
        
        try:
            yield conn
        finally:
            with self._lock:
                self._connection_pool.append(conn)
    
    def optimize_queries(self, conn):
        """优化查询性能"""
        # 创建索引
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_records_updated ON records(updated_at)",
            "CREATE INDEX IF NOT EXISTS idx_records_department ON records(department)",
            "CREATE INDEX IF NOT EXISTS idx_records_patient ON records(patient_name)",
            "CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)",
        ]
        
        for index_sql in indexes:
            try:
                conn.execute(index_sql)
            except Exception as e:
                print(f"[DB] 创建索引失败: {e}")
    
    def vacuum(self):
        """压缩数据库"""
        with self.get_connection() as conn:
            conn.execute('VACUUM')
    
    def get_stats(self):
        """获取数据库统计信息"""
        with self.get_connection() as conn:
            stats = {}
            
            # 表大小
            cursor = conn.execute("""
                SELECT name, 
                       page_count * page_size as size
                FROM sqlite_master 
                JOIN pragma_page_count() 
                JOIN pragma_page_size()
                WHERE type='table'
            """)
            for row in cursor:
                stats[row[0]] = row[1]
            
            return stats


class QueryCache:
    """查询缓存装饰器"""
    
    def __init__(self, max_size=1000, ttl=300):
        self.cache = {}
        self.max_size = max_size
        self.ttl = ttl
    
    def __call__(self, func):
        def wrapper(*args, **kwargs):
            # 生成缓存键
            key = f"{func.__name__}:{args}:{kwargs}"
            
            # 检查缓存
            if key in self.cache:
                cached_value, timestamp = self.cache[key]
                if time.time() - timestamp < self.ttl:
                    return cached_value
            
            # 执行查询
            result = func(*args, **kwargs)
            
            # 存储到缓存
            if len(self.cache) >= self.max_size:
                # 删除最旧的条目
                oldest_key = min(self.cache.keys(), 
                               key=lambda k: self.cache[k][1])
                del self.cache[oldest_key]
            
            self.cache[key] = (result, time.time())
            
            return result
        
        wrapper.cache = self.cache
        wrapper.clear_cache = lambda: self.cache.clear()
        
        return wrapper


# 全局查询缓存实例
query_cache = QueryCache(max_size=1000, ttl=300)


def optimize_database_performance(db_path):
    """一键优化数据库性能"""
    optimizer = DatabaseOptimizer(db_path)
    
    # 创建索引
    with optimizer.get_connection() as conn:
        optimizer.optimize_queries(conn)
    
    # 压缩数据库
    optimizer.vacuum()
    
    print("[DB] 数据库性能优化完成")
    
    return optimizer


if __name__ == "__main__":
    # 测试
    import os
    db_path = os.path.join(os.path.dirname(__file__), "data", "records.db")
    
    if os.path.exists(db_path):
        optimizer = optimize_database_performance(db_path)
        stats = optimizer.get_stats()
        print(f"数据库统计: {stats}")
    else:
        print(f"数据库不存在: {db_path}")
