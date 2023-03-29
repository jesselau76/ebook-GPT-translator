# ebook-GPT-Translator: : Enjoy reading with your favorite style.

[En](https://github.com/jesselau76/ebook-GPT-translator/blob/main/README.md) | [中文说明](https://github.com/jesselau76/ebook-GPT-translator/blob/main/README-zh.md)

该工具旨在帮助用户将文本从一种格式转换为另一种格式，以及使用 OpenAI API (model=`gpt-3.5-turbo`) 将其翻译成另一种语言。 目前支持PDF、DOCX、MOBI和EPUB文件格式转换翻译成EPUB文件及文本文件，可以将文字翻译成多种语言。

注：
- PDF、DOCX及MOBI文件只处理其中文本部分，图形部分不会出现在结果文件中。
- EPUB文件的图形部分全部放在每章之初，因EPUB文件为HTML语言格式，若保持原有格式需要大量拆分文字，以多段文字一并翻译保持翻译水准为原则，故图形部分不保持在原有位置，而全部放在每章最初。
- 初始页面、最终页面设置仅支持PDF文件。因EPUB、DOCX、MOBI及TXT文件等因字体大小，页面大小会有不同，无法处理页码。


你需要申请OpenAI API KEY,[申请地址](https://platform.openai.com/)，现有免费使用额度，3个月有效。

## 安装

要使用此工具，您需要在系统上安装 Python 3 以及以下软件包：

- pdfminer
- openai
- tqdm
- ebooklib
- bs4
- docx
- mobi

您可以通过运行以下命令来安装这些软件包：
```
pip install -r requirements.txt
```

git clone本git

```
git clone https://github.com/jesselau76/ebook-GPT-translator.git
```
升级到新版
```
cd ebook-GPT-translator
git pull
pip install -r requirements.txt
```
## 用法

使用前将settings.cfg.example改名为settings.cfg并用任何一款编辑器编辑.
```
cd ebook-GPT-translator
mv settings.cfg.example settings.cfg
nano settings.cfg
```
打开settings.cfg文件后
```
openai-apikey = sk-xxxxxxx
```

将sk-xxxxxxx替换为你的OpenAI api key.
修改其他选项，然后退出保存

如果需要先测试prompt,可以加--test参数只翻译前三段短文字。
运行命令：

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

或者要翻译名为 `example.docx` 的 docx 文件，您可以运行以下命令：
```
python3 text_translation.py example.docx
```

或者要翻译名为 `example.mobi` 的 mobi 文件，您可以运行以下命令：

```
python3 text_translation.py example.mobi
```
或者要翻译名为 `example.txt` 的 text 文件，您可以运行以下命令：
```
python3 text_translation.py example.txt
```
默认情况下，脚本会尝试将文本翻译成在 `target-language` 选项下的 `settings.cfg` 文件中指定的语言。 您还可以通过将`bilingual-output`选项设置为`True`来选择输出文本的双语版本。

## 特点
- 代码从 settings.cfg 文件中读取 OpenAI API 密钥、目标语言和其他选项。
- 该代码分别使用 pdfminer 和 ebooklib 库将 PDF、DOCX 和 EPUB 文件转换为文本。
- 该代码提供了一个选项来输出双语文本。
- 代码提供了一个进度条来显示PDF/EPUB到文本转换和翻译的进度
- 测试功能，只翻译前三页以节省API用量。
## 配置

`settings.cfg` 文件包含几个可用于配置脚本行为的选项：

- `openai-apikey`：您的 OpenAI API 的API Key
- `target-language`：您要将文本翻译成的语言（例如，`ja` 用于日语，`zh` 用于中文，也可加入风格描述，如`文言文`、`红楼梦风格的半文言文`等）。
![文言文](https://user-images.githubusercontent.com/40444824/223943798-4faf91a0-05ec-4a4e-9731-ba80bc9845c2.png)

- `bilingual-output`：是否输出文本的双语版本。
- `langcode`：输出 epub 文件的语言代码（例如 `ja` 表示日语，`zh` 表示中文等）。
- `startpage`: 从指定的起始页码开始翻译，且仅适用于PDF文件。
- `endpage`: 翻译将持续到PDF文件中指定的页码。此功能仅支持PDF文件。如果输入等于-1，则翻译将继续到文件结束。

## 输出


脚本的输出将是一个与输入文件同名的 EPUB 文件，但在末尾附加了`_translated`。 例如，如果输入文件是`example.pdf`，输出文件将是`example_translated.epub` 与`example_translated.txt`。

## 版权

这个工具是在 MIT 许可证下发布的。

## 免责声明：

本项目仅适用于已进入公共领域的书籍和资料。它不适用于受版权保护的内容。在使用本项目之前，我们强烈建议用户仔细查阅版权信息，并遵守相关法律法规，以保护自己和他人的权益。

对于因使用本项目而造成的任何损失或损害，本项目的作者和开发者概不负责。用户需承担与本项目使用相关的所有风险。在使用本项目之前，用户有责任确保已获得原版权持有者的许可，或使用开源 PDF、EPUB 或 MOBI 文件，以避免潜在的版权风险。

如果您对本项目的使用有任何疑虑或建议，请通过问题（issues）部分与我们联系。