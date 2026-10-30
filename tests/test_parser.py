from pathlib import Path

import pytest

from wechat_article_reader import PageStatus, WeChatReaderError, normalize_url, parse_article, read_article
from wechat_article_reader.fetcher import detect_status, extract_url

FIX = Path(__file__).parent / "fixtures"
URL = "https://mp.weixin.qq.com/s/test"


@pytest.fixture
def article():
    return parse_article((FIX / "article.html").read_text(encoding="utf-8"), URL)


def test_metadata(article):
    assert article.title == "测试文章标题"
    assert article.account == "测试公众号"  # not the `nickname:` object key in page JS
    assert article.author == "张三"
    assert article.publish_time.startswith("2023-11-15T06:13:20")
    assert article.description == "这是一篇测试文章"
    assert article.source_url == "https://example.com/source"
    assert article.account_id == "gh_123456"
    assert article.show_type == "article"


def test_body(article):
    md = article.markdown
    assert "![](https://mmbiz.qpic.cn/mmbiz_png/abc/640?wx_fmt=png)" in md  # data-src, not placeholder
    assert "data:image" not in md
    assert "**加粗**" in md and "****" not in md
    assert "## 小标题\n" in md
    assert "第二段 内容" in md and "\u200b" not in md
    assert "- 要点一" in md
    assert "```python\ndef hello():\n    return 1\n```" in md
    assert "[公众号名片：另一个号]" in md
    assert "[音频：一段音频]" in md
    assert "[视频]" in md
    assert "bad = 1" not in md
    assert article.images == ["https://mmbiz.qpic.cn/mmbiz_png/abc/640?wx_fmt=png"]


def test_markdown_header(article):
    out = article.to_markdown()
    assert out.startswith("# 测试文章标题\n")
    assert "公众号：测试公众号 ｜ 作者：张三 ｜ 发布时间：2023-11-15 06:13" in out
    assert f"> 原文：{URL}" in out


@pytest.mark.parametrize(
    "html,status",
    [
        ("<p>当前环境异常，完成验证后即可继续访问。</p>", PageStatus.VERIFY_REQUIRED),
        ("<script>location.href='/mp/secitptpage/verify.html'</script>", PageStatus.VERIFY_REQUIRED),
        ("<div>该内容已被发布者删除</div>", PageStatus.DELETED),
        ("<div>此内容因违规无法查看</div>", PageStatus.BLOCKED),
        ("<div>链接已过期</div>", PageStatus.EXPIRED),
        ('<div class="weui-msg__title warn">参数错误</div>', PageStatus.INVALID),
        ("<html><body></body></html>", PageStatus.UNAVAILABLE),
        ('<div id="js_content"><p>hi</p></div>', PageStatus.OK),
    ],
)
def test_detect_status(html, status):
    assert detect_status(html) == status


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("https://mp.weixin.qq.com/s/abcDEF_-123", "https://mp.weixin.qq.com/s/abcDEF_-123"),
        ("http://mp.weixin.qq.com/s/abc#rd", "https://mp.weixin.qq.com/s/abc"),
        ("mp.weixin.qq.com/s/abc", "https://mp.weixin.qq.com/s/abc"),
        ("看看这个 https://mp.weixin.qq.com/s/abc 不错", "https://mp.weixin.qq.com/s/abc"),
        (
            "https://mp.weixin.qq.com/s?__biz=MzA%3D&amp;mid=1&amp;idx=2&amp=&sn=x",
            "https://mp.weixin.qq.com/s?__biz=MzA=&mid=1&idx=2&sn=x",
        ),
    ],
)
def test_normalize_url(raw, expected):
    assert normalize_url(raw) == expected


def test_rejects_other_hosts():
    with pytest.raises(ValueError):
        normalize_url("https://example.com/s/abc")
    assert extract_url("no link here") is None


@pytest.mark.live
def test_live_read():
    try:
        art = read_article("https://mp.weixin.qq.com/s/j8q018Lck1TWHO3NxQDiJQ", browser="never")
    except WeChatReaderError as e:
        pytest.skip(f"WeChat refused this network: {e.status}")
    assert art.title and art.account and len(art.markdown) > 1000
