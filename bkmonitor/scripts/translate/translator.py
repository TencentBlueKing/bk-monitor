# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""


import json
import sys
from time import sleep

from googletrans import Translator as GooleTrans

from .config import COLLECTED_WORDS_FILE, STANDARD_WORDS_FILE, TRANSLATE_INTERVAL, TRANSLATE_WORDS_FILE


class Translator(object):
    def __init__(self):
        self.translator = GooleTrans(
            service_urls=[
                "translate.google.cn",
            ]
        )

        data = self.read(COLLECTED_WORDS_FILE, [])
        self.words = [record["word"] for record in data]
        self.translated_words = self.read(TRANSLATE_WORDS_FILE, {})
        self.standard_words = self.read(STANDARD_WORDS_FILE, {})
        self.translated_word_count = len(self.translated_words)

    @staticmethod
    def read(file_path, default):
        try:
            with open(file_path, "r") as f:
                return json.loads(f.read()) or default
        except IOError:
            return default

    @staticmethod
    def write(file_path, data):
        with open(file_path, "w+") as f:
            f.write(json.dumps(data, indent=2, ensure_ascii=False))

    def run(self):
        for word in self.words:
            print("translating word '{}'".format(word))

            # 标准翻译字典
            if word in self.standard_words:
                self.translated_words[word] = self.standard_words[word]

            # 使用API翻译
            if word not in self.translated_words:
                try:
                    t = self.translator.translate(word, dest="en")
                    self.translated_words[word] = t.text
                    self.write(TRANSLATE_WORDS_FILE, self.translated_words)
                    sleep(TRANSLATE_INTERVAL)
                except Exception as e:
                    print("translate error: {}".format(e))

        print("translate {} words".format(len(self.translated_words) - self.translated_word_count))

    @property
    def no_translate(self):
        no_translate_words = [word for word in self.words if word not in self.translated_words]
        return len(no_translate_words)


if __name__ == "__main__":
    translator = Translator()
    translator.run()
