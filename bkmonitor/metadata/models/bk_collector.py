"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import hashlib
import json
import logging
import time
from collections import defaultdict
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any

from django.conf import settings
from django.db import models

from constants.common import DEFAULT_TENANT_ID
from core.drf_resource import api

logger = logging.getLogger("metadata")


class BkCollectorDeployScene:
    """bk-collector 子配置下发场景，一个场景内 resource_key 唯一对应一条 V3 部署策略。"""

    APM_PLATFORM = "apm_platform"
    APM_APPLICATION = "apm_application"
    CUSTOM_REPORT = "custom_report"
    CUSTOM_LOG = "custom_log"
    PING_SERVER = "ping_server"


@dataclass
class _ExecuteBatch:
    """分批执行部署策略：每执行 batch_size 条后等待 interval 秒，再执行下一批"""

    batch_size: int
    interval: float
    on_wait: Callable[[int, float], None] | None = None
    executed: int = 0

    def before_execute(self):
        if self.executed and self.executed % self.batch_size == 0:
            if self.on_wait:
                self.on_wait(self.executed, self.interval)
            time.sleep(self.interval)
        self.executed += 1


# 仅在 execute_in_batches 上下文内生效，定时任务等其他调用方不受影响
_execute_batch: ContextVar[_ExecuteBatch | None] = ContextVar("bk_collector_execute_batch", default=None)


class BkCollectorDeployPolicy(models.Model):
    """
    bk-collector 子配置与节点管理 V3 部署策略的绑定关系

    V2 每份子配置是一条订阅；V3 改为一条 specify_plugin_sub_config_template 部署策略，
    下发范围、渲染上下文与 V2 订阅保持一致，节点管理生成的子配置文件名为
    <模板名去扩展名>_deploy_<部署策略ID><扩展名>，仍能命中 bk-collector 主配置里的 include 通配符。

    节点管理没有删除部署策略的接口，下线时把 scopes 置空并执行，由节点管理收敛删除子配置。
    """

    PLUGIN_NAME = "bk-collector"
    POLICY_NAME_PREFIX = "bkmonitor-collector"
    SPEC_TYPE = "specify_plugin_sub_config_template"
    SCOPE_TYPE = "instance"
    SCOPE_GRANULARITY = "host"
    PAGE_SIZE = 500
    # 主机所属业务缓存时间，同一轮刷新内大量策略共用同一批 Proxy，避免重复查询节点管理
    HOST_BIZ_CACHE_SECONDS = 600

    bk_tenant_id = models.CharField("租户ID", max_length=128, default=DEFAULT_TENANT_ID)
    scene = models.CharField("下发场景", max_length=32)
    resource_key = models.CharField("场景内资源标识", max_length=255)
    bk_biz_id = models.IntegerField("业务ID", default=0, db_index=True)
    bk_cloud_id = models.IntegerField("云区域ID", default=-1)
    policy_name = models.CharField("部署策略名称", max_length=255)
    deploy_policy_id = models.BigIntegerField("部署策略ID", null=True, default=None)
    fingerprint = models.CharField("最近一次成功下发的策略指纹", max_length=64, default="", blank=True)
    bk_host_ids = models.JSONField("最近一次成功下发的目标主机", default=list)
    last_workflow_id = models.CharField("最近一次执行的工作流ID", max_length=128, default="", blank=True)
    create_time = models.DateTimeField("创建时间", auto_now_add=True)
    update_time = models.DateTimeField("更新时间", auto_now=True)

    _host_biz_cache: dict[tuple[str, int], tuple[int, float]] = {}

    class Meta:
        verbose_name = "bk-collector 节点管理V3部署策略"
        verbose_name_plural = verbose_name
        unique_together = (("bk_tenant_id", "scene", "resource_key"),)
        db_table = "metadata_bk_collector_deploy_policy"

    @classmethod
    def is_enabled(cls) -> bool:
        return bool(getattr(settings, "ENABLE_BK_COLLECTOR_NODEMAN_V3", False))

    @classmethod
    def build_policy_name(cls, scene: str, resource_key: str) -> str:
        return f"{cls.POLICY_NAME_PREFIX}-{scene}-{resource_key}"

    @classmethod
    def deploy(
        cls,
        *,
        bk_tenant_id: str,
        scene: str,
        resource_key: str,
        template_name: str,
        context: dict[str, Any],
        bk_host_ids: list[int],
        bk_biz_id: int = 0,
        bk_cloud_id: int = -1,
    ) -> int | None:
        """
        按 V2 订阅同样的目标主机与上下文，声明一份 bk-collector 子配置

        目标主机为空时与 V2 一致直接跳过，不清空已下发配置，避免主机查询抖动导致配置被删除。
        已下发过的主机本轮在节点管理中查不到时（如主机同步延迟），保留上次下发范围不变更，
        避免节点管理删除这些主机上的子配置；业务明确移除的主机仍正常收缩。
        「已下发」以节点管理中该策略的实际范围为准，覆盖本地绑定丢失、上次执行失败未记录范围的情况。
        失败直接抛出，由调用方记录日志，不回退 V2。
        """
        host_ids = sorted({int(host_id) for host_id in bk_host_ids if host_id})
        if not host_ids:
            logger.info("[bk-collector-v3] skip %s(%s), no target hosts", scene, resource_key)
            return None

        record, _ = cls.objects.get_or_create(
            bk_tenant_id=bk_tenant_id,
            scene=scene,
            resource_key=resource_key,
            defaults={
                "bk_biz_id": bk_biz_id,
                "bk_cloud_id": bk_cloud_id,
                "policy_name": cls.build_policy_name(scene, resource_key),
            },
        )
        record.bk_biz_id = bk_biz_id
        record.bk_cloud_id = bk_cloud_id

        specs = cls._build_specs(template_name, context)
        scopes = cls._build_scopes(bk_tenant_id, host_ids)
        resolved_host_ids = sorted(host_id for scope in scopes for host_id in scope["scope"]["instance_ids"])
        if not resolved_host_ids:
            # 目标主机在节点管理 V3 中都查不到（如主机同步延迟），本轮不变更，避免清空已下发的配置
            logger.warning("[bk-collector-v3] skip %s(%s), no target hosts found in nodeman", scene, resource_key)
            return record.deploy_policy_id

        missing_host_ids = sorted(set(host_ids) - set(resolved_host_ids))
        if missing_host_ids:
            # 仍期望但本轮查不到的已下发主机：缩小范围会删除其子配置，保留上次有效范围，待下一轮查到后再更新
            lost_host_ids = sorted(set(missing_host_ids) & record._get_deployed_host_ids())
            if record.deploy_policy_id and lost_host_ids:
                logger.warning(
                    "[bk-collector-v3] keep last scopes of %s(%s), deployed hosts not found in nodeman: %s",
                    scene,
                    resource_key,
                    lost_host_ids,
                )
                return record.deploy_policy_id
            # 从未下发过的主机查不到时无法下发，先下发可解析的主机
            logger.warning(
                "[bk-collector-v3] %s(%s) skip new hosts not found in nodeman: %s",
                scene,
                resource_key,
                missing_host_ids,
            )
        # bk_host_ids 记录实际下发的主机，作为下一轮判断「已下发主机丢失」的依据
        return record._apply(specs=specs, scopes=scopes, bk_host_ids=resolved_host_ids)

    def withdraw(self) -> int | None:
        """清空下发范围，节点管理执行后会删除各主机上由该策略生成的子配置。"""
        if not self.deploy_policy_id:
            # 从未成功创建过策略，节点管理侧没有需要回收的配置
            self.delete()
            return None
        if not self.bk_host_ids and self.fingerprint:
            return self.deploy_policy_id
        # 策略已存在时只更新 scopes，保留原 specs
        return self._apply(specs=None, scopes=[], bk_host_ids=[])

    @classmethod
    @contextmanager
    def execute_in_batches(
        cls, batch_size: int, interval: float, on_wait: Callable[[int, float], None] | None = None
    ) -> Iterator[None]:
        """上下文内的策略执行按批进行，避免短时间触发大量执行导致节点管理渲染超时

        覆盖上下文内所有 execute 调用，包括 deploy 新建、更新策略后的立即执行。
        batch_size <= 0 或 interval <= 0 时不分批。
        """
        if batch_size <= 0 or interval <= 0:
            yield
            return
        token = _execute_batch.set(_ExecuteBatch(batch_size=batch_size, interval=interval, on_wait=on_wait))
        try:
            yield
        finally:
            _execute_batch.reset(token)

    def execute(self) -> str:
        """立即执行一次策略（节点管理也会每小时自动执行全部启用的策略）。"""
        if not self.deploy_policy_id:
            return ""
        batch = _execute_batch.get()
        if batch:
            batch.before_execute()
        result = api.node_man_v3.execute_deploy_policy(
            bk_tenant_id=self.bk_tenant_id, deploy_policy_id=self.deploy_policy_id
        )
        workflow_id = (result or {}).get("workflow_id") or ""
        if not workflow_id:
            raise ValueError(f"execute deploy policy({self.deploy_policy_id}) returned no workflow_id")
        self.last_workflow_id = workflow_id
        self.save(update_fields=["last_workflow_id", "update_time"])
        return workflow_id

    def _apply(self, *, specs: list[dict] | None, scopes: list[dict], bk_host_ids: list[int]) -> int:
        fingerprint = self._fingerprint(specs, scopes)
        if self.deploy_policy_id and self.fingerprint == fingerprint:
            return self.deploy_policy_id

        if not self.deploy_policy_id:
            # 绑定记录丢失策略ID（例如创建成功但保存前异常）时，按策略名找回，避免重复创建同名策略
            self.deploy_policy_id = self._find_policy_id()

        if self.deploy_policy_id:
            policy = {
                "deploy_policy_id": self.deploy_policy_id,
                "meta": {"name": self.policy_name, "description": self._description()},
                "scopes": scopes,
                "enabled": True,
            }
            fields = {"meta": True, "scopes": True, "enabled": True, "specs": specs is not None}
            if specs is not None:
                policy["specs"] = specs
            api.node_man_v3.update_deploy_policy(
                bk_tenant_id=self.bk_tenant_id, deploy_policies=[policy], fields=fields
            )
            logger.info(
                "[bk-collector-v3] update deploy policy(%s) %s, hosts: %s",
                self.deploy_policy_id,
                self.policy_name,
                bk_host_ids,
            )
        else:
            if specs is None:
                raise ValueError(f"deploy policy {self.policy_name} not found, can not withdraw without specs")
            result = api.node_man_v3.create_deploy_policy(
                bk_tenant_id=self.bk_tenant_id,
                name=self.policy_name,
                description=self._description(),
                enabled=True,
                specs=specs,
                scopes=scopes,
            )
            deploy_policy_id = int((result or {}).get("deploy_policy_id") or 0)
            if not deploy_policy_id:
                raise ValueError(f"create deploy policy {self.policy_name} returned no deploy_policy_id")
            self.deploy_policy_id = deploy_policy_id
            logger.info(
                "[bk-collector-v3] create deploy policy(%s) %s, hosts: %s",
                deploy_policy_id,
                self.policy_name,
                bk_host_ids,
            )
        # 策略ID优先落库，执行失败时下一轮仍能复用该策略
        self.save()

        self.execute()

        # 指纹只在成功派发后写入，失败时下一轮刷新会重试
        self.fingerprint = fingerprint
        self.bk_host_ids = bk_host_ids
        self.save(update_fields=["fingerprint", "bk_host_ids", "update_time"])
        return self.deploy_policy_id

    def _description(self) -> str:
        return f"bkmonitor bk-collector {self.scene} sub config: {self.resource_key}"

    def _get_deployed_host_ids(self) -> set[int]:
        """已下发主机：本地记录与节点管理中该策略的实际范围取并集

        本地记录可能不可信：绑定丢失时需按名称找回策略；上次更新范围后执行失败时 bk_host_ids 未更新，
        而节点管理的每小时自动执行可能已按新范围下发。找回的策略 ID 同时写回本地绑定。
        """
        deployed_host_ids = {int(host_id) for host_id in self.bk_host_ids or []}
        remote_policy = self._find_remote_policy()
        if not remote_policy:
            return deployed_host_ids

        remote_policy_id = int(remote_policy["deploy_policy_id"])
        if self.deploy_policy_id and self.deploy_policy_id != remote_policy_id:
            # 本地绑定与同名远端策略不一致时不混用范围，以本地绑定为准
            return deployed_host_ids
        if not self.deploy_policy_id:
            self.deploy_policy_id = remote_policy_id
            self.save(update_fields=["deploy_policy_id", "bk_biz_id", "bk_cloud_id", "update_time"])

        for scope in remote_policy.get("scopes") or []:
            deployed_host_ids.update(int(host_id) for host_id in (scope.get("scope") or {}).get("instance_ids") or [])
        return deployed_host_ids

    def _find_policy_id(self) -> int | None:
        remote_policy = self._find_remote_policy()
        return int(remote_policy["deploy_policy_id"]) if remote_policy else None

    def _find_remote_policy(self) -> dict[str, Any] | None:
        matches: dict[int, dict[str, Any]] = {}
        offset = 0
        while True:
            data = api.node_man_v3.list_deploy_policies(
                bk_tenant_id=self.bk_tenant_id,
                page={"offset": offset, "limit": self.PAGE_SIZE},
                exact_include_conditions={"deploy_policy_name": [self.policy_name]},
            )
            items = (data or {}).get("items") or []
            for item in items:
                name = (item.get("meta") or {}).get("name") or item.get("name")
                deploy_policy_id = int(item.get("deploy_policy_id") or 0)
                if name == self.policy_name and deploy_policy_id:
                    matches[deploy_policy_id] = item
            if len(items) < self.PAGE_SIZE:
                break
            offset += self.PAGE_SIZE

        if len(matches) > 1:
            raise ValueError(f"found multiple deploy policies named {self.policy_name}: {sorted(matches)}")
        return next(iter(matches.values())) if matches else None

    @classmethod
    def _build_specs(cls, template_name: str, context: dict[str, Any]) -> list[dict]:
        # 上下文先做一次 JSON 往返：与节点管理存储后的形态一致（如整型字典键转为字符串），指纹才稳定
        context = json.loads(json.dumps(context, default=str))
        return [
            {
                "type": cls.SPEC_TYPE,
                "param": {
                    "plugin_name": cls.PLUGIN_NAME,
                    "config_files_detail": [{"template_name": template_name, "is_main_config": False}],
                    "custom_config_context": context,
                },
            }
        ]

    @classmethod
    def _build_scopes(cls, bk_tenant_id: str, host_ids: list[int]) -> list[dict]:
        """V3 instance 范围要求带主机所属业务，按业务分组生成。"""
        host_biz_ids = cls._get_host_biz_ids(bk_tenant_id, host_ids)
        biz_host_ids: dict[int, list[int]] = defaultdict(list)
        for host_id in host_ids:
            if host_id not in host_biz_ids:
                logger.warning("[bk-collector-v3] host(%s) not found in nodeman v3, skip it", host_id)
                continue
            biz_host_ids[host_biz_ids[host_id]].append(host_id)

        return [
            {
                "type": cls.SCOPE_TYPE,
                "scope": {
                    "granularity": cls.SCOPE_GRANULARITY,
                    "bk_biz_id": bk_biz_id,
                    "instance_ids": sorted(biz_host_ids[bk_biz_id]),
                },
            }
            for bk_biz_id in sorted(biz_host_ids)
        ]

    @classmethod
    def _get_host_biz_ids(cls, bk_tenant_id: str, host_ids: list[int]) -> dict[int, int]:
        now = time.time()
        result: dict[int, int] = {}
        missing: list[int] = []
        for host_id in host_ids:
            cached = cls._host_biz_cache.get((bk_tenant_id, host_id))
            if cached and now - cached[1] < cls.HOST_BIZ_CACHE_SECONDS:
                result[host_id] = cached[0]
            else:
                missing.append(host_id)

        for start in range(0, len(missing), cls.PAGE_SIZE):
            batch = missing[start : start + cls.PAGE_SIZE]
            offset = 0
            while True:
                data = api.node_man_v3.list_hosts(
                    bk_tenant_id=bk_tenant_id,
                    page={"offset": offset, "limit": cls.PAGE_SIZE},
                    exact_include_conditions={"bk_host_id": batch},
                )
                items = (data or {}).get("items") or []
                for item in items:
                    host_id, bk_biz_id = int(item["bk_host_id"]), int(item["info"]["bk_biz_id"])
                    result[host_id] = bk_biz_id
                    cls._host_biz_cache[(bk_tenant_id, host_id)] = (bk_biz_id, now)
                offset += len(items)
                if not items or offset >= int((data or {}).get("total") or 0):
                    break
        return result

    @staticmethod
    def _fingerprint(specs: list[dict] | None, scopes: list[dict]) -> str:
        content = json.dumps({"specs": specs, "scopes": scopes}, sort_keys=True, default=str)
        return hashlib.sha256(content.encode()).hexdigest()
