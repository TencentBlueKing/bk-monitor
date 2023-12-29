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
import enum
import logging
import re
from collections import defaultdict
from typing import Dict, List, Union

from bkmonitor.models import AlarmClusterMatchRule

logger = logging.getLogger(__name__)


# 处理目标类型枚举
class TargetType(enum.Enum):
    biz = "biz"


class Cluster:
    """
    集群定义
    """

    def __init__(self, name: str, code: Union[int, str], tags: Dict[str, str], description: str = ""):
        """
        :param name: 集群名称
        :param code: 集群编码(4位的数字)
        :param tags: 集群标签
        :param description: 集群描述
        """
        self.name = self.check_name(name)
        self.code = str(int(code)).zfill(4)
        self.tags = tags
        self.description = description

        # 精确匹配关系: {"biz": {"cluster1": ["1", "2"], "cluster2": ["3", "4"]}}
        self.exact_match_configs = defaultdict(dict)

        # 目标匹配关系: {"biz": [{"cluster_name": "default", "pattern": ""}]}
        self.regex_match_configs = defaultdict(list)

        # 目标匹配缓存
        self.target_match_cache = defaultdict(dict)

    def get_match_config(self):
        """
        获取集群目标关系
        """
        queryset = AlarmClusterMatchRule.objects.all()
        exact_match_configs = defaultdict(dict)
        regex_match_configs = defaultdict(list)

        for relation in queryset:
            if relation.match_type == "exact":
                exact_match_configs[relation.target_type][relation.cluster_name] = set(map(str, relation.match_config))
            elif relation.match_type == "regex":
                for match_config in relation.match_config:
                    regex_match_configs[relation.target_type].append(
                        {
                            "cluster_name": match_config["cluster_name"],
                            "pattern": re.compile(match_config["pattern"]) if match_config["pattern"] else None,
                        }
                    )

        # 为每个目标类型添加默认集群
        for target_type in regex_match_configs:
            regex_match_configs[target_type].append({"cluster_name": "default", "pattern": None})

        self.exact_match_configs = exact_match_configs
        self.regex_match_configs = regex_match_configs

    @classmethod
    def check_name(cls, name: str) -> str:
        """
        1. 仅限数字0~9、字母a~z或A~Z、短划线（-）和下划线（_），统一转为小写
        2. 长度不超过64个字符
        """
        name = name.lower()
        if len(name) > 64:
            raise ValueError(f"invalid cluster name: {name}")
        for c in name:
            if not (c.isalnum() or c in "-_"):
                raise ValueError(f"invalid cluster name: {name}")
        return name

    def __repr__(self):
        return f"<Cluster: {self.name}>"

    def is_default(self) -> bool:
        """
        判断是否是默认集群
        """
        return self.name == "default"

    def match(self, target_type: TargetType, target: Union[str, int, float]) -> bool:
        """
        判断目标是否匹配当前集群
        """
        target = str(target)

        # 精确匹配
        if target in self.exact_match_configs[target_type].get(self.name, set()):
            return True

        # 正则匹配
        for match_config in self.regex_match_configs[target_type]:
            if match_config["cluster_name"] != self.name:
                continue

            # 如果pattern为空，则匹配所有目标
            if not match_config["pattern"]:
                return True

            # 如果pattern不为空，则匹配pattern
            if match_config["pattern"].match(target):
                return True
        return False

    def filter(self, target_type: TargetType, targets: List[Union[str, int, float]]) -> List[Union[str, int, float]]:
        """
        过滤出属于当前集群的目标
        """
        return [target for target in targets if self.match(target_type, target)]

    # 将目标分配到集群
    def assign_exact(self, target_type: TargetType, targets: List[Union[str, int, float]]) -> List[str]:
        """
        将目标分配到集群
        """
        assigned = False
        cleaned_clusters = []
        for relation in AlarmClusterMatchRule.objects.filter(target_type=target_type.value, match_type="exact"):
            if relation.cluster_name == self.name:
                len_before = len(relation.match_config)
                relation.match_config = list(set(relation.match_config) | set(targets))
                assigned = True
            else:
                len_before = len(relation.match_config)
                relation.match_config = list(set(relation.match_config) - set(targets))

            if len_before != len(relation.match_config):
                # 记录清理过的集群
                if relation.cluster_name != self.name:
                    cleaned_clusters.append(relation.cluster_name)

                if not relation.match_config:
                    relation.delete()
                else:
                    relation.save()

        # 如果没有匹配到集群，则创建新的集群规则
        if not assigned:
            AlarmClusterMatchRule.objects.create(
                target_type=target_type.value,
                match_type="exact",
                cluster_name=self.name,
                match_config=targets,
            )
        return cleaned_clusters

    @classmethod
    def assign_regex(cls, target_type: TargetType, match_configs: List[Dict[str, str]]):
        """
        设置目标匹配规则
        """
        for match_config in match_configs:
            if "cluster_name" not in match_config or "pattern" not in match_config:
                raise ValueError("invalid match_config: %s" % match_config)
        AlarmClusterMatchRule.objects.update_or_create(
            target_type=target_type.value,
            match_type="regex",
            defaults={"cluster_name": "", "match_config": match_configs},
        )
