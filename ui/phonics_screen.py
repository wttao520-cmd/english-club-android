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
from .theme import (ACCENT, BLUE, BORDER, CARD, FONT_NAME, GREEN, IPA_FONT_NAME,
                    MUTED, TEXT, YELLOW, AppLabel, AppTextInput, MixedFontLabel,
                    PrimaryButton, TitleLabel, rgba)
from .widgets import TypingBoard

CARD_BG = rgba("#1c2230")

# 音素「纯音」示范词。
#
# 为什么要这么绕：TTS 只能读完整的词，既读不了裸音标（/ʃ/ 会被念成斜杠符号），
# 也无法只读某个字母在词中的那一个音。所以「跟读」的做法是：挑一个
# 「该音就是全部」的最小示范词发音，并把「音标 → 示范词」显示给用户，
# 让他知道刚才听到的是那一段音（例如 /æ/ 听 at 里的 a，/ʃ/ 听 shh）。
_PHONEME_SOUND = {
    # ---- 元音（字母音 / 短元音 / 长元音 / 双元音）----
    "æ": "at", "e": "egg", "ɪ": "it", "ɒ": "on", "ʌ": "up",
    "iː": "see", "ɑː": "are", "ɔː": "or", "uː": "too", "ɜː": "her",
    "eɪ": "say", "aɪ": "eye", "əʊ": "go", "aʊ": "out", "ɔɪ": "oil",
    "juː": "you",
    # ---- 词族韵尾（FAMILY_SENTENCES 的音标）----
    "æt": "at", "en": "ten", "ɪg": "big", "ɒp": "top", "ʌn": "sun",
    "eɪk": "cake", "aɪt": "light", "ɪŋk": "ink", "aɪnd": "find",
    # ---- 单辅音（清音配元音，保证 TTS 发得出、听得清；浊音发本音）----
    "b": "ba", "k": "ka", "d": "da", "f": "fa", "g": "ga", "h": "ha",
    "dʒ": "jay", "l": "la", "m": "ma", "n": "na", "p": "pa", "r": "ra",
    "s": "sa", "t": "ta", "v": "va", "w": "wa", "j": "ya", "z": "za",
    # ---- 特殊辅音 ----
    "ks": "box",        # x 在词尾的 /ks/
    "kw": "quick",      # qu
    "tʃ": "chair",      # ch
    "ʃ": "shh",         # sh
    "θ": "think",       # th 清
    "ð": "this",        # th 浊
    "ŋ": "sing",        # ng
    "ŋk": "thank",      # nk
    # ---- 辅音连缀：本身不是"一个音"，用该连缀的最小词示范 ----
    "bl": "blue", "kl": "clock", "fl": "fly", "gl": "glass", "pl": "play",
    "sl": "slow", "br": "bread", "kr": "cry", "dr": "drink", "fr": "frog",
    "gr": "green", "pr": "price", "tr": "tree", "sk": "sky", "sc": "scarf",
    "sm": "small", "sn": "snow", "sp": "spell", "st": "stop",
    "sw": "swim", "tw": "twelve",
}
# 字母音分组：g 是单个字母、ipa 是它在单词里最常见的那个音，按字母兜底。
# （例：S=sa、X=box，其余见表内同名字母。）
_PHONEME_BY_LETTER = {
    "a": "at", "b": "ba", "c": "ka", "d": "da", "e": "egg", "f": "fa",
    "g": "ga", "h": "ha", "i": "it", "j": "jay", "k": "ka", "l": "la",
    "m": "ma", "n": "na", "o": "on", "p": "pa", "qu": "quick", "r": "ra",
    "s": "sa", "t": "ta", "u": "up", "v": "va", "w": "wa", "x": "box",
    "y": "ya", "z": "za",
}


def _norm_ipa(ipa):
    """把 "/ʃ/"、"/eɪ/"、"th (清)"、" /sm/ /sn/" 归一到单个纯音标串。"""
    s = (ipa or "").strip()
    if "(" in s:                      # th (清) / th (浊)
        s = s.split("(")[0].strip()
    s = s.replace("/", " ").strip()   # 去掉音标斜杠
    if " " in s:                      # "/sm/ /sn/" 之类复合音标，取第一个
        s = s.split()[0]
    if len(s) == 1 and s in ("清", "浊"):
        return ""
    return s


def phoneme_sound(entry):
    """返回该音素的「纯音」示范文本（供「♫ 跟读」朗读）。

    优先级：条目显式 sound 字段 → 音标精确查表 → 去掉长短音符号再查 →
    字母条目按字母查表 → 退回该条目第一个示例词（保证总有声音可听）。
    """
    if not hasattr(entry, "get"):
        return ""
    if entry.get("sound"):
        return entry["sound"]
    ipa = _norm_ipa(entry.get("ipa", ""))
    for key in (ipa, ipa.replace("ː", "")):
        if key in _PHONEME_SOUND:
            return _PHONEME_SOUND[key]
    g = (entry.get("g") or "").strip().lower()
    if g in _PHONEME_BY_LETTER:
        return _PHONEME_BY_LETTER[g]
    ws = entry.get("words") or []
    if ws:
        return ws[0][0]
    for key in ("ex", "en"):
        v = entry.get(key)
        if v:
            return v.split()[0] if key == "ex" else v
    return g


def _card(title, color=ACCENT, size=sp(22), ipa="", on_say=None, say_hint=""):
    """卡片容器：标题用主字体；ipa 非空时用 IPA 专用字体单独一行显示。

    主字体子集缺少部分国际音标字形（ŋ ɔ ə ʃ 等），若与中文混排会显示方块，
    故音标必须用 IPAFont 渲染。

    on_say 非空时，在音标右侧显示「♫ 跟读」按钮，点击读出该音素的纯音
    （用作示范的最小词，如 /æ/→at、/ʃ/→shh）——即"这个音本身"的发音，
    而不是示例词的整词读音。say_hint 为读不出发音时的提示文本。
    """
    box = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(6),
                    size_hint_y=None)
    box.bind(minimum_height=box.setter("height"))
    box.add_widget(AppLabel(text="[color=%s][b]%s[/b][/color]" % (color, title),
                            font_size=size, size_hint_y=None, height=dp(30),
                            halign="left"))
    if ipa:
        from kivy.uix.label import Label as KLabel
        row = BoxLayout(size_hint_y=None, height=dp(34), spacing=dp(8))
        ipa_lbl = KLabel(text=ipa, font_name=IPA_FONT_NAME, font_size=sp(20),
                         color=rgba(YELLOW), size_hint=(None, 1),
                         halign="left", valign="middle")
        ipa_lbl.texture_update()
        ipa_lbl.width = max(dp(60), ipa_lbl.texture_size[0] + dp(8))
        row.add_widget(ipa_lbl)
        if on_say:
            horn = PrimaryButton(text="♫ 跟读",
                                 size_hint=(None, None), width=dp(84),
                                 height=dp(32), font_size=sp(13),
                                 bg=rgba(BLUE))
            horn.bind(on_release=lambda x: on_say())
            row.add_widget(horn)
        row.add_widget(Widget())
        box.add_widget(row)
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

        # 跟读提示条：点击「♫ 跟读」后说明听到的是哪个音（自动隐藏）
        self.flash_lbl = AppLabel(text="", font_size=sp(12),
                                  size_hint_y=None, height=dp(20),
                                  halign="left")
        root.add_widget(self.flash_lbl)
        self._flash_ev = None

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
        card = _card(e["g"], ipa=e["ipa"],
                     on_say=lambda: self._say_phoneme(e))
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
            card = _card(f["g"], color=GREEN, size=sp(18), ipa=f["ipa"],
                         on_say=lambda ff=f: self._say_phoneme(ff))
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

    def _say_phoneme(self, entry):
        """读该音素的发音（同「♫ 跟读」按钮）。

        一年级教学场景下，"跟读"要听的是字母/音素本身的音，而不是某个
        整词的读音（例如 /æ/ 听 at 里那个 a 的音），故用最小示范词发音，
        并在顶部提示条说明"跟读：/æ/ → at"。
        entry 可为音素条目（含 words）或词族条目（含 en）。
        """
        if not self.ctx.config.get("tts_enabled", True):
            self._toast("发音已关闭，可在「设置」中开启")
            return
        word = phoneme_sound(entry)
        if not word:
            return
        ipa = (entry.get("ipa") or "") if hasattr(entry, "get") else ""
        self._flash("跟读：%s %s" % (ipa, word))
        self._say(word)

    def _flash(self, text):
        """在搜索框下方显示一行跟读提示（1.6s 后恢复原提示）。"""
        lbl = getattr(self, "flash_lbl", None)
        if lbl is None:
            return
        lbl.text = "[color=%s]%s[/color]" % (ACCENT, text)
        ev = getattr(self, "_flash_ev", None)
        if ev is not None:
            ev.cancel()
        from kivy.clock import Clock
        self._flash_ev = Clock.schedule_once(
            lambda dt: setattr(lbl, "text", ""), 1.6)

    def _toast(self, text):
        from kivy.uix.popup import Popup
        content = BoxLayout(padding=dp(14))
        content.add_widget(AppLabel(text=text, font_size=sp(13), halign="center"))
        pop = Popup(title="", separator_height=0, content=content,
                    size_hint=(0.8, 0.22), background="",
                    background_color=rgba("#141922"))
        pop.open()
        from kivy.clock import Clock
        Clock.schedule_once(lambda dt: pop.dismiss(), 1.6)

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
