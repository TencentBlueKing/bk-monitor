"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import pytest

from bkmonitor.data_source.utils.apm import TraceDatasourceTarget
from rum_web.constants import RumQueryMode
from rum_web.handlers.level.base import BaseRumLevelHandler
from rum_web.handlers.level.factory import RumLevelHandlerFactory, UnsupportedRumQueryMode
from rum_web.handlers.level.span import SpanLevelHandler


def _make_target(table_id: str = "bk_rum.default.span") -> TraceDatasourceTarget:
    return TraceDatasourceTarget.build(bk_biz_id=2, app_name="my_app", table_id=table_id)


class TestRumLevelHandlerFactory:
    """test_level_factory.py 验收断言"""

    # [a] 合法 mode 返回对应 Level
    def test_span_mode_returns_span_handler(self):
        data_sources = [_make_target()]
        handler = RumLevelHandlerFactory.create(RumQueryMode.SPAN.value, data_sources)
        assert isinstance(handler, SpanLevelHandler)

    def test_span_mode_string_returns_span_handler(self):
        """mode 以字符串形式传入同样有效"""
        data_sources = [_make_target()]
        handler = RumLevelHandlerFactory.create("span", data_sources)
        assert isinstance(handler, SpanLevelHandler)

    # [b] 未注册模式明确失败
    def test_unknown_mode_raises(self):
        with pytest.raises(UnsupportedRumQueryMode):
            RumLevelHandlerFactory.create("unknown_mode", [_make_target()])

    def test_view_mode_not_registered_raises(self):
        """view 尚未注册，应明确失败"""
        with pytest.raises(UnsupportedRumQueryMode):
            RumLevelHandlerFactory.create(RumQueryMode.VIEW.value, [_make_target()])

    def test_session_mode_not_registered_raises(self):
        """session 尚未注册，应明确失败"""
        with pytest.raises(UnsupportedRumQueryMode):
            RumLevelHandlerFactory.create(RumQueryMode.SESSION.value, [_make_target()])

    def test_empty_mode_raises(self):
        with pytest.raises(UnsupportedRumQueryMode):
            RumLevelHandlerFactory.create("", [_make_target()])

    # [c] data_sources 原样传入 Level
    def test_data_sources_passed_to_handler(self):
        data_sources = [_make_target("bk_rum.biz2.span"), _make_target("bk_rum.biz3.span")]
        handler = RumLevelHandlerFactory.create(RumQueryMode.SPAN.value, data_sources)
        assert handler.data_sources is data_sources

    def test_handler_is_base_rum_level_handler_subclass(self):
        handler = RumLevelHandlerFactory.create(RumQueryMode.SPAN.value, [_make_target()])
        assert isinstance(handler, BaseRumLevelHandler)
