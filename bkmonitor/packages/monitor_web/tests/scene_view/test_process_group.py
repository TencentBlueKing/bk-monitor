"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import unittest

from monitor_web.scene_view.process_group import group_process_configs


class TestGroupProcessConfigs(unittest.TestCase):
    def test_same_name_configs_are_one_group_with_distinct_sorted_ports(self):
        processes = [
            {
                "id": 20,
                "name": "redis",
                "protocol": "1",
                "ports": [6382, 6379],
                "bindIp": "127.0.0.1",
                "port": 6382,
                "user": "redis-6382",
                "startCommand": "redis-server --port 6382",
            },
            {
                "id": 10,
                "name": "redis",
                "protocol": "1",
                "ports": [6379, 6380],
                "bindIp": "127.0.0.1",
                "port": 6379,
                "user": "redis-6379",
                "startCommand": "redis-server --port 6379",
            },
        ]

        groups = group_process_configs(processes)
        reversed_groups = group_process_configs(list(reversed(processes)))

        self.assertEqual(len(groups), 1)
        self.assertEqual(groups, reversed_groups)
        self.assertEqual(groups[0]["id"], "redis")
        self.assertEqual(groups[0]["port"], 6379)
        self.assertEqual(groups[0]["user"], "redis-6379")
        self.assertEqual(groups[0]["startCommand"], "redis-server --port 6379")
        self.assertEqual(
            groups[0]["portBindings"],
            [
                {"protocol": "1", "bindIp": "127.0.0.1", "port": 6379},
                {"protocol": "1", "bindIp": "127.0.0.1", "port": 6380},
                {"protocol": "1", "bindIp": "127.0.0.1", "port": 6382},
            ],
        )

    def test_portless_process_keeps_an_empty_binding_list(self):
        groups = group_process_configs([{"id": 10, "name": "worker", "protocol": "1", "ports": []}])

        self.assertEqual(groups[0]["portBindings"], [])

    def test_ports_array_supplies_compatible_primary_port_when_port_is_missing(self):
        groups = group_process_configs(
            [{"id": 10, "name": "redis", "protocol": "1", "ports": [6382, 6379], "bindIp": "127.0.0.1"}]
        )

        self.assertEqual(groups[0]["port"], 6379)


if __name__ == "__main__":
    unittest.main()
