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
from furl import furl as furl_origin
from furl.furl import idna_decode
from furl.common import callable_attr
import urllib

__implements__ = ["furl"]


class furl(furl_origin):
    @furl_origin.host.setter
    def host(self, host):
        """
        Raises: ValueError on invalid host or malformed IPv6 address.
        """
        # Invalid IPv6 literal.
        urllib.parse.urlsplit("http://%s/" % host)  # Raises ValueError.

        if callable_attr(host, "lower"):
            host = host.lower()
        if callable_attr(host, "startswith") and host.startswith("xn--"):
            host = idna_decode(host)
        self._host = host
