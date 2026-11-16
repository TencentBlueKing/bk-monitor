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
from unittest import mock

import pytest
from rest_framework import serializers
from rest_framework.test import APIRequestFactory, force_authenticate

from bkmonitor.models import ActionConfig, AlertAssignGroup
from bkmonitor.utils.common_utils import fetch_biz_id_from_request
from fta_web.action import views as action_views
from fta_web.assign import views as assign_views

pytestmark = pytest.mark.django_db


def _create_action_config(biz):
    return ActionConfig.objects.create(name=f"config-{biz}", bk_biz_id=biz, plugin_id="2", execute_config={})


def _create_assign_group(biz):
    return AlertAssignGroup.objects.create(name=f"group-{biz}", bk_biz_id=biz)


USER = SimpleNamespace(tenant_id="tenant-a", is_active=True)


def _test_viewset(monkeypatch, model, views_module, viewset):
    # 模拟 IAM 放行请求业务：数据范围必须由视图自身收敛，不能依赖对象鉴权
    monkeypatch.setattr(
        views_module,
        "BusinessActionPermission",
        lambda *_: SimpleNamespace(has_permission=lambda *_: True, has_object_permission=lambda *_: True),
    )

    class ObjectSerializer(serializers.ModelSerializer):
        # 与真实序列化器一致，业务 ID 按整数输出
        bk_biz_id = serializers.IntegerField()

        class Meta:
            fields = ["id", "name", "bk_biz_id"]

    ObjectSerializer.Meta.model = model

    class TestViewSet(viewset):
        authentication_classes = []

        def get_serializer_class(self):
            return ObjectSerializer

    return TestViewSet


@pytest.fixture(
    params=[
        (ActionConfig, action_views, action_views.ActionConfigViewSet, _create_action_config),
        (AlertAssignGroup, assign_views, assign_views.AssignGroupViewSet, _create_assign_group),
    ],
    ids=["action_config", "assign_group"],
)
def api(request, monkeypatch):
    model, views_module, viewset, create = request.param
    TestViewSet = _test_viewset(monkeypatch, model, views_module, viewset)
    objects = {biz: create(biz) for biz in [0, 2, 3]}

    def call(biz=2, target=None):
        params = {"with_advance_fields": "no"}
        if biz is not None:
            params["bk_biz_id"] = biz
        path = "/?" + "&".join(f"{key}={value}" for key, value in params.items())
        req = APIRequestFactory().get(path)
        req.biz_id = None if biz is None else str(biz)
        force_authenticate(req, user=SimpleNamespace(tenant_id="tenant-a", is_active=True))
        action = "retrieve" if target else "list"
        return TestViewSet.as_view({"get": action})(req, **({"pk": target.id} if target else {}))

    def mutate(method, target, data):
        req = getattr(APIRequestFactory(), method)("/", data=data, format="json")
        # 与 RequestProvider 中间件一致，写请求的业务从 JSON body 解析
        req.biz_id = fetch_biz_id_from_request(req, {})
        force_authenticate(req, user=SimpleNamespace(tenant_id="tenant-a", is_active=True))
        action = {"patch": "partial_update", "delete": "destroy"}[method]
        return TestViewSet.as_view({method: action})(req, pk=target.id)

    call.mutate = mutate
    yield objects, call
    model.objects.filter(id__in=[obj.id for obj in objects.values()]).delete()


def _biz_ids(response):
    return {int(item["bk_biz_id"]) for item in response.data}


def test_list_only_returns_global_and_request_business(api):
    objects, call = api
    response = call(biz=2)
    assert response.status_code == 200
    assert _biz_ids(response) & {0, 2, 3} == {0, 2}


def test_list_without_business_only_returns_global(api):
    objects, call = api
    response = call(biz=None)
    assert response.status_code == 200
    assert _biz_ids(response) & {0, 2, 3} == {0}


def test_retrieve_rejects_other_business_object(api):
    objects, call = api
    assert call(biz=2, target=objects[0]).status_code == 200
    assert call(biz=2, target=objects[2]).status_code == 200
    assert call(biz=2, target=objects[3]).status_code == 404
    assert call(biz=None, target=objects[3]).status_code == 404


# AbstractRecordModel 保存时写入 naive datetime，会触发与本用例无关的 RuntimeWarning
@pytest.mark.filterwarnings("ignore::RuntimeWarning")
def test_write_uses_business_from_json_body(api):
    objects, call = api
    original_name = objects[3].name
    assert call.mutate("patch", objects[3], {"bk_biz_id": 2, "name": "changed"}).status_code == 404
    assert call.mutate("delete", objects[3], {"bk_biz_id": 2}).status_code == 404
    assert call.mutate("delete", objects[3], {}).status_code == 404
    objects[3].refresh_from_db()
    assert objects[3].name == original_name

    assert call.mutate("patch", objects[2], {"bk_biz_id": 2, "name": "changed"}).status_code == 200
    objects[2].refresh_from_db()
    assert objects[2].name == "changed"
    assert call.mutate("delete", objects[2], {"bk_biz_id": 2}).status_code == 204


def test_action_config_statistics_use_resolved_business(monkeypatch):
    TestViewSet = _test_viewset(monkeypatch, ActionConfig, action_views, action_views.ActionConfigViewSet)
    strategy_dict = mock.Mock(return_value={})
    config_rules = mock.Mock(return_value=[])
    monkeypatch.setattr(action_views, "get_action_config_strategy_dict", strategy_dict)
    monkeypatch.setattr(action_views, "get_action_config_rules", config_rules)
    monkeypatch.setattr(action_views, "ActionInstanceDocument", mock.MagicMock())
    objects = {biz: _create_action_config(biz) for biz in [0, 2, 3]}

    try:
        # 业务通过别名参数传入时，统计范围也需按解析出的业务限定
        for action, kwargs in (("list", {}), ("retrieve", {"pk": objects[0].id})):
            req = APIRequestFactory().get("/?bizId=2")
            req.biz_id = fetch_biz_id_from_request(req, {})
            force_authenticate(req, user=USER)
            assert TestViewSet.as_view({"get": action})(req, **kwargs).status_code == 200
            assert strategy_dict.call_args.kwargs["bk_biz_id"] == "2"
            assert config_rules.call_args.args[1] == "2"
    finally:
        ActionConfig.objects.filter(id__in=[obj.id for obj in objects.values()]).delete()
