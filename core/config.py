"""应用配置：保存在用户目录下的 config.json。"""

import json
import os

APP_NAME = "english_club"

DEFAULT_CONFIG = {
    # ---- AI（OpenAI 兼容接口，支持 DeepSeek / OpenAI / 通义 / 月之暗面 等）----
    "ai_enabled": False,
    "ai_base_url": "https://api.deepseek.com/v1",
    "ai_api_key": "",
    "ai_model": "deepseek-chat",
    # ---- 练习 ----
    "mode": "sentence",        # word | sentence | dictation
    "lesson_size": 10,         # 每关句子数
    "auto_next": True,         # 完成后自动进入下一句
    "sound_enabled": True,     # 输入音效
    "tts_enabled": True,       # 自动/手动朗读
    "auto_tts": False,         # 进入句子时自动朗读
    "daily_goal_minutes": 15,
}


_BASE_DIR = None


def set_base_dir(path):
    """安卓上指向 App.user_data_dir；必须在 Config 实例化之前调用。"""
    global _BASE_DIR
    _BASE_DIR = path


def app_dir():
    global _BASE_DIR
    if _BASE_DIR is None:
        # Android（p4a）：bootstrap 设置 ANDROID_APP_PATH=/data/user/0/<pkg>/files。
        # 不能指望调用方先 set_base_dir——main.py 顶层 import core.db 时就会
        # 调用本函数（DB_PATH = app_dir()/app.db），此时 build() 还没执行；
        # 而 Android 上 HOME=/，桌面分支会去创建 /data/.english_club 直接崩。
        env = os.environ.get("ANDROID_APP_PATH")
        if env:
            _BASE_DIR = env
        else:
            _BASE_DIR = os.path.join(os.path.expanduser("~"),
                                     "." + APP_NAME)
    os.makedirs(_BASE_DIR, exist_ok=True)
    return _BASE_DIR


class Config(object):
    def __init__(self, base_dir=None):
        if base_dir:
            set_base_dir(base_dir)
        self._path = os.path.join(app_dir(), "config.json")
        self._data = dict(DEFAULT_CONFIG)
        self.load()

    def load(self):
        if os.path.exists(self._path):
            try:
                with open(self._path, "r", encoding="utf-8") as f:
                    self._data.update(json.load(f))
            except Exception:
                pass
        return self._data

    def save(self):
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)

    def get(self, key, default=None):
        return self._data.get(key, DEFAULT_CONFIG.get(key, default))

    def set(self, key, value):
        self._data[key] = value
        self.save()

    def update(self, mapping):
        self._data.update(mapping)
        self.save()

    @property
    def path(self):
        return self._path
