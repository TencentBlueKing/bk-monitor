"""
Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
License for BK-LOG 蓝鲸日志平台:
--------------------------------------------------------------------
Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all copies or substantial
portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN
NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
We undertake not to change the open source license (MIT license) applicable to the current version of
the project delivered to anyone in the future.
"""

from django.test import TestCase
from rest_framework.exceptions import ValidationError

from apps.log_extract.serializers import check_file_path_legal


class TestCheckFilePathLegal(TestCase):
    def test_normal_path_passed(self):
        for file_path in [
            "/data/logs/",
            "/data/home/user00/hjol/ai-npc-1.0/logs/",
            "/data/logs/a.log",
            "/data/logs/*.log",
        ]:
            with self.subTest(file_path=file_path):
                check_file_path_legal(file_path)

    def test_relative_segment_rejected(self):
        # '/data/logs/..' 结尾没有后继斜杠，是最容易被漏拦的形式
        for file_path in ["/data/logs/../etc/", "/data/./logs/", "/data/logs/..", "/data/logs/.", "/..", "/."]:
            with self.subTest(file_path=file_path):
                with self.assertRaises(ValidationError) as ctx:
                    check_file_path_legal(file_path)
                self.assertIn("相对路径", str(ctx.exception))

    def test_hidden_path_rejected(self):
        # 点开头的目录与文件常用于存放凭证，需要与相对路径给出不同的提示
        for file_path in [
            "/data/home/user00/hjol/ai-npc-1.0/.npc/",
            "/data/home/user00/.ssh/id_rsa",
            "/data/home/user00/.netrc",
        ]:
            with self.subTest(file_path=file_path):
                with self.assertRaises(ValidationError) as ctx:
                    check_file_path_legal(file_path)
                self.assertIn("开头", str(ctx.exception))

    def test_malformed_path_rejected(self):
        for file_path in ["data/logs/", "/data//logs/", "/data/logs/a b.log", "/data/logs/$(whoami)/"]:
            with self.subTest(file_path=file_path):
                with self.assertRaises(ValidationError):
                    check_file_path_legal(file_path)
