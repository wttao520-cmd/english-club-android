#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""句子俱乐部 · 安卓版（Kivy）

桌面预览：  python main.py            （窗口按手机比例）
桌面全屏：  python main.py --tablet
打包 APK：  见 README.md / buildozer.spec
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from kivy.app import App
from kivy.core.window import Window
from kivy.metrics import dp
from kivy.properties import StringProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.screenmanager import ScreenManager, SlideTransition

from core import db
from core.context import AppContext
from core.courses_builtin import seed
from ui.library_screens import (CoursesScreen, ImportScreen, ReviewScreen,
                                StatsScreen)
from ui.phonics_screen import PhonicsScreen
from ui.practice_screen import PracticeScreen
from ui.settings_screen import MeScreen, SettingsScreen
from ui.theme import BG, BORDER, PANEL, rgba, setup_font

NAV = [("练习", "practice"), ("拼读", "phonics"), ("课程", "courses"),
       ("复习", "review"), ("我的", "me")]


class NavButton(BoxLayout):
    """底部导航项。"""

    text = StringProperty("")

    def __init__(self, **kw):
        from kivy.uix.behaviors import ButtonBehavior
        from kivy.uix.label import Label

        class _Inner(ButtonBehavior, BoxLayout):
            pass

        BoxLayout.__init__(self, **kw)
        self._btn = _Inner()
        self._lbl = Label(text=self.text, font_name="AppFont", font_size=dp(13),
                          color=rgba("#8b949e"))
        self._btn.add_widget(self._lbl)
        self.add_widget(self._btn)
        self.bind(text=self._sync)

    def _sync(self, *a):
        self._lbl.text = self.text

    def bind_press(self, cb):
        self._btn.bind(on_release=cb)

    def set_active(self, on):
        from ui.theme import TEXT
        self._lbl.color = rgba(TEXT) if on else rgba("#8b949e")
        self._lbl.bold = on


class RootWidget(BoxLayout):
    def __init__(self, app, **kw):
        BoxLayout.__init__(self, orientation="vertical", **kw)
        self.app = app

        with self.canvas.before:
            from kivy.graphics import Color, Rectangle
            Color(*rgba(BG))
            self._bg = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._sync_bg, size=self._sync_bg)

        self.sm = ScreenManager(transition=SlideTransition(duration=0.18))
        self.screens = {}
        for cls, name in [(PracticeScreen, "practice"), (PhonicsScreen, "phonics"),
                          (CoursesScreen, "courses"), (ReviewScreen, "review"),
                          (StatsScreen, "stats"), (ImportScreen, "import"),
                          (SettingsScreen, "settings"), (MeScreen, "me")]:
            s = cls(name=name)
            self.sm.add_widget(s)
            self.screens[name] = s
        self.add_widget(self.sm, 1)

        self.navbar = BoxLayout(size_hint_y=None, height=dp(56), spacing=0)
        self.nav_btns = {}
        for text, key in NAV:
            b = NavButton(text=text)
            b.bind_press(lambda x, k=key: self.app.goto(k))
            self.navbar.add_widget(b)
            self.nav_btns[key] = b
        self._paint_nav()
        self.add_widget(self.navbar)

    def _sync_bg(self, *a):
        self._bg.pos = self.pos
        self._bg.size = self.size

    def _paint_nav(self, *a):
        from kivy.graphics import Color, Rectangle
        self.navbar.canvas.before.clear()
        with self.navbar.canvas.before:
            Color(*rgba(PANEL))
            Rectangle(pos=self.navbar.pos, size=self.navbar.size)
            Color(*rgba(BORDER))
            Rectangle(pos=(self.navbar.x, self.navbar.y + self.navbar.height - dp(1)),
                      size=(self.navbar.width, dp(1)))
        self.navbar.bind(pos=self._paint_nav, size=self._paint_nav)


class EnglishClubApp(App):
    last_screen = StringProperty("me")

    def __init__(self, **kw):
        App.__init__(self, **kw)
        self.ctx = None
        self.root_widget = None

    # ------------------------------------------------------------ 构建
    def build(self):
        self.title = "句子俱乐部"
        base = self.user_data_dir if self._is_android() else None
        font_path = setup_font(base)
        from ui.theme import FONT_NAME
        self.font_name = FONT_NAME

        self.ctx = AppContext(base)
        db.init_db()
        seed()

        self.root_widget = RootWidget(self)
        self.sm = self.root_widget.sm
        self.refresh_all()
        self.goto("practice")

        # 启动信息写日志，便于排查安卓端问题
        try:
            from kivy.logger import Logger
            Logger.info("ClubApp: font=%s base=%s screens=%s"
                        % (font_path, base, self.sm.screen_names))
        except Exception:
            pass
        return self.root_widget

        self.root_widget = RootWidget(self)
        self.sm = self.root_widget.sm
        self.refresh_all()
        self.goto("practice")
        return self.root_widget

    @staticmethod
    def _is_android():
        try:
            from kivy.utils import platform
            return platform == "android"
        except Exception:
            return False

    # ------------------------------------------------------------ 导航
    def goto(self, name):
        if name not in self.sm.screen_names:
            return
        self.sm.current = name
        if name == "courses":
            self.screens("courses").refresh()
        elif name == "review":
            self.screens("review").refresh()
        elif name == "stats":
            self.screens("stats").refresh()
        elif name == "me":
            self.screens("me").refresh()
        elif name == "phonics":
            self.screens("phonics").refresh()
        for key, btn in self.root_widget.nav_btns.items():
            btn.set_active(key == name)

    def screens(self, name):
        return self.root_widget.screens[name]

    # ------------------------------------------------------------ 练习入口
    def start_course(self, course_id, mode=None):
        n = int(self.ctx.config.get("lesson_size", 10)) or 10
        rows = [dict(r) for r in db.due_course_cards(course_id, n)]
        if not rows:
            rows = [dict(r) for r in db.list_sentences(course_id)[:n]]
        course = db.get_course(course_id)
        self.start_sentences(rows, course["title"] if course else "练习", mode)

    def start_sentences(self, rows, title, mode=None):
        self.goto("practice")
        self.screens("practice").start(rows, title, mode)

    def refresh_all(self):
        if not self.ctx:
            return
        self.screens("practice").refresh_courses()
        try:
            self.screens("courses").refresh()
            self.screens("review").refresh()
            self.screens("stats").refresh()
            self.screens("me").refresh()
        except Exception:
            pass

    # ------------------------------------------------------------ 生命周期
    def on_pause(self):
        """安卓切到后台：保存状态，不销毁。"""
        return True

    def on_resume(self):
        self.refresh_all()

    def on_stop(self):
        try:
            self.ctx.config.save()
        except Exception:
            pass


def main():
    # 窗口尺寸只在桌面预览时设置；Android 上 Window 由 bootstrap 创建，改尺寸无意义
    try:
        from kivy.utils import platform
        is_android = platform == "android"
    except Exception:
        is_android = False
    if not is_android and "--tablet" not in sys.argv:
        Window.size = (420, 880)
    EnglishClubApp().run()


if __name__ == "__main__":
    main()
