#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
缓存管理模块
提供统一的缓存接口，支持内存缓存和Redis缓存
"""
import time
import json
import hashlib
from typing import Any, Optional
from functools import lru_cache


class MemoryCache:
    """内存缓存实现"""
    
    def __init__(self, max_size: int = 1000, ttl: int = 3600):
        """
        初始化缓存
        :param max_size: 最大缓存条目数
        :param ttl: 默认过期时间（秒）
        """
        self._cache = {}
        self._max_size = max_size
        self._ttl = ttl
    
    def get(self, key: str) -> Optional[Any]:
        """获取缓存值"""
        if key not in self._cache:
            return None
        
        value, expire_time = self._cache[key]
        
        # 检查是否过期
        if expire_time and time.time() > expire_time:
            del self._cache[key]
            return None
        
        return value
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None):
        """设置缓存值"""
        # 如果缓存已满，删除最旧的条目
        if len(self._cache) >= self._max_size:
            self._evict_oldest()
        
        expire_time = time.time() + (ttl or self._ttl) if ttl != 0 else None
        self._cache[key] = (value, expire_time)
    
    def delete(self, key: str):
        """删除缓存"""
        if key in self._cache:
            del self._cache[key]
    
    def clear(self):
        """清空缓存"""
        self._cache.clear()
    
    def _evict_oldest(self):
        """淘汰最旧的条目"""
        if not self._cache:
            return
        
        # 找到最早过期的条目
        oldest_key = min(self._cache.keys(), 
                        key=lambda k: self._cache[k][1] or float('inf'))
        del self._cache[olddest_key]
    
    def stats(self) -> dict:
        """获取缓存统计信息"""
        return {
            "size": len(self._cache),
            "max_size": self._max_size,
            "ttl": self._ttl,
        }


class RedisCache:
    """Redis缓存实现"""
    
    def __init__(self, host: str = 'localhost', port: int = 6379, db: int = 0):
        """初始化Redis缓存"""
        try:
            from redis import Redis
            self._client = Redis(host=host, port=port, db=db, decode_responses=True)
            self._available = True
        except ImportError:
            print("[Cache] Redis未安装，使用内存缓存")
            self._client = None
            self._available = False
            self._fallback = MemoryCache()
    
    def get(self, key: str) -> Optional[Any]:
        """获取缓存值"""
        if not self._available:
            return self._fallback.get(key)
        
        value = self._client.get(key)
        if value is None:
            return None
        
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    
    def set(self, key: str, value: Any, ttl: int = 3600):
        """设置缓存值"""
        if not self._available:
            return self._fallback.set(key, value, ttl)
        
        serialized = json.dumps(value, ensure_ascii=False)
        if ttl > 0:
            self._client.setex(key, ttl, serialized)
        else:
            self._client.set(key, serialized)
    
    def delete(self, key: str):
        """删除缓存"""
        if not self._available:
            return self._fallback.delete(key)
        
        self._client.delete(key)
    
    def clear(self):
        """清空缓存"""
        if not self._available:
            return self._fallback.clear()
        
        self._client.flushdb()
    
    def stats(self) -> dict:
        """获取缓存统计信息"""
        if not self._available:
            return self._fallback.stats()
        
        info = self._client.info()
        return {
            "size": info.get("db0", {}).get("keys", 0),
            "memory_used": info.get("used_memory_human", "0B"),
            "connected_clients": info.get("connected_clients", 0),
        }


# 全局缓存实例
_cache_instance = None


def get_cache(use_redis: bool = False) -> MemoryCache:
    """获取缓存实例"""
    global _cache_instance
    
    if _cache_instance is None:
        if use_redis:
            _cache_instance = RedisCache()
        else:
            _cache_instance = MemoryCache()
    
    return _cache_instance


def cache_key(*args, **kwargs) -> str:
    """生成缓存键"""
    key_parts = [str(arg) for arg in args]
    key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
    key_str = "|".join(key_parts)
    return hashlib.md5(key_str.encode()).hexdigest()


def cached(ttl: int = 3600):
    """缓存装饰器"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            cache = get_cache()
            key = f"{func.__module__}.{func.__name__}:{cache_key(*args, **kwargs)}"
            
            # 尝试从缓存获取
            cached_value = cache.get(key)
            if cached_value is not None:
                return cached_value
            
            # 执行函数
            result = func(*args, **kwargs)
            
            # 存入缓存
            cache.set(key, result, ttl)
            
            return result
        return wrapper
    return decorator


if __name__ == "__main__":
    # 测试缓存
    cache = MemoryCache(max_size=10, ttl=5)
    
    # 设置缓存
    cache.set("key1", "value1")
    cache.set("key2", {"data": "test"}, ttl=10)
    
    # 获取缓存
    print("key1:", cache.get("key1"))
    print("key2:", cache.get("key2"))
    
    # 统计信息
    print("Stats:", cache.stats())
    
    # 等待过期
    time.sleep(6)
    print("key1 after expire:", cache.get("key1"))
    print("key2 after expire:", cache.get("key2"))
