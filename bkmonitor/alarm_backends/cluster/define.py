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
import json
import logging
from collections import defaultdict
from typing import Dict, List, Optional, Union

from bkmonitor.utils.range import load_agg_condition_instance

logger = logging.getLogger(__name__)


# 处理目标类型枚举
class TargetType(enum.Enum):
    biz = "biz"
    alert_data_id = "alert_data_id"


class RoutingRule:
    """
    路由规则定义
    """

    target_type: TargetType
    cluster_name: str
    matcher_type: str
    matcher_config: Union[Dict, List]
    description: str

    def __init__(
        self,
        target_type: Union[TargetType, str],
        cluster_name: str,
        matcher_type: str,
        matcher_config: Optional[Union[Dict, List]],
        description: str = "",
    ):
        if isinstance(target_type, str):
            target_type = target_type.lower()
            if not hasattr(TargetType, target_type):
                raise ValueError(f"invalid target_type: {target_type}")
            self.target_type = TargetType[target_type]
        else:
            self.target_type = target_type

        self.cluster_name = Cluster.check_name(cluster_name)
        self.matcher_type = matcher_type
        self.matcher_config = matcher_config
        self.description = description

    def match(self, target: Union[str, int, float]) -> bool:
        """
        判断目标是否匹配当前路由规则
        """
        matcher_cls = _MATCHERS.get(self.matcher_type)
        if matcher_cls:
            matcher = matcher_cls(self.matcher_config)
            try:
                return matcher.match(target)
            except Exception as e:
                logger.exception(f"match target {target} with rule {self} failed: {e}")
        return False

    def __repr__(self):
        return (
            f"<RoutingRule: {self.target_type}, {self.cluster_name}, "
            f"{self.matcher_type}, {json.dumps(self.matcher_config)}>"
        )


class Cluster:
    """
    集群定义
    """

    def __init__(
        self,
        name: str,
        code: Union[int, str],
        tags: Dict[str, str],
        routing_rules: List[RoutingRule],
        description: str = "",
    ):
        """
        :param name: 集群名称
        :param code: 集群编码(4位的数字)
        :param tags: 集群标签
        :param routing_rules: 路由规则
        :param description: 集群描述
        """
        self.name = self.check_name(name)
        self.code = str(int(code)).zfill(4)
        self.tags = tags
        self.description = description
        self.routing_rules = []
        self.routing_rules.extend(routing_rules or [])

        self.routing_rules_by_type: Dict[TargetType, List[RoutingRule]] = defaultdict(list)
        for rule in self.routing_rules:
            self.routing_rules_by_type[rule.target_type].append(rule)

        # 业务目标类型的路由规则必须有一个 true 的匹配器
        biz_routing_rules = self.routing_rules_by_type[TargetType.biz]
        if len(biz_routing_rules) == 0 or biz_routing_rules[-1].matcher_type != "true":
            self.routing_rules_by_type[TargetType.biz].append(
                RoutingRule(
                    target_type=TargetType.biz,
                    cluster_name="default",
                    matcher_type="true",
                    matcher_config=None,
                )
            )

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
        # 获取目标类型对应的路由规则
        routing_rules = self.routing_rules_by_type[target_type]

        # 按顺序遍历路由规则，如果匹配上就返回 True，否则返回 False
        for rule in routing_rules:
            # 如果不是当前集群的规则，没匹配上就继续，匹配上就表示目标不属于当前集群
            if rule.cluster_name != self.name:
                if not rule.match(target):
                    continue
                else:
                    return False

            # 如果是当前集群的规则，匹配上就表示目标属于当前集群
            if rule.match(target):
                return True

        return False

    def filter(self, target_type: TargetType, targets: List[Union[str, int, float]]) -> List[Union[str, int, float]]:
        """
        过滤出属于当前集群的目标
        """
        return [target for target in targets if self.match(target_type, target)]

    def get_targets_by_cluster(
        self, target_type: TargetType, targets: List[Union[str, int, float]]
    ) -> Dict[str, List[Union[str, int, float]]]:
        """
        将目标按照集群进行分组
        """
        targets_by_cluster = defaultdict(list)
        for target in targets:
            for rule in self.routing_rules_by_type[target_type]:
                if rule.match(target):
                    targets_by_cluster[rule.cluster_name].append(target)
                    break
        return targets_by_cluster


# 匹配器注册表
_MATCHERS = {}


# 匹配器注册装饰器
def matcher_register():
    def wrapper(cls: Matcher):
        _MATCHERS[cls.type] = cls
        return cls

    return wrapper


class Matcher:
    """
    匹配器基类
    """

    type: str

    def __init__(self, config: Optional[Union[Dict, List]] = None):
        self.config = config

    def match(self, target: Union[str, int, float]) -> bool:
        """
        判断目标是否匹配当前路由规则
        """
        raise NotImplementedError


@matcher_register()
class TrueMatcher(Matcher):
    """
    总是返回 True 的匹配器
    """

    type = "true"

    def match(self, target: Union[str, int, float]) -> bool:
        """
        判断目标是否匹配当前路由规则
        """
        return True


@matcher_register()
class FalseMatcher(Matcher):
    """
    总是返回 False 的匹配器
    """

    type = "false"

    def match(self, target: Union[str, int, float]) -> bool:
        """
        判断目标是否匹配当前路由规则
        """
        return False


@matcher_register()
class ConditionMatcher(Matcher):
    """
    条件匹配器
    """

    type = "condition"

    def match(self, target: Union[str, int, float]) -> bool:
        """
        判断目标是否匹配当前路由规则
        """

        for sub_config in self.config:
            sub_config["key"] = "value"

        condition = load_agg_condition_instance(self.config)
        return condition.is_match({"value": target})
