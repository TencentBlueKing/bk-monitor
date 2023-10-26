"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
from typing import List

import pytest

from core.prometheus.tools import find_udp_data_sliced_indexes, slice_metrics_udp_data


def make_sample_bytes(bytes_len: int, metrics_count: int) -> bytes:
    """构造一个类似 Prometheus 格式的 Metrics 二进制"""
    # header 长 43
    header = b"# HELP abcd \xae\xe6\x95\xb0\n# TYPE abcd_count counter\n"
    if bytes_len - len(header) * metrics_count <= 0:
        raise ValueError("Should give a longer length")

    remain_len = bytes_len - len(header) * metrics_count
    sample_bytes = bytearray()
    times = remain_len // metrics_count
    remainder = remain_len % metrics_count
    padding_seq = [times] * metrics_count
    padding_seq[-1] += remainder

    fake_sample = b"qq{dd=1} 1\n"
    for index, padding in enumerate(padding_seq):
        sample_count = padding // len(fake_sample)
        padding_padding = padding % len(fake_sample) * b"\n"
        sample_bytes.extend(header + fake_sample * sample_count + padding_padding)
    return sample_bytes


class TestMetricUDPSlice:
    """测试 Metrics UDP Slice"""

    @pytest.mark.parametrize(
        "big_bytes_len,max_udp_package_len,metrics_count,expected_tuples",
        [
            # bytes 长度，协议允许的最大长度，数据中包含的指标种类数，预期数据分割状况
            (3000, 3000, 5, [(0, 3000)]),
            (3000, 2000, 4, [(0, 1500), (1500, 2250), (2250, 3000)]),
            (3000, 2000, 10, [(0, 1800), (1800, 2700), (2700, 3000)]),
            (3000, 1501, 2, [(0, 1500), (1500, 3000)]),
            (3000, 1500, 2, [(0, 1500), (1500, 3000)]),
            (65536, 65535, 1, [(0, 65535), (65535, 65536)]),
            (3000, 1495, 2, [(0, 1495), (1495, 1500), (1500, 2995), (2995, 3000)]),
            # 769 = (777 - 43) // 11 * 11 + 43
            (3000, 777, 2, [(0, 769), (769, 1500), (1500, 2269), (2269, 3000)]),
        ],
    )
    def test_slice(self, big_bytes_len, max_udp_package_len, metrics_count, expected_tuples):
        test_bytes = make_sample_bytes(big_bytes_len, metrics_count)
        parts = find_udp_data_sliced_indexes(test_bytes, max_udp_package_len)
        print([p.to_tuple() for p in parts])
        assert [p.to_tuple() for p in parts] == expected_tuples

        sliced: List[memoryview] = list(slice_metrics_udp_data(test_bytes, parts))
        for index, x in enumerate(sliced):
            assert bytes(x).startswith(b"# HELP")
            assert bytes(x).endswith(b"\n")
            assert len(x) <= max_udp_package_len

    def test_slice_simple(self):
        """用于理解当前切分逻辑的单元测试"""
        simple_example = (
            b"# HELP bkmonitor_access_data_process_count_total help_text\n"
            b"# TYPE bkmonitor_access_data_process_count_total counter\n"
            b'bkmonitor_access_data_process_count_total{foo="aaaaaaaaaa"}\n'
            b'bkmonitor_access_data_process_count_total{foo="bbbbbbbbbb"}\n'
            b'bkmonitor_access_data_process_count_total{foo="cccccccccc"}\n'
            b'bkmonitor_access_data_process_count_total{foo="dddddddddd"}\n'
            b'bkmonitor_access_data_process_count_total{foo="eeeeeeeeee"}\n'
            b'bkmonitor_access_data_process_count_total{foo="ffffffffff"}\n'
            b"# HELP bkmonitor_detect_data_process_count_total help_text\n"
            b"# TYPE bkmonitor_detect_data_process_count_total counter\n"
            b'bkmonitor_detect_data_process_count_total{foo="aaaaaaaaaa"}\n'
            b'bkmonitor_detect_data_process_count_total{foo="bbbbbbbbbb"}\n'
        )

        # metadata length: 116, one sample 60
        parts = find_udp_data_sliced_indexes(simple_example, 116 + 60 * 2)
        sliced: List[memoryview] = list(slice_metrics_udp_data(simple_example, parts))

        result_part1 = (
            b"# HELP bkmonitor_access_data_process_count_total help_text\n"
            b"# TYPE bkmonitor_access_data_process_count_total counter\n"
            b'bkmonitor_access_data_process_count_total{foo="aaaaaaaaaa"}\n'
            b'bkmonitor_access_data_process_count_total{foo="bbbbbbbbbb"}\n'
        )
        result_part2 = (
            b"# HELP bkmonitor_access_data_process_count_total help_text\n"
            b"# TYPE bkmonitor_access_data_process_count_total counter\n"
            b'bkmonitor_access_data_process_count_total{foo="cccccccccc"}\n'
            b'bkmonitor_access_data_process_count_total{foo="dddddddddd"}\n'
        )
        result_part3 = (
            b"# HELP bkmonitor_access_data_process_count_total help_text\n"
            b"# TYPE bkmonitor_access_data_process_count_total counter\n"
            b'bkmonitor_access_data_process_count_total{foo="eeeeeeeeee"}\n'
            b'bkmonitor_access_data_process_count_total{foo="ffffffffff"}\n'
        )
        result_part4 = (
            b"# HELP bkmonitor_detect_data_process_count_total help_text\n"
            b"# TYPE bkmonitor_detect_data_process_count_total counter\n"
            b'bkmonitor_detect_data_process_count_total{foo="aaaaaaaaaa"}\n'
            b'bkmonitor_detect_data_process_count_total{foo="bbbbbbbbbb"}\n'
        )

        print(bytes(sliced[0]))
        print(bytes(sliced[1]))
        print(bytes(sliced[2]))
        print(bytes(sliced[3]))

        assert len(sliced) == 4
        assert all(len(x) <= 116 + 65 * 2 for x in sliced)
        assert bytes(sliced[0]) == result_part1
        assert bytes(sliced[1]) == result_part2
        assert bytes(sliced[2]) == result_part3
        assert bytes(sliced[3]) == result_part4
