# ebook-GPT-translator

这是一个完成现代化升级后的电子书翻译工具，支持 TXT、EPUB、DOCX、PDF，以及可选的 MOBI 输入。新版本不再依赖旧的单文件脚本模式，而是重构为可维护的 Python 包，补上现代 OpenAI SDK、Azure/OpenAI-compatible provider、断点续跑缓存、术语表、测试和发布基础。

[English README](README.md)

## 演示

![ebook-GPT-translator 演示](./ebook.gif)

直链：[ebook.gif](./ebook.gif)

## v2 升级内容

- 将旧版全局 OpenAI API 调用迁移为基于客户端的现代 SDK 用法
- 增加 `openai`、`azure`、`compatible`、`mock` 四类 provider
- 增加基于 SQLite 的翻译缓存和 manifest，支持长任务续跑
- 增加分块和 token 上限控制，适配长文档
- 新增 `settings.toml`、`.env`，并完整兼容旧版 `[option]` 风格 `settings.cfg`
- 重构为 `src/` 包结构，便于维护和发布
- 增加单元测试和 GitHub Actions CI
- 保留旧入口 `text_translation.py`，降低迁移成本

## 支持的 provider

- `codex`：本机 Codex CLI，直接复用 ChatGPT subscription 登录态
- `openai`：官方 OpenAI API
- `azure`：Azure OpenAI 部署
- `compatible`：任意 OpenAI-compatible 接口，包括 Venice.ai 这类第三方服务
- `mock`：离线冒烟测试，不需要 API key

## 支持的格式

- 输入：`txt`、`md`、`epub`、`docx`、`pdf`
- 可选输入：`mobi`，需要额外执行 `pip install mobi`
- 输出：翻译后的 `txt` 和 `epub`

## 安装

```bash
git clone https://github.com/jesselau76/ebook-GPT-translator.git
cd ebook-GPT-translator
python3 -m pip install -r requirements.txt
```

如果需要 MOBI：

```bash
python3 -m pip install mobi
```

如果需要 XLSX 术语表支持：

```bash
python3 -m pip install openpyxl
```

## 快速开始

生成配置文件：

```bash
python3 -m ebook_gpt_translator init-config
```

启动桌面 GUI：

```bash
PYTHONPATH=src python3 -m ebook_gpt_translator.gui
```

或者安装后直接运行：

```bash
ebook-gpt-translator-gui
```

GUI 说明：

- `Config file` 是可选项。不填时，直接使用 GUI 当前表单里的设置。
- 如果你想保存一套固定预设，比如 provider、语言、上下文窗口、输出选项，再使用 config file。
- GUI 里的 `Model` 现在是下拉列表，会从你本机的 Codex 模型缓存里读取。
- GUI 里的 `Target language` 现在是常用语言下拉，同时也保留手动输入。
- GUI 里有 `Custom prompt` 输入框，可以直接写类似 `用红楼梦的风格翻译成中文` 的要求。
- GUI 现在会实时显示 block 和 chunk 两层进度，大文件翻译时不会再像卡死一样没有反馈。
- GUI 现在提供 `Check resume` 和 `Resume previous job`。如果 Codex 中途断掉，用同一文件和同一组设置重开任务，就会继续复用已完成 chunk 的缓存，并重建一致性上下文。

真实翻译：

```bash
PYTHONPATH=src python3 -m ebook_gpt_translator translate book.epub \
  --config settings.toml \
  --provider codex \
  --model gpt-5.2-codex \
  --reasoning-effort medium \
  --target-language "Simplified Chinese"
```

使用 Codex subscription 登录直接翻译：

```bash
PYTHONPATH=src python3 -m ebook_gpt_translator auth login --provider codex
PYTHONPATH=src python3 -m ebook_gpt_translator translate book.epub \
  --provider codex \
  --model gpt-5.2-codex \
  --reasoning-effort medium \
  --target-language "Simplified Chinese"
```

离线冒烟测试：

```bash
PYTHONPATH=src python3 -m ebook_gpt_translator translate sample.txt \
  --provider mock \
  --target-language German
```

本地保存 OpenAI 凭据：

```bash
PYTHONPATH=src python3 -m ebook_gpt_translator auth login --provider openai
```

默认 provider 说明：

- 现在默认 provider 是 `codex`
- 默认模型是 `gpt-5.2-codex`
- 默认 reasoning effort 是 `medium`
- 现在默认开启长篇一致性上下文，`context_window_blocks = 6`
- 默认启用章节记忆、滚动上下文和术语记忆
- 跨章节记忆会持久化到 sidecar memory 文件，重跑时继续复用
- 如果你想更便宜更快，可以用 `--reasoning-effort low`
- 如果你想切 Codex 模型，可以直接传 `--model`，例如 `gpt-5.2-codex`、`gpt-5.1-codex`、`gpt-5-codex-mini`
- 如果你想调整滚动上下文大小，可以传 `--context-window`
- 如果你不想手敲命令，GUI 已经暴露同样的 provider/model/context 配置项

查看 Codex 登录状态：

```bash
PYTHONPATH=src python3 -m ebook_gpt_translator auth status
```

列出本机可用的 Codex 模型：

```bash
PYTHONPATH=src python3 -m ebook_gpt_translator list-models
```

兼容旧入口：

```bash
PYTHONPATH=src python3 text_translation.py translate sample.txt --provider mock
```

## 历史需求对应实现

- Azure OpenAI：通过 `provider.kind = "azure"` 支持
- Venice.ai / 第三方兼容接口：通过 `provider.kind = "compatible"` 和 `api_base_url` 支持
- 跳过功能：通过 `--skip-existing` 支持
- 长文重试与续跑：通过 SQLite 缓存和 manifest 支持
- 术语替换：通过 CSV 或 XLSX glossary 支持，兼容原仓库样例
- 长篇一致性：默认携带章节记忆、前文已翻译上下文和术语记忆，帮助维持人名、地名、称谓和语气统一
- 翻译记忆会保存到 `.cache/jobs/*.memory.json`，便于跨章节和断点重跑继续复用
- Codex provider 现在会强制请求结构化 JSON，并只解析 `translation` 字段；遇到空结果会自动重试

## 开发与测试

运行测试：

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

本地安装：

```bash
python3 -m pip install -e .
```

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=jesselau76/ebook-GPT-translator&type=Date)](https://star-history.com/#jesselau76/ebook-GPT-translator&Date)
