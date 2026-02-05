"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from opentelemetry.semconv.resource import ResourceAttributes

from apm.constants import ApmCacheType
from apm.core.discover.base import (
    DiscoverBase,
    extract_field_value,
    get_topo_instance_key,
)
from apm.core.discover.cached_mixin import CachedDiscoverMixin
from apm.core.discover.instance_data import TopoInstanceData
from apm.models import ApmTopoDiscoverRule, TopoInstance
from constants.apm import OtlpKey


class InstanceDiscover(CachedDiscoverMixin, DiscoverBase):
    DISCOVERY_ALL_SPANS = True
    MAX_COUNT = 100000
    INSTANCE_ID_SPLIT = ":"
    model = TopoInstance

    @classmethod
    def _get_cache_type(cls) -> str:
        """获取缓存类型"""
        return ApmCacheType.TOPO_INSTANCE

    @classmethod
    def to_cache_key(cls, instance: TopoInstanceData) -> str:
        """从实例数据对象生成唯一的 key"""
        return cls.INSTANCE_ID_SPLIT.join(map(str, cls._to_found_key(instance)))

    @classmethod
    def build_instance_data(cls, instance_obj) -> TopoInstanceData:
        return TopoInstanceData(
            id=DiscoverBase.get_attr_value(instance_obj, "id"),
            topo_node_key=DiscoverBase.get_attr_value(instance_obj, "topo_node_key"),
            instance_id=DiscoverBase.get_attr_value(instance_obj, "instance_id"),
            instance_topo_kind=DiscoverBase.get_attr_value(instance_obj, "instance_topo_kind"),
            component_instance_category=DiscoverBase.get_attr_value(instance_obj, "component_instance_category"),
            component_instance_predicate_value=DiscoverBase.get_attr_value(
                instance_obj, "component_instance_predicate_value"
            ),
            sdk_name=DiscoverBase.get_attr_value(instance_obj, "sdk_name"),
            sdk_version=DiscoverBase.get_attr_value(instance_obj, "sdk_version"),
            sdk_language=DiscoverBase.get_attr_value(instance_obj, "sdk_language"),
            updated_at=DiscoverBase.get_attr_value(instance_obj, "updated_at"),
        )

    @classmethod
    def _to_found_key(cls, instance_data: TopoInstanceData) -> tuple:
        """从实例数据对象生成业务唯一标识（不包含数据库ID）用于在 discover 过程中匹配已存在的实例"""
        return (
            instance_data.topo_node_key,
            instance_data.instance_id,
            instance_data.instance_topo_kind,
            instance_data.component_instance_category,
            instance_data.component_instance_predicate_value,
            instance_data.sdk_name,
            instance_data.sdk_version,
            instance_data.sdk_language,
        )

    def get_remain_data(self):
        instances = self.model.objects.filter(bk_biz_id=self.bk_biz_id, app_name=self.app_name)
        return self.process_duplicate_records(instances, True, True)

    def discover(self, origin_data, exists_instances: dict[tuple, TopoInstanceData]):
        """
        Discover span instance
        KIND | BASE | DESC
        service | resource.bk.instance.id | this field will be filled during the bk_collector
        component | instance_key from rules | join with ':'
        need_update_instances -> [{"id": 243, "instance_id": "mysql:::3306"}]
        *_instance_keys -> {"243:mysql:::3306", "244:elasticsearch:::"}
        """
        component_rules = self.filter_rules(ApmTopoDiscoverRule.TOPO_COMPONENT)

        need_update_instances = list()
        need_create_instances = set()

        for span in origin_data:
            # service/components have different sources that can be discovered in parallel
            found_keys = []

            # SERVICE: supplemented by bk_collector
            instance_id = extract_field_value((OtlpKey.RESOURCE, OtlpKey.BK_INSTANCE_ID), span)
            if instance_id and any(bool(i) for i in instance_id.split(self.INSTANCE_ID_SPLIT)):
                service_name = extract_field_value((OtlpKey.RESOURCE, ResourceAttributes.SERVICE_NAME), span)
                sdk_name = extract_field_value((OtlpKey.RESOURCE, ResourceAttributes.TELEMETRY_SDK_NAME), span)
                sdk_version = extract_field_value((OtlpKey.RESOURCE, ResourceAttributes.TELEMETRY_SDK_VERSION), span)
                sdk_language = extract_field_value((OtlpKey.RESOURCE, ResourceAttributes.TELEMETRY_SDK_LANGUAGE), span)

                found_keys.append(
                    (
                        service_name,
                        instance_id,
                        ApmTopoDiscoverRule.TOPO_SERVICE,
                        None,
                        None,
                        sdk_name,
                        sdk_version,
                        sdk_language,
                    )
                )

                match_component_rule = self.get_match_rule(span, component_rules)
                if match_component_rule:
                    # COMPONENT
                    component_instance_id = get_topo_instance_key(
                        match_component_rule.instance_keys,
                        match_component_rule.topo_kind,
                        match_component_rule.category_id,
                        span,
                        simple_component_instance=False,
                        component_predicate_key=match_component_rule.predicate_key,
                    )
                    topo_key = get_topo_instance_key(
                        match_component_rule.instance_keys,
                        match_component_rule.topo_kind,
                        match_component_rule.category_id,
                        span,
                        component_predicate_key=match_component_rule.predicate_key,
                    )
                    found_keys.append(
                        (
                            f"{service_name}-{topo_key}",
                            component_instance_id,
                            ApmTopoDiscoverRule.TOPO_COMPONENT,
                            match_component_rule.category_id,
                            extract_field_value(match_component_rule.predicate_key, span),
                            sdk_name,
                            sdk_version,
                            sdk_language,
                        )
                    )
            for key in found_keys:
                if key in exists_instances:
                    need_update_instances.append(exists_instances[key])
                else:
                    need_create_instances.add(key)

        created_instances = [
            TopoInstance(
                bk_biz_id=self.bk_biz_id,
                app_name=self.app_name,
                topo_node_key=i[0],
                instance_id=i[1],
                instance_topo_kind=i[2],
                component_instance_category=i[3],
                component_instance_predicate_value=i[4],
                sdk_name=i[5],
                sdk_version=i[6],
                sdk_language=i[7],
            )
            for i in need_create_instances
        ]
        TopoInstance.objects.bulk_create(created_instances)

        # 使用 Mixin 的通用方法处理缓存刷新
        self.handle_cache_refresh_after_create(
            existing_instances=list(exists_instances.values()),
            created_db_instances=created_instances,
            updated_instances=need_update_instances,
        )
