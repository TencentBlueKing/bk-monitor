from bisect import bisect_left
from hashlib import md5
from typing import Any

import six


class HashRing:
    def __init__(self, nodes: list[Any], num_vnodes: int = 2**16):
        self.nodes = nodes

        self.ring = []
        self.hash2node = {}

        self.num_vnodes = num_vnodes
        sum_weight = sum(nodes.values())
        multiple = max(int(self.num_vnodes // sum_weight), 1)
        self.vnodes = multiple * sum_weight

        for node, _ in six.iteritems(nodes):
            for i in range(multiple):
                h = self._hash(str(node) + str(i))
                self.ring.append(h)
                self.hash2node[h] = node

        self.ring.sort()

    def _hash(self, key):
        return int(md5(str(key).encode("utf-8")).hexdigest(), 16) % (2**32)

    def get_node(self, key):
        h = self._hash(key)
        n = bisect_left(self.ring, h) % self.vnodes
        return self.hash2node[self.ring[n]]
