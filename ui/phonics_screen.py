# -*- coding: utf-8 -*-
"""自然拼读：音素速查 + 分组拼写练习。"""

from kivy.app import App
from kivy.metrics import dp, sp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.screenmanager import Screen
from kivy.uix.scrollview import ScrollView
from kivy.uix.tabbedpanel import TabbedPanel, TabbedPanelItem
from kivy.uix.widget import Widget

from core import db
from core.phonics_data import FAMILY_SENTENCES, GROUPS
from .theme import (ACCENT, BORDER, CARD, FONT_NAME, GREEN, IPA_FONT_NAME,
                    MUTED, TEXT, YELLOW, AppLabel, AppTextInput, MixedFontLabel,
                    PrimaryButton, TitleLabel, rgba)
from .widgets import TypingBoard

CARD_BG = rgba("#1c2230")


def _card(title, color=ACCENT, size=sp(22), ipa=""):
    """卡片容器：标题用主字体；ipa 非空时用 IPA 专用字体单独一行显示。

    主字体子集缺少部分国际音标字形（ŋ ɔ ə ʃ 等），若与中文混排会显示方块，
    故音标必须用 IPAFont 渲染。
    """
    box = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(6),
                    size_hint_y=None)
    box.bind(minimum_height=box.setter("height"))
    box.add_widget(AppLabel(text="[color=%s][b]%s[/b][/color]" % (color, title),
                            font_size=size, size_hint_y=None, height=dp(30),
                            halign="left"))
    if ipa:
        from kivy.uix.label import Label as KLabel
        box.add_widget(KLabel(
            text=ipa, font_name=IPA_FONT_NAME, font_size=sp(20),
            color=rgba(YELLOW), size_hint_y=None, height=dp(28),
            halign="left", valign="middle",
            text_size=(dp(400), dp(28))))
    with box.canvas.before:
        from kivy.graphics import Color as GColor
        from kivy.graphics import RoundedRectangle
        GColor(*CARD_BG)
        box._rect = RoundedRectangle(pos=box.pos, size=box.size, radius=[dp(12)])
        GColor(*rgba(BORDER))
        box._border = RoundedRectangle(pos=box.pos, size=box.size, radius=[dp(12)])
    box.bind(pos=lambda o, v: (setattr(o._rect, "pos", v),
                               setattr(o._border, "pos", v)),
             size=lambda o, v: (setattr(o._rect, "size", v),
                                setattr(o._border, "size", v)))
    return box


class PhonicsScreen(Screen):
    def __init__(self, **kw):
        Screen.__init__(self, **kw)
        self.keyword = ""
        self.groups = GROUPS
        self._build()

    @property
    def ctx(self):
        return App.get_running_app().ctx

    def _build(self):
        root = BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(8))

        head = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(6))
        head.add_widget(TitleLabel(text="自然拼读", size_hint_x=0.4))
        self.search = AppTextInput(hint_text="搜索 sh / light / -ight",
                                   size_hint_x=0.6, multiline=False,
                                   size_hint_y=None, height=dp(40))
        self.search.bind(text=self._on_search)
        head.add_widget(self.search)
        root.add_widget(head)

        self.tabs = TabbedPanel(do_default_tab=False, tab_width=dp(140),
                                tab_height=dp(42),
                                background_color=rgba("#0e1116"))
        root.add_widget(self.tabs)

        bar = BoxLayout(size_hint_y=None, height=dp(46))
        b = PrimaryButton(text="开始整组拼读训练", bg=rgba("#2f81f7"))
        b.bind(on_release=lambda x: self._practice_group())
        bar.add_widget(b)
        root.add_widget(bar)

        self.add_widget(root)
        self.refresh()

    # ------------------------------------------------------------ 构建
    def refresh(self):
        self.tabs.clear_tabs()
        for g in self.groups:
            item = TabbedPanelItem(text=g["title"], font_name=FONT_NAME)
            item.add_widget(self._group_scroll(g))
            self.tabs.add_widget(item)
        item = TabbedPanelItem(text="词族短句", font_name=FONT_NAME)
        item.add_widget(self._family_scroll())
        self.tabs.add_widget(item)
        if self.tabs.tab_list:
            self.tabs.switch_to(self.tabs.tab_list[0])

    def _group_scroll(self, group):
        sv = ScrollView(scroll_type=["bars", "content"], bar_width=dp(6))
        grid = GridLayout(cols=1, spacing=dp(10), size_hint_y=None, padding=dp(8))
        grid.bind(minimum_height=grid.setter("height"))
        grid.cards = []
        for e in group["entries"]:
            card = self._entry_card(e)
            grid.add_widget(card)
            grid.cards.append((card, e, group))
        sv.add_widget(grid)
        sv.grid = grid
        sv.group_key = group["key"]
        return sv

    def _entry_card(self, e):
        card = _card(e["g"], ipa=e["ipa"])
        # note 里可能嵌有 /…/ 音标段：用 MixedFontLabel 按字体分段渲染
        note = MixedFontLabel(text=e["note"], font_size=sp(12),
                              color=MUTED, size_hint_y=None, height=dp(20))
        card.add_widget(note)

        flow = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(6))
        for word, _split, zh in e["words"]:
            b = PrimaryButton(text="%s %s" % (word, zh), size_hint_x=None,
                              width=dp(100 + 8 * len(word)), font_size=sp(13))
            b.bind(on_release=lambda x, w=word: self._say(w))
            flow.add_widget(b)
        flow.add_widget(Widget())
        card.add_widget(flow)

        go = PrimaryButton(text="练这几个词", size_hint_y=None, height=dp(40),
                           bg=rgba("#2f81f7"))
        go.bind(on_release=lambda x: self._practice_entry(e))
        card.add_widget(go)
        return card

    def _family_scroll(self):
        sv = ScrollView(scroll_type=["bars", "content"], bar_width=dp(6))
        grid = GridLayout(cols=1, spacing=dp(10), size_hint_y=None, padding=dp(8))
        grid.bind(minimum_height=grid.setter("height"))
        grid.cards = []
        for f in FAMILY_SENTENCES:
            card = _card(f["g"], color=GREEN, size=sp(18), ipa=f["ipa"])
            en = AppLabel(text=f["en"], font_size=sp(16), size_hint_y=None, height=dp(26),
                          halign="left")
            zh = AppLabel(text=f["zh"], font_size=sp(12), color=rgba(MUTED),
                          size_hint_y=None, height=dp(20), halign="left")
            note = MixedFontLabel(text=f["note"], font_size=sp(11),
                                  color=MUTED, size_hint_y=None, height=dp(18))
            for w in (en, zh, note):
                w.text_size = (dp(420), None)
                card.add_widget(w)
            go = PrimaryButton(text="练这句", size_hint_y=None, height=dp(38),
                               bg=rgba("#2f81f7"))
            go.bind(on_release=lambda x, s=f: self._practice_family(s))
            card.add_widget(go)
            grid.add_widget(card)
            grid.cards.append((card, f, None))
        sv.add_widget(grid)
        sv.grid = grid
        sv.group_key = "family"
        return sv

    # ------------------------------------------------------------ 交互
    def _on_search(self, instance, text):
        self.keyword = (text or "").strip().lower()
        for i in range(len(self.tabs.tab_list)):
            pass
        for tab in self.tabs.tab_list:
            sv = tab.content
            grid = getattr(sv, "grid", None)
            if grid is None:
                continue
            for card, entry, _g in grid.cards:
                if isinstance(entry, dict) and "en" in entry:
                    hit = (not self.keyword
                           or self.keyword in entry["g"].lower()
                           or self.keyword in entry["en"].lower()
                           or self.keyword in entry["zh"]
                           or self.keyword in entry["note"])
                else:
                    hit = (not self.keyword
                           or self.keyword in entry["g"].lower()
                           or self.keyword in entry["ipa"].lower()
                           or self.keyword in entry["note"]
                           or any(self.keyword in w.lower() or self.keyword in zh
                                  for w, _s, zh in entry["words"]))
                card.opacity = 1 if hit else 0.25
                card.disabled = not hit

    def _say(self, word):
        if self.ctx.config.get("tts_enabled", True):
            self.ctx.speaker.say(word)

    def _practice_entry(self, e):
        rows = db.sentences_by_en([w[0] for w in e["words"]])
        if not rows:
            return
        # 标题只放字母组合（IPA 用主字体渲染会变方块，不放进标题）
        App.get_running_app().start_sentences(
            [dict(r) for r in rows], "%s 拼写" % e["g"], "phonics")

    def _practice_family(self, f):
        rows = db.sentences_by_en([f["en"]])
        if not rows:
            return
        App.get_running_app().start_sentences(
            [dict(r) for r in rows], "词族 %s" % f["g"], "phonics")

    def _practice_group(self):
        tab = self.tabs.current_tab
        sv = tab.content if tab else None
        key = getattr(sv, "group_key", None)
        if not key:
            return
        course = db.get_course_by_key("ph_" + key)
        if course:
            App.get_running_app().start_course(course["id"], "phonics")


_ = TypingBoard, CARD
