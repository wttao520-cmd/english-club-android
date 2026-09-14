# -*- coding: utf-8 -*-
"""宠物养成：6 种宠物、经验升级、三段进化、积分解锁。

积分在练习/复习中产出，作为宠物粮食消耗，喂养得经验升级。
纯逻辑层，不依赖 Kivy。
"""

MAX_LEVEL = 20

# species: (中文名, 解锁积分, 主题色, 描边色)
SPECIES = {
    "cat":     ("小猫",  0,    "#f6c453", "#e0a83a"),
    "bunny":   ("兔子",  300,  "#f7a6c1", "#e58aa8"),
    "duck":    ("鸭子",  400,  "#ffd94a", "#e8b920"),
    "panda":   ("熊猫",  800,  "#f2f2f2", "#3a3f4a"),
    "fox":     ("狐狸",  1200, "#ff9257", "#e2763e"),
    "unicorn": ("独角兽", 2000, "#c9b6ff", "#a98ef0"),
}


def species_name(key):
    return SPECIES.get(key, ("宠物", 0, "#f6c453", "#e0a83a"))[0]


def colors(key):
    body, shade = SPECIES.get(key, ("", 0, "#f6c453", "#e0a83a"))[2:4]
    return body, shade


def unlock_cost(key):
    return SPECIES.get(key, (0, 1 << 30))[1]


def exp_needed(level):
    """升到 level+1 所需经验（累计式：喂一次加 exp，直接对比门槛）。"""
    return 40 + (level - 1) * 25


def stage_of(level):
    """进化阶段：0 幼年 / 1 成长 / 2 完全体。"""
    if level >= 10:
        return 2
    if level >= 5:
        return 1
    return 0


def stage_name(stage):
    return ("幼年期", "成长期", "完全体")[max(0, min(2, stage))]


class PetState(object):
    """一只宠物的完整状态（从 db 行构造）。"""

    def __init__(self, row):
        import json
        self.species = row.get("species", "cat")
        self.name = row.get("name", "团子")
        self.exp = int(row.get("exp", 0))
        try:
            self.unlocked = json.loads(row.get("unlocked", '["cat"]'))
        except Exception:
            self.unlocked = ["cat"]
        if self.species not in self.unlocked:
            self.unlocked.append(self.species)
        self.level = 1
        self._recompute_level()

    def _recompute_level(self):
        lv, exp = 1, self.exp
        while lv < MAX_LEVEL and exp >= exp_needed(lv):
            exp -= exp_needed(lv)
            lv += 1
        self.level, self.exp_in_level = lv, exp
        self.need = exp_needed(lv) if lv < MAX_LEVEL else 0

    @property
    def stage(self):
        return stage_of(self.level)

    def add_exp(self, n):
        """喂养获得经验，返回 (level_up: bool, old_stage, new_stage)。"""
        old = (self.level, self.stage)
        self.exp = max(0, self.exp + int(n))
        self._recompute_level()
        return self.level > old[0], old[1], self.stage

    def save(self):
        from . import db
        db.pet_save(self.species, self.name, self.exp, self.unlocked)


def load():
    from . import db
    return PetState(db.pet_get())
