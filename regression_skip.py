#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""回归测试：跳过路径（用户在桌面复现的 ZeroDivisionError）。

复现场景：整句未输入任何字符（started_at=None）直接点「跳过」，
旧代码在 engine.wpm 处抛 ZeroDivisionError: float division by zero。
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.config import set_base_dir
set_base_dir(tempfile.mkdtemp(prefix="club-regr-"))

from core import db
from core.engine import TypingState


def main():
    db.init_db()

    # 1) 纯引擎层：未输入直接结束（旧代码在此抛 ZeroDivisionError）
    st = TypingState("Hello world")
    st.buffer = st.target
    st.skipped = True
    st.finish()
    r = st.rating
    w = st.wpm
    s = st.score()
    assert r == 0, "跳过应计 Again, got %s" % r
    assert s == 0, "跳过应 0 分, got %s" % s
    print("REGR OK  skip-no-input  rating=%s wpm=%.1f score=%d" % (r, w, s))

    # 2) UI 层：完整走 practice._skip -> _on_sentence_done -> SRS 入库
    import faulthandler
    faulthandler.dump_traceback_later(60, exit=True)

    from main import EnglishClubApp
    app = EnglishClubApp()
    app.build()

    courses = db.list_courses()
    assert courses, "课程未写入"
    practice = app.screens("practice")
    practice.start([dict(x) for x in db.list_sentences(courses[0]["id"])[:2]],
                   "回归")
    assert practice.session.state.started_at is None, "前置：未输入"
    practice._skip()
    res = practice.session.results[-1]
    assert res["rating"] == 0, res
    card = db.get_or_create_card(practice.session.current["id"])
    assert card.due is not None
    print("REGR OK  skip-through-ui  rating=%s score=%d" % (res["rating"], res["score"]))

    # 3) 正常输入路径不受影响
    practice.start([dict(x) for x in db.list_sentences(courses[0]["id"])[:1]], "正常")
    st2 = practice.session.state
    st2.sync(st2.target)
    practice._on_sentence_done()
    res2 = practice.session.results[-1]
    assert res2["rating"] == 5 and res2["score"] > 0, res2
    print("REGR OK  normal-input    rating=%s score=%d" % (res2["rating"], res2["score"]))
    print("REGR PASS")


if __name__ == "__main__":
    main()
