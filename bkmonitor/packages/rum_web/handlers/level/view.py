"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from bkmonitor.data_source.utils.apm import TraceDatasourceTarget
from rum_web.constants import RumQueryMode
from rum_web.handlers.level.base import BaseRumLevelHandler
from rum_web.handlers.query.view import ViewQuery
from semconv.rum.view import ViewSpec


class ViewLevelHandler(BaseRumLevelHandler):
    query: ViewQuery

    DISPLAY_FIELDS = [
        "attributes.view.id",
        "start_time",
        "attributes.view.url_template",
        "attributes.view.loading_type",
        "web_vitals.fcp",
        "web_vitals.lcp",
        "web_vitals.cls",
        "web_vitals.inp",
        "web_vitals.ttfb",
        "error_count",
        "request_count",
        "action_count",
        "resource.user_agent.name",
    ]
    RESIDENT_FIELDS = [
        "attributes.view.id",
        "attributes.view.url_template",
        "attributes.view.loading_type",
        "attributes.user.id",
    ]

    MODE = RumQueryMode.VIEW.value
    SPEC = ViewSpec

    def __init__(self, data_sources: list[TraceDatasourceTarget]):
        super().__init__(data_sources)
        self.query = ViewQuery(data_sources)
