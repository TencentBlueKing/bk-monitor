from datetime import timedelta
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from apps.constants import ExternalPermissionActionEnum, TokenStatusEnum
from apps.iam.handlers.actions import ActionEnum
from apps.log_commons.constants import DEFAULT_EXTERNAL_PERMISSION_EXPIRE_DAYS
from apps.log_commons.handlers.external_permission import ExternalPermissionHandler
from apps.log_commons.models import ExternalPermission


class TestExternalPermissionCreate(TestCase):
    SPACE_UID = "bkcc__2"
    ACTION_ID = "log_search"

    def _get(self, user):
        return ExternalPermission.objects.get(authorized_user=user, action_id=self.ACTION_ID, space_uid=self.SPACE_UID)

    def _create(self, users, resources, expire_time=None):
        kwargs = dict(
            authorized_users=users,
            space_uid=self.SPACE_UID,
            action_id=self.ACTION_ID,
            resources=resources,
        )
        if not expire_time:
            kwargs["expire_time"] = timezone.now() + timedelta(days=30)
        else:
            kwargs["expire_time"] = expire_time
        ExternalPermission.create(**kwargs)
        return kwargs.get("expire_time")

    # ---------- 全新用户创建 ----------
    def test_new_users_created(self):
        self._create(["user_a", "user_b"], ["1001", "1002"])
        self.assertEqual(ExternalPermission.objects.filter(space_uid=self.SPACE_UID).count(), 2)
        self.assertSetEqual(set(self._get("user_a").resources), {"1001", "1002"})

    # ---------- 已有用户新增资源合并 ----------
    def test_existing_user_resources_merged(self):
        self._create(["user_a"], ["1001"])
        self._create(["user_a"], ["1001", "1002"])
        perm = self._get("user_a")
        self.assertSetEqual(set(perm.resources), {"1001", "1002"})
        self.assertEqual(ExternalPermission.objects.filter(space_uid=self.SPACE_UID).count(), 1)

    # ---------- expire_time 有新值时正常更新 ----------
    def test_different_expire_time_updated(self):
        self._create(["user_a"], ["1001"])
        new_time = timezone.now() + timedelta(days=60)
        self._create(["user_a"], ["1001"], expire_time=new_time)
        self.assertEqual(self._get("user_a").expire_time, new_time)

    def test_new_user_uses_default_expire_time_when_empty(self):
        before = timezone.now() + timedelta(days=DEFAULT_EXTERNAL_PERMISSION_EXPIRE_DAYS)
        ExternalPermission.create(
            authorized_users=["user_a"],
            space_uid=self.SPACE_UID,
            action_id=self.ACTION_ID,
            resources=["1001"],
            expire_time=None,
        )
        after = timezone.now() + timedelta(days=DEFAULT_EXTERNAL_PERMISSION_EXPIRE_DAYS)

        expire_time = self._get("user_a").expire_time
        self.assertGreaterEqual(expire_time, before)
        self.assertLessEqual(expire_time, after)


class TestClusteringConfigActionValid(TestCase):
    """PO 环境（外部版）聚类配置接口的开放范围"""

    LOG_SEARCH = ExternalPermissionActionEnum.LOG_SEARCH.value
    LOG_EXTRACT = ExternalPermissionActionEnum.LOG_EXTRACT.value
    LOG_CLUSTERING = ExternalPermissionActionEnum.LOG_CLUSTERING.value

    # view_action 是 ViewSet 的方法名，check 对应 url_path check_regexp
    WRITE_VIEW_ACTIONS = ["update_access", "get_default_config", "debug", "check", "sample_log"]

    def _is_valid(self, view_set, view_action, action_id=None):
        return ExternalPermission.is_action_valid(
            view_set=view_set, view_action=view_action, action_id=action_id or self.LOG_CLUSTERING
        )

    # ---------- 聚类设置写入链路归属独立授权项 ----------
    def test_clustering_config_write_actions_allowed_for_log_clustering(self):
        for view_action in self.WRITE_VIEW_ACTIONS:
            with self.subTest(view_action=view_action):
                self.assertTrue(self._is_valid("ClusteringConfigViewSet", view_action))

    def test_regex_template_list_allowed_for_log_clustering(self):
        self.assertTrue(self._is_valid("RegexTemplateViewSet", "list"))

    # ---------- 只授予日志检索时拿不到聚类设置 ----------
    def test_clustering_config_write_actions_denied_for_log_search(self):
        for view_action in self.WRITE_VIEW_ACTIONS:
            with self.subTest(view_action=view_action):
                self.assertFalse(self._is_valid("ClusteringConfigViewSet", view_action, action_id=self.LOG_SEARCH))

    def test_regex_template_list_denied_for_log_search(self):
        self.assertFalse(self._is_valid("RegexTemplateViewSet", "list", action_id=self.LOG_SEARCH))

    # ---------- 聚类结果的读取仍归属日志检索 ----------
    def test_clustering_read_actions_stay_in_log_search(self):
        for view_action in ["get_config", "access_status"]:
            with self.subTest(view_action=view_action):
                self.assertTrue(self._is_valid("ClusteringConfigViewSet", view_action, action_id=self.LOG_SEARCH))

    # ---------- 接入能力不在开放范围内 ----------
    def test_create_access_not_allowed(self):
        for action_id in [self.LOG_CLUSTERING, self.LOG_SEARCH]:
            with self.subTest(action_id=action_id):
                self.assertFalse(self._is_valid("ClusteringConfigViewSet", "create_access", action_id=action_id))

    def test_regex_template_write_actions_not_allowed(self):
        for view_action in ["create", "partial_update", "destroy"]:
            with self.subTest(view_action=view_action):
                self.assertFalse(self._is_valid("RegexTemplateViewSet", view_action))

    # ---------- 其它授权项不得越界访问聚类配置 ----------
    def test_log_extract_cannot_update_clustering_config(self):
        self.assertFalse(self._is_valid("ClusteringConfigViewSet", "update_access", action_id=self.LOG_EXTRACT))

    def test_collector_tail_remains_unexposed(self):
        # 采集抽样不得直接挂 CollectorViewSet.tail / LogESBViewSet.call，否则会跳过索引集校验
        for view_set, view_action in [
            ("CollectorViewSet", "tail"),
            ("LogESBViewSet", "call"),
        ]:
            with self.subTest(view_set=view_set, view_action=view_action):
                self.assertFalse(self._is_valid(view_set, view_action))
                self.assertFalse(self._is_valid(view_set, view_action, action_id=self.LOG_SEARCH))

    def test_sample_log_action_id_is_log_clustering(self):
        from log_adapter.home.views import RequestProcessor

        self.assertEqual(
            RequestProcessor.get_action_id("ClusteringConfigViewSet", "sample_log"),
            self.LOG_CLUSTERING,
        )


class TestExportJobViewSetExternalContract(SimpleTestCase):
    """分片导出的外部版转发契约：逐 action 显式登记为日志检索，且不落入默认放行。"""

    LOG_SEARCH = ExternalPermissionActionEnum.LOG_SEARCH.value
    # view_action 是 ViewSet 的方法名，不是 url_path
    VIEW_ACTIONS = ["create", "list", "retrieve", "results", "download_link", "cancel"]

    def test_all_view_actions_are_valid_for_log_search(self):
        for view_action in self.VIEW_ACTIONS:
            with self.subTest(view_action=view_action):
                self.assertTrue(
                    ExternalPermission.is_action_valid(
                        view_set="ExportJobViewSet", view_action=view_action, action_id=self.LOG_SEARCH
                    )
                )

    def test_view_set_is_not_default_allowed(self):
        from log_adapter.home.views import RequestProcessor

        for view_action in self.VIEW_ACTIONS:
            with self.subTest(view_action=view_action):
                self.assertFalse(RequestProcessor.is_default_allowed("ExportJobViewSet", view_action))
                self.assertEqual(RequestProcessor.get_action_id("ExportJobViewSet", view_action), self.LOG_SEARCH)

    def test_registered_view_actions_match_route_actions(self):
        """登记项必须与路由实际反查出的 view_set/view_action 一致，否则代理层仍然 403"""
        from django.urls import resolve

        for path, method, view_action in [
            ("/api/v1/search/export_jobs/", "post", "create"),
            ("/api/v1/search/export_jobs/", "get", "list"),
            ("/api/v1/search/export_jobs/1/", "get", "retrieve"),
            ("/api/v1/search/export_jobs/1/results/", "get", "results"),
            ("/api/v1/search/export_jobs/1/download_link/", "get", "download_link"),
            ("/api/v1/search/export_jobs/1/cancel/", "post", "cancel"),
        ]:
            with self.subTest(path=path, method=method):
                view_func = resolve(path).func
                self.assertEqual(view_func.cls.__name__, "ExportJobViewSet")
                self.assertEqual(view_func.actions.get(method), view_action)

    def test_unregistered_view_action_is_rejected(self):
        self.assertFalse(
            ExternalPermission.is_action_valid(
                view_set="ExportJobViewSet", view_action="partial_update", action_id=self.LOG_SEARCH
            )
        )

    def test_create_resolves_index_set_from_body(self):
        """创建任务时转发入口能从 body 解析出索引集，实例级校验不会被跳过"""
        from log_adapter.home.views import RequestProcessor

        self.assertEqual(
            RequestProcessor.get_resource(
                action_id=self.LOG_SEARCH,
                kwargs={},
                json_data_str='{"space_uid": "bkcc__2", "index_set_id": 1001}',
            ),
            1001,
        )

    def test_detail_route_cannot_resolve_index_set(self):
        """详情类路由的 pk 是任务ID，转发入口解析不出索引集，收敛只能依赖视图内的创建者过滤"""
        from log_adapter.home.views import RequestProcessor

        self.assertIsNone(
            RequestProcessor.get_resource(action_id=self.LOG_SEARCH, kwargs={"pk": "1"}, json_data_str="{}")
        )


class TestLogClusteringIndependentFromLogSearch(TestCase):
    """log_clustering 与 log_search 相互独立，进入聚类设置时取资源交集"""

    SPACE_UID = "bkcc__2"
    LOG_SEARCH = ExternalPermissionActionEnum.LOG_SEARCH.value
    LOG_CLUSTERING = ExternalPermissionActionEnum.LOG_CLUSTERING.value

    def _create(self, action_id, resources, expired=False):
        expire_time = timezone.now() + timedelta(days=-1 if expired else 30)
        ExternalPermission.objects.create(
            authorized_user="user_a",
            space_uid=self.SPACE_UID,
            action_id=action_id,
            resources=resources,
            expire_time=expire_time,
        )

    def _get_log_search_resources(self):
        return ExternalPermission.get_resources(
            action_id=self.LOG_SEARCH, authorized_user="user_a", space_uid=self.SPACE_UID
        )

    def _can_access_clustering_settings(self, index_set_id):
        return ExternalPermission.can_access_clustering_settings(
            space_uid=self.SPACE_UID, authorized_user="user_a", index_set_id=index_set_id
        )

    def test_clustering_does_not_imply_log_search(self):
        from apps.constants import ACTIONS_IMPLYING_LOG_SEARCH

        self.assertNotIn(self.LOG_CLUSTERING, ACTIONS_IMPLYING_LOG_SEARCH)
        self.assertIn(ExternalPermissionActionEnum.CLIENT_LOG.value, ACTIONS_IMPLYING_LOG_SEARCH)

    def test_clustering_resources_not_merged_into_log_search(self):
        # 只授聚类配置时，不得把其索引集并入 log_search，否则会放通检索/上下文/导出
        self._create(self.LOG_CLUSTERING, [1001])

        result = self._get_log_search_resources()

        self.assertTrue(result["allowed"])
        self.assertEqual(result["resources"], [])

    def test_clustering_resources_not_polluted_by_log_search(self):
        # 反向不成立：日志检索授权不得让被授权人改到该索引集的聚类配置
        self._create(self.LOG_SEARCH, [1001])
        self._create(self.LOG_CLUSTERING, [2002])

        result = ExternalPermission.get_resources(
            action_id=self.LOG_CLUSTERING, authorized_user="user_a", space_uid=self.SPACE_UID
        )

        self.assertEqual(result["resources"], [2002])

    def test_clustering_settings_requires_both_permissions_on_same_index_set(self):
        self._create(self.LOG_SEARCH, [1001, 1002])
        self._create(self.LOG_CLUSTERING, [1002, 1003])

        self.assertFalse(self._can_access_clustering_settings(1001))
        self.assertTrue(self._can_access_clustering_settings(1002))
        self.assertFalse(self._can_access_clustering_settings(1003))

    def test_clustering_only_cannot_access_clustering_settings(self):
        self._create(self.LOG_CLUSTERING, [1001])

        self.assertFalse(self._can_access_clustering_settings(1001))

    def test_search_only_cannot_access_clustering_settings(self):
        self._create(self.LOG_SEARCH, [1001])

        self.assertFalse(self._can_access_clustering_settings(1001))

    def test_permission_from_other_space_does_not_grant_access(self):
        # 空间隔离: 另一空间的聚类配置授权不得让本空间的同号索引集通过校验
        self._create(self.LOG_SEARCH, [1001])
        ExternalPermission.objects.create(
            authorized_user="user_a",
            space_uid="bkcc__3",
            action_id=self.LOG_CLUSTERING,
            resources=[1001],
            expire_time=timezone.now() + timedelta(days=30),
        )

        self.assertFalse(self._can_access_clustering_settings(1001))

    def test_expired_clustering_permission_denies_access(self):
        self._create(self.LOG_SEARCH, [1001])
        self._create(self.LOG_CLUSTERING, [1001], expired=True)

        self.assertFalse(self._can_access_clustering_settings(1001))

    def test_unresolved_index_set_is_denied(self):
        # 解析不出索引集时必须拒绝, 鉴权入口不做兜底放行
        self._create(self.LOG_SEARCH, [1001])
        self._create(self.LOG_CLUSTERING, [1001])

        self.assertFalse(self._can_access_clustering_settings(None))

    def test_get_resource_from_index_set_scoped_request(self):
        """转发入口需要能从聚类配置类请求里解析出索引集, 否则实例级校验会被跳过"""
        from log_adapter.home.views import RequestProcessor

        self.assertEqual(
            RequestProcessor.get_resource(
                action_id=self.LOG_CLUSTERING, kwargs={"index_set_id": "1001"}, json_data_str=""
            ),
            1001,
        )
        self.assertEqual(
            RequestProcessor.get_resource(
                action_id=self.LOG_CLUSTERING, kwargs={}, json_data_str='{"index_set_id": 1001}'
            ),
            1001,
        )
        # 空间维度的授权项不解析索引集
        self.assertIsNone(
            RequestProcessor.get_resource(
                action_id=ExternalPermissionActionEnum.LOG_EXTRACT.value,
                kwargs={"index_set_id": "1001"},
                json_data_str="",
            )
        )


class TestLogClusteringAuthorizerStatus(TestCase):
    """聚类配置授权的有效性同样跟随授权人在该索引集上的日志检索权限"""

    SPACE_UID = "bkcc__2"
    AUTHORIZER = "authorizer_a"
    LOG_CLUSTERING = ExternalPermissionActionEnum.LOG_CLUSTERING.value

    def setUp(self):
        self.permission = ExternalPermission.objects.create(
            authorized_user="user_a",
            space_uid=self.SPACE_UID,
            action_id=self.LOG_CLUSTERING,
            resources=[1001],
            expire_time=timezone.now() + timedelta(days=30),
        )

    def _status(self, search_log_allowed: bool):
        batch_result = {"1001": {ActionEnum.SEARCH_LOG.id: search_log_allowed}}
        with (
            patch(
                "apps.log_commons.models.AuthorizerSettings.get_authorizer",
                return_value=self.AUTHORIZER,
            ),
            patch(
                "apps.iam.handlers.permission.Permission.batch_is_allowed",
                return_value=batch_result,
            ),
        ):
            return self.permission.status

    def test_status_available_when_authorizer_can_search(self):
        self.assertEqual(self._status(search_log_allowed=True), TokenStatusEnum.AVAILABLE.value)

    def test_status_invalid_when_authorizer_lost_search_permission(self):
        self.assertEqual(self._status(search_log_allowed=False), TokenStatusEnum.INVALID.value)

    def test_handler_status_follows_index_set_permission(self):
        """列表页走 handler 的批量预取路径, 聚类配置授权必须被纳入索引集维度的预取范围"""
        handler = ExternalPermissionHandler()

        with (
            patch(
                "apps.log_commons.handlers.external_permission.AuthorizerSettings.get_authorizer",
                return_value=self.AUTHORIZER,
            ),
            patch(
                "apps.iam.handlers.permission.Permission.batch_is_allowed",
                return_value={"1001": {ActionEnum.SEARCH_LOG.id: False}},
            ),
            patch(
                "apps.log_commons.handlers.external_permission.SpaceApi.batch_get_space_detail",
                return_value={},
            ),
        ):
            result = handler.list(space_uid=self.SPACE_UID)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["action_id"], self.LOG_CLUSTERING)
        self.assertEqual(result[0]["status"], TokenStatusEnum.INVALID.value)


class TestLogClusteringResourceByAction(TestCase):
    """授权页「操作实例」候选列表: 聚类配置与日志检索同为索引集维度"""

    SPACE_UID = "bkcc__2"

    def test_resource_by_action_returns_index_sets(self):
        from apps.log_search.models import LogIndexSet

        index_set = LogIndexSet.objects.create(
            index_set_name="clustering_index_set", space_uid=self.SPACE_UID, scenario_id="es"
        )

        with patch(
            "apps.log_search.handlers.index_set.IndexSetHandler.get_all_related_space_uids",
            return_value=[self.SPACE_UID],
        ):
            resources = ExternalPermission.get_resource_by_action(
                action_id=ExternalPermissionActionEnum.LOG_CLUSTERING.value, space_uid=self.SPACE_UID
            )

        self.assertEqual(
            resources,
            [{"id": index_set.index_set_id, "uid": index_set.index_set_id, "text": "clustering_index_set"}],
        )
