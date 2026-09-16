"""
拨测任务管理器

提供任务的完整生命周期管理
"""

import json
import logging
from collections.abc import Callable
from datetime import datetime
from typing import Any, cast, final

from bkmonitor.nodeman_integration.backend import node_man_backend
from bkmonitor.nodeman_integration.exceptions import NodeManV3CapabilityBlocked
from django.db.models import Q
from django.utils.translation import gettext as _
from packaging.version import Version

from bk_monitor_base.domains.space.cache import bk_biz_id_to_bk_tenant_id
from bk_monitor_base.domains.uptime_check.collector import UptimeCheckCollector
from bk_monitor_base.domains.uptime_check.constants import RESULT_MSG, UDP_RESULT_MSG
from bk_monitor_base.domains.uptime_check.define import UptimeCheckTaskStatus
from bk_monitor_base.domains.uptime_check.models import (
    UptimeCheckNodeModel,
    UptimeCheckTaskCollectorLog,
    UptimeCheckTaskModel,
    UptimeCheckTaskSubscription,
)
from bk_monitor_base.domains.uptime_check.services.data_access import DataAccessService
from bk_monitor_base.domains.uptime_check.services.subscription import SubscriptionService
from bk_monitor_base.infras.conversion import safe_int
from bk_monitor_base.infras.exception.base_error import BaseError
from bk_monitor_base.infras.third_party_api.nodeman import api as node_man_v2_api

logger = logging.getLogger(__name__)


class TestTaskError(BaseError):
    """拨测任务测试异常。"""


@final
class TaskManager:
    """
    拨测任务管理器

    封装任务部署、启动、停止等完整流程
    """

    def __init__(
        self,
        task: UptimeCheckTaskModel,
        on_deploy_success: Callable[[UptimeCheckTaskModel], None] | None = None,
    ):
        """
        初始化任务管理器

        Args:
            task: 拨测任务模型实例
            on_deploy_success: 部署成功后的回调钩子函数，接收 task 作为参数
        """
        self.task = task
        self.bk_tenant_id = bk_biz_id_to_bk_tenant_id(task.bk_biz_id)
        self.on_deploy_success = on_deploy_success
        self.use_nodeman_v3 = node_man_backend.is_v3
        if self.use_nodeman_v3:
            from bk_monitor_base.domains.uptime_check.services.nodeman_v3 import UptimeCheckNodeManV3Service

            self.nodeman_v3_service = UptimeCheckNodeManV3Service()
        else:
            self.nodeman_v3_service = None

        # 初始化服务
        self.subscription_service = SubscriptionService(bk_biz_id=task.bk_biz_id)

        self.data_access_service = DataAccessService(
            bk_tenant_id=self.bk_tenant_id, bk_biz_id=task.bk_biz_id, protocol=task.protocol
        )

    def test(self, node_id_list: list[int] | None = None) -> str:
        """
        测试拨测任务配置。

        下发测试配置，采集器只执行一次数据采集，直接返回采集结果，不经过计算平台。

        Args:
            node_id_list: 节点ID列表；为空时使用任务关联的所有节点。

        Returns:
            测试结果消息。

        Raises:
            TestTaskError: 测试失败时抛出异常。

        Note:
            权限检查（如公共节点权限）应由调用方在上层实现，底座不负责权限校验。
        """
        config = self.task.config or {}
        protocol = self.task.protocol

        # 1) 获取节点信息：如果传入 node_id_list 则按ID筛选，否则用任务关联节点
        if node_id_list is None:
            all_nodes = self.task.nodes.all()
        else:
            # 兼容历史数据：部分节点可能未回填 bk_tenant_id（为空），此时允许走测试流程
            all_nodes = UptimeCheckNodeModel.objects.filter(id__in=node_id_list).filter(
                Q(bk_tenant_id=self.bk_tenant_id) | Q(bk_tenant_id="")
            )

        biz_nodes: list[UptimeCheckNodeModel] = []
        common_nodes: list[UptimeCheckNodeModel] = []
        for node in all_nodes:
            # 测试前回填 host_id（如果无法回填，也允许走 ip + plat_id 测试）
            node.set_host_id()
            if node.is_common:
                common_nodes.append(node)
            else:
                biz_nodes.append(node)

        # 2) 版本校验：依赖 bkmonitorbeat 推荐版本 >= 3.5.0
        all_plugin: list[dict[str, Any]] = []
        if self.use_nodeman_v3:
            hosts_by_business: dict[int, list[int]] = {}
            for node in [*biz_nodes, *common_nodes]:
                if node.bk_host_id:
                    hosts_by_business.setdefault(node.bk_biz_id, []).append(int(node.bk_host_id))
            for target_bk_biz_id, target_host_ids in hosts_by_business.items():
                all_plugin.extend(
                    cast(
                        list[dict[str, Any]],
                        node_man_backend.v3.plugin_search_host_status(
                            bk_tenant_id=bk_biz_id_to_bk_tenant_id(target_bk_biz_id),
                            bk_biz_id=target_bk_biz_id,
                            bk_host_ids=target_host_ids,
                            plugin_names=["bkmonitorbeat"],
                        ),
                    )
                )
        else:
            bk_host_ids = [
                int(host_id)
                for host_id in all_nodes.values_list("bk_host_id", flat=True).distinct()
                if host_id
            ]
            plugin_result = node_man_v2_api.plugin_search(
                bk_tenant_id=self.bk_tenant_id,
                params=node_man_v2_api.PluginSearchParams(
                    page=1,
                    pagesize=max(len(bk_host_ids), 1),
                    conditions=[],
                    bk_host_id=bk_host_ids,
                ),
            )
            all_plugin = cast(list[dict[str, Any]], plugin_result.get("list", []))
        invalid_nodes: list[str] = []
        for plugin in all_plugin:
            plugin_status_list: list[dict[str, Any]] = [
                item for item in plugin.get("plugin_status", []) if isinstance(item, dict)
            ]
            beat_plugin: list[dict[str, Any]] = [
                item for item in plugin_status_list if item.get("name") == "bkmonitorbeat"
            ]
            if beat_plugin:
                beat_plugin_version = str(beat_plugin[0].get("version", "")).strip("\n")
                beat_plugin_version = ".".join(beat_plugin_version.split(".")[:3])
                try:
                    if beat_plugin_version and Version(beat_plugin_version) >= Version("3.5.0"):
                        continue
                except Exception:
                    # 版本格式异常，仍可测试下发拨测任务
                    pass
            invalid_nodes.append(f"{plugin['inner_ip'] or plugin['inner_ipv6']}-{plugin['bk_cloud_id']}")
        if invalid_nodes:
            raise TestTaskError(f"部分节点版本校验失败，推荐升级至v3.5.0以上版本:{','.join(invalid_nodes)}")

        # 3) 下发测试并收集结果
        success: list[dict[str, Any]] = []

        # 3.1) 非公共业务节点：可一次性按 host 列表下发
        if biz_nodes:
            collector = UptimeCheckCollector(bk_biz_id=biz_nodes[0].bk_biz_id)

            node_list: list[dict[str, Any]] = []
            for node in biz_nodes:
                if node.bk_host_id:
                    node_list.append({"bk_host_id": node.bk_host_id})
                else:
                    node_list.append({"ip": node.ip, "plat_id": node.plat_id})

            biz_result = collector.test(
                task={"config": config, "protocol": protocol, "bk_biz_id": self.task.bk_biz_id},
                hosts=node_list,
                bk_tenant_id=self.bk_tenant_id,
            )

            if len(biz_result["failed"]):
                err_msg = ""
                for err_obj in biz_result["failed"]:
                    err_msg += (
                        _(" 节点:") + f"{err_obj['bk_host_id']}|{err_obj.get('ip', '')}" + " - " + err_obj["errmsg"]
                    )
                raise TestTaskError(_("部分节点测试失败:%s") % err_msg, data=biz_result["failed"])
            success = success + biz_result["success"]

        # 3.2) 公共业务节点：可能遇到业务权限问题，逐个节点下发
        if common_nodes:
            common_result: list[dict[str, Any]] = []
            for node in common_nodes:
                collector = UptimeCheckCollector(bk_biz_id=node.bk_biz_id)
                node_list = (
                    [{"bk_host_id": node.bk_host_id}] if node.bk_host_id else [{"ip": node.ip, "plat_id": node.plat_id}]
                )
                result = collector.test(
                    bk_tenant_id=self.bk_tenant_id,
                    task={"config": config, "protocol": protocol, "bk_biz_id": self.task.bk_biz_id},
                    hosts=node_list,
                )
                common_result.append(result)

            common_failed = [r["failed"][0] for r in common_result if len(r["failed"])]
            common_success = [r["success"][0] for r in common_result if len(r["success"])]

            if len(common_failed):
                err_msg = ""
                for err_obj in common_failed:
                    err_msg += (
                        _(" 节点:") + f"{err_obj['bk_host_id']}|{err_obj.get('ip', '')}" + " - " + err_obj["errmsg"]
                    )
                raise TestTaskError(_("部分节点测试失败:%s") % err_msg, data=common_failed)
            success = success + common_success

        # 4) 解析结果：从 log_content 提取 error_code 并映射为错误信息
        try:
            if not success:
                raise TestTaskError(_("采集器无返回"))

            ok_result: list[str] = []
            fail_result: list[str] = []
            for success_info in success:
                log_content = success_info.get("log_content")
                assert isinstance(log_content, str)
                content_list = [line for line in log_content.split("\n") if line.startswith("{")]
                if protocol == UptimeCheckTaskModel.Protocol.ICMP:
                    failed_content_list = [
                        content
                        for content in content_list
                        if int(json.loads(content).get("dimensions")["error_code"]) != 0
                    ]
                else:
                    failed_content_list = [
                        content for content in content_list if json.loads(content).get("error_code") != 0
                    ]
                result_msg_map = UDP_RESULT_MSG if protocol == UptimeCheckTaskModel.Protocol.UDP else RESULT_MSG
                error_message: list[str] = []
                for failed_content in failed_content_list:
                    failed_content_dict = json.loads(failed_content)
                    error_code = str(failed_content_dict["error_code"])
                    if error_code in result_msg_map:
                        msg = result_msg_map[error_code]
                    else:
                        msg = _("未知错误（{error_code}）").format(error_code=error_code)
                        msg += f"message: {failed_content}"

                    error_message.append(
                        "{} {} {}".format(
                            failed_content_dict.get("target_host", ""),
                            failed_content_dict.get("message", ""),
                            msg,
                        )
                    )

                if not failed_content_list:
                    ok_result.append(RESULT_MSG["0"])
                else:
                    q_params = Q(bk_host_id=success_info["bk_host_id"])
                    if success_info["ip"]:
                        q_params = Q(ip=success_info["ip"]) | Q(bk_host_id=success_info["bk_host_id"])
                    node = all_nodes.filter(q_params).first()
                    assert node is not None
                    fail_result.append("node:{node}, log:{log}".format(node=node.name, log=" | ".join(error_message)))

            if len(fail_result):
                raise TestTaskError("\n".join(fail_result))
            if not ok_result:
                raise TestTaskError(_("采集器无返回"))
            return ok_result[0]

        except KeyError:
            err_msg = ""
            if success:
                err_msg = str(success[0].get("log_content", ""))
            raise TestTaskError(err_msg if err_msg else _("采集器无返回"))
        except ValueError:
            raise TestTaskError(_("采集器返回结果校验失败，请重试"))
        except TestTaskError:
            raise
        except Exception as e:
            logger.exception(e)
            raise TestTaskError(_("校验测试结果时发生异常，请联系系统管理员"))

    def deploy(self, *, force_nodeman_v3: bool = False) -> str:
        """部署任务

        完整的部署流程:
        1. 数据接入(申请DataID)
        2. 更新任务状态为启动中
        3. 判断是新增还是更新
        4. 创建/更新订阅
        5. 启用订阅
        6. 更新任务状态

        Returns:
            "success" 表示成功

        Raises:
            Exception: 部署失败时抛出异常
        """
        logger.info(f"开始部署拨测任务: task_id={self.task.pk}, protocol={self.task.protocol}")

        try:
            # 数据接入(获取或创建DataID)
            use_custom, data_id = self.data_access_service.get_or_create_data_id(
                independent=self.task.indepentent_dataid
            )

            # 更新任务状态
            self.task.status = UptimeCheckTaskStatus.STARTING.value
            self.task.save()

            # 修改节点管理日志

            UptimeCheckTaskCollectorLog.objects.filter(task_id=self.task.pk).update(is_deleted=True)

            # 准备节点数据
            nodes: list[dict[str, Any]] = []
            for node in self.task.nodes.all():
                nodes.append(
                    {"bk_biz_id": node.bk_biz_id, "bk_host_id": node.bk_host_id, "ip": node.ip, "plat_id": node.plat_id}
                )

            # 生成订阅配置
            task_group_id = self._get_task_group_id()
            subscription_configs = self.subscription_service.generate_subscription_config(
                task_id=self.task.pk,
                protocol=self.task.protocol,
                config=self.task.config or {},
                nodes=nodes,
                data_id=data_id,
                labels=self.task.labels or {},
                task_group_id=task_group_id,
                use_custom_report=use_custom,
            )

            if self.use_nodeman_v3:
                assert self.nodeman_v3_service is not None
                self.nodeman_v3_service.preflight_deploy(self.task, subscription_configs)
                for subscription_config in subscription_configs:
                    self.nodeman_v3_service.ensure(
                        self.task,
                        subscription_config,
                        force=force_nodeman_v3,
                    )
            else:
                existing_subscriptions = self._get_existing_subscriptions()

                # 判断是新增还是更新
                if not existing_subscriptions:
                    # 新增流程
                    self._handle_create_subscriptions(subscription_configs)
                else:
                    # 更新流程
                    self._handle_update_subscriptions(subscription_configs, existing_subscriptions)

            # 执行部署成功回调钩子(如:追加指标缓存)
            if self.on_deploy_success:
                try:
                    self.on_deploy_success(self.task)
                except Exception as hook_error:
                    logger.warning(f"部署成功回调执行失败: task_id={self.task.pk}, error={hook_error}")

            logger.info(f"拨测任务部署成功: task_id={self.task.pk}")
            return "success"

        except Exception as e:
            logger.error(f"拨测任务部署失败: task_id={self.task.pk}, error={e}")
            self.task.status = UptimeCheckTaskStatus.START_FAILED.value
            self.task.save()
            raise

    def start(self, operator: str) -> str:
        """
        启动任务

        完整流程:
        1. 前置检查是否有运行中的启停任务
        2. 如果没有订阅则执行deploy
        3. 如果有订阅则更新状态,启用订阅并执行START操作
        4. 更新任务状态为运行中

        Returns:
            "success" 表示成功

        Raises:
            Exception: 启动失败时抛出异常
        """
        logger.info(f"启动拨测任务: task_id={self.task.pk}")

        if self.use_nodeman_v3:
            return self._start_nodeman_v3(operator)

        # 步骤1: 前置检查是否有运行中的启停任务
        try:
            subscriptions = self._get_existing_subscriptions()
            if subscriptions:
                subscription_id = subscriptions[0]
                instance_list, _ = node_man_v2_api.batch_get_subscription_task_result(
                    bk_tenant_id=self.bk_tenant_id,
                    params={"subscription_id": safe_int(subscription_id)},
                )
                for instance in instance_list:
                    status = instance.get("status")
                    if status in ["PENDING", "RUNNING"]:
                        raise Exception(f"存在运行中的启停任务(status={status}),请稍后再试")
        except Exception as e:
            logger.error(f"拨测任务启停前置检查失败: {e}")
            raise

        try:
            # 步骤2: 判断是否需要deploy
            if not subscriptions:
                # 没有订阅,执行完整部署
                return self.deploy()

            # 步骤3: 更新状态为启动中
            self.task.status = UptimeCheckTaskStatus.STARTING.value
            self.task.update_user = operator
            self.task.save(update_fields=["status", "update_user", "update_time"])

            # 步骤4: 启用订阅
            for subscription in subscriptions:
                node_man_v2_api.switch_subscription(
                    bk_tenant_id=self.bk_tenant_id,
                    subscription_id=safe_int(subscription),
                    action="enable",
                )

            # 步骤5: 执行START操作
            action_name = f"bkmonitorbeat_{self.task.protocol.lower()}"
            for subscription in subscriptions:
                node_man_v2_api.run_subscription(
                    bk_tenant_id=self.bk_tenant_id,
                    subscription_id=safe_int(subscription),
                    actions={action_name: "START"},
                )

            # 步骤6: 更新状态为运行中
            self.task.status = UptimeCheckTaskStatus.RUNNING.value
            self.task.update_user = operator
            self.task.save(update_fields=["status", "update_user", "update_time"])

            logger.info(f"拨测任务启动成功: task_id={self.task.pk}")
            return "success"

        except Exception as e:
            logger.error(f"拨测任务启动失败: task_id={self.task.pk}, error={e}")
            self.task.status = UptimeCheckTaskStatus.START_FAILED.value
            self.task.update_user = operator
            self.task.save(update_fields=["status", "update_user", "update_time"])
            raise

    def stop(self, operator: str) -> str:
        """
        停止任务

        完整流程:
        1. 前置检查是否有运行中的启停任务
        2. 检查订阅是否存在
        3. 更新状态为停止中,关闭订阅并执行STOP操作
        4. 更新任务状态为已停止

        Returns:
            "success" 表示成功

        Raises:
            Exception: 停止失败时抛出异常
        """
        logger.info(f"停止拨测任务: task_id={self.task.pk}")

        if self.use_nodeman_v3:
            raise NodeManV3CapabilityBlocked(
                "uptime stop requires the DeployPolicy reverse field; enabled must remain true"
            )

        # 步骤1: 前置检查是否有运行中的启停任务
        try:
            subscriptions = self._get_existing_subscriptions()
            if not subscriptions:
                raise Exception("拨测任务对应订阅信息不存在")

            subscription_id = subscriptions[0]
            instance_list, _ = node_man_v2_api.batch_get_subscription_task_result(
                bk_tenant_id=self.bk_tenant_id,
                params={"subscription_id": safe_int(subscription_id)},
            )
            for instance in instance_list:
                status = instance["status"]
                if status in ["PENDING", "RUNNING"]:
                    raise Exception(f"存在运行中的启停任务(status={status}),请稍后再试")
        except Exception as e:
            logger.error(f"拨测任务启停前置检查失败: {e}")
            raise

        # 步骤2: 更新状态为停止中
        self.task.status = UptimeCheckTaskStatus.STOPING.value
        self.task.update_user = operator
        self.task.save(update_fields=["status", "update_user", "update_time"])

        try:
            # 步骤3: 关闭订阅
            for subscription in subscriptions:
                node_man_v2_api.switch_subscription(
                    bk_tenant_id=self.bk_tenant_id,
                    subscription_id=safe_int(subscription),
                    action="disable",
                )

            # 步骤4: 执行STOP操作
            action_name = f"bkmonitorbeat_{self.task.protocol.lower()}"
            for subscription in subscriptions:
                node_man_v2_api.run_subscription(
                    bk_tenant_id=self.bk_tenant_id,
                    subscription_id=safe_int(subscription),
                    actions={action_name: "STOP"},
                )

            # 步骤5: 更新状态为已停止
            self.task.status = UptimeCheckTaskStatus.STOPED.value
            self.task.update_user = operator
            self.task.save(update_fields=["status", "update_user", "update_time"])

            logger.info(f"拨测任务停止成功: task_id={self.task.pk}")
            return "success"

        except Exception as e:
            logger.error(f"拨测任务停止失败: task_id={self.task.pk}, error={e}")
            self.task.status = UptimeCheckTaskStatus.STOP_FAILED.value
            self.task.update_user = operator
            self.task.save(update_fields=["status", "update_user", "update_time"])
            raise

    def delete(self, operator: str) -> None:
        """
        删除任务

        删除所有关联的订阅
        """
        logger.info(f"删除拨测任务: task_id={self.task.pk}")

        if self.use_nodeman_v3:
            raise NodeManV3CapabilityBlocked(
                "uptime delete requires the DeployPolicy reverse field; DeployPolicy delete only detaches management"
            )

        action_name = f"bkmonitorbeat_{self.task.protocol.lower()}"
        subscriptions = self._get_existing_subscriptions()

        # 先关闭订阅
        for subscription_id in subscriptions:
            node_man_v2_api.switch_subscription(
                bk_tenant_id=self.bk_tenant_id,
                subscription_id=safe_int(subscription_id),
                action="disable",
            )

        # 再删除订阅
        for subscription_id in subscriptions:
            node_man_v2_api.run_subscription(
                bk_tenant_id=self.bk_tenant_id,
                subscription_id=safe_int(subscription_id),
                actions={action_name: "UNINSTALL_AND_DELETE"},
            )

        # 标记订阅为已删除
        UptimeCheckTaskSubscription.objects.filter(uptimecheck_id=self.task.pk).update(
            is_deleted=True, update_user=operator, update_time=datetime.now()
        )

    def _get_task_group_id(self) -> str:
        """获取任务分组ID"""
        try:
            # groups是通过related_name获取的
            task_group_ids: list[int] = list(self.task.groups.values_list("id", flat=True))
            task_group_ids.sort()
            if not task_group_ids:
                return "0"
            return ",".join(map(str, task_group_ids))
        except Exception:
            return "0"

    def _get_existing_subscriptions(self) -> list[int]:
        """获取已存在的订阅"""
        subscriptions = UptimeCheckTaskSubscription.objects.filter(
            uptimecheck_id=self.task.pk,
            is_deleted=False,  # 添加is_deleted过滤
            node_man_backend="v2",
        ).values_list("subscription_id", flat=True)

        return list(subscriptions)

    def _start_nodeman_v3(self, operator: str) -> str:
        """Reconcile the current forward policies for an explicit start request."""

        assert self.nodeman_v3_service is not None
        relations = list(
            UptimeCheckTaskSubscription.objects.filter(
                uptimecheck_id=self.task.pk,
                is_deleted=False,
            ).order_by("pk")
        )
        if not relations:
            return self.deploy(force_nodeman_v3=True)
        invalid_relations = [relation.pk for relation in relations if relation.node_man_backend != "v3"]
        if invalid_relations:
            raise NodeManV3CapabilityBlocked(
                f"uptime task {self.task.pk} still has V2 subscriptions: {invalid_relations}"
            )

        self.task.update_user = operator
        self.task.save(update_fields=["update_user", "update_time"])
        return self.deploy(force_nodeman_v3=True)

    def _handle_create_subscriptions(self, subscription_configs: list[dict[str, Any]]) -> None:
        """处理创建订阅"""
        logger.info(f"创建新订阅: task_id={self.task.pk}, count={len(subscription_configs)}")

        for config in subscription_configs:
            subscription_params = node_man_v2_api.CreateSubscriptionParams(
                steps=config["steps"],
                run_immediately=config["run_immediately"],
                scope=config["scope"],
            )

            if "target_hosts" in config:
                subscription_params["target_hosts"] = config["target_hosts"]

            # 向节点管理创建订阅（关键操作：保留少量日志）
            result = node_man_v2_api.create_subscription(
                bk_tenant_id=self.bk_tenant_id,
                params=subscription_params,
            )
            logger.info(
                "订阅创建成功: task_id=%s, subscription_id=%s, bk_biz_id=%s",
                self.task.pk,
                result.get("subscription_id"),
                config.get("scope", {}).get("bk_biz_id"),
            )

            # 保存订阅关系
            UptimeCheckTaskSubscription.objects.create(
                uptimecheck_id=self.task.pk,
                subscription_id=result["subscription_id"],
                bk_biz_id=config["scope"]["bk_biz_id"],
            )

        # 启用订阅
        subscriptions = self._get_existing_subscriptions()
        for subscription_id in subscriptions:
            node_man_v2_api.switch_subscription(
                bk_tenant_id=self.bk_tenant_id,
                subscription_id=safe_int(subscription_id),
                action="enable",
            )

    def _handle_update_subscriptions(
        self, subscription_configs: list[dict[str, Any]], existing_subscriptions: list[int]
    ) -> None:
        """处理更新订阅"""
        logger.info(f"更新订阅: task_id={self.task.pk}")

        # 先关闭所有订阅
        for subscription_id in existing_subscriptions:
            node_man_v2_api.switch_subscription(
                bk_tenant_id=self.bk_tenant_id,
                subscription_id=safe_int(subscription_id),
                action="disable",
            )

        # 获取现有订阅的详细信息
        existing_sub_details = list(
            UptimeCheckTaskSubscription.objects.filter(
                subscription_id__in=existing_subscriptions,
                is_deleted=False,
            ).values("subscription_id", "bk_biz_id")
        )

        # 构建业务ID到订阅ID的映射
        biz_to_sub = {sub["bk_biz_id"]: sub["subscription_id"] for sub in existing_sub_details}

        # 分类处理: 更新/新增/删除
        create_configs: list[dict[str, Any]] = []
        delete_sub_ids = list(biz_to_sub.keys())

        for config in subscription_configs:
            bk_biz_id = config["scope"]["bk_biz_id"]

            if bk_biz_id in biz_to_sub:
                # 更新
                subscription_id = biz_to_sub[bk_biz_id]
                update_params = node_man_v2_api.UpdateSubscriptionParams(
                    subscription_id=subscription_id,
                    steps=config["steps"],
                    run_immediately=True,
                    scope=config.get("scope"),
                )
                node_man_v2_api.update_subscription(
                    bk_tenant_id=self.bk_tenant_id,
                    params=update_params,
                )
                logger.info(
                    "订阅更新成功: task_id=%s, subscription_id=%s, bk_biz_id=%s",
                    self.task.pk,
                    subscription_id,
                    bk_biz_id,
                )
                delete_sub_ids.remove(bk_biz_id)
            else:
                # 新增
                create_configs.append(config)

        # 删除不再需要的订阅
        if delete_sub_ids:
            action_name = f"bkmonitorbeat_{self.task.protocol.lower()}"
            for bk_biz_id in delete_sub_ids:
                subscription_id = biz_to_sub[bk_biz_id]
                node_man_v2_api.run_subscription(
                    bk_tenant_id=self.bk_tenant_id,
                    subscription_id=safe_int(subscription_id),
                    actions={action_name: "UNINSTALL_AND_DELETE"},
                )
                logger.info(
                    "订阅删除成功: task_id=%s, subscription_id=%s, bk_biz_id=%s",
                    self.task.pk,
                    subscription_id,
                    bk_biz_id,
                )
                UptimeCheckTaskSubscription.objects.filter(subscription_id=subscription_id).update(is_deleted=True)

        # 创建新订阅
        for config in create_configs:
            subscription_params = node_man_v2_api.CreateSubscriptionParams(
                steps=config["steps"],
                run_immediately=config["run_immediately"],
                scope=config["scope"],
            )
            if "target_hosts" in config:
                subscription_params["target_hosts"] = config["target_hosts"]

            result = node_man_v2_api.create_subscription(
                bk_tenant_id=self.bk_tenant_id,
                params=subscription_params,
            )
            logger.info(
                "订阅创建成功: task_id=%s, subscription_id=%s, bk_biz_id=%s",
                self.task.pk,
                result.get("subscription_id"),
                config.get("scope", {}).get("bk_biz_id"),
            )
            UptimeCheckTaskSubscription.objects.create(
                uptimecheck_id=self.task.pk,
                subscription_id=result["subscription_id"],
                bk_biz_id=config["scope"]["bk_biz_id"],
            )

        # 重新启用所有订阅
        subscriptions = self._get_existing_subscriptions()
        for subscription_id in subscriptions:
            node_man_v2_api.switch_subscription(
                bk_tenant_id=self.bk_tenant_id,
                subscription_id=safe_int(subscription_id),
                action="enable",
            )
