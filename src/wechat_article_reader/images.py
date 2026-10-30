"""Download article images locally and rewrite Markdown links to the local files.

mmbiz.qpic.cn serves a "此图片来自微信公众平台，未经允许不可引用" placeholder when
it sees a foreign Referer, so we request without one.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import httpx

from .fetcher import DESKTOP_UA
from .parser import Article

_EXT = {"jpeg": "jpg", "jpg": "jpg", "png": "png", "gif": "gif", "webp": "webp", "svg": "svg", "bmp": "bmp"}


def _ext(url: str, content_type: str) -> str:
    fmt = parse_qs(urlsplit(url).query).get("wx_fmt", [""])[0].lower()
    if fmt in _EXT:
        return _EXT[fmt]
    sub = content_type.split("/")[-1].split(";")[0].lower()
    return _EXT.get(sub, "jpg")


def download_images(article: Article, out_dir: str | Path, timeout: float = 20.0) -> Article:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    mapping: dict[str, str] = {}
    with httpx.Client(headers={"User-Agent": DESKTOP_UA}, follow_redirects=True, timeout=timeout) as client:
        for i, url in enumerate(dict.fromkeys(article.images), 1):
            try:
                resp = client.get(url)
                resp.raise_for_status()
            except httpx.HTTPError:
                continue
            name = f"{i:03d}_{hashlib.md5(url.encode()).hexdigest()[:8]}.{_ext(url, resp.headers.get('content-type', ''))}"
            (out / name).write_bytes(resp.content)
            mapping[url] = str(out / name)

    def repl(m: re.Match) -> str:
        return f"![{m.group(1)}]({mapping.get(m.group(2), m.group(2))})"

    article.markdown = re.sub(r"!\[([^\]]*)\]\(([^)\s]+)\)", repl, article.markdown)
    article.images = [mapping.get(u, u) for u in article.images]
    return article
