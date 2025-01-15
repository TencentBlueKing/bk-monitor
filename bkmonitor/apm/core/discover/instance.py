# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
import datetime
import time

import pytz
from opentelemetry.semconv.resource import ResourceAttributes

from apm.core.discover.base import (
    DiscoverBase,
    extract_field_value,
    get_topo_instance_key,
)
from apm.core.handlers.instance_handlers import InstanceHandler
from apm.models import ApmTopoDiscoverRule, TopoInstance
from constants.apm import OtlpKey


class InstanceDiscover(DiscoverBase):
    DISCOVERY_ALL_SPANS = True
    MAX_COUNT = 100000
    INSTANCE_ID_SPLIT = ":"
    model = TopoInstance

    @classmethod
    def to_instance_key(cls, object_pk_id, instance_id):
        return cls.INSTANCE_ID_SPLIT.join([str(object_pk_id), str(instance_id)])

    @classmethod
    def to_id_and_key(cls, instances: list):
        """
        数据提取转化
        :param instances: 实例列表
        :return:
        """
        ids, keys = set(), set()
        for inst in instances:
            inst_id = inst.get("id")
            inst_key = cls.to_instance_key(inst_id, inst.get("instance_id"))
            keys.add(inst_key)
            ids.add(inst_id)
        return ids, keys

    @classmethod
    def merge_data(cls, instances: list, cache_data: dict) -> list:
        """
        更新 updated_at 字段
        :param instances: 实例数据
        :param cache_data: 缓存数据
        :return:
        """
        merge_data = []
        for instance in instances:
            key = cls.to_instance_key(instance.get("id"), instance.get("instance_id"))
            if key in cache_data:
                instance["updated_at"] = datetime.datetime.fromtimestamp(cache_data.get(key), tz=pytz.UTC)
            merge_data.append(instance)
        return merge_data

    def instance_clear_if_overflow(self, instances: list):
        """
        数据量大于100000时, 清除数据
        :param instances: 实例数据
        :return:
        """
        overflow_delete_data = []
        count = len(instances)
        if count > self.MAX_COUNT:
            delete_count = count - self.MAX_COUNT
            # 按照updated_at排序，从小到大
            instances.sort(key=lambda item: item.get("updated_at"))
            overflow_delete_data = instances[:delete_count]
            remain_instance_data = instances[delete_count:]
        else:
            remain_instance_data = instances
        return overflow_delete_data, remain_instance_data

    def instance_clear_expired(self, instances: list):
        """
        清除过期数据
        :param instances: 实例数据
        :return:
        """
        # mysql 中的 updated_at 时间字段, 它的时区是 UTC, 跟数据库保持一致
        boundary = datetime.datetime.now(tz=pytz.UTC) - datetime.timedelta(
            days=self.application.trace_datasource.retention
        )
        # 按照时间进行过滤
        expired_delete_data = []
        remain_instance_data = []
        for instance in instances:
            if instance.get("updated_at") <= boundary:
                expired_delete_data.append(instance)
            else:
                remain_instance_data.append(instance)
        return expired_delete_data, remain_instance_data

    def list_exists(self):
        res = {}
        instances = TopoInstance.objects.filter(bk_biz_id=self.bk_biz_id, app_name=self.app_name)
        for instance in instances:
            res.setdefault(
                (
                    instance.topo_node_key,
                    instance.instance_id,
                    instance.instance_topo_kind,
                    instance.component_instance_category,
                    instance.component_instance_predicate_value,
                    instance.sdk_name,
                    instance.sdk_version,
                    instance.sdk_language,
                ),
                dict(),
            ).update({"id": instance.id, "instance_id": instance.instance_id})

        return res

    def discover(self, origin_data):
        """
        Discover span instance
        KIND | BASE | DESC
        service | resource.bk.instance.id | this field will be filled during the bk_collector
        component | instance_key from rules | join with ':'
        need_update_instances -> [{"id": 243, "instance_id": "mysql:::3306"}]
        *_instance_keys -> {"243:mysql:::3306", "244:elasticsearch:::"}
        """
        exists_instances = self.list_exists()
        component_rules = self.filter_rules(ApmTopoDiscoverRule.TOPO_COMPONENT)

        need_update_instances = list()
        need_create_instances = set()
        need_create_instance_ids = set()

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
                    need_create_instance_ids.add(key[1])

        # create
        TopoInstance.objects.bulk_create(
            [
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
        )
        # query cache data and database data(with object_pk_id)
        cache_data, instance_data = self.query_cache_and_instance_data()

        # delete database data
        delete_instance_keys = self.clear_data(cache_data, instance_data)

        # refresh cache data
        _, create_instance_keys = self.to_id_and_key(
            [i for i in instance_data if i.get("instance_id") in need_create_instance_ids]
        )
        _, update_instance_keys = self.to_id_and_key(need_update_instances)
        self.refresh_cache_data(
            old_cache_data=cache_data,
            create_instance_keys=create_instance_keys,
            update_instance_keys=update_instance_keys,
            delete_instance_keys=delete_instance_keys,
        )

    def clear_data(self, cache_data, instance_data) -> set:
        """
        数据清除
        :param cache_data: 缓存数据
        :param instance_data: mysql 数据
        :return:
        """
        merge_data = self.merge_data(instance_data, cache_data)
        # 过期数据
        expired_delete_data, remain_instance_data = self.instance_clear_expired(merge_data)
        # 超量数据
        overflow_delete_data, remain_instance_data = self.instance_clear_if_overflow(remain_instance_data)
        delete_data = expired_delete_data + overflow_delete_data

        delete_ids, delete_keys = self.to_id_and_key(delete_data)
        if delete_ids:
            self.model.objects.filter(pk__in=delete_ids).delete()

        return delete_keys

    def refresh_cache_data(
        self,
        old_cache_data: dict,
        create_instance_keys: set,
        update_instance_keys: set,
        delete_instance_keys: set,
    ):
        now = int(time.time())
        old_cache_data.update({i: now for i in (create_instance_keys | update_instance_keys)})
        cache_data = {i: old_cache_data[i] for i in (set(old_cache_data.keys()) - delete_instance_keys)}
        name = InstanceHandler.get_topo_instance_cache_key(self.bk_biz_id, self.app_name)
        InstanceHandler().refresh_data(name, cache_data)

    def query_cache_and_instance_data(self):
        """
        缓存数据及实例数据查询
        """

        # 查询应用下的缓存数据
        name = InstanceHandler.get_topo_instance_cache_key(self.bk_biz_id, self.app_name)
        cache_data = InstanceHandler().get_cache_data(name)

        # 查询应用下的实例数据
        filter_params = {"bk_biz_id": self.bk_biz_id, "app_name": self.app_name}
        instance_data = list(TopoInstance.objects.filter(**filter_params).values("id", "instance_id", "updated_at"))

        return cache_data, instance_data
