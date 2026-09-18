# -*- coding: utf-8 -*-
"""接口全量测试：逐个调用 core/db.py 的全部公开接口（含边界与异常）。

用法： python api_test.py
"""
import os
import sys
import tempfile
import traceback

os.environ.setdefault("KIVY_NO_ARGS", "1")
os.environ.setdefault("KIVY_LOG_LEVEL", "error")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.config import set_base_dir
set_base_dir(tempfile.mkdtemp())

from core import db, pet as pet_mod, srs, engine  # noqa: E402

PASS = []
FAIL = []


def case(name):
    """装饰器：跑一个用例并记录结果。"""
    def deco(fn):
        try:
            fn()
            PASS.append(name)
            print("PASS  %s" % name)
        except Exception as e:
            FAIL.append((name, e))
            print("FAIL  %s  -> %s: %s" % (name, type(e).__name__, e))
            traceback.print_exc()
        return fn
    return deco


# ---------------------------------------------------------------- 初始化
@case("init_db / connect")
def _():
    db.init_db()
    conn = db.connect()
    assert conn is not None
    conn.close()


# ---------------------------------------------------------------- 课程
@case("add_course / get_course / list_courses")
def _():
    cid = db.add_course("接口测试课", "desc", "初级", "custom")
    assert cid > 0
    c = db.get_course(cid)
    assert c["title"] == "接口测试课"
    assert any(x["id"] == cid for x in db.list_courses())
    # 空标题也能建（不崩）
    cid2 = db.add_course("", "", "初级", "custom")
    assert cid2 > 0
    db.delete_course(cid2)


@case("get_course_by_key / builtin_key 唯一")
def _():
    cid = db.add_course("KEY 课", "d", "初级", "builtin", "test_key_xyz")
    c = db.get_course_by_key("test_key_xyz")
    assert c and c["id"] == cid
    assert db.get_course_by_key("no_such_key_!!!") is None
    db.delete_course(cid)


@case("course_category / grouped_courses")
def _():
    cat, sub = db.course_category({"builtin_key": "vocab_xqh1a_u1", "source": "builtin"})
    assert cat == "词汇课程" and "新启航" in sub
    cat, sub = db.course_category({"builtin_key": "", "source": "custom"})
    assert cat == "自定义导入"
    g = db.grouped_courses()
    assert isinstance(g, dict) and g
    total = sum(len(v) for subs in g.values() for v in subs.values())
    assert total == len(db.list_courses())


@case("delete_course 级联清除句子/卡片")
def _():
    cid = db.add_course("待删", "", "初级", "custom")
    db.add_sentences(cid, [("A b c.", "甲乙丙。", "")])
    assert db.count_sentences(cid) == 1
    db.delete_course(cid)
    assert db.get_course(cid) is None
    assert db.count_sentences(cid) == 0
    # 删除不存在的课程不应报错
    db.delete_course(999999)


# ---------------------------------------------------------------- 句子
@case("add_sentences / list_sentences / count_sentences / get_sentence")
def _():
    cid = db.add_course("句子课", "", "初级", "custom")
    db.add_sentences(cid, [("Hello world.", "你好世界。", "n"), ("How are you?", "你好吗？", "")])
    rows = db.list_sentences(cid)
    assert len(rows) == 2
    assert db.count_sentences(cid) == 2
    s = db.get_sentence(rows[0]["id"])
    assert s["en"] == "Hello world."
    assert db.get_sentence(999999) is None
    # 追加句子 seq 应接续
    db.add_sentences(cid, [("Third one.", "第三句。", "")])
    assert db.count_sentences(cid) == 3
    db.delete_course(cid)


@case("add_sentences 空列表")
def _():
    cid = db.add_course("空句课", "", "初级", "custom")
    db.add_sentences(cid, [])
    assert db.count_sentences(cid) == 0
    db.delete_course(cid)


@case("sentences_by_en / search_sentences")
def _():
    hits = db.sentences_by_en(["Hello world.", "不存在句!!!"])
    assert isinstance(hits, list)
    res = db.search_sentences("Hello", limit=10)
    assert isinstance(res, list)
    # 空关键词
    db.search_sentences("", limit=5)
    # 特殊字符不应导致 SQL 错误
    db.search_sentences("%'\"\\", limit=5)


@case("sentences_range（按 seq 闭区间）")
def _():
    cid = db.add_course("范围课", "", "初级", "custom")
    db.add_sentences(cid, [("S%d here." % i, "第%d句。" % i, "") for i in range(1, 6)])
    rows = db.list_sentences(cid)
    seqs = [r["seq"] for r in rows]
    lo, hi = seqs[0], seqs[2]
    got = db.sentences_range(cid, lo, hi)
    assert len(got) == 3, "seq %s..%s 取到 %d 条" % (lo, hi, len(got))
    assert all(lo <= r["seq"] <= hi for r in got)
    # 越界区间返回空
    assert len(db.sentences_range(cid, 10 ** 6, 10 ** 6 + 5)) == 0
    db.delete_course(cid)


# ---------------------------------------------------------------- SRS
@case("get_or_create_card / get_card / save_card")
def _():
    cid = db.add_course("卡片课", "", "初级", "custom")
    db.add_sentences(cid, [("Card test.", "卡片测试。", "")])
    sid = db.list_sentences(cid)[0]["id"]
    card = db.get_or_create_card(sid)
    assert card is not None
    # 幂等
    card2 = db.get_or_create_card(sid)
    assert card2.id == card.id and card2.sentence_id == sid
    got = db.get_card(sid)
    assert got is not None
    got.interval = 5.0
    db.save_card(got)
    assert db.get_card(sid).interval == 5.0
    db.delete_course(cid)


@case("due_course_cards / new_course_sentences / due_count")
def _():
    cid = db.add_course("到期课", "", "初级", "custom")
    db.add_sentences(cid, [("Due %d." % i, "到期%d。" % i, "") for i in range(4)])
    assert isinstance(db.due_course_cards(cid, limit=10), list)
    assert isinstance(db.new_course_sentences(cid, limit=10), list)
    assert db.due_count(cid) >= 0


@case("all_due_sentences / srs_counts")
def _():
    assert isinstance(db.all_due_sentences(limit=20), list)
    cnt = db.srs_counts()
    assert "total" in cnt and "due" in cnt


@case("add_review / bump_daily / get_daily / recent_daily / overall_stats")
def _():
    cid = db.add_course("统计课", "", "初级", "custom")
    db.add_sentences(cid, [("Stat one.", "统计一。", "")])
    sid = db.list_sentences(cid)[0]["id"]
    db.add_review(sid, 5, 40.0, 98.0, 10, 12, 3000)
    db.bump_daily(seconds=10, sentences=1, chars=12, errors=0, combo_max=10, score=100)
    d = db.get_daily()
    assert d is not None
    assert isinstance(db.recent_daily(days=7), list)
    st = db.overall_stats()
    assert isinstance(st, dict)
    db.delete_course(cid)


# ---------------------------------------------------------------- 缓存 / 档案
@case("cache_get / cache_put")
def _():
    db.cache_put("k1", "v1")
    assert db.cache_get("k1") == "v1"
    assert db.cache_get("__no_such__") is None
    db.cache_put("k1", "v2")   # 覆盖
    assert db.cache_get("k1") == "v2"


@case("profile_get / profile_set")
def _():
    db.profile_set("nick", "小明")
    assert db.profile_get("nick") == "小明"
    assert db.profile_get("__absent__", "默认") == "默认"


# ---------------------------------------------------------------- 积分 / 宠物
@case("get_points / add_points（含下限保护）")
def _():
    db.add_points(100)
    p0 = db.get_points()
    assert p0 >= 100
    db.add_points(-50)
    assert db.get_points() == p0 - 50
    db.add_points(-999999)     # 不应为负
    assert db.get_points() == 0


@case("pet_get / pet_save 持久化")
def _():
    st = pet_mod.load()
    st.unlocked = ["cat", "bunny"]
    st.species = "bunny"
    st.exp = 77
    st.save()
    st2 = pet_mod.load()
    assert st2.species == "bunny"
    assert st2.unlocked == ["cat", "bunny"]
    assert st2.exp == 77
    # 回退
    st2.species = "cat"
    st2.save()


@case("宠物升级/喂养/满级边界")
def _():
    st = pet_mod.PetState(db.pet_get())
    st.exp = 0
    st._recompute_level()
    assert st.level >= 1
    lv_before = st.level
    up, old_stage, new_stage = st.add_exp(10000)
    assert up and st.level > lv_before
    # 满级
    st.exp = 10 ** 9
    st._recompute_level()
    assert st.level <= pet_mod.MAX_LEVEL
    assert st.need == 0 or st.level == pet_mod.MAX_LEVEL
    # 满级再加经验不应崩
    st.add_exp(1000)


@case("宠物图鉴（SPECIES / 各接口）")
def _():
    assert isinstance(pet_mod.SPECIES, dict) and pet_mod.SPECIES
    for key in pet_mod.SPECIES:
        assert isinstance(pet_mod.species_name(key), str)
        assert isinstance(pet_mod.unlock_cost(key), int)
        assert isinstance(pet_mod.colors(key), tuple) and len(pet_mod.colors(key)) >= 2
        for lv in (1, 8, 15, pet_mod.MAX_LEVEL):
            stage = pet_mod.stage_of(lv)
            assert isinstance(pet_mod.stage_name(stage), str)
    # 未知 key 不应崩
    assert pet_mod.species_name("__nope__")
    assert pet_mod.unlock_cost("__nope__") >= 0
    assert pet_mod.exp_needed(1) > 0


@case("lesson_stars / lesson_save_star")
def _():
    cid = db.add_course("星星课", "", "初级", "custom")
    db.add_sentences(cid, [("Star %d." % i, "星%d。" % i, "") for i in range(6)])
    assert db.lesson_stars(cid) == {}
    db.lesson_save_star(cid, 0, 3, 500)
    db.lesson_save_star(cid, 0, 2, 400)   # 覆盖
    stars = db.lesson_stars(cid)
    assert stars.get(0) == 3 or str(0) in stars
    db.delete_course(cid)


# ---------------------------------------------------------------- 引擎
@case("engine.split_words 边界")
def _():
    assert engine.split_words("") == []
    assert engine.split_words("   ") == []
    assert engine.split_words("One") == [("One", "")]
    assert engine.split_words("Hello, how are you?") == \
        [("Hello", ", "), ("how", " "), ("are", " "), ("you", "?")]
    # 拼回原句
    for t in ["", "One", "Hello, how are you?", "It's fine.", "A  B"]:
        assert "".join(w + s for w, s in engine.split_words(t)) == t


@case("engine.ChoiceState 选词/取回/错选")
def _():
    st = engine.ChoiceState("Hello, how are you?", "sentence")
    assert st.n_words == 4
    assert st.pick_word("nope") is False and st.errors == 1
    assert st.pick_word("Hello") is True and st.placed == 1
    assert st.undo() is True and st.placed == 0
    assert st.undo() is False
    for w, _s in engine.split_words(st.target):
        assert st.pick_word(w)
    assert st.finished
    assert st.rating >= 0 and st.score() > 0


@case("engine.ChoiceState 单词模式")
def _():
    st = engine.ChoiceState("apple", "word")
    assert st.n_words == 1
    assert st.pick_option("banana") is False
    assert st.pick_option("apple") is True and st.finished


@case("engine.TypingState 自动空格")
def _():
    st = engine.TypingState("Hello, how are you?", auto_space=True)
    for ch in "Hello, how are you?".replace(" ", ""):
        st.type_char(ch)
    assert st.buffer == st.target and st.errors == 0


@case("engine.TypingState 普通输入/错误/回退")
def _():
    st = engine.TypingState("abc")
    assert st.type_char("a")
    st.type_char("x")
    assert st.errors == 1
    st.backspace()
    assert st.buffer == "a"
    st.type_char("b")
    st.type_char("c")
    assert st.finished


@case("engine.pick_distractors")
def _():
    d = engine.pick_distractors(["a", "b", "c", "d"], ["a"], 2)
    assert len(d) == 2 and "a" not in d
    assert engine.pick_distractors([], [], 2) == []
    assert engine.pick_distractors(["a"], ["a"], 2) == []


@case("engine.Session 流程与结算")
def _():
    rows = [{"id": i, "en": "Hello there.", "zh": "你好。", "note": ""} for i in range(2)]
    sess = engine.Session(rows, "接口测试", mode="choice")
    assert sess.total == 2
    st = sess.next()
    assert st is not None
    assert sess.current is not None
    for w, _s in engine.split_words(st.target):
        st.pick_word(w)
    st.finish()
    r = sess.commit_current()
    assert r is not None
    assert sess.done == 1 and sess.total_score > 0
    assert isinstance(sess.summary(), dict)
    # 完成第二句后 Session 才算完成
    st2 = sess.next()
    assert st2 is not None
    for w, _s in engine.split_words(st2.target):
        st2.pick_word(w)
    st2.finish()
    sess.commit_current()
    assert sess.done == 2
    assert sess.finished, "两句都完成后 Session.finished 应为 True"
    assert sess.next() is None


@case("engine.Session typing/word 模式")
def _():
    rows = [{"id": 1, "en": "Hi there.", "zh": "你好。", "note": ""}]
    for mode in ("typing", "sentence", "word", "dictation", "phonics", "choice"):
        s = engine.Session(list(rows), "m", mode=mode)
        st = s.next()
        assert st is not None, mode


# ---------------------------------------------------------------- SRS 模块
@case("srs 调度（评分映射/封顶/复习降级）")
def _():
    for r in (0, 1, 3, 4, 5):
        q = srs.rating_to_quality(r)
        assert 0 <= q <= 5
    # 连续满分：间隔应封顶 365 天，日期不溢出
    c = srs.Card(sentence_id=1)
    for _ in range(60):
        c = srs.schedule(c, 5)
        assert c.interval <= 365.0
    assert c.reps > 0
    # 失败评分：reps 归零、lapses+1、当天再来
    before = c.lapses
    c = srs.schedule(c, 1)
    assert c.reps == 0 and c.lapses == before + 1
    assert c.interval == 0.0
    assert c.due == srs.today_str()


@case("db 边界：超长文本 / 特殊字符 / 重复写入 / 不存在 id")
def _():
    cid = db.add_course("边界课" + "长" * 200, "描述" * 500, "初级", "custom")
    # 超长句子 + SQL 特殊字符 + emoji/换行
    weird = ("It's a \"test\" 100% \\ end; DROP TABLE courses; -- \n line2 😀",
             "这是含 %s 与 '引号' 的译文。")
    db.add_sentences(cid, [(weird[0], weird[1], "")])
    rows = db.list_sentences(cid)
    assert len(rows) == 1 and rows[0]["en"] == weird[0]
    # 重复写入同一条（应新增而非报错）
    db.add_sentences(cid, [(weird[0], weird[1], "")])
    assert db.count_sentences(cid) == 2
    # 不存在的 id
    assert db.get_course(10 ** 8) is None
    assert db.get_sentence(10 ** 8) is None
    assert db.get_card(10 ** 8) is None
    assert db.list_sentences(10 ** 8) == []
    assert db.due_count(10 ** 8) == 0
    # 搜索需转义 % 与 _（否则会当通配符）
    db.search_sentences("%", limit=5)
    db.search_sentences("_", limit=5)
    db.delete_course(cid)


@case("db 事务：多写后仍能读回（commit 生效）")
def _():
    cid = db.add_course("事务课", "", "初级", "custom")
    for i in range(30):
        db.add_sentences(cid, [("Row %d." % i, "第%d行。" % i, "")])
    assert db.count_sentences(cid) == 30
    # 每个写接口都应 commit：重开连接仍可见
    conn = db.connect()
    n = conn.execute("SELECT COUNT(*) c FROM sentences WHERE course_id=?",
                     (cid,)).fetchone()["c"]
    conn.close()
    assert n == 30, "写入未持久化：%d" % n
    db.delete_course(cid)


@case("lesson_save_star 只升不降")
def _():
    cid = db.add_course("星级课", "", "初级", "custom")
    db.add_sentences(cid, [("S.", "句。", "") for _ in range(4)])
    db.lesson_save_star(cid, 0, 3, 900)
    db.lesson_save_star(cid, 0, 1, 100)   # 更低不应覆盖
    stars = db.lesson_stars(cid)
    key = 0 if 0 in stars else "0"
    assert stars[key] == 3, stars
    db.delete_course(cid)


# ---------------------------------------------------------------- AI 生成
@case("ai._parse_dicts 容错解析（代码块/截断/字段缺失）")
def _():
    from core.ai_client import _parse_dicts
    # 正常
    r = _parse_dicts('[{"en":"Hi.","zh":"你好。"}]', ("en", "zh"))
    assert r == [{"en": "Hi.", "zh": "你好。"}], r
    # 带 ```json 代码块
    r = _parse_dicts('```json\n[{"en":"A."}]\n```', ("en", "zh"))
    assert r and r[0]["en"] == "A." and r[0]["zh"] == ""
    # 漏逗号 / 被截断 → 回退逐对象解析
    r = _parse_dicts('[{"en":"A."}{"en":"B."}]', ("en", "zh"))
    assert len(r) == 2, r
    # 词汇字段
    raw = ('[{"word":"apple","zh":"苹果","ipa":"/ˈæpl/",'
           '"ex":"I eat an apple.","ex_zh":"我吃苹果。","tip":"水果"}]')
    r = _parse_dicts(raw, ("word", "zh", "ipa", "ex", "ex_zh", "tip"))
    assert r[0]["word"] == "apple" and r[0]["ipa"].startswith("/")
    # 非 JSON
    assert _parse_dicts("hello world", ("en", "zh")) == []
    assert _parse_dicts("", ("en", "zh")) == []


@case("ai.generate_course / generate_vocab（桩：数量上限与 note 格式）")
def _():
    from core.ai_client import AIClient
    cli = AIClient({})

    # 用桩替换 chat：每批返回 50 条，且内容随批次数递增（避免被去重逻辑丢弃）
    _state = {"round": 0}

    def fake_chat(system, user, temperature=0.3, use_cache=True):
        key = "word" if '"word"' in system else "en"
        n = 50
        import re as _re
        m = _re.search(r"数量：(\d+)", user)
        if m:
            n = int(m.group(1))
        n = min(n, 50)
        base = _state["round"] * 50
        _state["round"] += 1
        items = []
        for i in range(n):
            j = base + i
            if key == "word":
                items.append('{"word":"w%d","zh":"词%d","ipa":"/w/",'
                             '"ex":"ex %d","ex_zh":"例%d","tip":"t"}' % (j, j, j, j))
            else:
                items.append('{"en":"s%d","zh":"句%d"}' % (j, j))
        return "[" + ",".join(items) + "]"

    cli.chat = fake_chat
    # 句子：请求 120 → 至少拿到 120
    pairs = cli.generate_course("测试", "初级", 120)
    assert len(pairs) == 120, len(pairs)
    assert pairs[0][0].startswith("s")
    # 词汇：请求 80 → 6 元组格式化为 3 元组，note 含三段
    vocab = cli.generate_vocab("测试", "初级", 80)
    assert len(vocab) == 80, len(vocab)
    w, zh, note = vocab[0]
    assert w.startswith("w") and zh.startswith("词")
    assert "音标：" in note and "例句：" in note and "译文：" in note and "讲解：" in note
    # 上限钳制：请求 99999 → 不报错，最多 5000
    big = cli.generate_course("测试", "初级", 99999)
    assert len(big) <= 5000
    # 最小钳制
    tiny = cli.generate_course("测试", "初级", 1)
    assert len(tiny) >= 1


@case("worker.run_async 异常回调不因闭包变量被删而崩（回归）")
def _():
    import time as _t
    from kivy.base import EventLoop
    from kivy.clock import Clock
    from core.worker import run_async
    EventLoop.ensure_window()
    got = {}

    def boom():
        raise ValueError("模拟接口失败")

    run_async(boom, lambda r: got.setdefault("ok", r),
              lambda m: got.setdefault("err", m))

    def _pump(cond, tries=200):
        for _ in range(tries):
            EventLoop.idle()
            Clock.tick()
            if cond():
                return True
            _t.sleep(0.01)
        return cond()

    assert _pump(lambda: "err" in got), "异常回调未触发"
    assert "模拟接口失败" in got["err"], got["err"]
    # 成功回调
    got2 = {}
    run_async(lambda: 1 + 1, lambda r: got2.setdefault("ok", r))
    assert _pump(lambda: "ok" in got2), "成功回调未触发"
    assert got2.get("ok") == 2


@case("拼读页音素卡片：跟读按钮存在且读的是该音素的纯音示范词")
def _():
    from main import EnglishClubApp
    app = EnglishClubApp()
    app.build()
    ph = app.screens("phonics")
    ph.refresh()
    assert ph.tabs.tab_list, "拼读页没有 tab"

    def _buttons(w):
        # PrimaryButton 继承 ButtonBehavior+BoxLayout，并不继承 uix.button.Button，
        # 故用「是否有 text 属性」判断，兼容所有按钮类。
        out = []
        if hasattr(w, "text") and w.text:
            out.append(w)
        for c in getattr(w, "children", []):
            out.extend(_buttons(c))
        return out

    # 直接检查卡片工厂产物：确认音素卡片含「跟读」按钮并能朗读
    from ui.phonics_screen import _card as make_card
    from ui.phonics_screen import phoneme_sound
    entry = None
    for g in ph.groups:
        for e in g["entries"]:
            if e.get("ipa") and e.get("words"):
                entry = e
                break
        if entry:
            break
    assert entry, "未找到带音标的音素条目"
    spoken = []
    ph.ctx.speaker.say = lambda t: spoken.append(t)
    card = make_card(entry["g"], ipa=entry["ipa"],
                     on_say=lambda: ph._say_phoneme(entry))
    horns = [b for b in _buttons(card) if "跟读" in (b.text or "")]
    assert horns, "音素卡片未生成「跟读」喇叭按钮"
    horns[0].dispatch("on_release")
    want = phoneme_sound(entry)
    assert spoken == [want], \
        "跟读应朗读纯音示范词 %r，实际 %r" % (want, spoken)
    assert want != entry["words"][0][0], \
        "跟读读的是纯音示范词，不应等于整词 %r" % want

    # 关键音素必须命中"纯音"表，而不是退化成整词
    # （/æ/→at 而非 apple；/ʃ/→shh 而非 ship）
    from core.phonics_data import GROUPS, FAMILY_SENTENCES
    expect = {"/æ/": "at", "/ʌ/": "up", "/ʃ/": "shh", "/θ/": "think",
              "/iː/": "see", "/eɪ/": "say", "/ŋ/": "sing"}
    seen = {}
    for g in GROUPS:
        for e in g["entries"]:
            seen.setdefault(e["ipa"], set()).add(phoneme_sound(e))
    for ipa, want in expect.items():
        assert ipa in seen, "缺少音素 %s" % ipa
        assert want in seen[ipa], \
            "%s 应由纯音表给 %r，实际 %r" % (ipa, want, sorted(seen[ipa]))
    for f in FAMILY_SENTENCES:
        assert phoneme_sound(f), "词族 %s 取不到示范读音" % f["g"]
    # 每个音素都必须有可读文本（不允许空串）
    for g in GROUPS:
        for e in g["entries"]:
            assert phoneme_sound(e).strip(), "%s %s 无示范读音" % (e["g"], e["ipa"])
    # 页面已为音素组构建卡片（tab_list 有内容，且卡片工厂带喇叭）
    assert ph.tabs.tab_list, "拼读页未构建任何 tab"

    # 提示条必须走 MixedFontLabel：主字体子集没有 ʃ ɪ ŋ 等字形，
    # 用普通 Label 会显示方块（回归：提示条曾用 AppLabel）。
    from ui.theme import (FONT_NAME, IPA_FONT_NAME, MixedFontLabel,
                          _IPA_CHARS)
    ph._flash("跟读：%s %s" % (entry["ipa"], want))
    assert isinstance(ph.flash_lbl, MixedFontLabel), \
        "跟读提示条必须是 MixedFontLabel，否则音标会显示方块"
    segs = MixedFontLabel.split_segments(ph.flash_lbl_text())
    ipa_part = [s for s, is_ipa in segs if is_ipa]
    assert ipa_part, "提示条文本未切出 IPA 段：%r" % (segs,)
    assert any(ch in "".join(ipa_part) for ch in entry["ipa"]), \
        "提示条的音标 %r 未被 IPA 字体渲染" % entry["ipa"]
    # 每个 IPA 段里的字符都必须能由 IPA 字体渲染（非 ASCII 纯音标字符）
    for seg in ipa_part:
        for ch in seg:
            if ch in _IPA_CHARS:
                continue
            assert ch in "/" or ch.isascii(), \
                "%r 落在 IPA 段但主字体与 IPA 字体都无字形" % ch
    # IPA 字体必须真的比主字体多出这些字形
    assert IPA_FONT_NAME != FONT_NAME

    # 全量回归：拼读内容里所有文本按分段结果渲染，都不允许出现缺字形
    # （回归：note「长音：food / moon；短音 /ʊ/：book / look」曾把
    #  两个斜杠之间的中文误判为音标段，中文在 IPA 字体下变方块）
    from ui.theme import _IPA_ALLOWED
    root = os.path.dirname(os.path.abspath(__file__))
    font_paths = {
        FONT_NAME: os.path.join(root, "assets/fonts/NotoSansSC-Subset.otf"),
        IPA_FONT_NAME: os.path.join(root, "assets/fonts/IPAFont-Subset.ttf"),
    }
    try:
        from fontTools.ttLib import TTFont
    except ImportError:
        TTFont = None
    if TTFont and all(os.path.exists(p) for p in font_paths.values()):
        cmaps = {k: set(TTFont(v).getBestCmap())
                 for k, v in font_paths.items()}
        texts = []
        for g in GROUPS:
            for e in g["entries"]:
                texts += [e["note"], e["ipa"]]
        for f in FAMILY_SENTENCES:
            texts += [f["note"], f["ipa"], f["en"], f["zh"]]
        for txt in texts:
            for seg, is_ipa in MixedFontLabel.split_segments(txt):
                cmap = cmaps[IPA_FONT_NAME if is_ipa else FONT_NAME]
                miss = [c for c in seg if ord(c) not in cmap and c not in " \t"]
                assert not miss, \
                    "%r 的片段 %r 用%s字体缺字形 %r" % (
                        txt, seg, "IPA" if is_ipa else "主", "".join(miss))
    assert _IPA_ALLOWED, "IPA 允许字符集为空"

    print("SMOKE OK  phonics-speaker entry=%s ipa=%s spoken=%r"
          % (entry["g"], entry["ipa"], spoken))


# ---------------------------------------------------------------- 汇总
print("\n" + "=" * 56)
print("通过 %d 项，失败 %d 项" % (len(PASS), len(FAIL)))
if FAIL:
    for name, e in FAIL:
        print("  ✗ %s -> %s: %s" % (name, type(e).__name__, e))
    sys.exit(1)
print("ALL API TESTS PASS")
