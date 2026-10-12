"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from types import SimpleNamespace

import pytest
from rest_framework.exceptions import ValidationError

from monitor_web.plugin.views import CollectorPluginViewSet, PluginManagerFactory


@pytest.mark.parametrize("bk_biz_id", [0, 2, -2])
def test_replace_plugin_is_deprecated_without_loading_or_mutating_plugin(mocker, bk_biz_id):
    view = CollectorPluginViewSet()
    get_queryset = mocker.patch.object(view, "get_queryset")
    get_manager = mocker.patch.object(PluginManagerFactory, "get_manager")
    request = SimpleNamespace(biz_id=bk_biz_id, data={"plugin_id": "test_plugin", "bk_biz_id": bk_biz_id})

    with pytest.raises(ValidationError) as exc:
        view.replace_plugin(request)

    assert exc.value.get_codes() == ["deprecated"]
    get_queryset.assert_not_called()
    get_manager.assert_not_called()
