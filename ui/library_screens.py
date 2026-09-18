# -*- coding: utf-8 -*-
"""课程库 / 今日复习 / 统计 / 导入。"""

from kivy.app import App
from kivy.clock import Clock
from kivy.metrics import dp, sp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.popup import Popup
from kivy.uix.progressbar import ProgressBar
from kivy.uix.screenmanager import Screen
from kivy.uix.scrollview import ScrollView
from kivy.uix.widget import Widget

from core import db
from core.srs import today_str
from core.worker import run_async
from .theme import (ACCENT, BLUE, BORDER, CARD, GREEN, MUTED, RED, TEXT,
                    YELLOW, AppLabel, AppSpinner, AppTextInput, PrimaryButton,
                    TitleLabel, rgba)
from .widgets import BarChart, StatCard

RATING_TEXT = {5: "Perfect", 4: "Great", 3: "Good", 0: "Again"}


def _row_card(rows, on_open=None, open_text="开始闯关", on_delete=None):
    """一行课程卡片（点击进入关卡选择；on_delete 时右侧显示删除按钮）。

    高度按内部内容精确计算（上 26 + 下 28 + 间距 4 + 上下内边距 24 = 82），
    避免内容溢出卡片、与相邻元素视觉重叠。
    """
    top_h = dp(26)
    bot_h = dp(28)
    pad_v = dp(12)
    box = BoxLayout(orientation="vertical", padding=[dp(12), pad_v],
                    spacing=dp(4), size_hint_y=None,
                    height=top_h + bot_h + dp(4) + pad_v * 2)
    from kivy.graphics import Color, Rectangle, RoundedRectangle
    with box.canvas.before:
        Color(*rgba(CARD))
        box._rect = RoundedRectangle(pos=box.pos, size=box.size, radius=[dp(12)])
        # 左侧彩色条（直接画在背景 canvas 里，不占用布局位）
        Color(*rgba(ACCENT, 0.9))
        box._bar = Rectangle(pos=(box.x + dp(2), box.y + dp(2)),
                             size=(dp(3), box.height - dp(4)))
    box.bind(pos=lambda o, v: (setattr(o._rect, "pos", v),
                               setattr(o._bar, "pos", (v[0] + dp(2), v[1] + dp(2)))),
             size=lambda o, v: (setattr(o._rect, "size", v),
                                setattr(o._bar, "size", (dp(3), v[1] - dp(4)))))
    top = BoxLayout(size_hint_y=None, height=top_h)
    top.add_widget(AppLabel(text="[b]%s[/b]" % rows[0], font_size=sp(15),
                            halign="left", text_size=(dp(200), None)))
    top.add_widget(AppLabel(text=rows[1], font_size=sp(12), color=rgba(MUTED),
                            size_hint_x=None, width=dp(52), halign="right"))
    if on_delete:
        del_btn = PrimaryButton(text="删除", size_hint_x=None, width=dp(52),
                                font_size=sp(12), bg=rgba(RED))
        del_btn.bind(on_release=lambda x: on_delete())
        top.add_widget(del_btn)
    box.add_widget(top)
    bottom = BoxLayout(size_hint_y=None, height=bot_h, spacing=dp(6))
    bottom.add_widget(AppLabel(text="%s 关 · 待复习 %s" % (rows[2], rows[3]),
                               font_size=sp(12), color=rgba(MUTED), halign="left"))
    if on_open:
        b = PrimaryButton(text=open_text, size_hint_x=None, width=dp(92),
                          font_size=sp(12), bg=rgba(BLUE))
        b.bind(on_release=lambda x: on_open())
        bottom.add_widget(b)
    box.add_widget(bottom)
    return box


class LessonPopup(Popup):
    """课程的关卡选择：圆点按钮 + 星级 + 逐关解锁（多邻国式）。"""

    def __init__(self, course, app, **kw):
        Popup.__init__(self, title="", separator_height=0, **kw)
        self.size_hint = (0.9, 0.85)
        self.background = ""
        self.background_color = rgba("#141922")
        self.course = course
        self.app = app

        n_items = db.count_sentences(course["id"])
        n_lessons = max(1, -(-n_items // 10))
        stars = db.lesson_stars(course["id"])

        root = BoxLayout(orientation="vertical", padding=dp(14), spacing=dp(10))
        head = BoxLayout(size_hint_y=None, height=dp(36))
        head.add_widget(AppLabel(text="[b]%s[/b]" % course["title"],
                                 font_size=sp(17), halign="left"))
        close = PrimaryButton(text="关闭", size_hint_x=None, width=dp(76),
                              font_size=sp(13), bg=rgba(CARD))
        close.bind(on_release=lambda x: self.dismiss())
        head.add_widget(close)
        root.add_widget(head)
        total_stars = sum(stars.values())
        root.add_widget(AppLabel(
            text="共 %d 关 · 已获得 [color=%s]★%d[/color] · 通过上一关解锁下一关"
                 % (n_lessons, YELLOW, total_stars),
            font_size=sp(12), color=rgba(MUTED), size_hint_y=None,
            height=dp(20), halign="left"))

        sv = ScrollView()
        grid = GridLayout(cols=3, spacing=dp(12), size_hint_y=None,
                          padding=dp(6))
        grid.bind(minimum_height=grid.setter("height"))
        unlocked_next = True
        for i in range(n_lessons):
            got = stars.get(i, 0)
            is_open = unlocked_next
            if got > 0:
                unlocked_next = True
            elif is_open and got == 0 and i > 0 and stars.get(i - 1, 0) == 0:
                is_open = False
            if got == 0 and i > 0 and stars.get(i - 1, 0) == 0:
                is_open = False

            cell = BoxLayout(orientation="vertical", spacing=dp(2),
                             size_hint_y=None, height=dp(96))
            label = AppLabel(
                text=("[color=%s]%s[/color]" % (YELLOW, "*" * got)
                      if got else ("[color=%s]?[/color]" % MUTED
                                   if not is_open else
                                   "[color=%s]第 %d 关[/color]" % (TEXT, i + 1))),
                font_size=sp(12), size_hint_y=None, height=dp(18),
                halign="center")
            if got == 0 and is_open:
                label.text = "[color=%s]第 %d 关[/color]" % (TEXT, i + 1)
            btn = PrimaryButton(
                text=("★%d" % got) if got else ("锁" if not is_open
                                                else str(i + 1)),
                font_size=sp(20),
                bg=rgba(GREEN if got == 3 else BLUE if is_open else "#20262f"),
                size_hint_y=None, height=dp(64))
            btn.disabled = not is_open
            if is_open:
                btn.bind(on_release=lambda x, idx=i: self._go(idx))
            cell.add_widget(btn)
            cell.add_widget(label)
            grid.add_widget(cell)
        sv.add_widget(grid)
        root.add_widget(sv)
        self.content = root

    def _go(self, idx):
        self.dismiss()
        self.app.start_lesson(self.course["id"], idx)


def _collapse_header(title, count, expanded, on_toggle, color=ACCENT,
                     indent=0, size=15):
    """可点击的折叠标题行：显示 ▸/▾ + 名称 + 数量。"""
    box = BoxLayout(size_hint_y=None, height=dp(42), padding=[dp(10 + indent), dp(4)])
    from kivy.graphics import Color, RoundedRectangle
    with box.canvas.before:
        Color(*rgba(CARD if indent == 0 else "#1b2130"))
        box._rect = RoundedRectangle(pos=box.pos, size=box.size, radius=[dp(10)])
    box.bind(pos=lambda o, v: setattr(o._rect, "pos", v),
             size=lambda o, v: setattr(o._rect, "size", v))
    # 折叠指示用 ASCII 的 -/+ ，避免主字体缺 ▸▾ 等符号导致显示方块
    mark = "[-]" if expanded else "[+]"
    box.add_widget(AppLabel(
        text="[b]%s %s[/b]" % (mark, title), font_size=sp(size),
        color=rgba(color), halign="left"))
    box.add_widget(AppLabel(
        text="%d 门" % count, font_size=sp(12), color=rgba(MUTED),
        size_hint_x=None, width=dp(56), halign="right"))
    box.bind(on_touch_down=lambda w, t: (
        on_toggle() if w.collide_point(*t.pos) else None))
    return box


class CoursesScreen(Screen):
    """课程库：大类 → 小类 → 课程，可折叠浏览。"""

    def __init__(self, **kw):
        Screen.__init__(self, **kw)
        self._expanded = {"cat": set(), "sub": set()}
        root = BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(8))
        head = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(6))
        head.add_widget(TitleLabel(text="课程库"))
        head.add_widget(Widget())
        ai_b = PrimaryButton(text="AI 生成课程", size_hint_x=None, width=dp(104),
                             font_size=sp(12), bg=rgba(BLUE))
        ai_b.bind(on_release=lambda x: self._ai_generate())
        head.add_widget(ai_b)
        b = PrimaryButton(text="刷新", size_hint_x=None, width=dp(66),
                          font_size=sp(12))
        b.bind(on_release=lambda x: self.refresh())
        head.add_widget(b)
        root.add_widget(head)

        self.sv = ScrollView(scroll_type=["bars", "content"], bar_width=dp(6))
        self.grid = GridLayout(cols=1, spacing=dp(8), size_hint_y=None, padding=dp(4))
        self.grid.bind(minimum_height=self.grid.setter("height"))
        self.sv.add_widget(self.grid)
        root.add_widget(self.sv)
        self.add_widget(root)

    def refresh(self):
        self.grid.clear_widgets()
        groups = db.grouped_courses()
        for cat, subs in groups.items():
            n_courses = sum(len(v) for v in subs.values())
            cat_open = cat in self._expanded["cat"]
            self.grid.add_widget(_collapse_header(
                cat, n_courses, cat_open,
                lambda c=cat: self._toggle("cat", c), color=ACCENT, size=16))
            if not cat_open:
                continue
            # 只有一个小类时省略小类层，直接把课程铺开（减少层级）
            single_sub = len(subs) == 1
            for sub, courses in subs.items():
                if not single_sub:
                    sub_key = "%s/%s" % (cat, sub)
                    sub_open = sub_key in self._expanded["sub"]
                    self.grid.add_widget(_collapse_header(
                        sub, len(courses), sub_open,
                        lambda k=sub_key: self._toggle("sub", k),
                        color=YELLOW, indent=12, size=14))
                    if not sub_open:
                        continue
                for c in courses:
                    self.grid.add_widget(self._course_card(c))

    def _course_card(self, c):
        n = db.count_sentences(c["id"])
        due = db.due_count(c["id"])
        card = _row_card([c["title"], c["level"], n, due],
                         on_open=lambda cc=dict(c): self._open(cc),
                         on_delete=lambda cc=dict(c): self._confirm_delete(cc))
        card.bind(on_touch_down=lambda w, t, cc=dict(c):
                  self._open(cc) if w.collide_point(*t.pos) and t.is_double_tap
                  else None)
        return card

    def _confirm_delete(self, course):
        """确认后删除课程（连同其句子、卡片、复习记录）。"""
        content = BoxLayout(orientation="vertical", spacing=dp(10),
                            padding=dp(12))
        content.add_widget(AppLabel(
            text="确定删除课程「[b]%s[/b]」吗？\n该课程的练习与复习记录也会一并删除。"
                 % course["title"], font_size=sp(14), halign="left"))
        btns = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(8))
        cancel = PrimaryButton(text="取消", bg=rgba(CARD))
        ok = PrimaryButton(text="删除", bg=rgba(RED))
        btns.add_widget(cancel)
        btns.add_widget(ok)
        content.add_widget(btns)
        pop = Popup(title="", separator_height=0, content=content,
                    size_hint=(0.86, 0.36), background="",
                    background_color=rgba("#141922"))
        cancel.bind(on_release=lambda x: pop.dismiss())

        def _do_delete(*a):
            db.delete_course(course["id"])
            pop.dismiss()
            App.get_running_app().refresh_all()
            self.refresh()
        ok.bind(on_release=_do_delete)
        pop.open()

    def _toggle(self, kind, key):
        s = self._expanded[kind]
        if key in s:
            s.discard(key)
        else:
            s.add(key)
        self.refresh()

    def _open(self, course):
        LessonPopup(course, App.get_running_app()).open()

    # ------------------------------------------------------- AI 生成课程
    def _ai_generate(self):
        ctx = App.get_running_app().ctx
        if not ctx.ai.enabled:
            self._toast("请先在「设置」中配置 AI Key（推荐免费的 Agnes）")
            return
        content = BoxLayout(orientation="vertical", spacing=dp(8), padding=dp(12))
        content.add_widget(AppLabel(
            text="描述你想学的主题，AI 会自动生成一门课程。",
            font_size=sp(12), color=rgba(MUTED), size_hint_y=None, height=dp(22)))
        topic = AppTextInput(hint_text="主题，如：机场值机 / 小学动物词汇",
                             multiline=False, size_hint_y=None, height=dp(40))
        content.add_widget(topic)
        # 课程类型：句子 / 词汇
        trow = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(8))
        trow.add_widget(AppLabel(text="类型", font_size=sp(13),
                                 size_hint_x=None, width=dp(40)))
        kind = AppSpinner(text="句子课程", values=["句子课程", "词汇课程"],
                          size_hint_x=None, width=dp(104))
        trow.add_widget(kind)
        trow.add_widget(AppLabel(text="难度", font_size=sp(13),
                                 size_hint_x=None, width=dp(40)))
        level = AppSpinner(text="初级", values=["初级", "中级", "高级"],
                           size_hint_x=None, width=dp(84))
        trow.add_widget(level)
        trow.add_widget(Widget())
        content.add_widget(trow)
        row = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(8))
        title_in = AppTextInput(hint_text="课程名称（可留空）", multiline=False)
        row.add_widget(title_in)
        content.add_widget(row)
        crow = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(8))
        self._cnt_lbl = AppLabel(text="数量", font_size=sp(13),
                                 size_hint_x=None, width=dp(40))
        crow.add_widget(self._cnt_lbl)
        cnt = AppTextInput(text="20", multiline=False, input_filter="int",
                           size_hint_x=None, width=dp(80))
        crow.add_widget(cnt)
        crow.add_widget(AppLabel(text="5 ~ 5000", font_size=sp(12),
                                 color=rgba(MUTED)))
        crow.add_widget(Widget())
        content.add_widget(crow)

        self._ai_status = AppLabel(text="", font_size=sp(12),
                                   color=rgba(MUTED), size_hint_y=None,
                                   height=dp(22))
        content.add_widget(self._ai_status)
        btns = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(8))
        cancel = PrimaryButton(text="取消", bg=rgba(CARD))
        gen = PrimaryButton(text="生成", bg=rgba(BLUE))
        btns.add_widget(cancel)
        btns.add_widget(gen)
        content.add_widget(btns)
        pop = Popup(title="", separator_height=0, content=content,
                    size_hint=(0.94, 0.56), background="",
                    background_color=rgba("#141922"))
        cancel.bind(on_release=lambda x: pop.dismiss())

        def _sync_cnt(*a):
            self._cnt_lbl.text = "词汇数" if kind.text == "词汇课程" else "句子数"
        kind.bind(text=_sync_cnt)

        def _run(*a):
            t = topic.text.strip()
            if not t:
                self._set_ai_status("[color=%s]请填写主题[/color]" % RED)
                return
            try:
                n = int(cnt.text or "20")
            except ValueError:
                n = 20
            n = max(5, min(5000, n))
            is_vocab = kind.text == "词汇课程"
            unit = "词汇" if is_vocab else "句子"
            self._set_ai_status(
                "[color=%s]AI 生成中… 已生成 0/%d 个%s[/color]" % (MUTED, n, unit))
            gen.disabled = True

            def _progress(done, total):
                # 工作线程回调：切到主线程更新进度
                Clock.schedule_once(
                    lambda dt: self._set_ai_status(
                        "[color=%s]AI 生成中… 已生成 %d/%d 个%s[/color]"
                        % (MUTED, done, total, unit)), 0)

            fn = ctx.ai.generate_vocab if is_vocab else ctx.ai.generate_course
            run_async(fn,
                      lambda items: self._on_ai_done(
                          items, t, title_in.text.strip(),
                          level.text, is_vocab, pop),
                      lambda msg: self._on_ai_fail(msg, gen),
                      t, level.text, n,
                      progress=_progress)
        gen.bind(on_release=_run)
        pop.open()

    def _set_ai_status(self, text):
        try:
            self._ai_status.text = text
            self._ai_status.markup = True
        except Exception:
            pass

    def _on_ai_done(self, items, topic, title, level, is_vocab, pop):
        if not items:
            self._set_ai_status("[color=%s]AI 未生成内容，请重试[/color]" % RED)
            return
        title = title or ("%s（AI）" % topic)
        kind_name = "词汇" if is_vocab else "句子"
        cid = db.add_course(title, "AI 生成%s：%s" % (kind_name, topic),
                            level, "custom")
        if is_vocab:
            # 词汇：(word, zh, note)
            db.add_sentences(cid, [(w, zh, note) for w, zh, note in items])
        else:
            db.add_sentences(cid, [(en, zh, "") for en, zh in items])
        pop.dismiss()
        App.get_running_app().refresh_all()
        self.refresh()
        self._toast("已生成%s课程「%s」，共 %d 个"
                    % (kind_name, title, len(items)))

    def _on_ai_fail(self, msg, gen):
        self._set_ai_status("[color=%s]%s[/color]" % (RED, msg))
        gen.disabled = False

    def _toast(self, text):
        content = BoxLayout(padding=dp(14))
        content.add_widget(AppLabel(text=text, font_size=sp(14), halign="center"))
        pop = Popup(title="", separator_height=0, content=content,
                    size_hint=(0.8, 0.24), background="",
                    background_color=rgba("#141922"))
        pop.open()
        Clock.schedule_once(lambda dt: pop.dismiss(), 1.8)


class ReviewScreen(Screen):
    def __init__(self, **kw):
        Screen.__init__(self, **kw)
        root = BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(8))
        head = BoxLayout(size_hint_y=None, height=dp(40))
        head.add_widget(TitleLabel(text="今日复习"))
        self.count_lbl = AppLabel(text="", font_size=sp(13), color=rgba(GREEN),
                                  size_hint_x=None, width=dp(120))
        head.add_widget(self.count_lbl)
        head.add_widget(Widget())
        b = PrimaryButton(text="开始复习", size_hint_x=None, width=dp(110), bg=rgba(BLUE))
        b.bind(on_release=lambda x: self._start())
        head.add_widget(b)
        root.add_widget(head)
        root.add_widget(AppLabel(
            text="系统按遗忘曲线自动安排复习时间——忘了的词，它比你先想起来。",
            font_size=sp(12), color=rgba(MUTED), size_hint_y=None, height=dp(22)))

        self.sv = ScrollView(scroll_type=["bars", "content"], bar_width=dp(6))
        self.grid = GridLayout(cols=1, spacing=dp(6), size_hint_y=None, padding=dp(4))
        self.grid.bind(minimum_height=self.grid.setter("height"))
        self.sv.add_widget(self.grid)
        root.add_widget(self.sv)
        self.add_widget(root)
        self.rows = []

    def refresh(self):
        self.rows = db.all_due_sentences(200)
        self.grid.clear_widgets()
        for r in self.rows:
            box = BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(2),
                            size_hint_y=None, height=dp(58))
            from kivy.graphics import Color, RoundedRectangle
            with box.canvas.before:
                Color(*rgba(CARD))
                box._rect = RoundedRectangle(pos=box.pos, size=box.size, radius=[dp(10)])
            box.bind(pos=lambda o, v: setattr(o._rect, "pos", v),
                     size=lambda o, v: setattr(o._rect, "size", v))
            box.add_widget(AppLabel(text=r["en"], font_size=sp(14), halign="left",
                                    text_size=(dp(420), None)))
            box.add_widget(AppLabel(text="%s · %s" % (r["zh"], r["course_title"]),
                                    font_size=sp(11), color=rgba(MUTED), halign="left",
                                    text_size=(dp(420), None)))
            self.grid.add_widget(box)
        self.count_lbl.text = "待复习 %d 句" % len(self.rows)

    def _start(self):
        if not self.rows:
            self.refresh()
        if not self.rows:
            return
        n = int(App.get_running_app().ctx.config.get("lesson_size", 10)) or 10
        App.get_running_app().start_sentences([dict(r) for r in self.rows[:n]], "今日复习")


class StatsScreen(Screen):
    def __init__(self, **kw):
        Screen.__init__(self, **kw)
        root = BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(8))
        head = BoxLayout(size_hint_y=None, height=dp(40))
        head.add_widget(TitleLabel(text="学习统计"))
        head.add_widget(Widget())
        b = PrimaryButton(text="刷新", size_hint_x=None, width=dp(80))
        b.bind(on_release=lambda x: self.refresh())
        head.add_widget(b)
        root.add_widget(head)

        self.cards_box = BoxLayout(size_hint_y=None, height=dp(92), spacing=dp(6))
        self.c_reviews = StatCard(title="累计句数", value="0", color=GREEN)
        self.c_acc = StatCard(title="准确率", value="0%", color=ACCENT)
        self.c_wpm = StatCard(title="WPM", value="0", color=TEXT)
        self.c_combo = StatCard(title="最高连击", value="0", color=YELLOW)
        for c in (self.c_reviews, self.c_acc, self.c_wpm, self.c_combo):
            self.cards_box.add_widget(c)
        root.add_widget(self.cards_box)

        root.add_widget(AppLabel(text="今日目标", font_size=sp(13),
                                 size_hint_y=None, height=dp(22)))
        self.goal_bar = ProgressBar(size_hint_y=None, height=dp(8), max=100)
        root.add_widget(self.goal_bar)
        self.goal_lbl = AppLabel(text="", font_size=sp(12), color=rgba(MUTED),
                                 size_hint_y=None, height=dp(22))
        root.add_widget(self.goal_lbl)

        root.add_widget(AppLabel(text="近 30 天学习时长", font_size=sp(12),
                                 color=rgba(MUTED), size_hint_y=None, height=dp(20)))
        self.chart = BarChart()
        root.add_widget(self.chart)

        root.add_widget(AppLabel(text="最近练习记录", font_size=sp(12),
                                 color=rgba(MUTED), size_hint_y=None, height=dp(20)))
        self.sv = ScrollView(scroll_type=["bars", "content"], bar_width=dp(6))
        self.grid = GridLayout(cols=1, spacing=dp(4), size_hint_y=None, padding=dp(4))
        self.grid.bind(minimum_height=self.grid.setter("height"))
        self.sv.add_widget(self.grid)
        root.add_widget(self.sv)
        self.add_widget(root)

    def refresh(self):
        s = db.overall_stats()
        self.c_reviews.value = str(s["reviews"])
        self.c_acc.value = "%.1f%%" % s["avg_accuracy"]
        self.c_wpm.value = "%.0f" % s["avg_wpm"]
        self.c_combo.value = "x%d" % s["max_combo"]

        today = db.get_daily()
        goal = int(App.get_running_app().ctx.config.get("daily_goal_minutes", 15)) or 15
        minutes = today["seconds"] / 60.0
        self.goal_bar.value = min(100, 100.0 * minutes / goal)
        self.goal_lbl.text = "今日 %.1f / %d 分钟 · 练习 %d 句 · 最高连击 %d" % (
            minutes, goal, today["sentences"], today["combo_max"])
        self.chart.set_data(db.recent_daily(30))

        conn = db.connect()
        rows = conn.execute(
            "SELECT r.*, s.en FROM reviews r JOIN sentences s ON s.id=r.sentence_id "
            "ORDER BY r.id DESC LIMIT 20").fetchall()
        conn.close()
        self.grid.clear_widgets()
        for r in rows:
            self.grid.add_widget(AppLabel(
                text="%s　[color=%s]%s[/color]　%.0f WPM　%.0f%%" % (
                    r["en"][:26], GREEN, RATING_TEXT.get(r["rating"], "-"),
                    r["wpm"], r["accuracy"]),
                font_size=sp(12), size_hint_y=None, height=dp(24), halign="left",
                text_size=(dp(520), None)))


class ImportScreen(Screen):
    def __init__(self, **kw):
        Screen.__init__(self, **kw)
        self.rows = []
        root = BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(8))
        root.add_widget(TitleLabel(text="导入内容"))
        root.add_widget(AppLabel(
            text="教材课文、歌词、TED 演讲、考题——粘贴进来，AI 自动拆句并翻译。",
            font_size=sp(12), color=rgba(MUTED), size_hint_y=None, height=dp(30)))

        row1 = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(6))
        self.title_edit = AppTextInput(hint_text="课程名称", multiline=False)
        row1.add_widget(self.title_edit)
        self.level_spin = AppSpinner(text="中级", values=["初级", "中级", "高级"],
                                     size_hint_x=None, width=dp(90))
        row1.add_widget(self.level_spin)
        root.add_widget(row1)

        self.text = AppTextInput(hint_text="在此粘贴英文原文…", size_hint_y=None,
                                 height=dp(120))
        root.add_widget(self.text)

        row2 = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(6))
        b1 = PrimaryButton(text="按标点拆分")
        b1.bind(on_release=lambda x: self._local_split())
        b2 = PrimaryButton(text="AI 智能拆句", bg=rgba(BLUE))
        b2.bind(on_release=lambda x: self._ai_split())
        row2.add_widget(b1)
        row2.add_widget(b2)
        root.add_widget(row2)

        self.progress = ProgressBar(size_hint_y=None, height=dp(4), max=100)
        self.progress.opacity = 0
        root.add_widget(self.progress)
        self.status_lbl = AppLabel(text="", font_size=sp(12), color=rgba(MUTED),
                                   size_hint_y=None, height=dp(22))
        root.add_widget(self.status_lbl)

        row3 = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(6))
        self.en_edit = AppTextInput(hint_text="英文句子", multiline=False)
        self.zh_edit = AppTextInput(hint_text="中文（可留空）", multiline=False,
                                    size_hint_x=0.7)
        add = PrimaryButton(text="添加", size_hint_x=None, width=dp(70))
        add.bind(on_release=lambda x: self._add_row())
        row3.add_widget(self.en_edit)
        row3.add_widget(self.zh_edit)
        row3.add_widget(add)
        root.add_widget(row3)

        self.sv = ScrollView(scroll_type=["bars", "content"], bar_width=dp(6))
        self.grid = GridLayout(cols=1, spacing=dp(4), size_hint_y=None, padding=dp(4))
        self.grid.bind(minimum_height=self.grid.setter("height"))
        self.sv.add_widget(self.grid)
        root.add_widget(self.sv)

        row4 = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(8))
        clr = PrimaryButton(text="清空")
        clr.bind(on_release=lambda x: self._clear())
        save = PrimaryButton(text="保存为课程", bg=rgba(GREEN))
        save.bind(on_release=lambda x: self._save())
        row4.add_widget(clr)
        row4.add_widget(save)
        root.add_widget(row4)
        self.add_widget(root)

    def _status(self, text, color=MUTED):
        self.status_lbl.text = "[color=%s]%s[/color]" % (color, text)

    def _local_split(self):
        import re
        text = re.sub(r"\s+", " ", self.text.text).strip()
        pairs = [(p.strip(), "") for p in re.split(r"(?<=[.!?。!?；;])\s+", text)
                 if len(p.strip()) >= 3]
        if not pairs:
            self._status("没有解析到句子", RED)
            return
        self._fill(pairs)
        self._status("已拆出 %d 句（未翻译，可让 AI 补充）" % len(pairs), GREEN)

    def _ai_split(self):
        raw = self.text.text.strip()
        if not raw:
            self._status("请先粘贴英文内容", RED)
            return
        ctx = App.get_running_app().ctx
        if not ctx.ai.enabled:
            self._status("请先在「设置」中配置 AI API Key", RED)
            return
        self.progress.opacity = 1
        self._status("AI 正在拆句并翻译…", MUTED)
        run_async(ctx.ai.split, self._on_split, self._on_split_fail,
                  raw, self.title_edit.text.strip())

    def _on_split(self, pairs):
        self.progress.opacity = 0
        if not pairs:
            self._status("AI 没有解析出句子", RED)
            return
        self._fill(pairs)
        self._status("AI 拆出 %d 句，确认后保存" % len(pairs), GREEN)

    def _on_split_fail(self, msg):
        self.progress.opacity = 0
        self._status(msg, RED)

    def _fill(self, pairs):
        self.grid.clear_widgets()
        self.rows = list(pairs)
        for en, zh in self.rows:
            box = BoxLayout(size_hint_y=None, height=dp(28), spacing=dp(6))
            e = AppTextInput(text=en, multiline=False, font_size=sp(12))
            z = AppTextInput(text=zh, multiline=False, font_size=sp(12), size_hint_x=0.7)
            box.add_widget(e)
            box.add_widget(z)
            self.grid.add_widget(box)

    def _add_row(self):
        en = self.en_edit.text.strip()
        if not en:
            return
        self.rows.append((en, self.zh_edit.text.strip()))
        self.en_edit.text = ""
        self.zh_edit.text = ""
        self._fill(self.rows)

    def _clear(self):
        self.rows = []
        self.grid.clear_widgets()

    def _save(self):
        items = []
        for i, box in enumerate(reversed(self.grid.children)):
            e, z = box.children[1], box.children[0]
            if e.text.strip():
                items.append((e.text.strip(), z.text.strip(), ""))
        if not items:
            self._status("表格是空的，先添加句子吧", RED)
            return
        title = self.title_edit.text.strip() or ("自定义课程 %d" % len(db.list_courses()))
        cid = db.add_course(title, "自定义导入", self.level_spin.text, "custom")
        db.add_sentences(cid, items)
        self._status("已保存，共 %d 句" % len(items), GREEN)
        self._clear()
        self.text.text = ""
        self.title_edit.text = ""
        App.get_running_app().refresh_all()


_ = today_str, Popup, AppSpinner, BORDER
