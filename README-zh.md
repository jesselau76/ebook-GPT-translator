# pdf-epub-GPT-翻译器

[En](https://github.com/jesselau76/pdf-epub-GPT-translator/blob/main/README.md) | [中文说明](https://github.com/jesselau76/pdf-epub-GPT-translator/blob/main/README-zh.md)

该工具旨在帮助用户将文本从一种格式转换为另一种格式，以及使用 OpenAI API (model=`gpt-3.5-turbo`) 将其翻译成另一种语言。 目前支持PDF和EPUB文件格式的转换，可以将文字翻译成多种语言。

你需要申请OpenAI API KEY,[申请地址](https://platform.openai.com/)

## 安装

要使用此工具，您需要在系统上安装 Python 3 以及以下软件包：

- pdfminer
- openai
- tqdm
- nltk
- ebooklib
- bs4

您可以通过运行以下命令来安装这些软件包：
```
pip install pdfminer pdfminer.six openai tqdm nltk ebooklib bs4
```

git clone本git

```
git clone https://github.com/jesselau76/pdf-epub-GPT-translator.git
```

## 用法
使用前更改`settings.cfg` 文件
```
openai-apikey = sk-xxxxxxx
```
将sk-xxxxxxx替换为你的OpenAI api key.

要使用此工具，只需运行“text_translation.py”脚本，将要翻译或转换的文件作为参数。 例如，要翻译名为“example.pdf”的 PDF 文件，您可以运行以下命令：

```
python3 text_translation.py example.pdf
```
或者要翻译名为 example.epub 的 epub 文件，您可以运行以下命令：
```
python3 text_translation.py example.epub
```
或者要翻译名为 example.txt 的 text 文件，您可以运行以下命令：
```
python3 text_translation.py example.txt
```
默认情况下，脚本会尝试将文本翻译成在 `target-language` 选项下的 `settings.cfg` 文件中指定的语言。 您还可以通过将“bilingual-output”选项设置为“True”来选择输出文本的双语版本。

## 特点
- 代码从 settings.cfg 文件中读取 OpenAI API 密钥、目标语言和其他选项。
- 该代码分别使用 pdfminer 和 ebooklib 库将 PDF 和 EPUB 文件转换为文本。
- 该代码提供了一个选项来输出双语文本。
- 代码提供了一个进度条来显示PDF/EPUB到文本转换和翻译的进度

## 配置

`settings.cfg` 文件包含几个可用于配置脚本行为的选项：

- `openai-apikey`：您的 OpenAI API 的API Key
- `target-language`：您要将文本翻译成的语言（例如，`ja` 用于日语，`zh` 用于中文，甚至是“文言文”等）。
![文言文](https://user-images.githubusercontent.com/40444824/223943798-4faf91a0-05ec-4a4e-9731-ba80bc9845c2.png)
- `bilingual-output`：是否输出文本的双语版本。
- `langcode`：输出 epub 文件的语言代码（例如 `ja` 表示日语，`zh` 表示中文等）。

## 输出


脚本的输出将是一个与输入文件同名的 EPUB 文件，但在末尾附加了`_translated`。 例如，如果输入文件是`example.pdf`，输出文件将是`example_translated.epub` 与`example_translated.txt`。

## 版权

这个工具是在 MIT 许可证下发布的。
