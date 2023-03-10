# pdf-epub-GPT-translator

[En](https://github.com/jesselau76/pdf-epub-GPT-translator/blob/main/README.md) | [中文说明](https://github.com/jesselau76/pdf-epub-GPT-translator/blob/main/README-zh.md)

This tool is designed to help users convert text from one format to another, as well as translate it into a different language using the OpenAI API (model="gpt-3.5-turbo"). It currently supports PDF and EPUB file formats for conversion, and can translate text into a variety of languages.

## Installation

To use this tool, you will need to have Python 3 installed on your system, as well as the following packages:

- pdfminer
- openai
- tqdm
- nltk
- ebooklib
- bs4

You can install these packages by running the following command:
```
pip install pdfminer pdfminer.six openai tqdm nltk ebooklib bs4
```

git clone

```
git clone https://github.com/jesselau76/pdf-epub-GPT-translator.git
```

## Usage

To use this tool, you need change setting.cfg at first.
```
cd pdf-epub-GPT-translator
nano settings.cfg
```

```
openai-apikey = sk-xxxxxxx
```
replace sk-xxxxxxx to your OpenAI api key.

Simply run the `text_translation.py` script with the file you want to translate or convert as an argument. For example, to translate a PDF file named `example.pdf`, you would run the following command:

```
python3 text_translation.py example.pdf
```
or to translate a epub file named `example.epub`, you would run the following command:
```
python3 text_translation.py example.epub
```

or to translate a text file named `example.txt`, you would run the following command:
```
python3 text_translation.py example.txt
```

By default, the script will attempt to translate the text into the language specified in the `settings.cfg` file under the `target-language` option. You can also choose to output a bilingual version of the text by setting the `bilingual-output` option to `True`.

## Feature
- The code reads the OpenAI API key, target language, and other options from a settings.cfg file.
- The code converts PDF and EPUB files to text using the pdfminer and ebooklib libraries, respectively.
- The code provides an option to output bilingual text.
- The code provides a progress bar to show the progress of PDF/EPUB to text conversion and translation

## Configuration

The `settings.cfg` file contains several options that can be used to configure the behavior of the script:

- `openai-apikey`: Your API key for the OpenAI API.
- `target-language`: The language you want to translate the text into (e.g. `ja` for Japanese, `zh` for Chinese, `文言文` or `红楼梦风格的半文言文` etc.).
![文言文](https://user-images.githubusercontent.com/40444824/223943798-4faf91a0-05ec-4a4e-9731-ba80bc9845c2.png)
- `bilingual-output`: Whether or not to output a bilingual version of the text.
- `langcode`: The language code for the output epub file (e.g. `ja` for Japanese, `zh` for Chinese, etc.).

## Output


The output of the script will be an EPUB file with the same name as the input file, but with `_translated` appended to the end. For example, if the input file is `example.pdf`, the output file will be `example_translated.epub` and `example_translated.txt`.

## License

This tool is released under the MIT License.
