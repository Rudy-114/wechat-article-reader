"""MCP server (stdio): exposes `read_wechat_article` to Claude Code, Cursor, Cline, etc."""

from __future__ import annotations

import json
import os
import time

try:  # mcp >= 2
    from mcp.server.mcpserver import MCPServer as _Server
except ImportError:  # mcp 1.x
    from mcp.server.fastmcp import FastMCP as _Server

from . import WeChatReaderError, read_article

mcp = _Server(
    "wechat-article-reader",
    log_level="WARNING",
    instructions=(
        "Use read_wechat_article for any mp.weixin.qq.com link. Generic web fetch tools "
        "usually get WeChat's '环境异常' verification page; this tool fetches from the "
        "user's own machine and returns the full article as Markdown."
    ),
)

_BROWSER_MODE = os.environ.get("WXREAD_BROWSER", "fallback")


def _render(url: str, include_images: bool, max_chars: int | None, as_json: bool) -> str:
    try:
        art = read_article(url, browser=_BROWSER_MODE)
    except ValueError as e:
        return f"ERROR invalid_url: {e}"
    except WeChatReaderError as e:
        return f"ERROR {e.status.value}: {e}"
    except Exception as e:  # network errors etc.
        return f"ERROR fetch_failed: {type(e).__name__}: {e}"
    if not include_images:
        art.strip_images()
    if max_chars and len(art.markdown) > max_chars:
        art.markdown = art.markdown[:max_chars] + f"\n\n…[truncated, {len(art.markdown)} chars total]"
    if as_json:
        return json.dumps(art.to_dict(), ensure_ascii=False, indent=2)
    return art.to_markdown()


@mcp.tool()
def read_wechat_article(
    url: str,
    include_images: bool = True,
    max_chars: int | None = None,
    as_json: bool = False,
) -> str:
    """Read a WeChat Official Account (微信公众号) article and return it as Markdown.

    Args:
        url: An mp.weixin.qq.com article link (short /s/xxx or long __biz=... form).
        include_images: Keep image links (mmbiz.qpic.cn) in the Markdown.
        max_chars: Truncate the body to this many characters (None = full article).
        as_json: Return structured JSON (title, account, author, publish_time, markdown, images...).
    """
    return _render(url, include_images, max_chars, as_json)


@mcp.tool()
def read_wechat_articles(urls: list[str], include_images: bool = False, max_chars: int | None = 20000) -> str:
    """Read several WeChat articles (sequentially, with a short pause between requests)."""
    out = []
    for i, u in enumerate(urls[:20]):
        if i:
            time.sleep(1.0)  # be polite; bursts are what trigger WeChat's verification page
        out.append(_render(u, include_images, max_chars, False))
    return "\n\n---\n\n".join(out)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
