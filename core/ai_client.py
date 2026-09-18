"""AI 客户端：OpenAI 兼容接口，用于翻译、语法讲解、自动拆句。

支持 DeepSeek / OpenAI / 通义千问 / 月之暗面 / 本地 Ollama 等，
只需在设置里填写 base_url、api_key 与 model。
"""

import hashlib
import json
import re

import time

import requests

from . import db

TIMEOUT = 90


class AIError(Exception):
    pass


def _md5(text):
    return hashlib.md5(text.encode("utf-8")).hexdigest()


class AIClient(object):
    def __init__(self, config):
        self.config = config

    @property
    def enabled(self):
        return bool(self.config.get("ai_enabled")) and bool(self.config.get("ai_api_key"))

    def chat(self, system, user, temperature=0.3, use_cache=True):
        """调用一次对话，返回字符串结果。"""
        return self.chat_messages(
            [{"role": "system", "content": system or ""},
             {"role": "user", "content": user or ""}],
            temperature, use_cache)

    def chat_messages(self, messages, temperature=0.3, use_cache=False):
        """多轮对话：messages 为 [{"role": ..., "content": ...}, ...]。"""
        if not self.config.get("ai_api_key"):
            raise AIError("尚未配置 AI API Key，请在「设置」中填写。")

        base = (self.config.get("ai_base_url") or "").rstrip("/")
        if not base:
            raise AIError("尚未配置 AI 接口地址。")
        url = base + "/chat/completions"

        payload = {
            "model": self.config.get("ai_model") or "deepseek-chat",
            "messages": messages,
            "temperature": temperature,
            "stream": False,
        }
        headers = {
            "Authorization": "Bearer " + self.config.get("ai_api_key", ""),
            "Content-Type": "application/json",
        }
        # 网络抖动/限流时重试（最多 3 次，退避 1s/2s）
        resp = None
        last_err = None
        for attempt in range(3):
            try:
                resp = requests.post(url, headers=headers, json=payload,
                                     timeout=TIMEOUT)
            except Exception as e:
                last_err = e
                time.sleep(1.0 * (attempt + 1))
                continue
            if resp.status_code in (429, 500, 502, 503, 504):
                last_err = "HTTP %s" % resp.status_code
                time.sleep(1.0 * (attempt + 1))
                continue
            break
        if resp is None:
            raise AIError("网络请求失败（已重试）：%s" % last_err)

        if resp.status_code != 200:
            raise AIError("AI 接口返回 %s：%s" % (resp.status_code, resp.text[:300]))

        try:
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
        except Exception:
            raise AIError("解析 AI 返回结果失败：%s" % resp.text[:300])

        return (content or "").strip()

    # ------------------------------------------------------------ 具体能力
    def translate(self, text):
        system = "你是英中翻译助手。只输出中文译文，不要解释、不要引号、不要多余内容。"
        return self.chat(system, text, temperature=0.1)

    def explain(self, sentence, question=None, translation=None):
        system = (
            "你是一位耐心的英语老师，面向中国学习者讲解英文句子。"
            "用中文回答，结构清晰、简洁（300 字以内），重点讲清语法点、搭配与易错处。"
        )
        user = "句子：%s\n" % sentence
        if translation:
            user += "参考译文：%s\n" % translation
        user += "问题：%s" % (question or "请讲解这个句子的语法和用法。")
        return self.chat(system, user, temperature=0.4)

    def split(self, text, title=""):
        """把一段英文拆成可练习的句子，返回 [(en, zh), ...]。"""
        system = (
            "你把任意英文材料拆分成便于打字练习的短句。"
            "严格只输出 JSON 数组，元素形如 {\"en\":\"...\",\"zh\":\"...\"}，不要任何解释或代码块标记。"
            "每个句子长度 4~20 个单词，保留原文用词，不要改写；译文准确通顺。"
        )
        user = "材料标题：%s\n\n%s" % (title or "未命名", text[:6000])
        raw = self.chat(system, user, temperature=0.2)
        return _parse_pairs(raw)

    def generate_course(self, topic, level="初级", count=20, style="", progress=None):
        """按主题生成一整门「句子」课程，返回 [(en, zh), ...]。

        topic 例如「机场值机」「点咖啡」；level 为初级/中级/高级；
        count 为句子数量（5~5000，超大时自动分批生成）。
        """
        count = max(5, min(5000, int(count or 20)))
        system = (
            "你是英语课程设计助手。根据用户给的主题，生成一组循序渐进的英文学习句子。"
            "严格只输出 JSON 数组，元素形如 {\"en\":\"...\",\"zh\":\"...\"}，"
            "不要任何解释、标题或代码块标记。"
            "要求：句子由易到难；每句 3~16 个单词；地道、无明显语法错误；"
            "中文译文准确、简洁；避免重复句式。"
        )
        return self._generate_batched(
            system, topic, level, count, style,
            item_hint="句子", key_en="en", key_zh="zh", progress=progress)

    def generate_vocab(self, topic, level="初级", count=20, style="", progress=None):
        """按主题生成一整门「词汇」课程，返回 [(word, zh, note), ...]。

        note 为多行文本，格式与内置词汇课一致：
            音标：...
            例句：...
            译文：...
            讲解：...
        count 为词汇数量（5~5000，超大时自动分批生成）。
        """
        count = max(5, min(5000, int(count or 20)))
        system = (
            "你是英语词汇课程设计助手。根据用户给的主题，生成一组循序渐进的英文单词。"
            "严格只输出 JSON 数组，元素形如："
            '{"word":"apple","zh":"苹果","ipa":"/ˈæpl/",'
            '"ex":"I eat an apple.","ex_zh":"我吃一个苹果。","tip":"常见水果"}'
            "。不要任何解释、标题或代码块标记。"
            "要求：单词为常用词、难度由易到难、不重复；"
            "ipa 用国际音标并加斜杠；ex 为 3~12 词的简单例句；"
            "ex_zh 为例句中文翻译；tip 为一句话中文讲解（10 字以内）。"
        )
        raw_items = self._generate_batched(
            system, topic, level, count, style,
            item_hint="单词", key_en="word", key_zh="zh",
            extra_keys=("ipa", "ex", "ex_zh", "tip"), return_dicts=True,
            progress=progress)
        out = []
        for d in raw_items:
            word = (d.get("word") or "").strip()
            if not word:
                continue
            zh = (d.get("zh") or "").strip()
            note = self._format_vocab_note(d)
            out.append((word, zh, note))
        return out[:count]

    @staticmethod
    def _format_vocab_note(d):
        """把结构化词汇字段拼成内置词汇课一致的 note 文本。"""
        lines = []
        if d.get("ipa"):
            lines.append("音标：%s" % d["ipa"])
        if d.get("ex"):
            lines.append("例句：%s" % d["ex"])
        if d.get("ex_zh"):
            lines.append("译文：%s" % d["ex_zh"])
        if d.get("tip"):
            lines.append("讲解：%s" % d["tip"])
        return "\n".join(lines)

    def _generate_batched(self, system, topic, level, count, style,
                          item_hint="条目", batch=50, key_en="en", key_zh="zh",
                          extra_keys=(), return_dicts=False, progress=None):
        """分批调用 AI 生成，支持最多 5000 条（避免单次请求过大/超时）。"""
        batch = max(10, min(200, int(batch)))
        need = min(5000, max(1, int(count)))
        out = []
        seen = set()
        guard = 0
        fail_streak = 0
        while len(out) < need and guard < 300:
            guard += 1
            n = min(batch, need - len(out))
            user = ("主题：%s\n难度：%s\n%s数量：%d\n%s"
                    % (topic, level, item_hint, n,
                       ("风格要求：" + style) if style else ""))
            if out:
                user += "\n（请继续生成不同的%s，不要与已生成内容重复）" % item_hint
            try:
                raw = self.chat(system, user, temperature=0.7)
            except Exception:
                # 单批失败：重试一次，仍失败则停止（保留已生成的部分）
                fail_streak += 1
                if fail_streak >= 2:
                    break
                continue
            got = _parse_dicts(raw, (key_en, key_zh) + tuple(extra_keys))
            # 去重（按主键），避免模型重复输出导致数量虚高
            fresh = []
            for d in got:
                k = d.get(key_en, "").lower()
                if k and k not in seen:
                    seen.add(k)
                    fresh.append(d)
            if not fresh:
                fail_streak += 1
                if fail_streak >= 2:
                    break
                continue
            fail_streak = 0
            out.extend(fresh)
            if progress:
                try:
                    progress(len(out), need)
                except Exception:
                    pass
        if return_dicts:
            return out[:need]
        return [(d.get(key_en, "").strip(), d.get(key_zh, "").strip())
                for d in out[:need] if d.get(key_en)]

    def ask(self, question, context=""):
        system = "你是英语学习助手，用中文简洁回答问题（200 字以内）。"
        user = "上下文：\n%s\n\n问题：%s" % (context or "无", question)
        return self.chat(system, user, temperature=0.5)


def _parse_dicts(raw, keys):
    """从模型输出中提取对象数组，返回 [{key: val, ...}, ...]。

    容错处理：去掉 ```json 代码块标记；截取最外层 []；若整体解析失败，
    则逐行尝试解析单个对象（应对模型漏掉逗号/被截断的情况）。
    """
    raw = (raw or "").strip()
    raw = re.sub(r"^```(?:json)?", "", raw).strip()
    raw = re.sub(r"```$", "", raw).strip()
    start, end = raw.find("["), raw.rfind("]")
    if start >= 0 and end > start:
        body = raw[start:end + 1]
    else:
        body = raw
    data = None
    try:
        data = json.loads(body)
    except Exception:
        # 回退：逐个大括号对象解析
        data = []
        for m in re.finditer(r"\{[^{}]*\}", body):
            try:
                data.append(json.loads(m.group()))
            except Exception:
                continue
    if not isinstance(data, list):
        return []
    out = []
    for item in data:
        if not isinstance(item, dict):
            continue
        d = {}
        for k in keys:
            v = item.get(k)
            if v is None and k == "zh":
                v = item.get("cn") or item.get("trans")
            d[k] = ("" if v is None else str(v)).strip()
        # 至少要有一个主键非空
        if d.get(keys[0]):
            out.append(d)
    return out


def _parse_pairs(raw):
    """从模型输出中提取 JSON 数组。"""
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?", "", raw).strip()
    raw = re.sub(r"```$", "", raw).strip()
    start, end = raw.find("["), raw.rfind("]")
    if start >= 0 and end > start:
        raw = raw[start:end + 1]
    try:
        data = json.loads(raw)
    except Exception:
        raise AIError("AI 返回的内容不是合法 JSON，请重试。\n\n%s" % raw[:300])

    out = []
    for item in data:
        if isinstance(item, dict):
            en = (item.get("en") or "").strip()
            zh = (item.get("zh") or "").strip()
        elif isinstance(item, str):
            en, zh = item.strip(), ""
        else:
            continue
        if en:
            out.append((en, zh))
    if not out:
        raise AIError("AI 没有解析出任何句子。")
    return out
