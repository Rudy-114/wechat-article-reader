"""Read WeChat Official Account (微信公众号) articles as clean Markdown, for AI agents."""

from __future__ import annotations

from .fetcher import (
    FetchResult,
    PageStatus,
    WeChatReaderError,
    extract_url,
    fetch,
    normalize_url,
)
from .parser import Article, parse_article

__version__ = "0.1.0"

__all__ = [
    "Article",
    "FetchResult",
    "PageStatus",
    "WeChatReaderError",
    "extract_url",
    "fetch",
    "normalize_url",
    "parse_article",
    "read_article",
    "__version__",
]


def read_article(
    url: str,
    *,
    browser: str = "fallback",
    timeout: float = 20.0,
    proxy: str | None = None,
) -> Article:
    """Fetch and parse one article. Raises WeChatReaderError if no content is available."""
    result = fetch(url, browser=browser, timeout=timeout, proxy=proxy)
    if result.status != PageStatus.OK:
        raise WeChatReaderError(result.status, result.url)
    art = parse_article(result.html, result.url, fetched_via=result.via)
    if not art.markdown and not art.title:
        raise WeChatReaderError(PageStatus.UNAVAILABLE, result.url)
    return art
