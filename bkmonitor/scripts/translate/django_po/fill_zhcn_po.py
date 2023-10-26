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


def safe_encode(s):
    try:
        return s.decode("utf-8")
    except:
        return s


class ScanPoFile(object):
    def __init__(self):
        pass

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
                        write_list.extend(ori_content)
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

        # print ''.join(write_list)
        content = "".join(write_list)
        with open(po_file, "w", encoding="utf-8") as f:
            f.write(content)
        pass


def main():
    from argparse import ArgumentParser

    parser = ArgumentParser(description="fill .po file with excel resource")
    parser.add_argument("-p", "--pofile", help=".po file to handle")
    args = parser.parse_args()

    scanner = ScanPoFile()
    scanner.scan(args.pofile)


if __name__ == "__main__":
    main()
