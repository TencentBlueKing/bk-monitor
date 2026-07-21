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
    DORIS_CLUSTER_TYPE,
    REGISTERED_SYSTEM_DEFAULT,
    VisibleEnum,
)
from apps.log_databus.exceptions import (
    StorageNotExistException,
    StorageNotPermissionException,
)
from apps.log_databus.handlers.storage import StorageHandler
from apps.log_databus.serializers import DorisVisibleConfigUpdateSerializer

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
class TestUpdateVisibleConfig(TestCase):
    """StorageHandler.update_visible_config 仅更新 visible_config"""

    def _run_update(self, cluster_info, params):
        with patch("apps.log_databus.handlers.storage.TransferApi") as mock_api, patch(
            "apps.log_databus.handlers.storage.user_operation_record"
        ) as mock_record, patch(
            "apps.log_databus.handlers.storage.get_request_username", return_value="tester"
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


class TestDorisVisibleConfigSerializer(TestCase):
    """DorisVisibleConfigUpdateSerializer 校验"""

    def test_multi_biz_requires_visible_bk_biz(self):
        serializer = DorisVisibleConfigUpdateSerializer(
            data={"cluster_id": 10, "bk_biz_id": OWNER_BIZ, "visible_config": {"visible_type": "multi_biz"}}
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("visible_config", serializer.errors)

    def test_biz_attr_requires_bk_biz_labels(self):
        serializer = DorisVisibleConfigUpdateSerializer(
            data={"cluster_id": 10, "bk_biz_id": OWNER_BIZ, "visible_config": {"visible_type": "biz_attr"}}
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("visible_config", serializer.errors)

    def test_valid_all_biz(self):
        serializer = DorisVisibleConfigUpdateSerializer(
            data={"cluster_id": 10, "bk_biz_id": OWNER_BIZ, "visible_config": {"visible_type": "all_biz"}}
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
