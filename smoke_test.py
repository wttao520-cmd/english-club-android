#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""无头冒烟测试：构建界面、模拟一次完整输入、校验拼读与复习调度。

    python smoke_test.py
"""

import os
import sys
import tempfile

os.environ.setdefault("KIVY_NO_ARGS", "1")
os.environ.setdefault("KIVY_LOG_LEVEL", "error")
if not os.environ.get("DISPLAY"):
    # 无图形环境时用 SDL 虚拟驱动（CI / 服务器）
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("KIVY_WINDOW", "sdl2")
    os.environ.setdefault("KIVY_GL_BACKEND", "mock")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

DATA = tempfile.mkdtemp(prefix="club-smoke-")


def main():
    import faulthandler
    # 冒烟环境若在某个 UI 属性 setter 内阻塞，90 秒后打印全部线程堆栈并退出
    faulthandler.dump_traceback_later(90, exit=True)

    from core import db
    from core.config import set_base_dir

    set_base_dir(DATA)

    from main import EnglishClubApp

    app = EnglishClubApp()
    app.build()
    print("SMOKE OK  build  screens=%d" % len(app.sm.screen_names))

    # ---- 内置课程已写入
    courses = db.list_courses()
    assert courses, "内置课程未写入"
    ph = [c for c in courses if (c["builtin_key"] or "").startswith("ph_")]
    assert ph, "自然拼读课程未写入"
    print("SMOKE OK  courses=%d (phonics=%d)" % (len(courses), len(ph)))

    # ---- 练习页：整句输入 + 结算
    practice = app.screens("practice")
    practice.start([dict(r) for r in db.list_sentences(courses[0]["id"])[:3]], "冒烟")
    st = practice.session.state
    target = st.target
    # 说明：桌面/CI 的 TextInput.text setter 在部分环境下会阻塞（软键盘语义），
    # 这里直接同步引擎状态——与 Android 软键盘回调 _on_text 走的是同一条
    # core 层路径（TextInput→st.sync→render），引擎逻辑完全一致。
    st.sync(target)
    assert st.finished, "输入未完成：%r != %r" % (st.buffer, target)
    practice._render()
    practice._on_sentence_done()
    assert practice.session.total_score > 0, "未产生得分"
    print("SMOKE OK  typing  %r score=%d combo=%d"
          % (target[:40], practice.session.total_score, st.combo_max))

    # ---- 拼读模式：音块着色
    rows = [dict(r) for r in db.list_sentences(ph[0]["id"])[:3]]
    practice.start(rows, "拼读冒烟", "phonics")
    chunks = practice._current_chunks()
    assert chunks and "".join(chunks) == practice.session.state.target, "音块拆分不匹配"
    practice._render()
    print("SMOKE OK  phonics chunks=%s" % chunks)

    # ---- 复习调度：完成一句后应产生到期卡片
    conn = db.connect()
    n = conn.execute("SELECT COUNT(*) c FROM cards").fetchone()["c"]
    conn.close()
    assert n > 0, "未生成复习卡片"
    print("SMOKE OK  srs cards=%d due=%s" % (n, db.srs_counts()))

    print("SMOKE PASS")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback
        traceback.print_exc()
        sys.exit(1)
