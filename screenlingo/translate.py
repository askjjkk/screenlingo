"""Онлайн-перевод: Google (основной), MyMemory (запасной), кэш."""
from collections import OrderedDict

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

    @staticmethod
    def parse(data) -> str:
        return "".join(seg[0] for seg in data[0] if seg and seg[0])

    def _request(self, text: str, src: str, dst: str) -> str:
        try:
            r = self.session.post(self.URL, params={"client": "gtx", "sl": src, "tl": dst, "dt": "t"},
                                  data={"q": text}, timeout=TIMEOUT)
            r.raise_for_status()
            return self.parse(r.json())
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

    def _one(self, text: str, src: str, dst: str) -> str:
        pair = f"{'autodetect' if src == 'auto' else src.split('-')[0]}|{dst.split('-')[0]}"
        try:
            r = requests.get(self.URL, params={"q": text[:500], "langpair": pair}, headers=UA, timeout=TIMEOUT)
            r.raise_for_status()
            data = r.json()
            if data.get("responseStatus") not in (200, "200"):
                raise TranslateError(str(data.get("responseDetails")))
            return data["responseData"]["translatedText"]
        except (requests.RequestException, ValueError, KeyError) as e:
            raise TranslateError(str(e)) from e

    def translate(self, texts: list[str], src: str, dst: str) -> list[str]:
        return [self._one(t, src, dst) for t in texts]


class FallbackTranslator:
    def __init__(self, translators):
        self.translators = translators

    def translate(self, texts: list[str], src: str, dst: str) -> list[str]:
        error = None
        for t in self.translators:
            try:
                return t.translate(texts, src, dst)
            except TranslateError as e:
                error = e
        raise TranslateError(f"все переводчики недоступны: {error}")


class CachedTranslator:
    def __init__(self, inner, maxsize: int = 512):
        self.inner = inner
        self.maxsize = maxsize
        self._cache: OrderedDict = OrderedDict()

    def translate(self, texts: list[str], src: str, dst: str) -> list[str]:
        missing = [t for t in dict.fromkeys(texts) if (t, src, dst) not in self._cache]
        if missing:
            for t, tr in zip(missing, self.inner.translate(missing, src, dst)):
                self._cache[(t, src, dst)] = tr
                if len(self._cache) > self.maxsize:
                    self._cache.popitem(last=False)
        out = []
        for t in texts:
            self._cache.move_to_end((t, src, dst))
            out.append(self._cache[(t, src, dst)])
        return out


def default_translator() -> CachedTranslator:
    return CachedTranslator(FallbackTranslator([GoogleTranslator(), MyMemoryTranslator()]))
