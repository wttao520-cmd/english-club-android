# -*- coding: utf-8 -*-
"""主题：颜色、中文字体解析、通用控件。"""

import os
import re

from kivy.core.text import LabelBase
from kivy.metrics import dp, sp
from kivy.properties import (ColorProperty, ListProperty, NumericProperty,
                             StringProperty)
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.checkbox import CheckBox
from kivy.uix.label import Label
from kivy.uix.spinner import Spinner, SpinnerOption
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget

# ------------------------------------------------------------------ 颜色
BG = "#0e1116"
PANEL = "#161b22"
PANEL2 = "#1c2230"
CARD = "#1a2029"
BORDER = "#262d3a"
TEXT = "#e6edf3"
MUTED = "#8b949e"
ACCENT = "#58a6ff"
GREEN = "#3fb950"
YELLOW = "#e3b341"
RED = "#f85149"
PURPLE = "#bc8cff"
BLUE = "#2f81f7"

CHUNK_COLORS = [GREEN, ACCENT, PURPLE, YELLOW, "#56d4dd", "#ff7b72"]


def rgba(hex_color, a=1.0):
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
    return (r, g, b, a)


# ------------------------------------------------------------------ 屏幕自适应
# 手机基准宽度（与 main.py 的桌面预览窗口一致）
BASE_WIDTH_DP = 420.0


def ui_scale():
    """按屏幕（窗口）宽度算出的 UI 缩放系数。

    手机（≈420dp 宽）返回 1.0；平板/大屏按比例放大，上限 2.2 避免过大。
    以「dp 宽度」为基准，因此不随像素密度重复放大。
    """
    try:
        from kivy.core.window import Window
        w = Window.width / dp(1)
        if w <= 0:
            return 1.0
        return max(1.0, min(2.2, w / BASE_WIDTH_DP))
    except Exception:
        return 1.0


def ssp(size):
    """自适应字号：主题字号 × 屏幕缩放（在 sp 基础上再按屏幕宽度放大）。"""
    return sp(size * ui_scale())


def sdp(size):
    """自适应尺寸：dp × 屏幕缩放（仅用于选词板等需要随屏放大的地方）。"""
    return dp(size * ui_scale())


# ------------------------------------------------------------------ 字体
FONT_NAME = "AppFont"
IPA_FONT_NAME = "IPAFont"  # 国际音标专用（中文子集字体无 IPA 字形）

_FONT_CANDIDATES = [
    # 打包进 APK 的简体子集（推荐，tools/build_font.py 生成）
    "assets/fonts/NotoSansSC-Subset.otf",
    "assets/fonts/NotoSansSC-Regular.otf",
    "assets/fonts/NotoSansSC-Regular.ttf",
    # Android 系统
    "/system/fonts/NotoSansCJK-Regular.ttc",
    "/system/fonts/NotoSansSC-Regular.otf",
    "/system/fonts/DroidSansFallback.ttf",
    "/system/fonts/NotoSerifCJK-Regular.ttc",
    # Linux 桌面预览
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Medium.ttc",
    "/usr/share/fonts/truetype/arphic/uming.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
]


def _first_existing(paths):
    for p in paths:
        if os.path.exists(p):
            return p
    return None


def setup_font(app_dir=None):
    """注册全局字体。返回实际使用的字体路径（None 表示用了内置兜底）。

    路径解析顺序：
      1. 相对本文件的路径：ui/theme.py 往上两级即项目根 / APK 内的应用目录。
         不能用 cwd 相对路径——Android 进程的 cwd 是 "/"，必然找不到。
      2. kivy.resource_find：Kivy 的资源搜索机制，能定位 APK 内 assets。
      3. Android 系统字体目录。
      4. 兜底：把 FONT_NAME 注册为 Kivy 自带 Roboto——保证所有
         font_name=FONT_NAME 的控件不会因字体缺失而崩溃（中文会显示方块，
         但应用能启动；该情况只在以上全部落空时发生）。
    """
    candidates = []
    try:
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        candidates += [
            os.path.join(root, "assets", "fonts", "NotoSansSC-Subset.otf"),
            os.path.join(root, "assets", "fonts", "NotoSansSC-Regular.otf"),
            os.path.join(root, "assets", "fonts", "NotoSansSC-Regular.ttf"),
        ]
    except Exception:
        pass
    try:
        from kivy.resources import resource_find
        found = resource_find("assets/fonts/NotoSansSC-Subset.otf")
        if found:
            candidates.append(found)
    except Exception:
        pass
    if app_dir:
        candidates.append(os.path.join(app_dir, "fonts", "NotoSansSC-Subset.otf"))
    candidates += _FONT_CANDIDATES

    path = _first_existing(candidates)
    try:
        if path:
            LabelBase.register(FONT_NAME, fn_regular=path)
        else:
            # 全部落空：用 Kivy 自带 Roboto 兜底，绝不返回未注册状态
            from kivy import kivy_data_dir
            path = os.path.join(kivy_data_dir, "fonts", "Roboto.ttf")
            LabelBase.register(FONT_NAME, fn_regular=path)

        # IPA 音标专用字体：中文子集字体不含国际音标字形
        ipa_candidates = []
        try:
            ipa_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            ipa_candidates.append(os.path.join(
                ipa_root, "assets", "fonts", "IPAFont-Subset.ttf"))
        except Exception:
            pass
        ipa_candidates += [
            "/system/fonts/NotoSans-Regular.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ]
        ipa = _first_existing(ipa_candidates)
        if ipa:
            LabelBase.register(IPA_FONT_NAME, fn_regular=ipa)
        else:
            LabelBase.register(IPA_FONT_NAME, fn_regular=path)
        return path
    except Exception:
        return None


# ------------------------------------------------------------------ 控件
class Card(BoxLayout):
    """带圆角边框背景的容器。"""

    background_color = ColorProperty(rgba(CARD))
    border_color = ColorProperty(rgba(BORDER))
    radius = ListProperty([dp(12)])


class AppLabel(Label):
    """默认中文字体与颜色的 Label。"""

    def __init__(self, **kw):
        kw.setdefault("font_name", FONT_NAME)
        kw.setdefault("color", rgba(TEXT))
        kw.setdefault("markup", True)
        Label.__init__(self, **kw)
        self.bind(size=self._wrap)
        self._wrap()

    def _wrap(self, *a):
        self.text_size = (self.width, None)


_IPA_SEG = re.compile(r"(/[^/\n]{0,24}/)")
# 国际音标字符（含重音/长音符号与「同上」符号）。
_IPA_CHARS = set("ʃʒθðŋɜɑɔəʊɪʌæɒɐɘɵɛɨøœɣβɸχɯɰɴʙɢʀʜʟɦɬɮʋɾɽʂʐʝɟɡɱɳɶɹɺɻʞʇʈˌˈːˑ")
# 音标字母里会出现、但普通英文也大量使用的字符（IPA 与拉丁字母重叠区）
_IPA_ASCII = set("abcdefghijklmnopqrstuvwxyz")
_IPA_ALLOWED = _IPA_CHARS | _IPA_ASCII | set(" /")


class MixedFontLabel(BoxLayout):
    """把文本按字体分段渲染：音标部分用 IPA 字体，其余用主字体。

    主字体子集不含部分国际音标字形（ɪ ə ʊ ɔ ʃ ː ˈ 等），混排会显示方块；
    Kivy 的 Label 不支持一行内多种字体，故把文本切成若干段，
    音标段单独用 IPAFont 的 Label，其余用主字体，按宽度自动换行排布。
    """

    def __init__(self, text="", font_size=None, color=MUTED, **kw):
        kw.setdefault("orientation", "horizontal")
        kw.setdefault("spacing", 0)
        kw.setdefault("size_hint_y", None)
        BoxLayout.__init__(self, **kw)
        self._fs = font_size or sp(12)
        self._color = color
        self._lbls = []
        self._set_segments(text or "")
        self.bind(width=self._reflow)
        self.bind(minimum_height=self.setter("height"))

    @staticmethod
    def split_segments(text):
        """把文本切成 [(片段, 是否用 IPA 字体), ...]。

        注意不能只靠「/…/ 包裹」判定音标：note 里写成
        「长音：food / moon；短音 /ʊ/：book / look」时，正则会把两个斜杠
        之间的「moon；短音」也当成音标，交给 IPA 字体渲染 → 中文变方块。
        因此只有**内容里不含非 IPA 字符**的 /…/ 才算音标段。
        """
        out = []
        for part in _IPA_SEG.split(text):
            if not part:
                continue
            if _IPA_SEG.fullmatch(part) and MixedFontLabel._is_ipa_only(part):
                out.append((part, True))
                continue
            out.extend(MixedFontLabel._split_by_char(part))
        return out

    @staticmethod
    def _is_ipa_only(seg):
        """判断一段文本（可含首尾斜杠）是否纯由音标字符构成。"""
        return all(ch in _IPA_ALLOWED for ch in seg)

    @staticmethod
    def _split_by_char(part):
        """把一段文本按「是否含 IPA 字符」切成连续片段。"""
        out = []
        buf = []
        cur = None
        for ch in part:
            want = ch in _IPA_CHARS
            if cur is None or want == cur:
                buf.append(ch)
                cur = want
            else:
                out.append(("".join(buf), cur))
                buf = [ch]
                cur = want
        if buf:
            out.append(("".join(buf), bool(cur)))
        return out

    def _set_segments(self, text):
        from kivy.uix.label import Label as KLabel
        self.clear_widgets()
        self._lbls = []
        for seg, is_ipa in self.split_segments(text):
            lbl = KLabel(text=seg,
                         font_name=(IPA_FONT_NAME if is_ipa else FONT_NAME),
                         font_size=self._fs, color=rgba(self._color),
                         size_hint=(None, None), halign="left", valign="top",
                         markup=False)
            lbl.texture_update()
            lbl.width = lbl.texture_size[0]
            lbl.height = lbl.texture_size[1]
            self._lbls.append(lbl)
            self.add_widget(lbl)
        self._reflow()

    def set_text(self, text):
        self._set_segments(text)

    def _reflow(self, *a):
        avail = max(dp(40), self.width)
        x = y = 0.0
        row_h = 0.0
        for lbl in reversed(self.children):
            w = max(dp(1), lbl.width)
            h = lbl.height
            if x > 0 and x + w > avail + 0.5:
                x = 0.0
                y += row_h
                row_h = 0.0
            lbl.pos = (self.x + x, self.y + self.height - y - h)
            x += w
            row_h = max(row_h, h)
        self.height = y + row_h


class MutedLabel(AppLabel):
    def __init__(self, **kw):
        kw.setdefault("color", rgba(MUTED))
        kw.setdefault("font_size", sp(13))
        AppLabel.__init__(self, **kw)


class TitleLabel(AppLabel):
    def __init__(self, **kw):
        kw.setdefault("font_size", sp(20))
        kw.setdefault("bold", True)
        kw.setdefault("size_hint_y", None)
        kw.setdefault("height", dp(34))
        kw.setdefault("halign", "left")
        kw.setdefault("valign", "middle")
        AppLabel.__init__(self, **kw)


class PrimaryButton(ButtonBehavior, BoxLayout):
    """自绘按钮：避免 Kivy 默认样式在不同系统上的差异。"""

    text = StringProperty("")
    bg = ColorProperty(rgba(PANEL2))
    fg = ColorProperty(rgba(TEXT))
    radius = NumericProperty(dp(10))
    font_size = NumericProperty(sp(15))

    def __init__(self, **kw):
        self._halign = kw.pop("halign", "center")
        self._lbl = AppLabel(halign=self._halign, valign="middle")
        bg = kw.pop("bg", None)
        BoxLayout.__init__(self, **kw)
        ButtonBehavior.__init__(self, **kw)
        self.add_widget(self._lbl)
        self.bind(pos=self._sync, size=self._sync, text=self._sync,
                  fg=self._sync, font_size=self._sync)
        self.bind(pos=self._move, size=self._move)
        self._paint()
        if bg is not None:
            self.bg = bg

    def _sync(self, *a):
        self._lbl.text = self.text
        self._lbl.color = self.fg
        self._lbl.font_size = self.font_size
        self._lbl.halign = getattr(self, "_halign", "center")
        self._lbl.pos = self.pos
        self._lbl.size = self.size
        self._lbl.text_size = self.size

    def on_bg(self, *a):
        self._paint()

    def _paint(self, *a):
        canvas = getattr(self, "canvas", None)
        if canvas is None:
            return
        from kivy.graphics import Color, RoundedRectangle
        canvas.before.clear()
        with canvas.before:
            Color(*self.bg)
            self._rect = RoundedRectangle(pos=self.pos, size=self.size,
                                          radius=[self.radius])

    def _move(self, *a):
        if getattr(self, "_rect", None) is not None:
            self._rect.pos = self.pos
            self._rect.size = self.size

    def on_state(self, *a):
        self.bg = rgba(BLUE if self.state == "down" else PANEL2)


class SectionBar(BoxLayout):
    """标题 + 右侧按钮的横条。"""

    def __init__(self, title="", **kw):
        kw.setdefault("size_hint_y", None)
        kw.setdefault("height", dp(48))
        kw.setdefault("spacing", dp(8))
        BoxLayout.__init__(self, **kw)
        t = TitleLabel(text=title)
        self.add_widget(t)
        self.actions = BoxLayout(size_hint_x=None, width=dp(120), spacing=dp(6))
        spacer = Widget()
        self.add_widget(spacer)
        self.add_widget(self.actions)


class AppTextInput(TextInput):
    """默认中文字体、无联想的输入框（用于捕获软键盘）。"""

    def __init__(self, **kw):
        kw.setdefault("font_name", FONT_NAME)
        kw.setdefault("background_color", rgba(PANEL2))
        kw.setdefault("foreground_color", rgba(TEXT))
        kw.setdefault("cursor_color", rgba(ACCENT))
        kw.setdefault("hint_text_color", rgba(MUTED))
        kw.setdefault("padding", [dp(12), dp(10), dp(12), dp(10)])
        kw.setdefault("keyboard_suggestions", False)
        TextInput.__init__(self, **kw)


class AppSpinnerOption(SpinnerOption):
    font_name = FONT_NAME

    def __init__(self, **kw):
        kw.setdefault("background_color", rgba(PANEL2))
        kw.setdefault("color", rgba(TEXT))
        SpinnerOption.__init__(self, **kw)


class AppSpinner(Spinner):
    option_cls = AppSpinnerOption

    def __init__(self, **kw):
        kw.setdefault("font_name", FONT_NAME)
        kw.setdefault("background_color", rgba(PANEL2))
        kw.setdefault("color", rgba(TEXT))
        kw.setdefault("size_hint_y", None)
        kw.setdefault("height", dp(40))
        Spinner.__init__(self, **kw)


class AppCheckBox(CheckBox):
    def __init__(self, **kw):
        kw.setdefault("size_hint", (None, None))
        kw.setdefault("size", (dp(34), dp(34)))
        CheckBox.__init__(self, **kw)


def divider():
    from kivy.graphics import Color, Rectangle
    w = Widget(size_hint_y=None, height=dp(1))
    with w.canvas:
        Color(*rgba(BORDER))
        w._r = Rectangle(pos=w.pos, size=w.size)
    w.bind(pos=lambda o, v: setattr(o._r, "pos", v),
           size=lambda o, v: setattr(o._r, "size", v))
    return w
