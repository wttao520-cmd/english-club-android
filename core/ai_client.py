"""AI 客户端：OpenAI 兼容接口，用于翻译、语法讲解、自动拆句。

支持 DeepSeek / OpenAI / 通义千问 / 月之暗面 / 本地 Ollama 等，
只需在设置里填写 base_url、api_key 与 model。
"""

import hashlib
import json
import re

import requests

from . import db

TIMEOUT = 60


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
        key = "chat:" + _md5((system or "") + "||" + (user or "") + "||" +
                             str(self.config.get("ai_model")))
        if use_cache:
            cached = db.cache_get(key)
            if cached is not None:
                return cached

        if not self.config.get("ai_api_key"):
            raise AIError("尚未配置 AI API Key，请在「设置」中填写。")

        base = (self.config.get("ai_base_url") or "").rstrip("/")
        if not base:
            raise AIError("尚未配置 AI 接口地址。")
        url = base + "/chat/completions"

        payload = {
            "model": self.config.get("ai_model") or "deepseek-chat",
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
            "stream": False,
        }
        headers = {
            "Authorization": "Bearer " + self.config.get("ai_api_key", ""),
            "Content-Type": "application/json",
        }
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=TIMEOUT)
        except Exception as e:
            raise AIError("网络请求失败：%s" % e)

        if resp.status_code != 200:
            raise AIError("AI 接口返回 %s：%s" % (resp.status_code, resp.text[:300]))

        try:
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
        except Exception:
            raise AIError("解析 AI 返回结果失败：%s" % resp.text[:300])

        content = (content or "").strip()
        if use_cache:
            db.cache_put(key, content)
        return content

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

    def ask(self, question, context=""):
        system = "你是英语学习助手，用中文简洁回答问题（200 字以内）。"
        user = "上下文：\n%s\n\n问题：%s" % (context or "无", question)
        return self.chat(system, user, temperature=0.5)


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
