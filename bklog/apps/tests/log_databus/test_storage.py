"""
Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
License for BK-LOG 蓝鲸日志平台:
--------------------------------------------------------------------
Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all copies or substantial
portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN
NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
We undertake not to change the open source license (MIT license) applicable to the current version of
the project delivered to anyone in the future.
"""

import copy
from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings

from apps.log_databus.constants import (
    ClusterTypeEnum,
    DORIS_CLUSTER_TYPE,
    REGISTERED_SYSTEM_DEFAULT,
    STORAGE_CLUSTER_TYPE,
    VisibleEnum,
)
from apps.exceptions import ValidationError
from apps.log_databus.exceptions import (
    StorageNotExistException,
    StorageNotPermissionException,
)
from apps.log_databus.handlers.collector.base import CollectorHandler
from apps.log_databus.handlers.etl_storage import EtlStorage
from apps.log_databus.handlers.storage import StorageHandler
from apps.log_databus.serializers import DorisVisibleConfigUpdateSerializer
from apps.log_databus.utils.storage_config import build_storage_retention_config, get_storage_retention
from apps.log_search.handlers.index_set import IndexSetHandler
from apps.log_search.models import Scenario

BLUEKING_BK_BIZ_ID = 2
OWNER_BIZ = 5
TARGET_BIZ = 100

ES_CONFIG = {
    "ES_PUBLIC_STORAGE_DURATION": 7,
    "ES_PRIVATE_STORAGE_DURATION": 7,
    "ES_REPLICAS": 0,
    "ES_SHARDS": 3,
    "ES_SHARDS_MAX": 64,
}


def _fake_index_sets():
    """构造一个 .filter(...).exists() 恒为 False 的伪 queryset"""
    qs = MagicMock()
    qs.filter.return_value.exists.return_value = False
    return qs


def _doris_cluster_obj(registered_system="other", custom_option=None, cluster_id=10):
    return {
        "cluster_type": DORIS_CLUSTER_TYPE,
        "auth_info": {"password": "secret"},
        "cluster_config": {
            "cluster_id": cluster_id,
            "cluster_name": "doris_cluster",
            "creator": "admin",
            "registered_system": registered_system,
            "create_time": 1700000000,
            "last_modify_time": 1700000000,
            "custom_option": custom_option if custom_option is not None else {},
        },
    }


class TestCanVisible(TestCase):
    """StorageHandler.can_visible 可见范围判定"""

    def setUp(self):
        self.handler = StorageHandler()

    def test_all_biz_always_visible(self):
        custom_option = {"bk_biz_id": OWNER_BIZ, "visible_config": {"visible_type": VisibleEnum.ALL_BIZ.value}}
        self.assertTrue(self.handler.can_visible(TARGET_BIZ, custom_option, "other"))

    def test_owner_biz_visible(self):
        custom_option = {"bk_biz_id": OWNER_BIZ, "visible_config": {"visible_type": VisibleEnum.CURRENT_BIZ.value}}
        self.assertTrue(self.handler.can_visible(OWNER_BIZ, custom_option, "other"))

    def test_current_biz_not_visible_to_others(self):
        custom_option = {"bk_biz_id": OWNER_BIZ, "visible_config": {"visible_type": VisibleEnum.CURRENT_BIZ.value}}
        self.assertFalse(self.handler.can_visible(TARGET_BIZ, custom_option, "other"))

    def test_multi_biz_hit_int_list(self):
        custom_option = {
            "bk_biz_id": OWNER_BIZ,
            "visible_config": {"visible_type": VisibleEnum.MULTI_BIZ.value, "visible_bk_biz": [TARGET_BIZ, 101]},
        }
        self.assertTrue(self.handler.can_visible(TARGET_BIZ, custom_option, "other"))

    def test_multi_biz_hit_dict_list(self):
        custom_option = {
            "bk_biz_id": OWNER_BIZ,
            "visible_config": {
                "visible_type": VisibleEnum.MULTI_BIZ.value,
                "visible_bk_biz": [{"bk_biz_id": TARGET_BIZ}],
            },
        }
        self.assertTrue(self.handler.can_visible(TARGET_BIZ, custom_option, "other"))

    def test_multi_biz_miss(self):
        custom_option = {
            "bk_biz_id": OWNER_BIZ,
            "visible_config": {"visible_type": VisibleEnum.MULTI_BIZ.value, "visible_bk_biz": [101, 102]},
        }
        self.assertFalse(self.handler.can_visible(TARGET_BIZ, custom_option, "other"))

    def test_legacy_no_visible_config(self):
        # 老数据没有 visible_config，非归属业务不可见
        custom_option = {"bk_biz_id": OWNER_BIZ}
        self.assertFalse(self.handler.can_visible(TARGET_BIZ, custom_option, "other"))
        self.assertTrue(self.handler.can_visible(OWNER_BIZ, custom_option, "other"))


@override_settings(BLUEKING_BK_BIZ_ID=BLUEKING_BK_BIZ_ID)
class TestFilterDorisCluster(TestCase):
    """StorageHandler.filter_doris_cluster 回填 visible_editable / visible_config"""

    def setUp(self):
        patcher_es = patch("apps.log_databus.handlers.storage.get_es_config", return_value=ES_CONFIG)
        patcher_idx = patch(
            "apps.log_search.handlers.index_set.IndexSetHandler.get_index_set_for_storage",
            return_value=_fake_index_sets(),
        )
        self.addCleanup(patcher_es.stop)
        self.addCleanup(patcher_idx.stop)
        patcher_es.start()
        patcher_idx.start()

    @staticmethod
    def _get_cluster_groups(cluster_obj):
        with patch(
            "apps.log_databus.handlers.storage.FeatureToggleObject.switch", return_value=True
        ), patch("apps.log_databus.handlers.storage.MultiExecuteFunc") as mock_multi_execute:
            mock_multi_execute.return_value.run.return_value = {DORIS_CLUSTER_TYPE: [cluster_obj]}
            return StorageHandler().get_cluster_groups(
                TARGET_BIZ,
                cluster_query_type=ClusterTypeEnum.DORIS.value,
            )

    def test_legacy_public_cluster_without_visible_config_remains_visible(self):
        cluster_obj = _doris_cluster_obj(
            registered_system=REGISTERED_SYSTEM_DEFAULT,
            custom_option={},
        )

        result = self._get_cluster_groups(cluster_obj)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["storage_cluster_id"], 10)
        self.assertTrue(result[0]["is_platform"])
        self.assertEqual(
            cluster_obj["cluster_config"]["custom_option"]["visible_config"],
            {"visible_type": VisibleEnum.ALL_BIZ.value},
        )

    def test_public_cluster_with_explicit_all_biz_is_visible_to_other_biz(self):
        cluster_obj = _doris_cluster_obj(
            registered_system=REGISTERED_SYSTEM_DEFAULT,
            custom_option={"visible_config": {"visible_type": VisibleEnum.ALL_BIZ.value}},
        )

        result = self._get_cluster_groups(cluster_obj)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["storage_cluster_id"], 10)
        self.assertTrue(result[0]["is_platform"])

    def test_private_cluster_owned_by_current_biz_remains_visible(self):
        cluster_obj = _doris_cluster_obj(
            registered_system="bkdata",
            custom_option={
                "bk_biz_id": TARGET_BIZ,
                "visible_config": {"visible_type": VisibleEnum.CURRENT_BIZ.value},
            },
        )

        result = self._get_cluster_groups(cluster_obj)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["bk_biz_id"], TARGET_BIZ)
        self.assertFalse(result[0]["is_platform"])

    def test_private_cluster_is_hidden_from_other_biz(self):
        cluster_obj = _doris_cluster_obj(
            registered_system="bkdata",
            custom_option={
                "bk_biz_id": OWNER_BIZ,
                "visible_config": {"visible_type": VisibleEnum.CURRENT_BIZ.value},
            },
        )

        self.assertEqual(self._get_cluster_groups(cluster_obj), [])

    def test_public_cluster_editable_only_for_blueking(self):
        cluster_obj = _doris_cluster_obj(
            registered_system=REGISTERED_SYSTEM_DEFAULT,
            custom_option={"visible_config": {"visible_type": VisibleEnum.ALL_BIZ.value}},
        )
        # 蓝鲸业务可编辑可见范围
        is_append, obj = StorageHandler.filter_doris_cluster(
            BLUEKING_BK_BIZ_ID, is_default=True, post_visible=True, cluster_obj=copy.deepcopy(cluster_obj)
        )
        self.assertTrue(is_append)
        self.assertFalse(obj["is_editable"])
        self.assertTrue(obj["visible_editable"])

        # 非蓝鲸业务不可编辑
        is_append, obj = StorageHandler.filter_doris_cluster(
            TARGET_BIZ, is_default=True, post_visible=True, cluster_obj=copy.deepcopy(cluster_obj)
        )
        self.assertTrue(is_append)
        self.assertFalse(obj["visible_editable"])

    def test_private_cluster_editable_for_owner(self):
        cluster_obj = _doris_cluster_obj(
            registered_system="other",
            custom_option={"bk_biz_id": OWNER_BIZ, "visible_config": {"visible_type": VisibleEnum.CURRENT_BIZ.value}},
        )
        is_append, obj = StorageHandler.filter_doris_cluster(
            OWNER_BIZ, is_default=True, post_visible=True, cluster_obj=copy.deepcopy(cluster_obj)
        )
        self.assertTrue(is_append)
        self.assertFalse(obj["is_editable"])
        self.assertTrue(obj["visible_editable"])

    def test_private_cluster_legacy_visible_bk_biz_compat(self):
        # 老可见范围配置 visible_bk_biz 会被转换成 multi_biz visible_config
        cluster_obj = _doris_cluster_obj(
            registered_system="other",
            custom_option={"bk_biz_id": OWNER_BIZ, "visible_bk_biz": [TARGET_BIZ]},
        )
        is_append, obj = StorageHandler.filter_doris_cluster(
            OWNER_BIZ, is_default=True, post_visible=True, cluster_obj=copy.deepcopy(cluster_obj)
        )
        self.assertTrue(is_append)
        visible_config = obj["cluster_config"]["custom_option"]["visible_config"]
        self.assertEqual(visible_config["visible_type"], VisibleEnum.MULTI_BIZ.value)
        self.assertEqual(visible_config["visible_bk_biz"][0]["bk_biz_id"], TARGET_BIZ)


@override_settings(BLUEKING_BK_BIZ_ID=BLUEKING_BK_BIZ_ID)
class TestFilterDorisClusterSetupConfig(TestCase):
    """
    doris 集群必须下发 setup_config.retention_days_max，
    否则前端取不到上限会回退到写死的 7 天（最大自定义天数为 7）
    """

    def setUp(self):
        patcher_es = patch("apps.log_databus.handlers.storage.get_es_config", return_value=ES_CONFIG)
        patcher_idx = patch(
            "apps.log_search.handlers.index_set.IndexSetHandler.get_index_set_for_storage",
            return_value=_fake_index_sets(),
        )
        self.addCleanup(patcher_es.stop)
        self.addCleanup(patcher_idx.stop)
        patcher_es.start()
        patcher_idx.start()

    @staticmethod
    def _filter(bk_biz_id, cluster_obj):
        _, obj = StorageHandler.filter_doris_cluster(
            bk_biz_id, is_default=True, post_visible=True, cluster_obj=copy.deepcopy(cluster_obj)
        )
        return obj["cluster_config"]["custom_option"]["setup_config"]

    def test_public_cluster_without_setup_config_falls_back_to_es_public_duration(self):
        setup_config = self._filter(
            BLUEKING_BK_BIZ_ID,
            _doris_cluster_obj(
                registered_system=REGISTERED_SYSTEM_DEFAULT,
                custom_option={"visible_config": {"visible_type": VisibleEnum.ALL_BIZ.value}},
            ),
        )
        self.assertEqual(setup_config["retention_days_max"], ES_CONFIG["ES_PUBLIC_STORAGE_DURATION"])
        self.assertEqual(setup_config["retention_days_default"], ES_CONFIG["ES_PUBLIC_STORAGE_DURATION"])

    def test_private_cluster_without_setup_config_falls_back_to_es_public_duration(self):
        setup_config = self._filter(
            OWNER_BIZ,
            _doris_cluster_obj(
                registered_system="other",
                custom_option={
                    "bk_biz_id": OWNER_BIZ,
                    "visible_config": {"visible_type": VisibleEnum.CURRENT_BIZ.value},
                },
            ),
        )
        self.assertEqual(setup_config["retention_days_max"], ES_CONFIG["ES_PUBLIC_STORAGE_DURATION"])

    def test_empty_setup_config_from_metadata_still_gets_defaults(self):
        """metadata 侧存了空字典时，缺省值不能被 custom_option 的整体覆盖冲掉"""
        setup_config = self._filter(
            OWNER_BIZ,
            _doris_cluster_obj(
                registered_system="other",
                custom_option={
                    "bk_biz_id": OWNER_BIZ,
                    "setup_config": {},
                    "visible_config": {"visible_type": VisibleEnum.CURRENT_BIZ.value},
                },
            ),
        )
        self.assertEqual(setup_config["retention_days_max"], ES_CONFIG["ES_PUBLIC_STORAGE_DURATION"])

    def test_admin_configured_setup_config_is_not_overwritten(self):
        setup_config = self._filter(
            OWNER_BIZ,
            _doris_cluster_obj(
                registered_system="other",
                custom_option={
                    "bk_biz_id": OWNER_BIZ,
                    "setup_config": {"retention_days_max": 90, "retention_days_default": 30},
                    "visible_config": {"visible_type": VisibleEnum.CURRENT_BIZ.value},
                },
            ),
        )
        self.assertEqual(setup_config["retention_days_max"], 90)
        self.assertEqual(setup_config["retention_days_default"], 30)

    def test_partially_configured_setup_config_only_fills_missing_keys(self):
        setup_config = self._filter(
            OWNER_BIZ,
            _doris_cluster_obj(
                registered_system="other",
                custom_option={
                    "bk_biz_id": OWNER_BIZ,
                    "setup_config": {"retention_days_max": 90},
                    "visible_config": {"visible_type": VisibleEnum.CURRENT_BIZ.value},
                },
            ),
        )
        self.assertEqual(setup_config["retention_days_max"], 90)
        self.assertEqual(setup_config["retention_days_default"], ES_CONFIG["ES_PUBLIC_STORAGE_DURATION"])

    def test_does_not_inject_es_only_fields(self):
        """doris 无副本/分片概念，不应照搬 ES 的 setup_config 字段"""
        setup_config = self._filter(
            OWNER_BIZ,
            _doris_cluster_obj(
                registered_system="other",
                custom_option={
                    "bk_biz_id": OWNER_BIZ,
                    "visible_config": {"visible_type": VisibleEnum.CURRENT_BIZ.value},
                },
            ),
        )
        es_only_fields = (
            "number_of_replicas_max",
            "number_of_replicas_default",
            "es_shards_default",
            "es_shards_max",
        )
        for es_only_field in es_only_fields:
            self.assertNotIn(es_only_field, setup_config)


@override_settings(BLUEKING_BK_BIZ_ID=BLUEKING_BK_BIZ_ID)
class TestUpdateVisibleConfig(TestCase):
    """StorageHandler.update_visible_config 仅更新 visible_config"""

    def _run_update(self, cluster_info, params):
        with (
            patch("apps.log_databus.handlers.storage.TransferApi") as mock_api,
            patch("apps.log_databus.handlers.storage.user_operation_record") as mock_record,
            patch("apps.log_databus.handlers.storage.get_request_username", return_value="tester"),
        ):
            mock_api.get_cluster_info.return_value = cluster_info
            mock_api.modify_cluster_info.return_value = {"cluster_config": {}, "auth_info": {"password": ""}}
            result = StorageHandler(params["cluster_id"]).update_visible_config(params)
            return mock_api, mock_record, result

    def test_update_preserves_other_custom_option(self):
        cluster_info = [
            {
                "cluster_config": {
                    "registered_system": "other",
                    "custom_option": {
                        "bk_biz_id": OWNER_BIZ,
                        "admin": ["admin"],
                        "source_type": "other",
                        "description": "keep me",
                        "visible_config": {"visible_type": VisibleEnum.CURRENT_BIZ.value},
                    },
                }
            }
        ]
        params = {
            "cluster_id": 10,
            "bk_biz_id": OWNER_BIZ,
            "visible_config": {"visible_type": VisibleEnum.MULTI_BIZ.value, "visible_bk_biz": [TARGET_BIZ]},
        }
        mock_api, mock_record, _ = self._run_update(cluster_info, params)

        mock_api.modify_cluster_info.assert_called_once()
        modify_params = mock_api.modify_cluster_info.call_args[0][0]
        self.assertEqual(modify_params["cluster_type"], DORIS_CLUSTER_TYPE)
        # 不传 auth_info：metadata #11701 缺省保留原凭据；Doris 查找已按 cluster_type 放宽
        self.assertNotIn("auth_info", modify_params)
        self.assertNotIn("registered_system", modify_params)
        custom_option = modify_params["custom_option"]
        # 只改 visible_config
        self.assertEqual(custom_option["visible_config"], params["visible_config"])
        # 其余字段保留
        self.assertEqual(custom_option["admin"], ["admin"])
        self.assertEqual(custom_option["description"], "keep me")
        self.assertEqual(custom_option["source_type"], "other")
        self.assertEqual(custom_option["bk_biz_id"], OWNER_BIZ)
        # 无连通性检测相关字段
        self.assertNotIn("hot_warm_config", modify_params)
        self.assertNotIn("setup_config", modify_params)
        mock_record.delay.assert_called_once()

    def test_cluster_not_exist_raises(self):
        params = {"cluster_id": 10, "bk_biz_id": OWNER_BIZ, "visible_config": {"visible_type": "all_biz"}}
        with self.assertRaises(StorageNotExistException):
            self._run_update([], params)

    def test_private_cluster_wrong_biz_forbidden(self):
        cluster_info = [
            {
                "cluster_config": {
                    "registered_system": "other",
                    "custom_option": {"bk_biz_id": OWNER_BIZ, "visible_config": {"visible_type": "current_biz"}},
                }
            }
        ]
        params = {"cluster_id": 10, "bk_biz_id": 999, "visible_config": {"visible_type": "all_biz"}}
        with self.assertRaises(StorageNotPermissionException):
            self._run_update(cluster_info, params)

    def test_public_cluster_non_blueking_forbidden(self):
        cluster_info = [
            {
                "cluster_config": {
                    "registered_system": REGISTERED_SYSTEM_DEFAULT,
                    "custom_option": {"bk_biz_id": BLUEKING_BK_BIZ_ID, "visible_config": {"visible_type": "all_biz"}},
                }
            }
        ]
        params = {"cluster_id": 10, "bk_biz_id": TARGET_BIZ, "visible_config": {"visible_type": "all_biz"}}
        with self.assertRaises(StorageNotPermissionException):
            self._run_update(cluster_info, params)

    @staticmethod
    def _private_cluster_info(custom_option_extra=None):
        custom_option = {
            "bk_biz_id": OWNER_BIZ,
            "admin": ["admin"],
            "source_type": "other",
            "description": "keep me",
            "visible_config": {"visible_type": VisibleEnum.CURRENT_BIZ.value},
        }
        custom_option.update(custom_option_extra or {})
        return [{"cluster_config": {"registered_system": "other", "custom_option": custom_option}}]

    def test_setup_config_is_written_when_provided(self):
        params = {
            "cluster_id": 10,
            "bk_biz_id": OWNER_BIZ,
            "visible_config": {"visible_type": VisibleEnum.ALL_BIZ.value},
            "setup_config": {"retention_days_max": 30, "retention_days_default": 14},
        }
        mock_api, _, _ = self._run_update(self._private_cluster_info(), params)

        custom_option = mock_api.modify_cluster_info.call_args[0][0]["custom_option"]
        self.assertEqual(custom_option["setup_config"], params["setup_config"])
        # 其余字段仍然保留
        self.assertEqual(custom_option["description"], "keep me")

    def test_setup_config_merges_by_key(self):
        """只传部分键时，已有的其它键需保留"""
        params = {
            "cluster_id": 10,
            "bk_biz_id": OWNER_BIZ,
            "visible_config": {"visible_type": VisibleEnum.ALL_BIZ.value},
            "setup_config": {"retention_days_max": 60, "retention_days_default": 30},
        }
        cluster_info = self._private_cluster_info(
            {"setup_config": {"retention_days_max": 7, "retention_days_default": 7, "legacy_key": "keep"}}
        )
        mock_api, _, _ = self._run_update(cluster_info, params)

        setup_config = mock_api.modify_cluster_info.call_args[0][0]["custom_option"]["setup_config"]
        self.assertEqual(setup_config["retention_days_max"], 60)
        self.assertEqual(setup_config["retention_days_default"], 30)
        self.assertEqual(setup_config["legacy_key"], "keep")

    def test_existing_setup_config_kept_when_not_provided(self):
        """未传 setup_config 时不能清掉管理员已配置的上限"""
        params = {
            "cluster_id": 10,
            "bk_biz_id": OWNER_BIZ,
            "visible_config": {"visible_type": VisibleEnum.ALL_BIZ.value},
        }
        cluster_info = self._private_cluster_info({"setup_config": {"retention_days_max": 90}})
        mock_api, _, _ = self._run_update(cluster_info, params)

        custom_option = mock_api.modify_cluster_info.call_args[0][0]["custom_option"]
        self.assertEqual(custom_option["setup_config"], {"retention_days_max": 90})


class TestDorisVisibleConfigSerializer(TestCase):
    """DorisVisibleConfigUpdateSerializer 校验"""

    def test_multi_biz_requires_visible_bk_biz(self):
        serializer = DorisVisibleConfigUpdateSerializer(
            data={"cluster_id": 10, "bk_biz_id": OWNER_BIZ, "visible_config": {"visible_type": "multi_biz"}}
        )
        with self.assertRaises(ValidationError):
            serializer.is_valid()

    def test_biz_attr_requires_bk_biz_labels(self):
        serializer = DorisVisibleConfigUpdateSerializer(
            data={"cluster_id": 10, "bk_biz_id": OWNER_BIZ, "visible_config": {"visible_type": "biz_attr"}}
        )
        with self.assertRaises(ValidationError):
            serializer.is_valid()

    def test_valid_all_biz(self):
        serializer = DorisVisibleConfigUpdateSerializer(
            data={"cluster_id": 10, "bk_biz_id": OWNER_BIZ, "visible_config": {"visible_type": "all_biz"}}
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_setup_config_is_optional(self):
        serializer = DorisVisibleConfigUpdateSerializer(
            data={"cluster_id": 10, "bk_biz_id": OWNER_BIZ, "visible_config": {"visible_type": "all_biz"}}
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertNotIn("setup_config", serializer.validated_data)

    def test_valid_setup_config(self):
        serializer = DorisVisibleConfigUpdateSerializer(
            data={
                "cluster_id": 10,
                "bk_biz_id": OWNER_BIZ,
                "visible_config": {"visible_type": "all_biz"},
                "setup_config": {"retention_days_max": 30, "retention_days_default": 14},
            }
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["setup_config"]["retention_days_max"], 30)

    def test_setup_config_default_must_not_exceed_max(self):
        serializer = DorisVisibleConfigUpdateSerializer(
            data={
                "cluster_id": 10,
                "bk_biz_id": OWNER_BIZ,
                "visible_config": {"visible_type": "all_biz"},
                "setup_config": {"retention_days_max": 7, "retention_days_default": 30},
            }
        )
        with self.assertRaises(ValidationError):
            serializer.is_valid()

    def test_setup_config_rejects_non_positive_days(self):
        serializer = DorisVisibleConfigUpdateSerializer(
            data={
                "cluster_id": 10,
                "bk_biz_id": OWNER_BIZ,
                "visible_config": {"visible_type": "all_biz"},
                "setup_config": {"retention_days_max": 0, "retention_days_default": 0},
            }
        )
        self.assertFalse(serializer.is_valid())


class TestMetadataStorageStatus(TestCase):
    @staticmethod
    def _cluster_info(cluster_id, owner_biz=BLUEKING_BK_BIZ_ID, visible_type=VisibleEnum.CURRENT_BIZ.value):
        return {
            "cluster_type": STORAGE_CLUSTER_TYPE,
            "auth_info": {},
            "cluster_config": {
                "cluster_id": cluster_id,
                "registered_system": "other",
                "custom_option": {
                    "bk_biz_id": owner_biz,
                    "visible_config": {"visible_type": visible_type},
                },
            },
        }

    @patch("apps.log_databus.handlers.storage.TransferApi.get_result_table_storage_status")
    def test_get_result_table_indices_adapts_metadata_fields_and_sorts(self, mock_get_storage_status):
        table_id = "2_bklog.test"
        mock_get_storage_status.return_value = {
            "items": [
                {
                    "table_id": table_id,
                    "data": {
                        "result_table": {"default_storage": STORAGE_CLUSTER_TYPE},
                        "storage_configs": {
                            "elasticsearch": {"storage_cluster_id": 7},
                            "doris": {"storage_cluster_id": 8},
                        },
                        "cluster_results": {
                            "7": {
                                "runtime": {
                                    "indices": {
                                        "items": [
                                            {
                                                "index": "2_bklog_test_20260809_0",
                                                "uuid": "old",
                                                "health": "yellow",
                                                "status": "open",
                                                "docs_count": 10,
                                                "docs_deleted": 1,
                                                "store_size_bytes": 1024,
                                                "primary_store_size_bytes": 512,
                                                "primary_shards": 2,
                                                "replica_factor": 1,
                                            },
                                            {
                                                "index": "2_bklog_test_20260810_0",
                                                "uuid": "new",
                                                "health": "green",
                                                "status": "open",
                                                "docs_count": 20,
                                                "docs_deleted": 2,
                                                "store_size_bytes": 2048,
                                                "primary_store_size_bytes": 1024,
                                                "primary_shards": 3,
                                                "replica_factor": 2,
                                            },
                                        ]
                                    }
                                }
                            }
                        },
                    },
                    "error": None,
                }
            ]
        }

        result = StorageHandler.get_result_table_indices(table_id)

        self.assertEqual([item["uuid"] for item in result], ["new", "old"])
        self.assertEqual(
            result[0],
            {
                "index": "2_bklog_test_20260810_0",
                "uuid": "new",
                "health": "green",
                "status": "open",
                "pri": "3",
                "rep": "2",
                "docs.count": "20",
                "docs.deleted": "2",
                "store.size": "2048",
                "pri.store.size": "1024",
            },
        )
        mock_get_storage_status.assert_called_once_with({"table_ids": [table_id]})

    @patch("apps.log_databus.handlers.storage.TransferApi.get_result_table_storage_status")
    def test_get_result_table_indices_skips_historical_es_when_doris_is_default(self, mock_get_storage_status):
        table_id = "2_bklog.doris_default"
        mock_get_storage_status.return_value = {
            "items": [
                {
                    "table_id": table_id,
                    "data": {
                        "result_table": {"default_storage": DORIS_CLUSTER_TYPE},
                        "storage_configs": {
                            STORAGE_CLUSTER_TYPE: {"storage_cluster_id": 7},
                            DORIS_CLUSTER_TYPE: {"storage_cluster_id": 8},
                        },
                        "cluster_results": {
                            "7": {
                                "storage_type": STORAGE_CLUSTER_TYPE,
                                "is_current_segment": False,
                                "runtime": {
                                    "indices": {
                                        "items": [
                                            {
                                                "index": "2_bklog_doris_default_20260810_0",
                                                "health": "green",
                                                "docs_count": 20,
                                            }
                                        ]
                                    }
                                },
                            },
                            "8": {
                                "storage_type": DORIS_CLUSTER_TYPE,
                                "is_current_segment": True,
                                "connectivity": {"is_connected": True},
                                "runtime": {
                                    "binding": {"physical_table_name": "mapleleaf_2.bklog_doris_default"},
                                    "table": {"name": "bklog_doris_default", "rows": 20},
                                    "partitions": [{"name": "p20260810", "rows": 20}],
                                },
                            },
                        },
                    },
                    "error": None,
                }
            ]
        }

        result = StorageHandler.get_result_table_indices(table_id)

        self.assertEqual([index["index"] for index in result], ["p20260810"])

    @patch("apps.log_databus.handlers.storage.TransferApi.get_result_table_storage_status")
    def test_get_result_table_indices_adapts_doris_partitions_to_unified_rows(self, mock_get_storage_status):
        table_id = "2_bklog.doris_only"
        mock_get_storage_status.return_value = {
            "items": [
                {
                    "table_id": table_id,
                    "data": {
                        "result_table": {"default_storage": DORIS_CLUSTER_TYPE},
                        "storage_configs": {DORIS_CLUSTER_TYPE: {"storage_cluster_id": 43}},
                        "cluster_results": {
                            "43": {
                                "storage_type": DORIS_CLUSTER_TYPE,
                                "connectivity": {"is_connected": True},
                                "runtime": {
                                    "binding": {"physical_table_name": "mapleleaf_2.bklog_doris_only"},
                                    "table": {"schema": "mapleleaf_2", "name": "bklog_doris_only"},
                                    "partitions": [
                                        {
                                            "name": "p20260812",
                                            "rows": 100,
                                            "data_length_bytes": 2000,
                                            "index_length_bytes": 48,
                                            "update_time": "2026-08-12 10:00:00",
                                        },
                                        {
                                            "name": "p20260813",
                                            "rows": 39556,
                                            "data_length_bytes": 5814000,
                                            "index_length_bytes": 197,
                                            "update_time": "2026-08-13 10:00:00",
                                        },
                                    ],
                                },
                            }
                        },
                    },
                    "error": None,
                }
            ]
        }

        result = StorageHandler.get_result_table_indices(table_id)

        # update_time 倒序
        self.assertEqual([index["index"] for index in result], ["p20260813", "p20260812"])
        self.assertEqual(
            result[0],
            {
                "index": "p20260813",
                "uuid": "doris:mapleleaf_2.bklog_doris_only:p20260813",
                "health": "green",
                "status": "open",
                "pri": "--",
                "rep": "--",
                "docs.count": "39556",
                "docs.deleted": "--",
                "store.size": "5814197",
                "pri.store.size": "--",
            },
        )

    def test_doris_storage_rows_fall_back_to_physical_table_without_partitions(self):
        item = {
            "table_id": "2_bklog.doris_no_partition",
            "data": {
                "result_table": {"default_storage": DORIS_CLUSTER_TYPE},
                "storage_configs": {DORIS_CLUSTER_TYPE: {"storage_cluster_id": 43}},
                "cluster_results": {
                    "43": {
                        "connectivity": {"is_connected": True},
                        "runtime": {
                            "table": {
                                "schema": "mapleleaf_2",
                                "name": "bklog_doris_no_partition",
                                "rows": 8,
                                "data_length_bytes": 100,
                                "index_length_bytes": 20,
                            },
                            "partitions": [],
                        },
                    }
                },
            },
            "error": None,
        }

        result = StorageHandler._get_result_table_indices_from_status(item)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["index"], "mapleleaf_2.bklog_doris_no_partition")
        self.assertEqual(result[0]["docs.count"], "8")
        self.assertEqual(result[0]["store.size"], "120")

    def test_doris_storage_rows_mark_health_by_connectivity_and_warnings(self):
        def build_item(cluster_status):
            return {
                "table_id": "2_bklog.doris_health",
                "data": {
                    "result_table": {"default_storage": DORIS_CLUSTER_TYPE},
                    "storage_configs": {DORIS_CLUSTER_TYPE: {"storage_cluster_id": 43}},
                    "cluster_results": {"43": cluster_status},
                },
                "error": None,
            }

        runtime = {"partitions": [{"name": "p20260813", "rows": 1}]}
        cases = [
            ({"connectivity": {"is_connected": True}, "runtime": runtime}, "green", "open"),
            (
                {
                    "connectivity": {"is_connected": True},
                    "warnings": [{"code": "HISTORICAL_DORIS_BINDING_NOT_SNAPSHOTTED"}],
                    "runtime": runtime,
                },
                "yellow",
                "open",
            ),
            ({"connectivity": {"is_connected": False}, "runtime": runtime}, "red", "unavailable"),
            ({"runtime_skipped": True, "runtime": runtime}, "--", "unknown"),
        ]
        for cluster_status, expected_health, expected_status in cases:
            with self.subTest(expected_health=expected_health):
                result = StorageHandler._get_result_table_indices_from_status(build_item(cluster_status))
                self.assertEqual(result[0]["health"], expected_health)
                self.assertEqual(result[0]["status"], expected_status)

    def test_get_result_table_indices_infers_doris_when_only_doris_configured(self):
        item = {
            "table_id": "2_bklog.doris_no_default",
            "data": {
                "storage_configs": {DORIS_CLUSTER_TYPE: {"storage_cluster_id": 43}},
                "cluster_results": {
                    "43": {
                        "connectivity": {"is_connected": True},
                        "runtime": {"partitions": [{"name": "p20260813", "rows": 3}]},
                    }
                },
            },
            "error": None,
        }

        result = StorageHandler._get_result_table_indices_from_status(item)

        self.assertEqual([index["index"] for index in result], ["p20260813"])

    def test_get_result_table_indices_skips_ambiguous_dual_storage_without_default(self):
        item = {
            "table_id": "2_bklog.ambiguous",
            "data": {
                "storage_configs": {
                    STORAGE_CLUSTER_TYPE: {"storage_cluster_id": 7},
                    DORIS_CLUSTER_TYPE: {"storage_cluster_id": 8},
                },
                "cluster_results": {
                    "7": {
                        "runtime": {
                            "indices": {
                                "items": [
                                    {
                                        "index": "2_bklog_ambiguous_20260810_0",
                                        "health": "green",
                                    }
                                ]
                            }
                        }
                    }
                },
            },
            "error": None,
        }

        self.assertEqual(StorageHandler._get_result_table_indices_from_status(item), [])

    @patch("apps.log_databus.handlers.storage.TransferApi.get_result_table_storage_status")
    def test_get_result_table_indices_returns_empty_for_item_error(self, mock_get_storage_status):
        table_id = "2_bklog.test"
        mock_get_storage_status.return_value = {
            "items": [
                {
                    "table_id": table_id,
                    "data": None,
                    "error": {"code": "RESULT_TABLE_NOT_FOUND", "message": "not found"},
                }
            ]
        }

        self.assertEqual(StorageHandler.get_result_table_indices(table_id), [])

    @patch("apps.log_databus.handlers.storage.logger.error")
    @patch("apps.log_databus.handlers.storage.TransferApi.get_result_table_storage_status")
    def test_get_result_tables_indices_logs_missing_items(self, mock_get_storage_status, mock_logger_error):
        table_id = "2_bklog.missing"
        mock_get_storage_status.return_value = {"items": []}

        self.assertEqual(StorageHandler.get_result_tables_indices([table_id]), {table_id: []})
        mock_logger_error.assert_called_once_with(
            "[storage] result table storage statuses missing items, table_ids=%s",
            [table_id],
        )

    @patch("apps.log_databus.handlers.storage.TransferApi.get_result_table_storage_status")
    def test_get_result_table_indices_marks_health_unknown_when_metadata_cat_fails(self, mock_get_storage_status):
        table_id = "2_bklog.test"
        mock_get_storage_status.return_value = {
            "items": [
                {
                    "table_id": table_id,
                    "data": {
                        "result_table": {"default_storage": STORAGE_CLUSTER_TYPE},
                        "storage_configs": {STORAGE_CLUSTER_TYPE: {"storage_cluster_id": 7}},
                        "cluster_results": {
                            "7": {
                                "runtime_skipped": False,
                                "warnings": [
                                    {
                                        "code": "INDEX_CAT_UNAVAILABLE",
                                        "message": "cat indices failed",
                                    }
                                ],
                                "errors": [],
                                "runtime": {
                                    "indices": {
                                        "items": [
                                            {
                                                "index": "2_bklog_test_20260810_0",
                                                "docs_count": 20,
                                            }
                                        ]
                                    }
                                },
                            }
                        },
                    },
                    "error": None,
                }
            ]
        }

        result = StorageHandler.get_result_table_indices(table_id)

        self.assertEqual(result[0]["health"], "--")
        self.assertEqual(IndexSetHandler._get_health(result), "--")

    def test_get_health_prioritizes_red_and_yellow_over_unknown(self):
        cases = [
            ([{"health": "green"}, {"health": "--"}], "--"),
            ([{"health": "--"}, {"health": "yellow"}], "yellow"),
            ([{"health": "yellow"}, {"health": "--"}, {"health": "red"}], "red"),
            ([{"health": "green"}, {"health": "green"}], "green"),
            ([{"health": None}], "--"),
        ]

        for source, expected in cases:
            with self.subTest(source=source):
                self.assertEqual(IndexSetHandler._get_health(source), expected)

    @patch("apps.log_databus.handlers.storage.TransferApi.get_result_table_storage_status")
    def test_get_result_tables_indices_batches_fifty_table_ids(self, mock_get_storage_status):
        def get_storage_status(params):
            return {
                "items": [
                    {
                        "table_id": table_id,
                        "data": {
                            "storage_configs": {"elasticsearch": {"storage_cluster_id": 7}},
                            "cluster_results": {"7": {"runtime": {"indices": {"items": []}}}},
                        },
                        "error": None,
                    }
                    for table_id in params["table_ids"]
                ]
            }

        mock_get_storage_status.side_effect = get_storage_status
        table_ids = [f"2_bklog.table_{index}" for index in range(51)]

        result = StorageHandler.get_result_tables_indices(table_ids)

        self.assertEqual(set(result), set(table_ids))
        self.assertEqual(mock_get_storage_status.call_count, 2)
        self.assertEqual(mock_get_storage_status.call_args_list[0].args[0]["table_ids"], table_ids[:50])
        self.assertEqual(mock_get_storage_status.call_args_list[1].args[0]["table_ids"], table_ids[50:])

    @patch("apps.log_databus.handlers.storage.TransferApi.get_result_table_storage_status")
    def test_get_result_tables_indices_degrades_failed_batch_and_continues(self, mock_get_storage_status):
        table_ids = [f"2_bklog.table_{index}" for index in range(51)]

        def get_storage_status(params):
            if len(params["table_ids"]) == 50:
                raise RuntimeError("metadata unavailable")
            table_id = params["table_ids"][0]
            return {
                "items": [
                    {
                        "table_id": table_id,
                        "data": {
                            "result_table": {"default_storage": STORAGE_CLUSTER_TYPE},
                            "storage_configs": {STORAGE_CLUSTER_TYPE: {"storage_cluster_id": 7}},
                            "cluster_results": {
                                "7": {
                                    "runtime": {
                                        "indices": {
                                            "items": [
                                                {
                                                    "index": "2_bklog_table_50_20260810_0",
                                                    "health": "green",
                                                }
                                            ]
                                        }
                                    }
                                }
                            },
                        },
                        "error": None,
                    }
                ]
            }

        mock_get_storage_status.side_effect = get_storage_status

        result = StorageHandler.get_result_tables_indices(table_ids)

        self.assertEqual(result[table_ids[0]], [])
        self.assertEqual(len(result[table_ids[-1]]), 1)
        self.assertEqual(mock_get_storage_status.call_count, 2)

    @patch("apps.log_databus.handlers.storage.TransferApi.get_cluster_status")
    def test_batch_connectivity_detect_adapts_status_and_batches_twenty_ids(self, mock_get_cluster_status):
        def get_cluster_status(params, bk_tenant_id=None):
            self.assertEqual(bk_tenant_id, "tenant-a")
            return [
                {
                    "cluster_id": cluster_id,
                    "cluster_type": "elasticsearch",
                    "is_available": True,
                    "nodes": {"total": 2, "available": 2},
                    "capacity": {"total_bytes": 1000},
                    "details": {
                        "health_status": "yellow",
                        "number_of_nodes": 3,
                        "active_shards": 10,
                        "initializing_shards": 1,
                        "unassigned_shards": 2,
                        "indices_store_bytes": 800,
                    },
                }
                for cluster_id in params["cluster_ids"]
            ]

        mock_get_cluster_status.side_effect = get_cluster_status

        with (
            patch.object(StorageHandler, "_get_visible_cluster_ids", return_value=list(range(1, 23))),
            patch("apps.log_databus.handlers.storage.Space.get_tenant_id", return_value="tenant-a"),
            patch("apps.log_databus.handlers.storage.cache.get_many", return_value={}),
            patch("apps.log_databus.handlers.storage.cache.set_many"),
        ):
            result = StorageHandler.batch_connectivity_detect(list(range(1, 23)), bk_biz_id=2)

        self.assertEqual(mock_get_cluster_status.call_count, 2)
        batches = sorted(
            [item.args[0]["cluster_ids"] for item in mock_get_cluster_status.call_args_list],
            key=lambda cluster_ids: cluster_ids[0],
        )
        self.assertEqual(batches, [list(range(1, 21)), [21, 22]])
        self.assertTrue(all(item.args[0]["bk_biz_id"] == 2 for item in mock_get_cluster_status.call_args_list))
        self.assertTrue(result[1]["status"])
        self.assertEqual(
            result[1]["cluster_stats"],
            {
                "node_count": 3,
                "shards_total": 13,
                "shards_pri": None,
                "data_node_count": 2,
                "indices_count": None,
                "indices_docs_count": None,
                "indices_store": 800,
                "total_store": 1000,
                "status": "yellow",
            },
        )

    @patch("apps.log_databus.handlers.storage.TransferApi.get_cluster_status")
    def test_batch_connectivity_detect_uses_metadata_doris_status(self, mock_get_cluster_status):
        mock_get_cluster_status.return_value = [
            {
                "cluster_id": 8,
                "cluster_type": DORIS_CLUSTER_TYPE,
                "is_available": False,
                "nodes": {"total": 2, "available": 0},
                "capacity": {
                    "total_bytes": 1000,
                    "available_bytes": 100,
                    "used_bytes": 900,
                    "used_percent": 90,
                },
                "details": {
                    "data_used_bytes": 800,
                    "tablet_count": 20,
                    "max_disk_used_percent": 91,
                },
                "status": "unavailable",
            }
        ]

        with (
            patch.object(StorageHandler, "_get_visible_cluster_ids", return_value=[8]),
            patch("apps.log_databus.handlers.storage.Space.get_tenant_id", return_value="tenant-a"),
            patch("apps.log_databus.handlers.storage.cache.get_many", return_value={}),
            patch("apps.log_databus.handlers.storage.cache.set_many"),
        ):
            result = StorageHandler.batch_connectivity_detect([8], bk_biz_id=2)

        self.assertEqual(
            result[8],
            {
                "status": False,
                "cluster_stats": {
                    "node_count": 2,
                    "available_node_count": 0,
                    "shards_total": None,
                    "shards_pri": None,
                    "data_node_count": 2,
                    "indices_count": None,
                    "indices_docs_count": None,
                    "indices_store": 800,
                    "total_store": 1000,
                    "available_store": 100,
                    "used_store": 900,
                    "used_percent": 90,
                    "tablet_count": 20,
                    "max_disk_used_percent": 91,
                    "status": "red",
                    "storage_status": "unavailable",
                },
            },
        )

    @patch(
        "apps.log_databus.handlers.storage.TransferApi.get_cluster_status",
        side_effect=RuntimeError("metadata unavailable"),
    )
    def test_batch_connectivity_detect_degrades_when_metadata_request_fails(self, mock_get_cluster_status):
        with (
            patch.object(StorageHandler, "_get_visible_cluster_ids", return_value=[7, 8]),
            patch("apps.log_databus.handlers.storage.Space.get_tenant_id", return_value="tenant-a"),
            patch("apps.log_databus.handlers.storage.cache.get_many", return_value={}),
            patch("apps.log_databus.handlers.storage.cache.set_many"),
        ):
            result = StorageHandler.batch_connectivity_detect([7, 8], bk_biz_id=2)

        mock_get_cluster_status.assert_called_once_with(
            {"cluster_ids": [7, 8], "bk_biz_id": 2},
            bk_tenant_id="tenant-a",
        )
        self.assertEqual(
            result,
            {
                7: {"status": False, "cluster_stats": None},
                8: {"status": False, "cluster_stats": None},
            },
        )

    @patch("apps.log_databus.handlers.storage.cache.set_many")
    @patch("apps.log_databus.handlers.storage.cache.get_many")
    @patch("apps.log_databus.handlers.storage.TransferApi.get_cluster_status")
    @patch("apps.log_databus.handlers.storage.TransferApi.get_cluster_info")
    @patch("apps.log_databus.handlers.storage.Space.get_tenant_id", return_value="tenant-a")
    def test_batch_connectivity_detect_filters_invisible_clusters_before_status_query(
        self,
        _mock_get_tenant_id,
        mock_get_cluster_info,
        mock_get_cluster_status,
        _mock_cache_get_many,
        _mock_cache_set_many,
    ):
        mock_get_cluster_info.return_value = [
            self._cluster_info(7),
            self._cluster_info(8, owner_biz=OWNER_BIZ),
        ]
        mock_get_cluster_status.return_value = [
            {
                "cluster_id": 7,
                "cluster_type": STORAGE_CLUSTER_TYPE,
                "is_available": True,
                "details": {"health_status": "green"},
            }
        ]
        _mock_cache_get_many.side_effect = lambda keys: {
            "connect_info_tenant-a_2_8": {
                "cluster_id": 8,
                "cluster_type": STORAGE_CLUSTER_TYPE,
                "is_available": True,
                "details": {"health_status": "green", "number_of_nodes": 99},
            }
            for key in keys
            if key == "connect_info_tenant-a_2_8"
        }

        result = StorageHandler.batch_connectivity_detect([7, 8], bk_biz_id=BLUEKING_BK_BIZ_ID)

        mock_get_cluster_info.assert_called_once_with({}, bk_tenant_id="tenant-a")
        self.assertEqual(
            list(_mock_cache_get_many.call_args.args[0]),
            ["connect_info_tenant-a_2_7"],
        )
        mock_get_cluster_status.assert_called_once_with(
            {"cluster_ids": [7], "bk_biz_id": BLUEKING_BK_BIZ_ID},
            bk_tenant_id="tenant-a",
        )
        self.assertTrue(result[7]["status"])
        self.assertEqual(result[8], {"status": False, "cluster_stats": None})

    @patch("apps.log_databus.handlers.storage.TransferApi.get_cluster_status")
    @patch(
        "apps.log_databus.handlers.storage.TransferApi.get_cluster_info",
        side_effect=RuntimeError("metadata unavailable"),
    )
    @patch("apps.log_databus.handlers.storage.Space.get_tenant_id", return_value="tenant-a")
    def test_batch_connectivity_detect_fails_closed_when_cluster_info_request_fails(
        self,
        _mock_get_tenant_id,
        mock_get_cluster_info,
        mock_get_cluster_status,
    ):
        result = StorageHandler.batch_connectivity_detect([7, 8], bk_biz_id=2)

        mock_get_cluster_info.assert_called_once_with({}, bk_tenant_id="tenant-a")
        mock_get_cluster_status.assert_not_called()
        self.assertEqual(
            result,
            {
                7: {"status": False, "cluster_stats": None},
                8: {"status": False, "cluster_stats": None},
            },
        )

    @patch("apps.log_databus.handlers.storage.TransferApi.get_cluster_status")
    @patch("apps.log_databus.handlers.storage.TransferApi.get_cluster_info")
    @patch("apps.log_databus.handlers.storage.Space.get_tenant_id")
    def test_batch_connectivity_detect_cache_isolated_by_tenant_biz_and_cluster(
        self,
        mock_get_tenant_id,
        mock_get_cluster_info,
        mock_get_cluster_status,
    ):
        mock_get_tenant_id.side_effect = lambda bk_biz_id: {
            2: "tenant-a",
            3: "tenant-b",
            4: "tenant-a",
        }[bk_biz_id]
        mock_get_cluster_info.return_value = [self._cluster_info(7, visible_type=VisibleEnum.ALL_BIZ.value)]
        mock_get_cluster_status.return_value = [
            {
                "cluster_id": 7,
                "cluster_type": STORAGE_CLUSTER_TYPE,
                "is_available": True,
                "details": {"health_status": "green"},
            }
        ]
        cache_store = {}
        cache_timeouts = []

        def get_many(keys):
            return {key: cache_store[key] for key in keys if key in cache_store}

        def set_many(values, timeout):
            cache_store.update(values)
            cache_timeouts.append(timeout)

        with (
            patch("apps.log_databus.handlers.storage.cache.get_many", side_effect=get_many),
            patch("apps.log_databus.handlers.storage.cache.set_many", side_effect=set_many),
        ):
            StorageHandler.batch_connectivity_detect([7, 7], bk_biz_id=2)
            StorageHandler.batch_connectivity_detect([7], bk_biz_id=2)
            StorageHandler.batch_connectivity_detect([7], bk_biz_id=4)
            StorageHandler.batch_connectivity_detect([7], bk_biz_id=3)

        self.assertEqual(mock_get_cluster_status.call_count, 3)
        self.assertEqual(
            set(cache_store),
            {
                "connect_info_tenant-a_2_7",
                "connect_info_tenant-a_4_7",
                "connect_info_tenant-b_3_7",
            },
        )
        self.assertEqual(cache_timeouts, [300, 300, 300])

    @patch("apps.log_databus.handlers.storage.MultiExecuteFunc")
    @patch("apps.log_databus.handlers.storage.cache.set_many")
    @patch("apps.log_databus.handlers.storage.cache.get_many", return_value={})
    @patch("apps.log_databus.handlers.storage.Space.get_tenant_id", return_value="tenant-a")
    def test_batch_connectivity_detect_schedules_batches_in_one_concurrent_executor(
        self,
        _mock_get_tenant_id,
        _mock_cache_get_many,
        _mock_cache_set_many,
        mock_multi_execute_cls,
    ):
        cluster_ids = list(range(1, 42))
        executor = mock_multi_execute_cls.return_value
        executor.run.return_value = {
            0: {cluster_id: StorageHandler._unavailable_cluster_status(cluster_id) for cluster_id in range(1, 21)},
            20: {cluster_id: StorageHandler._unavailable_cluster_status(cluster_id) for cluster_id in range(21, 41)},
            40: {41: StorageHandler._unavailable_cluster_status(41)},
        }

        with patch.object(StorageHandler, "_get_visible_cluster_ids", return_value=cluster_ids):
            result = StorageHandler.batch_connectivity_detect(cluster_ids + [1], bk_biz_id=2)

        mock_multi_execute_cls.assert_called_once_with(max_workers=5)
        self.assertEqual([call[0] for call in executor.method_calls], ["append", "append", "append", "run"])
        batches = [item.args[2]["cluster_ids"] for item in executor.append.call_args_list]
        self.assertEqual(batches, [list(range(1, 21)), list(range(21, 41)), [41]])
        self.assertEqual(len(result), 41)

    @patch("apps.log_databus.handlers.storage.TransferApi.get_cluster_status")
    def test_cluster_detail_uses_metadata_status_for_es_and_doris(self, mock_get_cluster_status):
        mock_get_cluster_status.return_value = [
            {
                "cluster_id": 7,
                "cluster_type": "elasticsearch",
                "is_available": True,
                "nodes": {"total": 2},
                "capacity": {"total_bytes": 1000},
                "details": {"health_status": "green", "number_of_nodes": 3},
            },
            {
                "cluster_id": 8,
                "cluster_type": DORIS_CLUSTER_TYPE,
                "is_available": True,
                "nodes": {"total": 2, "available": 2},
                "capacity": {"total_bytes": 2000, "used_bytes": 500},
                "details": {"data_used_bytes": 400, "tablet_count": 10},
                "status": "available",
            },
        ]
        clusters = [
            {"cluster_type": "elasticsearch", "cluster_config": {"cluster_id": 7}},
            {"cluster_type": DORIS_CLUSTER_TYPE, "cluster_config": {"cluster_id": 8}},
        ]

        with (
            patch("apps.log_databus.handlers.storage.Space.get_tenant_id", return_value="tenant-a"),
            patch("apps.log_databus.handlers.storage.cache.get_many", return_value={}),
            patch("apps.log_databus.handlers.storage.cache.set_many"),
        ):
            result = StorageHandler()._get_cluster_detail_info(clusters, bk_biz_id=2)

        mock_get_cluster_status.assert_called_once_with(
            {"cluster_ids": [7, 8], "bk_biz_id": 2},
            bk_tenant_id="tenant-a",
        )
        self.assertEqual(result[0]["cluster_stats"]["status"], "green")
        self.assertEqual(result[1]["cluster_stats"]["status"], "green")
        self.assertEqual(result[1]["cluster_stats"]["storage_status"], "available")
        self.assertEqual(result[1]["cluster_stats"]["tablet_count"], 10)
        self.assertEqual(result[1]["cluster_stats"]["indices_store"], 400)

    @patch.object(StorageHandler, "get_result_tables_indices")
    @patch.object(IndexSetHandler, "_get_data")
    def test_log_index_set_indices_use_metadata_status(self, mock_get_data, mock_get_indices):
        index_set = MagicMock(scenario_id=Scenario.LOG, storage_cluster_id=7)
        index_set.get_indexes.return_value = [{"result_table_id": "2_bklog.test"}]
        mock_get_data.return_value = index_set
        mock_get_indices.return_value = {
            "2_bklog.test": [
                {
                    "index": "2_bklog_test_20260810_0",
                    "health": "green",
                    "pri": 2,
                    "rep": 1,
                    "docs.count": 20,
                    "docs.deleted": 2,
                    "store.size": 2048,
                    "pri.store.size": 1024,
                }
            ]
        }

        result = IndexSetHandler(1).indices()

        mock_get_indices.assert_called_once_with(["2_bklog.test"])
        self.assertEqual(result["list"][0]["stat"]["health"], "green")
        self.assertEqual(result["list"][0]["stat"]["docs.count"], 20)
        self.assertEqual(result["list"][0]["stat"]["store.size"], 2048)
        self.assertEqual(result["list"][0]["stat"]["pri.store.size"], 1024)

    @patch.object(StorageHandler, "get_result_tables_indices", return_value={"2_bklog.test": []})
    @patch.object(IndexSetHandler, "_get_data")
    def test_log_index_set_without_physical_indices_keeps_legacy_placeholder(self, mock_get_data, _mock_get_indices):
        index_set = MagicMock(scenario_id=Scenario.LOG, storage_cluster_id=7)
        index_set.get_indexes.return_value = [{"result_table_id": "2_bklog.test"}]
        mock_get_data.return_value = index_set

        result = IndexSetHandler(1).indices()

        self.assertEqual(result["list"][0]["stat"]["health"], "--")
        self.assertEqual(result["list"][0]["details"], "--")

    @patch.object(StorageHandler, "get_result_table_indices", return_value=[{"index": "2_bklog_test_20260810_0"}])
    def test_collector_indices_info_uses_metadata_storage_status(self, mock_get_indices):
        handler = MagicMock()
        handler.data.table_id = "2_bklog.test"
        handler.data.storage_cluster_type = STORAGE_CLUSTER_TYPE

        result = CollectorHandler.indices_info(handler)

        mock_get_indices.assert_called_once_with("2_bklog.test")
        self.assertEqual(result, [{"index": "2_bklog_test_20260810_0"}])

    @patch.object(StorageHandler, "get_result_table_indices", return_value=[{"index": "p20260813"}])
    def test_collector_indices_info_no_longer_short_circuits_doris(self, mock_get_indices):
        handler = MagicMock()
        handler.data.table_id = "2_bklog.doris_only"
        handler.data.storage_cluster_type = DORIS_CLUSTER_TYPE

        result = CollectorHandler.indices_info(handler)

        mock_get_indices.assert_called_once_with("2_bklog.doris_only")
        self.assertEqual(result, [{"index": "p20260813"}])

    @patch.object(StorageHandler, "get_result_tables_indices")
    @patch.object(IndexSetHandler, "_get_data")
    def test_log_index_set_aggregation_ignores_placeholder_values(self, mock_get_data, mock_get_indices):
        index_set = MagicMock(scenario_id=Scenario.LOG, storage_cluster_id=43)
        index_set.get_indexes.return_value = [{"result_table_id": "2_bklog.doris_only"}]
        mock_get_data.return_value = index_set
        mock_get_indices.return_value = {
            "2_bklog.doris_only": [
                {
                    "index": "p20260813",
                    "health": "green",
                    "pri": "--",
                    "rep": "--",
                    "docs.count": "39556",
                    "docs.deleted": "--",
                    "store.size": "5814197",
                    "pri.store.size": "--",
                }
            ]
        }

        stat = IndexSetHandler(1).indices()["list"][0]["stat"]

        self.assertEqual(stat["docs.count"], 39556)
        self.assertEqual(stat["store.size"], 5814197)
        # 整列都是占位值时继续返回 "--"，不能塌成 0
        self.assertEqual(stat["pri"], "--")
        self.assertEqual(stat["docs.deleted"], "--")
        self.assertEqual(stat["pri.store.size"], "--")


class TestStorageRetentionCompat(TestCase):
    """Doris 的过期天数在 metadata 里叫 expire_days，日志平台对外统一暴露 retention"""

    RESULT_TABLE_CONFIG = {
        "option": {},
        "field_list": [
            {
                "field_name": "dtEventTimeStamp",
                "alias_name": "",
                "field_type": "timestamp",
                "is_built_in": True,
                "is_dimension": True,
                "option": {"es_type": "date", "time_zone": 0, "time_format": "epoch_millis"},
            }
        ],
    }

    @staticmethod
    def _make_row(table_id):
        return {
            "table_id": table_id,
            "category_id": "os",
            "custom_type": "log",
            "created_at": "2026-08-13 10:00:00",
            "updated_at": "2026-08-13 10:00:00",
        }

    def test_get_storage_retention_prefers_es_retention(self):
        self.assertEqual(get_storage_retention({"retention": 14, "expire_days": 30}), 14)

    def test_get_storage_retention_falls_back_to_doris_expire_days(self):
        self.assertEqual(get_storage_retention({"expire_days": 30}), 30)

    def test_get_storage_retention_returns_default_when_absent(self):
        self.assertIsNone(get_storage_retention({}))
        self.assertEqual(get_storage_retention(None, default=0), 0)
        self.assertEqual(get_storage_retention({"bkbase_table_id": "x"}, default=0), 0)

    def test_get_storage_retention_treats_zero_as_unset(self):
        # bulk_cluster_infos 查不到结果表时兜底为 retention=0，该值不代表用户配置了 0 天
        self.assertEqual(get_storage_retention({"retention": 0}, default=7), 7)

    def test_get_storage_retention_skips_placeholder_retention_for_doris(self):
        # doris 结果表即便同时带上 ES 语义的 retention 占位值，也应以 expire_days 为准
        self.assertEqual(get_storage_retention({"retention": 0, "expire_days": 30}), 30)

    def test_build_storage_retention_config_for_es(self):
        self.assertEqual(build_storage_retention_config(STORAGE_CLUSTER_TYPE, 14), {"retention": 14})

    def test_build_storage_retention_config_for_doris(self):
        # DorisStorage 的 create_table 与 UPGRADE_FIELD_CONFIG 都只认 expire_days，必须补上该键
        self.assertEqual(
            build_storage_retention_config(DORIS_CLUSTER_TYPE, 14),
            {"retention": 14, "expire_days": 14},
        )

    def test_build_storage_retention_config_round_trips_with_getter(self):
        # 写入与读取两个方向应互为逆运算，避免再次出现字段名口径漂移
        for cluster_type in (STORAGE_CLUSTER_TYPE, DORIS_CLUSTER_TYPE):
            with self.subTest(cluster_type=cluster_type):
                config = build_storage_retention_config(cluster_type, 14)
                self.assertEqual(get_storage_retention(config), 14)

    def test_parse_result_table_config_maps_doris_expire_days_to_retention(self):
        collector_config = EtlStorage.parse_result_table_config(
            result_table_config=copy.deepcopy(self.RESULT_TABLE_CONFIG),
            result_table_storage={
                "cluster_config": {"cluster_id": 43, "cluster_name": "doris", "display_name": "doris"},
                "storage_config": {"expire_days": 30, "bkbase_table_id": "bklog_doris_only"},
            },
        )

        self.assertEqual(collector_config["retention"], 30)
        self.assertEqual(collector_config["storage_cluster_id"], 43)

    def test_add_cluster_info_maps_doris_expire_days_to_retention(self):
        cluster_infos = {
            "2_bklog.doris_only": {
                "cluster_config": {"cluster_id": 43, "cluster_name": "doris"},
                "storage_config": {"expire_days": 30},
            }
        }
        data = [self._make_row("2_bklog.doris_only")]

        with (
            patch.object(CollectorHandler, "bulk_cluster_infos", return_value=cluster_infos),
            patch("apps.log_databus.handlers.collector.base.get_local_param", return_value="Asia/Shanghai"),
        ):
            result = CollectorHandler.add_cluster_info(data)

        self.assertEqual(result[0]["retention"], 30)

    def test_parse_result_table_config_keeps_es_retention(self):
        collector_config = EtlStorage.parse_result_table_config(
            result_table_config=copy.deepcopy(self.RESULT_TABLE_CONFIG),
            result_table_storage={
                "cluster_config": {"cluster_id": 1, "cluster_name": "es", "display_name": "es"},
                "storage_config": {"retention": 7},
            },
        )

        self.assertEqual(collector_config["retention"], 7)

    def test_add_cluster_info_es_and_doris_expose_retention_uniformly(self):
        cluster_infos = {
            "2_bklog.retention_es": {
                "cluster_config": {"cluster_id": 1, "cluster_name": "es"},
                "storage_config": {"retention": 7},
            },
            "2_bklog.retention_doris": {
                "cluster_config": {"cluster_id": 43, "cluster_name": "doris"},
                # doris 结果表同时带 ES 语义的 retention 占位值时，仍应取 expire_days
                "storage_config": {"retention": 0, "expire_days": 30},
            },
        }
        data = [self._make_row("2_bklog.retention_es"), self._make_row("2_bklog.retention_doris")]

        with (
            patch.object(CollectorHandler, "bulk_cluster_infos", return_value=cluster_infos),
            patch("apps.log_databus.handlers.collector.base.get_local_param", return_value="Asia/Shanghai"),
        ):
            result = CollectorHandler.add_cluster_info(data)

        self.assertEqual(result[0]["retention"], 7)
        self.assertEqual(result[1]["retention"], 30)

    def test_add_cluster_info_falls_back_to_zero_when_metadata_missing(self):
        # metadata 未返回集群信息时保持原有兜底行为
        data = [self._make_row("2_bklog.retention_missing")]

        with (
            patch.object(CollectorHandler, "bulk_cluster_infos", return_value={}),
            patch("apps.log_databus.handlers.collector.base.get_local_param", return_value="Asia/Shanghai"),
        ):
            result = CollectorHandler.add_cluster_info(data)

        self.assertEqual(result[0]["retention"], 0)
        self.assertEqual(result[0]["storage_cluster_id"], -1)
