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
    practice.start([dict(r) for r in db.list_sentences(courses[0]["id"])[:3]],
                   "冒烟", "sentence")
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

    # ---- 单词模式：打完单词自动补空格（不手动敲空格）
    multi = [dict(r) for r in db.list_sentences(courses[0]["id"])
             if " " in r["en"]][:1]
    assert multi, "找不到多词句子用于测试单词模式"
    practice.start(multi, "单词冒烟", "word")
    st = practice.session.state
    assert st.auto_space, "单词模式未开启自动空格"
    tgt = st.target
    # 只输入「非空格字符」，空格应被自动补齐
    for ch in tgt.replace(" ", ""):
        st.type_char(ch)
    assert st.buffer == tgt, "自动补空格结果不符：%r != %r" % (st.buffer, tgt)
    assert st.finished, "单词模式未完成"
    assert st.errors == 0, "自动补空格不应产生错误：errors=%d" % st.errors
    print("SMOKE OK  word auto-space  %r" % tgt[:40])

    # ---- 拼读模式：音块着色
    rows = [dict(r) for r in db.list_sentences(ph[0]["id"])[:3]]
    practice.start(rows, "拼读冒烟", "phonics")
    chunks = practice._current_chunks()
    assert chunks and "".join(chunks) == practice.session.state.target, "音块拆分不匹配"
    practice._render()
    print("SMOKE OK  phonics chunks=%s" % chunks)

    # ---- 选词模式（句子）：点词按顺序填入即完成
    rows = [dict(r) for r in db.list_sentences(courses[0]["id"])[:2]]
    practice.start(rows, "选词冒烟", "choice")
    st = practice.session.state
    from core.engine import split_words
    words = [w for w, _s in split_words(st.target)]
    for w in words:
        assert st.pick_word(w), "选词失败：%r" % w
    assert st.finished, "选词后未完成：%r != %r" % (st.buffer, st.target)
    practice._render()
    practice._on_sentence_done()
    assert practice.session.total_score > 0, "选词模式未产生得分"
    print("SMOKE OK  choice words=%d" % len(words))

    # ---- 选词模式：候选池只含当前句的词（无外部干扰）
    practice.start(rows[:3], "选词单词冒烟", "choice")
    st = practice.session.state
    cur_words = [x for x, _s in st.words]
    practice._render()
    cb = practice.choice_board
    pool_words = [t.text for t in cb.pool.children]
    assert sorted(pool_words) == sorted(cur_words), \
        "候选池应只有当前句的词：pool=%s cur=%s" % (pool_words, cur_words)
    # 流式布局：视口宽度决定换行（FlowLayout 宽度随 ScrollView 视口）
    # 窄视口下必须换行（用窄宽度保证与词长无关）
    cb.pool.width = 120.0
    cb.pool._relayout()
    rowset = {}
    for ch in cb.pool.children:
        rowset.setdefault(round(ch.y), []).append(ch.text)
    assert len(rowset) >= 2, "窄视口下词块未换行：%s" % rowset
    for ch in cb.pool.children:
        assert ch.height <= 40.0, "词块过高：%s" % ch.height
    # 恢复常见手机宽度再排一次，供后续位置稳定性断言
    cb.pool.width = 380.0
    cb.pool._relayout()

    # 选中一个词后：该词块隐藏，其余词块顺序（位置）不变
    before = [(t.text, round(t.x), round(t.y)) for t in cb.pool.children]
    first = cur_words[0]
    assert st.pick_word(first), "选词失败：%r" % first
    practice._render()
    after = [(t.text, round(t.x), round(t.y)) for t in cb.pool.children]
    assert [x[0] for x in after] == [x[0] for x in before], "词库顺序变了"
    # 被选中的那个词块被隐藏（透明且不可点，但保留占位）
    sel = [t for t in cb.pool.children if t.text == first][0]
    assert sel.opacity == 0 and sel.disabled, "选中的词块未隐藏"
    # 其余词块的坐标保持不变（不跳变）
    moved = [(a, b) for a, b in zip(before, after)
             if a[0] != first and (a[1] != b[1] or a[2] != b[2])]
    assert not moved, "选中后其它词块位置跳变：%s" % moved
    for w in cur_words[1:]:
        assert st.pick_word(w), "选词失败：%r" % w
    assert st.finished
    practice._render()
    practice._on_sentence_done()

    # ---- 跳过：应刷新到下一句（词库随之更新）
    before = practice.session.state.target
    practice._skip()
    after = practice.session.state.target
    assert after != before, "跳过后未进入下一句"
    new_pool = [t.text for t in practice.choice_board.pool.children]
    assert new_pool, "跳过后词库未刷新"
    print("SMOKE OK  choice rows=%d stable-order ok skip-refresh ok" % len(rowset))

    # ---- 选词模式：选错不结算，仍可继续
    practice.start(rows[1:2], "选词纠错", "choice")
    st = practice.session.state
    st.pick_word("__wrong__")
    assert not st.finished and st.errors == 1, "选错应记错误且未完成"
    print("SMOKE OK  choice wrong-guard")

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
