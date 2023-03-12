# pdf-epub-GPT-翻译器

[En](https://github.com/jesselau76/pdf-epub-GPT-translator/blob/main/README.md) | [中文说明](https://github.com/jesselau76/pdf-epub-GPT-translator/blob/main/README-zh.md)

该工具旨在帮助用户将文本从一种格式转换为另一种格式，以及使用 OpenAI API (model=`gpt-3.5-turbo`) 将其翻译成另一种语言。 目前支持PDF和EPUB文件格式的转换，可以将文字翻译成多种语言。

你需要申请OpenAI API KEY,[申请地址](https://platform.openai.com/)

## 安装

要使用此工具，您需要在系统上安装 Python 3 以及以下软件包：

- pdfminer
- openai
- tqdm
- ebooklib
- bs4

您可以通过运行以下命令来安装这些软件包：
```
pip install pdfminer pdfminer.six openai tqdm ebooklib bs4
```

git clone本git

```
git clone https://github.com/jesselau76/pdf-epub-GPT-translator.git
```

## 用法

使用前将settings.cfg.example改名为settings.cfg并编辑.
```
cd pdf-epub-GPT-translator
mv settings.cfg.example settings.cfg
nano settings.cfg
```

```
openai-apikey = sk-xxxxxxx
```

将sk-xxxxxxx替换为你的OpenAI api key.

如果需要先测试prompt,可以加--test参数

```
python3 text_translation.py [-h] [--test] filename

positional arguments:
  filename    Name of the input file

options:
  -h, --help  show this help message and exit
  --test      Only translate the first 3 short texts
```

运行`text_translation.py`脚本，将要翻译或转换的文件作为参数。 例如，要翻译名为`example.pdf`的 PDF 文件，您可以运行以下命令：

```
python3 text_translation.py example.pdf
```
或者要翻译名为 `example.epub` 的 epub 文件，您可以运行以下命令：
```
python3 text_translation.py example.epub
```
或者要翻译名为 `example.txt` 的 text 文件，您可以运行以下命令：
```
python3 text_translation.py example.txt
```
默认情况下，脚本会尝试将文本翻译成在 `target-language` 选项下的 `settings.cfg` 文件中指定的语言。 您还可以通过将`bilingual-output`选项设置为`True`来选择输出文本的双语版本。

## 特点
- 代码从 settings.cfg 文件中读取 OpenAI API 密钥、目标语言和其他选项。
- 该代码分别使用 pdfminer 和 ebooklib 库将 PDF 和 EPUB 文件转换为文本。
- 该代码提供了一个选项来输出双语文本。
- 代码提供了一个进度条来显示PDF/EPUB到文本转换和翻译的进度
- 测试功能，只翻译前三页以节省API用量。
## 配置

`settings.cfg` 文件包含几个可用于配置脚本行为的选项：

- `openai-apikey`：您的 OpenAI API 的API Key
- `target-language`：您要将文本翻译成的语言（例如，`ja` 用于日语，`zh` 用于中文，也可加入风格描述，如`文言文`、`红楼梦风格的半文言文`等）。


- `bilingual-output`：是否输出文本的双语版本。
- `langcode`：输出 epub 文件的语言代码（例如 `ja` 表示日语，`zh` 表示中文等）。

## 输出


脚本的输出将是一个与输入文件同名的 EPUB 文件，但在末尾附加了`_translated`。 例如，如果输入文件是`example.pdf`，输出文件将是`example_translated.epub` 与`example_translated.txt`。

## 版权

这个工具是在 MIT 许可证下发布的。

## 免责声明：

本项目仅适用于进入公共领域的图书，不适用于受版权保护的材料。强烈建议用户在使用本项目前仔细阅读版权信息，并遵守相关法律法规以保护自己和他人的权利。

作者或开发人员不承担因使用本项目而导致的任何损失或损害的责任。用户承担使用本项目所涉及的所有风险。用户必须确认在使用本项目之前已经获得了原始版权持有人的许可或使用了开源PDF/EPUB文件，以避免潜在的版权风险。

如果您对使用本项目有任何疑虑或建议，请通过问题部分与我们联系。
