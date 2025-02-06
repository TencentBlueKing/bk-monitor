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
"""
测试使用，配置vm模块， target: test 集群的 故障影响范围
"""


from alarm_backends.service.alert.qos.scope import EmptyScope


class Scope(EmptyScope):
    duration = 60 * 10

    def get_scope_dimension(self):
        return {
            "id": __name__,
            'category': 'dimension',
            'scope_type': '',
            # 根据实际情况更新
            'begin_time': 0,
            'end_time': 0,
            'dimension_config': {
                'dimension_conditions': [
                    {'key': 'bk_biz_id', 'value': [2], 'method': 'eq', 'condition': 'and', 'name': 'bk_biz_id'}
                ]
            },
            'cycle_config': {'type': 1},
        }
