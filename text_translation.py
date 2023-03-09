# -*- coding: utf-8 -*-

import pdfminer.high_level
import re
import openai
from tqdm import tqdm
import nltk
nltk.download('punkt')
from nltk.tokenize import sent_tokenize
import ebooklib
from ebooklib import epub
import os
from bs4 import BeautifulSoup
import configparser

# 读取option文件
config = configparser.ConfigParser()
config.read('settings.cfg')

# 获取openai_apikey和language
openai_apikey = config.get('option', 'openai-apikey')
language_name = config.get('option', 'target-language')
bilingual_output = config.get('option', 'bilingual-output')
language_code = config.get('option', 'langcode')
# 设置openai的API密钥
openai.api_key = openai_apikey

def convert_epub_to_text(epub_filename):
    # 打开epub文件
    book = epub.read_epub(epub_filename)
    
    # 获取所有文本
    text = ""
    for item in book.get_items():
        if item.get_type() == ebooklib.ITEM_DOCUMENT:
            # 使用BeautifulSoup提取纯文本
            soup = BeautifulSoup(item.get_content(), 'html.parser')
            text += re.sub(r'\n+', '\n', soup.get_text().strip())
    
    # 返回文本
    return text

def text_to_epub(text, filename, language_code='en'):
    text = text.replace("\n", "<br>")
    # 创建epub书籍对象
    book = epub.EpubBook()

    # 设置元数据
    book.set_identifier('id')
    book.set_title('Title')
    book.set_language(language_code)

    # 创建章节对象
    c = epub.EpubHtml(title='Chapter 1', file_name='chap_1.xhtml', lang=language_code)
    c.content = text

    # 将章节添加到书籍中
    book.add_item(c)

    # 添加toc
    book.toc = (epub.Link('chap_1.xhtml', 'Chapter 1', 'chap_1'),)
    # 设置书脊顺序
    book.spine = ['nav', c]
    # 添加导航
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())

    # 设置书籍封面
    # book.set_cover('image.jpg', open('image.jpg', 'rb').read())

    # 将书籍写入文件
    epub.write_epub(filename, book, {})
# 将PDF文件转换为文本
def convert_pdf_to_text(pdf_filename):
    with open(pdf_filename, 'rb') as file:
        text = pdfminer.high_level.extract_text(file)
        return text

# 将文本分成不大于1024字符的短文本list
def split_text(text):
    # 使用nltk将文本分割为句子
    sentence_list = sent_tokenize(text)
    # 初始化短文本列表
    short_text_list = []
    # 初始化当前短文本
    short_text = ""
    # 遍历句子列表
    for s in sentence_list:
        # 如果当前短文本加上新的句子长度不大于1024，则将新的句子加入当前短文本
        if len(short_text + s) <= 1024:
            short_text += s
        # 如果当前短文本加上新的句子长度大于1024，则将当前短文本加入短文本列表，并重置当前短文本为新的句子
        else:
            short_text_list.append(short_text)
            short_text = s
    # 将最后的短文本加入短文本列表
    short_text_list.append(short_text)
    return short_text_list

# 将句号替换为句号+回车
def return_text(text):
    text = text.replace(".", ".\n")
    text = text.replace("。", "。\n")
    text = text.replace("！", "！\n")
    return text
# 翻译短文本
def translate_text(text):
    
    # 调用openai的API进行翻译
    try:
        completion = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "user",
                    
                    "content": f"translate the following text into {language_name}: \n{text}",
                }
            ],
        )
        t_text = (
            completion["choices"][0]
            .get("message")
            .get("content")
            .encode("utf8")
            .decode()
        )
    except Exception as e:
        import time
        # TIME LIMIT for open api please pay
        sleep_time = 60
        time.sleep(sleep_time)
        print(e, f"will sleep  {sleep_time} seconds")
        
        completion = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "user",
                    "content": f"translate the following text into {language_name}: \n{text}",
                }
            ],
        )
        t_text = (
            completion["choices"][0]
            .get("message")
            .get("content")
            .encode("utf8")
            .decode()
        )
    
    return t_text

    
    

# 获取命令行参数
import sys
filename = sys.argv[1]
base_filename, file_extension = os.path.splitext(filename)
new_filename = base_filename + "_translated.epub"
new_filenametxt = base_filename + "_translated.txt"
text = ""
# 根据文件类型调用相应的函数
if filename.endswith('.pdf'):
    with tqdm(total=10, desc="Converting PDF to text") as pbar:
        for i in range(10):
            text = convert_pdf_to_text(filename)
            pbar.update(1)
elif filename.endswith('.epub'):
    with tqdm(total=10, desc="Converting epub to text") as pbar:
        for i in range(10):
            text = convert_epub_to_text(filename)
            pbar.update(1)
else:
    print("Unsupported file type")
# 将PDF文件转换为文本



# 将所有回车替换为空格
text = text.replace("\n", " ")

# 将多个空格替换为一个空格
import re
text = re.sub(r"\s+", " ", text)




# 将文本分成不大于1024字符的短文本list
short_text_list = split_text(text)

# 初始化翻译后的文本
translated_text = ""

# 遍历短文本列表，依次翻译每个短文本
for short_text in tqdm(short_text_list):
    print(return_text(short_text))
    # 翻译当前短文本
    translated_short_text = translate_text(short_text)
    short_text = return_text(short_text)
    translated_short_text = return_text(translated_short_text)
    # 将当前短文本和翻译后的文本加入总文本中
    if bilingual_output == "True":
        translated_text += f"{short_text}\n{translated_short_text}\n"
    else:
        translated_text += f"{translated_short_text}\n"
    #print(short_text)
    print(translated_short_text)
    
# 将翻译后的文本写入epub文件
text_to_epub(translated_text, new_filename, language_code)


# 将翻译后的文本同时写入txt文件 incase epub插件出问题
with open(new_filenametxt, "w", encoding="utf-8") as f:
    f.write(translated_text)