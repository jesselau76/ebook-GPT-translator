# ebook-GPT-translator: Enjoy reading with your favorite style.
[En](https://github.com/jesselau76/ebook-GPT-translator/blob/main/README.md) | [中文说明](https://github.com/jesselau76/ebook-GPT-translator/blob/main/README-zh.md)

This tool is designed to help users convert text from one format to another, as well as translate it into a different language using the OpenAI API (model="gpt-3.5-turbo"). It currently supports converting and translating PDF, DOCX, EPUB, and MOBI file formats into EPUB and text files and can translate text into multiple languages.

Notes:

- For  PDF, DOCX, and MOBI files, only the text portions will be processed, and graphical elements will not appear in the resulting files.
- For EPUB files, all graphical elements will be placed at the beginning of each chapter, as EPUB files use HTML language format. To maintain translation quality, the text will be translated in multiple segments without preserving the original formatting, so graphical elements will not be kept in their original positions but will be placed at the beginning of each chapter.
- The startpage and endpage settings are only supported for PDF files. This is because the font size and page size may vary in EPUB, DOCX, MOBI,and TXT files, making it difficult to process.

## Installation

To use this tool, you will need to have Python 3 installed on your system, as well as the following packages:

- pdfminer
- openai
- tqdm
- ebooklib
- bs4
- docx
- mobi

You can install these packages by running the following command:
```
pip install -r requirements.txt
```

git clone

```
git clone https://github.com/jesselau76/ebook-GPT-translator.git
```

Update to new version
```
cd ebook-GPT-translator
git pull
pip install -r requirements.txt
```
## Usage

To use this tool, you need rename settings.cfg.example to settings.cfg at first.
```
cd ebook-GPT-translator
mv settings.cfg.example settings.cfg
nano settings.cfg
```

```
openai-apikey = sk-xxxxxxx
```
replace sk-xxxxxxx to your OpenAI api key.
Change others options then press CTRL-X to save.

run the command: 
```
python3 text_translation.py [-h] [--test] filename

positional arguments:
  filename    Name of the input file

options:
  -h, --help  show this help message and exit
  --test      Only translate the first 3 short texts
```

Simply run the `text_translation.py` script with the file you want to translate or convert as an argument. For example, to translate a PDF file named `example.pdf`, you would run the following command:

```
python3 text_translation.py example.pdf
```
or to translate a epub file named `example.epub`, you would run the following command:
```
python3 text_translation.py example.epub
```

or to translate a docx file named `example.docx`, you would run the following command:
```
python3 text_translation.py example.docx
```

or to translate a text file named `example.txt`, you would run the following command:
```
python3 text_translation.py example.txt
```

to translate a MOBI file named example.mobi, you would run the following command:
```
python3 text_translation.py example.mobi
```
By default, the script will attempt to translate the text into the language specified in the `settings.cfg` file under the `target-language` option. You can also choose to output a bilingual version of the text by setting the `bilingual-output` option to `True`.

## Feature
- The code reads the OpenAI API key, target language, and other options from a settings.cfg file.
- The code converts PDF, DOCX and EPUB files to text using the pdfminer and ebooklib libraries, respectively.
- The code provides an option to output bilingual text.
- The code provides a progress bar to show the progress of PDF/EPUB to text conversion and translation
- Test function available. Only translate 3 short texts to save your API usage with --test.

## Configuration

The `settings.cfg` file contains several options that can be used to configure the behavior of the script:

- `openai-apikey`: Your API key for the OpenAI API.
- `target-language`: The language you want to translate the text into (e.g. `ja` for Japanese, `zh` for Chinese, `文言文` or `红楼梦风格的半文言文` etc.).
![文言文](https://user-images.githubusercontent.com/40444824/223943798-4faf91a0-05ec-4a4e-9731-ba80bc9845c2.png)
- `bilingual-output`: Whether or not to output a bilingual version of the text.
- `langcode`: The language code for the output epub file (e.g. `ja` for Japanese, `zh` for Chinese, etc.).
- `startpage`: Translation begins from the specified start page number and is exclusively available for PDF files.
- `endpage`: Translation will continue until the specified page number in a PDF file. This feature supports PDF files exclusively. If the input is equal to -1, the translation will proceed until the end of the file.


## Output


The output of the script will be an EPUB file with the same name as the input file, but with `_translated` appended to the end. For example, if the input file is `example.pdf`, the output file will be `example_translated.epub` and `example_translated.txt`.

## License

This tool is released under the MIT License.

## Disclaimer:

This project is intended for use with public domain books and materials only. It is not designed for use with copyrighted content. Users are strongly advised to carefully review copyright information before utilizing this project and to adhere to relevant laws and regulations in order to protect their own rights and the rights of others.

The authors and developers of this project shall not be held responsible for any loss or damage resulting from the use of this project. Users assume all risks associated with its use. It is the responsibility of users to ensure they have obtained permission from the original copyright holder or used open-source PDF, EPUB, or MOBI files before employing this project to avoid potential copyright risks.

If you have any concerns or suggestions about the use of this project, please contact us through the issues section.