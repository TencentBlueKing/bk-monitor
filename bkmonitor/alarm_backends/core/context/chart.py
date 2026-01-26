"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import asyncio
import base64
import datetime
import json
import logging
import os
import tempfile

import arrow
import pytz
from django.conf import settings
from django.template.loader import get_template
from django.utils.translation import gettext as _

from alarm_backends.constants import CONST_ONE_DAY
from alarm_backends.core.control.item import Item
from alarm_backends.core.i18n import i18n
from bkmonitor.browser import get_browser, get_or_create_eventloop
from bkmonitor.utils import time_tools
from constants.data_source import DataTypeLabel
from constants.strategy import AGG_METHOD_REAL_TIME
from core.unit import load_unit

logger = logging.getLogger("fta_action.run")


async def render_html(html_file_path: str) -> bytes | None:
    """
    渲染html字符串为图片
    """
    browser = await get_browser()

    # 打开页面
    page = await browser.newPage()
    await page.goto(f"file://{html_file_path}")

    # 设置页面大小
    await page.setViewport({"width": 1520, "height": 635, "deviceScaleFactor": 1})

    # 额外等待一段时间确保动画完成
    await asyncio.sleep(0.03)

    panel = await page.querySelector(".chart-contain")
    if not panel:
        return b""

    # 截图
    img_bytes = await panel.screenshot({"type": "jpeg", "quality": 90})

    # 关闭页面
    try:
        await page.close()
    except Exception as e:
        logger.exception(f"[render_alarm_graph] close page error: {e}")

    return img_bytes


def get_chart_image(chart_data) -> str:
    try:
        template_path = os.path.join(settings.BASE_DIR, "alarm_backends", "templates", "image_exporter")
        template = get_template("image_exporter/graph.html")
        html_string = template.render({"context": json.dumps(chart_data)})

        # 将html写入临时文件，并使用浏览器渲染（Chrome/pyppeteer）
        with tempfile.NamedTemporaryFile(prefix="tmp_chart_image_", dir=template_path, suffix=".html") as f:
            f.write(html_string.encode("utf-8"))
            f.flush()

            loop = get_or_create_eventloop()
            img_bytes = loop.run_until_complete(render_html(f.name))
            if not img_bytes:
                return ""

            # 转换为base64
            img_base64 = base64.b64encode(img_bytes).decode("utf-8")
            return img_base64
    except Exception as e:
        logger.exception(f"[render_alarm_graph] get_chart_image fail: {e}")
        return ""


def get_chart_by_origin_alarm(item, source_time, title=""):
    # 非时序型或实时监控不出图
    if (
        DataTypeLabel.TIME_SERIES not in item.data_type_labels
        or item.query_configs[0].get("agg_method", []) == AGG_METHOD_REAL_TIME
    ):
        return None

    source_time = arrow.get(time_tools.localtime(source_time))
    chart_data = get_chart_data(item, source_time, title)
    return get_chart_image(chart_data)


def get_chart_data(item: Item, source_time, title=""):
    """
    获取图表数据
    :param item: 监控项配置
    :type item: Item
    :param source_time: 告警事件
    :type source_time: Arrow
    :return:
    """
    unify_query = item.query

    # 按维度增加过滤条件
    interval = max(data_source.interval for data_source in unify_query.data_sources)
    chart_option = {_("今日"): 0, _("昨日"): -1, _("上周"): -7}

    start_time = source_time.replace(hours=-max(interval * 5 // 3600, 1))
    end_time = source_time.replace(minutes=max(interval // 60, 5))

    unit = load_unit(item.unit)

    series = []
    for name, offset in list(chart_option.items()):
        data = []
        records = unify_query.query_data(
            start_time=start_time.replace(days=offset).timestamp * 1000,
            end_time=(end_time.replace(days=offset) if offset != 0 else source_time.replace(seconds=interval)).timestamp
            * 1000,
        )
        for record in records:
            value = record["_result_"]
            try:
                # 只有当 value 为数字时才进行 round
                if isinstance(value, int | float):
                    value = round(value, int(settings.POINT_PRECISION))
            except Exception:
                # 非预期的数据，直接抛异常并记录日志
                logger.exception(f"[render_alarm_graph] round value error: {value}, type: {type(value)}")
                raise Exception(f"[render_alarm_graph] round value error: {value}, type: {type(value)}")
            data.append([record["_time_"] - offset * CONST_ONE_DAY * 1000, value])

        # 在 data 中根据查询配置的 interval 补充空点None，以免图表无法显示出数据断点的情况
        if data and interval > 0:
            # 按时间戳排序数据点
            data.sort(key=lambda x: x[0])

            # 计算时间范围
            # 注意：由于数据时间戳已经通过 `record["_time_"] - offset * CONST_ONE_DAY * 1000` 调整到同一时间轴
            # 因此时间范围也应该基于 offset=0 的时间（即今天的时间范围），这样所有时间段的数据才能对齐
            chart_start_time = start_time.timestamp * 1000  # 使用基准时间（offset=0）
            # 结束时间也要使用基准时间，与查询逻辑保持一致
            if offset == 0:
                chart_end_time = source_time.replace(seconds=interval).timestamp * 1000
            else:
                # 对于昨天和上周，查询时使用的是 end_time.replace(days=offset)
                # 数据调整后对应到基准的 end_time
                chart_end_time = end_time.timestamp * 1000

            # 补齐空点
            # 优化：使用更精确的匹配逻辑，确保数据点时间对齐，避免重复和错位
            # 同时考虑时间偏移，确保昨天和上周的数据与今天的数据在同一时间轴上对齐显示
            filled_data = []
            interval_ms = interval * 1000  # interval 单位为秒，转换为毫秒
            tolerance_ms = interval_ms // 2  # 允许的时间误差：半个间隔

            current_time = chart_start_time
            data_index = 0

            while current_time <= chart_end_time:
                # 查找最接近当前时间点的数据点（在误差范围内）
                matched_index = None
                min_diff = tolerance_ms + 1

                # 从当前位置开始查找，直到数据点时间超过当前时间+误差范围
                # 优化：由于数据已排序，可以提前终止搜索
                search_index = data_index
                while search_index < len(data):
                    data_time = data[search_index][0]
                    diff = data_time - current_time

                    # 如果数据点时间已经超出误差范围且大于当前时间，停止搜索
                    if diff > tolerance_ms:
                        break

                    # 检查是否在误差范围内（包括负的差值，即数据点在当前时间之前）
                    abs_diff = abs(diff)
                    if abs_diff <= tolerance_ms and abs_diff < min_diff:
                        min_diff = abs_diff
                        matched_index = search_index

                    search_index += 1

                if matched_index is not None:
                    # 找到匹配的数据点，使用实际数据，并将时间戳对齐到当前时间点
                    matched_data = data[matched_index]
                    filled_data.append([current_time, matched_data[1]])
                    # 跳过已匹配的数据点（注意：这里直接跳到 matched_index + 1，因为数据已排序）
                    data_index = matched_index + 1
                else:
                    # 无数据点，补充空点
                    filled_data.append([current_time, None])

                current_time += interval_ms

            # 优化：不再添加时间范围外的数据点，避免图表时间轴扩展
            # 如果需要显示范围外的数据，可以取消下面的注释
            # while data_index < len(data):
            #     filled_data.append(data[data_index])
            #     data_index += 1

            data = filled_data

        series.append({"name": name, "data": data})
    timezone = i18n.get_timezone()
    utcoffset = datetime.datetime.now(pytz.timezone(timezone)).utcoffset()
    if utcoffset is not None:
        timezone_offset = -int(utcoffset.total_seconds()) // 60
    else:
        timezone_offset = 0

    return {
        "unit": unit.suffix,
        "chart_type": "spline",
        "title": title or item.name,
        "subtitle": item.query_configs[0].get("metric_field", ""),
        "source_timestamp": source_time.timestamp * 1000,
        "locale": i18n.get_locale().replace("_", "-"),
        "timezone": timezone,
        "series": series,
        "timezoneOffset": timezone_offset,
    }
