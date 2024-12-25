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


import sys

from django.db.models import Q

from bkmonitor.data_source.handler import DataQueryHandler


class TestSQL(object):
    def setup_method(self, method):
        self.q_obj = DataQueryHandler("bk_monitor", "time_series")
        print("before {}: {}".format(method, self.q_obj), file=sys.stderr)  # noqa

    def teardown_method(self, method):
        self.q_obj = None
        print("after {}: {}".format(method, self.q_obj), file=sys.stderr)  # noqa

    def test_table_name(self):
        qs = self.q_obj.table("2_system_cpu_summary")
        assert str(qs.query) == "SELECT * FROM 2_system_cpu_summary"

    def test_select(self):
        qs = self.q_obj.table("2_system_cpu_summary").values("usage")
        assert str(qs.query) == "SELECT `usage` FROM 2_system_cpu_summary"

    def test_group_by(self):
        qs = self.q_obj.table("2_system_cpu_summary").group_by("usage")
        assert str(qs.query) == "SELECT * FROM 2_system_cpu_summary GROUP BY `usage`"

    def test_order_by(self):
        qs = self.q_obj.table("2_system_cpu_summary").order_by("usage")
        assert str(qs.query) == "SELECT * FROM 2_system_cpu_summary ORDER BY `usage`"

    def test_order_by_desc(self):
        qs = self.q_obj.table("2_system_cpu_summary").order_by("usage desc")
        assert str(qs.query) == "SELECT * FROM 2_system_cpu_summary ORDER BY usage desc"

    def test_limit(self):
        qs = self.q_obj.table("2_system_cpu_summary").limit(1)
        assert str(qs.query) == "SELECT * FROM 2_system_cpu_summary LIMIT 1"


class TestComplexQuerySQL(object):
    def setup_method(self, method):
        self.q_obj = DataQueryHandler("bk_monitor", "time_series")
        self.q_obj = self.q_obj.table("2_system_cpu_summary")
        print("before {}: {}".format(method, self.q_obj), file=sys.stderr)

    def teardown_method(self, method):
        self.q_obj = None
        print("after {}: {}".format(method, self.q_obj), file=sys.stderr)

    def test_single_condition(self):
        qs = self.q_obj.filter(ip="127.0.0.1")
        assert str(qs.query) == "SELECT * FROM 2_system_cpu_summary WHERE `ip` = 127.0.0.1"

    def test_multi_condition(self):
        qs = self.q_obj.filter(ip="127.0.0.1").filter(bk_cloud_id="0")
        assert str(qs.query) == "SELECT * FROM 2_system_cpu_summary WHERE `ip` = 127.0.0.1 AND `bk_cloud_id` = 0"

    def test_single_q_condition(self):
        qs = self.q_obj.filter(Q(ip="127.0.0.1"))
        assert str(qs.query) == "SELECT * FROM 2_system_cpu_summary WHERE `ip` = 127.0.0.1"

    def test_multi_q_condition(self):
        qs = self.q_obj.filter(Q(ip="127.0.0.1")).filter(Q(bk_cloud_id="0"))
        assert str(qs.query) == "SELECT * FROM 2_system_cpu_summary WHERE `ip` = 127.0.0.1 AND `bk_cloud_id` = 0"

    def test_q_or_q_condition(self):
        qs = self.q_obj.filter(Q(ip="127.0.0.1") | Q(ip="127.0.0.2"))
        assert str(qs.query) == "SELECT * FROM 2_system_cpu_summary WHERE `ip` = 127.0.0.1 OR `ip` = 127.0.0.2"

    def test_q_and_q_condition(self):
        qs = self.q_obj.filter(Q(ip="127.0.0.1") & Q(bk_cloud_id="0"))
        assert str(qs.query) == "SELECT * FROM 2_system_cpu_summary WHERE `ip` = 127.0.0.1 AND `bk_cloud_id` = 0"

    def test_q_nested_condition(self):
        qs = self.q_obj.filter(Q(ip="127.0.0.1", bk_cloud_id="0") | Q(ip="127.0.0.2", bk_cloud_id=0))
        assert (
            str(qs.query) == "SELECT * FROM 2_system_cpu_summary "
            "WHERE (`bk_cloud_id` = 0 AND `ip` = 127.0.0.1) OR (`bk_cloud_id` = 0 AND `ip` = 127.0.0.2)"
        )

    def test_q_nested_q_condition(self):
        qs = self.q_obj.filter(Q(Q(ip="127.0.0.1") & Q(bk_cloud_id="0")) | Q(Q(ip="127.0.0.2") & Q(bk_cloud_id=0)))
        assert (
            str(qs.query) == "SELECT * FROM 2_system_cpu_summary "
            "WHERE (`ip` = 127.0.0.1 AND `bk_cloud_id` = 0) OR (`ip` = 127.0.0.2 AND `bk_cloud_id` = 0)"
        )

    def test_q_nested_q_and_q_condition(self):
        qs = self.q_obj.filter(Q(Q(ip="127.0.0.1") | Q(ip="127.0.0.2"))).filter(Q(bk_cloud_id=2))
        assert (
            str(qs.query) == "SELECT * FROM 2_system_cpu_summary "
            "WHERE (`ip` = 127.0.0.1 OR `ip` = 127.0.0.2) AND `bk_cloud_id` = 2"
        )


class TestLookupCondition(object):
    """
    Lookup unittest

    operators = {
        'exact': '= %s',
        'eq': '= %s',
        'neq': '!= %s',
        'gt': '> %s',
        'gte': '>= %s',
        'lt': '< %s',
        'lte': '<= %s',
        'contains': 'LIKE %s',
    }
    """

    def setup_method(self, method):
        self.q_obj = DataQueryHandler("bk_monitor", "time_series")
        self.q_obj = self.q_obj.table("2_system_cpu_summary")
        print("before {}: {}".format(method, self.q_obj), file=sys.stderr)

    def teardown_method(self, method):
        self.q_obj = None
        print("after {}: {}".format(method, self.q_obj), file=sys.stderr)

    def test_default_lookup(self):
        qs = self.q_obj.filter(ip="127.0.0.1")
        assert str(qs.query) == "SELECT * FROM 2_system_cpu_summary WHERE `ip` = 127.0.0.1"

    def test_exact_lookup(self):
        qs = self.q_obj.filter(ip="127.0.0.1")
        assert str(qs.query) == "SELECT * FROM 2_system_cpu_summary WHERE `ip` = 127.0.0.1"

    def test_eq_lookup(self):
        qs = self.q_obj.filter(ip__eq="127.0.0.1")
        assert str(qs.query) == "SELECT * FROM 2_system_cpu_summary WHERE `ip` = 127.0.0.1"

    def test_neq_lookup(self):
        qs = self.q_obj.filter(ip__neq="127.0.0.1")
        assert str(qs.query) == "SELECT * FROM 2_system_cpu_summary WHERE `ip` != 127.0.0.1"

    def test_gt_lookup(self):
        qs = self.q_obj.filter(bk_cloud_id__gt=0)
        assert str(qs.query) == "SELECT * FROM 2_system_cpu_summary WHERE `bk_cloud_id` > 0"

    def test_gte_lookup(self):
        qs = self.q_obj.filter(bk_cloud_id__gte=0)
        assert str(qs.query) == "SELECT * FROM 2_system_cpu_summary WHERE `bk_cloud_id` >= 0"

    def test_lt_lookup(self):
        qs = self.q_obj.filter(bk_cloud_id__lt=0)
        assert str(qs.query) == "SELECT * FROM 2_system_cpu_summary WHERE `bk_cloud_id` < 0"

    def test_lte_lookup(self):
        qs = self.q_obj.filter(bk_cloud_id__lte=0)
        assert str(qs.query) == "SELECT * FROM 2_system_cpu_summary WHERE `bk_cloud_id` <= 0"

    # def test_in_lookup(self):
    #     qs = self.q_obj.filter(ip__in=0)
    #     assert str(qs.query) == "SELECT * FROM 2_system_cpu_summary WHERE bk_cloud_id > 0"

    def test_contains_lookup(self):
        qs = self.q_obj.filter(ip__contains="123")
        assert str(qs.query) == "SELECT * FROM 2_system_cpu_summary WHERE `ip` LIKE %123%"

    def test_eq_neq_value_list_lookup(self):
        qs = self.q_obj.filter(a=[1, 2, 3], b=3).filter(**{"c__neq": [4, 5], "d__eq": [6, 7]})
        assert (
            str(qs.query) == "SELECT * FROM 2_system_cpu_summary "
            "WHERE (`a` = 1 OR `a` = 2 OR `a` = 3) AND `b` = 3 AND (`c` != 4 AND `c` != 5) AND (`d` = 6 OR `d` = 7)"
        )

    def test_gt_lt_value_list_lookup(self):
        qs = self.q_obj.filter(a=[1, 2, 3], b=3).filter(**{"c__gt": [4, 5], "d__lt": [6, 7]})
        assert (
            str(qs.query) == "SELECT * FROM 2_system_cpu_summary "
            "WHERE (`a` = 1 OR `a` = 2 OR `a` = 3) AND `b` = 3 AND `c` > 5 AND `d` < 6"
        )

    def test_gte_lte_value_list_lookup(self):
        qs = self.q_obj.filter(a=[1, 2, 3], b=3).filter(**{"c__gte": [4, 5], "d__lte": [6, 7]})
        assert (
            str(qs.query) == "SELECT * FROM 2_system_cpu_summary "
            "WHERE (`a` = 1 OR `a` = 2 OR `a` = 3) AND `b` = 3 AND `c` >= 5 AND `d` <= 6"
        )


class TestSpecialCondition(object):
    def setup_method(self, method):
        self.q_obj = DataQueryHandler("bk_monitor", "time_series")
        self.q_obj = self.q_obj.table("2_system_cpu_summary")
        print("before {}: {}".format(method, self.q_obj), file=sys.stderr)

    def teardown_method(self, method):
        self.q_obj = None
        print("after {}: {}".format(method, self.q_obj), file=sys.stderr)

    def test_special_sql(self):
        qs = (
            self.q_obj.filter(Q(ip="127.0.0.1", bk_cloud_id="0"), time__gt="5m")
            .group_by("bk_cloud_id", "ip")
            .order_by("time desc")
            .limit(1)
            .values("usage", "bk_cloud_id", "ip")
        )
        assert (
            str(qs.query) == "SELECT `usage`, `bk_cloud_id`, `ip` "
            "FROM 2_system_cpu_summary "
            "WHERE (`bk_cloud_id` = 0 AND `ip` = 127.0.0.1) AND `time` > 5m "
            "GROUP BY `bk_cloud_id`, `ip` "
            "ORDER BY time desc "
            "LIMIT 1"
        )
