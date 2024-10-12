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
import logging
import socket
import time
import typing
from dataclasses import dataclass, field
from functools import wraps
from types import MethodType
from typing import Generator, List, Optional

from django.conf import settings
from prometheus_client.exposition import push_to_gateway
from prometheus_client.metrics import MetricWrapperBase

from alarm_backends.core.cluster import get_cluster

logger = logging.getLogger(__name__)


def get_udp_socket(address, port) -> socket.socket:
    """兼容客户场景可能是 ipv6 的地址"""
    try:
        udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udp_socket.connect((address, port))
        udp_socket.close()
        return socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    except socket.error:
        return socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)


def get_metric_agg_gateway_url(udp: bool = False):
    if settings.IS_CONTAINER_MODE and get_cluster().name != "default":
        url = f"bk-monitor-{get_cluster().name}-prom-agg-gateway"
        if udp:
            url = f"{url}:81"
        return url

    if udp:
        return settings.METRIC_AGG_GATEWAY_UDP_URL
    return settings.METRIC_AGG_GATEWAY_URL


def udp_handler(url, method, timeout, headers, data):
    """
    upd网关推送处理
    """

    def handle():
        address = get_metric_agg_gateway_url(udp=True)
        if not address:
            return

        split_result = address.split(":")
        address = split_result[0]

        if len(split_result) == 1:
            port = 10206
        else:
            port = int(split_result[1])
        udp_socket = get_udp_socket(address, port)

        for sliced_data in slice_metrics_udp_data(data, find_udp_data_sliced_indexes(data)):
            try:
                # 发送消息
                udp_socket.sendto(sliced_data, (address, port))
            except Exception as e:
                logger.exception(
                    "[push_to_gateway] send metrics to (%s:%s) error: %s, len: %s", address, port, e, len(sliced_data)
                )
                raise
        logger.info("[push_to_gateway] send metrics success, len: %s", len(data))

    return handle


@dataclass
class SlicedIndex:
    start: int
    end: int
    # 用于标记当前切片数据本身并不是以 # HELP 开头
    valid_start: bool = True
    # valid_start = False 时需要通过 buffer_start 来补足
    buffer_start: Optional[bytes] = None

    def to_tuple(self) -> tuple:
        return self.start, self.end

    def __len__(self):
        return self.end - self.start


@dataclass
class SlicedIndexList:
    indexes: List[SlicedIndex] = field(default_factory=list)
    # 用于缓存上一次有效的开头
    buffer_valid_start: Optional[bytes] = None

    _original_data: Optional[bytes] = None

    def get_valid_start_content(self, start: int, end: int):
        """找到完整的指标头

        example:
        # HELP xxxxx asdfasdf
        # TYPE xxxxx counter
        """

        type_start = self._original_data.find(b"# TYPE", start, end)
        if type_start == -1:
            raise ValueError("metrics has no valid metadata: type")

        meta_end = self._original_data.find(b"\n", type_start, end)
        if meta_end == -1:
            raise ValueError("metrics has no valid metadata: end")

        self.buffer_valid_start = self._original_data[start : meta_end + 1]
        return

    def find_end_via_buffer_start(self, start: int, package_max_size: int) -> int:
        """通过当前初步找到的切片末尾和缓冲区的指标元信息，找到在添加了元信息后的切片末尾"""
        if not self.buffer_valid_start:
            return len(self._original_data)

        next_new_start = self._original_data.rfind(
            b"\n", start, start + package_max_size - len(self.buffer_valid_start)
        )
        if next_new_start == -1 or next_new_start == package_max_size:
            return len(self._original_data)

        return next_new_start + 1

    def add(self, start: int, end: int, valid_start: bool = True):
        """添加切片点"""
        self.indexes.append(SlicedIndex(start, end, valid_start, buffer_start=self.buffer_valid_start))

    def __iter__(self):
        for elem in self.indexes:
            yield elem

    def __getitem__(self, ii):
        """Get a list item"""
        return self.indexes[ii]


def find_udp_data_sliced_indexes(data: bytes, udp_package_max_size: int = 65507, mtu: int = 1500) -> SlicedIndexList:
    """对 UDP 发送数据进行切片处理，保证每次发送成功
    :param data: 预发送数据
    :param udp_package_max_size: 当前系统支持的最大 UDP 发送包大小，以 bytes 计算，默认为 65507 (在 macOS 下默认为 9126)
    :param mtu: Maximum Transmission Unit

    udp_package_max_size = 0xffff - (sizeof(IP Header) + sizeof(UDP Header)) = 65535-(20+8) = 65507
    ref to: https://erg.abdn.ac.uk/users/gorry/course/inet-pages/udp.html
    """
    length = len(data)
    if length > mtu:
        # 当前我们暂不考虑处理 MTU 的问题，先解决 UDP 包过大的情况
        logger.debug("[push_to_gateway] UDP packages is larger than MTU, not safe for single push.")

    if length <= udp_package_max_size:
        return SlicedIndexList(indexes=[SlicedIndex(0, length)])

    sliced_index_list = SlicedIndexList(_original_data=data)
    try:
        find_sliced_indexes(data, 0, udp_package_max_size, sliced_index_list)
    except RecursionError:
        logger.warning("[push_to_gateway] data has no valid format, drop it...")

    return sliced_index_list


def find_sliced_indexes(data: bytes, start: int, udp_package_max_size: int, sliced_index_list: SlicedIndexList):
    """递归找寻指标开头标志

    当某个 metrics 数据大小大于 UDP 协议最大包限制时，原则上我们无法通过 UDP 发送该数据
    但这里尝试以最大限制切片发送该数据，以一个超过最大限制的数据为例
    # +-----------------+ 协议最大长度
    # +-----------------+  +-------------------+  +-------------------+
    # 有效            有效  有效(无法合并丢弃)   有效  有效              有效
    聚合网关一次推送请求中，当且仅当有效开头和有效结尾——即格式完全正确——才能被成功解析
    """
    valid_start = data.find(b"# HELP", start, start + udp_package_max_size) == start
    if valid_start:
        # 说明当前切片仅有字符串初始拥有有效开头
        # 加当前拿到的有效元信息添加到缓冲区，方便给后续缺少有效开头的切片添加
        sliced_index_list.get_valid_start_content(start, start + udp_package_max_size)

    # 尝试从右查找有效开头, 同时假定原始数据肯定是有效开头
    valid_start_index = data.rfind(b"# HELP", start, start + udp_package_max_size)
    if valid_start_index in [-1, start]:
        # 由于 sample 肯定会转行，通过转行保证当前包的内容格式有效
        valid_end_index = data.rfind(b"\n", start, start + udp_package_max_size)
        next_valid_start = data.find(b"# HELP", valid_end_index)
        # 如果当前转行结束点后正好下一个是有效开头，即正好可以按需切分，无需其他工作
        if next_valid_start == valid_end_index + 1:
            sliced_index_list.add(start, valid_end_index + 1, valid_start)
            find_sliced_indexes(data, valid_end_index + 1, udp_package_max_size, sliced_index_list)
            return

        if valid_start_index == start:
            next_start = valid_end_index + 1
        else:
            # 当前切片点会导致下一个包没有有效开头
            # 所以尝试添加新的切片点，并获取下一次切片点的开始
            next_start = sliced_index_list.find_end_via_buffer_start(start, udp_package_max_size)

        sliced_index_list.add(start, next_start, valid_start)
        if next_start < len(data):
            find_sliced_indexes(data, next_start, udp_package_max_size, sliced_index_list)

        return

    # 在规定大小内可以切分出有效的 metrics
    sliced_index_list.add(start, valid_start_index, valid_start)
    find_sliced_indexes(data, valid_start_index, udp_package_max_size, sliced_index_list)
    return


def slice_metrics_udp_data(data: bytes, sliced_indexes: SlicedIndexList) -> Generator[memoryview, None, None]:
    """拆分 metrics UDP data"""
    # Q: 为什么不直接切分?
    # A: 直接按照大小切分会降 bytes 中的字面值切断，让服务端对于指标无法理解，所以要按照字面值的内容做切分

    # memoryview 无需额外拷贝，更节省更高效
    mview = memoryview(data)
    for index in sliced_indexes:
        if not index.valid_start:
            yield index.buffer_start + bytes(data[index.start : index.end])
        else:
            yield mview[index.start : index.end]


def push_to_agg_gateway(metric: MetricWrapperBase):
    """
    推送指标到聚合网关并清空指标数据
    PS: 清空是为了避免数据被累加重复推送到聚合网关
    """
    if not get_metric_agg_gateway_url():
        return

    push_to_gateway(gateway="", job="", registry=metric, handler=udp_handler)
    # 由于是使用聚合网关每次需要清空指标内容
    with metric._lock:
        metric._metrics = {}


def task_timer(queue: str = None) -> typing.Callable[[typing.Callable], typing.Callable]:
    """
    函数计时器
    """
    if not queue:
        queue = "celery"

    def actual_timer(func) -> typing.Callable:
        from core.prometheus import metrics

        @wraps(func)
        def wrapper(*args, **kwargs):
            result, exception = None, None
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
            except Exception as e:  # noqa
                exception = e

            exception_name = exception.__class__.__name__ if exception else "None"
            # 记录函数执行时间
            metrics.CELERY_TASK_EXECUTE_TIME.labels(
                task_name=func.__name__,
                queue=queue,
                exception=exception_name,
            ).observe(time.time() - start_time)
            metrics.report_all()

            # 如果函数执行失败，抛出异常
            if exception:
                raise exception
            return result

        return wrapper

    return actual_timer


def hack_task(self, *args, **kwargs):
    def wrapper(func):
        return self._old_task(*args, **kwargs)(task_timer(queue=kwargs.get("queue"))(func))

    return wrapper


def celery_app_timer(app):
    """
    对 celery app 进行 patch，为其增加函数计时器
    """
    app._old_task = app.task
    app.task = MethodType(hack_task, app)
