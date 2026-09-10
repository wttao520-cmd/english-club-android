# -*- coding: utf-8 -*-
"""自绘控件：打字板、连击徽章、统计卡片、柱状图。"""

from kivy.core.text import Label as CoreLabel
from kivy.graphics import Color, Rectangle, RoundedRectangle
from kivy.metrics import dp, sp
from kivy.properties import (BooleanProperty, ListProperty, NumericProperty,
                             ObjectProperty, StringProperty)
from kivy.uix.widget import Widget

from .theme import (ACCENT, BLUE, BORDER, CHUNK_COLORS, FONT_NAME, GREEN,
                    MUTED, RED, TEXT, YELLOW, rgba)

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
        if items:
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
