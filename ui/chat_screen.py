# -*- coding: utf-8 -*-
"""AI 对话练习：选择场景 → 与 AI 角色英语对话 → 自动纠错与提示。

气泡式聊天界面；每条有效英文消息得积分；对话历史保存在内存（切场景重置）。
"""

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.metrics import dp, sp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.screenmanager import Screen
from kivy.uix.widget import Widget

from core import chat_scenes, db
from core.worker import run_async
from .theme import (ACCENT, BLUE, BORDER, CARD, FONT_NAME, GREEN, MUTED,
                    PANEL2, TEXT, YELLOW, AppLabel, AppTextInput,
                    PrimaryButton, TitleLabel, rgba)
from .widgets import PickerPopup

MAX_TURNS = 20  # 对话上下文最多保留的轮数（省 token）


def _bubble(text, color, bg, align_right=False, small=False):
    """一个聊天气泡（右对齐=用户，左=AI）。

    高度只单向传导：文字纹理高度 → 气泡内边距 → 行高。
    禁止 holder↔bubble 互相绑定（数值型属性同值赋值也会 dispatch，
    会造成 do_layout 无限循环：Clock "too much iteration" 告警）。
    """
    holder = BoxLayout(size_hint_y=None, height=dp(44))
    bubble = BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(2),
                       size_hint_x=0.78 if align_right else 0.86)
    lbl = AppLabel(text=text, font_size=sp(12 if small else 14),
                   color=rgba(color), halign="left")
    lbl.bind(width=lambda o, w: setattr(o, "text_size", (w, None)))

    def _sync_h(_o, ts):
        new_h = ts[1] + dp(22)
        if abs(holder.height - new_h) > 0.5:   # 防抖：阻断同值循环
            holder.height = new_h
    lbl.bind(texture_size=_sync_h)
    bubble.add_widget(lbl)

    if align_right:
        holder.add_widget(Widget())
        holder.add_widget(bubble)
    else:
        holder.add_widget(bubble)
        holder.add_widget(Widget())

    from kivy.graphics import Color as GColor
    from kivy.graphics import RoundedRectangle
    with bubble.canvas.before:
        GColor(*rgba(bg))
        bubble._rect = RoundedRectangle(pos=bubble.pos, size=bubble.size,
                                        radius=[dp(12)])
    bubble.bind(pos=lambda o, v: setattr(o._rect, "pos", v),
                size=lambda o, v: setattr(o._rect, "size", v))
    return holder


def _split_reply(raw):
    """把 AI 回复拆成 (英文, 纠错, 提示)。"""
    en_lines, fix, tip = [], "", ""
    mode = "en"
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("【纠错】"):
            mode = "fix"
            fix = line.replace("【纠错】", "").strip()
            continue
        if line.startswith("【提示】"):
            mode = "tip"
            tip = line.replace("【提示】", "").strip()
            continue
        if mode == "en":
            en_lines.append(line)
        elif mode == "fix":
            fix += " " + line
        else:
            tip += " " + line
    return ("\n".join(en_lines) or "…", fix, tip)


class ChatScreen(Screen):
    def __init__(self, **kw):
        Screen.__init__(self, **kw)
        self.scene = chat_scenes.get("free")
        self.history = []   # [{"role","content"}, ...]
        self._build()

    @property
    def ctx(self):
        return App.get_running_app().ctx

    # ------------------------------------------------------------ UI
    def _build(self):
        root = BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(6))

        top = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(6))
        self.scene_btn = PrimaryButton(
            text="%s %s" % (self.scene["icon"], self.scene["title"]),
            font_size=sp(14))
        self.scene_btn.bind(on_release=lambda b: self._pick_scene())
        top.add_widget(self.scene_btn)
        top.add_widget(self._points_label())
        root.add_widget(top)

        self.info_lbl = AppLabel(text="", font_size=sp(11), color=rgba(MUTED),
                                 size_hint_y=None, height=dp(18), halign="left")
        root.add_widget(self.info_lbl)

        self.sv = ScrollView(scroll_type=["bars", "content"], bar_width=dp(4))
        self.grid = GridLayout(cols=1, spacing=dp(8), size_hint_y=None,
                               padding=dp(4))
        self.grid.bind(minimum_height=self.grid.setter("height"))
        self.sv.add_widget(self.grid)
        root.add_widget(self.sv)

        row = BoxLayout(size_hint_y=None, height=dp(56), spacing=dp(6))
        self.inp = AppTextInput(hint_text="用英语回复…", multiline=False)
        self.inp.bind(on_text_validate=lambda w: self._send())
        row.add_widget(self.inp)
        send = PrimaryButton(text="发送", size_hint_x=None, width=dp(84),
                             bg=rgba(BLUE), font_size=sp(15))
        send.bind(on_release=lambda x: self._send())
        row.add_widget(send)
        root.add_widget(row)

        bar = BoxLayout(size_hint_y=None, height=dp(42), spacing=dp(6))
        for text, cb in [("翻译我的话", self._translate_last),
                         ("重开对话", self._reset)]:
            b = PrimaryButton(text=text, font_size=sp(12), bg=rgba(PANEL2))
            b.bind(on_release=cb)
            bar.add_widget(b)
        bar.add_widget(Widget())
        root.add_widget(bar)

        self.add_widget(root)

    def _points_label(self):
        self.pts_lbl = AppLabel(
            text="[color=%s]%d 分[/color]" % (YELLOW, db.get_points()),
            font_size=sp(14), bold=True, size_hint_x=None, width=dp(80),
            halign="right")
        return self.pts_lbl

    def refresh(self):
        self.pts_lbl.text = "[color=%s]%d 分[/color]" % (YELLOW, db.get_points())

    def on_enter(self, *a):
        if not self.grid.children:
            self._reset()

    # ------------------------------------------------------------ 气泡
    def _add_bubble(self, text, mine=False, small=False):
        if mine:
            bub = _bubble(text, "#ffffff", BLUE, align_right=True)
        else:
            bub = _bubble(text, TEXT, CARD, align_right=False, small=small)
        self.grid.add_widget(bub, 0)   # GridLayout 索引 0 = 视觉底部
        Clock.schedule_once(lambda dt: setattr(self.sv, "scroll_y", 0), 0.05)

    def _add_typing(self):
        self.typing = _bubble("对方输入中…", MUTED, PANEL2, small=True)
        self.grid.add_widget(self.typing, 0)
        Clock.schedule_once(lambda dt: setattr(self.sv, "scroll_y", 0), 0.05)

    def _remove_typing(self):
        t = getattr(self, "typing", None)
        if t is not None and t.parent:
            self.grid.remove_widget(t)
        self.typing = None

    # ------------------------------------------------------------ 场景
    def _pick_scene(self):
        names = ["%s %s" % (s["icon"], s["title"]) for s in chat_scenes.SCENES]
        PickerPopup("选择对话场景", names, self._scene_chosen,
                    current="%s %s" % (self.scene["icon"], self.scene["title"])
                    ).open()

    def _scene_chosen(self, name):
        for s in chat_scenes.SCENES:
            if "%s %s" % (s["icon"], s["title"]) == name:
                self.scene = s
                break
        self.scene_btn.text = "%s %s" % (self.scene["icon"], self.scene["title"])
        self.info_lbl.text = self.scene["desc"]
        self._reset()

    def _reset(self, *a):
        self.history = []
        self.grid.clear_widgets()
        self._add_bubble(self.scene["opening"], mine=False)
        self.history.append({"role": "assistant",
                             "content": self.scene["opening"]})
        self.info_lbl.text = self.scene["desc"]

    # ------------------------------------------------------------ 发送
    def _send(self, *a):
        text = self.inp.text.strip()
        if not text:
            return
        if not self.ctx.ai.config.get("ai_api_key"):
            self._add_bubble("请先在「设置」中启用 AI 并填写 API Key。",
                             mine=False, small=True)
            return
        self.inp.text = ""
        self._add_bubble(text, mine=True)
        self.history.append({"role": "user", "content": text})

        words = len(text.split())
        if words >= 2:
            db.add_points(2)
            self.pts_lbl.text = "[color=%s]%d 分[/color]" % (
                YELLOW, db.get_points())

        self._add_typing()
        messages = [{"role": "system", "content": self.scene["system"]}]
        messages += self.history[-MAX_TURNS * 2:]
        run_async(self.ctx.ai.chat_messages, self._on_reply,
                  self._on_fail, messages, 0.7)

    def _on_reply(self, raw):
        self._remove_typing()
        en, fix, tip = _split_reply(raw)
        self._add_bubble(en, mine=False)
        if fix:
            self._add_bubble("✎ %s" % fix, mine=False, small=True)
        if tip:
            self._add_bubble("💡 %s" % tip, mine=False, small=True)
        self.history.append({"role": "assistant", "content": en})
        self.pts_lbl.text = "[color=%s]%d 分[/color]" % (YELLOW, db.get_points())

    def _on_fail(self, msg):
        self._remove_typing()
        self._add_bubble("AI 出错了：%s" % msg, mine=False, small=True)

    def _translate_last(self, *a):
        """翻译学生最近一句英文。"""
        last = None
        for m in reversed(self.history):
            if m["role"] == "user":
                last = m["content"]
                break
        if not last:
            return
        self._add_typing()
        run_async(self.ctx.ai.translate, self._on_translate,
                  self._on_fail, last)

    def _on_translate(self, text):
        self._remove_typing()
        self._add_bubble("🇨🇳 %s" % (text or "（无）"), mine=False, small=True)
