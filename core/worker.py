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
            # 注意：except 块结束后 `e` 会被删除（Python 语义），
            # 而回调是延迟在主线程执行的，故必须先把异常信息取出为普通变量。
            msg = "%s: %s" % (type(e).__name__, e)
            err_cb = on_error
            if err_cb:
                Clock.schedule_once(lambda dt, m=msg: err_cb(m), 0)
            return
        ok_cb = on_ok
        if ok_cb:
            Clock.schedule_once(lambda dt, r=result: ok_cb(r), 0)

    threading.Thread(target=target, daemon=True).start()
