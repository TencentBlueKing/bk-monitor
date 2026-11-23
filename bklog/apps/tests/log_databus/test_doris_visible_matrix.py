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

# 共用的 Doris 集群原始记录样例：101 未配置可见范围，102 仅空间 B 可见。
ACCEPTANCE_CLUSTERS = [
    {
        "cluster_type": DORIS_CLUSTER_TYPE,
        "auth_info": {"password": ""},
        "cluster_config": {
            "cluster_id": 101,
            "cluster_name": "doris_unconfigured",
            "creator": "test_user",
            "registered_system": REGISTERED_SYSTEM_DEFAULT,
            "create_time": 1700000000,
            "last_modify_time": 1700000000,
            "custom_option": "",
        },
    },
    {
        "cluster_type": DORIS_CLUSTER_TYPE,
        "auth_info": {"password": ""},
        "cluster_config": {
            "cluster_id": 102,
            "cluster_name": "doris_shared_with_b",
            "creator": "test_user",
            "registered_system": "bkdata",
            "create_time": 1700000000,
            "last_modify_time": 1700000000,
            "custom_option": {
                "bk_biz_id": 201,
                "visible_config": {
                    "visible_type": VisibleEnum.MULTI_BIZ.value,
                    "visible_bk_biz": [SPACE_BIZ_ID],
                    "bk_biz_labels": {},
                },
            },
        },
    },
]


def _space_uid_stub(bk_biz_id):
    """隔离 Metadata 空间接口；真实实现见 bkm_space/utils.py:37-56。"""

    return f"bkci__{-int(bk_biz_id)}" if int(bk_biz_id) < 0 else f"bkcc__{bk_biz_id}"


def _parse_space_uid_stub(space_uid):
    """隔离 api.SpaceApi.parse_space_uid，返回与真实实现一致的二元组。"""

    return tuple(space_uid.split("__", 1))


def _cluster_record(registered_system, custom_option=None, cluster_id=CLUSTER_ID):
    """构造 Doris 集群原始记录；公共集群形态覆盖 _default 注册来源。"""

    return {
        "cluster_type": DORIS_CLUSTER_TYPE,
        "auth_info": {"password": ""},
        "cluster_config": {
            "cluster_id": cluster_id,
            "cluster_name": "doris_matrix",
            "creator": "test_user",
            "registered_system": registered_system,
            "create_time": 1700000000,
            "last_modify_time": 1700000000,
            "custom_option": {} if custom_option is None else custom_option,
        },
    }


@override_settings(
    MIDDLEWARE=(OVERRIDE_MIDDLEWARE,),
    BLUEKING_BK_BIZ_ID=BLUEKING_BK_BIZ_ID,
    IGNORE_IAM_PERMISSION=True,
)
class TestDorisVisibleMatrixApi(TestCase):
    """参数化规则矩阵与完整 API 回归，共用同一份原始样例与请求夹具。"""

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
            # 用 patch(..., create=True) 记录调用开始前的原值，stop() 自动恢复；
            # 中间件随后写入的 admin 请求上下文不会泄漏到后续用例
            patch("apps.utils.local._local.request", None, create=True),
            patch("apps.utils.local._local.time_zone", None, create=True),
        ]
        for patcher in patchers:
            patcher.start()
            self.addCleanup(patcher.stop)
        # IndexSetHandler.get_index_set_for_storage 走真实实现，返回真实 QuerySet；
        # 测试库无索引集记录，is_use 为 False。

    def _query_records(self, records, bk_biz_id):
        """按给定原始记录发起真实 HTTP 请求，返回响应 data 中的集群 ID 集合。"""

        parsed_records = [parse_cluster_info(copy.deepcopy(record)) for record in records]

        def _query_cluster_info(__):
            return copy.deepcopy(parsed_records)

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

    def _query(self, custom_option, bk_biz_id, registered_system="bkdata"):
        """按单条记录的 custom_option 形态请求，返回集群 ID 集合。"""

        return self._query_records([_cluster_record(registered_system, custom_option)], bk_biz_id)

    def test_visible_type_matrix(self):
        """一套参数化矩阵覆盖私有与 _default 集群的全部可见类型组合。"""

        cases = [
            # name, custom_option, registered_system, owner_biz, owner_expected, space_expected
            ("custom_option 为空字符串", "", "bkdata", OWNER_BIZ_ID, False, False),
            ("缺少 visible_config", {"bk_biz_id": OWNER_BIZ_ID}, "bkdata", OWNER_BIZ_ID, False, False),
            (
                "visible_config 为空对象",
                {"bk_biz_id": OWNER_BIZ_ID, "visible_config": {}},
                "bkdata",
                OWNER_BIZ_ID,
                False,
                False,
            ),
            (
                "指定业务名单为空",
                {
                    "bk_biz_id": OWNER_BIZ_ID,
                    "visible_config": {"visible_type": VisibleEnum.MULTI_BIZ.value, "visible_bk_biz": []},
                },
                "bkdata",
                OWNER_BIZ_ID,
                False,
                False,
            ),
            (
                "业务属性条件为空",
                {
                    "bk_biz_id": OWNER_BIZ_ID,
                    "visible_config": {"visible_type": VisibleEnum.BIZ_ATTR.value, "bk_biz_labels": {}},
                },
                "bkdata",
                OWNER_BIZ_ID,
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
                "bkdata",
                OWNER_BIZ_ID,
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
                "bkdata",
                OWNER_BIZ_ID,
                False,
                True,
            ),
            (
                "显式全部业务可见",
                {"bk_biz_id": OWNER_BIZ_ID, "visible_config": {"visible_type": VisibleEnum.ALL_BIZ.value}},
                "bkdata",
                OWNER_BIZ_ID,
                True,
                True,
            ),
            ("公共集群未指定范围", "", REGISTERED_SYSTEM_DEFAULT, BLUEKING_BK_BIZ_ID, False, False),
            (
                "公共集群名单仅包含 B",
                {
                    "bk_biz_id": BLUEKING_BK_BIZ_ID,
                    "visible_config": {
                        "visible_type": VisibleEnum.MULTI_BIZ.value,
                        "visible_bk_biz": [SPACE_BIZ_ID],
                        "bk_biz_labels": {},
                    },
                },
                REGISTERED_SYSTEM_DEFAULT,
                BLUEKING_BK_BIZ_ID,
                False,
                True,
            ),
            (
                "公共集群显式全部业务可见",
                {"bk_biz_id": BLUEKING_BK_BIZ_ID, "visible_config": {"visible_type": VisibleEnum.ALL_BIZ.value}},
                REGISTERED_SYSTEM_DEFAULT,
                BLUEKING_BK_BIZ_ID,
                True,
                True,
            ),
            (
                "公共集群 current_biz（归属业务改写为蓝鲸业务）",
                {
                    "bk_biz_id": BLUEKING_BK_BIZ_ID,
                    "visible_config": {"visible_type": VisibleEnum.CURRENT_BIZ.value},
                },
                REGISTERED_SYSTEM_DEFAULT,
                BLUEKING_BK_BIZ_ID,
                True,
                False,
            ),
            (
                "旧根级名单与显式 all_biz 共存",
                {
                    "bk_biz_id": OWNER_BIZ_ID,
                    "visible_bk_biz": [SPACE_BIZ_ID],
                    "visible_config": {"visible_type": VisibleEnum.ALL_BIZ.value},
                },
                "bkdata",
                OWNER_BIZ_ID,
                True,
                True,
            ),
        ]

        for name, custom_option, registered_system, owner_biz, owner_expected, space_expected in cases:
            with self.subTest(case=name):
                self.assertCountEqual(
                    self._query(custom_option, owner_biz, registered_system),
                    [CLUSTER_ID] if owner_expected else [],
                )
                self.assertCountEqual(
                    self._query(custom_option, SPACE_BIZ_ID, registered_system),
                    [CLUSTER_ID] if space_expected else [],
                )

    def test_original_sample_returns_only_configured(self):
        """当前版本的原始样例回归：101 未配置不可见，仅返回已配置的 102。"""

        self.assertCountEqual(
            self._query_records(copy.deepcopy(ACCEPTANCE_CLUSTERS), SPACE_BIZ_ID),
            [102],
        )

        empty_object_records = copy.deepcopy(ACCEPTANCE_CLUSTERS)
        empty_object_records[0]["cluster_config"]["custom_option"] = {}
        self.assertCountEqual(self._query_records(empty_object_records, SPACE_BIZ_ID), [102])

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

    def test_malformed_biz_attr_does_not_break_candidate_list(self):
        """坏配置与正常集群同批时接口成功，只返回正常集群。"""

        records = copy.deepcopy(ACCEPTANCE_CLUSTERS)
        records.append(
            _cluster_record(
                "bkdata",
                {
                    "bk_biz_id": 201,
                    "visible_config": {
                        "visible_type": VisibleEnum.BIZ_ATTR.value,
                        "bk_biz_labels": {"space_type": []},
                    },
                },
                cluster_id=103,
            )
        )
        with patch(
            "apps.log_databus.handlers.storage.SpaceApi.get_related_space",
            side_effect=AssertionError("should not be called"),
        ):
            result = self._query_records(records, SPACE_BIZ_ID)

        self.assertCountEqual(result, [102])

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
