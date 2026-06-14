"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import socket

from alarm_backends.core.storage import redis as redis_storage
from alarm_backends.core.storage.redis import (
    REDIS_SOCKET_TIMEOUT_FLOOR,
    SentinelRedisCache,
    build_tcp_keepalive_options,
    gen_resilient_socket_conf,
)


class TestResilientSocketConf:
    """连接韧性参数: socket_timeout 红线(必须 > 最长阻塞 BRPOP 的 5s) + connect/read 解耦 + keepalive。"""

    def test_floor_guards_blocking_brpop_timeout(self):
        # 低于 floor 的配置必须被抬到 floor，否则空闲 BRPOP(server 5s) 会先被 socket 超时打断
        conf = gen_resilient_socket_conf(socket_timeout=3)
        assert conf["socket_timeout"] >= REDIS_SOCKET_TIMEOUT_FLOOR
        assert conf["socket_timeout"] > 5

    def test_keeps_configured_value_when_above_floor(self):
        conf = gen_resilient_socket_conf(socket_timeout=20)
        assert conf["socket_timeout"] == 20

    def test_none_socket_timeout_falls_back_to_floor(self):
        # queue 后端历史上无 socket_timeout 配置 -> None -> 抬到 floor(而非保持无超时无限挂)
        conf = gen_resilient_socket_conf(socket_timeout=None)
        assert conf["socket_timeout"] == REDIS_SOCKET_TIMEOUT_FLOOR

    def test_connect_timeout_decoupled_and_short(self):
        # connect 与 read 解耦: connect 短且远小于 read, 使主切换时重连快速失败而非挂死
        conf = gen_resilient_socket_conf(socket_timeout=10)
        assert conf["socket_connect_timeout"] <= 5
        assert conf["socket_connect_timeout"] < conf["socket_timeout"]

    def test_keepalive_enabled(self):
        conf = gen_resilient_socket_conf(socket_timeout=10)
        assert conf["socket_keepalive"] is True

    def test_keepalive_options_only_contain_existing_constants(self):
        # 平台守卫: macOS 无 socket.TCP_KEEPIDLE, 直接引用未守卫常量会 AttributeError;
        # 这里确保 options 只纳入当前平台真实存在的常量, 否则 redis-py setsockopt 会报错。
        options = build_tcp_keepalive_options()
        valid_consts = {
            getattr(socket, name)
            for name in ("TCP_KEEPIDLE", "TCP_KEEPINTVL", "TCP_KEEPCNT")
            if getattr(socket, name, None) is not None
        }
        assert set(options.keys()) <= valid_consts


class TestSentinelDataConnectionHardening:
    """回归审计点: socket_timeout 在 __init__ 被 pop 后仅用于 sentinel 发现, 未回填 master/slave 数据连接。"""

    def test_master_slave_get_bounded_timeout_and_keepalive(self, mocker):
        mock_sentinel_cls = mocker.patch.object(redis_storage, "Sentinel")
        mock_sentinel = mock_sentinel_cls.return_value
        mock_sentinel.sentinels = []  # 供 create_instance 末尾 list(map(close_instance, ...)) 迭代

        conf = {
            "host": "sentinel-1;sentinel-2",
            "port": 26379,
            "db": 10,
            "master_name": "mymaster",
            "socket_timeout": 10,
            "password": "pwd",
        }
        # 构造即触发 refresh_instance -> create_instance
        SentinelRedisCache(conf)

        # sentinel 发现连接使用短 connect 超时, 不喂入长读超时
        sentinel_kwargs = mock_sentinel_cls.call_args.kwargs["sentinel_kwargs"]
        assert sentinel_kwargs["socket_connect_timeout"] <= 5

        # master/slave 数据连接被注入有界读超时 + keepalive(修复历史上的丢弃)
        for call in (mock_sentinel.master_for.call_args, mock_sentinel.slave_for.call_args):
            assert call.kwargs["socket_timeout"] >= REDIS_SOCKET_TIMEOUT_FLOOR
            assert call.kwargs["socket_keepalive"] is True
            assert call.kwargs["socket_connect_timeout"] < call.kwargs["socket_timeout"]
