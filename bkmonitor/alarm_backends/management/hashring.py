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


from bisect import bisect_left
from hashlib import md5

import six
from six.moves import range


class HashRing(object):
    def __init__(self, nodes, num_vnodes=2 ** 16):
        self.nodes = nodes

        self.ring = []
        self.hash2node = {}

        self.num_vnodes = num_vnodes
        sum_weight = sum(nodes.values())
        multiple = max(int(self.num_vnodes // sum_weight), 1)
        self.vnodes = multiple * sum_weight

        for node, weight in six.iteritems(nodes):
            for i in range(multiple):
                h = self._hash(str(node) + str(i))
                self.ring.append(h)
                self.hash2node[h] = node

        self.ring.sort()

    def _hash(self, key):
        return int(md5(str(key).encode("utf-8")).hexdigest(), 16) % (2 ** 32)

    def get_node(self, key):
        h = self._hash(key)
        n = bisect_left(self.ring, h) % self.vnodes
        return self.hash2node[self.ring[n]]
