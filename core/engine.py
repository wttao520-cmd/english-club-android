"""练习引擎：逐字符输入、连击、评分、计时。"""

import time

RATING_LABEL = {5: "Perfect", 4: "Great", 3: "Good", 0: "Again"}


def rate(errors, backspaces=0):
    """按错误次数给出评级 0/3/4/5。"""
    if errors == 0 and backspaces == 0:
        return 5
    if errors <= 1:
        return 4
    if errors <= 4:
        return 3
    return 0


class TypingState(object):
    """单句输入状态机。

    buffer 保存用户实际输入；与 target 的最长公共前缀即已确认正确的部分，
    之后的部分视为错误（显示为红色，需退格修正后才能继续）。
    """

    def __init__(self, target):
        self.target = target
        self.buffer = ""
        self.keystrokes = 0
        self.errors = 0
        self.backspaces = 0
        self.combo = 0
        self.combo_max = 0
        self.started_at = None
        self.finished_at = None
        self.practiced_any = False
        self.skipped = False

    # ---------------------------------------------------------- 状态
    @property
    def ok_len(self):
        n = 0
        for a, b in zip(self.buffer, self.target):
            if a == b:
                n += 1
            else:
                break
        return n

    @property
    def cursor(self):
        return len(self.buffer)

    @property
    def finished(self):
        return self.buffer == self.target

    @property
    def has_error(self):
        return self.ok_len < len(self.buffer)

    def type_char(self, ch):
        if self.started_at is None:
            self.started_at = time.time()
        self.keystrokes += 1
        if self.cursor >= len(self.target):
            self.errors += 1
            self.combo = 0
            return False
        self.buffer += ch
        if self.buffer[-1] == self.target[len(self.buffer) - 1] and self.ok_len == len(self.buffer):
            self.combo += 1
            self.combo_max = max(self.combo_max, self.combo)
            return True
        self.errors += 1
        self.combo = 0
        return False

    def backspace(self):
        if self.buffer:
            self.buffer = self.buffer[:-1]
            self.backspaces += 1
            self.keystrokes += 1
            return True
        return False

    def sync(self, new_text):
        """把输入框的文本同步为状态（软键盘一次性给出整段文本时使用）。

        从公共前缀处回退，再逐字重放，保证 ok_len / errors / combo 与逐键输入一致。
        """
        new_text = new_text or ""
        if new_text == self.buffer:
            return
        i = 0
        while i < min(len(self.buffer), len(new_text)) and self.buffer[i] == new_text[i]:
            i += 1
        for _ in range(len(self.buffer) - i):
            self.backspace()
        for ch in new_text[i:]:
            self.type_char(ch)

    def reset(self):
        self.buffer = ""
        self.combo = 0

    # ---------------------------------------------------------- 结算
    def finish(self):
        self.finished_at = time.time()

    @property
    def duration(self):
        if self.started_at is None:
            return 0.0
        end = self.finished_at or time.time()
        return max(0.001, end - self.started_at)

    @property
    def wpm(self):
        # 未输入任何字符（如直接跳过）时 duration=0，必须返回 0 而不是除零
        d = self.duration
        if d <= 0:
            return 0.0
        return (len(self.target) / 5.0) / (d / 60.0)

    @property
    def accuracy(self):
        if self.keystrokes == 0:
            return 100.0
        return max(0.0, 100.0 * (1 - self.errors / float(self.keystrokes)))

    @property
    def rating(self):
        if self.skipped:
            return 0   # 跳过计 Again，SRS 会重新安排复习
        return rate(self.errors, self.backspaces)

    def score(self):
        if self.skipped:
            return 0   # 跳过不得分
        base = len(self.target) * 10
        bonus = self.combo_max * 5 + (200 if self.rating == 5 else 0)
        penalty = self.errors * 20
        return max(10, base + bonus - penalty)


class Session(object):
    """一关练习：管理句子队列、累计数据与进度。"""

    def __init__(self, sentences, title="练习", sound_cb=None):
        self.sentences = list(sentences)
        self.title = title
        self.sound_cb = sound_cb
        self.index = -1
        self.total_score = 0
        self.total_chars = 0
        self.total_errors = 0
        self.combo_max = 0
        self.perfect = 0
        self.started_at = time.time()
        self.state = None
        self.results = []

    @property
    def total(self):
        return len(self.sentences)

    @property
    def done(self):
        return self.index + 1

    def next(self):
        self.index += 1
        if self.index >= self.total:
            self.state = None
            return None
        self.state = TypingState(self.sentences[self.index]["en"])
        return self.state

    @property
    def current(self):
        if 0 <= self.index < self.total:
            return self.sentences[self.index]
        return None

    @property
    def finished(self):
        return self.index >= self.total - 1 and self.state is not None and self.state.finished

    def commit_current(self):
        """结算当前句子，返回结算字典。幂等：同一句只结算一次。"""
        st = self.state
        if st is None or not st.finished:
            return None
        if getattr(st, "committed", False):
            return None   # 防重入：auto_next 清空输入框时会二次触发
        st.committed = True
        st.finish()
        r = {
            "sentence": self.current,
            "rating": st.rating,
            "wpm": st.wpm,
            "accuracy": st.accuracy,
            "combo_max": st.combo_max,
            "errors": st.errors,
            "duration": st.duration,
            "score": st.score(),
        }
        self.results.append(r)
        self.total_score += r["score"]
        self.total_chars += len(st.target)
        self.total_errors += st.errors
        self.combo_max = max(self.combo_max, st.combo_max)
        if r["rating"] == 5:
            self.perfect += 1
        return r

    @property
    def elapsed(self):
        return time.time() - self.started_at

    def summary(self):
        n = max(1, len(self.results))
        return {
            "title": self.title,
            "sentences": len(self.results),
            "score": self.total_score,
            "accuracy": sum(x["accuracy"] for x in self.results) / n,
            "wpm": sum(x["wpm"] for x in self.results) / n,
            "combo_max": self.combo_max,
            "perfect": self.perfect,
            "elapsed": self.elapsed,
        }
