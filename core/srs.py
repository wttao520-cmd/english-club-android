"""SM-2 间隔重复算法（简化版）。"""

import datetime

DAY = datetime.timedelta(days=1)


def today_str():
    return datetime.date.today().isoformat()


def _now_str():
    return datetime.datetime.now().isoformat(timespec="seconds")


class Card(object):
    """一条待复习记录，对应一个句子。"""

    def __init__(self, id=None, sentence_id=None, ease=2.5, interval=0.0,
                 reps=0, lapses=0, due=None, last_review=None):
        self.id = id
        self.sentence_id = sentence_id
        self.ease = ease
        self.interval = interval
        self.reps = reps
        self.lapses = lapses
        self.due = due or today_str()
        self.last_review = last_review

    @property
    def is_due(self):
        try:
            return datetime.date.fromisoformat(self.due) <= datetime.date.today()
        except Exception:
            return True

    def to_row(self):
        return (self.sentence_id, self.ease, self.interval, self.reps,
                self.lapses, self.due, self.last_review)


def schedule(card, quality):
    """根据作答质量(0-5)更新卡片的间隔与难度系数，返回更新后的卡片。"""
    q = max(0, min(5, int(quality)))

    if q < 3:
        card.reps = 0
        card.lapses += 1
        card.interval = 0.0            # 当天再来一次
        card.due = today_str()
    else:
        if card.reps == 0:
            card.interval = 1.0
        elif card.reps == 1:
            card.interval = 6.0
        else:
            card.interval = round(card.interval * card.ease, 2)
        card.reps += 1
        card.ease = round(max(1.3, card.ease + (0.1 - (5 - q) * (0.08 + (5 - q) * 0.02))), 4)
        card.due = (datetime.date.today() + datetime.timedelta(days=card.interval)).isoformat()

    card.last_review = _now_str()
    return card


def rating_to_quality(rating):
    """把练习评级映射为 SM-2 的 quality。"""
    return {0: 0, 3: 3, 4: 4, 5: 5}.get(int(rating), 4)


def next_intervals(card):
    """返回 (Again, Hard, Good, Perfect) 四个按钮对应的下一次间隔文案。"""
    def fmt(days):
        if days < 1:
            return "今天"
        if days < 30:
            return "%d 天" % round(days)
        return "%.1f 月" % (days / 30.0)

    return (
        fmt(0),
        fmt(max(1.0, card.interval * 0.5)),
        fmt(1.0 if card.reps == 0 else (6.0 if card.reps == 1 else card.interval * card.ease)),
        fmt(6.0 if card.reps <= 1 else card.interval * card.ease * 1.3),
    )
