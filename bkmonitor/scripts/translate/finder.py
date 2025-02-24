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
import os
import sys

from .checker import TranslateChecker
from .config import COLLECTED_WORDS_FILE

Suffix = ".py"


def list_dir(path, suffix, exclude_path_list=None):
    """
    找到待检测文件
    """
    ret = []
    dirs = os.listdir(path)
    for i in dirs:
        if i.startswith(".") or i.startswith("~"):
            continue
        abs_path = os.path.join(path, i)
        if exclude_path_list and any(abs_path.startswith(i) for i in exclude_path_list):
            continue
        if i.endswith(suffix):
            ret.append(abs_path)
        elif os.path.isdir(abs_path):
            ret += list_dir(abs_path, suffix=suffix, exclude_path_list=exclude_path_list)
    return ret


def main():
    from argparse import ArgumentParser

    parser = ArgumentParser(description="Find chinese string from file")
    parser.add_argument("path", help="[file|file path] to handle")
    parser.add_argument("-e", "--exclude", nargs="*", help="exclude file path")
    args = parser.parse_args()

    if os.path.isdir(args.path):
        file_lists = list_dir(args.path, suffix=Suffix, exclude_path_list=args.exclude)
    else:
        file_lists = [
            args.path,
        ]

    process_count = 0
    error_count = 0
    collected_words = []
    for each_file in file_lists:
        try:
            print("processing: %s" % each_file)
            checker = TranslateChecker(None, filename=each_file)
            finder = checker.parse()
            for word in finder.words:
                collected_words.append(
                    {
                        "file": each_file,
                        "word": word.s,
                        "lineno": word.lineno,
                        "col_offset": word.col_offset,
                    }
                )

            process_count += 1
        except Exception as e:
            error_count += 1
            import traceback

            traceback.print_exc()
            print("Error: process file:{}, message: {}".format(each_file, e), file=sys.stderr)

    with open(COLLECTED_WORDS_FILE, "w+") as f:
        f.write(json.dumps(collected_words, indent=2, ensure_ascii=False))

    print("process {} files, error {} files, collect {} words".format(process_count, error_count, len(collected_words)))


if __name__ == "__main__":
    main()
