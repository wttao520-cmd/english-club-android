# -*- coding: utf-8 -*-
"""核心练习页。

手机上用系统软键盘输入：一个不可见的 TextInput 负责唤起键盘并接收文本，
打字板负责逐字符着色。桌面预览时用物理键盘输入同一个 TextInput。
"""

import random

from kivy.app import App
from kivy.clock import Clock
from kivy.metrics import dp, sp
from kivy.properties import StringProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.progressbar import ProgressBar
from kivy.uix.screenmanager import Screen
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget

from core import db
from core.engine import RATING_LABEL, Session, split_words
from core.srs import rating_to_quality, schedule
from core.worker import run_async
from .theme import (ACCENT, BLUE, CARD, FONT_NAME, GREEN, IPA_FONT_NAME,
                    MUTED, PANEL2, RED, TEXT, YELLOW, AppLabel, AppSpinner,
                    AppSpinnerOption, AppTextInput, PrimaryButton, TitleLabel,
                    rgba)
from .widgets import ComboBadge, PickerPopup, TypingBoard, WordChoiceBoard
from .pet_screen import PetEntry

# 选词模式（choice）免键盘：点选词块拼出当前句
MODES = [("句子模式", "sentence"), ("单词模式", "word"),
         ("默写模式", "dictation"), ("拼读模式（听音拼写）", "phonics"),
         ("选词模式", "choice")]

CHOICE_MODES = ("choice",)

RATING_COLOR = {5: GREEN, 4: ACCENT, 3: YELLOW, 0: RED}

LESSON_SIZE = 10


def lesson_count(n_items):
    """课程共有多少关。"""
    return max(1, -(-n_items // LESSON_SIZE))


def stars_for(accuracy, rating_avg):
    """按准确率与平均评分给 1~3 星。"""
    if accuracy >= 90 and rating_avg >= 4.5:
        return 3
    if accuracy >= 70:
        return 2
    return 1


class AIPanel(Popup):
    """AI 英语老师面板（手机上以浮层方式打开）。"""

    def __init__(self, screen, **kw):
        Popup.__init__(self, title="", separator_height=0, **kw)
        self.screen = screen
        self.size_hint = (0.96, 0.8)
        self.background = ""
        self.background_color = rgba("#141922")

        root = BoxLayout(orientation="vertical", padding=dp(14), spacing=dp(10))
        root.add_widget(TitleLabel(text="AI 英语老师"))

        self.out = AppTextInput(readonly=True, size_hint=(1, 1),
                                background_color=rgba("#1c2230"))
        root.add_widget(self.out)

        self.inp = AppTextInput(hint_text="有疑问？直接问，例如：为什么用 in 不用 on？",
                                size_hint_y=None, height=dp(46), multiline=False)
        self.inp.bind(on_text_validate=lambda w: self._ask())
        root.add_widget(self.inp)

        bar = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(8))
        for text, cb in [("讲解本句", lambda x: self.screen._ai_explain(self)),
                         ("翻译本句", lambda x: self.screen._ai_translate(self)),
                         ("提问", self._ask)]:
            b = PrimaryButton(text=text, size_hint_x=0.33)
            b.bind(on_release=cb)
            bar.add_widget(b)
        root.add_widget(bar)

        close = PrimaryButton(text="关闭", size_hint_y=None, height=dp(44),
                              bg=rgba(CARD))
        close.bind(on_release=self.dismiss)
        root.add_widget(close)
        self.content = root

    def _ask(self, *a):
        q = self.inp.text.strip()
        if not q:
            return
        self.inp.text = ""
        self.screen._ai_ask(self, q)

    def set_text(self, text):
        self.out.text = text


class PracticeScreen(Screen):
    status = StringProperty("")

    def __init__(self, **kw):
        Screen.__init__(self, **kw)
        self.session = None
        self.course_ids = []
        self._mode = self._norm_mode(
            App.get_running_app().ctx.config.get("mode", "choice"))
        self._build()
        # 立即按当前模式设一次显隐：否则启动时选词板会以初始高度占位，
        # 叠加打字板后总高超出竖屏，把顶部课程/模式按钮挤出可视区。
        self._apply_mode_visibility()
        Clock.schedule_interval(self._tick, 0.5)

    @property
    def ctx(self):
        return App.get_running_app().ctx

    # ------------------------------------------------------------ UI
    def _build(self):
        root = BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(6))

        # 第一行：宠物+积分入口 | 课程选择 | 模式选择（全弹窗化，竖屏不截断）
        top = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(6))
        self.pet_entry = PetEntry()
        top.add_widget(self.pet_entry)
        self.course_btn = PrimaryButton(
            text="选择课程", size_hint_x=1, font_size=sp(13), bg=rgba(PANEL2))
        self.course_btn.bind(on_release=lambda b: self._pick_course())
        top.add_widget(self.course_btn)
        self.mode_btn = PrimaryButton(
            text=self._mode_name(self.ctx.config.get("mode", "choice")),
            size_hint_x=None, width=dp(104), font_size=sp(12), bg=rgba(ACCENT))
        self.mode_btn.bind(on_release=lambda b: self._pick_mode())
        top.add_widget(self.mode_btn)
        root.add_widget(top)

        # 第二行：关卡标签 | 得分 | 用时
        row2 = BoxLayout(size_hint_y=None, height=dp(24), spacing=dp(6))
        self.lesson_lbl = AppLabel(text="", font_size=sp(12), color=rgba(YELLOW),
                                   halign="left")
        self.score_lbl = AppLabel(text="0 分", font_size=sp(14), bold=True,
                                  color=rgba(GREEN), size_hint_x=None,
                                  width=dp(70), halign="right")
        self.time_lbl = AppLabel(text="00:00", font_size=sp(13),
                                 color=rgba(MUTED), size_hint_x=None,
                                 width=dp(54), halign="right")
        row2.add_widget(self.lesson_lbl)
        row2.add_widget(Widget())
        row2.add_widget(self.score_lbl)
        row2.add_widget(self.time_lbl)
        root.add_widget(row2)

        # 中文提示（题干）
        self.zh_lbl = AppLabel(text="像玩游戏一样，用句子学英语", font_size=sp(19),
                               bold=True, halign="center", size_hint_y=None,
                               height=dp(48), color=rgba(TEXT))
        root.add_widget(self.zh_lbl)

        # 音标行（词汇课程显示，IPAFont 专用字体）
        self.ipa_lbl = Label(text="", font_name=IPA_FONT_NAME,
                             font_size=sp(18), color=rgba(ACCENT),
                             size_hint_y=None, height=dp(0), halign="center",
                             valign="middle")
        root.add_widget(self.ipa_lbl)

        self.note_lbl = AppLabel(text="", font_size=sp(12), color=rgba(MUTED),
                                 halign="center", size_hint_y=None, height=dp(18))
        root.add_widget(self.note_lbl)

        # ---------------- 中部答题区（弹性占满剩余空间）----------------
        answer = BoxLayout(size_hint_y=1)
        self.answer_area = answer
        root.add_widget(answer)

        # 打字板（句子/单词/默写/拼读模式）：弹性填满答题区
        self.board = TypingBoard()
        self.board.size_hint = (1, 1)
        self.board.focus_callback = self._focus_input
        self.board_area = self.board

        # 选词板（选词 / 选词·单词模式）：上排槽位 + 下排流式词库
        self.choice_board = WordChoiceBoard(self._on_word_pick, self._on_undo)
        self.choice_board.size_hint = (1, 1)

        # 隐藏输入框：唤起软键盘并接收文本
        self.input = TextInput(size_hint=(1, None), height=dp(1), opacity=0,
                               multiline=False, font_name=FONT_NAME,
                               keyboard_suggestions=False, input_type="text")
        self.input.bind(text=self._on_text)
        self.input.bind(on_text_validate=lambda w: self._manual_next())
        root.add_widget(self.input)

        # 键盘唤起按钮（仅打字模式显示）
        self.focus_btn = PrimaryButton(
            text="点击此处开始输入（唤起键盘）", size_hint_y=None, height=dp(42),
            bg=rgba(BLUE))
        self.focus_btn.bind(on_release=lambda b: self._focus_input())
        root.add_widget(self.focus_btn)

        # 结算提示 + 连击
        row3 = BoxLayout(size_hint_y=None, height=dp(34), spacing=dp(6))
        self.rating_lbl = AppLabel(text="", font_size=sp(17), bold=True,
                                   halign="left")
        self.combo = ComboBadge()
        row3.add_widget(self.rating_lbl)
        row3.add_widget(self.combo)
        root.add_widget(row3)

        # 进度
        self.progress = ProgressBar(size_hint_y=None, height=dp(6), max=100)
        root.add_widget(self.progress)
        self.progress_lbl = AppLabel(text="", font_size=sp(11), color=rgba(MUTED),
                                     size_hint_y=None, height=dp(16))
        root.add_widget(self.progress_lbl)

        # 操作条
        bar = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(6))
        for text, cb in [("朗读", self._speak), ("重来", self._retry),
                         ("跳过", self._skip), ("下一句", self._manual_next),
                         ("AI", self._open_ai)]:
            b = PrimaryButton(text=text, font_size=sp(13))
            b.bind(on_release=cb)
            bar.add_widget(b)
        root.add_widget(bar)

        self.add_widget(root)

    # ------------------------------------------------------------ 数据
    def refresh_courses(self):
        courses = db.list_courses()
        self.course_ids = [c["id"] for c in courses]
        self.courses = [dict(c) for c in courses]
        if not getattr(self, "_current_title", None) and courses:
            self._current_title = courses[0]["title"]
        self.course_btn.text = self._current_title or "选择课程"
        self.pet_entry.refresh()

    @staticmethod
    def _norm_mode(mode):
        """把历史遗留的模式名归一化（choice_word 已并入 choice）。"""
        if mode == "choice_word":
            return "choice"
        return mode if mode in dict(MODES).values() else "sentence"

    def _mode_name(self, mode):
        return dict((v, k) for k, v in MODES).get(mode, "句子模式")

    def _current_cid(self):
        title = getattr(self, "_current_title", None)
        for c in getattr(self, "courses", []):
            if c["title"] == title:
                return c["id"]
        return self.course_ids[0] if self.course_ids else None

    def _pick_course(self):
        titles = [c["title"] for c in getattr(self, "courses", [])]
        if not titles:
            return
        PickerPopup("选择课程", titles, self._course_chosen,
                    current=getattr(self, "_current_title", None)).open()

    def _course_chosen(self, title):
        self._current_title = title
        self.course_btn.text = title
        self.lesson_lbl.text = ""
        self._on_course_picked()

    def _pick_mode(self):
        names = [m[0] for m in MODES]
        PickerPopup("练习模式", names, self._mode_chosen,
                    current=self._mode_name(self._mode)).open()

    def _mode_chosen(self, name):
        mode = dict(MODES).get(name, "sentence")
        self.ctx.config.set("mode", mode)
        self.mode = mode
        self.mode_btn.text = name
        self._apply_mode_visibility()
        if self.session and self.session.state:
            # 切换模式会改变状态机类型：用当前课程句子按新模式重新开始，
            # 避免旧 state（如 TypingState）在新界面下行为错乱。
            rows = [dict(r) for r in self.session.sentences]
            self.start(rows, self.session.title, mode)

    def _on_course_picked(self, *a):
        cid = self._current_cid()
        if cid is None:
            return
        course = db.get_course(cid)
        key = course["builtin_key"] if course else ""
        n = int(self.ctx.config.get("lesson_size", 10)) or 10
        rows = db.due_course_cards(cid, n)
        if not rows:
            rows = db.list_sentences(cid)[:n]
        self.lesson_ctx = None
        mode = "choice" if key.startswith("vocab_") else None
        self.start([dict(r) for r in rows],
                   course["title"] if course else "练习", mode)

    def start_lesson(self, course_id, lesson_idx):
        """闯关模式：练习课程的一个固定关卡。"""
        course = db.get_course(course_id)
        rows = db.sentences_range(course_id,
                                  lesson_idx * LESSON_SIZE,
                                  lesson_idx * LESSON_SIZE + LESSON_SIZE - 1)
        if not rows:
            return
        mode = None
        key = course["builtin_key"] if course else ""
        if key.startswith("vocab_"):
            mode = "choice"
        total_lessons = lesson_count(db.count_sentences(course_id))
        self.lesson_ctx = (course_id, lesson_idx, total_lessons)
        self.start([dict(r) for r in rows],
                   course["title"] if course else "练习", mode)

    # ------------------------------------------------------------ 会话
    @property
    def mode(self):
        return self._mode

    @mode.setter
    def mode(self, v):
        self._mode = v

    def start(self, sentences, title, mode=None):
        if not sentences:
            self.status = "这个课程还没有可练习的句子"
            return
        if mode:
            self._mode = mode
            self.mode_btn.text = self._mode_name(mode)
        lctx = getattr(self, "lesson_ctx", None)
        if lctx:
            self.lesson_lbl.text = "第 %d / %d 关" % (lctx[1] + 1, lctx[2])
        else:
            self.lesson_lbl.text = "自由练习"
        self._switching = True   # 清空输入框期间屏蔽 _on_text
        self.session = Session(list(sentences), title,
                               mode=self._session_mode())
        self.session.earned = 0
        self._apply_mode_visibility()
        self.input.text = ""
        self._switching = False
        self._next_sentence()

    def _next_sentence(self):
        # 清空输入框会同步触发 _on_text("")，若旧 state 处于 finished 会被
        # 误判为再次完成 → 同一句重复结算 + 再调度一个 auto_next（前进两步）。
        # _switching 屏蔽 + commit 幂等（engine 层）双保险。
        self._switching = True
        self.input.text = ""
        self._switching = False
        st = self.session.next()
        if st is None:
            self._finish_session()
            return
        self.rating_lbl.text = ""
        self._render()
        # 拼读模式：必须先听到发音，再听音拼写（延迟一点确保音频通道就绪）
        if self._mode == "phonics":
            Clock.schedule_once(lambda dt: self._speak(), 0.35)
        elif self.ctx.config.get("auto_tts") and self.ctx.config.get("tts_enabled"):
            self._speak()
        # 选词模式用点击作答，不自动弹出软键盘
        if self._mode not in CHOICE_MODES:
            Clock.schedule_once(lambda dt: self._focus_input(), 0.15)

    # ------------------------------------------------------------ 选词模式
    def _session_mode(self):
        if self._mode in ("word", "sentence", "dictation", "phonics"):
            return self._mode
        return "choice" if self._mode == "choice" else "typing"

    def _apply_mode_visibility(self):
        """按当前模式切换答题控件：把当前模式用的那块放进弹性答题区。

        必须真正 add/remove（而不是 opacity/size_hint），否则隐藏的控件
        仍会占位、拦截触摸，导致「被单词挡住、点不了键盘」。
        """
        is_choice = self._mode in CHOICE_MODES
        want = self.choice_board if is_choice else self.board
        area = self.answer_area
        if want.parent is not area:
            area.clear_widgets()
            area.add_widget(want)
        # 选词模式不需要软键盘：彻底隐藏「唤起键盘」按钮（不占位、不透明）
        self.focus_btn.height = 0 if is_choice else dp(42)
        self.focus_btn.opacity = 0 if is_choice else 1
        self.focus_btn.disabled = is_choice

    def _render_choice(self, st, cur):
        """选词模式：候选池 = 当前句的所有单词。

        打乱只做一次并缓存（按句子 id）；之后选中的词只是「隐藏」，
        完整池顺序始终不变，因此其余词块的位置绝不跳变；
        取回时对应词块重新显现，回到原位。
        """
        words = split_words(st.target)
        placed = st.placed
        sid = cur["id"] if cur is not None and "id" in cur.keys() else st.target
        if getattr(self, "_pool_cache_sid", None) != sid:
            full = [w for w, _sp in words]
            random.shuffle(full)
            self._pool_cache_sid = sid
            self._pool_full = full            # 打乱后的完整池（顺序固定）
        full = list(getattr(self, "_pool_full", []))
        used = [w for w, _sp in words[:placed]]
        self.choice_board.show(words, placed, full, used=used,
                               wrong_text=getattr(st, "wrong_text", None))

    def _on_word_pick(self, text, tile=None):
        """句子选词：点击词块尝试填入下一个空位。"""
        st = self.session.state if self.session else None
        if st is None or st.finished:
            return
        try:
            ok = st.pick_word(text)
        except AttributeError:
            return
        if ok:
            self.ctx.sfx.play("key")
            self._render()
            if st.finished:
                self._on_sentence_done()
        else:
            self.ctx.sfx.play("bad")
            self.rating_lbl.text = ("[color=%s]选错啦，再想想[/color]" % RED)
            self._render()
            if tile is not None and hasattr(tile, "reset_bg"):
                tile.set_bg(RED)
                Clock.schedule_once(lambda dt: tile.reset_bg(), 0.4)

    def _on_undo(self, idx=None):
        """取回最后一个已填入的词。"""
        st = self.session.state if self.session else None
        if st is None or not hasattr(st, "undo"):
            return
        if st.undo():
            self.rating_lbl.text = ""
            self._render()

    def _current_chunks(self):
        cur = self.session.current if self.session else None
        if cur is None or self.session.state is None:
            return None
        raw = cur["phonics"] if "phonics" in cur.keys() else ""
        if not raw:
            return None
        parts = raw.split("|")
        return parts if "".join(parts) == self.session.state.target else None

    def _render(self):
        st = self.session.state if self.session else None
        cur = self.session.current if self.session else None
        if st is None or cur is None:
            return
        self.zh_lbl.text = cur["zh"] or "（暂无译文，可让 AI 翻译）"
        note = cur["note"] if "note" in cur.keys() else ""
        # 音标行：note 以「音标：/…/」开头时提取显示（IPAFont）
        ipa_text = ""
        if note.startswith("音标："):
            nl = note.find("\n")
            ipa_text = note[3:nl if nl > 0 else None].strip()
            note = note[nl + 1:] if nl > 0 else ""
        self.ipa_lbl.text = ipa_text
        self.ipa_lbl.height = dp(26) if ipa_text else dp(0)
        if self._mode == "phonics" and note.count("｜") == 2:
            note = "%s｜%s" % (note.split("｜")[1], note.split("｜")[2])
        self.note_lbl.text = note or ""
        if self._mode == "choice":
            self._render_choice(st, cur)
        else:
            hidden = self._mode in ("dictation", "phonics")
            self.board.set_state(st.target, st.buffer, st.ok_len, hidden,
                                 self._current_chunks())
        total = max(1, self.session.total)
        self.progress.value = 100.0 * self.session.done / total
        self.progress_lbl.text = "第 %d / %d 句 · %s" % (
            self.session.done, total, self.session.title)
        self.combo.value = st.combo
        self.score_lbl.text = str(self.session.total_score)

    def _focus_input(self):
        if self._mode in CHOICE_MODES:
            return
        self.input.focus = True

    # ------------------------------------------------------------ 输入
    def _on_text(self, instance, value):
        if getattr(self, "_switching", False):
            return   # 程序性清空/切换，非用户输入
        if self._mode in CHOICE_MODES:
            return   # 选词模式不通过文本输入
        st = self.session.state if self.session else None
        if st is None:
            return
        target = st.target
        if len(value) > len(target):
            value = value[:len(target)]
            instance.text = value
            return
        st.sync(value)
        self._render()
        self.ctx.sfx.play("bad" if st.has_error else "key")
        if st.finished:
            self._on_sentence_done()

    def _tick(self, dt):
        if self.session and self.session.state and self.session.state.started_at:
            import time
            secs = int(time.time() - self.session.started_at)
            self.time_lbl.text = "%02d:%02d" % (secs // 60, secs % 60)

    # ------------------------------------------------------------ 结算
    def _on_sentence_done(self):
        st = self.session.state
        res = self.session.commit_current()
        if res is None:
            return
        self.ctx.sfx.play("perfect" if res["rating"] == 5 else "good")

        sid = self.session.current["id"]
        card = db.get_or_create_card(sid)
        schedule(card, rating_to_quality(res["rating"]))
        db.save_card(card)
        db.add_review(sid, res["rating"], res["wpm"], res["accuracy"],
                      res["combo_max"], len(st.target), int(res["duration"] * 1000))
        db.bump_daily(seconds=int(res["duration"]), sentences=1, chars=len(st.target),
                      errors=res["errors"], combo_max=res["combo_max"], score=res["score"])

        if res["rating"] == 0:
            self.session.sentences.append(dict(self.session.current))

        # ---- 积分：完成即得，Perfect 与连击有加成 ----
        gain = 2 + (3 if res["rating"] == 5 else 0) \
            + min(5, res["combo_max"] // 5)
        new_total = db.add_points(gain)
        self.pet_entry.refresh()
        self.session.earned = getattr(self.session, "earned", 0) + gain

        color = RATING_COLOR.get(res["rating"], TEXT)
        self.rating_lbl.text = (
            "[color=%s]%s[/color]  [color=%s]%.0f WPM · 准确率 %.0f%%[/color]"
            "  [color=%s]+%d 分[/color]"
            % (color, RATING_LABEL[res["rating"]], MUTED,
               res["wpm"], res["accuracy"], YELLOW, gain))
        self._render()
        # 拼读模式已在句首播放过发音，完成后不再重复播放
        if self._mode != "phonics":
            self._speak()
        if self.ctx.config.get("auto_next", True):
            self._auto_event = Clock.schedule_once(lambda dt: self._auto_next(), 1.1)

    def _cancel_auto_next(self):
        """取消已排定的自动前进（用户手动点了「下一句」时立即走）。"""
        ev = getattr(self, "_auto_event", None)
        if ev is not None:
            ev.cancel()
            self._auto_event = None

    def _auto_next(self):
        if self.session and self.session.state and self.session.state.finished:
            self._next_sentence()

    def _manual_next(self, *a):
        st = self.session.state if self.session else None
        if st is not None and st.finished:
            # 句子已完成：立即进下一句，取消 1.1 秒自动等待
            self._cancel_auto_next()
            self._next_sentence()
        elif self.session is not None and st is not None:
            # 给出可见反馈，避免“点了没反应”的困惑
            self.rating_lbl.text = ("[color=%s]先完成当前句子，或用「跳过」[/color]"
                                    % MUTED)
            self._focus_input()
        else:
            self._focus_input()

    def _retry(self, *a):
        if self.session and self.session.state:
            self.session.state.reset()
            self.input.text = ""
            self.rating_lbl.text = ""
            self._render()
        self._focus_input()

    def _skip(self, *a):
        if self.session and self.session.state:
            import time
            st = self.session.state
            st.buffer = st.target
            # 从未输入过的句子：把时间窗补齐，避免 wpm/耗时异常
            if st.started_at is None:
                st.started_at = time.time() - 0.001
            st.skipped = True   # 结算时 rating=Again、score=0（见 engine.py）
            st.finished_at = time.time()
            self._on_sentence_done()
            # 跳过意图明确：立即进下一句，不等自动计时
            self._cancel_auto_next()
            self._next_sentence()

    def _speak(self, *a):
        if not self.ctx.config.get("tts_enabled", True):
            return
        if self.session and self.session.current:
            self.ctx.speaker.say(self.session.current["en"])

    def _finish_session(self):
        summary = self.session.summary()
        self.board.set_state("", "", 0)
        self.zh_lbl.text = "本关完成！"
        self.ipa_lbl.text = ""
        self.ipa_lbl.height = dp(0)
        self.progress.value = 100

        # ---- 关卡结算：算星、落库、首次通关奖励 ----
        stars = stars_for(summary["accuracy"],
                          summary["score"] / max(1, summary["sentences"] * 100))
        summary["stars"] = stars
        summary["points"] = getattr(self.session, "earned", 0)
        lctx = getattr(self, "lesson_ctx", None)
        summary["lesson"] = lctx
        if lctx:
            course_id, idx, total_lessons = lctx
            first = db.lesson_stars(course_id).get(idx, 0) == 0
            db.lesson_save_star(course_id, idx, stars, summary["score"])
            bonus = 20 if first else 5
            db.add_points(bonus)
            summary["points"] += bonus
            self.lesson_lbl.text = "第 %d / %d 关 · %s" % (
                idx + 1, total_lessons, "★" * stars)
        else:
            db.add_points(5)  # 自由练习整场奖励
            summary["points"] += 5
        self.pet_entry.refresh()

        App.get_running_app().refresh_all()
        self._show_summary(summary)

    def _show_summary(self, s):
        box = BoxLayout(orientation="vertical", padding=dp(16), spacing=dp(10))
        box.add_widget(TitleLabel(text="关卡完成！"))
        if s.get("lesson"):
            cid, idx, total = s["lesson"]
            box.add_widget(AppLabel(
                text="第 %d / %d 关 · [color=%s]%s[/color]" % (
                    idx + 1, total, YELLOW, "*" * s["stars"]),
                font_size=sp(15), size_hint_y=None, height=dp(28),
                halign="center"))
        for name, val, color in [("得分", str(s["score"]), GREEN),
                                 ("准确率", "%.1f%%" % s["accuracy"], ACCENT),
                                 ("速度", "%.0f WPM" % s["wpm"], TEXT),
                                 ("最大连击", "x%d" % s["combo_max"], YELLOW),
                                 ("Perfect", "%d / %d" % (s["perfect"], s["sentences"]), GREEN)]:
            box.add_widget(AppLabel(text="[color=%s]%s[/color]：%s" % (color, name, val),
                                    font_size=sp(16), size_hint_y=None, height=dp(28)))
        box.add_widget(AppLabel(
            text="[color=%s]获得 %d 积分 · 去喂宠物吧！[/color]" % (YELLOW, s["points"]),
            font_size=sp(15), size_hint_y=None, height=dp(30), halign="center"))
        box.add_widget(AppLabel(text="用时 %.1f 分钟 · %s" % (s["elapsed"] / 60.0, s["title"]),
                                font_size=sp(12), color=rgba(MUTED),
                                size_hint_y=None, height=dp(24)))
        bar = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(8))
        again = PrimaryButton(text="再来一关", bg=rgba(BLUE))
        back = PrimaryButton(text="返回")
        bar.add_widget(again)
        bar.add_widget(back)
        box.add_widget(bar)

        popup = Popup(title="", content=box, size_hint=(0.9, 0.75),
                      background="", background_color=rgba(CARD),
                      separator_height=0)
        again.bind(on_release=lambda b: (popup.dismiss(),
                                         self._on_course_picked()))
        back.bind(on_release=popup.dismiss)
        popup.open()

    # ------------------------------------------------------------ AI
    def _open_ai(self, *a):
        AIPanel(self).open()

    def _guard_ai(self, panel):
        if not self.ctx.ai.enabled:
            panel.set_text("尚未启用 AI：请在「设置」中填写 API Key 后使用。")
            return False
        panel.set_text("AI 思考中…")
        return True

    def _ai_explain(self, panel):
        if not self.session or not self.session.current:
            panel.set_text("先开始练习，再让 AI 讲解当前句子。")
            return
        if not self._guard_ai(panel):
            return
        cur = self.session.current
        zh = cur["zh"] if "zh" in cur.keys() else ""
        run_async(self.ctx.ai.explain, panel.set_text, panel.set_text,
                  cur["en"], None, zh)

    def _ai_translate(self, panel):
        if not self.session or not self.session.current:
            return
        if not self._guard_ai(panel):
            return
        run_async(self.ctx.ai.translate, panel.set_text, panel.set_text,
                  self.session.current["en"])

    def _ai_ask(self, panel, question):
        if not self._guard_ai(panel):
            return
        ctx_text = self.session.current["en"] if self.session and self.session.current else ""
        run_async(self.ctx.ai.ask, panel.set_text, panel.set_text, question, ctx_text)


_ = AppSpinnerOption, Label, ScrollView
