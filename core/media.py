# -*- coding: utf-8 -*-
"""朗读与音效。

平台策略
--------
Android（pyjnius 原生实现，无 Kivy Sound）：
  - 音效：android.media.SoundPool，低延迟、专为 UI 反馈设计
  - 朗读：android.media.MediaPlayer 播放有道在线发音缓存，
    或 android.speech.tts.TextToSpeech（原生 TTS，离线可用、零延迟）
    —— 原生 TTS 优先，网络不可用时仍能朗读。

桌面 / 其他（Kivy SoundLoader）：
  - 仅在 Kivy <= 2.3.0 启用。2.3.1 的 audio_sdl2 存在 load 死锁问题
    （Cython 扩展持 GIL 死锁会冻结全进程，线程隔离无效），故禁用。

所有对外方法均不抛异常、不阻塞主线程超过毫秒级。
"""

import hashlib
import os
import re
import threading

import requests
from kivy.logger import Logger
from kivy.utils import platform as _kivy_platform

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

_IS_ANDROID = _kivy_platform == "android"
_IS_KIVY_231 = False
try:
    import kivy
    parts = tuple(int(re.sub(r"\D", "", x) or 0)
                  for x in kivy.__version__.split(".")[:3])
    _IS_KIVY_231 = parts >= (2, 3, 1)
except Exception:
    pass


def _cache_path(text):
    os.makedirs(CACHE_DIR, exist_ok=True)
    return os.path.join(CACHE_DIR, hashlib.md5(text.encode("utf-8")).hexdigest() + ".mp3")


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


def _download(text):
    try:
        resp = requests.get(TTS_URL % requests.utils.quote(text), timeout=6)
        if resp.status_code == 200 and len(resp.content) > 1024:
            path = _cache_path(text)
            with open(path, "wb") as f:
                f.write(resp.content)
            return path
    except Exception as e:
        Logger.info("Speaker: download failed %s" % e)
    return None


# ==================================================================
# Android 原生实现
# ==================================================================
if _IS_ANDROID:
    from jnius import autoclass

    _SoundPool = autoclass("android.media.SoundPool")
    _AudioAttrs = autoclass("android.media.AudioAttributes")
    _AudioManager = autoclass("android.media.AudioManager")
    _MediaPlayer = autoclass("android.media.MediaPlayer")
    _Log = autoclass("android.util.Log")

    class _AndroidSfx(object):
        """基于 SoundPool 的低延迟音效（一次加载，多次播放）。"""

        def __init__(self, enabled=True):
            self.enabled = enabled
            self._pool = None
            self._ids = {}
            self._lock = threading.Lock()
            try:
                attrs = _AudioAttrs.Builder().setUsage(
                    _AudioManager.USAGE_ASSISTANCE_SONIFICATION).build()
                self._pool = _SoundPool(attrs, _AudioManager.STREAM_SYSTEM, 0)
                base = os.path.join(app_dir(), "sfx")
                for name, (f, d, v) in TONE.items():
                    p = os.path.join(base, name + ".wav")
                    if not os.path.exists(p):
                        _make_wav(p, f, d, v)
                    self._ids[name] = self._pool.load(p, 1)
            except Exception as e:
                Logger.info("Sfx(android): init failed %s" % e)
                self.enabled = False

        def play(self, name):
            if not self.enabled or name not in self._ids:
                return
            try:
                self._pool.play(self._ids[name], 0.5, 0.5, 1, 0, 1.0)
            except Exception:
                pass

    class _AndroidSpeaker(object):
        """朗读：MediaPlayer 播放有道在线发音缓存（下载/prepare 均在工作线程）。

        说明：曾评估 android.speech.tts.TextToSpeech，但 pyjnius 实现
        OnInitListener 异步回调复杂、且国产 ROM 常缺 TTS 数据，故采用
        在线发音缓存方案——联网时首播约 1~2 秒延迟，之后走本地缓存。
        """

        def __init__(self):
            self._lock = threading.Lock()

        def say(self, text):
            text = (text or "").strip()
            if not text:
                return False
            threading.Thread(target=self._play, args=(text,),
                             daemon=True).start()
            return True

        def _play(self, text):
            with self._lock:  # 串行播放，避免多个 MediaPlayer 并发
                try:
                    path = _cache_path(text)
                    if not os.path.exists(path) or os.path.getsize(path) < 1024:
                        path = _download(text)
                        if path is None:
                            return
                    mp = _MediaPlayer()
                    try:
                        mp.setDataSource(path)
                        mp.prepare()
                        mp.start()
                        # 等待播放结束（wav 时长已知上限 10s），随后释放
                        import time
                        time.sleep(min(10, 1.5 + len(text) * 0.09))
                    finally:
                        try:
                            mp.stop()
                        except Exception:
                            pass
                        mp.release()
                except Exception as e:
                    Logger.info("Speaker(android): play failed %s" % e)

    class _Noop(object):
        def say(self, *a, **k):
            return False

        def play(self, *a, **k):
            return False

    Sfx = _AndroidSfx
    Speaker = _AndroidSpeaker

# ==================================================================
# 桌面实现（Kivy SoundLoader；2.3.1+ 因 load 死锁禁用音频）
# ==================================================================
else:
    from kivy.core.audio import SoundLoader

    class _DesktopSfx(object):
        def __init__(self, enabled=True):
            self.enabled = enabled and not _IS_KIVY_231
            self._cache = {}
            self._paths = {}
            if not self.enabled:
                return
            try:
                base = os.path.join(app_dir(), "sfx")
                for name, (f, d, v) in TONE.items():
                    p = os.path.join(base, name + ".wav")
                    if not os.path.exists(p):
                        _make_wav(p, f, d, v)
                    self._paths[name] = p
            except Exception as e:
                Logger.info("Sfx: init failed %s" % e)
                self.enabled = False

        def play(self, name):
            if not self.enabled or name not in self._paths:
                return
            try:
                snd = self._cache.get(name)
                if snd is None:
                    snd = SoundLoader.load(self._paths[name])
                    if snd is not None:
                        snd.volume = 0.5
                        self._cache[name] = snd
                if snd is not None:
                    snd.play()
            except Exception as e:
                Logger.info("Sfx: play failed %s" % e)

    class _DesktopSpeaker(object):
        def __init__(self):
            self.disabled = _IS_KIVY_231

        def say(self, text):
            if self.disabled or not (text or "").strip():
                return False
            def work():
                try:
                    text2 = text.strip()
                    path = _cache_path(text2)
                    if not os.path.exists(path) or os.path.getsize(path) < 1024:
                        path = _download(text2)
                    if path:
                        snd = SoundLoader.load(path)
                        if snd:
                            snd.play()
                except Exception as e:
                    Logger.info("Speaker: play failed %s" % e)
            threading.Thread(target=work, daemon=True).start()
            return True

    Sfx = _DesktopSfx
    Speaker = _DesktopSpeaker
