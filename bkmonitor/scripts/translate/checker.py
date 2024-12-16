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


import ast
import re
import sys
from collections import defaultdict

import pycodestyle

"""
Django Translate Checker
"""

try:
    from flake8.engine import pep8 as stdin_utils
except ImportError:
    from flake8 import utils as stdin_utils


__version__ = "0.0.1"

Messages = {
    "no_trans": 'TRAN2 string("{}") no translate.',
    "should_use_lazy": 'TRAN3 string("{}") should use lazy translate function.',
    "no_import": "TRAN1 has need translate string but no import translate function.",
}

# 待检测字符串匹配的正则
StringRegex = r"[\u4e00-\u9fff]"  # noqa

ImportPath = "django.utils.translation"
ImportNames = ["gettext", "pgettext", "ngettext", "npgettext"]
LazyImportNames = ["{}_lazy".format(name) for name in ImportNames] + ["gettext_noop"]


class TranslateFuncFinder(ast.NodeVisitor):
    def __init__(self, *args, **kwargs):
        super(TranslateFuncFinder, self).__init__(*args, **kwargs)
        self.trans_func_names = set()
        self.lazy_trans_func_names = set()

    def visit_ImportFrom(self, node):
        """
        遍历文件中的包导入语句，确定翻译函数名称
        """
        if node.module != ImportPath:
            return

        for name in node.names:
            if name.name in ImportNames:
                self.trans_func_names.add(name.asname or name.name)
            elif name.name in LazyImportNames:
                self.lazy_trans_func_names.add(name.asname or name.name)


class TranslateFinder(ast.NodeVisitor):
    def __init__(self, trans_func_names, lazy_trans_func_names, *args, **kwargs):
        """

        :param trans_func_names: set
        :type trans_func_names: set
        :param lazy_trans_func_names: set
        :type lazy_trans_func_names: set
        :param args:
        :param kwargs:
        """
        super(TranslateFinder, self).__init__(*args, **kwargs)
        self.errors = defaultdict(list)
        self.words = []
        self.trans_func_names = trans_func_names
        self.lazy_trans_func_names = lazy_trans_func_names
        self.all_trans_func_names = set()
        self.all_trans_func_names.update(trans_func_names, lazy_trans_func_names)

    @staticmethod
    def is_in_func(node):
        """
        是否在函数中
        """
        parent = node.parent

        in_func = False
        while not isinstance(parent, ast.Module):
            if isinstance(parent, (ast.Lambda, ast.FunctionDef)):
                in_func = True
                break

            parent = parent.parent

        return in_func

    @staticmethod
    def is_in_assign(node):
        """
        是否在表达式中
        """
        parent = node.parent

        in_assign = False
        while not isinstance(parent, ast.Module):
            if isinstance(parent, (ast.Assign, ast.Return)):
                in_assign = True
                break

            parent = parent.parent

        return in_assign

    @staticmethod
    def get_near_call(node):
        """
        最近的函数调用
        """
        while not isinstance(node, ast.Module):
            if isinstance(node, ast.Call):
                return node
            node = node.parent

    def visit_Str(self, node):
        # 如果没有引入翻译函数，则不用检查
        if "no_import" in self.errors:
            return

        # 判断属于待检测字符串
        string = node.s
        if isinstance(string, str):
            string = string.decode("utf8")
        if not re.findall(StringRegex, string):
            return

        # 非表达式中的字符串忽略
        if not self.is_in_assign(node):
            return

        # 判断是否有引入翻译函数
        if not self.trans_func_names and not self.lazy_trans_func_names:
            self.errors["no_import"] = [node]
            return

        # 收集已被标记字符串
        if isinstance(node.parent, ast.Call):
            func_id = getattr(node.parent.func, "id", None) or node.parent.func.attr
            if func_id in self.all_trans_func_names:
                self.words.append(node)

        # 检查是否存在未翻译字符串
        call = self.get_near_call(node)
        if call:
            func_id = getattr(call.func, "id", None) or call.func.attr
            if self.is_in_func(node):
                if func_id not in self.all_trans_func_names:
                    self.errors["no_trans"].append(node)
            else:
                if func_id in self.trans_func_names:
                    self.errors["should_use_lazy"].append(node)
                elif func_id not in self.lazy_trans_func_names:
                    self.errors["no_trans"].append(node)
        else:
            self.errors["no_trans"].append(node)


class TranslateChecker(object):
    options = None
    name = "flake8-translate-checker"
    version = __version__

    def __init__(self, tree, filename):
        self.tree = tree
        self.filename = filename
        self.lines = None

    def load_file(self):
        if self.filename in ("stdin", "-", None):
            self.filename = "stdin"
            self.lines = stdin_utils.stdin_get_value().splitlines(True)
        else:
            self.lines = pycodestyle.readlines(self.filename)

        # 过滤文件编码声明
        self.lines = [line for line in self.lines if not re.match(r"#.*coding.*", line)]

        if not self.tree:
            self.tree = ast.parse("".join(self.lines))

    def parse(self):
        # 加载待检测文件
        if not self.tree or not self.lines:
            self.load_file()

        # 记录父节点
        for node in ast.walk(self.tree):
            for child in ast.iter_child_nodes(node):
                child.parent = node
        parser = TranslateFuncFinder()
        parser.visit(self.tree)

        parser = TranslateFinder(parser.trans_func_names, parser.lazy_trans_func_names)
        parser.visit(self.tree)
        return parser

    def run(self):
        parser = self.parse()
        errors = parser.errors

        for key, values in list(errors.items()):
            for value in values:
                yield (value.lineno, value.col_offset, Messages[key].format(value.s), TranslateChecker)
