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
import random
import time

from googletrans import Translator as GooleTrans

default = []


def safe_encode(s):
    try:
        return s.decode("utf-8")
    except Exception:
        return s


class ScanPoFile(object):
    def __init__(self):
        self.translator = GooleTrans(
            service_urls=[
                "translate.google.cn",
                "translate.google.com.hk",
                "translate.google.com.tw",
                "translate.google.com",
            ]
        )
        self.translator.raise_exception = True

    def _translate(self, ready_to_tran):
        try:
            random_int = random.random()
            time.sleep(random_int)
            t = self.translator.translate(ready_to_tran, dest="en")
            print("翻译成功:{}-->{}".format(ready_to_tran, t.text))
            return t.text
        except Exception as e:
            print("翻译失败, 原因:{}, 当前语句：{}".format(e, ready_to_tran))
            return "翻译失败"

    def scan(self, po_file):
        write_list = []
        with open(po_file, "rb") as f:
            ori_content = []
            wait_for_write = False
            for line in f.readlines():
                line = safe_encode(line)
                if wait_for_write:
                    if not line.strip():
                        if ori_content[0].strip() == '""':
                            ori_content = ori_content[1:]
                        ready_to_tran = "".join(map(str.strip, ori_content)).replace('""', "")
                        if self._translate(ready_to_tran) != "翻译失败":
                            write_list.pop()
                            write_list.extend(['msgstr ' + self._translate(ready_to_tran), "\n"])
                        ori_content = []
                    write_list.append(line)
                    wait_for_write = False
                elif line.startswith('msgid "'):
                    ori_content = [
                        line[6:],
                    ]
                    write_list.append(line)
                elif line.startswith('msgstr ""') and ori_content:
                    wait_for_write = True
                    write_list.append(line)
                elif line.startswith('"') and ori_content:
                    ori_content.append(line)
                    write_list.append(line)
                else:
                    write_list.append(line)
            #     # 添加默认翻译的内容
            #     for i in default:
            #         if i in line:
            #             continue
            #         if i not in write_list:
            #             write_list.append('msgid "{}"\n'.format(i))
            #             write_list.append('msgstr "{}"\n'.format(self._translate(i)))

        content = "".join(write_list)
        with open(po_file, "w", encoding="utf-8") as f:
            # 如果这里报错了，要回滚下po文件，要不然就没了
            f.write(content)


def main():
    from argparse import ArgumentParser

    parser = ArgumentParser(description="fill .po file with excel resource")
    parser.add_argument("-p", "--pofile", help=".po file to handle")
    args = parser.parse_args()
    scanner = ScanPoFile()
    scanner.scan(args.pofile)


if __name__ == "__main__":
    main()
