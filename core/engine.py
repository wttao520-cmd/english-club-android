"""练习引擎：逐字符输入、连击、评分、计时。"""

import random
import re
import time

RATING_LABEL = {5: "Perfect", 4: "Great", 3: "Good", 0: "Again"}

WORD_RE = re.compile(r"[A-Za-z][A-Za-z'\-]*")


def split_words(text):
    """按英文词切分句子，返回 [(词, 词后空白)] 列表（保留原始标点/空格）。

    选词模式用它把句子拆成可点击的词块：标点跟随前一个词（"don't," 整体），
    空白单独挂在该词之后，拼回时逐字拼接即等于原句。
    """
    out = []
    last = 0
    for m in WORD_RE.finditer(text or ""):
        if m.start() > last:
            # 前一个词与当前词之间是标点/空格 → 归到前一个词尾
            if out:
                out[-1][1] += text[last:m.start()]
            else:
                out.append(["", text[last:m.start()]])
        out.append([m.group(), ""])
        last = m.end()
    if last < len(text or ""):
        if out:
            out[-1][1] += text[last:]
        else:
            out.append(["", text[last:]])
    # 丢弃纯空白首块
    if out and not out[0][0]:
        lead = out.pop(0)
        if out:
            out[0][1] = lead[1] + out[0][1]
    return [(w, sp) for w, sp in out if w]


def pick_distractors(pool, exclude, count, rng=None):
    """从 pool 中取 count 个不在 exclude 里的干扰词（去重、打乱）。

    词汇课程选词时用：混入少量「本句没有的词」增加辨识难度，
    否则候选里只有正确答案，选择就失去意义。
    """
    rnd = rng or random
    low = set((w or "").lower() for w in exclude)
    cand = []
    seen = set()
    for w in pool:
        w = (w or "").strip()
        if not w or w.lower() in low or w.lower() in seen:
            continue
        seen.add(w.lower())
        cand.append(w)
    rnd.shuffle(cand)
    return cand[:max(0, count)]


def shuffled_indices(n, rng=None):
    """生成 0..n-1 的乱序索引（n<=1 时原样返回），尽量不等于顺序。"""
    idx = list(range(n))
    if n <= 1:
        return idx
    rnd = rng or random
    for _ in range(8):
        rnd.shuffle(idx)
        if idx != list(range(n)):
            break
    return idx


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

    def __init__(self, target, auto_space=False):
        self.target = target
        self.auto_space = auto_space   # 单词模式：单词打完自动补空格
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

    def _auto_fill_spaces(self):
        """单词模式：把用户未输入的空格自动补齐（不计错误、不计连击）。

        仅当 buffer 已与 target 前缀一致、且下一个字符为空格时才补，
        保证「打完单词自动跳到下一个词」。
        """
        if not self.auto_space:
            return
        while self.ok_len == len(self.buffer) and \
                len(self.buffer) < len(self.target) and \
                self.target[len(self.buffer)] == " ":
            self.buffer += " "

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
        # 单词模式：空格已由 _auto_fill_spaces 补好，用户再敲空格视为已完成，
        # 直接忽略（不计错误、不计按键），避免软键盘回传空格被判错。
        if self.auto_space and ch == " " and self.cursor < len(self.target) \
                and self.target[self.cursor] == " ":
            return True
        self.keystrokes += 1
        if self.cursor >= len(self.target):
            self.errors += 1
            self.combo = 0
            return False
        self.buffer += ch
        if self.buffer[-1] == self.target[len(self.buffer) - 1] and self.ok_len == len(self.buffer):
            self.combo += 1
            self.combo_max = max(self.combo_max, self.combo)
            self._auto_fill_spaces()
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
        if self.auto_space:
            # 单词模式：用户输入不含自动补的空格。把去空格文本作为「已确认
            # 前缀」，从公共前缀处回退后重放，自动空格由 _auto_fill_spaces 补。
            new_text = new_text.replace(" ", "")
            cur = self.buffer.replace(" ", "")
            if new_text == cur:
                return
            i = 0
            while i < min(len(cur), len(new_text)) and cur[i] == new_text[i]:
                i += 1
            for _ in range(len(cur) - i):
                self.backspace()
            for ch in new_text[i:]:
                self.type_char(ch)
            return
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


class ChoiceState(object):
    """选词模式状态机（手机端免键盘）。

    复用 TypingState 的 buffer/评分逻辑：每选中一个正确的词，就把该词的文本
    追加进 buffer，因此 finished / rating / score 全部与打字模式一致。

    mode="word" 时 target 为单个单词，只需选出一个正确项；
    mode="sentence" 时 target 为整句，需按顺序把所有词选完。
    """

    def __init__(self, target, mode="sentence", rng=None):
        self.target = target
        self.mode = mode
        self.rng = rng
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
        self.last_wrong = False
        self.wrong_text = None

        if mode == "word":
            self.words = [(target, "")]
        else:
            self.words = split_words(target)
        self._prefix = [""]
        for w, sp in self.words:
            self._prefix.append(self._prefix[-1] + w + sp)
        self._fp = [""]          # 不含词尾空白的拼接（用于 placed 判定）
        for w, _sp in self.words:
            self._fp.append(self._fp[-1] + w)

    # ---------------------------------------------------------- 状态
    @property
    def n_words(self):
        return len(self.words)

    @property
    def placed(self):
        """已正确填入的词数（buffer 与逐词拼接前缀的最长匹配）。

        _prefix 单调递增，故取最长的 i 使 buffer == _prefix[i+1]；
        不能遇到 i=0 不匹配就 break（buffer 比第一个前缀长时会在 i=0 断掉）。
        """
        n = 0
        for i in range(self.n_words):
            if self.buffer == self._prefix[i + 1]:
                n = i + 1
            elif len(self.buffer) > len(self._prefix[i + 1]):
                # buffer 已超过该前缀，继续往后找（不回退）
                continue
            else:
                break
        return n

    @property
    def finished(self):
        return self.n_words > 0 and self.buffer == self._prefix[-1]

    @property
    def ok_len(self):
        return len(self.buffer)

    @property
    def cursor(self):
        return len(self.buffer)

    @property
    def has_error(self):
        return self.last_wrong

    # ---------------------------------------------------------- 交互
    def _touch(self):
        if self.started_at is None:
            self.started_at = time.time()

    def pick_word(self, text):
        """尝试把词 text 填入下一个空位；返回 True 表示正确。"""
        self._touch()
        self.keystrokes += 1
        self.last_wrong = False
        self.wrong_text = None
        i = self.placed
        if i >= self.n_words:
            return False
        # 允许词与后续标点/空格一起匹配（如 "you?"）
        if text == self.words[i][0]:
            self.buffer = self._prefix[i + 1]
            self.combo += 1
            self.combo_max = max(self.combo_max, self.combo)
            return True
        self.errors += 1
        self.combo = 0
        self.last_wrong = True
        self.wrong_text = text
        return False

    def pick_option(self, text, correct_zh=None):
        """单词模式四选一：text 命中英文单词或中文释义即算对。"""
        self._touch()
        self.keystrokes += 1
        self.last_wrong = False
        if text == self.target or (correct_zh and text == correct_zh):
            self.buffer = self.target
            self.combo += 1
            self.combo_max = max(self.combo_max, self.combo)
            return True
        self.errors += 1
        self.combo = 0
        self.last_wrong = True
        return False

    def undo(self):
        """取回最后一个已填入的词。"""
        n = self.placed
        if n <= 0:
            return False
        self.buffer = self._prefix[n - 1]
        self.backspaces += 1
        return True

    def reset(self):
        self.buffer = ""
        self.combo = 0
        self.last_wrong = False
        self.wrong_text = None

    def sync(self, new_text):
        """兼容 TypingState 接口（冒烟测试/兜底），直接整句同步。"""
        new_text = new_text or ""
        if new_text == self.buffer:
            return
        self._touch()
        self.buffer = new_text

    # ---------------------------------------------------------- 结算（同打字模式）
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
            return 0
        return rate(self.errors, self.backspaces)

    def score(self):
        if self.skipped:
            return 0
        base = len(self.target) * 10
        bonus = self.combo_max * 5 + (200 if self.rating == 5 else 0)
        penalty = self.errors * 20
        return max(10, base + bonus - penalty)


class Session(object):
    """一关练习：管理句子队列、累计数据与进度。"""

    def __init__(self, sentences, title="练习", sound_cb=None, mode="typing"):
        self.sentences = list(sentences)
        self.title = title
        self.sound_cb = sound_cb
        self.mode = mode
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
        target = self.sentences[self.index]["en"]
        if self.mode == "choice":
            # 选词模式：按顺序点选词块拼出整句
            self.state = ChoiceState(target, "sentence")
        else:
            # 单词模式：单词打完自动补空格
            self.state = TypingState(target, auto_space=(self.mode == "word"))
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
