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

from apps.log_extract.handlers.explorer import ExplorerHandler

USER = "admin"


class TestFilterServerAccessFile(TestCase):
    """
    测试日志提取的目录与文件鉴权匹配口径
    """

    def test_dir_with_dot_in_path(self):
        """
        测试目录鉴权，授权目录中的 '.' 不能当作正则通配符匹配到形近目录
        """
        allowed_dir_file_list = [{"file_path": "/data/a/.npc/", "file_type": {".log"}, "operator": USER}]
        for request_dir in ["/data/a/.npc/", "/data/a/.npc/sub/"]:
            self.assertTrue(ExplorerHandler.filter_server_access_file(allowed_dir_file_list, request_dir, "dirname"))
        for request_dir in ["/data/a/xnpc/", "/data/a/1npc/sub/"]:
            self.assertFalse(ExplorerHandler.filter_server_access_file(allowed_dir_file_list, request_dir, "dirname"))

    def test_dir_without_special_chars(self):
        """
        测试目录鉴权，不含正则元字符的授权目录匹配行为保持不变
        """
        allowed_dir_file_list = [{"file_path": "/data/logs/", "file_type": {".log"}, "operator": USER}]
        self.assertTrue(ExplorerHandler.filter_server_access_file(allowed_dir_file_list, "/data/logs/app/", "dirname"))
        self.assertFalse(ExplorerHandler.filter_server_access_file(allowed_dir_file_list, "/data/other/", "dirname"))

    def test_dir_with_other_regex_metacharacters(self):
        """
        测试目录鉴权，授权目录中的括号与星号按字面匹配而非正则语义
        """
        allowed_dir_file_list = [{"file_path": "/data/logs(1)/", "file_type": {".log"}, "operator": USER}]
        self.assertTrue(
            ExplorerHandler.filter_server_access_file(allowed_dir_file_list, "/data/logs(1)/app/", "dirname")
        )
        self.assertFalse(ExplorerHandler.filter_server_access_file(allowed_dir_file_list, "/data/logs1/", "dirname"))

        allowed_dir_file_list = [{"file_path": "/data/logs*/", "file_type": {".log"}, "operator": USER}]
        self.assertTrue(ExplorerHandler.filter_server_access_file(allowed_dir_file_list, "/data/logs*/app/", "dirname"))
        self.assertFalse(ExplorerHandler.filter_server_access_file(allowed_dir_file_list, "/data/log/", "dirname"))

    def test_dir_with_unbalanced_bracket(self):
        """
        测试目录鉴权，未闭合方括号不再触发正则编译异常
        """
        allowed_dir_file_list = [{"file_path": "/data/[abc/", "file_type": {".log"}, "operator": USER}]
        self.assertTrue(ExplorerHandler.filter_server_access_file(allowed_dir_file_list, "/data/[abc/app/", "dirname"))
        self.assertFalse(ExplorerHandler.filter_server_access_file(allowed_dir_file_list, "/data/other/", "dirname"))

    def test_file_branch_unaffected(self):
        """
        测试文件鉴权分支行为不变
        """
        allowed_dir_file_list = [{"file_path": "/data/logs/", "file_type": {".log"}, "operator": USER}]
        self.assertTrue(ExplorerHandler.filter_server_access_file(allowed_dir_file_list, "/data/logs/app.log"))
        self.assertFalse(ExplorerHandler.filter_server_access_file(allowed_dir_file_list, "/data/logs/app.txt"))
