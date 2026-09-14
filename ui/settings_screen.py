# -*- coding: utf-8 -*-
"""设置与「我的」：AI 接入、练习偏好、数据、统计入口。"""

import os

from kivy.app import App
from kivy.metrics import dp, sp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.popup import Popup
from kivy.uix.screenmanager import Screen
from kivy.uix.scrollview import ScrollView
from kivy.uix.widget import Widget

from core.config import app_dir
from core.worker import run_async
from .theme import (ACCENT, BLUE, CARD, GREEN, MUTED, RED, TEXT,
                    AppCheckBox, AppLabel, AppSpinner, AppTextInput,
                    PrimaryButton, TitleLabel, rgba)


def _section(parent, title):
    box = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(8),
                    size_hint_y=None)
    box.bind(minimum_height=box.setter("height"))
    box.add_widget(TitleLabel(text=title, font_size=sp(16)))
    parent.add_widget(box)
    return box


def _row(label, widget, label_w=dp(96)):
    row = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(6))
    row.add_widget(AppLabel(text=label, font_size=sp(13), size_hint_x=None,
                            width=label_w, halign="left"))
    row.add_widget(widget)
    return row


class SettingsScreen(Screen):
    def __init__(self, **kw):
        Screen.__init__(self, **kw)
        self.ctx = App.get_running_app().ctx
        root = BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(8))

        sv = ScrollView(scroll_type=["bars", "content"], bar_width=dp(6))
        self.body = BoxLayout(orientation="vertical", spacing=dp(10),
                              size_hint_y=None, padding=dp(2))
        self.body.bind(minimum_height=self.body.setter("height"))
        sv.add_widget(self.body)
        root.add_widget(sv)
        self.add_widget(root)
        self._build()

    # ------------------------------------------------------------ UI
    def _build(self):
        b = self.body

        # ---- AI
        ai = _section(b, "AI 英语老师")
        self.ai_enable = AppCheckBox(active=bool(self.ctx.config.get("ai_enabled")))
        ai.add_widget(_row("启用 AI", self._with_label(self.ai_enable, "翻译 / 讲解 / 拆句")))
        self.base_edit = AppTextInput(text=self.ctx.config.get("ai_base_url") or "",
                                      multiline=False, hint_text="https://api.deepseek.com/v1")
        self.key_edit = AppTextInput(text=self.ctx.config.get("ai_api_key") or "",
                                     multiline=False, password=True, hint_text="sk-...")
        self.model_edit = AppTextInput(text=self.ctx.config.get("ai_model") or "",
                                       multiline=False, hint_text="deepseek-chat")
        ai.add_widget(_row("接口地址", self.base_edit, dp(110)))
        ai.add_widget(_row("API Key", self.key_edit, dp(110)))
        ai.add_widget(_row("模型", self.model_edit, dp(110)))

        preset = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(6))
        for name, url, model in [
            ("DeepSeek", "https://api.deepseek.com/v1", "deepseek-chat"),
            ("OpenAI", "https://api.openai.com/v1", "gpt-4o-mini"),
            ("月之暗面", "https://api.moonshot.cn/v1", "moonshot-v1-8k"),
            ("Ollama", "http://localhost:11434/v1", "qwen2.5"),
        ]:
            pb = PrimaryButton(text=name, font_size=sp(12))
            pb.bind(on_release=lambda x, u=url, m=model: self._preset(u, m))
            preset.add_widget(pb)
        ai.add_widget(preset)

        test_row = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(8))
        self.test_btn = PrimaryButton(text="测试连接")
        self.test_btn.bind(on_release=lambda x: self._test())
        self.save_btn = PrimaryButton(text="保存设置", bg=rgba(BLUE))
        self.save_btn.bind(on_release=lambda x: self._save())
        test_row.add_widget(self.test_btn)
        test_row.add_widget(self.save_btn)
        ai.add_widget(test_row)
        self.state_lbl = AppLabel(text="", font_size=sp(12), size_hint_y=None, height=dp(24))
        ai.add_widget(self.state_lbl)

        # ---- 练习
        p = _section(b, "练习")
        self.mode_spin = AppSpinner(
            text={"sentence": "句子模式", "word": "单词模式",
                  "dictation": "默写模式", "phonics": "拼读模式（听音拼写）"}.get(
                self.ctx.config.get("mode"), "句子模式"),
            values=["句子模式", "单词模式", "默写模式", "拼读模式（听音拼写）"])
        p.add_widget(_row("默认模式", self.mode_spin, dp(110)))
        self.auto_next = AppCheckBox(active=bool(self.ctx.config.get("auto_next", True)))
        p.add_widget(_row("", self._with_label(self.auto_next, "答完后自动进入下一句")))
        self.sound_cb = AppCheckBox(active=bool(self.ctx.config.get("sound_enabled", True)))
        p.add_widget(_row("", self._with_label(self.sound_cb, "按键音效")))
        self.tts_cb = AppCheckBox(active=bool(self.ctx.config.get("tts_enabled", True)))
        p.add_widget(_row("", self._with_label(self.tts_cb, "启用朗读（在线发音）")))
        self.auto_tts_cb = AppCheckBox(active=bool(self.ctx.config.get("auto_tts", False)))
        p.add_widget(_row("", self._with_label(self.auto_tts_cb, "进入句子时自动朗读")))

        # ---- 数据
        d = _section(b, "数据")
        d.add_widget(AppLabel(text=app_dir(), font_size=sp(11), color=rgba(MUTED),
                              size_hint_y=None, height=dp(30)))
        d.add_widget(AppLabel(
            text="数据库保存于应用私有目录；卸载应用会一并清除，重要进度请定期导出。",
            font_size=sp(11), color=rgba(MUTED), size_hint_y=None, height=dp(30)))

        b.add_widget(Widget(size_hint_y=None, height=dp(20)))

    @staticmethod
    def _with_label(check, text):
        box = BoxLayout(spacing=dp(6))
        box.add_widget(check)
        box.add_widget(AppLabel(text=text, font_size=sp(13), halign="left"))
        return box

    def _preset(self, url, model):
        self.base_edit.text = url
        self.model_edit.text = model

    # ------------------------------------------------------------ 动作
    def _save(self):
        mode_map = {"句子模式": "sentence", "单词模式": "word",
                    "默写模式": "dictation", "拼读模式（听音拼写）": "phonics"}
        self.ctx.config.update({
            "ai_enabled": self.ai_enable.active,
            "ai_base_url": self.base_edit.text.strip(),
            "ai_api_key": self.key_edit.text.strip(),
            "ai_model": self.model_edit.text.strip(),
            "mode": mode_map.get(self.mode_spin.text, "sentence"),
            "auto_next": self.auto_next.active,
            "sound_enabled": self.sound_cb.active,
            "tts_enabled": self.tts_cb.active,
            "auto_tts": self.auto_tts_cb.active,
        })
        self.ctx.reload_ai()
        self._state("设置已保存", GREEN)
        App.get_running_app().refresh_all()

    def _test(self):
        self._save()
        self.test_btn.disabled = True
        self._state("正在测试…", MUTED)
        run_async(self.ctx.ai.translate,
                  lambda txt: self._on_test("连接成功，译文：%s" % txt, True),
                  lambda msg: self._on_test("连接失败：%s" % msg, False),
                  "Practice makes perfect.")

    def _on_test(self, msg, ok):
        self.test_btn.disabled = False
        self._state(msg, GREEN if ok else RED)

    def _state(self, text, color=MUTED):
        self.state_lbl.text = "[color=%s]%s[/color]" % (color, text)


class MeScreen(Screen):
    """「我的」：总览 + 各功能入口。"""

    def __init__(self, **kw):
        Screen.__init__(self, **kw)
        root = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(10))
        root.add_widget(TitleLabel(text="我的"))

        self.overview = AppLabel(text="", font_size=sp(13), size_hint_y=None,
                                 height=dp(70), halign="left")
        root.add_widget(self.overview)

        # 宠物乐园入口（大卡片）
        from .pet_screen import PetEntry
        from .widgets import PetWidget
        import core.pet as pet_mod
        st = pet_mod.load()
        pet_card = BoxLayout(orientation="horizontal", padding=dp(10),
                             spacing=dp(10), size_hint_y=None, height=dp(84))
        with pet_card.canvas.before:
            from kivy.graphics import Color, RoundedRectangle
            Color(*rgba("#1c2230"))
            pet_card._rect = RoundedRectangle(pos=pet_card.pos,
                                              size=pet_card.size,
                                              radius=[dp(12)])
        pet_card.bind(pos=lambda o, v: setattr(o._rect, "pos", v),
                      size=lambda o, v: setattr(o._rect, "size", v))
        pet_card.add_widget(PetWidget(species=st.species, stage=st.stage,
                                      size_hint=(None, None),
                                      size=(dp(64), dp(64)), happy=True))
        from kivy.uix.behaviors import ButtonBehavior
        info = BoxLayout(orientation="vertical")
        info.add_widget(AppLabel(text="[b]宠物乐园[/b]", font_size=sp(16),
                                 size_hint_y=None, height=dp(26), halign="left"))
        info.add_widget(AppLabel(
            text="%s · Lv.%d · %s\n练得越多，吃得越饱" % (
                pet_mod.species_name(st.species), st.level,
                pet_mod.stage_name(st.stage)),
            font_size=sp(12), color=rgba("#8b949e"), halign="left"))
        pet_card.add_widget(info)
        tap = ButtonBehavior
        self._pet_tap = PetEntry()
        self._pet_tap.opacity = 0
        self._pet_tap.size_hint_y = None
        self._pet_tap.height = dp(1)
        pet_card.add_widget(self._pet_tap)
        pet_card.bind(on_touch_down=self._on_pet_touch)
        root.add_widget(pet_card)

        for text, screen, color in [("学习统计", "stats", BLUE),
                                    ("导入内容", "import", GREEN),
                                    ("设置（AI / 练习 / 数据）", "settings", ACCENT)]:
            b = PrimaryButton(text=text, size_hint_y=None, height=dp(52),
                              bg=rgba(color), font_size=sp(16))
            b.bind(on_release=lambda x, s=screen: self._goto(s))
            root.add_widget(b)

        root.add_widget(Widget())
        root.add_widget(AppLabel(text="句子俱乐部 · 安卓版 v1.0\n数据全部保存在本机",
                                 font_size=sp(11), color=rgba(MUTED),
                                 size_hint_y=None, height=dp(40), halign="center"))
        self.add_widget(root)

    def _on_pet_touch(self, w, touch):
        if w.collide_point(*touch.pos) and touch.button == "left":
            from .pet_screen import PetPopup
            p = PetPopup()
            p.bind(on_dismiss=lambda x: self.refresh())
            p.open()
            return True
        return False

    def _goto(self, name):
        app = App.get_running_app()
        app.last_screen = "me"
        app.sm.current = name

    def refresh(self):
        from core import db
        s = db.overall_stats()
        c = db.srs_counts()
        self.overview.text = (
            "累计练习 [color=%s]%d[/color] 句　·　准确率 [color=%s]%.1f%%[/color]\n"
            "平均 [color=%s]%.0f WPM[/color]　·　最高连击 [color=%s]x%d[/color]\n"
            "已学 %d 句　·　今日待复习 [color=%s]%d[/color] 句"
            % (GREEN, s["reviews"], ACCENT, s["avg_accuracy"], TEXT, s["avg_wpm"],
               "#e3b341", s["max_combo"], c["learned"], "#e3b341", c["due"]))


_ = os, Popup, CARD
