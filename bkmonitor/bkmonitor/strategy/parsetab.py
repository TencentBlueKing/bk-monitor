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
# parsetab.py
# This file is automatically generated. Do not edit.
# pylint: disable=W,C,R
_tabversion = "3.10"

_lr_method = "LALR"

_lr_signature = "leftANDORrightN_NOTAND LPAREN NOT OR RPAREN VARexpression : NOT expression %prec N_NOTexpression : expression OR expressionexpression : expression AND expressionexpression : VARexpression : LPAREN expression RPAREN"

_lr_action_items = {
    "NOT": (
        [
            0,
            2,
            4,
            5,
            6,
        ],
        [
            2,
            2,
            2,
            2,
            2,
        ],
    ),
    "VAR": (
        [
            0,
            2,
            4,
            5,
            6,
        ],
        [
            3,
            3,
            3,
            3,
            3,
        ],
    ),
    "LPAREN": (
        [
            0,
            2,
            4,
            5,
            6,
        ],
        [
            4,
            4,
            4,
            4,
            4,
        ],
    ),
    "$end": (
        [
            1,
            3,
            7,
            9,
            10,
            11,
        ],
        [
            0,
            -4,
            -1,
            -2,
            -3,
            -5,
        ],
    ),
    "OR": (
        [
            1,
            3,
            7,
            8,
            9,
            10,
            11,
        ],
        [
            5,
            -4,
            -1,
            5,
            -2,
            -3,
            -5,
        ],
    ),
    "AND": (
        [
            1,
            3,
            7,
            8,
            9,
            10,
            11,
        ],
        [
            6,
            -4,
            -1,
            6,
            -2,
            -3,
            -5,
        ],
    ),
    "RPAREN": (
        [
            3,
            7,
            8,
            9,
            10,
            11,
        ],
        [
            -4,
            -1,
            11,
            -2,
            -3,
            -5,
        ],
    ),
}

_lr_action = {}
for _k, _v in _lr_action_items.items():
    for _x, _y in zip(_v[0], _v[1]):
        if not _x in _lr_action:
            _lr_action[_x] = {}
        _lr_action[_x][_k] = _y
del _lr_action_items

_lr_goto_items = {
    "expression": (
        [
            0,
            2,
            4,
            5,
            6,
        ],
        [
            1,
            7,
            8,
            9,
            10,
        ],
    ),
}

_lr_goto = {}
for _k, _v in _lr_goto_items.items():
    for _x, _y in zip(_v[0], _v[1]):
        if not _x in _lr_goto:
            _lr_goto[_x] = {}
        _lr_goto[_x][_k] = _y
del _lr_goto_items
_lr_productions = [
    ("S' -> expression", "S'", 1, None, None, None),
    ("expression -> NOT expression", "expression", 2, "p_expression_not", "expression.py", 171),
    ("expression -> expression OR expression", "expression", 3, "p_expression_or", "expression.py", 176),
    ("expression -> expression AND expression", "expression", 3, "p_expression_and", "expression.py", 181),
    ("expression -> VAR", "expression", 1, "p_expression_var", "expression.py", 186),
    ("expression -> LPAREN expression RPAREN", "expression", 3, "p_expression_group", "expression.py", 191),
]
