# -*- coding: utf-8 -*-
"""课程库 / 今日复习 / 统计 / 导入。"""

from kivy.app import App
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


def _row_card(rows, on_open=None, open_text="开始练习"):
    """一行课程卡片。"""
    box = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(4),
                    size_hint_y=None, height=dp(74))
    from kivy.graphics import Color, RoundedRectangle
    with box.canvas.before:
        Color(*rgba(CARD))
        box._rect = RoundedRectangle(pos=box.pos, size=box.size, radius=[dp(12)])
    box.bind(pos=lambda o, v: setattr(o._rect, "pos", v),
             size=lambda o, v: setattr(o._rect, "size", v))
    top = BoxLayout(size_hint_y=None, height=dp(26))
    top.add_widget(AppLabel(text="[b]%s[/b]" % rows[0], font_size=sp(15),
                            halign="left", text_size=(dp(240), None)))
    top.add_widget(AppLabel(text=rows[1], font_size=sp(12), color=rgba(MUTED),
                            size_hint_x=None, width=dp(60), halign="right"))
    box.add_widget(top)
    bottom = BoxLayout(size_hint_y=None, height=dp(28), spacing=dp(6))
    bottom.add_widget(AppLabel(text="共 %s 句 · 待复习 %s" % (rows[2], rows[3]),
                               font_size=sp(12), color=rgba(MUTED), halign="left"))
    if on_open:
        b = PrimaryButton(text=open_text, size_hint_x=None, width=dp(92),
                          font_size=sp(12), bg=rgba(BLUE))
        b.bind(on_release=lambda x: on_open())
        bottom.add_widget(b)
    box.add_widget(bottom)
    return box


class CoursesScreen(Screen):
    def __init__(self, **kw):
        Screen.__init__(self, **kw)
        root = BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(8))
        head = BoxLayout(size_hint_y=None, height=dp(40))
        head.add_widget(TitleLabel(text="课程库"))
        head.add_widget(Widget())
        b = PrimaryButton(text="刷新", size_hint_x=None, width=dp(80))
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
        for c in db.list_courses():
            n = db.count_sentences(c["id"])
            due = db.due_count(c["id"])
            card = _row_card([c["title"], c["level"], n, due],
                             on_open=lambda cid=c["id"]: self._open(cid))
            card.bind(on_touch_down=lambda w, t, cid=c["id"]:
                      self._open(cid) if w.collide_point(*t.pos) and t.is_double_tap
                      else None)
            self.grid.add_widget(card)

    def _open(self, cid):
        App.get_running_app().start_course(cid)


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
