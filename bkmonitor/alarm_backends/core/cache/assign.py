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
from collections import defaultdict

from alarm_backends.core.cache.base import CacheManager
from alarm_backends.core.cache.cmdb.business import BusinessManager
from bkmonitor.models.fta.assign import AlertAssignGroup, AlertAssignRule
from bkmonitor.utils import extended_json
from constants.action import GLOBAL_BIZ_ID


class AssignCacheManager(CacheManager):
    """
    告警屏蔽缓存
    """

    # 策略详情的缓存key
    BIZ_CACHE_KEY_TEMPLATE = CacheManager.CACHE_KEY_PREFIX + ".assign.biz_{bk_biz_id}"
    PRIORITY_CACHE_KEY_TEMPLATE = CacheManager.CACHE_KEY_PREFIX + ".assign.biz_priority_{bk_biz_id}_{priority}"
    GROUP_CACHE_KEY_TEMPLATE = CacheManager.CACHE_KEY_PREFIX + ".assign.biz_group_{bk_biz_id}_{group_id}"

    @classmethod
    def get_assign_priority_by_biz_id(cls, bk_biz_id):
        """
        按业务ID返回存在的priority列表
        :param bk_biz_id: 业务ID
        """
        default_priority = cls.get_global_config(cls.BIZ_CACHE_KEY_TEMPLATE) or []
        priority = cls.cache.get(cls.BIZ_CACHE_KEY_TEMPLATE.format(bk_biz_id=bk_biz_id))
        if priority:
            return sorted(set(extended_json.loads(priority) + default_priority), reverse=True)
        else:
            return sorted(default_priority, reverse=True)

    @classmethod
    def get_assign_groups_by_priority(cls, bk_biz_id, priority):
        """
        按业务ID
        :param priority: 优先级
        :param bk_biz_id: 业务ID
        """
        default_groups = cls.get_global_config(cls.PRIORITY_CACHE_KEY_TEMPLATE, priority=priority) or []
        groups = cls.cache.get(cls.PRIORITY_CACHE_KEY_TEMPLATE.format(bk_biz_id=bk_biz_id, priority=priority))
        if groups:
            return set(extended_json.loads(groups) + default_groups)
        else:
            return set(default_groups)

    @classmethod
    def get_assign_rules_by_group(cls, bk_biz_id, group_id):
        """
        按规则组ID获取对应的分配规则
        """
        default_rules = cls.get_global_config(cls.GROUP_CACHE_KEY_TEMPLATE, group_id=group_id)
        if default_rules:
            # 如果是全平台有数据，表示当前group为全局的，直接返回
            return default_rules
        rules = cls.cache.get(cls.GROUP_CACHE_KEY_TEMPLATE.format(group_id=group_id, bk_biz_id=bk_biz_id))
        if rules:
            return extended_json.loads(rules)
        else:
            return []

    @classmethod
    def get_global_config(cls, key_template, **kwargs):
        kwargs.update({"bk_biz_id": GLOBAL_BIZ_ID})
        values = cls.cache.get(key_template.format(**kwargs))
        if values:
            return extended_json.loads(values)
        else:
            return None

    @classmethod
    def refresh(cls):
        biz_list = BusinessManager.all()
        # 拉取生效的屏蔽配置，因为是缓存，把未来十分钟内会生效的屏蔽配置也拉进来

        biz_id_list = [biz.bk_biz_id for biz in biz_list]
        # 全平台业务采用0
        biz_id_list.append(0)

        groups = list(
            AlertAssignGroup.objects.filter(bk_biz_id__in=biz_id_list).values(
                "id", "name", "priority", "bk_biz_id", "is_enabled"
            )
        )

        group_ids = [group["id"] for group in groups]

        rules = list(AlertAssignRule.objects.filter(assign_group_id__in=group_ids, is_enabled=True).values())

        # 按业务缓存
        biz_priority = defaultdict(set)
        biz_priority_groups = defaultdict(set)
        group_base_info = defaultdict(dict)
        for group in groups:
            biz_priority[f'biz_{group["bk_biz_id"]}'].add(group["priority"])
            biz_priority_groups[f'biz_priority_{group["bk_biz_id"]}_{group["priority"]}'].add(group["id"])
            group_base_info[group["id"]] = group
        group_rules = defaultdict(list)
        for rule in rules:
            group_id = rule["assign_group_id"]
            rule["group_name"] = group_base_info[group_id]["name"]
            group_rules[rule["assign_group_id"]].append(rule)

        pipeline = cls.cache.pipeline()
        for bk_biz_id in biz_id_list:
            biz_key = f'biz_{bk_biz_id}'
            if biz_key in biz_priority:
                #
                pipeline.set(
                    cls.BIZ_CACHE_KEY_TEMPLATE.format(bk_biz_id=bk_biz_id),
                    extended_json.dumps(list(biz_priority[biz_key])),
                    cls.CACHE_TIMEOUT,
                )
                for priority in biz_priority[biz_key]:
                    biz_priority_key = f'biz_priority_{bk_biz_id}_{priority}'
                    if biz_priority_key in biz_priority_groups:
                        pipeline.set(
                            cls.PRIORITY_CACHE_KEY_TEMPLATE.format(bk_biz_id=bk_biz_id, priority=priority),
                            extended_json.dumps(list(biz_priority_groups[biz_priority_key])),
                            cls.CACHE_TIMEOUT,
                        )
                    else:
                        pipeline.delete(cls.BIZ_CACHE_KEY_TEMPLATE.format(bk_biz_id=bk_biz_id, priority=priority))
            else:
                # 业务ID不存在，删除掉对应的业务
                pipeline.delete(cls.BIZ_CACHE_KEY_TEMPLATE.format(bk_biz_id=bk_biz_id))
                pipeline.delete(cls.PRIORITY_CACHE_KEY_TEMPLATE.format(bk_biz_id=bk_biz_id, priority="*"))
                pipeline.delete(cls.GROUP_CACHE_KEY_TEMPLATE.format(bk_biz_id=bk_biz_id, group_id="*"))

        # 按组设置规则配置
        for group_id, group_rule in group_rules.items():
            pipeline.set(
                cls.GROUP_CACHE_KEY_TEMPLATE.format(group_id=group_id, bk_biz_id=group_rule[0]["bk_biz_id"]),
                extended_json.dumps(group_rule),
                cls.CACHE_TIMEOUT,
            )

        # 清理已经删除掉的分组
        expired_groups = set(group_base_info.keys()).difference(set(group_rules.keys()))
        for group_id in expired_groups:
            pipeline.delete(
                cls.GROUP_CACHE_KEY_TEMPLATE.format(bk_biz_id=group_base_info[group_id]["bk_biz_id"], group_id=group_id)
            )
        deleted_groups = AlertAssignGroup.origin_objects.filter(is_deleted=True)
        for group in deleted_groups:
            pipeline.delete(cls.GROUP_CACHE_KEY_TEMPLATE.format(bk_biz_id=group.bk_biz_id, group_id=group.id))
        pipeline.execute()


def main():
    AssignCacheManager.refresh()
