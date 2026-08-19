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
import functools
import ipaddress
import operator
import re
from collections import defaultdict

import arrow
from django.conf import settings
from django.core.cache import cache
from django.db.models import Q, Sum
from django.utils.translation import gettext as _

from apps.api import BkDataResourceCenterApi, BkLogApi, TransferApi
from apps.constants import (
    SpacePropertyEnum,
    UserOperationActionEnum,
    UserOperationTypeEnum,
)
from apps.decorators import user_operation_record
from apps.feature_toggle.handlers.toggle import FeatureToggleObject
from apps.iam import Permission, ResourceEnum
from apps.log_databus.constants import (
    BKLOG_RESULT_TABLE_PATTERN,
    ClusterTypeEnum,
    DEFAULT_ES_SCHEMA,
    DEFAULT_ES_TAGS,
    DEFAULT_ES_TRANSPORT,
    DORIS_STORAGE_CLUSTER,
    NODE_ATTR_PREFIX_BLACKLIST,
    REGISTERED_SYSTEM_DEFAULT,
    STORAGE_CLUSTER_TYPE,
    EsSourceType,
    VisibleEnum,
    DORIS_CLUSTER_TYPE,
)
from apps.log_databus.exceptions import (
    BKBaseStorageSyncFailed,
    ESClusterAlreadyExistException,
    NodeSettingException,
    StorageHaveResource,
    StorageNotExistException,
    StorageNotPermissionException,
    StorageUnKnowEsVersionException,
)
from apps.log_databus.models import CollectorConfig, StorageCapacity, StorageUsed
from apps.log_databus.utils.es_config import get_es_config
from apps.log_esquery.utils.es_client import (
    es_client_ping,
    es_socket_ping,
    get_es_client,
)
from apps.log_esquery.utils.es_route import EsRoute
from apps.log_search.models import BizProperty, Scenario, Space
from apps.utils.local import get_local_param, get_request_username
from apps.utils.log import logger
from apps.utils.thread import MultiExecuteFunc
from apps.utils.time_handler import format_user_time_zone
from bkm_space.api import SpaceApi
from bkm_space.define import SpaceTypeEnum
from bkm_space.utils import bk_biz_id_to_space_uid, parse_space_uid
import builtins

CACHE_EXPIRE_TIME = 300
METADATA_CLUSTER_STATUS_BATCH_SIZE = 20
METADATA_CLUSTER_STATUS_MAX_WORKERS = 5
METADATA_RESULT_TABLE_STATUS_BATCH_SIZE = 50
# Doris 无等价指标的物理存储行字段，沿用前端既有占位样式，不能落成 0
DORIS_STORAGE_ROW_PLACEHOLDER = "--"


class StorageHandler:
    def __init__(self, cluster_id=None):
        self.cluster_id = cluster_id
        super().__init__()

    def can_visible(self, bk_biz_id, custom_option, registered_system) -> bool:
        # 兼容系统预置集群未设置集群ID的情况
        if registered_system == REGISTERED_SYSTEM_DEFAULT and not custom_option["bk_biz_id"]:
            return True

        # 兼容老数据没有visible_config的情况
        if not custom_option.get("visible_config") and bk_biz_id != custom_option["bk_biz_id"]:
            return False

        # 如果当前业务是创建业务 直接可见
        if bk_biz_id == custom_option["bk_biz_id"]:
            return True

        visible_config = custom_option["visible_config"]

        # 全业务可见
        if visible_config["visible_type"] == VisibleEnum.ALL_BIZ.value:
            return True

        # 当前租户可见
        # TODO: 需要补充过滤判定逻辑
        if visible_config["visible_type"] == VisibleEnum.CURRENT_TENANT.value:
            return True

        if visible_config["visible_type"] == VisibleEnum.MULTI_BIZ.value:
            # 兼容两种数据格式：整数列表 [1, 2, 3] 或字典列表 [{"bk_biz_id": 1}, {"bk_biz_id": 2}]
            visible_bk_biz_id_list = []
            for bk_biz in visible_config["visible_bk_biz"]:
                if isinstance(bk_biz, dict):
                    visible_bk_biz_id_list.append(str(bk_biz["bk_biz_id"]))
                else:
                    visible_bk_biz_id_list.append(str(bk_biz))
            return str(bk_biz_id) in visible_bk_biz_id_list

        if visible_config["visible_type"] == VisibleEnum.BIZ_ATTR.value:
            # 如果空间类型不是业务，需要找出该空间关联的业务再做判断(如果有)
            space_uid = bk_biz_id_to_space_uid(bk_biz_id)
            space_type, space_id = parse_space_uid(space_uid)
            bk_biz_labels = visible_config.get("bk_biz_labels", {})
            if not bk_biz_labels:
                return False
            # 如果存在空间类型的属性, 则判断空间类型是否在属性值列表中
            label_space_type_value_list = bk_biz_labels.get(SpacePropertyEnum.SPACE_TYPE.value, [])
            if label_space_type_value_list and space_type in label_space_type_value_list:
                return True
            if label_space_type_value_list and space_type not in label_space_type_value_list:
                return False
            related_space = SpaceApi.get_related_space(space_uid, SpaceTypeEnum.BKCC.value)
            if not related_space:
                return False
            bk_biz_id = related_space.bk_biz_id
            q_filter = Q()
            for label_key, label_values in bk_biz_labels.items():
                q_filter &= functools.reduce(
                    operator.or_,
                    [
                        Q(bk_biz_id=bk_biz_id, biz_property_id=label_key, biz_property_value=label_value)
                        for label_value in label_values
                    ],
                )
            return BizProperty.objects.filter(q_filter).exists()
        return False

    def get_cluster_groups(
        self,
        bk_biz_id,
        cluster_query_type=ClusterTypeEnum.ES.value,
        is_default=True,
        enable_archive=False,
        cluster_id=None,
    ):
        """
        获取集群列表
        :param bk_biz_id: bk_biz_id
        :param cluster_query_type: 集群类型
        :param is_default: 是否查询公共集群
        :param enable_archive: 是否只查询可归档集群
        :param cluster_id: 可选集群ID
        :return:
        """
        multi_execute_func = MultiExecuteFunc()

        cluster_infos = []
        cluster_types = []

        if cluster_query_type == ClusterTypeEnum.ALL.value or cluster_query_type == ClusterTypeEnum.ES.value:
            cluster_types.append(STORAGE_CLUSTER_TYPE)

        if (
            cluster_query_type == ClusterTypeEnum.ALL.value or cluster_query_type == ClusterTypeEnum.DORIS.value
        ) and FeatureToggleObject.switch(DORIS_STORAGE_CLUSTER, bk_biz_id):
            cluster_types.append(DORIS_CLUSTER_TYPE)

        for cluster_type in cluster_types:
            params = {"cluster_type": cluster_type}
            if cluster_id:
                params["cluster_id"] = cluster_id
            multi_execute_func.append(cluster_type, TransferApi.get_cluster_info, params)

        result = multi_execute_func.run()

        for cluster_type, cluster_info_list in result.items():
            cluster_infos.extend(cluster_info_list)

        cluster_groups = self.filter_cluster_groups(
            cluster_infos,
            bk_biz_id,
            is_default=is_default,
            enable_archive=enable_archive,
            post_visible=True,
        )

        cluster_groups = [
            cluster
            for cluster in cluster_groups
            if self.can_visible(
                bk_biz_id,
                cluster["cluster_config"].get("custom_option"),
                cluster["cluster_config"]["registered_system"],
            )
        ]

        return [
            {
                "storage_usage": i["storage_usage"],
                "storage_total": i["storage_total"],
                "index_count": i["index_count"],
                "biz_count": i["biz_count"],
                "storage_cluster_id": i["cluster_config"].get("cluster_id"),
                "storage_cluster_name": i["cluster_config"].get("cluster_name"),
                "storage_display_name": i["cluster_config"].get("display_name")
                or i["cluster_config"].get("cluster_name"),
                "storage_version": i["cluster_config"].get("version"),
                "storage_type": i["cluster_type"],
                "priority": i["priority"],
                "registered_system": i["cluster_config"].get("registered_system"),
                "bk_biz_id": i["cluster_config"]["custom_option"]["bk_biz_id"],
                "enable_hot_warm": i["cluster_config"]["custom_option"]
                .get("hot_warm_config", {})
                .get("is_enabled", False),
                "setup_config": i["cluster_config"]["custom_option"]["setup_config"],
                "admin": i["cluster_config"]["custom_option"].get("admin", [i["cluster_config"]["creator"]]),
                "description": i["cluster_config"]["custom_option"]["description"],
                "source_type": i["cluster_config"]["custom_option"]["source_type"],
                "enable_assessment": i["cluster_config"]["custom_option"]["enable_assessment"],
                "enable_archive": i["cluster_config"]["custom_option"]["enable_archive"],
                "is_platform": self.is_platform_cluster(
                    i["cluster_config"]["custom_option"]["visible_config"]["visible_type"]
                ),
                "visible_editable": i.get("visible_editable", False),
            }
            for i in cluster_groups
            if i
        ]

    def get_cluster_groups_filter(
        self,
        bk_biz_id,
        cluster_query_type=ClusterTypeEnum.ES.value,
        is_default=True,
        enable_archive=False,
    ):
        """
        获取集群列表并过滤
        :param bk_biz_id: bk_biz_id
        :param cluster_query_type: 集群查询类型
        :param is_default: 是否查询公共集群
        :param enable_archive: 是否只查询可归档集群
        :return:
        """
        cluster_groups = self.get_cluster_groups(
            bk_biz_id, cluster_query_type=cluster_query_type, is_default=is_default, enable_archive=enable_archive
        )

        # 排序：第三方集群 > 默认集群
        cluster_groups.sort(key=lambda c: c["priority"])

        # 获取公共集群使用情况
        public_clusters = [
            cluster["storage_cluster_id"]
            for cluster in cluster_groups
            if cluster.get("registered_system") == REGISTERED_SYSTEM_DEFAULT
        ]
        if not public_clusters:
            return cluster_groups

        es_config = get_es_config(bk_biz_id)
        # 获取公共集群容易配额
        storage_capacity = self.get_storage_capacity(bk_biz_id, public_clusters)
        for cluster in cluster_groups:
            if cluster.get("registered_system") == REGISTERED_SYSTEM_DEFAULT:
                cluster["storage_capacity"] = storage_capacity["storage_capacity"]
                cluster["storage_used"] = storage_capacity["storage_used"]
                cluster["max_retention"] = es_config["ES_PUBLIC_STORAGE_DURATION"]
            else:
                cluster["storage_capacity"] = 0
                cluster["storage_used"] = 0
                cluster["max_retention"] = es_config["ES_PRIVATE_STORAGE_DURATION"]
        return cluster_groups

    @classmethod
    def filter_cluster_groups(
        cls, cluster_groups, bk_biz_id, is_default=True, enable_archive=False, post_visible=False
    ):
        """
        筛选集群，并判断集群是否可编辑
        :param cluster_groups: 集群信息列表
        :param bk_biz_id: bk_biz_id
        :param is_default: 是否查询公共集群
        :param enable_archive: 是否只查询可归档的集群
        :return:
        """
        # 筛选集群 & 判断是否可编辑
        cluster_data = list()
        es_config = get_es_config(bk_biz_id)

        def get_storage_info(cluster_id):
            used = StorageUsed.objects.filter(
                bk_biz_id=StorageUsed.CLUSTER_INFO_BIZ_ID, storage_cluster_id=cluster_id
            ).first()
            if not used:
                return {"storage_usage": 0, "storage_total": 0, "index_count": 0, "biz_count": 0}
            return {
                "storage_usage": used.storage_usage,
                "storage_total": used.storage_total,
                "index_count": used.index_count,
                "biz_count": used.biz_count,
            }

        for cluster_obj in cluster_groups:
            cluster_type = cluster_obj.get("cluster_type")

            is_append = False
            after_filter_cluster_obj = None

            if cluster_type == STORAGE_CLUSTER_TYPE:
                is_append, after_filter_cluster_obj = cls.filter_es_cluster(
                    bk_biz_id, is_default, post_visible, cluster_obj, es_config
                )
            elif cluster_type == DORIS_CLUSTER_TYPE:
                is_append, after_filter_cluster_obj = cls.filter_doris_cluster(
                    bk_biz_id, is_default, post_visible, cluster_obj
                )

            if not is_append or not after_filter_cluster_obj:
                continue

            after_filter_cluster_obj.update(
                get_storage_info(after_filter_cluster_obj["cluster_config"].get("cluster_id"))
            )

            cluster_data.append(after_filter_cluster_obj)

        return [
            cluster
            for cluster in cluster_data
            if (not enable_archive)
            or (enable_archive and cluster["cluster_config"]["custom_option"].get("enable_archive", False))
        ]

    @classmethod
    def filter_es_cluster(cls, bk_biz_id, is_default, post_visible, cluster_obj, es_config):
        from apps.log_search.handlers.index_set import IndexSetHandler

        custom_option = cluster_obj["cluster_config"]["custom_option"]

        # 判断是否有setup_config配置
        if not custom_option.get("setup_config", {}):
            custom_option["setup_config"] = {
                "retention_days_max": es_config["ES_PUBLIC_STORAGE_DURATION"],
                "retention_days_default": es_config["ES_PUBLIC_STORAGE_DURATION"],
                "number_of_replicas_max": es_config["ES_REPLICAS"],
                "number_of_replicas_default": es_config["ES_REPLICAS"],
                "es_shards_default": es_config["ES_SHARDS"],
                "es_shards_max": es_config["ES_SHARDS_MAX"],
            }
        # 判断setup_config配置里是否有es_shards配置
        if not custom_option["setup_config"].get("es_shards_default"):
            custom_option["setup_config"]["es_shards_default"] = es_config["ES_SHARDS"]
            custom_option["setup_config"]["es_shards_max"] = es_config["ES_SHARDS_MAX"]
        cluster_obj["cluster_config"]["create_time"] = StorageHandler.convert_standard_time(
            cluster_obj["cluster_config"]["create_time"]
        )
        cluster_obj["cluster_config"]["last_modify_time"] = StorageHandler.convert_standard_time(
            cluster_obj["cluster_config"]["last_modify_time"]
        )
        cluster_obj["cluster_config"]["schema"] = cluster_obj["cluster_config"].get("schema") or DEFAULT_ES_SCHEMA
        enable_hot_warm = (
            cluster_obj["cluster_config"]["custom_option"].get("hot_warm_config", {}).get("is_enabled", False)
        )
        cluster_obj["cluster_config"]["enable_hot_warm"] = enable_hot_warm

        # 公共集群：凭据信息和域名置空处理，并添加不允许编辑标签
        if cluster_obj["cluster_config"].get("registered_system") == REGISTERED_SYSTEM_DEFAULT:
            if not is_default:
                return False, cluster_obj
            if not cls.storage_visible(bk_biz_id, settings.BLUEKING_BK_BIZ_ID, post_visible=post_visible):
                return False, cluster_obj
            cluster_obj["is_editable"] = True
            cluster_obj["auth_info"]["password"] = ""
            cluster_obj["cluster_config"]["max_retention"] = es_config["ES_PUBLIC_STORAGE_DURATION"]
            # 默认集群权重：推荐集群 > 其他
            cluster_obj["priority"] = 1 if cluster_obj["cluster_config"].get("is_default_cluster") else 2
            if not cluster_obj["cluster_config"].get("custom_option", {}).get("visible_config"):
                custom_option = {
                    "visible_config": {"visible_type": VisibleEnum.ALL_BIZ.value},
                    "admin": [cluster_obj["cluster_config"]["creator"]],
                    "setup_config": {
                        "retention_days_max": es_config["ES_PUBLIC_STORAGE_DURATION"],
                        "retention_days_default": es_config["ES_PUBLIC_STORAGE_DURATION"],
                        "number_of_replicas_max": es_config["ES_REPLICAS"],
                        "number_of_replicas_default": es_config["ES_REPLICAS"],
                        "es_shards_default": settings.ES_SHARDS,
                        "es_shards_max": settings.ES_SHARDS_MAX,
                    },
                    "description": "",
                    "enable_archive": False,
                    "enable_assessment": False,
                    "source_type": EsSourceType.OTHER.value,
                    "source_name": EsSourceType.get_choice_label(EsSourceType.OTHER.value),
                }
                custom_option.update(cluster_obj["cluster_config"]["custom_option"])
                cluster_obj["cluster_config"]["custom_option"] = custom_option
            index_sets = IndexSetHandler.get_index_set_for_storage(cluster_obj["cluster_config"]["cluster_id"])
            if (
                cluster_obj["cluster_config"].get("custom_option", {}).get("visible_config", {}).get("visible_type", "")
                == VisibleEnum.MULTI_BIZ.value
            ):
                cluster_obj["cluster_config"]["custom_option"]["visible_config"]["visible_bk_biz"] = [
                    {
                        "bk_biz_id": bk_biz_id,
                        "is_use": index_sets.filter(
                            space_uid=bk_biz_id_to_space_uid(bk_biz_id), is_active=True
                        ).exists(),
                    }
                    for bk_biz_id in cluster_obj["cluster_config"]["custom_option"]["visible_config"]["visible_bk_biz"]
                ]
            cluster_obj["cluster_config"]["custom_option"]["bk_biz_id"] = settings.BLUEKING_BK_BIZ_ID
            cluster_obj["source_type"] = cluster_obj["cluster_config"]["custom_option"]["source_type"]
            cluster_obj["source_name"] = EsSourceType.get_choice_label(cluster_obj["source_type"])
            return True, cluster_obj

        # 非公共集群， 筛选bk_biz_id，密码置空处理，并添加可编辑标签
        new_custom_option = {
            "admin": [cluster_obj["cluster_config"]["creator"]],
            "setup_config": {
                "retention_days_max": es_config["ES_PUBLIC_STORAGE_DURATION"],
                "retention_days_default": es_config["ES_PUBLIC_STORAGE_DURATION"],
                "number_of_replicas_max": es_config["ES_REPLICAS"],
                "number_of_replicas_default": es_config["ES_REPLICAS"],
                "es_shards_default": settings.ES_SHARDS,
                "es_shards_max": settings.ES_SHARDS_MAX,
            },
            "description": "",
            "enable_archive": False,
            "enable_assessment": False,
            "source_type": cluster_obj["cluster_config"]["custom_option"].get("source_type", EsSourceType.OTHER.value),
            "source_name": EsSourceType.get_choice_label(custom_option.get("source_type", EsSourceType.OTHER.value)),
        }
        custom_biz_id = cluster_obj["cluster_config"]["custom_option"].get("bk_biz_id")
        custom_visible_bk_biz = cluster_obj["cluster_config"]["custom_option"].get("visible_bk_biz", [])

        if not cls.storage_visible(bk_biz_id, custom_biz_id, post_visible=post_visible):
            return False, cluster_obj

        cluster_obj["is_editable"] = True
        cluster_obj["auth_info"]["password"] = ""
        # 第三方es权重最高
        cluster_obj["priority"] = 0
        cluster_obj["bk_biz_id"] = custom_biz_id
        cluster_obj["source_type"] = cluster_obj["cluster_config"]["custom_option"].get(
            "source_type", EsSourceType.OTHER.value
        )
        cluster_obj["source_name"] = EsSourceType.get_choice_label(cluster_obj["source_type"])

        index_sets = IndexSetHandler.get_index_set_for_storage(cluster_obj["cluster_config"]["cluster_id"])

        cluster_obj["visible_bk_biz"] = [
            {
                "bk_biz_id": bk_biz_id,
                "is_use": index_sets.filter(space_uid=bk_biz_id_to_space_uid(bk_biz_id), is_active=True).exists(),
            }
            for bk_biz_id in custom_visible_bk_biz
        ]

        # 如果这个存在说明是老的可见范围配置
        if custom_visible_bk_biz:
            new_custom_option["visible_config"] = {
                "visible_type": VisibleEnum.MULTI_BIZ.value,
                "visible_bk_biz": [
                    {
                        "bk_biz_id": bk_biz_id,
                        "is_use": index_sets.filter(
                            space_uid=bk_biz_id_to_space_uid(bk_biz_id), is_active=True
                        ).exists(),
                    }
                    for bk_biz_id in custom_visible_bk_biz
                ],
            }
            new_custom_option.update(cluster_obj["cluster_config"]["custom_option"])
            cluster_obj["cluster_config"]["custom_option"] = new_custom_option
            return True, cluster_obj

        # 如果可见范围配置不存在，则直接为当前业务可见
        if not custom_option.get("visible_config"):
            new_custom_option["visible_config"] = {
                "visible_type": VisibleEnum.CURRENT_BIZ.value,
            }
            new_custom_option.update(cluster_obj["cluster_config"]["custom_option"])
            cluster_obj["cluster_config"]["custom_option"] = new_custom_option
            return True, cluster_obj

        if custom_option["visible_config"]["visible_type"] == VisibleEnum.MULTI_BIZ.value:
            custom_option["visible_config"]["visible_bk_biz"] = [
                {
                    "bk_biz_id": bk_biz_id,
                    "is_use": index_sets.filter(space_uid=bk_biz_id_to_space_uid(bk_biz_id), is_active=True).exists(),
                }
                for bk_biz_id in custom_option["visible_config"]["visible_bk_biz"]
            ]

        return True, cluster_obj

    @classmethod
    def filter_doris_cluster(cls, bk_biz_id, is_default, post_visible, cluster_obj):
        from apps.log_search.handlers.index_set import IndexSetHandler

        es_config = get_es_config(bk_biz_id)

        default_custom_option = {
            "admin": [cluster_obj["cluster_config"]["creator"]],
            "setup_config": {},
            "description": "",
            "enable_archive": False,
            "enable_assessment": False,
            "source_type": EsSourceType.OTHER.value,
        }

        cluster_obj["cluster_config"]["schema"] = cluster_obj["cluster_config"].get("schema") or DEFAULT_ES_SCHEMA

        cluster_obj["cluster_config"]["create_time"] = StorageHandler.convert_standard_time(
            cluster_obj["cluster_config"]["create_time"]
        )
        cluster_obj["cluster_config"]["last_modify_time"] = StorageHandler.convert_standard_time(
            cluster_obj["cluster_config"]["last_modify_time"]
        )

        if not cluster_obj["cluster_config"].get("custom_option"):
            cluster_obj["cluster_config"]["custom_option"] = {}

        # 公共集群: 密码空置处理, 添加不可编辑标签
        if cluster_obj["cluster_config"].get("registered_system") == REGISTERED_SYSTEM_DEFAULT:
            if not is_default:
                return False, cluster_obj

            if not cls.storage_visible(bk_biz_id, settings.BLUEKING_BK_BIZ_ID, post_visible=post_visible):
                return False, cluster_obj

            # doris 集群不可编辑（连接信息），但允许蓝鲸业务编辑可见范围
            cluster_obj["is_editable"] = False
            cluster_obj["visible_editable"] = int(bk_biz_id) == int(settings.BLUEKING_BK_BIZ_ID)
            cluster_obj["auth_info"]["password"] = ""
            cluster_obj["cluster_config"]["max_retention"] = es_config["ES_PUBLIC_STORAGE_DURATION"]
            # 默认集群权重: 推荐集群 > 其他
            cluster_obj["priority"] = 1 if cluster_obj["cluster_config"].get("is_default_cluster") else 2

            # 兼容 visible_config 上线前注册的历史公共集群
            if not cluster_obj["cluster_config"]["custom_option"].get("visible_config"):
                cluster_obj["cluster_config"]["custom_option"]["visible_config"] = {
                    "visible_type": VisibleEnum.ALL_BIZ.value
                }

            if (
                cluster_obj["cluster_config"]["custom_option"].get("visible_config", {}).get("visible_type", "")
                == VisibleEnum.MULTI_BIZ.value
            ):
                index_sets = IndexSetHandler.get_index_set_for_storage(cluster_obj["cluster_config"]["cluster_id"])
                cluster_obj["cluster_config"]["custom_option"]["visible_config"]["visible_bk_biz"] = [
                    {
                        "bk_biz_id": bk_biz_id,
                        "is_use": index_sets.filter(
                            space_uid=bk_biz_id_to_space_uid(bk_biz_id), is_active=True
                        ).exists(),
                    }
                    for bk_biz_id in cluster_obj["cluster_config"]["custom_option"]["visible_config"].get(
                        "visible_bk_biz", []
                    )
                ]

            default_custom_option.update(cluster_obj["cluster_config"]["custom_option"])
            default_custom_option["source_name"] = EsSourceType.get_choice_label(default_custom_option["source_type"])
            cluster_obj["cluster_config"]["custom_option"] = default_custom_option

            cluster_obj["cluster_config"]["custom_option"]["bk_biz_id"] = settings.BLUEKING_BK_BIZ_ID
            cluster_obj["source_type"] = cluster_obj["cluster_config"]["custom_option"]["source_type"]
            cluster_obj["source_name"] = cluster_obj["cluster_config"]["custom_option"]["source_name"]

            return True, cluster_obj

        # 非公共集群: 筛选bk_biz_id, 密码空置处理, 添加不可编辑标签
        custom_biz_id = cluster_obj["cluster_config"]["custom_option"].get("bk_biz_id")
        custom_visible_bk_biz = cluster_obj["cluster_config"]["custom_option"].get("visible_bk_biz", [])

        if not cls.storage_visible(bk_biz_id, custom_biz_id, post_visible=post_visible):
            return False, cluster_obj

        index_sets = IndexSetHandler.get_index_set_for_storage(cluster_obj["cluster_config"]["cluster_id"])

        # doris 集群不可编辑（连接信息），但允许归属业务编辑可见范围
        cluster_obj["is_editable"] = False
        cluster_obj["visible_editable"] = str(custom_biz_id) == str(bk_biz_id)
        cluster_obj["auth_info"]["password"] = ""
        # 第三方es权重最高
        cluster_obj["priority"] = 0

        cluster_obj["visible_bk_biz"] = [
            {
                "bk_biz_id": bk_biz_id,
                "is_use": index_sets.filter(space_uid=bk_biz_id_to_space_uid(bk_biz_id), is_active=True).exists(),
            }
            for bk_biz_id in custom_visible_bk_biz
        ]

        # 如果这个存在说明是老的可见范围配置
        if custom_visible_bk_biz:
            cluster_obj["cluster_config"]["custom_option"]["visible_config"] = {
                "visible_type": VisibleEnum.MULTI_BIZ.value,
                "visible_bk_biz": [
                    {
                        "bk_biz_id": bk_biz_id,
                        "is_use": index_sets.filter(
                            space_uid=bk_biz_id_to_space_uid(bk_biz_id), is_active=True
                        ).exists(),
                    }
                    for bk_biz_id in custom_visible_bk_biz
                ],
            }
        # 如果可见范围配置不存在, 则直接为当前业务可见
        elif not cluster_obj["cluster_config"]["custom_option"].get("visible_config"):
            cluster_obj["cluster_config"]["custom_option"]["visible_config"] = {
                "visible_type": VisibleEnum.CURRENT_BIZ.value,
            }
        # 如果可见范围是多业务可见，则补充业务使用情况
        elif (
            cluster_obj["cluster_config"]["custom_option"]["visible_config"].get("visible_type", "")
            == VisibleEnum.MULTI_BIZ.value
        ):
            cluster_obj["cluster_config"]["custom_option"]["visible_config"]["visible_bk_biz"] = [
                {
                    "bk_biz_id": bk_biz_id,
                    "is_use": index_sets.filter(space_uid=bk_biz_id_to_space_uid(bk_biz_id), is_active=True).exists(),
                }
                for bk_biz_id in cluster_obj["cluster_config"]["custom_option"]["visible_config"].get(
                    "visible_bk_biz", []
                )
            ]

        default_custom_option.update(cluster_obj["cluster_config"]["custom_option"])
        default_custom_option["source_name"] = EsSourceType.get_choice_label(default_custom_option["source_type"])
        cluster_obj["cluster_config"]["custom_option"] = default_custom_option

        cluster_obj["bk_biz_id"] = custom_biz_id
        cluster_obj["source_type"] = cluster_obj["cluster_config"]["custom_option"]["source_type"]
        cluster_obj["source_name"] = cluster_obj["cluster_config"]["custom_option"]["source_name"]

        return True, cluster_obj

    @staticmethod
    def storage_visible(bk_biz_id, custom_bk_biz_id, post_visible=False) -> bool:
        if post_visible:
            return True
        bk_biz_id = int(bk_biz_id)
        if not custom_bk_biz_id:
            return False

        custom_bk_biz_id = int(custom_bk_biz_id)
        return custom_bk_biz_id == bk_biz_id

    @staticmethod
    def convert_standard_time(time_stamp):
        try:
            time_zone = get_local_param("time_zone")
            return arrow.get(int(time_stamp)).to(time_zone).strftime("%Y-%m-%d %H:%M:%S%z")
        except Exception:  # pylint: disable=broad-except
            return time_stamp

    @staticmethod
    def is_platform_cluster(visible_type):
        return visible_type in [VisibleEnum.ALL_BIZ.value, VisibleEnum.BIZ_ATTR.value, VisibleEnum.MULTI_BIZ.value]

    def list(
        self,
        bk_biz_id,
        cluster_query_type=ClusterTypeEnum.ES.value,
        cluster_id=None,
        is_default=True,
        enable_archive=False,
    ):
        """
        存储集群列表
        :return:
        """
        multi_execute_func = MultiExecuteFunc()

        cluster_infos = []
        cluster_types = []

        if cluster_query_type == ClusterTypeEnum.ALL.value or cluster_query_type == ClusterTypeEnum.ES.value:
            cluster_types.append(STORAGE_CLUSTER_TYPE)

        if (
            cluster_query_type == ClusterTypeEnum.ALL.value or cluster_query_type == ClusterTypeEnum.DORIS.value
        ) and FeatureToggleObject.switch(DORIS_STORAGE_CLUSTER, bk_biz_id):
            cluster_types.append(DORIS_CLUSTER_TYPE)

        for cluster_type in cluster_types:
            params = {"cluster_type": cluster_type}
            if cluster_id:
                params["cluster_id"] = cluster_id
            multi_execute_func.append(cluster_type, TransferApi.get_cluster_info, params)

        result = multi_execute_func.run()

        for cluster_type, cluster_info_list in result.items():
            cluster_infos.extend(cluster_info_list)

        if cluster_id:
            cluster_infos = self._get_cluster_nodes(cluster_infos)
            cluster_infos = self._get_cluster_detail_info(cluster_infos, bk_biz_id=bk_biz_id)
        cluster_groups = self.filter_cluster_groups(cluster_infos, bk_biz_id, is_default, enable_archive)
        for cluster_info in cluster_groups:
            cluster_info["is_platform"] = self.is_platform_cluster(
                cluster_info["cluster_config"]["custom_option"]["visible_config"]["visible_type"]
            )
            cluster_info.setdefault("visible_editable", False)
        return cluster_groups

    def _get_cluster_nodes(self, cluster_info: builtins.list[dict]):
        for cluster in cluster_info:
            if cluster.get("cluster_type", STORAGE_CLUSTER_TYPE) == DORIS_CLUSTER_TYPE:
                continue
            cluster_id = cluster.get("cluster_config").get("cluster_id")
            nodes_stats = EsRoute(
                scenario_id=Scenario.ES, storage_cluster_id=cluster_id, raise_exception=False
            ).cluster_nodes_stats()
            if not nodes_stats:
                cluster["nodes"] = []
                continue
            cluster["nodes"] = [
                {
                    "tag": node.get("attributes", {}).get("tag", ""),
                    "attributes": node.get("attributes"),
                    "name": node["name"],
                    "ip": node["ip"],
                    "host": node["host"],
                    "roles": node["roles"],
                    "mem_total": node["os"]["mem"]["total_in_bytes"],
                    "store_total": node["fs"]["total"]["total_in_bytes"],
                }
                for node in nodes_stats["nodes"].values()
            ]
        return cluster_info

    def _get_cluster_detail_info(self, cluster_info: builtins.list[dict], bk_biz_id=None):
        cluster_ids = [
            cluster.get("cluster_config", {}).get("cluster_id")
            for cluster in cluster_info
            if cluster.get("cluster_config", {}).get("cluster_id") is not None
        ]
        try:
            bk_tenant_id = Space.get_tenant_id(bk_biz_id=int(bk_biz_id))
        except Exception:  # pylint: disable=broad-except
            logger.exception("[storage] get tenant failed, bk_biz_id=%s", bk_biz_id)
            statuses = {}
        else:
            statuses = self._get_cluster_statuses(cluster_ids, bk_biz_id, bk_tenant_id)
        for cluster in cluster_info:
            cluster_id = cluster.get("cluster_config", {}).get("cluster_id")
            status = statuses.get(cluster_id)
            cluster["cluster_stats"] = self._build_cluster_status(status)["cluster_stats"] if status else None
        return cluster_info

    @staticmethod
    def get_hot_warm_node_info(params: dict) -> (int, int):
        hot_node_num = 0
        warm_node_num = 0
        es_client = get_es_client(
            version=params["version"],
            hosts=[params["domain_name"]],
            username=params["auth_info"]["username"],
            password=params["auth_info"]["password"],
            port=params["port"],
            scheme=params["schema"],
        )
        if params.get("enable_hot_warm", False):
            hot_attr_name = params.get("hot_attr_name")
            hot_attr_value = params.get("hot_attr_value")
            warm_attr_name = params.get("warm_attr_name")
            warm_attr_value = params.get("warm_attr_value")
            nodeattrs = es_client.cat.nodeattrs(format="json", h="host,attr,value,ip")
            for nodeattr in nodeattrs:
                if nodeattr["attr"] == hot_attr_name and nodeattr["value"] == hot_attr_value:
                    hot_node_num += 1
                elif nodeattr["attr"] == warm_attr_name and nodeattr["value"] == warm_attr_value:
                    warm_node_num += 1
        else:
            nodes = es_client.cat.nodes(format="json")
            for node in nodes:
                if node.get("node.role", "").find("d") != -1:
                    hot_node_num += 1
                else:
                    warm_node_num += 1
        return hot_node_num, warm_node_num

    def sync_es_cluster(self, params: dict, is_create: bool = True) -> str:
        # 获取参数字典
        setup_config = params["setup_config"]
        bk_biz_id = params["bk_biz_id"]
        username = get_request_username()
        resource_set_id = f"{bk_biz_id}_{params['cluster_name']}" if is_create else params.pop("bkbase_cluster_id")
        cluster_name = params.get("cluster_name")
        # 获取节点信息
        hot_node_num, warm_node_num = self.get_hot_warm_node_info(params)
        # 获取管理员信息
        admin = params.get("admin", [])
        if username not in admin:
            admin.append(username)
        # 构造请求参数
        bkbase_params = {
            "bk_username": username,
            "bk_biz_id": bk_biz_id,
            "resource_set_id": resource_set_id,
            "resource_set_name": cluster_name,
            "geog_area_code": "inland",
            "category": "es",
            "provider": "user",
            "purpose": _("BKLog集群同步"),
            "share": False,
            "admin": admin,
            "tag": params.get("bkbase_tags", []) or DEFAULT_ES_TAGS,
            "connection_info": {
                "username": params["auth_info"]["username"],
                "password": params["auth_info"]["password"],
                "enable_auth": True,
                "host": params["domain_name"],
                "port": params["port"],
                "transport": DEFAULT_ES_TRANSPORT,
                "enable_replica": True if setup_config.get("number_of_replicas_default", 0) else False,
                "hot_save_days": setup_config.get("retention_days_default", 1),
                "total_shards_per_node": 1,
                "max_shard_num": hot_node_num,
                "has_cold_nodes": bool(warm_node_num),
                "has_hot_node": bool(hot_node_num),
                "hot_node_num": hot_node_num,
                "save_days": setup_config.get("retention_days_default", 1),
                "cluster_type": "es",
                "cluster_name": cluster_name,
            },
            "version": params["version"],
        }

        # 创建集群
        if is_create:
            bkbase_result = BkDataResourceCenterApi.create_resource_set(bkbase_params)
        # 更新集群
        else:
            bkbase_result = BkDataResourceCenterApi.update_resource_set(bkbase_params)
        logger.info("BkDataResourceAPI Result %s", bkbase_result)
        if not isinstance(bkbase_result, dict) or not bkbase_result.get("resource_capacity", {}).get("storage"):
            raise BKBaseStorageSyncFailed(bkbase_result)
        return bkbase_result["resource_capacity"]["storage"]["cluster_name"]

    def create(self, params):
        """
        创建集群
        :param params:
        :return:
        """
        params["domain_name"] = self.format_ipv6_es_domain_name(params["domain_name"])
        if self.check_es_exist(params):
            raise ESClusterAlreadyExistException()

        if params.get("cluster_namespace"):
            params["custom_option"]["cluster_namespace"] = params["cluster_namespace"]

        if params.get("option"):
            params["custom_option"]["option"] = params["option"]

        if params.get("create_bkbase_cluster", False):
            bkbase_cluster_id = self.sync_es_cluster(params)
            params["custom_option"]["bkbase_cluster_id"] = bkbase_cluster_id

        bk_biz_id = int(params["custom_option"]["bk_biz_id"])
        es_source_id = TransferApi.create_cluster_info(params)
        username = get_request_username()

        # add user_operation_record
        operation_record = {
            "username": username,
            "biz_id": bk_biz_id,
            "record_type": UserOperationTypeEnum.STORAGE,
            "record_object_id": int(es_source_id),
            "action": UserOperationActionEnum.CREATE,
            "params": params,
        }
        user_operation_record.delay(operation_record)

        Permission().grant_creator_action(
            resource=ResourceEnum.ES_SOURCE.create_simple_instance(
                es_source_id, attribute={"name": params.get("display_name") or params.get("cluster_name")}
            )
        )

        return es_source_id

    def update(self, params):
        """
        更新集群
        :param params:
        :return:
        """
        # 判断是否可编辑
        bk_biz_id = int(params["custom_option"]["bk_biz_id"])
        get_cluster_info_params = {"cluster_type": STORAGE_CLUSTER_TYPE, "cluster_id": int(self.cluster_id)}
        cluster_objs = TransferApi.get_cluster_info(get_cluster_info_params)
        if not cluster_objs:
            raise StorageNotExistException()

        # # 判断该集群是否可编辑
        # if cluster_objs[0]["cluster_config"].get("registered_system") == REGISTERED_SYSTEM_DEFAULT:
        #     raise StorageNotPermissionException()

        # 判断该集群是否属于该业务
        if cluster_objs[0]["cluster_config"].get("registered_system") != REGISTERED_SYSTEM_DEFAULT:
            if cluster_objs[0]["cluster_config"]["custom_option"].get("bk_biz_id") != bk_biz_id:
                raise StorageNotPermissionException()

        if cluster_objs[0]["cluster_config"].get("registered_system") == REGISTERED_SYSTEM_DEFAULT:
            if bk_biz_id != settings.BLUEKING_BK_BIZ_ID:
                raise StorageNotPermissionException()

        # 当前端传入的账号或密码为空时，取原账号密码
        if not params["auth_info"]["username"] or not params["auth_info"]["password"]:
            params["auth_info"]["username"] = cluster_objs[0]["auth_info"]["username"]
            params["auth_info"]["password"] = cluster_objs[0]["auth_info"]["password"]

        # 集群英文名不可修改, 保持原值
        params["cluster_name"] = cluster_objs[0]["cluster_config"]["cluster_name"]

        hot_warm_config_is_enabled = params["custom_option"]["hot_warm_config"]["is_enabled"]
        connect_result, version_num_str = BkLogApi.connectivity_detect(  # pylint: disable=unused-variable
            params={
                "bk_biz_id": bk_biz_id,
                "domain_name": params["domain_name"],
                "port": params["port"],
                "version_info": True,
                "schema": params["schema"],
                "cluster_id": self.cluster_id,
                "es_auth_info": {
                    "username": params["auth_info"]["username"],
                    "password": params["auth_info"]["password"],
                },
            },
        )

        # 更新信息
        raw_custom_option = cluster_objs[0]["cluster_config"]["custom_option"]

        # 原集群信息中有，新集群信息中没有时进行补充
        if raw_custom_option.get("bkbase_cluster_id"):
            params["bkbase_cluster_id"] = raw_custom_option["bkbase_cluster_id"]
            params["version"] = version_num_str
            bkbase_cluster_id = self.sync_es_cluster(params, False)
            params["custom_option"]["bkbase_cluster_id"] = bkbase_cluster_id

        # 更新Namespace信息
        if params.get("cluster_namespace"):
            params["custom_option"]["cluster_namespace"] = params["cluster_namespace"]
        elif raw_custom_option.get("cluster_namespace"):
            params["custom_option"]["cluster_namespace"] = raw_custom_option["cluster_namespace"]

        if params.get("option"):
            params["custom_option"]["option"] = params["option"]
        elif raw_custom_option.get("option"):
            params["custom_option"]["option"] = raw_custom_option["option"]

        cluster_obj = TransferApi.modify_cluster_info(params)
        cluster_obj["auth_info"]["password"] = ""
        custom_option = cluster_objs[0]["cluster_config"]["custom_option"]
        if not isinstance(custom_option, dict):
            custom_option = {}
        current_hot_warm_config_is_enabled = custom_option.get("hot_warm_config", {}).get("is_enabled", False)
        if current_hot_warm_config_is_enabled and not hot_warm_config_is_enabled:
            from apps.log_databus.tasks.collector import (
                shutdown_collector_warm_storage_config,
            )

            shutdown_collector_warm_storage_config.delay(int(self.cluster_id))
        elif not current_hot_warm_config_is_enabled and hot_warm_config_is_enabled:
            from apps.log_databus.tasks.collector import update_collector_storage_config

            update_collector_storage_config.delay(int(self.cluster_id))

        # add user_operation_record
        operation_record = {
            "username": get_request_username(),
            "biz_id": bk_biz_id,
            "record_type": UserOperationTypeEnum.STORAGE,
            "record_object_id": self.cluster_id,
            "action": UserOperationActionEnum.UPDATE,
            "params": params,
        }
        user_operation_record.delay(operation_record)

        return cluster_obj

    def update_visible_config(self, params):
        """
        仅更新 Doris 集群可见范围配置
        Doris 集群由外部（bkbase/metadata）注册，bklog 侧不创建、无域名/账号/连通性概念，
        因此此处只允许更新 custom_option.visible_config，其余字段保持原值。
        :param params: {"cluster_id", "bk_biz_id", "visible_config"}
        :return:
        """
        bk_biz_id = int(params["bk_biz_id"])

        cluster_objs = TransferApi.get_cluster_info(
            {"cluster_type": DORIS_CLUSTER_TYPE, "cluster_id": int(self.cluster_id)}
        )
        if not cluster_objs:
            raise StorageNotExistException()

        cluster_config = cluster_objs[0]["cluster_config"]
        registered_system = cluster_config.get("registered_system")
        raw_custom_option = cluster_config.get("custom_option") or {}

        # 权限校验：公共集群仅蓝鲸业务可改；非公共集群仅归属业务可改
        if registered_system == REGISTERED_SYSTEM_DEFAULT:
            if bk_biz_id != settings.BLUEKING_BK_BIZ_ID:
                raise StorageNotPermissionException()
        else:
            if raw_custom_option.get("bk_biz_id") != bk_biz_id:
                raise StorageNotPermissionException()

        # 只覆盖 visible_config，保留其余 custom_option 字段
        new_custom_option = copy.deepcopy(raw_custom_option)
        new_custom_option["visible_config"] = params["visible_config"]

        # 不传 auth_info：metadata ModifyClusterInfoResource（#11701）在 auth_info 缺省时保留原凭据；
        # 传空账号会把 bkbase 同步的真实 Doris 凭据永久覆盖为空。
        # Doris 查找权限：metadata 已放宽为 registered_system∈{调用方,_default} OR cluster_type=doris，
        # 无需再传 registered_system。create_cluster_info_before 会去掉 ESB 注入的 auth_info，避免误清凭据。
        modify_params = {
            "cluster_id": int(self.cluster_id),
            "cluster_type": DORIS_CLUSTER_TYPE,
            "custom_option": new_custom_option,
        }
        cluster_obj = TransferApi.modify_cluster_info(modify_params)

        # add user_operation_record
        operation_record = {
            "username": get_request_username(),
            "biz_id": bk_biz_id,
            "record_type": UserOperationTypeEnum.STORAGE,
            "record_object_id": self.cluster_id,
            "action": UserOperationActionEnum.UPDATE,
            "params": modify_params,
        }
        user_operation_record.delay(operation_record)

        return cluster_obj

    def destroy(self):
        from apps.log_search.handlers.index_set import IndexSetHandler

        # check index_set
        index_sets = IndexSetHandler.get_index_set_for_storage(self.cluster_id)
        if index_sets.filter(is_active=True).exists():
            raise StorageHaveResource

        # TODO 检查计算平台关联的集群

        TransferApi.delete_cluster_info({"cluster_id": self.cluster_id})

    def connectivity_detect(
        self,
        bk_biz_id,
        domain_name=None,
        port=None,
        username=None,
        password=None,
        version_info=False,
        default_auth=False,
        schema=DEFAULT_ES_SCHEMA,
        **kwargs,
    ):
        # 有传用户但是没有密码，通过接口查询该cluster密码信息
        # version_info 为True，会返回连接状态和版本信息的元组，False只返回连接状态bool
        version = ""
        if self.cluster_id:
            params = {"cluster_type": STORAGE_CLUSTER_TYPE, "cluster_id": int(self.cluster_id)}
            clusters = TransferApi.get_cluster_info(params)

            # 判断集群信息是否存在，及是否有读取改集群信息权限
            if not clusters:
                raise StorageNotExistException()

            cluster_obj = clusters[0]
            # 比较集群bk_biz_id是否匹配
            cluster_config = cluster_obj["cluster_config"]
            if not self.can_visible(
                bk_biz_id, cluster_config.get("custom_option", {}), cluster_config["registered_system"]
            ):
                raise StorageNotPermissionException()

            # 集群不可以修改域名、端口
            domain_name = cluster_config["domain_name"]
            port = cluster_config["port"]

            # 现有集群用户不修改密码则使用集群现有密码
            if username and not password:
                password = cluster_obj["auth_info"]["password"]

            # 兼容批量连通性测试，使用存储凭据信息
            if default_auth:
                username = cluster_obj["auth_info"].get("username")
                password = cluster_obj["auth_info"].get("password")
                # 新增批量获取状态时schema
                schema = cluster_config.get("schema") or DEFAULT_ES_SCHEMA
            version = cluster_config.get("version", "")

        connect_result = self._send_detective(version, domain_name, port, username, password, version_info, schema)
        return connect_result

    def list_node_attrs(
        self,
        bk_biz_id,
        domain_name=None,
        port=None,
        username=None,
        password=None,
        default_auth=False,
        schema=DEFAULT_ES_SCHEMA,
        **kwargs,
    ):
        """
        获取集群各节点的属性
        """
        # 有传用户但是没有密码，通过接口查询该cluster密码信息
        version = ""
        if self.cluster_id:
            params = {"cluster_type": STORAGE_CLUSTER_TYPE, "cluster_id": int(self.cluster_id)}
            cluster_obj = TransferApi.get_cluster_info(params)[0]

            # 判断集群信息是否存在，及是否有读取改集群信息权限
            if not cluster_obj:
                raise StorageNotExistException()

            # 比较集群bk_biz_id是否匹配
            cluster_config = cluster_obj["cluster_config"]
            if not self.can_visible(
                bk_biz_id, cluster_config.get("custom_option", {}), cluster_config["registered_system"]
            ):
                raise StorageNotPermissionException()

            # 集群不可以修改域名、端口
            domain_name = cluster_config["domain_name"]
            port = cluster_config["port"]

            # 现有集群用户不修改密码则使用集群现有密码
            if username and not password:
                password = cluster_obj["auth_info"]["password"]

            # 兼容批量连通性测试，使用存储凭据信息
            if default_auth:
                username = cluster_obj["auth_info"].get("username")
                password = cluster_obj["auth_info"].get("password")

            version = cluster_config.get("version", "")

        es_client = get_es_client(
            version=version, hosts=[domain_name], username=username, password=password, scheme=schema, port=port
        )
        # 数据节点
        datanode_list = []
        filter_datanode_list = []
        # 尝试获取节点设置
        try:
            data = es_client.transport.perform_request("GET", "/_nodes/settings")
            nodes = data["nodes"]
            for node_key, node_info in nodes.items():
                node = node_info["settings"]["node"]
                attr = node_info["settings"]["node"]["attr"]
                additional_params = {
                    "id": node_key,
                    "name": node_info["name"],
                    "ip": node_info["ip"],
                    "host": node_info["host"],
                }
                result = self.flatten_json(attr, additional_params)
                # 是否存在 data key
                if "data" in node:
                    if node["data"] == "true":
                        datanode_list.extend(result)
                # 不存在 data key 也添加
                else:
                    datanode_list.extend(result)
        except Exception as e:
            raise NodeSettingException(NodeSettingException.MESSAGE.format(error_info=e))
        else:
            # 筛选节点
            for node in datanode_list:
                # 对节点属性进行过滤，有些是内置的，需要忽略
                if any(node["attr"].startswith(prefix) for prefix in NODE_ATTR_PREFIX_BLACKLIST):
                    continue  # 如果以黑名单前缀开头则跳过
                filter_datanode_list.append(node)
        return filter_datanode_list

    @staticmethod
    def flatten_json(json_data, additional_params=None):
        out = []

        def flatten(x, name=""):
            if isinstance(x, dict):
                for key in x:
                    flatten(x[key], name + key + ".")
            elif isinstance(x, list):
                for i, item in enumerate(x):
                    flatten(item, name + str(i) + ".")
            else:
                # 将额外参数与当前的 attr 和 value 结合
                entry = {"attr": name[:-1], "value": x}
                if additional_params:
                    entry.update(additional_params)
                out.append(entry)

        flatten(json_data)
        return out

    @classmethod
    def batch_connectivity_detect(cls, cluster_list, bk_biz_id):
        """
        :param cluster_list:
        :param bk_biz_id:
        :return:
        """
        cluster_list = list(dict.fromkeys(cluster_list))
        result = {cluster_id: {"status": False, "cluster_stats": None} for cluster_id in cluster_list}
        bk_biz_id = int(bk_biz_id)
        try:
            bk_tenant_id = Space.get_tenant_id(bk_biz_id=bk_biz_id)
        except Exception:  # pylint: disable=broad-except
            logger.exception("[storage] get tenant failed, bk_biz_id=%s", bk_biz_id)
            return result

        visible_cluster_ids = cls._get_visible_cluster_ids(cluster_list, bk_biz_id, bk_tenant_id)
        statuses = cls._get_cluster_statuses(visible_cluster_ids, bk_biz_id, bk_tenant_id)
        result.update({cluster_id: cls._build_cluster_status(status) for cluster_id, status in statuses.items()})
        return result

    @classmethod
    def _get_visible_cluster_ids(cls, cluster_list, bk_biz_id, bk_tenant_id):
        requested_cluster_ids = set(cluster_list)
        try:
            cluster_infos = TransferApi.get_cluster_info({}, bk_tenant_id=bk_tenant_id)
        except Exception:  # pylint: disable=broad-except
            logger.exception(
                "[storage] get cluster infos for visibility failed, bk_biz_id=%s, bk_tenant_id=%s",
                bk_biz_id,
                bk_tenant_id,
            )
            return []

        visible_cluster_ids = []
        handler = cls()
        for cluster_info in cluster_infos:
            cluster_config = cluster_info.get("cluster_config") or {}
            cluster_id = cluster_config.get("cluster_id")
            if cluster_id not in requested_cluster_ids:
                continue
            try:
                if handler.can_visible(
                    bk_biz_id,
                    cluster_config.get("custom_option") or {},
                    cluster_config.get("registered_system"),
                ):
                    visible_cluster_ids.append(cluster_id)
            except Exception:  # pylint: disable=broad-except
                logger.exception(
                    "[storage] check cluster visibility failed, bk_biz_id=%s, cluster_id=%s",
                    bk_biz_id,
                    cluster_id,
                )
        return visible_cluster_ids

    @classmethod
    def _get_cluster_statuses(cls, cluster_list, bk_biz_id, bk_tenant_id):
        cluster_list = list(dict.fromkeys(cluster_list))
        if not cluster_list:
            return {}

        cache_keys = {
            cluster_id: cls._get_cluster_status_cache_key(bk_tenant_id, bk_biz_id, cluster_id)
            for cluster_id in cluster_list
        }
        try:
            cached_statuses = cache.get_many(cache_keys.values())
        except Exception:  # pylint: disable=broad-except
            logger.exception("[storage] get cluster status cache failed")
            cached_statuses = {}

        result = {
            cluster_id: cached_statuses[cache_key]
            for cluster_id, cache_key in cache_keys.items()
            if cache_key in cached_statuses and isinstance(cached_statuses[cache_key], dict)
        }
        missing_cluster_ids = [cluster_id for cluster_id in cluster_list if cluster_id not in result]
        if not missing_cluster_ids:
            return result

        multi_execute_func = MultiExecuteFunc(max_workers=METADATA_CLUSTER_STATUS_MAX_WORKERS)
        for start in range(0, len(missing_cluster_ids), METADATA_CLUSTER_STATUS_BATCH_SIZE):
            cluster_ids = missing_cluster_ids[start : start + METADATA_CLUSTER_STATUS_BATCH_SIZE]
            multi_execute_func.append(
                start,
                cls._get_cluster_status_batch,
                {
                    "cluster_ids": cluster_ids,
                    "bk_biz_id": bk_biz_id,
                    "bk_tenant_id": bk_tenant_id,
                },
            )

        fetched_statuses = {}
        for batch_result in multi_execute_func.run(return_exception=True).values():
            if isinstance(batch_result, Exception):
                logger.error("[storage] get cluster status batch failed: %s", batch_result)
                continue
            fetched_statuses.update(batch_result)

        for cluster_id in missing_cluster_ids:
            fetched_statuses.setdefault(cluster_id, cls._unavailable_cluster_status(cluster_id))
        result.update(fetched_statuses)

        try:
            cache.set_many(
                {cache_keys[cluster_id]: fetched_statuses[cluster_id] for cluster_id in missing_cluster_ids},
                CACHE_EXPIRE_TIME,
            )
        except Exception:  # pylint: disable=broad-except
            logger.exception("[storage] set cluster status cache failed")
        return result

    @staticmethod
    def _get_cluster_status_cache_key(bk_tenant_id, bk_biz_id, cluster_id):
        return f"connect_info_{bk_tenant_id}_{bk_biz_id}_{cluster_id}"

    @classmethod
    def _get_cluster_status_batch(cls, params):
        cluster_ids = params["cluster_ids"]
        requested_cluster_ids = set(cluster_ids)
        try:
            statuses = TransferApi.get_cluster_status(
                {"cluster_ids": cluster_ids, "bk_biz_id": params["bk_biz_id"]},
                bk_tenant_id=params["bk_tenant_id"],
            )
        except Exception:  # pylint: disable=broad-except
            logger.exception("[storage] get cluster statuses failed, cluster_ids=%s", cluster_ids)
            statuses = []

        result = {}
        for status in statuses:
            cluster_id = status.get("cluster_id")
            if cluster_id not in requested_cluster_ids:
                continue
            result[cluster_id] = status
        for cluster_id in cluster_ids:
            result.setdefault(cluster_id, cls._unavailable_cluster_status(cluster_id))
        return result

    @staticmethod
    def _unavailable_cluster_status(cluster_id):
        return {
            "cluster_id": cluster_id,
            "cluster_type": None,
            "is_available": False,
        }

    @staticmethod
    def _build_cluster_status(status):
        details = status.get("details") or {}
        nodes = status.get("nodes") or {}
        capacity = status.get("capacity") or {}
        if status.get("cluster_type") == DORIS_CLUSTER_TYPE:
            is_available = bool(status.get("is_available"))
            storage_status = status.get("status")
            health_status = "yellow" if storage_status == "degraded" else ("green" if is_available else "red")
            return {
                "status": is_available,
                "cluster_stats": {
                    "node_count": nodes.get("total"),
                    "available_node_count": nodes.get("available"),
                    "shards_total": None,
                    "shards_pri": None,
                    "data_node_count": nodes.get("total"),
                    "indices_count": None,
                    "indices_docs_count": None,
                    "indices_store": details.get("data_used_bytes"),
                    "total_store": capacity.get("total_bytes"),
                    "available_store": capacity.get("available_bytes"),
                    "used_store": capacity.get("used_bytes"),
                    "used_percent": capacity.get("used_percent"),
                    "tablet_count": details.get("tablet_count"),
                    "max_disk_used_percent": details.get("max_disk_used_percent"),
                    "status": health_status,
                    "storage_status": storage_status,
                },
            }
        if status.get("cluster_type") != STORAGE_CLUSTER_TYPE:
            return {"status": bool(status.get("is_available")), "cluster_stats": None}

        shard_values = [
            details.get("active_shards"),
            details.get("initializing_shards"),
            details.get("unassigned_shards"),
        ]
        shards_total = (
            sum(value for value in shard_values if value is not None)
            if any(value is not None for value in shard_values)
            else None
        )
        return {
            "status": bool(status.get("is_available")),
            "cluster_stats": {
                "node_count": details.get("number_of_nodes"),
                "shards_total": shards_total,
                "shards_pri": None,
                "data_node_count": nodes.get("total"),
                "indices_count": None,
                "indices_docs_count": None,
                "indices_store": details.get("indices_store_bytes"),
                "total_store": capacity.get("total_bytes"),
                "status": details.get("health_status"),
            },
        }

    @classmethod
    def get_result_table_indices(cls, table_id):
        return cls.get_result_tables_indices([table_id]).get(table_id, [])

    @classmethod
    def get_result_tables_indices(cls, table_ids):
        table_ids = list(dict.fromkeys(table_ids))
        result = {table_id: [] for table_id in table_ids}
        for start in range(0, len(table_ids), METADATA_RESULT_TABLE_STATUS_BATCH_SIZE):
            batch_table_ids = table_ids[start : start + METADATA_RESULT_TABLE_STATUS_BATCH_SIZE]
            try:
                storage_status = TransferApi.get_result_table_storage_status({"table_ids": batch_table_ids})
            except Exception:  # pylint: disable=broad-except
                logger.exception(
                    "[storage] get result table storage statuses failed, table_ids=%s",
                    batch_table_ids,
                )
                continue
            returned_table_ids = set()
            for item in storage_status.get("items", []):
                table_id = item.get("table_id")
                if table_id not in result:
                    continue
                returned_table_ids.add(table_id)
                result[table_id] = cls._get_result_table_indices_from_status(item)
            missing_table_ids = [table_id for table_id in batch_table_ids if table_id not in returned_table_ids]
            if missing_table_ids:
                logger.error(
                    "[storage] result table storage statuses missing items, table_ids=%s",
                    missing_table_ids,
                )
        return result

    @classmethod
    def _get_result_table_indices_from_status(cls, item):
        if not item or item.get("error"):
            logger.error(
                "[storage] get result table storage status failed, table_id=%s, item=%s",
                item.get("table_id") if item else None,
                item,
            )
            return []

        data = item.get("data") or {}
        storage_configs = data.get("storage_configs") or {}
        default_storage = (data.get("result_table") or {}).get("default_storage")
        configured_storage_types = {
            storage_type for storage_type, storage_config in storage_configs.items() if storage_config
        }
        if default_storage is None:
            # 只有「唯一配置存储」这一无歧义场景才回退推导，双存储并存时宁可返回空也不猜
            if len(configured_storage_types) != 1:
                logger.warning(
                    "[storage] skip result table indices without unambiguous default storage, "
                    "table_id=%s, configured_storage_types=%s",
                    item.get("table_id"),
                    sorted(configured_storage_types),
                )
                return []
            default_storage = next(iter(configured_storage_types))
        if default_storage not in (STORAGE_CLUSTER_TYPE, DORIS_CLUSTER_TYPE):
            return []

        storage_config = storage_configs.get(default_storage) or {}
        cluster_id = storage_config.get("storage_cluster_id")
        cluster_results = data.get("cluster_results") or {}
        cluster_status = cluster_results.get(str(cluster_id)) or cluster_results.get(cluster_id) or {}

        if default_storage == DORIS_CLUSTER_TYPE:
            return cls._build_doris_storage_rows(cluster_status)
        return cls._build_es_storage_rows(cluster_status)

    @classmethod
    def _build_es_storage_rows(cls, cluster_status):
        runtime = cluster_status.get("runtime") or {}
        indices = (runtime.get("indices") or {}).get("items") or []
        health_unavailable = (
            cluster_status.get("runtime_skipped")
            or bool(cluster_status.get("errors"))
            or any(
                isinstance(warning, dict) and warning.get("code") == "INDEX_CAT_UNAVAILABLE"
                for warning in cluster_status.get("warnings") or []
            )
        )
        return cls.sort_indices(
            [cls._build_result_table_index(index, health_unavailable=health_unavailable) for index in indices]
        )

    @staticmethod
    def _build_result_table_index(index, health_unavailable=False):
        health = index.get("health")
        if not health or (health_unavailable and health not in {"red", "yellow"}):
            health = "--"
        return {
            "index": index.get("index"),
            "uuid": index.get("uuid"),
            "health": health,
            "status": index.get("status"),
            "pri": str(index.get("primary_shards") or 0),
            "rep": str(index.get("replica_factor") or 0),
            "docs.count": str(index.get("docs_count") or 0),
            "docs.deleted": str(index.get("docs_deleted") or 0),
            "store.size": str(index.get("store_size_bytes") or 0),
            "pri.store.size": str(index.get("primary_store_size_bytes") or 0),
        }

    @classmethod
    def _build_doris_storage_rows(cls, cluster_status):
        """把 Doris 物理表 / 分区适配成与 ES 物理索引一致的行结构，前端不感知存储类型"""
        runtime = cluster_status.get("runtime") or {}
        health, status = cls._get_doris_storage_health(cluster_status)
        physical_table_name = cls._get_doris_physical_table_name(runtime)

        partitions = runtime.get("partitions") or []
        if partitions:
            rows = [
                (
                    cls._doris_row_sort_key(partition),
                    cls._build_doris_storage_row(
                        name=partition.get("name"),
                        physical_table_name=physical_table_name,
                        rows_count=partition.get("rows"),
                        data_length_bytes=partition.get("data_length_bytes"),
                        index_length_bytes=partition.get("index_length_bytes"),
                        health=health,
                        status=status,
                    ),
                )
                for partition in partitions
            ]
            return [row for _, row in sorted(rows, key=operator.itemgetter(0), reverse=True)]

        # 无分区表不返回空列表，用物理表兜底一行，避免前端把「无分区」误判为「接口无数据」
        table = runtime.get("table") or {}
        if not table:
            return []
        return [
            cls._build_doris_storage_row(
                name=physical_table_name,
                physical_table_name=physical_table_name,
                rows_count=table.get("rows"),
                data_length_bytes=table.get("data_length_bytes"),
                index_length_bytes=table.get("index_length_bytes"),
                health=health,
                status=status,
            )
        ]

    @staticmethod
    def _build_doris_storage_row(
        name, physical_table_name, rows_count, data_length_bytes, index_length_bytes, health, status
    ):
        store_size = StorageHandler._to_int(data_length_bytes) + StorageHandler._to_int(index_length_bytes)
        return {
            "index": name,
            "uuid": f"doris:{physical_table_name}:{name}" if physical_table_name and name else None,
            "health": health,
            "status": status,
            # Doris 没有分片概念，也不统计删除文档数，用现有占位值保持前端渲染不变
            "pri": DORIS_STORAGE_ROW_PLACEHOLDER,
            "rep": DORIS_STORAGE_ROW_PLACEHOLDER,
            "docs.count": str(StorageHandler._to_int(rows_count)),
            "docs.deleted": DORIS_STORAGE_ROW_PLACEHOLDER,
            "store.size": str(store_size),
            "pri.store.size": DORIS_STORAGE_ROW_PLACEHOLDER,
        }

    @staticmethod
    def _doris_row_sort_key(partition):
        update_time = partition.get("update_time")
        # 缺少更新时间的分区统一排在有时间的分区之后
        return bool(update_time), str(update_time or ""), str(partition.get("name") or "")

    @staticmethod
    def _get_doris_physical_table_name(runtime):
        binding = runtime.get("binding") or {}
        physical_table_name = binding.get("physical_table_name")
        if physical_table_name:
            return physical_table_name
        table = runtime.get("table") or {}
        schema, name = table.get("schema"), table.get("name")
        if schema and name:
            return f"{schema}.{name}"
        return name or None

    @staticmethod
    def _get_doris_storage_health(cluster_status):
        """Doris 健康状态由连通性与 runtime 告警推导，对外沿用 ES 的 green/yellow/red/-- 口径"""
        if cluster_status.get("runtime_skipped"):
            return "--", "unknown"
        connectivity = cluster_status.get("connectivity")
        if connectivity is not None and not connectivity.get("is_connected", False):
            return "red", "unavailable"
        if cluster_status.get("errors"):
            return "red", "unavailable"
        if connectivity is None:
            return "--", "unknown"
        if cluster_status.get("warnings"):
            return "yellow", "open"
        return "green", "open"

    @staticmethod
    def _to_int(value):
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

    def _send_detective(
        self,
        version: str,
        domain_name: str,
        port: int,
        username="",
        password="",
        version_info=False,
        schema=DEFAULT_ES_SCHEMA,
    ) -> bool | tuple:
        # socket ping
        es_socket_ping(host=domain_name, port=port)
        # 利用es_client对用户名和密码的连通性进行验证, version默认走es7
        es_client = get_es_client(
            version=version, hosts=[domain_name], username=username, password=password, port=port, scheme=schema
        )
        es_client_ping(es_client)

        if not version_info:
            return True, ""
        else:
            info_dict = es_client.info()
            version_number: str = self.dump_version_info(info_dict, domain_name, port)
            return True, version_number

    def dump_version_info(self, info_dict: dict, domain_name: str, port: int) -> str:
        if info_dict:
            version = info_dict.get("version")
            if version:
                number = version.get("number")
            else:
                raise StorageUnKnowEsVersionException(
                    StorageUnKnowEsVersionException.MESSAGE.format(ip=domain_name, port=port)
                )
        else:
            raise StorageUnKnowEsVersionException(
                StorageUnKnowEsVersionException.MESSAGE.format(ip=domain_name, port=port)
            )

        return number

    def get_cluster_info_by_id(self):
        """
        根据集群ID查询集群信息，密码返回
        :return:
        """
        cluster_info = TransferApi.get_cluster_info({"cluster_id": self.cluster_id})
        if not cluster_info:
            raise StorageNotExistException()
        return cluster_info[0]

    def get_cluster_info_by_table(self, table_id):
        """
        根据result_table_id查询集群信息
        :return:
        """
        storage_cluster_type = CollectorConfig.get_storage_cluster_type_by_table_id(table_id)
        cluster_info = TransferApi.get_result_table_storage(
            {"result_table_list": table_id, "storage_type": storage_cluster_type}
        )
        if not cluster_info.get(table_id):
            raise StorageNotExistException()
        return cluster_info[table_id]

    @classmethod
    def get_storage_capacity(cls, bk_biz_id, storage_clusters):
        storage = {"storage_capacity": 0, "storage_used": 0}
        if int(settings.ES_STORAGE_CAPACITY) <= 0:
            return storage
        biz_storage = StorageCapacity.objects.filter(bk_biz_id=bk_biz_id).first()
        storage["storage_capacity"] = int(settings.ES_STORAGE_CAPACITY)
        if biz_storage:
            storage["storage_capacity"] = biz_storage.storage_capacity

        storage_used = (
            StorageUsed.objects.filter(bk_biz_id=bk_biz_id, storage_cluster_id__in=storage_clusters)
            .all()
            .aggregate(total=Sum("storage_used"))
        )
        if storage_used:
            storage["storage_used"] = round(storage_used.get("total", 0) or 0, 2)
        return storage

    def cluster_nodes(self):
        result = EsRoute(scenario_id=Scenario.ES, storage_cluster_id=self.cluster_id).cluster_nodes_stats()
        return [
            {
                "name": node["name"],
                "ip": node["host"],
                "cpu_use": node["os"]["cpu"]["percent"],
                "disk_use": node["fs"]["total"]["available_in_bytes"] / node["fs"]["total"]["total_in_bytes"],
                "jvm_mem_use": node["jvm"]["mem"]["heap_used_percent"],
                "tag": node["attributes"].get("tag", ""),
            }
            for node in result.get("nodes").values()
        ]

    def indices(self):
        indices_info = EsRoute(scenario_id=Scenario.ES, storage_cluster_id=self.cluster_id).cat_indices()
        indices_info = self.sort_indices(indices_info)
        ret = defaultdict(dict)
        other_indices = {"index_pattern": "other", "indices": []}
        for indices in indices_info:
            is_bklog_rt, rt = self._match_bklog_indices(indices["index"])
            if is_bklog_rt and not indices["index"].startswith("write"):
                ret[rt]["index_pattern"] = rt
                ret[rt].setdefault("indices", []).append(indices)
                continue
            other_indices["indices"].append(indices)
        result = []
        for index in ret.values():
            result.append(index)
        result.append(other_indices)
        return result

    def _match_bklog_indices(self, index: str) -> (bool, str):
        pattern = re.compile(BKLOG_RESULT_TABLE_PATTERN)
        match = pattern.findall(index)
        if match:
            return True, match[0]
        return False, ""

    @staticmethod
    def sort_indices(indices: list):
        def compare_indices_by_date(index_a, index_b):
            index_a = index_a.get("index")
            index_b = index_b.get("index")

            def convert_to_normal_date_tuple(index_name) -> tuple:
                # example 1: 2_bklog_xxxx_20200321_1 -> (20200321, 1)
                # example 2: 2_xxxx_2020032101 -> (20200321, 1)
                result = re.findall(r"(\d{8})_(\d{1,7})$", index_name) or re.findall(r"(\d{8})(\d{2})$", index_name)
                if result:
                    return result[0][0], int(result[0][1])
                # not match
                return index_name, 0

            converted_index_a = convert_to_normal_date_tuple(index_a)
            converted_index_b = convert_to_normal_date_tuple(index_b)

            return (converted_index_a > converted_index_b) - (converted_index_a < converted_index_b)

        return sorted(indices, key=functools.cmp_to_key(compare_indices_by_date), reverse=True)

    def repository(self, bk_biz_id=None, cluster_id=None):
        cluster_info = self.get_cluster_groups(bk_biz_id)
        if not cluster_info:
            return []
        if cluster_id:
            cluster_info = [cluster for cluster in cluster_info if cluster["storage_cluster_id"] == cluster_id]
        cluster_info_by_id = {cluster["storage_cluster_id"]: cluster for cluster in cluster_info}
        repository_info = TransferApi.list_es_snapshot_repository({"cluster_ids": list(cluster_info_by_id.keys())})
        name_prefix = f"{bk_biz_id}_bklog_"
        result = []

        for repository in repository_info:
            repository.pop("settings", None)
            # 需要兼容历史的仓库名称
            if not repository["repository_name"].startswith(name_prefix) and "bklog" in repository["repository_name"]:
                continue
            repository.update(
                {
                    "cluster_name": cluster_info_by_id[repository["cluster_id"]]["storage_cluster_name"],
                    "display_name": cluster_info_by_id[repository["cluster_id"]]["storage_display_name"],
                    "cluster_source_name": EsSourceType.get_choice_label(
                        cluster_info_by_id[repository["cluster_id"]].get("source_type")
                    ),
                    "cluster_source_type": cluster_info_by_id[repository["cluster_id"]].get("source_type"),
                    "create_time": format_user_time_zone(
                        repository["create_time"], get_local_param("time_zone", settings.TIME_ZONE)
                    ),
                }
            )
            result.append(repository)
        return result

    def format_ipv6_es_domain_name(self, domain_name: str):
        """
        当es域名为ipv6地址时, 将ipv6地址转换为long形式
        :param domain_name: es地址, 可能是 ipv4, ipv6, 域名
        :return:
        """

        try:
            ipaddr = ipaddress.IPv6Address(domain_name)
            domain_name = ipaddr.exploded
        except ipaddress.AddressValueError:
            return domain_name

        return domain_name

    def check_es_exist(self, params):
        """
        检查es集群是否存在
        params: 创建集群的参数
        """

        domain_name = self.format_ipv6_es_domain_name(params["domain_name"])
        port = params["port"]

        exist_clusters = TransferApi.get_cluster_info({"cluster_type": STORAGE_CLUSTER_TYPE, "no_request": True})
        if not exist_clusters:
            return False
        for exist_cluster in exist_clusters:
            exist_cluster_name = self.format_ipv6_es_domain_name(exist_cluster["cluster_config"]["domain_name"])
            exist_cluster_port = exist_cluster["cluster_config"]["port"]
            if domain_name == exist_cluster_name and port == exist_cluster_port:
                return True

        return False
