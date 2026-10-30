# wechat-article-reader

![Python](https://img.shields.io/badge/python-3.10%2B-blue) ![License](https://img.shields.io/badge/license-MIT-green)

**让 AI Agent 读得到微信公众号文章。** 一个命令 / 一个 MCP 工具 / 一个本地 HTTP 接口，把 `mp.weixin.qq.com` 链接变成干净的 Markdown。

[English](#english) · [为什么 Agent 读不到公众号](#为什么-agent-读不到公众号) · [安装](#安装) · [接入各家-agent](#接入各家-agent) · [常见问题](#常见问题)

```console
$ wxread https://mp.weixin.qq.com/s/j8q018Lck1TWHO3NxQDiJQ
# 黄铁军：大模型时代，AI生态何以“根深叶茂”

> 公众号：智源研究院 ｜ 发布时间：2022-06-10 17:16
> 原文：https://mp.weixin.qq.com/s/j8q018Lck1TWHO3NxQDiJQ

6月1日，在2022智源大会“人工智能新基建”专题论坛上，北京智源人工智能研究院院长……
```

## 为什么 Agent 读不到公众号

公众号文章页面本身是公开的，并没有"接口被关"。问题出在**请求从哪里发出**：

| 抓取方式 | 结果 |
|---|---|
| Agent 内置的 WebFetch / 浏览工具（在云端服务器上发请求） | ❌ `环境异常：当前环境异常，完成验证后即可继续访问` |
| 本地 `curl`，不带浏览器 UA | ❌ 同上 |
| **本地网络 + 正常浏览器请求头** | ✅ 完整正文 |

微信会对数据中心 IP 和"不像浏览器"的请求返回验证页。大多数 Agent 的联网工具都运行在云端，所以一碰到公众号就失败。

本项目的做法很简单：**在你自己的电脑上、用你自己的网络去请求文章**，再把页面解析成 Agent 好读的 Markdown（正文、标题、公众号名、作者、发布时间、图片、代码块……）。

它**不会**破解、绕过或自动完成任何验证码。如果你本地也被要求验证，工具会如实返回 `verify_required`；你可以选择开启浏览器模式，在弹出的窗口里**自己**完成验证。

## 功能

- 📄 正文转 Markdown：标题层级、加粗、列表、表格、代码块（含公众号逐行 `<code>` 的代码片段）、图片（`data-src` 懒加载）
- 🏷️ 元数据：标题、公众号名称、作者、发布时间、摘要、封面、「阅读原文」链接、`gh_` 原始 ID
- 🔗 链接兼容：短链 `/s/xxxx`、长链 `__biz=&mid=&idx=&sn=`、带 `&amp;` 的、从一段文字里自动提取
- 🚦 明确的失败原因：`verify_required` / `deleted` / `blocked` / `expired` / `invalid`……Agent 能据此决定下一步
- 🖼️ 可选下载图片到本地（不带 Referer，避开"此图片来自微信公众平台未经允许不可引用"）
- 🧩 四种接入方式：**CLI**、**MCP Server**、**本地 HTTP API**、**Agent Skill**
- 🌐 可选浏览器模式（Playwright + 本机 Chrome，持久化登录态）

## 安装

需要 Python ≥ 3.10 和 [uv](https://docs.astral.sh/uv/)（`curl -LsSf https://astral.sh/uv/install.sh | sh`，或 `brew install uv`）。

```bash
# 推荐：安装成全局命令 wxread
uv tool install git+https://github.com/Rudy-114/wechat-article-reader

# 或者不安装，直接运行
uvx --from git+https://github.com/Rudy-114/wechat-article-reader wxread https://mp.weixin.qq.com/s/xxxx

# 不用 uv 也可以
pip install git+https://github.com/Rudy-114/wechat-article-reader
```

升级到最新版：`uv tool install --reinstall git+https://github.com/Rudy-114/wechat-article-reader`

可选：浏览器模式（遇到验证时弹出窗口让你手动完成）

```bash
uv tool install "wechat-article-reader[browser] @ git+https://github.com/Rudy-114/wechat-article-reader"
# 默认使用本机 Chrome；没有 Chrome 时：
uvx playwright install chromium
```

## 用法

### CLI

```bash
wxread <url>                      # Markdown 输出到 stdout
wxread <url> --json               # 结构化 JSON（含元数据）
wxread <url> --no-images          # 去掉图片，省 token
wxread <url> -o a.md --images ./img   # 保存文件并下载图片到本地
wxread <url> --browser            # 直接用浏览器打开（需 [browser]）
wxread "看看这篇 https://mp.weixin.qq.com/s/xxxx 写得不错"   # 自动提取链接
```

退出码：`0` 成功，`2` 非公众号链接，`3` 需要验证，`4` 网络错误，`5` 文章不可用（删除/违规/过期等）。

### MCP Server

```bash
wxread mcp
```

提供两个工具：

| 工具 | 说明 |
|---|---|
| `read_wechat_article(url, include_images=True, max_chars=None, as_json=False)` | 读取一篇文章 |
| `read_wechat_articles(urls, include_images=False, max_chars=20000)` | 批量读取（最多 20 篇，每篇间隔 1 秒） |

### 本地 HTTP API

给能发 HTTP 请求、但不支持 MCP 的工具（n8n、Dify / Coze 本地部署、自写脚本……）：

```bash
wxread serve --port 8765
curl "http://127.0.0.1:8765/read?url=https://mp.weixin.qq.com/s/xxxx"            # Markdown
curl "http://127.0.0.1:8765/read?url=https://mp.weixin.qq.com/s/xxxx&format=json" # JSON
curl "http://127.0.0.1:8765/read?url=...&images=0"                                # 不要图片
```

默认只监听 `127.0.0.1`。

### Python

```python
from wechat_article_reader import read_article

art = read_article("https://mp.weixin.qq.com/s/xxxx")
print(art.title, art.account, art.publish_time)
print(art.to_markdown())
```

## 接入各家 Agent

下面的配置都假设你已经按上面用 `uv tool install` 装好了 `wxread` 命令。

<details open>
<summary><b>Claude Code</b></summary>

```bash
claude mcp add wechat -s user -- wxread mcp
```

或者用 Skill（不需要常驻 MCP）：

```bash
git clone https://github.com/Rudy-114/wechat-article-reader
mkdir -p ~/.claude/skills && cp -r wechat-article-reader/skills/wechat-article-reader ~/.claude/skills/
```
</details>

<details>
<summary><b>Codex CLI</b>（<code>~/.codex/config.toml</code>）</summary>

```toml
[mcp_servers.wechat]
command = "wxread"
args = ["mcp"]
```
</details>

<details>
<summary><b>Cursor / Windsurf / Cline / Claude Desktop / Cherry Studio / Trae 等</b>（JSON 配置）</summary>

```json
{
  "mcpServers": {
    "wechat": {
      "command": "wxread",
      "args": ["mcp"]
    }
  }
}
```

配置文件位置：Cursor `~/.cursor/mcp.json`；Claude Desktop `~/Library/Application Support/Claude/claude_desktop_config.json`（macOS）；Windsurf `~/.codeium/windsurf/mcp_config.json`；Cline / Cherry Studio 在设置界面里添加。

> 部分 GUI 应用读不到你 shell 里的 PATH，如果提示找不到 `wxread`，把 `command` 写成绝对路径（`which wxread` 查看，一般是 `~/.local/bin/wxread`）。
</details>

<details>
<summary><b>只能执行命令的 Agent</b>（Aider、OpenHands、各类自建 Agent……）</summary>

把这段放进 `AGENTS.md` / 系统提示词：

```markdown
## 读取微信公众号文章
遇到 mp.weixin.qq.com 链接时，不要用内置网页抓取（会被微信拦截为"环境异常"）。
运行 `wxread "<url>"` 获取 Markdown 正文（未安装时：`uv tool install git+https://github.com/Rudy-114/wechat-article-reader`）；加 `--no-images` 可省 token。
失败时 stderr 会给出原因（verify_required / deleted / blocked / expired）。
```
</details>

## 常见问题

**还是返回 `verify_required`（环境异常）？**
- 确认是在你自己的电脑 / 家庭或公司网络上运行，**关掉代理 / VPN**（境外节点、机房 IP 基本必定触发）。
- 短时间请求太多也会触发，歇几分钟再试；批量读取请保持间隔。
- 装上 `[browser]`，用 `wxread --browser <url>`：会打开一个 Chrome 窗口，你手动完成验证后，工具会自动读取正文。浏览器配置保存在 `~/.cache/wechat-article-reader/browser-profile`，之后通常不用再验证。

**把 MCP 部署到云服务器可以吗？** 一般不行，云服务器 IP 正是被拦截的那一类。本工具的意义就在于"本地运行"。

**能搜索公众号文章吗？** 本工具只负责"读"。搜索请用 Agent 自带的搜索引擎加上 `site:mp.weixin.qq.com`。搜狗微信搜索的跳转链接有反爬机制，本项目不做绕过。

**链接打开显示"链接已过期"？** 带 `timestamp=&signature=` 的是临时链接，会过期。需要找到永久链接（`/s/xxxx` 或带 `__biz&mid&idx&sn` 的）。

**图片 / 文字类型的"小绿书"、短内容？** 已做兼容（提取图片列表和文字），属于 best-effort；如果遇到解析不全的文章，欢迎提 Issue 附上链接。

**MCP 环境变量**
| 变量 | 默认 | 说明 |
|---|---|---|
| `WXREAD_BROWSER` | `fallback` | `never` / `fallback`（遇到验证且装了 Playwright 时弹窗）/ `always` |
| `WXREAD_BROWSER_CHANNEL` | `chrome` | Playwright 浏览器通道，如 `msedge` |
| `WXREAD_PROFILE_DIR` | `~/.cache/wechat-article-reader/browser-profile` | 浏览器配置目录 |

## 合理使用

本项目用于让个人的 AI 助手阅读**你本来就能在浏览器里打开的公开文章**。请：

- 不要用于大规模爬取、镜像或转载他人内容；文章版权归原作者所有。
- 保持合理的请求频率。
- 不要尝试用本项目绕过微信的验证或风控机制。

## 开发

```bash
uv venv && uv pip install -e ".[dev]"
pytest              # 离线单元测试
pytest -m live      # 联网测试（需要能访问微信的本地网络）
```

---

## English

**Let AI agents read WeChat Official Account (微信公众号) articles.**

WeChat article pages are public, but WeChat serves a "环境异常" (abnormal environment) verification page to datacenter IPs and non-browser clients. Most agents' built-in web fetch tools run in the cloud, so they always hit that page. This tool fetches the page **from your own machine and network** with ordinary browser headers and converts it into clean Markdown with metadata. It never solves or bypasses captchas. If verification is required, it reports `verify_required`, or with the optional `[browser]` extra it opens a real Chrome window so you can complete the check yourself.

```bash
uv tool install git+https://github.com/Rudy-114/wechat-article-reader
wxread <url>                                   # CLI → Markdown
wxread mcp                                     # MCP server (stdio)
wxread serve --port 8765                       # local HTTP API: GET /read?url=...
claude mcp add wechat -s user -- wxread mcp    # Claude Code
```

MCP tools: `read_wechat_article(url, include_images, max_chars, as_json)` and `read_wechat_articles(urls, ...)`.

Please use it responsibly: personal reading by your own assistant, reasonable request rates, no mass scraping or republishing.

## License

MIT
