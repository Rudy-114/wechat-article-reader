"""Command line: `wxread <url>` prints the article as Markdown.

    wxread https://mp.weixin.qq.com/s/xxxx              # Markdown to stdout
    wxread <url> --json                                  # structured JSON
    wxread <url> -o article.md --images ./img            # save + download images
    wxread mcp                                           # run MCP server (stdio)
    wxread serve --port 8765                             # run local HTTP API
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import WeChatReaderError, __version__, read_article

EXIT_CODES = {"invalid_url": 2, "verify_required": 3, "fetch_failed": 4}


def _read(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="wxread", description="Read a WeChat (微信公众号) article as Markdown.")
    p.add_argument("url", help="mp.weixin.qq.com article URL (or text containing one)")
    p.add_argument("--json", action="store_true", help="output JSON with metadata")
    p.add_argument("-o", "--output", help="write to this file instead of stdout")
    p.add_argument("--images", metavar="DIR", help="download images into DIR and rewrite links")
    p.add_argument("--no-images", action="store_true", help="drop image links from the Markdown")
    p.add_argument("--no-header", action="store_true", help="body only, no title/metadata header")
    p.add_argument("--browser", nargs="?", const="always", default="fallback",
                   choices=["never", "fallback", "always"],
                   help="use a real browser window (needs the [browser] extra). Default: fallback")
    p.add_argument("--proxy", help="HTTP(S) proxy URL (by default system proxy env vars are used)")
    p.add_argument("--timeout", type=float, default=20.0)
    p.add_argument("--version", action="version", version=f"wechat-article-reader {__version__}")
    a = p.parse_args(argv)

    try:
        art = read_article(a.url, browser=a.browser, timeout=a.timeout, proxy=a.proxy)
    except ValueError as e:
        print(f"error[invalid_url]: {e}", file=sys.stderr)
        return EXIT_CODES["invalid_url"]
    except WeChatReaderError as e:
        print(f"error[{e.status.value}]: {e}", file=sys.stderr)
        return EXIT_CODES.get(e.status.value, 5)
    except Exception as e:
        print(f"error[fetch_failed]: {type(e).__name__}: {e}", file=sys.stderr)
        return EXIT_CODES["fetch_failed"]

    if a.images:
        from .images import download_images

        download_images(art, a.images, timeout=a.timeout)
    if a.no_images:
        art.strip_images()

    text = json.dumps(art.to_dict(), ensure_ascii=False, indent=2) if a.json else art.to_markdown(header=not a.no_header)
    if a.output:
        Path(a.output).write_text(text, encoding="utf-8")
        print(f"saved: {a.output}", file=sys.stderr)
    else:
        sys.stdout.write(text if text.endswith("\n") else text + "\n")
    return 0


def main(argv: list[str] | None = None) -> None:
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] == "mcp":
        from .mcp_server import main as mcp_main

        mcp_main()
        return
    if argv and argv[0] == "serve":
        sp = argparse.ArgumentParser(prog="wxread serve")
        sp.add_argument("--host", default="127.0.0.1")
        sp.add_argument("--port", type=int, default=8765)
        a = sp.parse_args(argv[1:])
        from .http_server import serve

        serve(a.host, a.port)
        return
    sys.exit(_read(argv))


if __name__ == "__main__":
    main()
