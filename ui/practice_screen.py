# -*- coding: utf-8 -*-
"""核心练习页。

手机上用系统软键盘输入：一个不可见的 TextInput 负责唤起键盘并接收文本，
打字板负责逐字符着色。桌面预览时用物理键盘输入同一个 TextInput。
"""

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
from core.engine import RATING_LABEL, Session
from core.srs import rating_to_quality, schedule
from core.worker import run_async
from .theme import (ACCENT, BLUE, CARD, FONT_NAME, GREEN, MUTED, RED, TEXT,
                    YELLOW, AppLabel, AppSpinner, AppSpinnerOption, AppTextInput,
                    PrimaryButton, TitleLabel, rgba)
from .widgets import ComboBadge, TypingBoard

MODES = [("句子模式", "sentence"), ("单词模式", "word"),
         ("默写模式", "dictation"), ("拼读模式（听音拼写）", "phonics")]

RATING_COLOR = {5: GREEN, 4: ACCENT, 3: YELLOW, 0: RED}


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
        for text, cb in [("讲解本句", lambda: self.screen._ai_explain(self)),
                         ("翻译本句", lambda: self.screen._ai_translate(self)),
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
        self._mode = App.get_running_app().ctx.config.get("mode", "sentence")
        self._build()
        Clock.schedule_interval(self._tick, 0.5)

    @property
    def ctx(self):
        return App.get_running_app().ctx

    # ------------------------------------------------------------ UI
    def _build(self):
        root = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(8))

        # 顶部：课程 / 模式 / 分数 / 时间 / 连击
        top = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(6))
        self.course_spin = AppSpinner(text="选择课程", size_hint_x=0.46)
        self.course_spin.bind(text=self._on_course_picked)
        self.mode_spin = AppSpinner(
            text=dict((v, k) for k, v in MODES).get(
                self.ctx.config.get("mode", "sentence"), "句子模式"),
            values=[m[0] for m in MODES], size_hint_x=0.34)
        self.mode_spin.bind(text=self._on_mode_picked)
        self.score_lbl = AppLabel(text="0", size_hint_x=None, width=dp(56),
                                  font_size=sp(18), bold=True, color=rgba(GREEN),
                                  halign="right")
        self.time_lbl = AppLabel(text="00:00", size_hint_x=None, width=dp(56),
                                 font_size=sp(13), color=rgba(MUTED), halign="right")
        top.add_widget(self.course_spin)
        top.add_widget(self.mode_spin)
        top.add_widget(self.score_lbl)
        top.add_widget(self.time_lbl)
        root.add_widget(top)

        combo_row = BoxLayout(size_hint_y=None, height=dp(64))
        combo_row.add_widget(Widget())
        self.combo = ComboBadge()
        combo_row.add_widget(self.combo)
        root.add_widget(combo_row)

        # 中文提示
        self.zh_lbl = AppLabel(text="像玩游戏一样，用句子学英语", font_size=sp(20),
                               bold=True, halign="center", size_hint_y=None,
                               height=dp(56), color=rgba(TEXT))
        root.add_widget(self.zh_lbl)

        self.note_lbl = AppLabel(text="", font_size=sp(12), color=rgba(MUTED),
                                 halign="center", size_hint_y=None, height=dp(20))
        root.add_widget(self.note_lbl)

        self.rating_lbl = AppLabel(text="", font_size=sp(22), bold=True,
                                   halign="center", size_hint_y=None, height=dp(34))
        root.add_widget(self.rating_lbl)

        # 打字板
        board_box = BoxLayout(size_hint_y=None, height=dp(170))
        self.board = TypingBoard()
        board_box.add_widget(self.board)
        self.board.bind(height=lambda o, v: setattr(board_box, "height", v))
        self.board.focus_callback = self._focus_input
        self.board_area = board_box
        root.add_widget(board_box)

        # 隐藏输入框：唤起软键盘并接收文本
        self.input = TextInput(size_hint=(1, None), height=dp(1), opacity=0,
                               multiline=False, font_name=FONT_NAME,
                               keyboard_suggestions=False, input_type="text")
        self.input.bind(text=self._on_text)
        self.input.bind(on_text_validate=lambda w: self._manual_next())
        root.add_widget(self.input)

        self.focus_btn = PrimaryButton(
            text="点击此处开始输入（唤起键盘）", size_hint_y=None, height=dp(46),
            bg=rgba(BLUE))
        self.focus_btn.bind(on_release=lambda b: self._focus_input())
        root.add_widget(self.focus_btn)

        # 进度
        self.progress = ProgressBar(size_hint_y=None, height=dp(6), max=100)
        root.add_widget(self.progress)
        self.progress_lbl = AppLabel(text="", font_size=sp(11), color=rgba(MUTED),
                                     size_hint_y=None, height=dp(18))
        root.add_widget(self.progress_lbl)

        # 操作条
        bar = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(6))
        for text, cb in [("朗读", self._speak), ("重来", self._retry),
                         ("跳过", self._skip), ("下一句", self._manual_next),
                         ("AI", self._open_ai)]:
            b = PrimaryButton(text=text)
            b.bind(on_release=cb)
            bar.add_widget(b)
        root.add_widget(bar)

        self.add_widget(root)

    # ------------------------------------------------------------ 数据
    def refresh_courses(self):
        courses = db.list_courses()
        self.course_ids = [c["id"] for c in courses]
        self.course_spin.values = [c["title"] for c in courses]
        if courses and self.course_spin.text not in self.course_spin.values:
            self.course_spin.text = courses[0]["title"]

    def _current_cid(self):
        i = (self.course_spin.values.index(self.course_spin.text)
             if self.course_spin.text in self.course_spin.values else -1)
        return self.course_ids[i] if 0 <= i < len(self.course_ids) else None

    def _on_course_picked(self, spinner, text):
        cid = self._current_cid()
        if cid is None:
            return
        app = App.get_running_app()
        n = int(self.ctx.config.get("lesson_size", 10)) or 10
        rows = db.due_course_cards(cid, n)
        if not rows:
            rows = db.list_sentences(cid)[:n]
        course = db.get_course(cid)
        self.start([dict(r) for r in rows], course["title"] if course else "练习")

    def _on_mode_picked(self, spinner, text):
        mode = dict(MODES).get(text, "sentence")
        self.ctx.config.set("mode", mode)
        self.mode = mode
        if self.session and self.session.state:
            self._render()

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
            name = dict((v, k) for k, v in MODES).get(mode, "句子模式")
            self.mode_spin.text = name
        self._switching = True   # 清空输入框期间屏蔽 _on_text
        self.session = Session(list(sentences), title)
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
        if self._mode == "phonics" or (
                self.ctx.config.get("auto_tts") and self.ctx.config.get("tts_enabled")):
            self._speak()
        Clock.schedule_once(lambda dt: self._focus_input(), 0.15)

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
        if self._mode == "phonics" and note.count("｜") == 2:
            note = "%s｜%s" % (note.split("｜")[1], note.split("｜")[2])
        self.note_lbl.text = note or ""
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
        self.input.focus = True

    # ------------------------------------------------------------ 输入
    def _on_text(self, instance, value):
        if getattr(self, "_switching", False):
            return   # 程序性清空/切换，非用户输入
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

        color = RATING_COLOR.get(res["rating"], TEXT)
        self.rating_lbl.text = ("[color=%s]%s[/color]  [color=%s]%.0f WPM · 准确率 %.0f%%[/color]"
                                % (color, RATING_LABEL[res["rating"]], MUTED,
                                   res["wpm"], res["accuracy"]))
        self._render()
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
        self.progress.value = 100
        App.get_running_app().refresh_all()
        self._show_summary(summary)

    def _show_summary(self, s):
        box = BoxLayout(orientation="vertical", padding=dp(16), spacing=dp(10))
        box.add_widget(TitleLabel(text="关卡完成！"))
        for name, val, color in [("得分", str(s["score"]), GREEN),
                                 ("准确率", "%.1f%%" % s["accuracy"], ACCENT),
                                 ("速度", "%.0f WPM" % s["wpm"], TEXT),
                                 ("最大连击", "x%d" % s["combo_max"], YELLOW),
                                 ("Perfect", "%d / %d" % (s["perfect"], s["sentences"]), GREEN)]:
            box.add_widget(AppLabel(text="[color=%s]%s[/color]：%s" % (color, name, val),
                                    font_size=sp(16), size_hint_y=None, height=dp(28)))
        box.add_widget(AppLabel(text="用时 %.1f 分钟 · %s" % (s["elapsed"] / 60.0, s["title"]),
                                font_size=sp(12), color=rgba(MUTED),
                                size_hint_y=None, height=dp(24)))
        bar = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(8))
        again = PrimaryButton(text="再来一关", bg=rgba(BLUE))
        back = PrimaryButton(text="返回")
        bar.add_widget(again)
        bar.add_widget(back)
        box.add_widget(bar)

        popup = Popup(title="", content=box, size_hint=(0.9, 0.7),
                      background="", background_color=rgba(CARD),
                      separator_height=0)
        again.bind(on_release=lambda b: (popup.dismiss(),
                                         self._on_course_picked(None, self.course_spin.text)))
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
