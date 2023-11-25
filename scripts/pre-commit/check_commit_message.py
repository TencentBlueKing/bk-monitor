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
import re
import sys

"""
校验提交信息是否包含规范的前缀
"""


ALLOWED_COMMIT_MSG_PREFIX = [
    ("feat", "A new feature. Correlates with MINOR in SemVer"),
    ("fix", "A bug fix. Correlates with PATCH in SemVer"),
    ("docs", "Documentation only changes"),
    ("style", "Changes that do not affect the meaning of the code"),
    ("refactor", "A code change that neither fixes a bug nor adds a feature"),
    ("perf", "A code change that improves performance"),
    ("test", "Adding missing or correcting existing tests"),
    ("chore", "Changes to the build process or auxiliary tools and libraries such as documentation generation"),
    ("merge", "Merge branch and fix conflicts"),
]


def get_commit_message():
    args = sys.argv
    if len(args) <= 1:
        print("Warning: The path of file `COMMIT_EDITMSG` not given, skipped!")
        return 0
    commit_message_filepath = args[1]
    with open(commit_message_filepath, "r", encoding="utf-8") as fd:
        content = fd.read()
    return content.strip().lower()


def main():
    content = get_commit_message()

    result = re.match(r"^(\w+)(\(\S+\))?!?:\s*([^\n\r]+)$", content)
    if result:
        label, scope, subject = result.groups()
        for prefix in ALLOWED_COMMIT_MSG_PREFIX:
            if label == prefix[0]:
                return 0

    print("Commit Message 不符合规范！必须包含以下前缀之一：")
    for prefix in ALLOWED_COMMIT_MSG_PREFIX:
        print("%-12s\t- %s" % prefix)

    return 1


if __name__ == "__main__":
    exit(main())
