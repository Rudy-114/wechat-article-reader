"""Fetch WeChat Official Account (公众号) article pages from the local machine.

Why this works: mp.weixin.qq.com article pages are public, but WeChat shows a
"环境异常 / 完成验证后即可继续访问" page to datacenter IPs and to clients that
don't look like a browser. Most agents fetch the web from a cloud server, so
they hit that page. Fetching from the user's own network with ordinary browser
headers returns the real article.

This module does NOT try to solve or bypass any verification. If WeChat asks for
verification even locally, we report it and (optionally) open a real browser
window so the human can complete it themselves.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx

DESKTOP_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
)

DEFAULT_HEADERS = {
    "User-Agent": DESKTOP_UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

ALLOWED_HOSTS = {"mp.weixin.qq.com"}

_URL_RE = re.compile(r"(?:https?://)?mp\.weixin\.qq\.com/[^\s<>\"'）)】]+", re.I)


class PageStatus(str, Enum):
    OK = "ok"
    VERIFY_REQUIRED = "verify_required"  # 环境异常，需要验证
    DELETED = "deleted"  # 该内容已被发布者删除
    BLOCKED = "blocked"  # 因违规无法查看 / 已被屏蔽
    EXPIRED = "expired"  # 临时链接已过期
    INVALID = "invalid"  # 参数错误
    MIGRATED = "migrated"  # 公众号已迁移
    UNAVAILABLE = "unavailable"  # 其它无法识别的空页面


STATUS_HINTS = {
    PageStatus.VERIFY_REQUIRED: (
        "WeChat returned its '环境异常' verification page. This usually means the "
        "request came from a server/VPN/proxy IP or too many requests were made. "
        "Run on your own network without a proxy, slow down, or retry with "
        "browser mode (`wxread --browser <url>`) and complete the check yourself."
    ),
    PageStatus.DELETED: "The publisher deleted this article (该内容已被发布者删除).",
    PageStatus.BLOCKED: "WeChat has blocked this article (违规/投诉/屏蔽), it cannot be viewed.",
    PageStatus.EXPIRED: (
        "This is a temporary link that has expired (链接已过期). Temporary links contain "
        "`timestamp`/`signature` parameters; find the permanent mp.weixin.qq.com/s/... link instead."
    ),
    PageStatus.INVALID: "WeChat says the URL parameters are invalid (参数错误). Check the link is complete.",
    PageStatus.MIGRATED: "The account has migrated (该公众号已迁移); the article may live under a new link.",
    PageStatus.UNAVAILABLE: "WeChat returned a page without article content (possibly deleted or restricted).",
}

# Order matters: verification first, it can appear alongside other words.
_STATUS_MARKERS: list[tuple[PageStatus, tuple[str, ...]]] = [
    (PageStatus.VERIFY_REQUIRED, ("环境异常", "完成验证后即可继续访问", "secitptpage/verify")),
    (PageStatus.DELETED, ("该内容已被发布者删除", "已被发布者删除")),
    (PageStatus.BLOCKED, ("此内容因违规无法查看", "此内容被投诉且经审核涉嫌", "已被屏蔽", "涉嫌违反相关法律法规")),
    (PageStatus.EXPIRED, ("链接已过期",)),
    (PageStatus.MIGRATED, ("该公众号已迁移",)),
    (PageStatus.INVALID, ('weui-msg__title warn">参数错误', ">参数错误<")),
]


class WeChatReaderError(Exception):
    def __init__(self, status: PageStatus, url: str, message: str | None = None):
        self.status = status
        self.url = url
        super().__init__(message or STATUS_HINTS.get(status, status.value))


@dataclass
class FetchResult:
    url: str  # normalized input URL
    final_url: str  # after redirects
    html: str
    status: PageStatus
    via: str = "http"  # "http" or "browser"


def extract_url(text: str) -> str | None:
    """Find the first mp.weixin.qq.com URL inside arbitrary text."""
    m = _URL_RE.search(text.replace("&amp;", "&"))
    return m.group(0) if m else None


def normalize_url(url: str) -> str:
    """Validate and clean a WeChat article URL.

    Handles links copied out of HTML (``&amp;``), search-engine artifacts
    (``amp=`` empty params), missing scheme, and ``#rd``/``#wechat_redirect`` fragments.
    """
    url = url.strip().strip("<>\"'")
    if not re.match(r"^https?://", url, re.I):
        url = extract_url(url) or url
        if url.lower().startswith("mp.weixin.qq.com"):
            url = "https://" + url
    url = url.replace("&amp;", "&")
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    if host not in ALLOWED_HOSTS:
        raise ValueError(f"Not a WeChat article URL (expected mp.weixin.qq.com): {url}")
    query = [(k.replace("amp;", ""), v) for k, v in parse_qsl(parts.query, keep_blank_values=True)]
    query = [(k, v) for k, v in query if k and not (k == "amp" and v == "")]
    return urlunsplit(("https", host, parts.path, urlencode(query, safe="=%"), ""))


def detect_status(html: str) -> PageStatus:
    if 'id="js_content"' in html or "picture_page_info_list" in html or "js_text_content" in html:
        # Real article markers exist; still guard against a verify page embedding them.
        if "环境异常" in html and "完成验证" in html:
            return PageStatus.VERIFY_REQUIRED
        return PageStatus.OK
    for status, markers in _STATUS_MARKERS:
        if any(m in html for m in markers):
            return status
    if "var msg_title" in html or "og:title" in html:
        return PageStatus.OK
    return PageStatus.UNAVAILABLE


def fetch_http(url: str, *, timeout: float = 20.0, proxy: str | None = None) -> FetchResult:
    url = normalize_url(url)
    with httpx.Client(
        headers=DEFAULT_HEADERS,
        follow_redirects=True,
        timeout=timeout,
        proxy=proxy,
        trust_env=proxy is None,
    ) as client:
        resp = client.get(url)
    resp.raise_for_status()
    html = resp.text
    return FetchResult(url=url, final_url=str(resp.url), html=html, status=detect_status(html))


def fetch(
    url: str,
    *,
    browser: str = "fallback",
    timeout: float = 20.0,
    proxy: str | None = None,
    headless: bool = False,
) -> FetchResult:
    """Fetch an article page.

    browser:
      "never"    – plain HTTP only.
      "fallback" – plain HTTP; if WeChat asks for verification and Playwright is
                   installed, open a browser window so the user can complete it.
      "always"   – go straight to the browser.
    """
    if browser == "always":
        from .browser import fetch_browser

        return fetch_browser(normalize_url(url), timeout=timeout, headless=headless)

    result = fetch_http(url, timeout=timeout, proxy=proxy)
    if result.status == PageStatus.VERIFY_REQUIRED and browser == "fallback":
        try:
            from .browser import BrowserUnavailable, fetch_browser
        except ImportError:  # pragma: no cover
            return result
        try:
            return fetch_browser(result.url, timeout=timeout, headless=headless)
        except BrowserUnavailable:
            return result
    return result
