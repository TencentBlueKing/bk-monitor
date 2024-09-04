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
0.253 __call__  django/utils/deprecation.py:110
└─ 0.253 inner  django/core/handlers/exception.py:44
      [125 frames hidden]  django, blueapps, whitenoise, apigw_m...
         0.253 __call__  django/utils/deprecation.py:110
         │  0.237 _get_response  django/core/handlers/base.py:160
         │  │  0.118 _cache_controlled  django/views/decorators/cache.py:29
         │  │  └─ 0.118 template  core/drf_resource/viewsets.py:198
         │  │     └─ 0.118 request  core/drf_resource/base.py:214
         │  │        └─ 0.116 perform_request  monitor_web/iam/resources.py:72
         │  │           └─ 0.116 is_allowed_by_biz  bkmonitor/iam/permission.py:375
         │  │              ├─ 0.096 create_simple_instance  bkmonitor/iam/resource.py:77
         │  │              │  ├─ 0.088 get_space_detail  monitor_web/commons/biz/space_api.py:37
         │  │              │  │  └─ 0.088 get  django/core/cache/backends/locmem.py:35
         │  │              │  │        [3 frames hidden]  django, <built-in>
         │  │              │  │           0.088 loads  <built-in>:0
         │  │              │  └─ 0.008 [self]
         │  │              └─ 0.021 is_allowed  bkmonitor/iam/permission.py:289
         │  │                 └─ 0.021 wrapper  cachetools/__init__.py:514
         │  │                       [8 frames hidden]  cachetools, iam
         │  │                          0.021 is_allowed  iam/iam.py:193
         │  │                          └─ 0.020 _do_policy_query  bkmonitor/iam/compatible.py:65
         │  │                             └─ 0.020 _do_policy_query  iam/iam.py:55
         │  │                                   [51 frames hidden]  iam, requests, opentelemetry, urllib3...
         │  ├─ 0.101 process_view  common/middlewares.py:34
         │  │  ├─ 0.093 get_space_detail  monitor_web/commons/biz/space_api.py:37
         │  │  │  └─ 0.093 get  django/core/cache/backends/locmem.py:35
         │  │  │        [3 frames hidden]  django, <built-in>
         │  │  │           0.093 loads  <built-in>:0
         │  │  └─ 0.008 [self]
         │  ├─ 0.015 process_view  bkmonitor/middlewares/authentication.py:42
         │  │  └─ 0.015 process_view  blueapps/account/components/bk_ticket/middlewares.py:30
         │  │        [73 frames hidden]  blueapps, django, dj_db_conn_pool, sq...
         └─ 0.011 process_response  bkmonitor/middlewares/prometheus.py:49
            └─ 0.011 report_all  core/prometheus/metrics.py:31
               └─ 0.009 push_to_gateway  prometheus_client/exposition.py:428
                     [6 frames hidden]  prometheus_client
                        0.009 _use_gateway  prometheus_client/exposition.py:537
                        ├─ 0.006 handle  core/prometheus/tools.py:57
                        │  └─ 0.003 get_udp_socket  core/prometheus/tools.py:29
                        │     └─ 0.003 socket.connect  <built-in>:0
                        │           [2 frames hidden]  <built-in>

django locmem 使用pickle序列化数据， 在内存缓存中，可以不进行序列化。
get  django/core/cache/backends/locmem.py:35
该方法占用整体耗时0.180
占比 180/253 = 71%
"""

from django.core.cache.backends import locmem


class DummyPickle(object):
    @staticmethod
    def dumps(value, *args, **kwargs):
        return value

    @staticmethod
    def loads(value, *args, **kwargs):
        return value


locmem.pickle = DummyPickle()


class LocalMemCache(locmem.LocMemCache):
    pass
