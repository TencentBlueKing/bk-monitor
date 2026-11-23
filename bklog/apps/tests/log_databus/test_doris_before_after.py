import copy
import json
from unittest.mock import patch

from django.test import TestCase, override_settings

from apps.api.modules.transfer import parse_cluster_info
from apps.log_databus.constants import DORIS_CLUSTER_TYPE, REGISTERED_SYSTEM_DEFAULT, VisibleEnum
from apps.log_databus.handlers.storage import StorageHandler
from apps.log_search.models import LogIndexSet


BLUEKING_BK_BIZ_ID = 2
TARGET_SPACE_ID = -101
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

# Doris 集群原始记录样例
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
                    "visible_bk_biz": [-101],
                    "bk_biz_labels": {},
                },
            },
        },
    },
]


def _space_uid_stub(bk_biz_id):
    """隔离 api.SpaceApi.get_space_detail 的外部调用。

    这里只关心 cluster_groups 返回的 ID 集合，空间映射用固定串即可；
    IndexSetHandler 使用真实 QuerySet，业务判定逻辑保持原样。
    """

    return f"bkci__{-int(bk_biz_id)}" if int(bk_biz_id) < 0 else f"bkcc__{bk_biz_id}"


def _no_index_sets(__):
    """用真实 QuerySet 满足 IndexSetHandler 的返回契约。"""

    return LogIndexSet.objects.none()


def _legacy_backfill_records():
    """复现改动前 filter_doris_cluster 对未配置集群的两处默认回填。

    只变换测试内的纯字典：公共集群回填 all_biz，私有集群回填 current_biz。
    变换后的记录仍走当前的归一化与过滤链路，唯一变量是可见性判定语义。
    """

    records = copy.deepcopy(ACCEPTANCE_CLUSTERS)
    for record in records:
        config = record["cluster_config"]
        custom_option = config.get("custom_option") or {}
        if not isinstance(custom_option, dict):
            custom_option = {}
        if not custom_option.get("visible_config"):
            visible_type = (
                VisibleEnum.ALL_BIZ.value
                if config.get("registered_system") == REGISTERED_SYSTEM_DEFAULT
                else VisibleEnum.CURRENT_BIZ.value
            )
            custom_option["visible_config"] = {"visible_type": visible_type}
        config["custom_option"] = custom_option
    return records


def _empty_object_records():
    """把第一条记录的 custom_option 由空串改为空对象。"""

    records = copy.deepcopy(ACCEPTANCE_CLUSTERS)
    records[0]["cluster_config"]["custom_option"] = {}
    return records


@override_settings(
    MIDDLEWARE=(OVERRIDE_MIDDLEWARE,),
    BLUEKING_BK_BIZ_ID=BLUEKING_BK_BIZ_ID,
    IGNORE_IAM_PERMISSION=True,
)
class TestDorisClusterGroupsBeforeAfter(TestCase):
    """按三种 custom_option 数据态分别断言返回的集群 ID 集合。"""

    def setUp(self):
        patchers = [
            patch("apps.log_databus.handlers.storage.get_es_config", return_value=ES_CONFIG),
            patch("apps.iam.handlers.drf.ViewBusinessPermission.has_permission", return_value=True),
            patch("apps.log_databus.handlers.storage.FeatureToggleObject.switch", return_value=True),
            patch("apps.log_databus.handlers.storage.bk_biz_id_to_space_uid", side_effect=_space_uid_stub),
            patch(
                "apps.log_search.handlers.index_set.IndexSetHandler.get_index_set_for_storage",
                side_effect=_no_index_sets,
            ),
            # OverrideMiddleware.process_request 会写 _local.request / _local.time_zone。
            # 用 patch(..., create=True) 记录调用开始前的原值，stop() 自动恢复。
            patch("apps.utils.local._local.request", None, create=True),
            patch("apps.utils.local._local.time_zone", None, create=True),
        ]
        for patcher in patchers:
            patcher.start()
            self.addCleanup(patcher.stop)

    def _cluster_ids(self, records):
        """按给定数据形态请求 cluster_groups 并返回响应 data 中的集群 ID 集合。"""

        def _query_cluster_info(__):
            return [parse_cluster_info(copy.deepcopy(record)) for record in records]

        with patch(
            "apps.log_databus.handlers.storage.TransferApi.get_cluster_info",
            side_effect=_query_cluster_info,
        ):
            response = self.client.get(
                "/api/v1/databus/storage/cluster_groups/",
                {"bk_biz_id": TARGET_SPACE_ID, "cluster_type": DORIS_CLUSTER_TYPE},
            )

        self.assertEqual(response.status_code, 200)
        content = json.loads(response.content)
        self.assertTrue(content["result"], content.get("message"))
        return [item["storage_cluster_id"] for item in content["data"]]

    def _legacy_cluster_ids(self, records):
        """按改动前的语义装配响应：归一化与过滤共用当前实现，判定不传 cluster_type。"""

        parsed = [parse_cluster_info(copy.deepcopy(record)) for record in records]
        handler = StorageHandler()
        groups = StorageHandler.filter_cluster_groups(
            parsed,
            TARGET_SPACE_ID,
            is_default=True,
            enable_archive=False,
            post_visible=True,
        )
        return [
            cluster["cluster_config"]["cluster_id"]
            for cluster in groups
            if handler.can_visible(
                TARGET_SPACE_ID,
                cluster["cluster_config"]["custom_option"],
                cluster["cluster_config"]["registered_system"],
            )
        ]

    def test_same_sample_before_and_after_fix(self):
        """同一份脱敏样例：改动前返回 101、102，改动后仅返回 102。"""

        before_ids = self._legacy_cluster_ids(_legacy_backfill_records())
        after_ids = self._cluster_ids(copy.deepcopy(ACCEPTANCE_CLUSTERS))

        self.assertCountEqual(before_ids, [101, 102])
        self.assertCountEqual(after_ids, [102])

    def test_empty_object_custom_option_returns_only_configured(self):
        """把第一条 custom_option 改为空对象后，仍仅返回 102。"""

        self.assertCountEqual(self._cluster_ids(_empty_object_records()), [102])
