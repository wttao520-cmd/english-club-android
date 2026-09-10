# -*- coding: utf-8 -*-
"""朗读与音效：基于 Kivy SoundLoader，桌面与安卓通用。

在线发音（有道）在后台线程下载并缓存到本地，首次播放有短暂延迟；
离线时自动降级为静默，不影响练习。
"""

import hashlib
import os
import threading

import requests
from kivy.core.audio import SoundLoader
from kivy.logger import Logger

from .config import app_dir

CACHE_DIR = os.path.join(app_dir(), "tts")
TTS_URL = "https://dict.youdao.com/dictvoice?type=2&audio=%s"

TONE = {
    "key": (760.0, 0.035, 0.22),
    "bad": (180.0, 0.12, 0.30),
    "good": (980.0, 0.09, 0.26),
    "perfect": (1320.0, 0.18, 0.30),
    "combo": (1180.0, 0.10, 0.26),
}
RATE = 22050


def _cache_path(text):
    os.makedirs(CACHE_DIR, exist_ok=True)
    return os.path.join(CACHE_DIR, hashlib.md5(text.encode("utf-8")).hexdigest() + ".mp3")


def _ensure_dir():
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
    except Exception:
        pass


def _make_wav(path, freq, dur, vol):
    """程序生成 wav 音效，避免打包外部资源。"""
    import math
    import struct
    import wave

    os.makedirs(os.path.dirname(path), exist_ok=True)
    frames = int(RATE * dur)
    data = bytearray()
    for i in range(frames):
        t = float(i) / RATE
        env = min(1.0, t / 0.005) * max(0.0, 1.0 - t / dur)
        v = vol * env * math.sin(2 * math.pi * freq * t)
        v += 0.25 * vol * env * math.sin(4 * math.pi * freq * t)
        data += struct.pack("<h", int(max(-1.0, min(1.0, v)) * 32767))
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(bytes(data))


class Speaker(object):
    """句子/单词朗读。"""

    def say(self, text):
        text = (text or "").strip()
        if not text:
            return False
        try:
            _ensure_dir()
            path = _cache_path(text)
            if os.path.exists(path) and os.path.getsize(path) >= 1024:
                self._play(path)
                return True
        except Exception:
            return False
        t = threading.Thread(target=self._download, args=(text, path), daemon=True)
        t.start()
        return True

    def _download(self, text, path):
        try:
            resp = requests.get(TTS_URL % requests.utils.quote(text), timeout=6)
            if resp.status_code == 200 and len(resp.content) > 1024:
                with open(path, "wb") as f:
                    f.write(resp.content)
                self._play(path)
        except Exception as e:
            Logger.info("Speaker: download failed %s" % e)

    @staticmethod
    def _play(path):
        try:
            snd = SoundLoader.load(path)
            if snd:
                snd.play()
        except Exception:
            pass


class Sfx(object):
    """按键音效。"""

    def __init__(self, enabled=True):
        self.enabled = enabled
        self._paths = {}
        try:
            base = os.path.join(app_dir(), "sfx")
            for name, (f, d, v) in TONE.items():
                p = os.path.join(base, name + ".wav")
                if not os.path.exists(p):
                    _make_wav(p, f, d, v)
                self._paths[name] = p
        except Exception as e:
            Logger.info("Sfx: init failed %s" % e)

    def play(self, name):
        if not self.enabled or name not in self._paths:
            return
        try:
            snd = SoundLoader.load(self._paths[name])
            if snd:
                snd.volume = 0.5
                snd.play()
        except Exception:
            pass
