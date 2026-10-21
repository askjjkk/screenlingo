"""Онлайн-перевод: Google (основной), MyMemory (запасной), кэш.
Исходный язык можно не указывать (src="auto"): переводчик определит его сам,
а определённый язык будет в last_detected."""
import threading
from collections import Counter, OrderedDict

import requests

TIMEOUT = 8
UA = {"User-Agent": "Mozilla/5.0 ScreenLingo"}


class TranslateError(Exception):
    pass


class GoogleTranslator:
    URL = "https://translate.googleapis.com/translate_a/single"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(UA)
        self.last_detected = None

    @staticmethod
    def parse(data) -> str:
        return "".join(seg[0] for seg in data[0] if seg and seg[0])

    @staticmethod
    def parse_detected(data) -> str | None:
        return data[2] if len(data) > 2 and isinstance(data[2], str) else None

    def _request(self, text: str, src: str, dst: str) -> str:
        try:
            r = self.session.post(self.URL, params={"client": "gtx", "sl": src, "tl": dst, "dt": "t"},
                                  data={"q": text}, timeout=TIMEOUT)
            r.raise_for_status()
            data = r.json()
            self.last_detected = self.parse_detected(data) or (None if src == "auto" else src)
            return self.parse(data)
        except (requests.RequestException, ValueError, IndexError, TypeError) as e:
            raise TranslateError(str(e)) from e

    def translate(self, texts: list[str], src: str, dst: str) -> list[str]:
        if not texts:
            return []
        # одним запросом: блоки через перевод строки, внутри блоков переносов нет
        clean = [t.replace("\n", " ") for t in texts]
        parts = self._request("\n".join(clean), src, dst).split("\n")
        if len(parts) == len(clean):
            return [p.strip() for p in parts]
        return [self._request(t, src, dst).strip() for t in clean]


class MyMemoryTranslator:
    URL = "https://api.mymemory.translated.net/get"
    last_detected = None

    def _one(self, text: str, src: str, dst: str) -> str:
        pair = f"{'autodetect' if src == 'auto' else src.split('-')[0]}|{dst.split('-')[0]}"
        try:
            r = requests.get(self.URL, params={"q": text[:500], "langpair": pair}, headers=UA, timeout=TIMEOUT)
            r.raise_for_status()
            data = r.json()
            if data.get("responseStatus") not in (200, "200"):
                raise TranslateError(str(data.get("responseDetails")))
            self.last_detected = data["responseData"].get("detectedLanguage") or (None if src == "auto" else src)
            return data["responseData"]["translatedText"]
        except (requests.RequestException, ValueError, KeyError) as e:
            raise TranslateError(str(e)) from e

    def translate(self, texts: list[str], src: str, dst: str) -> list[str]:
        return [self._one(t, src, dst) for t in texts]


class FallbackTranslator:
    def __init__(self, translators):
        self.translators = translators
        self.last_detected = None

    def translate(self, texts: list[str], src: str, dst: str) -> list[str]:
        error = None
        for t in self.translators:
            try:
                out = t.translate(texts, src, dst)
                self.last_detected = getattr(t, "last_detected", None)
                return out
            except TranslateError as e:
                error = e
        raise TranslateError(f"все переводчики недоступны: {error}")


class CachedTranslator:
    """Кэш + замок: из него безопасно переводить из нескольких потоков."""

    def __init__(self, inner, maxsize: int = 512):
        self.inner = inner
        self.maxsize = maxsize
        self._cache: OrderedDict = OrderedDict()  # (текст, src, dst) -> (перевод, язык оригинала)
        self._lock = threading.Lock()

    def translate(self, texts: list[str], src: str, dst: str) -> list[str]:
        return self.translate_detect(texts, src, dst)[0]

    def translate_detect(self, texts: list[str], src: str, dst: str) -> tuple[list[str], str | None]:
        """Перевод и язык, который определил переводчик (самый частый среди строк)."""
        with self._lock:
            missing = [t for t in dict.fromkeys(texts) if (t, src, dst) not in self._cache]
            if missing:
                translated = self.inner.translate(missing, src, dst)
                detected = getattr(self.inner, "last_detected", None) or (None if src == "auto" else src)
                for t, tr in zip(missing, translated):
                    self._cache[(t, src, dst)] = (tr, detected)
                    if len(self._cache) > self.maxsize:
                        self._cache.popitem(last=False)
            out, langs = [], Counter()
            for t in texts:
                self._cache.move_to_end((t, src, dst))
                tr, lang = self._cache[(t, src, dst)]
                out.append(tr)
                if lang:
                    langs[lang] += 1
            return out, (langs.most_common(1)[0][0] if langs else None)


def default_translator() -> CachedTranslator:
    return CachedTranslator(FallbackTranslator([GoogleTranslator(), MyMemoryTranslator()]))
