import copy
import json
from unittest.mock import patch

from django.test import TestCase, override_settings

from apps.api.modules.transfer import parse_cluster_info
from apps.log_databus.constants import DORIS_CLUSTER_TYPE, REGISTERED_SYSTEM_DEFAULT, VisibleEnum


BLUEKING_BK_BIZ_ID = 2
OWNER_BIZ_ID = 5
SPACE_BIZ_ID = -101
CLUSTER_ID = 900

# 与 apps/tests/log_databus/test_storage.py:52 使用同一套测试中间件，
# 注入 request.user 与请求上下文，避免未登录被 302 重定向。
OVERRIDE_MIDDLEWARE = "apps.tests.middlewares.OverrideMiddleware"

ES_CONFIG = {
    "ES_PUBLIC_STORAGE_DURATION": 7,
    "ES_PRIVATE_STORAGE_DURATION": 7,
    "ES_REPLICAS": 0,
    "ES_SHARDS": 3,
    "ES_SHARDS_MAX": 64,
}


def _space_uid_stub(bk_biz_id):
    """隔离 Metadata 空间接口；真实实现见 bkm_space/utils.py:37-56。"""

    return f"bkci__{-int(bk_biz_id)}" if int(bk_biz_id) < 0 else f"bkcc__{bk_biz_id}"


def _parse_space_uid_stub(space_uid):
    """隔离 api.SpaceApi.parse_space_uid，返回与真实实现一致的二元组。"""

    return tuple(space_uid.split("__", 1))


def _cluster_record(registered_system):
    """构造 Doris 集群原始记录；公共集群形态覆盖 _default 注册来源。"""

    return {
        "cluster_type": DORIS_CLUSTER_TYPE,
        "auth_info": {"password": ""},
        "cluster_config": {
            "cluster_id": CLUSTER_ID,
            "cluster_name": "doris_matrix",
            "creator": "test_user",
            "registered_system": registered_system,
            "create_time": 1700000000,
            "last_modify_time": 1700000000,
            "custom_option": {},
        },
    }


@override_settings(
    MIDDLEWARE=(OVERRIDE_MIDDLEWARE,),
    BLUEKING_BK_BIZ_ID=BLUEKING_BK_BIZ_ID,
    IGNORE_IAM_PERMISSION=True,
)
class TestDorisVisibleMatrixApi(TestCase):
    """在 A/B 两个空间各发一次 HTTP 请求，覆盖私有与 _default 集群的配置组合。"""

    def setUp(self):
        patchers = [
            patch("apps.log_databus.handlers.storage.get_es_config", return_value=ES_CONFIG),
            # 接口级请求需通过业务权限校验；此处只放行权限，不改动业务判定逻辑
            patch("apps.iam.handlers.drf.ViewBusinessPermission.has_permission", return_value=True),
            patch("apps.log_databus.handlers.storage.FeatureToggleObject.switch", return_value=True),
            patch("apps.log_databus.handlers.storage.bk_biz_id_to_space_uid", side_effect=_space_uid_stub),
            # _match_biz_attr 会调 parse_space_uid（storage.py），真实实现落在
            # bkm_space/utils.py:59-60 的 api.SpaceApi.parse_space_uid，CI 无该服务。
            patch(
                "apps.log_databus.handlers.storage.parse_space_uid",
                side_effect=_parse_space_uid_stub,
            ),
            patch(
                "apps.log_databus.handlers.storage.SpaceApi.get_related_space",
                return_value=None,
            ),
            # OverrideMiddleware.process_request 会写 _local.request / _local.time_zone。
            # 用 patch(..., create=True) 记录用例开始前的原值，stop() 自动恢复；
            # 中间件随后写入的 admin 请求上下文不会泄漏到后续用例
            patch("apps.utils.local._local.request", None, create=True),
            patch("apps.utils.local._local.time_zone", None, create=True),
        ]
        for patcher in patchers:
            patcher.start()
            self.addCleanup(patcher.stop)
        # IndexSetHandler.get_index_set_for_storage 走真实实现，返回真实 QuerySet；
        # 测试库无索引集记录，is_use 为 False。

    def _query(self, custom_option, bk_biz_id, registered_system="bkdata"):
        """按 custom_option 形态构造记录，发起真实 HTTP 请求并返回 ID 集合。"""

        record = _cluster_record(registered_system)
        record["cluster_config"]["custom_option"] = custom_option

        def _query_cluster_info(__):
            return [parse_cluster_info(copy.deepcopy(record))]

        with patch(
            "apps.log_databus.handlers.storage.TransferApi.get_cluster_info",
            side_effect=_query_cluster_info,
        ):
            response = self.client.get(
                "/api/v1/databus/storage/cluster_groups/",
                {"bk_biz_id": bk_biz_id, "cluster_type": DORIS_CLUSTER_TYPE},
            )

        self.assertEqual(response.status_code, 200)
        content = json.loads(response.content)
        self.assertTrue(content["result"], content.get("message"))
        return [item["storage_cluster_id"] for item in content["data"]]

    def test_matrix_on_owner_space_and_project_space(self):
        """8行矩阵，前三是「未指定范围」的三种数据形态"""

        cases = [
            (
                "custom_option 为空字符串",
                "",
                False,
                False
            ),

            (
                "缺少 visible_config",
                {"bk_biz_id": OWNER_BIZ_ID},
                False,
                False
            ),

            (
                "visible_config 为空对象",
                {"bk_biz_id": OWNER_BIZ_ID, "visible_config": {}},
                False,
                False,
            ),

            (
                "指定业务名单为空",
                {
                    "bk_biz_id": OWNER_BIZ_ID,
                    "visible_config": {"visible_type": VisibleEnum.MULTI_BIZ.value, "visible_bk_biz": []},
                },
                False,
                False,
            ),

            (
                "业务属性条件为空",
                {
                    "bk_biz_id": OWNER_BIZ_ID,
                    "visible_config": {"visible_type": VisibleEnum.BIZ_ATTR.value, "bk_biz_labels": {}},
                },
                False,
                False,
            ),

            (
                "名单仅包含 B",
                {
                    "bk_biz_id": OWNER_BIZ_ID,
                    "visible_config": {
                        "visible_type": VisibleEnum.MULTI_BIZ.value,
                        "visible_bk_biz": [SPACE_BIZ_ID],
                        "bk_biz_labels": {},
                    },
                },
                False,
                True,
            ),

            (
                "属性仅 B 命中",
                {
                    "bk_biz_id": OWNER_BIZ_ID,
                    "visible_config": {
                        "visible_type": VisibleEnum.BIZ_ATTR.value,
                        "bk_biz_labels": {"space_type": ["bkci"]},
                    },
                },
                False,
                True,
            ),

            (
                "显式全部业务可见",
                {"bk_biz_id": OWNER_BIZ_ID, "visible_config": {"visible_type": VisibleEnum.ALL_BIZ.value}},
                True,
                True,
            )
        ]

        for name, custom_option, owner_expected, space_expected in cases:
            with self.subTest(case=name):
                self.assertCountEqual(
                    self._query(custom_option, OWNER_BIZ_ID),
                    [CLUSTER_ID] if owner_expected else [],
                )
                self.assertCountEqual(
                    self._query(custom_option, SPACE_BIZ_ID),
                    [CLUSTER_ID] if space_expected else [],
                )

    def test_matrix_on_default_public_clusters(self):
        """覆盖 registered_system=_default 的公共集群配置组合。

        filter_doris_cluster 末尾会把 custom_option["bk_biz_id"] 改写为
        settings.BLUEKING_BK_BIZ_ID，所以公共集群的归属业务恒为该值：
        这里 A 取 BLUEKING_BK_BIZ_ID，B 取 SPACE_BIZ_ID。
        current_biz 比对的就是这个归属业务，因此只对 A 放行、对 B 拒绝；
        写入侧禁止公共集群配置该组合，正是为了避免出现只有 A 可见的结果。
        """

        cases = [
            (
                "未指定范围",
                "",
                False,
                False
            ),

            (
                "名单仅包含 B",
                {
                    "bk_biz_id": BLUEKING_BK_BIZ_ID,
                    "visible_config": {
                        "visible_type": VisibleEnum.MULTI_BIZ.value,
                        "visible_bk_biz": [SPACE_BIZ_ID],
                        "bk_biz_labels": {},
                    },
                },
                False,
                True,
            ),

            (
                "显式全部业务可见",
                {"bk_biz_id": BLUEKING_BK_BIZ_ID, "visible_config": {"visible_type": VisibleEnum.ALL_BIZ.value}},
                True,
                True,
            ),

            (
                "current_biz（写入侧已拒绝的配置组合）",
                {
                    "bk_biz_id": BLUEKING_BK_BIZ_ID,
                    "visible_config": {"visible_type": VisibleEnum.CURRENT_BIZ.value},
                },
                True,
                False,
            )
        ]

        for name, custom_option, owner_expected, space_expected in cases:
            with self.subTest(case=name):
                self.assertCountEqual(
                    self._query(custom_option, BLUEKING_BK_BIZ_ID, REGISTERED_SYSTEM_DEFAULT),
                    [CLUSTER_ID] if owner_expected else [],
                )
                self.assertCountEqual(
                    self._query(custom_option, SPACE_BIZ_ID, REGISTERED_SYSTEM_DEFAULT),
                    [CLUSTER_ID] if space_expected else [],
                )

    def test_clearing_visible_config_makes_cluster_invisible_again(self):
        """以已配置与清空后两种数据形态分别请求，后者返回空集合。"""

        configured = {
            "bk_biz_id": OWNER_BIZ_ID,
            "visible_config": {
                "visible_type": VisibleEnum.MULTI_BIZ.value,
                "visible_bk_biz": [SPACE_BIZ_ID],
                "bk_biz_labels": {},
            },
        }
        cleared = {"bk_biz_id": OWNER_BIZ_ID}

        self.assertCountEqual(self._query(configured, SPACE_BIZ_ID), [CLUSTER_ID])
        self.assertCountEqual(self._query(cleared, SPACE_BIZ_ID), [])

    def test_current_tenant_matches_only_same_tenant(self):
        """候选列表：同租户命中，跨租户拒绝，全部业务可见不受影响。"""

        custom_option = {
            "bk_biz_id": OWNER_BIZ_ID,
            "visible_config": {"visible_type": VisibleEnum.CURRENT_TENANT.value},
        }
        with patch(
            "apps.log_databus.handlers.storage.get_request_tenant_id",
            return_value="tenant-a",
        ), patch(
            "apps.log_databus.handlers.storage.Space.get_tenant_id",
            return_value="tenant-a",
        ):
            self.assertCountEqual(self._query(custom_option, SPACE_BIZ_ID), [CLUSTER_ID])

        with patch(
            "apps.log_databus.handlers.storage.get_request_tenant_id",
            return_value="tenant-a",
        ), patch(
            "apps.log_databus.handlers.storage.Space.get_tenant_id",
            return_value="tenant-b",
        ):
            self.assertCountEqual(self._query(custom_option, SPACE_BIZ_ID), [])

        all_biz_option = {
            "bk_biz_id": OWNER_BIZ_ID,
            "visible_config": {"visible_type": VisibleEnum.ALL_BIZ.value},
        }
        with patch(
            "apps.log_databus.handlers.storage.get_request_tenant_id",
            return_value="tenant-a",
        ), patch(
            "apps.log_databus.handlers.storage.Space.get_tenant_id",
            return_value="tenant-b",
        ):
            self.assertCountEqual(self._query(all_biz_option, SPACE_BIZ_ID), [CLUSTER_ID])

    def test_explicit_all_biz_wins_over_legacy_root_list(self):
        """候选列表：旧根级名单与显式 all_biz 共存时，A/B 两个空间都能选到。"""

        custom_option = {
            "bk_biz_id": OWNER_BIZ_ID,
            "visible_bk_biz": [SPACE_BIZ_ID],
            "visible_config": {"visible_type": VisibleEnum.ALL_BIZ.value},
        }
        self.assertCountEqual(self._query(custom_option, OWNER_BIZ_ID), [CLUSTER_ID])
        self.assertCountEqual(self._query(custom_option, SPACE_BIZ_ID), [CLUSTER_ID])
