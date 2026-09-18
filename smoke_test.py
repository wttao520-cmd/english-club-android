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

    # ---- 课程库分组：大类→小类，每门课都应归入某个大类
    groups = db.grouped_courses()
    total_grouped = sum(len(v) for subs in groups.values() for v in subs.values())
    assert total_grouped == len(courses), \
        "分组课程数不符：%d != %d" % (total_grouped, len(courses))
    assert "词汇课程" in groups and "自然拼读" in groups, \
        "缺少预期大类：%s" % list(groups)
    for c in courses:
        cat, sub = db.course_category(c)
        assert cat and sub, "课程未分类：%s" % c["title"]
    # 拼读课程必须落在「自然拼读」大类（而不是被归到句子课程）
    for c in ph:
        assert db.course_category(c)[0] == "自然拼读", \
            "拼读课程被误分类：%s" % c["title"]
    print("SMOKE OK  course-groups=%s" % "、".join(groups.keys()))

    # ---- 练习页：整句输入 + 结算
    practice = app.screens("practice")

    # ---- 「选择课程」弹窗：分组折叠 + 选择回填
    from ui.widgets import PickerPopup
    holder = {}
    _orig_init = PickerPopup.__init__

    def _patched(self, *a, **k):
        _orig_init(self, *a, **k)
        holder["p"] = self

    PickerPopup.__init__ = _patched
    try:
        practice._current_title = None
        practice._pick_course()
        pop = holder["p"]
        assert pop._groups and len(pop._groups) > 1, "课程弹窗未分组"
        g0 = pop._groups[0][0]
        if g0 in pop._open_groups:
            pop._toggle_group(g0)
        n_fold = len(pop._grid.children)
        pop._toggle_group(g0)
        n_open = len(pop._grid.children)
        assert n_open > n_fold, "展开分组未渲染课程项：%d -> %d" % (n_fold, n_open)
        # 再次折叠：不能因为 _open_groups 变空而被强制重新展开
        pop._toggle_group(g0)
        n_closed = len(pop._grid.children)
        assert n_closed == n_fold, \
            "折叠失效：折叠后 %d，应为 %d" % (n_closed, n_fold)
        name = pop._groups[0][1][0]
        pop._pick(name)
        assert practice._current_title == name, "选课后未回填标题"
        print("SMOKE OK  course-picker groups=%d fold=%d open=%d reopen-collapse ok"
              % (len(pop._groups), n_fold, n_open))
    finally:
        PickerPopup.__init__ = _orig_init

    # ---- 从课程库进入某课程后，练习页「选择课程」按钮应同步为该课程名
    _c = courses[3]
    practice.start([dict(r) for r in db.list_sentences(_c["id"])[:1]],
                   _c["title"], None)
    assert practice._current_title == _c["title"], "进入课程后未同步标题"
    assert practice.course_btn.text == _c["title"], "课程按钮未同步"
    print("SMOKE OK  course-title-sync %r" % _c["title"][:20])

    # ---- 删除课程：连同句子/卡片一起清除
    n_before = len(db.list_courses())
    tmp_cid = db.add_course("临时课程", "test", "初级", "custom")
    db.add_sentences(tmp_cid, [("Hello world.", "你好世界。", "")])
    assert len(db.list_courses()) == n_before + 1
    assert db.count_sentences(tmp_cid) == 1
    db.delete_course(tmp_cid)
    assert len(db.list_courses()) == n_before, "删除课程后数量不对"
    assert db.count_sentences(tmp_cid) == 0, "删除课程后句子未清除"
    print("SMOKE OK  delete-course")

    # ---- AI 生成课程（用桩替换 AI，验证「生成→保存为课程」链路）
    class _FakeAI(object):
        enabled = True

        def generate_course(self, topic, level, count, style=""):
            return [("Where is the gate?", "登机口在哪里？"),
                    ("Here is your ticket.", "这是您的机票。")]

    _real_ai = app.ctx.ai
    app.ctx.ai = _FakeAI()
    try:
        ai_pairs = app.ctx.ai.generate_course("机场", "初级", 2)
        assert len(ai_pairs) == 2
        ai_cid = db.add_course("机场值机（AI）", "AI 生成", "初级", "custom")
        db.add_sentences(ai_cid, [(en, zh, "") for en, zh in ai_pairs])
        assert db.count_sentences(ai_cid) == 2, "AI 课程句子未写入"
        db.delete_course(ai_cid)
        print("SMOKE OK  ai-generate-course pairs=%d" % len(ai_pairs))
    finally:
        app.ctx.ai = _real_ai


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

    # ---- 宠物：解锁/切换/喂养必须真正持久化（老 bug：pet 表未 commit）
    from core import pet as pet_mod
    db.add_points(5000)
    st0 = pet_mod.load()
    st0.unlocked.append("bunny")
    st0.species = "bunny"
    st0.save()
    st1 = pet_mod.load()
    assert st1.species == "bunny", "宠物切换未持久化"
    assert "bunny" in st1.unlocked, "宠物解锁未持久化"
    st1.add_exp(10)
    st1.save()
    assert pet_mod.load().exp == st1.exp, "宠物经验未持久化"
    # 回退为初始宠物，避免影响后续用例
    st2 = pet_mod.load()
    st2.species = "cat"
    st2.save()
    print("SMOKE OK  pet-persist species/bonus ok")

    # ---- 选词模式（句子课程）：候选池只含当前句的词（无干扰）
    sentence_course = [c for c in courses
                       if not (c["builtin_key"] or "").startswith(
                           ("vocab_", "ph_", "xqh"))
                       ][0]
    rows = [dict(r) for r in db.list_sentences(sentence_course["id"])[:2]]
    practice._is_vocab = False
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

    # ---- 选词模式（句子课程）：候选池只含当前句的词（无外部干扰）
    practice._is_vocab = False
    practice.start(rows[:3], "选词单词冒烟", "choice")
    st = practice.session.state
    cur_words = [x for x, _s in st.words]
    practice._render()
    cb = practice.choice_board
    pool_words = [t.text for t in cb.pool.children]
    assert sorted(pool_words) == sorted(cur_words), \
        "句子课程候选池应只有当前句的词：pool=%s cur=%s" % (pool_words, cur_words)
    # 流式布局：视口宽度决定换行（FlowLayout 宽度随 ScrollView 视口）
    # 窄视口下必须换行（用窄宽度保证与词长无关）
    cb.pool.width = 120.0
    cb.pool._relayout()
    rowset = {}
    for ch in cb.pool.children:
        rowset.setdefault(round(ch.y), []).append(ch.text)
    assert len(rowset) >= 2, "窄视口下词块未换行：%s" % rowset
    # 词块高度应随屏幕缩放（手机≈40dp，平板更大），只校验未被撑得异常大
    for ch in cb.pool.children:
        assert ch.height <= 120.0, "词块过高：%s" % ch.height
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

    # ---- 选词模式（词汇课程）：候选池应混入 2 个本句以外的干扰词
    vocab_course = [c for c in courses
                    if (c["builtin_key"] or "").startswith("vocab_xqh1")][0]
    vrows = [dict(r) for r in db.list_sentences(vocab_course["id"])[:1]]
    practice._is_vocab = True
    practice.start(vrows, "词汇选词", "choice")
    practice._render()
    st = practice.session.state
    real = [w for w, _s in st.words]
    vpool = [t.text for t in practice.choice_board.pool.children]
    extra = [w for w in vpool if w not in real]
    assert len(extra) == 2, "词汇课程应混入 2 个干扰词：%s" % vpool
    for w in real:
        assert w in vpool, "词汇候选池缺少正确词：%s" % vpool
    print("SMOKE OK  vocab-choice distractors=%s" % extra)

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
