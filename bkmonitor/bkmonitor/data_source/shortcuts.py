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


from bkmonitor.data_source.models.data_structure import DataPoint  # noqa


def main():
    """
    from bkmonitor.data_source.models.query import DataQuery
    q_obj = DataQuery(("bk_monitor", "time_series"))
    qs = q_obj.table("2_system_cpu_summary").values('usage').limit(1)
    print qs.query      # 打印查询语句
    print qs.raw_data   # 返回原始结果
    print qs.data       # 返回DataPoint对象


    from bkmonitor.data_source.models.query import DataQuery
    q_obj = DataQuery(("bk_log_search", "time_series"))
    print q_obj.dsl_index_set_id(61).group_by('username').values('avg(age) as _age').raw_data

    """

    pass


if __name__ == "__main__":
    main()
