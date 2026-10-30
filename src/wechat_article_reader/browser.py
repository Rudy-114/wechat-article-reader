"""Optional real-browser fallback (``pip install 'wechat-article-reader[browser]'``).

Opens the article in a real, visible browser with a persistent profile. If WeChat
shows a verification page, the *user* completes it in the window; we just wait
for the article to appear. Nothing here automates or solves the check.
"""

from __future__ import annotations

import os
from pathlib import Path

from .fetcher import FetchResult, PageStatus, detect_status


class BrowserUnavailable(RuntimeError):
    pass


def profile_dir() -> Path:
    base = os.environ.get("WXREAD_PROFILE_DIR")
    if base:
        return Path(base).expanduser()
    return Path.home() / ".cache" / "wechat-article-reader" / "browser-profile"


def fetch_browser(
    url: str,
    *,
    timeout: float = 20.0,
    headless: bool = False,
    wait_for_user: float = 180.0,
) -> FetchResult:
    try:
        from playwright.sync_api import Error as PlaywrightError
        from playwright.sync_api import sync_playwright
    except ImportError as e:
        raise BrowserUnavailable(
            "Browser mode needs Playwright: pip install 'wechat-article-reader[browser]'"
        ) from e

    channel = os.environ.get("WXREAD_BROWSER_CHANNEL", "chrome")
    with sync_playwright() as p:
        launch = dict(user_data_dir=str(profile_dir()), headless=headless, locale="zh-CN")
        try:
            ctx = p.chromium.launch_persistent_context(channel=channel, **launch)
        except PlaywrightError:
            try:  # fall back to Playwright's bundled Chromium
                ctx = p.chromium.launch_persistent_context(**launch)
            except PlaywrightError as e:
                raise BrowserUnavailable(
                    f"Could not launch a browser ({e}). Install Chrome, or run `playwright install chromium`."
                ) from e
        try:
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=timeout * 1000)
            html = page.content()
            if detect_status(html) == PageStatus.VERIFY_REQUIRED and not headless:
                # Give the human time to complete WeChat's check in the window.
                try:
                    page.wait_for_selector("#js_content, #js_text_content", timeout=wait_for_user * 1000)
                except PlaywrightError:
                    pass
                html = page.content()
            return FetchResult(url=url, final_url=page.url, html=html, status=detect_status(html), via="browser")
        finally:
            ctx.close()
