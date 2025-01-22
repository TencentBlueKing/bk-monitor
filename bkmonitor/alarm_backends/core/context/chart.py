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
import asyncio
import base64
import datetime
import json
import logging
import os
import tempfile
from typing import Optional

import arrow
import pytz
from django.conf import settings
from django.template.loader import get_template
from django.utils.translation import gettext as _

from alarm_backends.constants import CONST_ONE_DAY
from alarm_backends.core.control.item import Item
from alarm_backends.core.i18n import i18n
from alarm_backends.service.scheduler.tasks.image_exporter import render_html_string_to_graph
from bkmonitor.browser import get_browser, get_or_create_eventloop
from bkmonitor.utils import time_tools
from constants.data_source import DataTypeLabel
from constants.strategy import AGG_METHOD_REAL_TIME
from core.unit import load_unit

logger = logging.getLogger("fta_action.run")


async def render_html(html_file_path: str) -> Optional[bytes]:
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
        return

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

        # 使用pyppeteer渲染
        if settings.ALARM_GRAPH_RENDER_MODE == "pyppeteer":
            return render_html_string_to_graph(html_string)
        else:
            # 将html写入临时文件，并使用浏览器渲染
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
            if value:
                value = round(value, settings.POINT_PRECISION)
            data.append([record["_time_"] - offset * CONST_ONE_DAY * 1000, value])

        series.append({"name": name, "data": data})
    timezone = i18n.get_timezone()
    timezone_offset = -int(datetime.datetime.now(pytz.timezone(timezone)).utcoffset().total_seconds()) // 60

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
