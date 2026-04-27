"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸智云 - Resource SDK (BlueKing - Resource SDK) available.
Copyright (C) 2017-2025 Tencent,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the
specific language governing permissions and limitations under the License.
We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.
"""

import abc
import re
from typing import Any

from django.conf import settings

from apm.models import DataLink
from bkmonitor.utils.tenant import bk_biz_id_to_bk_tenant_id
from bkm_space.utils import bk_biz_id_to_space_uid, is_bk_saas_space, parse_space_uid
from bkm_space.define import SpaceTypeEnum
from core.drf_resource import resource
from apm.core.handlers.serializers import ApplicationStorageRouteSerializer


class ApplicationHelper:
    DEFAULT_CLUSTER_TYPE = "elasticsearch"
    DEFAULT_CLUSTER_NAME = "_default"
    # 业务下默认应用的应用名称
    DEFAULT_APPLICATION_NAME = "default_app"

    @classmethod
    def get_default_cluster_id(cls, bk_biz_id: int, app_name: str | None = None):
        """
        从DataLink/集群列表中获取默认集群
        """
        if app_name:
            for _route_dict in settings.APM_APP_STORAGE_ROUTES:
                s = ApplicationStorageRouteSerializer(data=_route_dict)
                if not s.is_valid():
                    continue
                route_dict = s.validated_data
                rule_dict: dict[str, Any] = route_dict["rule"]
                if (
                    rule_dict["space_type"] == SpaceTypeEnum.BKSAAS.value
                    and is_bk_saas_space(bk_biz_id_to_space_uid(bk_biz_id))
                    and re.match(rule_dict["name__reg"], app_name)
                ):
                    return route_dict["storage"]["es_storage_cluster_id"]
        datalink = DataLink.get_data_link(bk_biz_id)
        if datalink and datalink.elasticsearch_cluster_id:
            return datalink.elasticsearch_cluster_id

        clusters = resource.metadata.query_cluster_info(
            bk_tenant_id=bk_biz_id_to_bk_tenant_id(bk_biz_id),
            cluster_type=cls.DEFAULT_CLUSTER_TYPE,
            # 兼容metadata逻辑
            registered_system=settings.APP_CODE,
        )
        return next(
            (
                i.get("cluster_config").get("cluster_id")
                for i in clusters
                if i.get("cluster_config", {}).get("registered_system") == cls.DEFAULT_CLUSTER_NAME
            ),
            None,
        )

    @classmethod
    def get_default_storage_config(cls, bk_biz_id: int, app_name: str | None = None):
        """获取默认的集群配置"""
        es_storage_cluster = settings.APM_APP_DEFAULT_ES_STORAGE_CLUSTER
        if not es_storage_cluster or es_storage_cluster == -1:
            # 默认集群从集群列表中选择
            default_cluster_id = ApplicationHelper.get_default_cluster_id(bk_biz_id, app_name)
            if default_cluster_id:
                es_storage_cluster = default_cluster_id

        # 填充默认存储集群
        return {
            "es_storage_cluster": es_storage_cluster,
            "es_retention": settings.APM_APP_DEFAULT_ES_RETENTION,
            "es_number_of_replicas": settings.APM_APP_DEFAULT_ES_REPLICAS,
            "es_shards": settings.APM_APP_DEFAULT_ES_SHARDS,
            "es_slice_size": settings.APM_APP_DEFAULT_ES_SLICE_LIMIT,
        }

    @classmethod
    def create_default_application(cls, bk_biz_id):
        """创建默认应用"""

        from apm_web.models import Application

        application = Application.objects.filter(bk_biz_id=bk_biz_id, app_name=cls.DEFAULT_APPLICATION_NAME).first()
        if application:
            # 存在默认应用 直接返回
            return application

        from apm.resources import CreateApplicationSimpleResource

        CreateApplicationSimpleResource()(bk_biz_id=bk_biz_id, app_name=cls.DEFAULT_APPLICATION_NAME)
        return Application.objects.filter(bk_biz_id=bk_biz_id, app_name=cls.DEFAULT_APPLICATION_NAME).first()


class SharedDatasourceRule(abc.ABC):
    """共享数据源匹配规则抽象基类

    子类通过 TYPE_KEY 声明规则类型，从 params 字典中按约定键名读取自身所需参数

    :cvar TYPE_KEY: 规则类型标识，对应配置中 rules 列表每一项的 type 字段
    """

    TYPE_KEY: str = ""

    def __init__(self, params: dict[str, Any]):
        self.params = params or {}

    @abc.abstractmethod
    def match(self, bk_biz_id: int, app_name: str) -> bool:
        """判断当前应用是否命中该规则"""


class SpaceTypeRule(SharedDatasourceRule):
    """空间类型规则

    从 params.space_types 读取允许的空间类型列表（如 ["bksaas"]），业务所属空间类型命中任一即返回 True
    """

    TYPE_KEY = "SPACE_TYPE"

    def match(self, bk_biz_id: int, app_name: str) -> bool:
        space_uid = bk_biz_id_to_space_uid(bk_biz_id)
        if not space_uid:
            return False
        space_type, _ = parse_space_uid(space_uid)
        return space_type in self.params.get("space_types", [])


class AppNamePrefixRule(SharedDatasourceRule):
    """应用名前缀规则

    从 params.prefixes 读取允许的前缀列表，应用名以任一前缀开头即返回 True
    """

    TYPE_KEY = "APP_NAME_PREFIX"

    def match(self, bk_biz_id: int, app_name: str) -> bool:
        return any(app_name.startswith(prefix) for prefix in self.params.get("prefixes", []))


class SharedDatasourceRuleFactory:
    """共享数据源规则工厂

    按 settings.APM_SHARED_DATASOURCE_RULES 配置逐个数据源类型进行求值。
    注：每个数据源类型下的 group 之间为 OR 关系（任一命中即该类型需共享），单个 group 内的 rules 通过 connector(AND/OR) 组合
    """

    BUILDER_REGISTER: dict[str, type[SharedDatasourceRule]] = {
        SpaceTypeRule.TYPE_KEY: SpaceTypeRule,
        AppNamePrefixRule.TYPE_KEY: AppNamePrefixRule,
    }

    @classmethod
    def list_shared_datasource_types(cls, bk_biz_id: int, app_name: str) -> list[str]:
        """应用需共享的数据源类型

        按配置逐个数据源类型独立求值，返回命中共享规则的数据源类型列表

        :param bk_biz_id: 业务 ID
        :param app_name: 应用名
        :return: 命中共享规则的数据源类型列表（如 ["trace", "log"]）；全部未命中时返回空列表
        """
        rules_config: dict[str, Any] = settings.APM_SHARED_DATASOURCE_RULES or {}

        shared_types: list[str] = []
        for datasource_type, type_config in rules_config.items():
            groups: list[dict[str, Any]] = type_config.get("list", [])
            if cls._match_any_group(groups, bk_biz_id, app_name):
                shared_types.append(datasource_type)
        return shared_types

    @classmethod
    def _match_any_group(cls, groups: list[dict[str, Any]], bk_biz_id: int, app_name: str) -> bool:
        """数据源类型级匹配

        group 间为 OR 关系，任一 group 命中即返回 True
        """
        for group in groups:
            if cls._match_group(group, bk_biz_id, app_name):
                return True
        return False

    @classmethod
    def _match_group(cls, group: dict[str, Any], bk_biz_id: int, app_name: str) -> bool:
        """单 group 内匹配

        根据 connector 对 rules 进行 AND / OR 组合；非法 connector 或空 rules 视为不命中
        """
        connector: str = group.get("connector", "AND")
        rule_configs: list[dict[str, Any]] = group.get("rules", [])
        if not rule_configs:
            return False

        rule_results = (cls._match_rule(rule_config, bk_biz_id, app_name) for rule_config in rule_configs)
        if connector == "AND":
            return all(rule_results)
        if connector == "OR":
            return any(rule_results)
        return False

    @classmethod
    def _match_rule(cls, rule_config: dict[str, Any], bk_biz_id: int, app_name: str) -> bool:
        """单规则匹配

        未注册的规则类型视为不命中，避免误判
        """
        rule_cls = cls.BUILDER_REGISTER.get(rule_config.get("type"))
        if not rule_cls:
            return False
        rule = rule_cls(params=rule_config.get("params", {}))
        return rule.match(bk_biz_id, app_name)
