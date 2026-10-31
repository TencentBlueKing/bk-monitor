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
from rum_web.handlers.query.session import SessionQuery
from semconv.rum.session import SessionSpec


class SessionLevelHandler(BaseRumLevelHandler):
    query: SessionQuery

    DISPLAY_FIELDS = [
        "attributes.session.id",
        "start_time",
        "attributes.user.id",
        "resource.user_agent.name",
        "resource.user_agent.os.name",
        "enter_url_template",
        "view_count",
        "action_count",
        "error_count",
        "duration",
    ]
    RESIDENT_FIELDS = [
        "attributes.session.id",
        "attributes.user.id",
        "resource.user_agent.name",
        "resource.user_agent.os.name",
    ]

    MODE = RumQueryMode.SESSION.value
    SPEC = SessionSpec

    def __init__(self, data_sources: list[TraceDatasourceTarget]):
        super().__init__(data_sources)
        self.query = SessionQuery(data_sources)
