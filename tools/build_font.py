#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成打包用的字体子集。

Kivy 默认字体（Roboto）不含中文，APK 里必须自带中文字体，否则显示方块。
本脚本从系统 Noto CJK 中取出简体（SC）字面，按「GB2312 常用字 + 项目内出现
的所有字符（含 IPA 音标）」做子集化，输出到 assets/fonts/NotoSansSC-Subset.otf，
体积约 2~4 MB，远小于完整字体的 16 MB。

用法：
    pip install fonttools
    python tools/build_font.py            # 自动寻找系统字体
    python tools/build_font.py 字体路径   # 指定字体

无 fonttools 或系统无 CJK 字体时脚本会给出提示，此时可跳过：
APK 会退回到系统 /system/fonts/NotoSansCJK-Regular.ttc（多数安卓机型可用）。
"""

import glob
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "assets", "fonts", "NotoSansSC-Subset.otf")

SYSTEM_FONTS = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Medium.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Black.ttc",
    "/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc",
    "/usr/share/fonts/truetype/arphic/uming.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    "/system/fonts/NotoSansCJK-Regular.ttc",
    "/system/fonts/NotoSansSC-Regular.otf",
    "/usr/share/fonts/opentype/noto/NotoSansSC-Regular.otf",
]


def gb2312_chars():
    """GB2312 一级字库（常用 3755 字），足够日常学习与界面文案。"""
    chars = []
    for hi in range(0xB0, 0xD8):
        for lo in range(0xA1, 0xFF):
            try:
                chars.append(bytes([hi, lo]).decode("gb2312"))
            except Exception:
                pass
    return chars


def project_chars():
    chars = set()
    for path in glob.glob(os.path.join(ROOT, "**", "*.py"), recursive=True):
        with open(path, "r", encoding="utf-8") as f:
            try:
                chars.update(f.read())
            except Exception:
                pass
    return chars


def pick_face(fonts):
    """从字体集合中选择简体字面。"""
    from fontTools.ttLib import TTFont, TTCollection

    for path in fonts:
        if not os.path.exists(path):
            continue
        try:
            if path.endswith(".ttc"):
                try:
                    coll = TTCollection(path, lazy=True)
                except TypeError:
                    coll = TTCollection(path)
                best = None
                for f in coll.fonts:
                    name = f["name"].getDebugName(1) or ""
                    if "SC" in name or "Simplified" in name or "简体" in name:
                        best = (path, f, name)
                        break
                    if best is None:
                        best = (path, f, name)
                return best
            f = TTFont(path)
            return path, f, (f["name"].getDebugName(1) or "")
        except Exception as e:
            print("  跳过 %s：%s" % (path, e))
    return None, None, None


def main():
    try:
        from fontTools import subset
    except ImportError:
        print("缺少 fonttools，请先执行： pip install fonttools")
        print("（可跳过：APK 会退回系统字体）")
        return 1

    src = sys.argv[1] if len(sys.argv) > 1 else None
    candidates = [src] + SYSTEM_FONTS if src else SYSTEM_FONTS

    path, face, name = pick_face(candidates)
    if face is None:
        print("未找到中文字体，可用 --help 查看说明，或手动指定字体路径。")
        return 1
    print("源字体：%s\n字面：%s" % (path, name))

    wanted = set(gb2312_chars()) | project_chars()
    # ASCII、常用标点、音标与国际音标区块
    wanted |= set(chr(c) for c in range(0x20, 0x7F))
    wanted |= set("　、。，．！？；：（）《》【】「」『』…—～·“”‘’￥%")
    # UI 常见符号（折叠箭头、勾、星号等）——主字体缺这些会显示成方块
    wanted |= set("★☆●◆■▲▼▸▾▶◀•○□◇☀☂♪♫☺☻✓✗√←↑↓→↔≈×✎")
    wanted |= set("ʃʒθðŋɜɑɔəʊɪʌæːˈˌʧʤɒɐɘɵʁçɲʎɹɻɫʍʔħʕ"
                  "ɛɜɨøœɣβðɸχɯɰɴʙɢʀʜʟɦɬɮʋɾɽʂʐʝɟɡɱɳɵɶɹɺɻɽʞʇʈ")

    cmap = set(face.getBestCmap().keys())
    missing = sorted(c for c in wanted if ord(c) not in cmap)
    text = "".join(sorted(c for c in wanted if ord(c) in cmap))

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    options = subset.Options()
    options.layout_features = ["*"]
    options.notdef_outline = True
    options.drop_tables += ["DSIG"]
    options.name_IDs = ["*"]
    ss = subset.Subsetter(options=options)
    ss.populate(text=text)
    ss.subset(face)
    face.save(OUT)

    size = os.path.getsize(OUT) / 1024.0 / 1024.0
    print("已生成：%s（%.2f MB，包含 %d 个字形）" % (OUT, size, len(text)))
    if missing:
        print("注意：源字体缺少 %d 个字符（多为 IPA 音标），将显示为方块：%s"
              % (len(missing), "".join(missing[:60])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
