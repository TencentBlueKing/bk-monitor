"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2024 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
import logging
from collections import defaultdict
from distutils.version import StrictVersion
from functools import reduce

from django.conf import settings
from django.db import connections
from django.db.models import Q
from django.utils.translation import ugettext as _
from rest_framework import serializers

from bkmonitor.models import MetricListCache, QueryConfigModel, StrategyModel
from bkmonitor.utils.cipher import RSACipher
from bkmonitor.utils.request import get_request
from constants.cmdb import TargetNodeType
from constants.data_source import DataSourceLabel, DataTypeLabel
from core.drf_resource import Resource, api
from core.drf_resource.exceptions import CustomException
from core.errors.api import BKAPIError
from core.errors.collecting import CollectingError
from monitor_web.collecting.constant import COLLECT_TYPE_CHOICES
from monitor_web.collecting.deploy import get_collect_installer
from monitor_web.models import (
    CollectConfigMeta,
    CustomEventGroup,
    DeploymentConfigVersion,
)
from monitor_web.plugin.constant import PluginType

logger = logging.getLogger(__name__)

# 最低版本依赖
PLUGIN_VERSION = {PluginType.PROCESS: {"bkmonitorbeat": "0.33.0" if settings.PLATFORM == "ieod" else "2.10.0"}}
# 推荐bkmonitorbeat版本依赖
RECOMMENDED_VERSION = {"bkmonitorbeat": "2.13.0"}


class ListLegacySubscription(Resource):
    """
    获取各个采集项遗留的订阅配置
    """

    def perform_request(self, validated_request_data):
        # 把已经删除的采集配置也包括在内
        meta_configs = CollectConfigMeta.origin_objects.all()

        # 当前监控依然有效的订阅id
        actived_subscription_ids = set(
            meta_configs.filter(is_deleted=False).values_list("deployment_config__subscription_id", flat=True)
        )

        meta_configs = list(
            meta_configs.values(
                "id", "name", "bk_biz_id", "deployment_config_id", "deployment_config__subscription_id", "is_deleted"
            )
        )

        meta_configs = {c["id"]: c for c in meta_configs}

        deploy_configs = DeploymentConfigVersion.origin_objects.filter(
            config_meta_id__in=list(meta_configs.keys())
        ).values("id", "config_meta_id", "subscription_id")

        for deploy_config in deploy_configs:
            config_meta_id = deploy_config["config_meta_id"]
            meta_config = meta_configs[config_meta_id]
            meta_config.setdefault("legacy_subscription_ids", [])
            meta_config.setdefault("deleted_subscription_ids", [])
            if (
                meta_config["is_deleted"]
                or meta_config["deployment_config__subscription_id"] != deploy_config["subscription_id"]
            ):
                # 采集配置被删除，历史订阅全部算在内
                # 采集配置未被删除： 订阅ID不等于当前正在启用的，才计算在内。
                meta_config["legacy_subscription_ids"].append(deploy_config["subscription_id"])

        # 需要返回的结果
        # example:
        # [{
        #     'id': 176,
        #     'name': 'test',
        #     'bk_biz_id': 12,
        #     'deployment_config_id': 267,
        #     'deployment_config__subscription_id': 2748,  # 当前订阅ID
        #     'legacy_subscription_ids': [1, 2, 3]  # 需要清理的订阅ID
        #     'deleted_subscription_ids': [4, 5, 6]  # 已正常卸载的订阅ID，一般无需关注
        # }]
        results = list(meta_configs.values())

        with connections["nodeman"].cursor() as cursor:
            # 尝试查询节点管理DB，最新的一次任务中属于自动触发的所有订阅ID（可能有问题的订阅ID）
            auto_trigger_query_sql = """
            select a.subscription_id from node_man_subscriptiontask as a
            inner join
            (select max(id) as c, subscription_id from node_man_subscriptiontask group by subscription_id) as b
            on a.subscription_id = b.subscription_id and a.id=b.c and a.is_auto_trigger = 1;
            """
            cursor.execute(auto_trigger_query_sql)
            desc = cursor.description
            auto_trigger_list = [dict(list(zip([col[0] for col in desc], row))) for row in cursor.fetchall()]

            # 查询属于监控插件采集的订阅列表
            # 插件采集的 step_id 固定是 bkmonitorbeat
            # 其他有 bkmonitorproxy, bkmonitorbeat_http。需要特别注意不要把这些计算在内
            # 节点管理2.1及之后，新增category字段
            all_monitor_subscription_query_sql = '''
            select a.subscription_id from node_man_subscriptionstep as a
            inner join node_man_subscription as b on a.subscription_id = b.id
            where a.step_id IN ("bkmonitorbeat","bkmonitorlog") and b.is_deleted = 0
            and config not like "%MAIN_%_PLUGIN%" and b.category is null;'''
            cursor.execute(all_monitor_subscription_query_sql)
            all_monitor_subscription_ids = {item[0] for item in cursor.fetchall()}

        logger.info("[list_legacy_subscription] query result from nodeman: %s", auto_trigger_list)

        auto_trigger_subscriptions = {row["subscription_id"] for row in auto_trigger_list}
        all_legacy_subscription_ids = []
        for result in results:
            legacy_subscription_ids = result.get("legacy_subscription_ids", [])
            # 与查回来的订阅ID取并集，筛选出已被删除的但最后一次是自动触发的那些订阅ID（当前自动触发均为安装类操作）
            result["legacy_subscription_ids"] = list(set(legacy_subscription_ids) & auto_trigger_subscriptions)
            result["deleted_subscription_ids"] = list(set(legacy_subscription_ids) - auto_trigger_subscriptions)
            # 这里面仅表示该订阅id在当前采集配置下被遗弃，还需要和全局有效的订阅id再做一次差值
            all_legacy_subscription_ids.extend(result["legacy_subscription_ids"])

        response = {
            "detail": results,
            "total_legacy_subscription_ids": sorted(list(set(all_legacy_subscription_ids) - actived_subscription_ids)),
            "wild_subscription_ids": sorted(
                list(all_monitor_subscription_ids - {c["subscription_id"] for c in deploy_configs})
            ),
        }

        return response


class CleanLegacySubscription(Resource):
    """
    停用并删除遗留的订阅配置
    如果是刚下发的升级，这时候订阅id是刚删除的状态，此时需要等半小时再执行清理订阅的操作
    """

    class RequestSerializer(serializers.Serializer):
        subscription_id = serializers.ListField(required=True, label="节点管理订阅ID", child=serializers.IntegerField())
        action_type = serializers.CharField(default="STOP", label="动作类型")
        is_force = serializers.BooleanField(default=False, label="是否强制清理")

    @staticmethod
    def clean_subscription(subscription_id, action_type, is_force):
        # 如果不是强制清理，需要判断订阅是不是已被删除了，已删除的才允许操作
        if not is_force:
            # 先查一次确认是否为遗留的订阅配置。如果订阅ID还存在，则不允许此操作
            subscription_infos = api.node_man.subscription_info(subscription_id_list=[subscription_id])
            if subscription_infos:
                raise CollectingError({"msg": _('当前订阅ID未被删除，无法操作。可增加 "is_force=1" 参数强制操作 ')})

        # 1. 修改订阅配置，把删除状态更新成未删除，同时enable改成不启动
        with connections["nodeman"].cursor() as cursor:
            cursor.execute(
                "UPDATE node_man_subscription SET enable = 0, is_deleted = 0 WHERE id = %s;", (subscription_id,)
            )

        try:
            # 2. 获取订阅详情
            subscription_infos = api.node_man.subscription_info(subscription_id_list=[subscription_id])
            if not subscription_infos:
                raise CollectingError({"msg": _("订阅ID不存在")})
            subscription_info = subscription_infos[0]

            logger.info("[clean_legacy_subscription] info: %s", subscription_info)

            # 从返回的订阅详情中，拼接动作参数。默认仅停用，不删除文件
            action_params = {step["id"]: action_type for step in subscription_info["steps"]}

            # 3. 调用执行订阅的api
            run_result = api.node_man.run_subscription(subscription_id=subscription_id, actions=action_params)
            logger.info("[clean_legacy_subscription] run result: %s", run_result)
            return run_result
        except Exception as e:
            raise e
        finally:
            # 4. 删除订阅的api
            with connections["nodeman"].cursor() as cursor:
                cursor.execute(
                    "UPDATE node_man_subscription SET enable = 0, is_deleted = 1 WHERE id = %s;", (subscription_id,)
                )

    def perform_request(self, validated_request_data):
        subscription_ids = validated_request_data["subscription_id"]

        results = []
        for subscription_id in subscription_ids:
            try:
                result = self.clean_subscription(
                    subscription_id, validated_request_data["action_type"], validated_request_data["is_force"]
                )
                result.update({"result": True})
            except Exception as e:
                result = {
                    "result": False,
                    "message": str(e),
                }
            result["subscription_id"] = subscription_id
            results.append(result)
        return results


class ListLegacyStrategy(Resource):
    """
    列出当前配置的告警策略中无效的部分：
    1. 基于日志关键字采集配置了策略，之后又删除了日志关键字；
    2. 基于自定义事件上报配置了策略，之后又删除了自定义事件； 当前配置了策略的自定义事件不让删除
    3. 基于插件对应的采集配置了策略，之后又删除了插件；  暂不考虑该场景
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")

    def perform_request(self, validated_request_data):
        # 1. 获取有效的事件相关的rt表：包含日志关键字和自定义事件
        event_rt_list = list(
            CustomEventGroup.objects.filter(bk_biz_id=validated_request_data["bk_biz_id"]).values_list(
                "table_id", flat=True
            )
        )

        # 2. 找到已经不再有效的rt表（采集被删除）对应的策略
        strategy_ids = list(
            StrategyModel.objects.filter(bk_biz_id=validated_request_data["bk_biz_id"]).values_list("id", flat=True)
        )
        invalid_strategy_ids = QueryConfigModel.objects.filter(strategy_id__in=strategy_ids).filter(
            Q(data_source_label=DataSourceLabel.BK_MONITOR_COLLECTOR, data_type_label=DataTypeLabel.LOG)
            | Q(data_source_label=DataSourceLabel.CUSTOM, data_type_label=DataTypeLabel.EVENT)
        )

        if event_rt_list:
            invalid_strategy_ids = invalid_strategy_ids.exclude(
                reduce(lambda x, y: x | y, (Q(config__result_table_id=table_id) for table_id in event_rt_list))
            )

        return list(invalid_strategy_ids)


class ListRelatedStrategy(Resource):
    """
    列出当前配置的所有相关策略
    1.拿到所有指标的collect_config_ids
    2.找到要删除的采集配置对应的指标
    3.从alarm_item里找到对应的策略ID
    4.返回数据
    - 模糊：返回涉及到的策略ID及名称
    - 精准：查看rt_query_config_id对应的结果表的条件中是否使用了该采集配置
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        collect_config_id = serializers.IntegerField(required=True, label="采集配置ID")

    def perform_request(self, validated_request_data):
        collect_config = CollectConfigMeta.objects.get(id=validated_request_data["collect_config_id"])
        result = {"fuzzy_strategies": [], "accurate_strategies": []}

        # 1.拿到所有指标的collect_config_ids
        related_metrics = []
        metrics = MetricListCache.objects.filter(bk_biz_id__in=[0, validated_request_data["bk_biz_id"]])

        # 2.找到要删除的采集配置对应的指标
        for metric in metrics:
            if metric.data_type_label == "log" and validated_request_data["collect_config_id"] == int(
                metric.related_id
            ):
                related_metrics.append(f"{metric.data_source_label}.{metric.data_type_label}.{metric.metric_field}")
            elif metric.collect_config_ids == "":
                continue
            elif validated_request_data["collect_config_id"] in metric.collect_config_ids:
                related_metrics.append(f"{metric.data_source_label}.{metric.result_table_id}.{metric.metric_field}")

        # 3.从alarm_item里找到对应的策略ID
        fuzzy_alarm_items = [
            query_config.strategy_id for query_config in QueryConfigModel.objects.filter(metric_id__in=related_metrics)
        ]
        result["fuzzy_strategies"] = [
            {"strategy_id": strategy.id, "strategy_name": strategy.name}
            for strategy in StrategyModel.objects.filter(
                bk_biz_id=validated_request_data["bk_biz_id"], id__in=fuzzy_alarm_items
            )
        ]

        # 4.返回相关策略
        # 如果是日志关键字，不区别模糊和精准
        if collect_config.collect_type == PluginType.LOG or collect_config.collect_type == PluginType.SNMP_TRAP:
            result["accurate_strategies"] = result["fuzzy_strategies"]
            return result

        # 精准：查看rt_query_config_id对应的结果表的条件中是否使用了该采集配置
        acc_alarm_items = []
        rt_configs = QueryConfigModel.objects.filter(metric_id__in=related_metrics).values("strategy_id", "config")
        for rt_config in rt_configs:
            conditions = rt_config["config"].get("agg_condition", [])
            for config in conditions:
                if config["key"] != "bk_collect_config_id" or config["method"] != "eq":
                    continue
                if collect_config.name in config["value"]:
                    acc_alarm_items.append(rt_config["strategy_id"])
        result["accurate_strategies"] = [
            {"strategy_id": strategy.id, "strategy_name": strategy.name}
            for strategy in StrategyModel.objects.filter(
                bk_biz_id=validated_request_data["bk_biz_id"], id__in=acc_alarm_items
            )
        ]
        return result


class IsTaskReady(Resource):
    """
    向节点管理轮询任务是否已经初始化完成
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        collect_config_id = serializers.IntegerField(required=True, label="采集配置ID")

    def perform_request(self, validated_request_data):
        config_id = validated_request_data["collect_config_id"]
        config = CollectConfigMeta.objects.select_related("deployment_config").get(id=config_id)

        # 兼容非节点管理部署的采集
        if not config.deployment_config.subscription_id:
            return True

        params = {
            "subscription_id": config.deployment_config.subscription_id,
            "task_id_list": config.deployment_config.task_ids,
        }
        try:
            result = api.node_man.check_task_ready(**params)
            return result
        except BKAPIError as e:
            # 兼容旧版节点管理设计，若esb不存在此接口，则说明为旧版逻辑
            logger.info(f"[is_task_ready] {e}")
            return True


class EncryptPasswordResource(Resource):
    """
    基于内置RSA公钥，对用户采集配置下发的密码类文本进行加密
    """

    class RequestSerializer(serializers.Serializer):
        password = serializers.CharField(required=True, label="明文密码")

    def perform_request(self, validated_request_data):
        password = validated_request_data["password"]
        if not settings.RSA_PRIVATE_KEY:
            # 未配置RSA秘钥对，不加密
            return password
        cipher = RSACipher()
        cipher.load_pri_key(settings.RSA_PRIVATE_KEY)
        if isinstance(password, str):
            password = password.encode("utf8")
        return cipher.encrypt(password).decode("utf8")


class DecryptPasswordResource(Resource):
    class RequestSerializer(serializers.Serializer):
        encrypted_text = serializers.CharField(required=True, label="密文")

    def perform_request(self, validated_request_data):
        if not settings.RSA_PRIVATE_KEY:
            raise
        encrypted_text = validated_request_data["encrypted_text"]
        cipher = RSACipher()
        cipher.load_pri_key(settings.RSA_PRIVATE_KEY)
        if isinstance(encrypted_text, str):
            encrypted_text = encrypted_text.encode("utf8")
        return cipher.decrypt(encrypted_text).decode("utf8")


class CheckAdjectiveCollect(Resource):
    """
    检查游离态采集配置【清理可选】
    """

    class RequestSerializer(serializers.Serializer):
        clean = serializers.BooleanField(required=False, label="是否清理", default=False)

    def perform_request(self, validated_request_data):
        configs = CollectConfigMeta.objects.filter(last_operation="STOP")
        config_id_map = {config.id: config for config in configs}
        dcvs = dict(
            DeploymentConfigVersion.objects.filter(config_meta_id__in=list(config_id_map.keys())).values_list(
                "subscription_id", "config_meta_id"
            )
        )
        infos = api.node_man.subscription_info(subscription_id_list=list(dcvs.keys()))
        need_switch_off_and_stop = []
        for i in infos:
            if not i["enable"]:
                continue
            need_switch_off_and_stop.append({"config_id": dcvs[i["id"]], "subscription_id": i["id"]})

        if not validated_request_data["clean"]:
            return need_switch_off_and_stop

        is_superuser = get_request().user.is_superuser
        if not is_superuser:
            raise CustomException("You are not superuser, can't clean.")
        for i in need_switch_off_and_stop:
            api.node_man.switch_subscription(subscription_id=i["subscription_id"], action="disable")
            installer = get_collect_installer(config_id_map[i["config_id"]])
            installer.stop()
        return need_switch_off_and_stop


class FetchCollectConfigStat(Resource):
    """
    获取采集配置列表统计信息
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=False, label="业务ID")

    @staticmethod
    def sum_by_field(config, result, field, type_list, dismiss, default=""):
        status = config.get_cache_data(field, default)
        if not type_list.get(config.collect_type) or status in dismiss:
            return result
        result[type_list[config.collect_type]][status] += 1
        return result

    def perform_request(self, validated_request_data):
        result = {}
        configs = CollectConfigMeta.objects.filter(is_deleted=False, bk_biz_id=validated_request_data["bk_biz_id"])
        type_list_id_name = {}
        type_list_name_id = {}

        for item in COLLECT_TYPE_CHOICES:
            if item[0] in ["log", "Built-In"]:
                continue
            type_list_id_name[item[0]] = item[1]
            type_list_name_id[item[1]] = item[0]

        for item in list(type_list_id_name.values()):
            result[item] = defaultdict(int)

        for config in configs:
            result = self.sum_by_field(config, result, "status", type_list_id_name, [])
            result = self.sum_by_field(config, result, "task_status", type_list_id_name, ["STOPPED"])
            if config.get_cache_data("need_upgrade", False):
                result[type_list_id_name[config.collect_type]]["need_upgrade"] += 1

        new_result = []
        for key, value in result.items():
            new_result.append(
                {
                    "id": type_list_name_id.get(key),
                    "name": key,
                    "nums": value,
                }
            )
        return new_result


class CheckPluginVersionResource(Resource):
    """
    获取采集配置列表统计信息
    """

    class RequestSerializer(serializers.Serializer):
        target_nodes = serializers.ListField(required=True, child=serializers.DictField(), label="目标实例")
        target_node_type = serializers.ChoiceField(
            required=True, label="采集目标类型", choices=DeploymentConfigVersion.TARGET_NODE_TYPE_CHOICES
        )
        collect_type = serializers.ChoiceField(
            required=True, label="采集方式", choices=CollectConfigMeta.COLLECT_TYPE_CHOICES
        )
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")

    @staticmethod
    def get_host_ids(validated_request_data):
        hosts = []
        if validated_request_data["target_node_type"] == TargetNodeType.INSTANCE:
            hosts = api.cmdb.get_host_by_ip(
                {
                    "bk_biz_id": validated_request_data["bk_biz_id"],
                    "ips": validated_request_data["target_nodes"],
                }
            )
        elif validated_request_data["target_node_type"] == TargetNodeType.TOPO:
            topo_dict = defaultdict(list)
            for topo_node in validated_request_data["target_nodes"]:
                if topo_node["bk_obj_id"] == "biz":
                    break
                topo_dict[topo_node["bk_obj_id"]].append(topo_node["bk_inst_id"])
            hosts = api.cmdb.get_host_by_topo_node(
                {"bk_biz_id": validated_request_data["bk_biz_id"], "topo_nodes": topo_dict}
            )
        elif validated_request_data["target_node_type"] in [
            TargetNodeType.SERVICE_TEMPLATE,
            TargetNodeType.SET_TEMPLATE,
        ]:
            template_ids = [target_node["bk_inst_id"] for target_node in validated_request_data["target_nodes"]]
            hosts = api.cmdb.get_host_by_template(
                bk_biz_id=validated_request_data["bk_biz_id"],
                bk_obj_id=validated_request_data["target_node_type"],
                template_ids=template_ids,
            )

        bk_host_ids = [h.bk_host_id for h in hosts]
        return bk_host_ids[:500]

    def perform_request(self, validated_request_data):
        invalid_host = defaultdict(list)
        result = True
        bk_host_ids = []
        plugin_versions = {}
        # 其他采集类型的依赖版本暂不校验 or 旧版采集器processbeat下发进程采集不校验
        if validated_request_data["collect_type"] != PluginType.PROCESS:
            return {"result": True, "invalid_host": {}}
        target_nodes = validated_request_data["target_nodes"]
        if target_nodes:
            if target_nodes[0].get("bk_host_id"):
                bk_host_ids = [node["bk_host_id"] for node in target_nodes]
            elif target_nodes[0].get("ip"):
                bk_host_ids = self.get_host_ids(validated_request_data)
        # 无法获取对应目标，跳过版本校验
        if not bk_host_ids:
            return {"result": result, "plugin_version": plugin_versions, "invalid_host": invalid_host}
        for collect_type, check_plugins in PLUGIN_VERSION.items():
            if validated_request_data["collect_type"] != collect_type:
                continue
            # 动态进程采集依赖bkmonitorbeat-v2.10.0/v0.33.0
            all_plugin = api.node_man.plugin_search(
                {"page": 1, "pagesize": len(bk_host_ids), "conditions": [], "bk_host_id": bk_host_ids}
            )["list"]
            for plugin in all_plugin:
                for plugin_name, version in check_plugins.items():
                    beat_plugin = list(filter(lambda x: x["name"] == plugin_name, plugin["plugin_status"]))
                    if beat_plugin:
                        beat_plugin_version = beat_plugin[0]["version"].strip("\n")
                        beat_plugin_version = ".".join(beat_plugin_version.split(".")[:3])
                        try:
                            if beat_plugin_version and StrictVersion(beat_plugin_version) >= StrictVersion(version):
                                continue
                        except (ValueError, TypeError, AttributeError):
                            # 版本格式异常，提示校验不通过，仍可下发进程采集
                            pass
                    result = False
                    invalid_host[plugin_name].append(
                        (plugin.get("inner_ipv6", plugin["inner_ip"]), plugin["bk_cloud_id"])
                    )
        return {"result": result, "plugin_version": RECOMMENDED_VERSION, "invalid_host": invalid_host}
