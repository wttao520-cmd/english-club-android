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
    practice.input.text = target          # 模拟软键盘一次性给出整段文本
    assert st.finished, "输入未完成：%r != %r" % (st.buffer, target)
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
