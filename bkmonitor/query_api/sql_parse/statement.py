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
import logging

import sqlparse
from sqlparse import tokens as T

from query_api.exceptions import SQLSyntaxError

logger = logging.getLogger("sql_parse")


class SQLStatement(object):
    def __init__(self, sql):
        logger.info("<<< %s" % sql)
        self._sql = sql
        tlist_tuple = sqlparse.parse(sql.strip())
        if len(tlist_tuple) > 1:
            raise SQLSyntaxError("unsupported multiple sql")
        tlist = tlist_tuple[0]
        self.statement = tlist
        self._init()
        self.process()

    def _init(self):
        self.select_items = []
        self.result_table = None
        self.where_token = None
        self.group_items = []
        self.order_items = []
        self.limit_item = None
        self.slimit_item = None

    def process(self):
        self._process(self.statement)

    def refresh_token(self, token):
        self._init()
        while 1:
            statement = getattr(token, "parent")
            if statement is not None:
                token = statement
            else:
                break
        self.statement = statement
        self.process()

    def _next_kw(self, tlist, idx=-1):
        key_words = ("FROM", "WHERE", "GROUP", "ORDER", "LIMIT")
        m_split = T.Keyword, key_words, True
        tidx, token = tlist.token_next_by(m=m_split, idx=idx)
        return tidx, token

    def _process_dml(self, tlist):
        tidx, token = tlist.token_next_by(m=(T.Keyword.DML, "SELECT"))
        if token:
            return tidx, token
        raise SQLSyntaxError("sql must start with keyword: `select`")

    def _process(self, tlist):
        idx, keyword = self._process_dml(tlist)
        if not keyword:
            raise Exception
        while keyword:
            func_name = "_process_%s" % keyword.normalized.split(" ")[0]
            args = [
                idx,
            ]
            idx, keyword = self._next_kw(tlist, idx)
            args.append(idx or len(tlist.tokens))
            func = getattr(self, func_name.lower())
            func(tlist, *args)

    def _process_default(self, tlist, start_idx, end_idx):
        for sgroup in tlist.get_sublists():
            if start_idx < tlist.token_index(sgroup) < end_idx:
                yield self._split_items(sgroup)
        yield []

    def _process_select(self, tlist, start_idx, end_idx):
        for select_item in next(self._process_default(tlist, start_idx, end_idx)):
            self.select_items.append(select_item)
        else:
            idx, all_selected_token = tlist.token_next_by(m=(T.Wildcard, "*"))
            if idx and start_idx < idx < end_idx:
                self.select_items.append(all_selected_token)
        if not self.select_items:
            idx, keyword_item = tlist.token_next_by(t=T.Keyword, idx=start_idx)
            if keyword_item and idx < end_idx:
                self.select_items.append(keyword_item)
        # logger.debug(u"select fields: %s" % (", ".join(map(str, self.select_items))))

    def _process_from(self, tlist, start_idx, end_idx):
        from_iter = self._process_default(tlist, start_idx, end_idx)
        result_table = next(from_iter)
        if len(result_table) != 1:
            raise SQLSyntaxError("result_table must only one, %d given." % len(result_table))
        self.result_table = result_table[0]
        # logger.debug(u"result_table: %s" % self.result_table)
        try:
            # process where
            next(from_iter)
        except StopIteration:
            pass

    def _process_where(self, tlist):
        self.where_token = tlist
        # logger.debug(u"where: %s" % tlist)

    def _process_group(self, tlist, start_idx, end_idx):
        for group_items in next(self._process_default(tlist, start_idx, end_idx)):
            self.group_items.append(group_items)
        # logger.debug(u"group fields: %s" % (", ".join(map(str, self.group_items))))

    def _process_order(self, tlist, start_idx, end_idx):
        self.order_items = next(self._process_default(tlist, start_idx, end_idx))

    def _process_limit(self, tlist, start_idx, end_idx):
        limit_item = None
        for idx, token in enumerate(tlist[start_idx + 1 : end_idx]):
            if token.value.strip():
                limit_item = token
                break

        if not limit_item:
            raise SQLSyntaxError("`LIMIT` need a number.")

        self.limit_item = limit_item

    def _process_slimit(self, tlist, start_idx, end_idx):
        slimit_item = None
        for idx, token in enumerate(tlist[start_idx + 1 : end_idx]):
            if token.value.strip():
                slimit_item = token
                break

        if not slimit_item:
            raise SQLSyntaxError("`SLIMIT` need a number.")

        self.slimit_item = slimit_item

    def _split_items(self, tlist):
        func_name = "_split_{cls}".format(cls=type(tlist).__name__)
        func = getattr(self, func_name.lower(), lambda x: x)
        result = func(tlist)
        if not isinstance(result, list):
            result = [result]
        return result

    def _split_identifierlist(self, tlist):
        return [self._split_identifier(identifier) for identifier in tlist.get_identifiers()]

    def _split_identifier(self, tlist):
        return tlist

    def _split_where(self, tlist):
        return self._process_where(tlist)

    def __repr__(self):
        return str(self.statement)
