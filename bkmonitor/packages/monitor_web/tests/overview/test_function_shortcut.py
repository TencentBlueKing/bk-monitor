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

from monitor_web.overview.resources import GetFunctionShortcutResource

MODULE = "monitor_web.overview.resources"


def _app(application_id: int, bk_biz_id: int):
    """构造一个轻量的 Application 占位对象（仅含被读取的字段）。"""
    return SimpleNamespace(
        application_id=application_id,
        bk_biz_id=bk_biz_id,
        app_name=f"app_{application_id}",
        app_alias=f"别名_{application_id}",
    )


def _svc(topo_key: str):
    return {"topo_key": topo_key}


class TestBuildAppServicesMap:
    """_build_app_services_map：并发预取各应用服务集合。"""

    def test_concurrent_prefetch_matches_serial(self):
        """并发预取的结果与逐应用串行累积完全一致（覆盖多应用、避免结果错位/丢失）。"""
        apps = {1: _app(1, 100), 2: _app(2, 200), 3: _app(3, 300)}
        per_app = {
            1: [_svc("svc-a"), _svc("svc-b")],
            2: [_svc("svc-c")],
            3: [_svc("svc-d"), _svc("svc-e"), _svc("svc-d")],  # 含重复，去重为 set
        }

        with mock.patch(
            f"{MODULE}.ServiceHandler.list_services",
            side_effect=lambda app: per_app[app.application_id],
        ):
            result = GetFunctionShortcutResource._build_app_services_map(apps)

        assert result == {
            1: {"svc-a", "svc-b"},
            2: {"svc-c"},
            3: {"svc-d", "svc-e"},
        }

    def test_empty_apps_short_circuits(self):
        """空应用集合直接返回空 dict，且不触发任何服务查询。"""
        with mock.patch(f"{MODULE}.ServiceHandler.list_services") as m:
            assert GetFunctionShortcutResource._build_app_services_map({}) == {}
            m.assert_not_called()

    def test_single_app_failure_is_skipped_not_fatal(self):
        """单个应用查询异常时跳过该应用（map_ignore_exception），其余应用不受影响。

        这是相较原串行实现（任一应用异常即整个接口 500）的稳健性增强。
        """
        apps = {1: _app(1, 100), 2: _app(2, 200)}

        def _side_effect(app):
            if app.application_id == 2:
                raise ValueError("apm api down for app 2")
            return [_svc("svc-a")]

        with mock.patch(f"{MODULE}.ServiceHandler.list_services", side_effect=_side_effect):
            result = GetFunctionShortcutResource._build_app_services_map(apps)

        # 失败的 app 2 被丢弃，不会 KeyError；app 1 正常返回
        assert result == {1: {"svc-a"}}


class TestFavoriteApmServiceUsesCorrectApp:
    """get_favorite_shortcuts 的 apm_service 分支：每条收藏项归属正确的应用。"""

    def test_each_item_belongs_to_its_own_app(self):
        """回归此前的预存 bug：收藏项的 bk_biz_id/app_name/application_id/app_alias
        曾误用上一循环残留的 app（恒为最后一个应用），导致所有收藏项被错挂到最后一个应用。
        """
        app1, app2 = _app(1, 100), _app(2, 200)
        apps_qs = [app1, app2]
        # 两个应用各有一条收藏配置；app1 收藏的服务仍存在，app2 收藏含一个已过期服务
        configs = [
            SimpleNamespace(level_key="1", config_value=["svc-a"]),
            SimpleNamespace(level_key="2", config_value=["svc-c", "svc-stale"]),
        ]
        per_app = {1: [_svc("svc-a")], 2: [_svc("svc-c")]}

        with (
            mock.patch(f"{MODULE}.get_request", return_value=mock.Mock()),
            mock.patch(f"{MODULE}.get_request_tenant_id", return_value="system"),
            mock.patch(f"{MODULE}.ApmMetaConfig.objects") as mock_apm_objects,
            mock.patch(f"{MODULE}.Application.objects") as mock_app_objects,
            mock.patch(
                f"{MODULE}.ServiceHandler.list_services",
                side_effect=lambda app: per_app[app.application_id],
            ),
            # 权限过滤直通，便于断言归属字段
            mock.patch(f"{MODULE}.filter_data_by_permission", side_effect=lambda **kw: kw["data"]),
        ):
            mock_apm_objects.filter.return_value = configs
            mock_app_objects.filter.return_value = apps_qs

            result = GetFunctionShortcutResource.get_favorite_shortcuts("admin", ["apm_service"], limit=10)

        assert len(result) == 1
        items = result[0]["items"]
        # 过期服务 svc-stale 被过滤，剩 svc-a / svc-c 各一条
        by_service = {item["service_name"]: item for item in items}
        assert set(by_service) == {"svc-a", "svc-c"}

        # 关键断言：每条收藏项归属各自的应用，而非统一挂到最后一个应用
        assert by_service["svc-a"]["application_id"] == 1
        assert by_service["svc-a"]["bk_biz_id"] == 100
        assert by_service["svc-a"]["app_name"] == "app_1"
        assert by_service["svc-c"]["application_id"] == 2
        assert by_service["svc-c"]["bk_biz_id"] == 200
        assert by_service["svc-c"]["app_name"] == "app_2"


class TestRecentApmService:
    """get_recent_shortcuts 的 apm_service 分支：并发预取 + 存在性过滤 + limit 截断。"""

    def _patch_ctx(self, access_records, apps_qs, per_app):
        """构造 recent apm_service 所需的 mock 上下文。"""
        user_config = SimpleNamespace(value={"apm_service": access_records})
        ctx = []
        p_uc = mock.patch(f"{MODULE}.UserConfig")
        p_app = mock.patch(f"{MODULE}.Application.objects")
        p_svc = mock.patch(
            f"{MODULE}.ServiceHandler.list_services",
            side_effect=lambda app: per_app[app.application_id],
        )
        ctx.extend([p_uc, p_app, p_svc])
        uc = p_uc.start()
        uc.objects.filter.return_value.first.return_value = user_config
        app_objs = p_app.start()
        app_objs.filter.return_value = apps_qs
        p_svc.start()
        return ctx

    @staticmethod
    def _stop(ctx):
        for p in ctx:
            p.stop()

    def test_parallel_equivalence_and_filtering(self):
        """并发预取与串行等价；过期服务、不存在的应用都被正确过滤，且各项归属正确应用。"""
        app1, app2 = _app(1, 100), _app(2, 200)
        access_records = [
            {"application_id": 1, "service_name": "svc-a"},  # 存在
            {"application_id": 2, "service_name": "svc-c"},  # 存在
            {"application_id": 2, "service_name": "svc-stale"},  # 已过期 → 过滤
            {"application_id": 999, "service_name": "svc-x"},  # 应用不存在 → 跳过
        ]
        per_app = {1: [_svc("svc-a")], 2: [_svc("svc-c")]}

        ctx = self._patch_ctx(access_records, [app1, app2], per_app)
        try:
            result = GetFunctionShortcutResource.get_recent_shortcuts("admin", ["apm_service"], limit=10)
        finally:
            self._stop(ctx)

        items = result[0]["items"]
        by_service = {item["service_name"]: item for item in items}
        assert set(by_service) == {"svc-a", "svc-c"}
        assert by_service["svc-a"]["application_id"] == 1
        assert by_service["svc-a"]["bk_biz_id"] == 100
        assert by_service["svc-c"]["application_id"] == 2
        assert by_service["svc-c"]["bk_biz_id"] == 200

    def test_limit_truncation(self):
        """limit 截断生效：两条均有效但 limit=1 时只返回 1 条。"""
        app1, app2 = _app(1, 100), _app(2, 200)
        access_records = [
            {"application_id": 1, "service_name": "svc-a"},
            {"application_id": 2, "service_name": "svc-c"},
        ]
        per_app = {1: [_svc("svc-a")], 2: [_svc("svc-c")]}

        ctx = self._patch_ctx(access_records, [app1, app2], per_app)
        try:
            result = GetFunctionShortcutResource.get_recent_shortcuts("admin", ["apm_service"], limit=1)
        finally:
            self._stop(ctx)

        assert len(result[0]["items"]) == 1
