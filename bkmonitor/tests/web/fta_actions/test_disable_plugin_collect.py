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
from django.http import QueryDict

from bkmonitor.models import EventPluginInstance, PluginType
from core.errors.iam import PermissionDeniedError
from fta_web.event_plugin.resources import DisablePluginCollectResource
from fta_web.event_plugin.views import EventPluginViewSet


@pytest.mark.parametrize(
    ("params", "ids"),
    [
        ({"id": 1}, [1]),
        ({"ids": 1}, [1]),
        ({"ids": "1, 2"}, [1, 2]),
        ({"ids": [1, "2"]}, [1, 2]),
        (QueryDict("ids=1&ids=2"), [1, 2]),
    ],
)
def test_disable_ids(params, ids):
    assert DisablePluginCollectResource().validate_request_data(params)["ids"] == ids


@pytest.mark.parametrize("params", [{}, {"ids": []}, {"ids": "1,bad"}, {"ids": {"bad": 1}}, {"ids": 0}])
def test_invalid_ids(params):
    assert not DisablePluginCollectResource.RequestSerializer(data=params).is_valid()


def test_disable_batch(mocker):
    one, unbound, two = [SimpleNamespace(id=i, data_id=data_id) for i, data_id in [(1, 41), (2, 0), (3, 43)]]
    query = mocker.patch.object(EventPluginInstance.objects, "filter")
    query.return_value.filter.return_value = [one, unbound, two]
    manager = mocker.patch("fta_web.event_plugin.resources.get_manager")
    result = DisablePluginCollectResource().request({"ids": "1,2,3", "bk_biz_id": 9})
    query.assert_called_once_with(id__in=[1, 2, 3])
    query.return_value.filter.assert_called_once_with(bk_biz_id=9)
    assert manager.call_args_list == [mocker.call(one), mocker.call(two)]
    assert manager.return_value.switch.call_args_list == [mocker.call(False), mocker.call(False)]
    assert result == {"disabled_ids": [1, 3]}


@pytest.mark.parametrize(
    ("biz", "body", "allowed"),
    [(9, {}, True), (9, {"bk_biz_id": 8}, True), (9, {"bk_biz_id": 9}, False), (0, {"bk_biz_id": 0}, True)],
)
def test_business_permission_cannot_disable_outside_scope(mocker, biz, body, allowed):
    view = EventPluginViewSet()
    view.action = "instance/disable_collect"
    request = SimpleNamespace(method="POST", biz_id=biz, data=body)
    view.request = request
    mocker.patch("fta_web.event_plugin.views.IAMPermission.has_permission", side_effect=PermissionDeniedError())
    mocker.patch("fta_web.event_plugin.views.BusinessActionPermission.has_permission", return_value=allowed)
    with pytest.raises(PermissionDeniedError):
        view.check_permissions(request)


def test_disable_single_updates_datasource_and_instance(mocker):
    instance = EventPluginInstance(id=7, data_id=42, is_enabled=True, update_user="tester")
    api = mocker.Mock()
    mocker.patch("bkmonitor.event_plugin.accessor.api", new=api)
    mocker.patch("bkmonitor.event_plugin.accessor.get_request_username", return_value="tester")
    save = mocker.patch.object(instance, "save")
    mocker.patch.object(EventPluginInstance.objects, "filter", return_value=[instance])
    instance.event_plugin = SimpleNamespace(plugin_type=PluginType.HTTP_PUSH)
    assert DisablePluginCollectResource().request({"id": 7}) == {"disabled_ids": [7]}
    api.metadata.modify_data_id.assert_called_once_with({"data_id": 42, "is_enable": False, "operator": "tester"})
    assert instance.is_enabled is False
    save.assert_called_once_with(update_fields=["is_enabled"])


def test_business_permission_allows_scoped_request(mocker):
    view = EventPluginViewSet()
    view.action = "instance/disable_collect"
    request = SimpleNamespace(method="POST", biz_id=9, data={"bk_biz_id": 9, "ids": [1]})
    view.request = request
    mocker.patch("fta_web.event_plugin.views.IAMPermission.has_permission", side_effect=PermissionDeniedError())
    check = mocker.patch("fta_web.event_plugin.views.BusinessActionPermission.has_permission", return_value=True)
    view.check_permissions(request)
    check.assert_called_once_with(request, view)
