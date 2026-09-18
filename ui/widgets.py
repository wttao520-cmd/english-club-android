# -*- coding: utf-8 -*-
"""自绘控件：打字板、连击徽章、统计卡片、柱状图。"""

from kivy.core.text import Label as CoreLabel
from kivy.graphics import Color, Ellipse, Line, Rectangle, RoundedRectangle, Triangle
from kivy.metrics import dp, sp
from kivy.properties import (BooleanProperty, ListProperty, NumericProperty,
                             ObjectProperty, StringProperty)
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.widget import Widget

from .theme import (ACCENT, BLUE, BORDER, CARD, CHUNK_COLORS, FONT_NAME, GREEN,
                    MUTED, PANEL2, RED, TEXT, YELLOW, AppLabel, PrimaryButton,
                    rgba, sdp, ssp, ui_scale)

_TEX_CACHE = {}

MONO_FONT = "RobotoMono-Regular"


def _tex(char, color_hex, font_size, mono=False):
    key = (char, color_hex, int(font_size), mono)
    t = _TEX_CACHE.get(key)
    if t is None:
        kwargs = dict(text=char, font_size=font_size, color=rgba(color_hex))
        if not mono:
            kwargs["font_name"] = FONT_NAME
        lbl = CoreLabel(**kwargs)
        lbl.refresh()
        t = lbl.texture
        _TEX_CACHE[key] = t
    return t


class TypingBoard(Widget):
    """逐字符高亮的打字板。

    chunks 非空时按音块交替着色（自然拼读）；hidden 时答案显示为占位方块。
    """

    target = StringProperty("")
    buffer = StringProperty("")
    hidden = BooleanProperty(False)
    chunks = ListProperty([])
    font_size = NumericProperty(sp(26))
    min_height = NumericProperty(dp(150))
    focus_callback = ObjectProperty(None)

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos) and self.focus_callback:
            self.focus_callback()
        return Widget.on_touch_down(self, touch)

    def __init__(self, **kw):
        Widget.__init__(self, **kw)
        self.size_hint_y = None
        self.height = self.min_height
        self.ok = 0
        self.bind(target=self.redraw, buffer=self.redraw, hidden=self.redraw,
                  chunks=self.redraw, pos=self.redraw, size=self.redraw,
                  font_size=self.redraw)
        self.redraw()

    # ---------------------------------------------------------- 状态
    def set_state(self, target, buffer, ok, hidden=False, chunks=None):
        self.ok = ok
        self.hidden = hidden
        self.chunks = list(chunks) if chunks else []
        self.target = target
        self.buffer = buffer

    def chunk_of(self, index):
        if not self.chunks:
            return -1
        pos = 0
        for i, c in enumerate(self.chunks):
            pos += len(c)
            if index < pos:
                return i
        return len(self.chunks) - 1

    def _spans(self):
        spans, pos = [], 0
        for c in self.chunks:
            spans.append((pos, pos + len(c), c))
            pos += len(c)
        return spans

    def _chunk_start(self, index):
        pos = 0
        for i, c in enumerate(self.chunks):
            if i == index:
                return pos
            pos += len(c)
        return 0

    # ---------------------------------------------------------- 布局
    def _layout(self):
        fs = self.font_size
        probe = _tex("M", TEXT, fs, mono=True)
        cw = probe.width + dp(7)
        line_h = int(fs * 1.85)
        max_w = max(dp(60), self.width - dp(24))
        gap = cw * 0.40 if self.chunks else 0.0
        x0 = self.x + dp(12)
        y0 = self.y + self.height - line_h - dp(10)

        words, cur = [], ""
        for ch in self.target:
            cur += ch
            if ch == " ":
                words.append(cur)
                cur = ""
        if cur:
            words.append(cur)

        items = []
        x, y, pos = float(x0), float(y0), 0
        for w in words:
            ww = cw * len(w)
            if self.chunks:
                for k in range(pos + 1, pos + len(w)):
                    if self.chunk_of(k) != self.chunk_of(k - 1):
                        ww += gap
            if x + ww > x0 + max_w and x > x0:
                x = float(x0)
                y -= line_h
            for k, ch in enumerate(w):
                if self.chunks and (pos + k) > 0 and \
                        self.chunk_of(pos + k) != self.chunk_of(pos + k - 1):
                    x += gap
                items.append([ch, x, y, cw, line_h, self.chunk_of(pos + k)])
                x += cw
            pos += len(w)
        return items, cw, line_h, gap

    # ---------------------------------------------------------- 绘制
    def redraw(self, *a):
        self.canvas.clear()
        with self.canvas:
            Color(*rgba("#141922"))
            Rectangle(pos=self.pos, size=(self.width, max(self.height, dp(40))))

        if not self.target:
            with self.canvas:
                Color(*rgba(MUTED))
                t = _tex("选择课程后开始练习", MUTED, sp(15))
                if t:
                    Rectangle(texture=t, pos=(self.center_x - t.width / 2,
                                              self.center_y - t.height / 2),
                              size=t.size)
            return

        items, cw, line_h, _gap = self._layout()
        # 仅固定高度模式（size_hint_y=None）下按内容自增高；
        # 弹性填满时由父容器决定高度，避免布局抖动。
        if items and self.size_hint_y is None:
            need = (self.y + self.height - items[-1][2]) + dp(16)
            h = max(self.min_height, need)
            if abs(h - self.height) > 1:
                self.height = h
                return

        fs = self.font_size
        cursor = len(self.buffer)
        cur_chunk = self.chunk_of(cursor) if self.chunks else -1

        with self.canvas:
            # 当前音块底框
            if cur_chunk >= 0:
                for start, end, _ in self._spans():
                    if start != self._chunk_start(cur_chunk):
                        continue
                    f = items[start]
                    l = items[min(end, len(items)) - 1]
                    c = CHUNK_COLORS[cur_chunk % len(CHUNK_COLORS)]
                    Color(*rgba(c, 0.16))
                    RoundedRectangle(
                        pos=(f[1] - dp(3), f[2] + f[4] * 0.06),
                        size=(l[1] + l[3] - f[1] + dp(2), f[4] * 0.86),
                        radius=[dp(6)])
                    break

            for idx, it in enumerate(items):
                ch, x, y, w, h, ci = it
                if idx < self.ok:
                    color = CHUNK_COLORS[ci % len(CHUNK_COLORS)] if ci >= 0 else GREEN
                    char = ch
                    bg = None
                    fg = "#ffffff"
                elif idx < cursor:
                    color = RED
                    char = self.buffer[idx] if idx < len(self.buffer) else ch
                    bg = RED
                    fg = "#ffffff"
                elif idx == cursor:
                    color = BLUE
                    char = ch
                    bg = BLUE
                    fg = "#ffffff"
                else:
                    color = "#4d5766"
                    char = "\u25af" if self.hidden else ch
                    bg = None
                    fg = "#3d4756" if self.hidden else "#4d5766"

                if bg:
                    Color(*rgba(bg))
                    Rectangle(pos=(x, y + h * 0.12), size=(w - dp(2), h * 0.76))

                if ch == " ":
                    if idx < self.ok:
                        Color(*rgba("#31405a"))
                        Rectangle(pos=(x + w * 0.3, y + h * 0.62), size=(w * 0.4, dp(2)))
                    continue

                t = _tex(char, fg if bg else color, fs, mono=not self.hidden or bg)
                if t is None:
                    continue
                Color(1, 1, 1, 1)
                Rectangle(texture=t, pos=(x + (w - t.width) / 2,
                                          y + h * 0.12 + (h * 0.76 - t.height) / 2),
                          size=t.size)

            # 光标下划线
            if cursor < len(items):
                it = items[cursor]
                Color(*rgba(ACCENT))
                Rectangle(pos=(it[1], it[2] + it[4] * 0.9), size=(it[3] - dp(2), dp(2)))


class FlowLayout(BoxLayout):
    """流式布局：子控件按自身宽度从左到右排列，放不下自动换行。

    子控件需 size_hint=(None, None) 并自带 width/height；容器高度按内容自适应。

    可用宽度来源（按优先级）：
      1. 外部显式设置的 width（非 100 默认值）；
      2. 父级 ScrollView 的宽度（自动探测）。
    这样即便放在 ScrollView 里（Kivy 不会自动给 size_hint=(None,None) 的子项
    分配宽度），也能拿到正确宽度进行换行。
    """

    def __init__(self, **kw):
        kw.setdefault("orientation", "horizontal")
        kw.setdefault("spacing", dp(6))
        kw.setdefault("padding", dp(4))
        # size_hint_x=1 让 ScrollView 自动把宽度设为视口宽度；
        # size_hint_y=None + 自身 height 让高度按内容自适应。
        kw.setdefault("size_hint", (1, None))
        self.valign = kw.pop("valign", "top")   # top | bottom | center
        BoxLayout.__init__(self, **kw)
        self._h = dp(40)
        self.bind(width=self._on_width, children=self._on_children)
        self.height = self._h

    def _on_width(self, *a):
        self._relayout()

    def _on_children(self, *a):
        # 新加的 tile 其 width 在 add_widget 之后才设定，
        # 故监听每个子项的 width/height 变化，任一变化都重排。
        for ch in self.children:
            if not getattr(ch, "_flow_bound", False):
                ch._flow_bound = True
                ch.bind(width=self._relayout, height=self._relayout)
        self._relayout()

    def do_layout(self, *a):
        """接管布局：BoxLayout 会把子项排成一行，这里改为流式换行。"""
        self._relayout()

    def _avail(self):
        return max(dp(20), self.width - self.padding[0] - self.padding[2])

    def _offset(self, inner_h):
        """内容顶部相对容器顶部的内缩量（inner_h 为不含 padding 的纯内容高度）。

        返回 0 表示内容贴顶；返回 extra 表示内容贴底（贴近拇指）。
        """
        extra = self.height - inner_h - self.padding[1] - self.padding[3]
        if extra <= 0:
            return 0.0
        if self.valign == "bottom":
            return extra
        if self.valign == "center":
            return extra / 2.0
        return 0.0

    def _rows(self, avail):
        """按宽度切行，返回每行的子项列表（顺序为添加顺序）。"""
        rows = []
        x = 0.0
        for ch in reversed(self.children):
            w = max(dp(1), ch.width)
            if not rows or (x > 0 and x + w > avail + 0.5):
                rows.append([])
                x = 0.0
            rows[-1].append(ch)
            x += w + self.spacing
        return rows

    def _relayout(self, *a):
        if getattr(self, "_in_layout", False):
            return
        self._in_layout = True
        try:
            avail = self._avail()
            rows = self._rows(avail)
            inner_h = sum(max(ch.height for ch in r) for r in rows if r)
            inner_h += self.spacing * max(0, len(rows) - 1)
            content_h = inner_h + self.padding[1] + self.padding[3]
            # 固定高度模式下按内容自增高
            if self.size_hint_y is None and abs(content_h - self._h) > 0.5:
                self._h = content_h
                self.height = content_h
            self._place(avail, rows, inner_h)
        finally:
            self._in_layout = False

    def _place(self, avail, rows, inner_h):
        # 内容顶部基准 y：bottom 时整体下沉到底部（贴近拇指）
        base = self.y + self.height - self.padding[1] - self._offset(inner_h)
        y = 0.0
        for row in rows:
            if not row:
                continue
            rh = max(ch.height for ch in row)
            x = 0.0
            for ch in row:
                ch.pos = (self.x + self.padding[0] + x, base - y - ch.height)
                x += max(dp(1), ch.width) + self.spacing
            y += rh + self.spacing


class WordTile(PrimaryButton):
    """选词模式中的一个可点词块。"""

    def __init__(self, text, on_pick, **kw):
        kw.setdefault("text", text)
        kw.setdefault("font_size", ssp(14))
        kw.setdefault("size_hint", (None, None))
        kw.setdefault("bg", rgba(PANEL2))
        PrimaryButton.__init__(self, **kw)
        self._on_pick = on_pick
        self._base_bg = self.bg
        self.bind(on_release=lambda b: self._on_pick(self))

    def set_bg(self, color):
        self.bg = rgba(color)

    def reset_bg(self):
        self.bg = self._base_bg


class WordChoiceBoard(BoxLayout):
    """选词模式答题区：

    上排「已填入区」按顺序显示选中的词（点击可取回），
    下排「词库区」用流式布局展示候选词块（按文字宽度自动换行），
    点击词块即自动填入下一个空位。
    """

    def __init__(self, on_pick, on_undo, **kw):
        kw.setdefault("orientation", "vertical")
        kw.setdefault("spacing", dp(8))
        BoxLayout.__init__(self, **kw)
        self.on_pick = on_pick
        self.on_undo = on_undo

        # 已填入区：流式排列（长句自动多行）。这里用普通容器而非 ScrollView，
        # 避免 ScrollView 在内容不超过视口时把子项 y 放到 0 干扰对齐。
        self._slots_min = sdp(88)
        self.slots = FlowLayout(spacing=sdp(5), padding=sdp(2), valign="top",
                                size_hint=(1, None))
        filled_wrap = BoxLayout(size_hint_y=None, height=self._slots_min)
        filled_wrap.add_widget(self.slots)
        self._filled_wrap = filled_wrap
        self.add_widget(filled_wrap)
        self.slots.bind(height=self._sync_slots_height)

        # 词库区：流式排列，词块按文字宽度自动换行；
        # 容器撑满剩余空间，valign=bottom 让词块沉到底部（贴近拇指，好点）。
        self.pool_wrap = BoxLayout()
        self.pool = FlowLayout(spacing=sdp(5), padding=sdp(2), valign="bottom",
                               size_hint=(1, 1))
        self.pool_wrap.add_widget(self.pool)
        self.add_widget(self.pool_wrap)
        self.pool_wrap.bind(width=self._sync_pool_width)
        self._sync_pool_width()

    def _sync_slots_height(self, *a):
        """槽位区高度跟随内容（多行时变高，句子长也能看全）。"""
        need = max(self._slots_min, self.slots.height + sdp(8))
        cap = max(self._slots_min, self.height * 0.45)
        h = min(need, cap)
        if abs(h - self._filled_wrap.height) > 1:
            self._filled_wrap.height = h

    def _sync_pool_width(self, *a):
        """width 由 size_hint_x=1 + ScrollView 自动管理；触发一次重排即可。"""
        if self.pool.width > 0:
            self.pool._relayout()

    # ---------------------------------------------------------- 渲染
    def show(self, words, placed, pool, used=None, wrong_text=None):
        """渲染选中槽位与词库。

        words: [(词, 空白)] 当前句词序；placed: 已正确填入词数；
        pool: 乱序后的「完整候选池」（顺序固定，不随选择变化）；
        used: 已被选走的词列表（用于把对应词块隐藏，其余词块位置不动）。
        """
        self._words = list(words)
        self._placed = placed

        # ---- 上排槽位 ----
        self.slots.clear_widgets()
        for i, (w, _sp) in enumerate(self._words):
            if i < placed:
                t = PrimaryButton(text=w, font_size=ssp(15),
                                  size_hint=(None, None), bg=rgba(GREEN))
                t.height = sdp(40)
                t.width = self._btn_width(t, w)
                t.bind(on_release=lambda b, idx=i: self.on_undo(idx))
                self.slots.add_widget(t)
            else:
                chip = PrimaryButton(text="", font_size=ssp(15),
                                     size_hint=(None, None), width=sdp(46),
                                     height=sdp(40), bg=rgba("#141922"))
                self.slots.add_widget(chip)
        if not self._words:
            self.slots.add_widget(AppLabel(
                text="（本句没有可选的词）", color=rgba(MUTED),
                size_hint_y=None, height=sdp(34)))

        # ---- 下排词库：池签名不变时复用已有词块，只切换显隐，位置绝不跳变 ----
        pool = list(pool)
        sig = tuple(pool)
        if getattr(self, "_pool_sig", None) != sig:
            self.pool.clear_widgets()
            for w in pool:
                tile = WordTile(w, self._tile_pressed)
                tile.height = sdp(40)
                tile.width = self._btn_width(tile, w)
                self.pool.add_widget(tile)
            self._pool_sig = sig
        # 按 used 计数隐藏对应词块（保留顺序，其它词块不动）
        used = list(used or [])
        hidden = {}
        for w in used:
            hidden[w] = hidden.get(w, 0) + 1
        for tile in self.pool.children:
            # 已选走的词块：透明+不可点，但**保留原有宽高占位**，
            # 这样其余词块不会左移填补空位——位置保持不动。
            n = hidden.get(tile.text, 0)
            if n > 0:
                hidden[tile.text] = n - 1
                tile.opacity = 0
                tile.disabled = True
            else:
                tile.opacity = 1
                tile.disabled = False

        self._pool_words = pool
        self._sync_pool_width()
        self.pool._relayout()

    @staticmethod
    def _btn_width(btn, text):
        """按文字实际宽度自适应按钮宽度，并封顶（随屏幕缩放）。

        PrimaryButton 内部的 Label 的 text_size 会跟随按钮尺寸（循环依赖），
        直接用它的 texture_size 会得到错误宽度，故用 CoreLabel 单独量文字。
        """
        try:
            lbl = CoreLabel(text=text, font_name=FONT_NAME, font_size=ssp(15))
            lbl.refresh()
            tw = lbl.texture.width
        except Exception:
            tw = dp(len(text) * 8 * ui_scale())
        return min(sdp(260), max(sdp(36), tw + sdp(20)))

    def _tile_pressed(self, tile):
        self.on_pick(tile.text, tile)


class ComboBadge(Widget):
    value = NumericProperty(0)

    def __init__(self, **kw):
        Widget.__init__(self, **kw)
        self.size_hint = (None, None)
        self.size = (dp(96), dp(64))
        self.bind(value=self.redraw, pos=self.redraw, size=self.redraw)
        self.redraw()

    @property
    def color(self):
        v = self.value
        if v >= 100:
            return "#bc8cff"
        if v >= 50:
            return "#ff7b72"
        if v >= 25:
            return YELLOW
        if v >= 10:
            return ACCENT
        return MUTED

    def redraw(self, *a):
        self.canvas.clear()
        c = self.color
        with self.canvas:
            Color(*rgba(c, 0.12))
            RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(10)])
            Color(*rgba(MUTED))
            t1 = _tex("COMBO", MUTED, sp(10))
            if t1:
                Rectangle(texture=t1, pos=(self.center_x - t1.width / 2,
                                           self.y + self.height - t1.height - dp(6)),
                          size=t1.size)
            Color(*rgba(c))
            t2 = _tex("x%d" % self.value, c, sp(26))
            if t2:
                Rectangle(texture=t2, pos=(self.center_x - t2.width / 2,
                                           self.y + dp(12)), size=t2.size)


class BarChart(Widget):
    """近 N 天学习时长柱状图。"""

    data = ListProperty([])

    def __init__(self, **kw):
        Widget.__init__(self, **kw)
        self.size_hint_y = None
        self.height = dp(150)
        self.bind(data=self.redraw, pos=self.redraw, size=self.redraw)

    def set_data(self, rows, key="seconds"):
        self.data = [[r["date"], float(r.get(key, 0) or 0)] for r in rows]

    def redraw(self, *a):
        self.canvas.clear()
        with self.canvas:
            Color(*rgba("#141922"))
            Rectangle(pos=self.pos, size=(self.width, self.height))
        if not self.data:
            return
        pad = dp(14)
        n = len(self.data)
        maxv = max([v for _, v in self.data] + [60.0])
        bw = (self.width - pad * 2) / float(n)
        with self.canvas:
            for i, (_d, v) in enumerate(self.data):
                bh = max(dp(2), (self.height - pad * 2) * (v / maxv))
                x = self.x + pad + i * bw
                y = self.y + pad
                Color(*rgba(GREEN if v >= maxv * 0.5 else "#2ea043"))
                Rectangle(pos=(x + bw * 0.18, y), size=(bw * 0.64, bh))
            Color(*rgba(MUTED))
            for i in (0, n // 2, n - 1):
                if 0 <= i < n:
                    d = self.data[i][0]
                    t = _tex(d[5:], MUTED, sp(9))
                    if t:
                        Rectangle(texture=t,
                                  pos=(self.x + pad + i * bw + bw / 2 - t.width / 2,
                                       self.y + dp(2)), size=t.size)


class StatCard(Widget):
    """统计数字卡片。"""

    title = StringProperty("")
    value = StringProperty("")
    color = StringProperty(TEXT)

    def __init__(self, **kw):
        Widget.__init__(self, **kw)
        self.size_hint_y = None
        self.height = dp(84)
        self.bind(title=self.redraw, value=self.redraw, color=self.redraw,
                  pos=self.redraw, size=self.redraw)

    def redraw(self, *a):
        self.canvas.clear()
        with self.canvas:
            Color(*rgba("#1c2230"))
            RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(12)])
            Color(*rgba(MUTED))
            t = _tex(self.title, MUTED, sp(12))
            if t:
                Rectangle(texture=t, pos=(self.x + dp(14),
                                          self.y + self.height - t.height - dp(12)),
                          size=t.size)
            Color(*rgba(self.color))
            v = _tex(self.value, self.color, sp(24))
            if v:
                Rectangle(texture=v, pos=(self.x + dp(14), self.y + dp(14)), size=v.size)
            Color(*rgba(BORDER))


# ==================================================================
# 宠物：纯 canvas 绘制的几何小宠物（无外部素材，APK 零体积成本）
# ==================================================================
class PetWidget(Widget):
    """根据 species 与进化阶段画一只小宠物。

    stage: 0 幼年（小圆脸）/ 1 成长（加身体+肚皮）/ 2 完全体（加皇冠）
    """

    species = StringProperty("cat")
    stage = NumericProperty(0)
    happy = BooleanProperty(False)

    _SKETCH = {
        "cat": "ears_point", "bunny": "ears_long", "duck": "beak",
        "panda": "ears_round", "fox": "ears_big", "unicorn": "horn",
    }

    def __init__(self, **kw):
        Widget.__init__(self, **kw)
        self.bind(species=self.redraw, stage=self.redraw, pos=self.redraw,
                  size=self.redraw, happy=self.redraw)

    def redraw(self, *a):
        from core.pet import colors
        self.canvas.clear()
        body, shade = colors(self.species)
        ear = self._SKETCH.get(self.species, "ears_point")
        s = max(dp(10), min(self.width, self.height))
        cx, cy = self.center_x, self.center_y
        r = s * (0.20 if self.stage == 0 else 0.22)
        head_y = cy + s * (0.20 if self.stage else 0.08)
        eye_dx, eye_dy = r * 0.42, r * 0.10
        er = max(dp(1.2), r * 0.10)

        with self.canvas:
            # ---- 身体（成长期起）----
            if self.stage >= 1:
                bw, bh = r * 1.5, r * 1.25
                by = cy - s * 0.30
                Color(*rgba(shade))
                Ellipse(pos=(cx - bw / 2 - dp(1.5), by - dp(1.5)),
                        size=(bw + dp(3), bh + dp(3)))
                Color(*rgba(body))
                Ellipse(pos=(cx - bw / 2, by), size=(bw, bh))
                Color(*rgba("#ffffff", 0.85))
                Ellipse(pos=(cx - bw * 0.30, by + bh * 0.08),
                        size=(bw * 0.6, bh * 0.62))

            # ---- 物种特征 ----
            if ear == "ears_point":
                for dx in (-1, 1):
                    Color(*rgba(shade))
                    Triangle(points=[cx + dx * r * 0.75, head_y + r * 0.55,
                                     cx + dx * r * 1.15, head_y + r * 1.55,
                                     cx + dx * r * 0.10, head_y + r * 0.95])
            elif ear == "ears_long":
                for dx in (-1, 1):
                    Color(*rgba(shade))
                    Ellipse(pos=(cx + dx * r * 0.55 - r * 0.22, head_y + r * 0.55),
                            size=(r * 0.44, r * 1.5))
            elif ear == "ears_round":
                for dx in (-1, 1):
                    Color(*rgba("#3a3f4a"))
                    Ellipse(pos=(cx + dx * r * 0.85 - r * 0.28, head_y + r * 0.55),
                            size=(r * 0.56, r * 0.56))
            elif ear == "ears_big":
                for dx in (-1, 1):
                    Color(*rgba(shade))
                    Triangle(points=[cx + dx * r * 0.45, head_y + r * 0.65,
                                     cx + dx * r * 1.45, head_y + r * 1.75,
                                     cx + dx * r * 0.05, head_y + r * 0.95])
            elif ear == "horn":
                Color(*rgba("#ffd166"))
                Triangle(points=[cx - r * 0.14, head_y + r * 0.85,
                                 cx + r * 0.14, head_y + r * 0.85,
                                 cx, head_y + r * 1.85])
                for dx in (-1, 1):
                    Color(*rgba("#efe3ff"))
                    Ellipse(pos=(cx + dx * r * 0.95 - r * 0.20, head_y + r * 0.60),
                            size=(r * 0.40, r * 0.40))

            # ---- 头 ----
            Color(*rgba(shade))
            Ellipse(pos=(cx - r - dp(1.5), head_y - r - dp(1.5)),
                    size=(r * 2 + dp(3), r * 2 + dp(3)))
            Color(*rgba(body))
            Ellipse(pos=(cx - r, head_y - r), size=(r * 2, r * 2))

            # ---- 眼睛 + 腮红 ----
            for dx in (-1, 1):
                Color(*rgba("#2b2f38"))
                Ellipse(pos=(cx + dx * eye_dx - er, head_y + eye_dy - er),
                        size=(er * 2, er * 2))
                Color(*rgba("#ffffff"))
                Ellipse(pos=(cx + dx * eye_dx - er * 0.3,
                             head_y + eye_dy + er * 0.15),
                        size=(er * 0.8, er * 0.8))
            blush = r * 0.16
            for dx in (-1, 1):
                Color(*rgba("#ff8fa3", 0.55))
                Ellipse(pos=(cx + dx * r * 0.62 - blush,
                             head_y - r * 0.30 - blush * 0.6),
                        size=(blush * 2, blush * 1.2))

            # ---- 嘴（开心时上扬）----
            Color(*rgba("#7a5230"))
            mw, mh = r * 0.34, r * (0.18 if self.happy else 0.08)
            my = head_y - r * 0.42
            if ear == "beak":
                Color(*rgba("#ff9f43"))
                Triangle(points=[cx - r * 0.42, my + r * 0.30,
                                 cx + r * 0.42, my + r * 0.30,
                                 cx, my - r * 0.05])
            else:
                Line(points=[cx - mw / 2, my + (mh if self.happy else 0),
                             cx, my - mh * 0.6,
                             cx + mw / 2, my + (mh if self.happy else 0)],
                     width=max(dp(0.8), r * 0.05))

            # ---- 完全体皇冠 ----
            if self.stage >= 2:
                cy0 = head_y + r * (1.95 if ear == "horn" else 1.65)
                cw = r * 0.9
                Color(*rgba("#ffd166"))
                Triangle(points=[cx - cw / 2, cy0, cx + cw / 2, cy0, cx, cy0 + r * 0.75])
                Color(*rgba("#ffe9a8"))
                Ellipse(pos=(cx - dp(1.6), cy0 + r * 0.55),
                        size=(dp(3.2), dp(3.2)))


class PickerPopup(Popup):
    """全屏式选项弹窗：替代 Spinner，竖屏下永远不会显示不全。

    groups 不为空时按「分组标题（可折叠）+ 组内选项」渲染，便于课程多时浏览。
    groups 形如：[("小类名", [选项文本, ...]), ...]。
    """

    def __init__(self, title, values, on_pick, current=None, groups=None, **kw):
        Popup.__init__(self, title="", separator_height=0, **kw)
        self.size_hint = (0.9, 0.82)
        self.background = ""
        self.background_color = rgba("#141922")
        self.values = list(values)
        self.on_pick = on_pick
        self.current = current
        self._groups = list(groups) if groups else None
        self._open_groups = set()
        self._auto_expanded = False   # 只在首次打开时自动展开当前项所在组

        root = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(8))
        head = BoxLayout(size_hint_y=None, height=dp(36))
        head.add_widget(AppLabel(text="[b]%s[/b]" % title, font_size=sp(17),
                                 halign="left"))
        close = PrimaryButton(text="关闭", size_hint_x=None, width=dp(76),
                              font_size=sp(13), bg=rgba(CARD))
        close.bind(on_release=lambda x: self.dismiss())
        head.add_widget(close)
        root.add_widget(head)

        self._sv = ScrollView(scroll_type=["bars", "content"], bar_width=dp(6))
        self._grid = GridLayout(cols=1, spacing=dp(6), size_hint_y=None,
                                padding=dp(2))
        self._grid.bind(minimum_height=self._grid.setter("height"))
        self._sv.add_widget(self._grid)
        root.add_widget(self._sv)
        self.content = root
        self._fill()

    def _fill(self):
        self._grid.clear_widgets()
        if not self._groups:
            for v in self.values:
                self._grid.add_widget(self._option(v))
            return
        # 分组模式：首次打开时展开含当前选项的组，之后完全尊重用户折叠状态
        # （不能用 `if not self._open_groups` 判断，否则用户折叠到空集合后会被强制再展开）
        if not self._auto_expanded:
            self._auto_expanded = True
            for name, items in self._groups:
                if self.current in items:
                    self._open_groups.add(name)
        for name, items in self._groups:
            opened = name in self._open_groups
            self._grid.add_widget(self._group_header(name, len(items), opened))
            if opened:
                for v in items:
                    self._grid.add_widget(self._option(v, indent=dp(10)))

    def _group_header(self, name, count, opened):
        from kivy.graphics import Color, RoundedRectangle
        box = BoxLayout(size_hint_y=None, height=dp(44),
                        padding=[dp(10), dp(4)])
        with box.canvas.before:
            Color(*rgba(CARD))
            box._rect = RoundedRectangle(pos=box.pos, size=box.size,
                                         radius=[dp(10)])
        box.bind(pos=lambda o, v: setattr(o._rect, "pos", v),
                 size=lambda o, v: setattr(o._rect, "size", v))
        mark = "[-]" if opened else "[+]"
        box.add_widget(AppLabel(text="[b]%s %s[/b]" % (mark, name),
                                font_size=sp(15), color=rgba(YELLOW),
                                halign="left"))
        box.add_widget(AppLabel(text="%d" % count, font_size=sp(12),
                                color=rgba(MUTED), size_hint_x=None,
                                width=dp(40), halign="right"))
        box.bind(on_touch_down=lambda w, t, n=name: (
            self._toggle_group(n) if w.collide_point(*t.pos) else None))
        return box

    def _toggle_group(self, name):
        if name in self._open_groups:
            self._open_groups.discard(name)
        else:
            self._open_groups.add(name)
        self._fill()

    def _option(self, v, indent=0):
        sel = (v == self.current)
        b = PrimaryButton(
            text=("[b]%s[/b]" % v) + ("　[color=%s]√[/color]" % GREEN
                                      if sel else ""),
            size_hint_y=None, height=dp(50), font_size=sp(15),
            bg=rgba(ACCENT if sel else PANEL2), halign="left")
        if indent:
            b.padding = [indent, dp(4)]
        b.bind(on_release=lambda x, val=v: self._pick(val))
        return b

    def _pick(self, val):
        self.dismiss()
        if self.on_pick:
            self.on_pick(val)
