"""LLM translation: providers + batch translate with checks.

Providers:
    anthropic  official SDK (pip install anthropic); key from settings,
               ANTHROPIC_API_KEY or an `ant auth login` profile
    openai     any OpenAI-compatible /chat/completions endpoint: OpenAI,
               OpenRouter, Ollama, LM Studio, vLLM... (plain HTTP)

Settings live in ~/.config/psptool/llm.json (0600), never in the project,
so a key does not end up in a shared folder.
"""
import json
import os
import re
import urllib.error
import urllib.request
from typing import Callable, Dict, List, Optional

from . import net

CONFIG = os.path.join(os.path.expanduser("~"), ".config", "psptool", "llm.json")

DEFAULTS = {
    "provider": "anthropic",
    "anthropic": {"api_key": "", "model": "claude-opus-5-5", "effort": "medium"},
    "openai": {"api_key": "", "base_url": "https://api.openai.com/v1", "model": "gpt-4o"},
    "batch": 30,
    "target_lang": "русский",
}

TAG = re.compile(r"\[[#0-9a-fA-F]+\]")


def load_settings() -> Dict:
    s = json.loads(json.dumps(DEFAULTS))
    try:
        with open(CONFIG, encoding="utf-8") as f:
            saved = json.load(f)
        for k, v in saved.items():
            if isinstance(v, dict) and isinstance(s.get(k), dict):
                s[k].update(v)
            else:
                s[k] = v
    except (OSError, ValueError):
        pass
    return s


def save_settings(s: Dict):
    os.makedirs(os.path.dirname(CONFIG), exist_ok=True)
    fd = os.open(CONFIG, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(s, f, ensure_ascii=False, indent=1)


def public_settings(s: Dict) -> Dict:
    """For the UI: keys are masked."""
    out = json.loads(json.dumps(s))
    for p in ("anthropic", "openai"):
        k = out[p].get("api_key", "")
        out[p]["api_key"] = ("…" + k[-4:]) if k else ""
        out[p]["has_key"] = bool(k) or bool(os.environ.get("%s_API_KEY" % p.upper()))
    return out


# --- providers ---------------------------------------------------------------

SCHEMA = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"n": {"type": "integer"}, "text": {"type": "string"}},
                "required": ["n", "text"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["items"],
    "additionalProperties": False,
}


class LLMError(Exception):
    pass


def _ask_anthropic(cfg: Dict, system: str, user: str) -> str:
    try:
        import anthropic
    except ImportError:
        raise LLMError("pip install anthropic")
    client = anthropic.Anthropic(api_key=cfg["api_key"]) if cfg.get("api_key") else anthropic.Anthropic()
    try:
        # fallbacks="default": if a safety classifier declines, the API
        # re-runs the request on a fallback model inside the same call
        resp = client.beta.messages.create(
            model=cfg.get("model") or DEFAULTS["anthropic"]["model"],
            max_tokens=16000,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            output_config={"effort": cfg.get("effort") or "medium",
                           "format": {"type": "json_schema", "schema": SCHEMA}},
            system=system,
            messages=[{"role": "user", "content": user}],
        )
    except anthropic.AuthenticationError:
        raise LLMError("Anthropic: неверный ключ")
    except anthropic.RateLimitError:
        raise LLMError("Anthropic: превышен лимит запросов, попробуй позже")
    except anthropic.APIStatusError as e:
        raise LLMError("Anthropic %s: %s" % (e.status_code, e.message))
    except anthropic.APIConnectionError:
        raise LLMError("Anthropic: нет соединения")
    if resp.stop_reason == "refusal":
        raise LLMError("модель отказалась отвечать на этот кусок")
    if resp.stop_reason == "max_tokens":
        raise LLMError("ответ обрезан (max_tokens), уменьши пачку")
    return "".join(b.text for b in resp.content if b.type == "text")


def _ask_openai(cfg: Dict, system: str, user: str) -> str:
    key = cfg.get("api_key") or os.environ.get("OPENAI_API_KEY", "")
    url = (cfg.get("base_url") or DEFAULTS["openai"]["base_url"]).rstrip("/") + "/chat/completions"
    body = {
        "model": cfg.get("model"),
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "response_format": {"type": "json_object"},
    }
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"),
                                 headers={"Content-Type": "application/json",
                                          **({"Authorization": "Bearer " + key} if key else {})})
    try:
        with net.urlopen(req, timeout=600) as r:
            data = json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise LLMError("%s %s: %s" % (url, e.code, e.read()[:300].decode("utf-8", "replace")))
    except urllib.error.URLError as e:
        raise LLMError("%s: %s" % (url, e.reason))
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError):
        raise LLMError("неожиданный ответ: %s" % json.dumps(data)[:300])


def ask(settings: Dict, system: str, user: str) -> str:
    p = settings.get("provider", "anthropic")
    if p == "anthropic":
        return _ask_anthropic(settings["anthropic"], system, user)
    if p == "openai":
        return _ask_openai(settings["openai"], system, user)
    raise LLMError("unknown provider " + p)


# --- translation -------------------------------------------------------------

SYSTEM = """Ты переводишь японскую видеоигру BLEACH ~Soul Carnival 2~ (PSP) на {lang}.
Тебе дают строки игры: оригинал (JP) и, если есть, английский фанатский перевод (EN) как подсказку. У субтитров роликов есть только EN — переводи с него. В субтитрах не ставь переносы строк, их расставит программа. Надписи на картинках (note — уточнение от переводчика, следуй ему) переводи коротко: они должны влезть на место оригинала. Переводи по смыслу оригинала, подсказку используй для понимания. Пиши естественно, как в изданной локализации: живые реплики, без канцелярита. Имена и термины — по глоссарию. Проверенные переводы — образец: те же слова, имена и обращения переводи так же, держи их стиль.

Разметка в строках — это коды движка, их надо сохранить:
- [8029], [8100] и другие [четыре hex-цифры] — команды. Перенеси каждую в перевод, в том же количестве и порядке, на соответствующее место (команды в начале — в начало, в конце — в конец).
- [#1000]…[#103f] — значки кнопок (○, ×, L, R…). Сохрани их там же по смыслу.
- [#…] с меньшим номером — японская буква, которую не распознали. Это часть японского текста: переводи по смыслу, сам тег не переноси.
- {{ и }} — выделение цветом. Сохрани пары и выдели ими то же понятие.
- Перенос строки (\\n): не больше переносов, чем в оригинале. У каждой строки есть "max" — сколько символов влезает в одну строку на экране; не превышай. Сокращай формулировку, если не влезает.
- [8010] — точка возможного переноса в японском, в переводе её можно убрать.

Верни JSON: {{"items": [{{"n": номер, "text": перевод}}, ...]}} — по одному элементу на каждую строку, номера как во входе."""


def _commands(s: str) -> List[str]:
    """Tags a translation must keep: commands [8029] and icons [#1000]+,
    not [8010] (JP line-break hint) and not raw kanji glyphs [#5c]."""
    out = []
    for t in TAG.findall(s):
        if t.lower() == "[8010]":
            continue
        if t.startswith("[#") and int(t[2:-1], 16) < 0x1000:
            continue
        out.append(t)
    return out


def check(src: str, dst: str, encode: Optional[Callable[[str], object]],
          measure: Optional[Callable[[str], List[int]]] = None, limit_px: int = 0,
          max_bytes: int = 0) -> str:
    """'' if ok, else what is wrong (in Russian, goes back to the model)."""
    if _commands(src) != _commands(dst):
        return "команды не совпадают: нужно %s, есть %s" % (" ".join(_commands(src)), " ".join(_commands(dst)))
    if src.count("{") != dst.count("{") or src.count("}") != dst.count("}"):
        return "число скобок { } не совпадает с оригиналом"
    raw = [t for t in TAG.findall(dst) if t.startswith("[#") and int(t[2:-1], 16) < 0x1000]
    if raw:
        return "убери %s — это японский знак, а не команда" % " ".join(raw)
    if dst.count("\n") > src.count("\n"):
        return "переносов строк не больше %d, а их %d" % (src.count("\n"), dst.count("\n"))
    if max_bytes and len(dst.encode("utf-8")) > max_bytes:
        return "слишком длинно: не больше %d байт UTF-8 (кириллица — 2 байта на букву), сократи" % max_bytes
    try:
        if encode:
            encode(dst)
    except ValueError as e:
        return "символ, которого нет в шрифте игры: %s — замени" % str(e).replace("no glyph for ", "")
    if measure and limit_px:
        over = [k + 1 for k, w in enumerate(measure(dst)) if w > limit_px]
        if over:
            return "строка %s не влезает на экран, сократи" % ", ".join(map(str, over))
    return ""


def _parse(text: str) -> Dict[int, str]:
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise LLMError("в ответе нет JSON")
    data = json.loads(m.group(0))
    return {int(x["n"]): x["text"] for x in data.get("items", [])}


def _grams(s: str) -> set:
    s = re.sub(r"\s+", "", TAG.sub("", s))
    return {s[k:k + 2] for k in range(len(s) - 1)} or set(s)


class Examples:
    """Checked translations, offered to the model as samples:
    for each batch the ones sharing most words with it."""

    def __init__(self, pairs: List[tuple], limit: int = 20):
        self.pool = [(src, dst, _grams(src)) for src, dst in pairs]
        self.limit = limit
        df: Dict[str, int] = {}
        for _, _, g in self.pool:
            for x in g:
                df[x] = df.get(x, 0) + 1
        # rare pieces (names, terms) weigh more than common kana like した
        self.weight = {x: 1.0 / n for x, n in df.items()}

    def pick(self, rows: List[Dict]) -> List[tuple]:
        if not self.pool:
            return []
        want = set()
        for r in rows:
            want |= _grams(r["src"])
        skip = {r["src"] for r in rows}
        scored = []
        for src, dst, g in self.pool:
            if src in skip:
                continue
            score = sum(self.weight[x] for x in g & want)
            if score:
                scored.append((score / (1 + 0.02 * len(g)), src, dst))
        scored.sort(key=lambda x: -x[0])
        return [(src, dst) for _, src, dst in scored[:self.limit]]


def _prompt(rows: List[Dict], glossary: str, notes: Dict[int, str], examples=()) -> str:
    parts = []
    if glossary.strip():
        parts.append("Глоссарий (JP / EN → перевод):\n" + glossary.strip())
    if examples:
        parts.append("Проверенные переводы:\n" + "\n".join(
            json.dumps({"jp": a, "ru": b}, ensure_ascii=False) for a, b in examples))
    lines = []
    for n, r in enumerate(rows):
        # movie subtitles: only the English (read from the patched video)
        item = {"n": n, "en": r["src"]} if r.get("sub") else {"n": n, "jp": r["src"]}
        if r.get("max_chars"):
            item["max"] = r["max_chars"]
        if r.get("max_bytes"):
            item["max_bytes"] = r["max_bytes"]
        if r.get("note"):
            item["note"] = r["note"]
        if r.get("ref"):
            item["en"] = r["ref"]
        if n in notes:
            item["fix"] = notes[n]
        lines.append(json.dumps(item, ensure_ascii=False))
    parts.append("Строки:\n" + "\n".join(lines))
    return "\n\n".join(parts)


def translate(rows: List[Dict], settings: Dict, encode: Callable[[str], object],
              glossary: str = "", measure: Optional[Callable[[str], List[int]]] = None,
              log=print, attempts: int = 3, examples: Optional[Examples] = None) -> Dict[int, str]:
    """rows: [{src, ref, limit_px?, max_chars?}] -> {index: translation};
    only results that pass `check`."""
    system = SYSTEM.format(lang=settings.get("target_lang", "русский"))
    done: Dict[int, str] = {}
    todo = list(range(len(rows)))
    notes: Dict[int, str] = {}
    samples = examples.pick(rows) if examples else []
    for attempt in range(attempts):
        if not todo:
            break
        batch = [rows[i] for i in todo]
        got = _parse(ask(settings, system, _prompt(batch, glossary, {k: notes[i] for k, i in enumerate(todo) if i in notes}, samples)))
        retry = []
        for k, i in enumerate(todo):
            text = got.get(k)
            if text is None:
                notes[i] = "строка пропущена в ответе"
                retry.append(i)
                continue
            if rows[i].get("sub") or rows[i].get("ttf"):  # drawn with a TTF: any char
                err = check(rows[i]["src"], text, None)
            elif rows[i].get("utf8"):  # system font: any char, limit in bytes
                err = check(rows[i]["src"], text, None, max_bytes=rows[i].get("max_bytes", 0))
            else:
                err = check(rows[i]["src"], text, encode, measure, rows[i].get("limit_px", 0))
            if err:
                notes[i] = "прошлый вариант «%s» не подошёл: %s" % (text, err)
                retry.append(i)
            else:
                done[i] = text
        todo = retry
    for i in todo:
        log("  не вышло: %s — %s" % (rows[i]["src"][:40].replace("\n", " "), notes.get(i, "")))
    return done
