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
from django.core.cache import cache
from django.core.exceptions import MiddlewareNotUsed
from django.utils.deprecation import MiddlewareMixin

from bkmonitor.utils.local import local
from core.drf_resource.contrib.api import get_bk_login_ticket
from core.errors import Error

"""
应用防护：
系统防护是从系统表现，例如Load、RT、QPS和线程数四个维度出发，对应用的入口流量进行控制，让系统尽可能跑在最大吞吐量的同时保证系统稳定性。

定义：
用户负载(load)： 默认使用当前线程数(thread)
方案:
- 判定规则：按用户来统计负载（【依赖】用户鉴权中间件， 因此该中间件需要放置在登录鉴权中间件之后），基于用户当前占用的负载来决定是否允许用户继续访问。(process_view)
- 数据存放【依赖】django-cache(redis)
- 熔断规则：当判定用户不允许访问后，对应用户的token将被限制请求。(process_request)
    基于token限制的原因是: 不需要经过token->user的消耗，尽快释放worker资源
- 限制请求范围： 视图查询相关的系列api


# 功能启用：
from django.core.cache import cache
# 这里20是个示例
cache.set("rate_limit", 21)
# 去除ttl， cache的set默认会带上timeout参数
cache.persist("rate_limit")
"""


def init(limit=21):
    # 功能开启
    cache.set(ProtectionMiddleware.cache_key_prefix, limit)
    cache.persist(ProtectionMiddleware.cache_key_prefix)


class RateLimitedError(Error):
    status_code = 429
    name = "rate limited error"
    message_tpl = "only allow {rate} requests for per logged in user at the moment.  Try again in {seconds}s."


class ProtectionMiddleware(MiddlewareMixin):

    cache_key_prefix = "rate_limit"

    def __init__(self, get_response=None):
        super(ProtectionMiddleware, self).__init__(get_response)
        # 未配置redis 作为cache backend，该中间件失效
        if not hasattr(cache, "ttl"):
            raise MiddlewareNotUsed

        try:
            self.timeout = 120
            self.rate_limit = int(cache.get(self.cache_key_prefix))
        except TypeError:
            raise MiddlewareNotUsed

    def process_request(self, request):
        # 限制范围： 视图查询相关接口
        if "/rest/v2/grafana/" not in request.path:
            return
        # process_request 提前进行熔断，省略后续所有中间件的process_view处理，包含用户信息获取等。
        token_info = get_bk_login_ticket(request)
        # bk_token or bk_ticket
        if len(token_info) != 1:
            return
        setattr(local, "token_key", str(token_info))
        ttl = cache.ttl(local.token_key)
        if ttl:
            # 用户处于流控中，禁止继续
            raise RateLimitedError(rate=self.rate_limit, seconds=ttl)

    def process_view(self, request, view, args, kwargs):
        if not hasattr(request, "user"):
            return
        user_key = self.user_key(request.user.username)
        # 非用户实际发起的请求，进行豁免
        if user_key in ["system", "admin"]:
            return
        # 不存在则初始化
        if cache.set(user_key, 1, timeout=self.timeout, nx=True):
            return

        # 获取当前负载
        load = cache.get(user_key)
        if load >= self.rate_limit:
            cache.set(local.token_key, "forbidden", self.timeout)
            cache.set(f"{user_key}_slug", "forbidden", self.timeout)
            return

        cache.incr(user_key)
        cache.expire(user_key, self.timeout)

    def process_response(self, request, response):
        if not hasattr(request, "user"):
            return
        user_key = self.user_key(request.user.username)
        # 尝试归零
        if cache.set(user_key, 0, timeout=self.timeout, nx=True):
            return

        cache.decr(user_key)
        return response

    def user_key(self, username):
        return "{}_{}".format(self.cache_key_prefix, username)
