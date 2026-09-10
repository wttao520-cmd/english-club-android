# -*- coding: utf-8 -*-
"""后台线程执行 AI 请求，结果通过回调回到 UI 线程。"""

import threading

from kivy.clock import Clock


def run_async(func, on_ok=None, on_error=None, *args, **kwargs):
    """在工作线程执行 func，成功/失败回调均在主线程触发。"""

    def target():
        try:
            result = func(*args, **kwargs)
        except Exception as e:
            if on_error:
                Clock.schedule_once(lambda dt: on_error(str(e)), 0)
            return
        if on_ok:
            Clock.schedule_once(lambda dt: on_ok(result), 0)

    threading.Thread(target=target, daemon=True).start()
