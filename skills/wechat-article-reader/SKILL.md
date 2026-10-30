---
name: wechat-article-reader
description: Read WeChat Official Account (微信公众号) articles from mp.weixin.qq.com links as Markdown. Use whenever a task involves an mp.weixin.qq.com URL, or a web fetch returned "环境异常" / "完成验证后即可继续访问" for a WeChat article.
---

# Reading WeChat (微信公众号) articles

Built-in web fetch tools run on cloud servers, and WeChat answers them with a
"环境异常" verification page. Fetch the article locally with `wechat-article-reader`
instead. Do not try WebFetch on mp.weixin.qq.com first.

## Read an article

```bash
wxread "<mp.weixin.qq.com url>"
```

If `wxread` is not installed, install it once with `uv tool install git+https://github.com/Rudy-114/wechat-article-reader`
(or `pip install git+https://github.com/Rudy-114/wechat-article-reader`), or run it without installing:
`uvx --from git+https://github.com/Rudy-114/wechat-article-reader wxread "<url>"`.

Useful flags:
- `--no-images`: drop image links to save tokens when images don't matter.
- `--json`: structured output (title, account, author, publish_time, markdown, images, source_url).
- `-o file.md --images ./img`: save the article and download its images. Use this when you need to look at the images, since mmbiz.qpic.cn links often can't be viewed directly.

The output starts with a header (title, 公众号, 作者, 发布时间, 原文链接) followed by the body.

## Several articles

Run them one at a time with a short pause (`sleep 1`) between requests. Bursts trigger WeChat's verification.

## When it fails

The error is printed to stderr as `error[<status>]: <reason>`:

| status | meaning | what to do |
|---|---|---|
| `verify_required` | WeChat wants a human check (proxy/VPN, server IP, or too many requests) | Tell the user. Suggest turning off the proxy/VPN, waiting a few minutes, or running `wxread --browser "<url>"` (needs `wechat-article-reader[browser]`) and completing the check in the window. Never try to solve or bypass the check yourself. |
| `deleted` / `blocked` | Article removed by publisher / by WeChat | Report it; look for a reposted copy elsewhere if the user needs the content. |
| `expired` | Temporary link (`timestamp`/`signature` params) expired | Ask for, or search for, the permanent link. |
| `invalid` | Truncated or malformed URL | Check the URL was copied completely. |
| `invalid_url` | Not an mp.weixin.qq.com link | Use your normal web tools. |

## Finding articles

This tool only reads. To find articles, use your search tool with `site:mp.weixin.qq.com <keywords>`, then read the result URLs with the command above.
