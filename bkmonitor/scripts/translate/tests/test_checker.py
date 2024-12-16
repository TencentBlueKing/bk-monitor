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
import unittest

from ..checker import TranslateChecker, TranslateFinder, TranslateFuncFinder


class TranslateFuncFinderTest(unittest.TestCase):
    def test_import_finder(self):
        node = ast.parse(
            """
from django.utils.translation import gettext as _, gettext_lazy as _lazy
        """
        )
        parser = TranslateFuncFinder()
        parser.visit(node)
        self.assertSetEqual(parser.trans_func_names, {"_"})
        self.assertSetEqual(parser.lazy_trans_func_names, {"_lazy"})


class TranslateFinderTest(unittest.TestCase):
    def test_import_finder(self):
        with open("test_data.txt", "r") as f:
            node = ast.parse(f.read())

        for n in ast.walk(node):
            for child in ast.iter_child_nodes(n):
                child.parent = n

        parser = TranslateFinder({"_"}, {"_lazy"})
        parser.visit(node)
        errors = parser.errors
        self.assertEqual(len(errors["should_use_lazy"]), 1)
        self.assertEqual(errors["should_use_lazy"][0].s, "字符串2")
        self.assertEqual(len(errors["no_trans"]), 2)
        self.assertEqual(errors["no_trans"][0].s, "字符串")
        self.assertEqual(errors["no_trans"][1].s, "返回值")

        parser = TranslateFinder(set(), set())
        parser.visit(node)
        errors = parser.errors
        self.assertEqual(len(errors["no_import"]), 1)


class TranslateCheckerTest(unittest.TestCase):
    def test_checker(self):
        checker = TranslateChecker(None, "test_data.txt")
        result = [
            (
                19,
                10,
                'TRAN3 string("字符串2") should use lazy translate function.',
            ),
            (
                11,
                4,
                'TRAN2 string("字符串") no translate.',
            ),
            (
                25,
                15,
                'TRAN2 string("返回值") no translate.',
            ),
        ]

        errors = checker.run()
        for index, error in enumerate(errors):
            self.assertEqual(error[:3], result[index])


if __name__ == "__main__":
    unittest.main()
