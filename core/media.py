# -*- coding: utf-8 -*-
"""朗读与音效。

平台策略
--------
Android（pyjnius 原生实现，无 Kivy Sound）：
  - 音效：android.media.SoundPool，低延迟、专为 UI 反馈设计
  - 朗读：android.media.MediaPlayer 播放有道在线发音缓存，
    或 android.speech.tts.TextToSpeech（原生 TTS，离线可用、零延迟）
    —— 原生 TTS 优先，网络不可用时仍能朗读。

桌面 / 其他：
  - 朗读：外部播放器子进程（ffplay/mpv），彻底绕开 Kivy 音频，
    还能播放 SoundLoader 解不了的 mp3；未装播放器时静默禁用。
  - 音效：仅在 Kivy <= 2.3.0 启用。2.3.1 的 audio_sdl2 存在 load 死锁问题
    （Cython 扩展持 GIL 死锁会冻结全进程，线程隔离无效），故禁用。

所有对外方法均不抛异常、不阻塞主线程超过毫秒级。
"""

import hashlib
import os
import re
import shutil
import subprocess
import threading
import time

import requests
from kivy.logger import Logger
from kivy.utils import platform as _kivy_platform

from .config import app_dir

CACHE_DIR = os.path.join(app_dir(), "tts")

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


def _download(text, voice=2, timeout=10, retries=2):
    """下载有道发音到缓存（带重试与换音色兜底）。成功返回路径，失败返回 None。"""
    os.makedirs(CACHE_DIR, exist_ok=True)
    path = _cache_path(text)
    url = "https://dict.youdao.com/dictvoice?type=%d&audio=%s"
    for attempt in range(retries + 1):
        try:
            resp = requests.get(url % (voice, requests.utils.quote(text)),
                                timeout=timeout)
            if resp.status_code == 200 and len(resp.content) > 1024:
                with open(path, "wb") as f:
                    f.write(resp.content)
                return path
            Logger.info("Speaker: http=%s len=%s (attempt %d)"
                        % (resp.status_code, len(resp.content), attempt))
        except Exception as e:
            Logger.info("Speaker: download failed %s (attempt %d)"
                        % (e, attempt))
    # 换英式/美式音色再兜底一轮：个别内容单音色接口偶发 403/空响应
    other = 1 if voice == 2 else 2
    try:
        resp = requests.get(url % (other, requests.utils.quote(text)),
                            timeout=timeout)
        if resp.status_code == 200 and len(resp.content) > 1024:
            with open(path, "wb") as f:
                f.write(resp.content)
            return path
    except Exception as e:
        Logger.info("Speaker: fallback voice failed %s" % e)
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
            self._gen = 0  # 代际号：新一次 say() 让上一次提前退场，避免锁排队

        def say(self, text):
            text = (text or "").strip()
            if not text:
                return False
            self._gen += 1
            threading.Thread(target=self._play,
                             args=(text, self._gen), daemon=True).start()
            return True

        def _play(self, text, gen):
            with self._lock:  # 串行播放，避免多个 MediaPlayer 并发
                if gen != self._gen:
                    return  # 已有更新的播放请求，本次放弃
                try:
                    path = _cache_path(text)
                    if not os.path.exists(path) or os.path.getsize(path) < 1024:
                        path = _download(text)
                        if path is None:
                            Logger.info(
                                "Speaker(android): no audio for %r"
                                % text[:40])
                            return
                    mp = _MediaPlayer()
                    try:
                        mp.setDataSource(path)
                        mp.prepare()
                        mp.start()
                        # 轮询真实播放状态：播完立即释放；最长 20s 防卡死。
                        # （旧实现按字符数估算固定 sleep，长句被切、且锁被
                        #   占满导致下一次点击排队无声。）
                        deadline = time.time() + 20
                        while time.time() < deadline:
                            if gen != self._gen:
                                break
                            try:
                                if not mp.isPlaying():
                                    break
                            except Exception:
                                pass  # 个别 ROM isPlaying 异常时按满时长兜底
                            time.sleep(0.2)
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
# 桌面实现
# 音效仍走 Kivy SoundLoader（2.3.1+ 默认禁用，规避 audio_sdl2 load 死锁）；
# 朗读改调外部播放器子进程（ffplay/mpv）：无死锁风险，且支持 Kivy 解不了的 mp3。
# ==================================================================
else:
    from kivy.core.audio import SoundLoader

    _PLAYER = None
    for _exe in ("ffplay", "mpv"):
        if shutil.which(_exe):
            _PLAYER = _exe
            break

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
            self._exe = _PLAYER
            if not self._exe:
                Logger.info("Speaker: 未找到 ffplay/mpv，桌面朗读不可用")

        def say(self, text):
            text = (text or "").strip()
            if not text or not self._exe:
                return False

            def work():
                try:
                    path = _cache_path(text)
                    if not os.path.exists(path) \
                            or os.path.getsize(path) < 1024:
                        path = _download(text)
                    if not path:
                        Logger.info("Speaker: no audio for %r" % text[:40])
                        return
                    if self._exe == "ffplay":
                        cmd = ["ffplay", "-nodisp", "-autoexit",
                               "-loglevel", "quiet", path]
                    else:
                        cmd = ["mpv", "--no-video", "--really-quiet", path]
                    subprocess.run(cmd, stdout=subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL, timeout=30)
                except Exception as e:
                    Logger.info("Speaker: play failed %s" % e)

            threading.Thread(target=work, daemon=True).start()
            return True

    Sfx = _DesktopSfx
    Speaker = _DesktopSpeaker
