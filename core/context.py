# -*- coding: utf-8 -*-
"""全局上下文：配置、AI、朗读、音效。"""

from .ai_client import AIClient
from .config import Config
from .media import Sfx, Speaker


class _Null(object):
    def say(self, *a, **k):
        return False

    def play(self, *a, **k):
        return False


class AppContext(object):
    def __init__(self, base_dir=None):
        self.config = Config(base_dir)
        self.ai = AIClient(self.config)
        try:
            self.speaker = Speaker()
        except Exception:
            self.speaker = _Null()
        try:
            self.sfx = Sfx(self.config.get("sound_enabled", True))
        except Exception:
            self.sfx = _Null()

    def reload_ai(self):
        self.ai = AIClient(self.config)
        if hasattr(self.sfx, "enabled"):
            self.sfx.enabled = self.config.get("sound_enabled", True)
