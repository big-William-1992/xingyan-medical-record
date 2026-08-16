#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
国际化（i18n）框架
支持中文/英文，可扩展其他语言
用法：
    from i18n import get_text, set_language
    set_language('en')
    print(get_text('app.title'))
"""
import json
import os

# 语言包目录
LOCALES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "locales")

# 当前语言
_current_language = "zh_CN"

# 语言包缓存
_lang_cache = {}


def _load_language(lang):
    """加载语言包"""
    if lang in _lang_cache:
        return _lang_cache[lang]

    path = os.path.join(LOCALES_DIR, f"{lang}.json")
    if not os.path.exists(path):
        # 回退到中文
        path = os.path.join(LOCALES_DIR, "zh_CN.json")
        if not os.path.exists(path):
            return {}

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        _lang_cache[lang] = data
        return data
    except Exception:
        return {}


def set_language(lang):
    """设置当前语言（如 'zh_CN', 'en_US'）"""
    global _current_language
    _current_language = lang
    # 预加载语言包
    _load_language(lang)


def get_language():
    """获取当前语言"""
    return _current_language


def get_text(key, **kwargs):
    """
    获取翻译文本
    支持点号路径：get_text('app.title')
    支持格式化：get_text('record.saved', count=3)
    """
    data = _load_language(_current_language)

    # 按点号逐级查找
    parts = key.split(".")
    value = data
    for part in parts:
        if isinstance(value, dict) and part in value:
            value = value[part]
        else:
            # 回退到中文
            zh_data = _load_language("zh_CN")
            value = zh_data
            for p in parts:
                if isinstance(value, dict) and p in value:
                    value = value[p]
                else:
                    return key
            break

    if isinstance(value, str) and kwargs:
        try:
            return value.format(**kwargs)
        except (KeyError, IndexError):
            return value

    return value if isinstance(value, str) else key


# 便捷别名
t = get_text
i18n = get_text


def get_available_languages():
    """获取可用语言列表"""
    languages = []
    if os.path.exists(LOCALES_DIR):
        for f in sorted(os.listdir(LOCALES_DIR)):
            if f.endswith(".json"):
                languages.append(f[:-5])
    return languages


# ─── 前端语言包导出 ───
def export_frontend_language(lang):
    """导出语言包为 JS（供前端使用）"""
    data = _load_language(lang)
    import json as _json
    return "window.I18N=" + _json.dumps(data, ensure_ascii=False)


if __name__ == "__main__":
    print("可用语言:", get_available_languages())
    print("当前语言:", get_language())
    print("标题:", get_text("app.title"))
