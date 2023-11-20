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

from django.template import Template

# agg节点sql模板
AGG_METRICS_SQL_EXPR = Template(
    """
SELECT bk_biz_id, ip, bk_cloud_id, bk_target_ip, bk_target_cloud_id,
    {% for metric, metric_alias in metric_infos %}
         AVG(`{{ metric }}`) as `{{ metric_alias }}`{% if not forloop.last %},{% endif %}
    {% endfor %}
FROM {{output_table_name}}
GROUP BY bk_biz_id, ip, bk_cloud_id, bk_target_ip, bk_target_cloud_id"""
)

# agg_trans节点sql模板
AGG_TRANS_METRICS_SQL_EXPR = Template(
    """
SELECT bk_biz_id, ip, bk_cloud_id, bk_target_ip, bk_target_cloud_id,
CONCAT_WS('#',
    {{ metrics_strs }}
) AS metrics_key,
CONCAT_WS('#',
    {% for metric in metrics %}
        CAST(IF(`{{ metric }}` IS NOT NULL,`{{ metric }}`,0.0) AS VARCHAR){% if not forloop.last %},{% endif %}
    {% endfor %}
) AS metrics_value
from {{output_table_name}}
"""
)

# 最后将所有节点合并的sql模板
MERGE_SQL_EXPR = Template(
    """
SELECT bk_biz_id, ip, bk_cloud_id, bk_target_ip, bk_target_cloud_id, udf_merge_metrics_into_json('#',
    metrics_key, '#', metrics_value)
    AS metrics_json
FROM {{output_table_name}}
GROUP BY bk_biz_id, ip, bk_cloud_id, bk_target_ip, bk_target_cloud_id"""
)
