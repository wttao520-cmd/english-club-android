# -*- coding: utf-8 -*-
"""宠物乐园：喂养、升级、进化、解锁新宠物。"""

from kivy.app import App
from kivy.metrics import dp, sp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.popup import Popup
from kivy.uix.progressbar import ProgressBar
from kivy.uix.scrollview import ScrollView
from kivy.uix.widget import Widget

from core import db, pet as pet_mod
from .theme import (ACCENT, BLUE, BORDER, CARD, GREEN, MUTED, PANEL2, RED,
                    TEXT, YELLOW, AppLabel, PrimaryButton, TitleLabel, rgba)
from .widgets import PetWidget


def _stars(n, size=sp(16)):
    return AppLabel(text="[color=%s]%s[/color][color=%s]%s[/color]" % (
        YELLOW, "*" * n, MUTED, "*" * (3 - n)), font_size=size,
        size_hint_y=None, height=dp(22), markup=True)


class PetPopup(Popup):
    """宠物乐园主弹窗。"""

    def __init__(self, **kw):
        Popup.__init__(self, title="", separator_height=0, **kw)
        self.size_hint = (0.96, 0.92)
        self.background = ""
        self.background_color = rgba("#141922")
        self.state = pet_mod.load()
        self._build()

    def _build(self):
        self.content = self._make_content()

    def _make_content(self):
        st = self.state
        root = BoxLayout(orientation="vertical", padding=dp(14), spacing=dp(8))

        head = BoxLayout(size_hint_y=None, height=dp(34))
        head.add_widget(TitleLabel(text="宠物乐园"))
        pts = db.get_points()
        head.add_widget(AppLabel(
            text="[color=%s]%d 分[/color]" % (YELLOW, pts), font_size=sp(14),
            size_hint_x=None, width=dp(90), halign="right"))
        root.add_widget(head)

        # 宠物舞台
        stage_box = BoxLayout(size_hint_y=None, height=dp(150))
        self.pet_view = PetWidget(species=st.species, stage=st.stage,
                                  happy=True, size_hint=(1, 1))
        stage_box.add_widget(self.pet_view)
        root.add_widget(stage_box)

        # 名字 + 等级 + 经验条
        body, shade = pet_mod.colors(st.species)
        info = BoxLayout(orientation="vertical", size_hint_y=None,
                         height=dp(74), spacing=dp(4))
        info.add_widget(AppLabel(
            text="[b]%s[/b] · %s · [color=%s]%s[/color]" % (
                st.name, pet_mod.species_name(st.species),
                ACCENT, pet_mod.stage_name(st.stage)),
            font_size=sp(15), size_hint_y=None, height=dp(24),
            halign="center"))
        lv_row = BoxLayout(size_hint_y=None, height=dp(22))
        lv_row.add_widget(AppLabel(
            text="Lv.%d" % st.level if st.level < pet_mod.MAX_LEVEL
            else "Lv.MAX", font_size=sp(13), bold=True,
            color=rgba(body), size_hint_x=None, width=dp(60), halign="left"))
        self.exp_bar = ProgressBar(max=max(1, st.need), value=st.exp_in_level)
        lv_row.add_widget(self.exp_bar)
        info.add_widget(lv_row)
        info.add_widget(AppLabel(
            text="经验 %d / %d · 喂一次 10 分" % (st.exp_in_level, st.need)
            if st.need else "已达最高等级，它是你的骄傲！",
            font_size=sp(11), color=rgba(MUTED), size_hint_y=None, height=dp(20),
            halign="center"))
        root.add_widget(info)

        # 喂养按钮
        feed_row = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(8))
        for label, cost, bg in [("喂 1 次\n10 分", 10, PANEL2),
                                ("喂 5 次\n50 分", 50, PANEL2),
                                ("喂到升级", -1, BLUE)]:
            b = PrimaryButton(text=label, font_size=sp(13), bg=rgba(bg))
            b.bind(on_release=lambda x, c=cost: self._feed(c))
            feed_row.add_widget(b)
        root.add_widget(feed_row)

        self.msg = AppLabel(text="", font_size=sp(12), color=rgba(GREEN),
                            size_hint_y=None, height=dp(20), halign="center")
        root.add_widget(self.msg)

        # 宠物仓库
        root.add_widget(AppLabel(text="我的宠物 / 可解锁", font_size=sp(13),
                                 color=rgba(MUTED), size_hint_y=None, height=dp(22)))
        sv = ScrollView()
        grid = GridLayout(cols=3, spacing=dp(8), size_hint_y=None,
                          padding=dp(2))
        grid.bind(minimum_height=grid.setter("height"))
        for key in pet_mod.SPECIES:
            grid.add_widget(self._pet_card(key))
        sv.add_widget(grid)
        root.add_widget(sv)

        close = PrimaryButton(text="关闭", size_hint_y=None, height=dp(44),
                              bg=rgba(CARD))
        close.bind(on_release=lambda x: self.dismiss())
        root.add_widget(close)
        return root

    def _pet_card(self, key):
        st = self.state
        unlocked = key in st.unlocked
        active = key == st.species
        box = BoxLayout(orientation="vertical", padding=dp(6), spacing=dp(2),
                        size_hint_y=None, height=dp(120))
        name, cost, body, _shade = pet_mod.SPECIES[key]
        with box.canvas.before:
            from kivy.graphics import Color, RoundedRectangle
            c = ACCENT if active else CARD
            Color(*rgba(c, 0.35 if active else 1.0))
            box._rect = RoundedRectangle(pos=box.pos, size=box.size,
                                         radius=[dp(10)])
        box.bind(pos=lambda o, v: setattr(o._rect, "pos", v),
                 size=lambda o, v: setattr(o._rect, "size", v))
        pw = PetWidget(species=key, stage=2 if unlocked else 0,
                       size_hint=(1, 1), opacity=1.0 if unlocked else 0.35)
        box.add_widget(pw)
        if unlocked:
            lbl = "[b]%s[/b]%s" % (name, "（使用中）" if active else "")
            box.add_widget(AppLabel(text=lbl, font_size=sp(12),
                                    size_hint_y=None, height=dp(20),
                                    halign="center"))
            if not active:
                b = PrimaryButton(text="切换", font_size=sp(11),
                                  size_hint_y=None, height=dp(30))
                b.bind(on_release=lambda x, k=key: self._switch(k))
                box.add_widget(b)
            else:
                box.add_widget(Widget(size_hint_y=None, height=dp(30)))
        else:
            box.add_widget(AppLabel(text="??? %s" % name, font_size=sp(12),
                                    color=rgba(MUTED), size_hint_y=None,
                                    height=dp(20), halign="center"))
            b = PrimaryButton(text="%d 分解锁" % cost, font_size=sp(10),
                              size_hint_y=None, height=dp(30), bg=rgba(YELLOW))
            b.bind(on_release=lambda x, k=key: self._unlock(k))
            box.add_widget(b)
        return box

    # ------------------------------------------------------------ 行为
    def _refresh(self):
        st = self.state
        self.pet_view.species = st.species
        self.pet_view.stage = st.stage
        self.exp_bar.max = max(1, st.need)
        self.exp_bar.value = st.exp_in_level
        root = self._make_content()
        self.content.clear_widgets()
        self.content = root

    def _feed(self, count):
        st = self.state
        pts = db.get_points()
        cost_each = 10
        if count == -1:
            # 喂到升级：估算需要多少次
            need_exp = st.need - st.exp_in_level
            count = max(1, -(-need_exp // cost_each))  # 向上取整
        count = min(count, pts // cost_each)
        if count <= 0:
            self.msg.text = "[color=%s]积分不足：练习和复习都能赚积分哦[/color]" % RED
            self.msg.markup = True
            return
        db.add_points(-count * cost_each)
        level_up, old_stage, _new_stage = st.add_exp(count * cost_each)
        st.save()
        self.pet_view.happy = True
        if level_up:
            self.msg.text = "[b][color=%s]%s 升到 Lv.%d！%s[/color][/b]" % (
                YELLOW, st.name, st.level,
                "进化成%s了！" % pet_mod.stage_name(st.stage)
                if st.stage != old_stage else "")
            self.msg.markup = True
        else:
            self.msg.text = "[color=%s]%s 吃得很开心（+%d 经验）[/color]" % (
                GREEN, st.name, count * cost_each)
            self.msg.markup = True
        self._refresh()

    def _switch(self, key):
        st = self.state
        st.species = key
        st.save()
        self._refresh()

    def _unlock(self, key):
        st = self.state
        cost = pet_mod.unlock_cost(key)
        if db.get_points() < cost:
            self.msg.text = "[color=%s]积分不够，还差 %d 分[/color]" % (
                RED, cost - db.get_points())
            self.msg.markup = True
            return
        db.add_points(-cost)
        st.unlocked.append(key)
        st.species = key
        st.save()
        self.msg.text = "[b][color=%s]新伙伴 %s 加入！[/color][/b]" % (
            YELLOW, pet_mod.species_name(key))
        self.msg.markup = True
        self._refresh()

    def open(self, *a, **kw):
        Popup.open(self, *a, **kw)


class PetEntry(BoxLayout):
    """练习页顶部的小宠物入口：宠物头像 + 积分，点按打开宠物乐园。"""

    def __init__(self, **kw):
        BoxLayout.__init__(self, size_hint_x=None, width=dp(124),
                           spacing=dp(4), **kw)
        self._pw = PetWidget(species="cat", stage=0, size_hint=(None, None),
                             size=(dp(38), dp(38)))
        self._lbl = AppLabel(text="[color=%s]0[/color]" % YELLOW,
                             font_size=sp(16), bold=True, size_hint_x=None,
                             width=dp(72), halign="left")
        self.add_widget(self._pw)
        self.add_widget(self._lbl)
        self.refresh()

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            self._open_pet()
            return True
        return BoxLayout.on_touch_down(self, touch)

    def refresh(self):
        st = pet_mod.load()
        self._pw.species = st.species
        self._pw.stage = st.stage
        self._lbl.text = "[color=%s]%d[/color]" % (YELLOW, db.get_points())

    def _open_pet(self):
        p = PetPopup()
        p.bind(on_dismiss=lambda x: self.refresh())
        p.open()
