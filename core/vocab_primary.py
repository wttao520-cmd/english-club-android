# -*- coding: utf-8 -*-
"""小学阶段核心词汇库：按主题分组，覆盖约 550 个课标词。

来源：义务教育英语课程标准（二级）核心词表，参照人教/外研/译林主流教材。
每套主题作为一门内置课程写入数据库，以"单词模式"练习：
  - en   = 单词（练习目标）
  - zh   = 词性 + 词义
  - note = 例句 + 译文 + 用法讲解（练习页提示栏显示）
"""

from .vocab_p1 import GROUPS as _G1
from .vocab_p2 import GROUPS as _G2
from .vocab_p3 import GROUPS as _G3
from .vocab_p4 import GROUPS as _G4

_ALL_GROUPS = _G1 + _G2 + _G3 + _G4


def _note(ex, ex_zh, tip):
    return "例句：%s\n%s\n讲解：%s" % (ex, ex_zh, tip)


# 与 courses_builtin.COURSES 同构：直接进 seed()。
VOCAB_COURSES = [
    {
        "key": "vocab_" + g["key"],
        "title": g["title"],
        "level": "初级",
        "desc": g["desc"],
        "items": [
            (w, zh, _note(ex, ex_zh, tip))
            for (w, zh, ex, ex_zh, tip) in g["items"]
        ],
    }
    for g in _ALL_GROUPS
]

WORD_COUNT = sum(len(g["items"]) for g in _ALL_GROUPS)
