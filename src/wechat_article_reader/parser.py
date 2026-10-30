"""Turn a WeChat article HTML page into clean Markdown + metadata."""

from __future__ import annotations

import html as htmllib
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone

from bs4 import BeautifulSoup, Tag
from markdownify import MarkdownConverter

CST = timezone(timedelta(hours=8))

# item_show_type values seen on mp.weixin.qq.com
SHOW_TYPES = {
    "0": "article",
    "5": "video",
    "7": "audio",
    "8": "image",  # 图片消息 / 小绿书
    "10": "text",  # 文字消息 / 短内容
    "11": "repost",
}


@dataclass
class Article:
    url: str
    title: str = ""
    account: str = ""  # 公众号名称
    author: str = ""
    publish_time: str = ""  # ISO 8601, Asia/Shanghai
    timestamp: int | None = None
    description: str = ""
    cover: str = ""
    source_url: str = ""  # 「阅读原文」链接
    account_id: str = ""  # gh_xxx
    biz: str = ""
    show_type: str = "article"
    markdown: str = ""
    images: list[str] = field(default_factory=list)
    fetched_via: str = "http"

    def to_dict(self) -> dict:
        return asdict(self)

    def header_lines(self) -> list[str]:
        meta = []
        if self.account:
            meta.append(f"公众号：{self.account}")
        if self.author and self.author != self.account:
            meta.append(f"作者：{self.author}")
        if self.publish_time:
            meta.append(f"发布时间：{self.publish_time.replace('T', ' ')[:16]}")
        lines = [f"# {self.title or '(无标题)'}", ""]
        if meta:
            lines.append("> " + " ｜ ".join(meta))
        lines.append(f"> 原文：{self.url}")
        if self.source_url:
            lines.append(f"> 阅读原文：{self.source_url}")
        return lines

    def strip_images(self) -> "Article":
        """Drop image lines from the Markdown (useful for text-only agents / token budgets)."""
        md = re.sub(r"^\s*!\[[^\]]*\]\([^)]*\)\s*$", "", self.markdown, flags=re.M)
        self.markdown = re.sub(r"\n{3,}", "\n\n", md).strip()
        return self

    def to_markdown(self, header: bool = True) -> str:
        if not header:
            return self.markdown
        return "\n".join(self.header_lines()) + "\n\n" + self.markdown + "\n"


# ---------------------------------------------------------------- JS vars


def _js_unescape(s: str) -> str:
    s = re.sub(r"\\x([0-9a-fA-F]{2})", lambda m: chr(int(m.group(1), 16)), s)
    s = re.sub(r"\\u([0-9a-fA-F]{4})", lambda m: chr(int(m.group(1), 16)), s)
    s = s.replace("\\'", "'").replace('\\"', '"').replace("\\/", "/").replace("\\n", "\n").replace("\\\\", "\\")
    return htmllib.unescape(htmllib.unescape(s))


def _js_var(html: str, *names: str) -> str:
    """Read `var name = "..."` / `htmlDecode("...")` / `name: '...'` style assignments."""
    value = r"\s*(?:htmlDecode\()?\s*(?P<q>[\"'])(?P<v>(?:\\.|(?!(?P=q)).)*)(?P=q)"
    # Strict `var x = ...` first: page JS also contains unrelated `x: "..."` object keys.
    for prefix, sep in ((r"var\s+", "="), (r"(?<![\w.$-])", "[=:]")):
        for name in names:
            for m in re.finditer(prefix + re.escape(name) + r"\s*" + sep + value, html):
                v = m.group("v").strip()
                if v and not v.startswith("data-"):
                    return _js_unescape(v).strip()
    return ""


def _meta(soup: BeautifulSoup, key: str) -> str:
    tag = soup.find("meta", attrs={"property": key}) or soup.find("meta", attrs={"name": key})
    return (tag.get("content") or "").strip() if tag else ""


def _text(soup: BeautifulSoup, selector: str) -> str:
    el = soup.select_one(selector)
    return el.get_text(" ", strip=True) if el else ""


# ---------------------------------------------------------------- body cleanup


class _Converter(MarkdownConverter):
    def convert_img(self, el, text, parent_tags=None, **kw):
        src = el.get("data-src") or el.get("src") or ""
        if not src or src.startswith("data:"):
            return ""
        alt = (el.get("alt") or "").strip()
        return f"![{alt}]({src})"


def _code_language(el: Tag) -> str:
    lang = el.get("data-lang") or ""
    if not lang:
        for cls in el.get("class") or []:
            m = re.match(r"code-snippet__(\w+)", cls)
            if m and m.group(1) not in ("fix", "js_wrap"):
                lang = m.group(1)
    return lang


def _prepare_body(root: Tag, account: str) -> list[str]:
    for t in root.find_all(["script", "style", "noscript"]):
        t.decompose()

    # Code blocks: WeChat often renders each line as its own <code>.
    for pre in root.find_all("pre"):
        codes = pre.find_all("code", recursive=False)
        text = "\n".join(c.get_text() for c in codes) if len(codes) > 1 else pre.get_text()
        pre.clear()
        pre.string = text

    # Nested <strong><strong> and bold inside headings render as `****`; unwrap them.
    for t in root.find_all(["strong", "b", "em", "i"]):
        if t.find_parent(["h1", "h2", "h3", "h4", "h5", "h6"]) or t.find_parent(t.name):
            t.unwrap()

    def placeholder(tag: Tag, text: str) -> None:
        p = BeautifulSoup("", "html.parser").new_tag("p")
        p.string = text
        tag.replace_with(p)

    # Embedded widgets → readable placeholders
    for t in root.find_all("mp-common-profile"):
        placeholder(t, f"[公众号名片：{t.get('data-nickname') or account}]")
    for t in root.find_all(["mpvoice", "mp-common-mpaudio"]):
        name = t.get("name") or t.get("data-title") or t.get("data-name") or ""
        placeholder(t, f"[音频{('：' + name) if name else ''}]")
    for t in root.find_all(["mpvideo", "mp-common-videosnap"]):
        placeholder(t, f"[视频{('：' + t.get('data-desc')) if t.get('data-desc') else ''}]")
    for t in root.find_all("iframe"):
        if "video" in " ".join(t.get("class") or []) or "v.qq.com" in (t.get("data-src") or ""):
            placeholder(t, "[视频]")
        else:
            t.decompose()
    for t in root.find_all(["mp-miniprogram", "mp-common-miniprogram"]):
        title = t.get("data-miniprogram-title") or ""
        placeholder(t, f"[小程序{('：' + title) if title else ''}]")

    images = []
    for img in root.find_all("img"):
        src = img.get("data-src") or img.get("src") or ""
        if src and not src.startswith("data:"):
            images.append(src)
    return images


def _clean_markdown(md: str) -> str:
    md = md.replace("\xa0", " ").replace("\u200b", "").replace("\ufeff", "")
    md = re.sub(r"[ \t]+\n", "\n", md)
    md = re.sub(r"\n{3,}", "\n\n", md)
    # Nested/adjacent <strong> produce `****x****` or `**a****b**`; collapse them.
    md = re.sub(r"\*{4,}", "", md)
    # Drop stray emphasis markers left by empty <strong>/<em> spans
    md = re.sub(r"^\s*(\*\*|__|\*)\s*$", "", md, flags=re.M)
    md = re.sub(r"\n{3,}", "\n\n", md)
    return md.strip()


def _to_md(el: Tag) -> str:
    conv = _Converter(heading_style="ATX", bullets="-", code_language_callback=_code_language, strip=["span"])
    return _clean_markdown(conv.convert_soup(el))


# ---------------------------------------------------------------- main entry


def parse_article(html: str, url: str, fetched_via: str = "http") -> Article:
    soup = BeautifulSoup(html, "html.parser")

    title = _js_var(html, "msg_title") or _meta(soup, "og:title") or _text(soup, "#activity-name")
    account = _js_var(html, "nickname", "nick_name") or _text(soup, "#js_name")
    author = _meta(soup, "author") or _text(soup, "#js_author_name") or _js_var(html, "author")
    ts_raw = _js_var(html, "ct", "create_time")
    ts = int(ts_raw) if ts_raw.isdigit() else None
    show_code = _js_var(html, "item_show_type") or "0"

    art = Article(
        url=url,
        title=title,
        account=account,
        author=author,
        timestamp=ts,
        publish_time=datetime.fromtimestamp(ts, CST).isoformat() if ts else "",
        description=_js_var(html, "msg_desc") or _meta(soup, "og:description") or _meta(soup, "description"),
        cover=_js_var(html, "msg_cdn_url") or _meta(soup, "og:image"),
        source_url=_js_var(html, "msg_source_url"),
        account_id=_js_var(html, "user_name"),
        biz=_js_var(html, "biz"),
        show_type=SHOW_TYPES.get(show_code, show_code),
        fetched_via=fetched_via,
    )

    body = soup.select_one("#js_content")
    md = ""
    if body is not None:
        art.images = _prepare_body(body, account)
        md = _to_md(body)

    if not md:
        # 文字消息 / 图片消息 pages keep their text elsewhere.
        for sel in ("#js_text_content", "#js_text_desc", "#js_image_desc", ".share_notice", ".rich_media_content"):
            el = soup.select_one(sel)
            if el is not None:
                _prepare_body(el, account)
                md = _to_md(el)
                if md:
                    break
    if not md:
        md = _js_var(html, "content_noencode", "ContentNoEncode")

    if art.show_type == "image" or (not art.images and "picture_page_info_list" in html):
        block = html[html.find("picture_page_info_list") :][:200_000]
        pics = list(dict.fromkeys(re.findall(r"cdn_url\s*:\s*['\"]([^'\"]+)['\"]", block)))
        pics = [_js_unescape(p) for p in pics]
        if pics:
            art.images = pics
            md = (md + "\n\n" if md else "") + "\n\n".join(f"![]({p})" for p in pics)

    if not md and art.description:
        md = art.description

    art.markdown = md
    return art
