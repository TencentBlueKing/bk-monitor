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
import base64
import copy
import re
from collections import OrderedDict, defaultdict
from functools import cmp_to_key, lru_cache
from typing import Dict, List, Optional, Union

import arrow
from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils.functional import cached_property
from django.utils.translation import ugettext as _
from django.utils.translation import ugettext_lazy as _lazy

from bkmonitor.commons.storage import get_default_image_storage
from bkmonitor.utils.db.fields import JsonField, YamlField
from bkmonitor.utils.user import get_global_user
from core.drf_resource import api
from monitor_web.commons.data_access import PluginDataAccessor
from monitor_web.models import OperateRecordModelBase
from monitor_web.plugin.constant import (
    DEFAULT_TRAP_V3_CONFIG,
    PLUGIN_REVERSED_DIMENSION,
    PluginType,
)
from monitor_web.plugin.signature import Signature


class CollectorPluginMeta(OperateRecordModelBase):
    """
    采集插件源信息
    """

    PluginType = PluginType
    PLUGIN_TYPE_CHOICES = (
        (PluginType.EXPORTER, PluginType.EXPORTER),
        (PluginType.SCRIPT, PluginType.SCRIPT),
        (PluginType.JMX, PluginType.JMX),
        (PluginType.DATADOG, PluginType.DATADOG),
        (PluginType.PUSHGATEWAY, "BK-Pull"),
        (PluginType.BUILT_IN, "BK-Monitor"),
        (PluginType.LOG, PluginType.LOG),
        (PluginType.PROCESS, "Process"),
        (PluginType.SNMP_TRAP, PluginType.SNMP_TRAP),
        (PluginType.SNMP, PluginType.SNMP),
        (PluginType.K8S, PluginType.K8S),
    )

    VIRTUAL_PLUGIN_TYPE = [PluginType.LOG, PluginType.PROCESS, PluginType.SNMP_TRAP, PluginType.K8S]

    plugin_id = models.CharField("插件ID", max_length=64, primary_key=True)
    bk_biz_id = models.IntegerField("业务ID", default=0, blank=True, db_index=True)
    bk_supplier_id = models.IntegerField("开发商ID", default=0, blank=True)
    plugin_type = models.CharField("插件类型", max_length=32, choices=PLUGIN_TYPE_CHOICES, db_index=True)
    tag = models.CharField("插件标签", max_length=64, default="")
    label = models.CharField("二级标签", max_length=64, default="")
    is_internal = models.BooleanField("是否内置", default=False)

    def __str__(self):
        return f"{self.plugin_type}-{self.plugin_id}"

    @property
    def is_global(self):
        """
        是否为全局插件
        """
        return self.bk_biz_id == 0

    @property
    def edit_allowed(self):
        if self.is_internal:
            return False
        return True

    @property
    def delete_allowed(self):
        return not (self.is_internal or self.current_version.collecting_config_total)

    @property
    def export_allowed(self):
        if self.plugin_type == self.PluginType.BUILT_IN or not self.release_version:
            return False
        return True

    @cached_property
    def release_version(self) -> Optional["PluginVersionHistory"]:
        """
        最新的发布版本
        """
        return self.versions.filter(stage=PluginVersionHistory.Stage.RELEASE).last()

    @property
    def packaged_release_version(self) -> Optional["PluginVersionHistory"]:
        """
        最新的发布版本
        """
        version = self.versions.filter(stage=PluginVersionHistory.Stage.RELEASE, is_packaged=True).last()
        if not version:
            version = self.versions.filter(stage=PluginVersionHistory.Stage.RELEASE).last()
        return version

    @property
    def initial_version(self):
        """
        最初的发布版本
        """
        return self.versions.filter(stage=PluginVersionHistory.Stage.RELEASE).first()

    @cached_property
    def current_version(self):
        """
        获取当前版本
        ⚠️ 不要在 for 循环里调用，会引发 n+1 查询导致额外耗时
        """
        release_version = self.release_version
        if release_version:
            return release_version

        # 如果没有发布版本，获取最新草稿版本
        debug_version = self.versions.filter(~Q(stage=PluginVersionHistory.Stage.RELEASE)).last()
        if not debug_version:
            # 没有草稿版本，创建一个
            debug_version = self.generate_version(config_version=1, info_version=1)

        return debug_version

    @classmethod
    def fetch_id__current_version_id_map(cls, ids: List[str]) -> Dict[str, int]:
        version_infos: List[Dict[str, Union[int, str]]] = PluginVersionHistory.objects.filter(plugin_id__in=ids).values(
            "plugin_id", "id", "stage"
        )
        # 排序规则：Release > DEBUG/UNREGISTER

        def _version_comparator(_left: Dict[str, Union[int, str]], _right: Dict[str, Union[int, str]]) -> int:
            """stage 相同时 ID 优先，stage 不同时，stage=RELEASE 优先"""
            if _left["stage"] == _right["stage"]:
                return (1, -1)[_left["id"] < _right["id"]]
            return (1, -1)[_right["stage"] == PluginVersionHistory.Stage.RELEASE]

        version_infos_gby_plugin_id: Dict[str, List[Dict[str, Union[int, str]]]] = defaultdict(list)
        for version_info in version_infos:
            version_infos_gby_plugin_id[version_info["plugin_id"]].append(version_info)

        id__current_version_id_map: Dict[str, int] = {}
        for plugin_id, version_infos in version_infos_gby_plugin_id.items():
            ordered_version_infos: List[Dict[str, Union[int, str]]] = sorted(
                version_infos, key=cmp_to_key(_version_comparator)
            )
            # 取出最新版本
            id__current_version_id_map[plugin_id] = ordered_version_infos[-1]["id"]

        return id__current_version_id_map

    def get_version(self, config_version, info_version):
        """
        获取特定版本
        """
        return self.versions.get(config_version=config_version, info_version=info_version)

    def get_release_ver_by_config_ver(self, config_version):
        version = self.versions.filter(config_version=config_version, stage=PluginVersionHistory.Stage.RELEASE).last()
        return version

    def rollback_version_status(self, config_version):
        """
        获取特定版本
        """
        version = self.versions.filter(
            config_version=config_version, stage=PluginVersionHistory.Stage.RELEASE, is_packaged=True
        )
        if not version:
            self.versions.filter(config_version=config_version, stage=PluginVersionHistory.Stage.RELEASE).update(
                stage=PluginVersionHistory.Stage.UNREGISTER
            )

    def get_debug_version(self, config_version):
        version = self.versions.filter(
            config_version=config_version,
            stage__in=[PluginVersionHistory.Stage.DEBUG, PluginVersionHistory.Stage.RELEASE],
            is_packaged=True,
        ).last()
        if not version:
            version = self.versions.filter(
                config_version=config_version, stage=PluginVersionHistory.Stage.RELEASE
            ).last()
        return version

    def generate_version(self, config_version, info_version, config=None, info=None):
        """
        生成特定版本
        """
        try:
            version = self.get_version(config_version, info_version)
            if config:
                version.config = config
            if info:
                version.info = info
            version.save()
        except PluginVersionHistory.DoesNotExist:
            if config is None:
                config = CollectorPluginConfig.objects.create()
            if info is None:
                info: CollectorPluginInfo = CollectorPluginInfo.objects.create()
            version = self.versions.create(
                config_version=config_version,
                info_version=info_version,
                config=config,
                info=info,
            )
        return version

    def get_plugin_detail(self):
        current_version = self.current_version
        logo_base64 = current_version.info.logo_content
        plugin_detail = {
            "plugin_id": self.plugin_id,
            "plugin_display_name": current_version.info.plugin_display_name,
            "plugin_type": self.plugin_type,
            "tag": self.tag,
            "label": self.label,
            "status": "normal" if current_version.is_release else "draft",
            "logo": logo_base64,
            "collector_json": current_version.config.collector_json,
            "config_json": current_version.config.config_json,
            "enable_field_blacklist": current_version.info.enable_field_blacklist,
            "metric_json": current_version.info.metric_json,
            "description_md": current_version.info.description_md,
            "config_version": current_version.config_version,
            "info_version": current_version.info_version,
            "stage": current_version.stage,
            "bk_biz_id": self.bk_biz_id,
            "signature": Signature(current_version.signature).dumps2yaml() if current_version.signature else "",
            "is_support_remote": current_version.config.is_support_remote,
            "is_official": current_version.is_official,
            "is_safety": current_version.is_safety,
            "create_user": self.create_user,
            "update_user": current_version.update_user,
            "os_type_list": current_version.os_type_list,
            "create_time": current_version.create_time,
            "update_time": current_version.update_time,
            "related_conf_count": current_version.get_related_config_count(),
            "edit_allowed": self.edit_allowed if not current_version.is_official else False,
            "is_split_measurement": self.is_split_measurement,
        }
        if self.plugin_type == PluginType.SNMP_TRAP:
            params = current_version.deployment_versions.last().params
            plugin_detail["config_json"] = self.get_config_json(params["snmp_trap"])
        return plugin_detail

    def convert_metric_to_field_dict(self, metrics):
        """
        将 metric 转换为 metric_json 所需要的字典格式
        :param metrics: TimeSeriesMetric 的指标格式：形如{"field_name": "", "metric_display_name": "",
                        "unit": "", "type": "", "tag_list": []}
        :return:result: [field]
        """
        result = []
        # tag的缓存，避免重复，初始值为保留维度字段
        tag_cache = set(self.reserved_dimension_list)
        for metric in metrics:
            result.append(
                {
                    "description": metric.get("description", ""),
                    "type": "double",  # 因为默认自动发现上来的类型是float，但是metric_json不支持float，所以写死为double
                    "monitor_type": "metric",
                    "unit": metric.get("unit", ""),
                    "name": metric.get("field_name", ""),
                    "is_diff_metric": False,
                    "is_active": True,
                    "source_name": "",
                    "dimensions": [],
                    "order": 0,
                    "is_disabled": metric.get("is_disabled", False),
                }
            )
            for tag in metric.get("tag_list", []):
                if tag.get("field_name", "") in tag_cache:
                    continue
                result.append(
                    {
                        "description": tag.get("description", ""),
                        "type": tag.get("type", "") or "string",
                        "monitor_type": "dimension",
                        "unit": tag.get("unit", ""),
                        "name": tag.get("field_name", ""),
                        "is_diff_metric": False,
                        "is_active": True,
                        "source_name": "",
                        "dimensions": [],
                        "order": 0,
                        "is_disabled": tag.get("is_disabled", False),
                    }
                )
                tag_cache.add(tag.get("field_name", ""))
        return result

    def filter_metric_by_table_rule(self, group_list):
        """
        通过 table rule 对指标进行自动匹配分组
        :param group_list: QueryTimeSeriesGroup 返回数据
        :return: match_result: 命中规则的指标，包括其 table 信息，格式如：{table_name: [metric, metric]}
                not_match_result: 未能命中规则的指标，格式如：[metric]
                map_of_metric_and_tag: 指标和维度的映射关系
        """
        # metric_json 中有的指标集合
        metric_from_plugin_set = self.current_version.info.metric_set
        # 表名和分组规则映射
        table_rule_map = self.current_version.info.table_rule_map
        # 将发现的新的指标分配到对应的规则在的表中：TSMetric -> table-field
        # 命中规则的指标
        match_result = {}
        # 未能命中规则的指标
        not_match_result = []
        map_of_metric_and_tag = {}
        for group in group_list:
            metric_info_list = group["metric_info_list"]
            # 需要考虑未上报数据的情况
            if not metric_info_list:
                continue
            metric = metric_info_list[0]
            map_of_metric_and_tag[metric["field_name"]] = metric["tag_list"]
            # 如果该指标已存在 metric_json，则略过
            if metric["field_name"] in metric_from_plugin_set:
                continue
            for table_name, rule_list in table_rule_map.items():
                for rule in rule_list:
                    if not re.search(rule, metric["field_name"]):
                        continue
                    # 如果有命中，则立刻停止对该 metric 的规则匹配
                    match_result.setdefault(table_name, []).append(metric)
                    break
                else:
                    # 如果没有被break，则继续下一个循环
                    continue
                break
            else:
                # 添加未能命中rule的指标
                not_match_result.append(metric)
        return match_result, not_match_result, map_of_metric_and_tag

    def update_metric_json_from_ts_group(self, group_list):
        """
        从 TimeSeriesGroup 中更新 metric_json 数据
        :param group_list: QueryTimeSeriesGroup 返回数据
        :return:
        """
        match_rule_metric_under_table, not_match_rule_metric, map_of_metric_and_tag = self.filter_metric_by_table_rule(
            group_list
        )
        # 是否存在默认组
        has_default_group_flag = False
        # 将指标存回 metric_json
        for table_fields in self.current_version.info.metric_json:
            # 判断是不是默认分组
            if table_fields["table_name"] == "group_default" and table_fields["table_desc"] == "默认分组":
                has_default_group_flag = True
                # 将TSMetric 的指标格式转换为 field 的字典格式
                table_fields["fields"].extend(self.convert_metric_to_field_dict(not_match_rule_metric))
            if table_fields["table_name"] not in match_rule_metric_under_table:
                continue
            match_rule_metrics = match_rule_metric_under_table[table_fields["table_name"]]
            # 将TSMetric 的指标格式转换为 field 的字典格式
            table_fields["fields"].extend(self.convert_metric_to_field_dict(match_rule_metrics))
        # 如果没有默认分组，则初始化一个
        if not has_default_group_flag:
            self.current_version.info.metric_json.append(
                {
                    "table_name": "group_default",
                    "table_desc": "默认分组",
                    "rule_list": [],
                    "fields": self.convert_metric_to_field_dict(not_match_rule_metric),
                }
            )

        for table_fields in self.current_version.info.metric_json:
            # table 下的指标
            metric_under_table = set()
            # table 下的集合
            dimension_under_table = set()
            # tag name 的集合
            tag_list_set = set()
            # tag 数据抽出来
            tag_data_list = []
            for field in table_fields["fields"]:
                if field["monitor_type"] == "metric":
                    metric_under_table.add(field["name"])
                    field_tag_list = map_of_metric_and_tag.get(field["name"], [])
                    # 自动发现模式下，更新 metric_json 中指标的 tag_list 值
                    field["tag_list"] = field_tag_list
                    for tag in field_tag_list:
                        tag_data_list.append(tag)
                        tag_list_set.add(tag["field_name"])
                else:
                    dimension_under_table.add(field["name"])
            # 如果未有新增的 tag，则跳过
            if not (tag_list_set - dimension_under_table - set(self.reserved_dimension_list)):
                continue
            additional_tag = tag_list_set - dimension_under_table - set(self.reserved_dimension_list)
            # 避免维度重复，加一层过滤
            add_tag_cache = []
            for tag_data in tag_data_list:
                if tag_data["field_name"] in additional_tag:
                    if tag_data["field_name"] in add_tag_cache:
                        continue
                    add_tag_cache.append(tag_data["field_name"])
                    table_fields["fields"].append(
                        {
                            "description": tag_data.get("description", ""),
                            "type": tag_data.get("type", "") or "string",
                            "monitor_type": "dimension",
                            "unit": tag_data.get("unit", ""),
                            "name": tag_data.get("field_name", ""),
                            "is_diff_metric": False,
                            "is_active": True,
                            "source_name": "",
                            "dimensions": [],
                            "order": 0,
                            "is_disabled": tag_data.get("is_disabled", False),
                        }
                    )
        self.current_version.info.save()

    def should_refresh_metric_json(self, timeout=5 * 60):
        """
        判断是否需要刷新当前metric json，默认刷新时间是5分钟，以避免每次打开页面查看都需要同步一次数据。
        :param timeout: 过期时间，单位为秒
        :return: True 表示需要刷新，False 表示不需要刷新
        """
        update_time = arrow.get(self.current_version.info.update_time)
        current_time = arrow.now(tz=update_time.tzinfo)
        time_delta = current_time.timestamp - update_time.timestamp
        if time_delta > timeout:
            return True
        return False

    def refresh_metric_json(self):
        """
        从TimeSeriesMetric刷新metric_json
        """
        # 如果未开启黑名单或没有超过刷新周期（默认五分钟），直接返回
        if not self.current_version.info.enable_field_blacklist or not self.should_refresh_metric_json(timeout=5 * 60):
            return
        operator = get_global_user()
        plugin_data_info = PluginDataAccessor(self.current_version, operator)
        # 查询TSGroup
        group_list = api.metadata.query_time_series_group(
            time_series_group_name=plugin_data_info.db_name, label=plugin_data_info.label
        )
        # 仅对有数据做处理
        if len(group_list) == 0:
            return
        self.reserved_dimension_list = [
            field_name for field_name, _ in PLUGIN_REVERSED_DIMENSION + plugin_data_info.dms_field
        ]
        self.update_metric_json_from_ts_group(group_list)

    def get_config_json(self, params):
        trap_config = [
            {
                "default": params.get("server_port"),
                "mode": "collector",
                "type": "text",
                "key": "server_port",
                "name": _("Trap服务端口"),
                "description": _("Trap服务端口"),
            },
            {
                "default": params.get("listen_ip"),
                "mode": "collector",
                "type": "text",
                "key": "listen_ip",
                "name": _("绑定地址"),
                "description": _("绑定地址"),
            },
            {
                "default": params.get("yaml"),
                "mode": "collector",
                "type": "file",
                "key": "yaml",
                "name": _("Yaml配置文件"),
                "description": _("Yaml配置文件"),
            },
            {
                "default": params.get("community"),
                "mode": "collector",
                "type": "text",
                "key": "community",
                "name": _("团体名"),
                "description": _("团体名"),
            },
        ]
        #
        if params.get("version") == "v3":
            auth_info = {
                k: [
                    [
                        {
                            "default": i["security_name"],
                            "mode": "collector",
                            "type": "text",
                            "key": "security_name",
                            "name": _("安全名"),
                            "description": _("安全名"),
                        },
                        {
                            "default": i["context_name"],
                            "mode": "collector",
                            "type": "text",
                            "key": "context_name",
                            "name": _("上下文名称"),
                            "description": _("上下文名称"),
                        },
                        {
                            "default": i["security_level"],
                            "election": ["authPriv", "authNoPriv", "noAuthNoPriv"],
                            "mode": "collector",
                            "type": "list",
                            "key": "security_level",
                            "name": _("安全级别"),
                            "description": _("安全级别"),
                        },
                        {
                            "default": i["authentication_protocol"],
                            "election": ["MD5", "SHA", "DES", "AES"],
                            "mode": "collector",
                            "type": "list",
                            "key": "authentication_protocol",
                            "name": _("验证协议"),
                            "description": _("验证协议"),
                            "auth_priv": {
                                "noAuthNoPriv": {"need": False},
                                "authNoPriv": {
                                    "need": True,
                                    "election": ["MD5", "SHA", "SHA224", "SHA256", "SHA384", "SHA512"],
                                },
                                "authPriv": {
                                    "need": True,
                                    "election": ["MD5", "SHA", "SHA224", "SHA256", "SHA384", "SHA512"],
                                },
                            },
                        },
                        {
                            "default": i["authentication_passphrase"],
                            "mode": "collector",
                            "type": "text",
                            "key": "authentication_passphrase",
                            "name": _("验证口令"),
                            "description": _("验证口令"),
                            "auth_priv": {
                                "noAuthNoPriv": {"need": False},
                                "authNoPriv": {"need": True},
                                "authPriv": {"need": True},
                            },
                        },
                        {
                            "default": i["privacy_protocol"],
                            "election": ["DES", "AES"],
                            "mode": "collector",
                            "type": "list",
                            "key": "privacy_protocol",
                            "name": _("隐私协议"),
                            "description": _("隐私协议"),
                            "auth_priv": {
                                "NoAuthNoPriv": {"need": False},
                                "authNoPriv": {"need": False},
                                "authPriv": {"need": True, "election": ["DES", "AES", "AES192", "AES256", "AES256c"]},
                            },
                        },
                        {
                            "default": i["privacy_passphrase"],
                            "mode": "collector",
                            "type": "text",
                            "key": "privacy_passphrase",
                            "name": _("私钥"),
                            "description": _("私钥"),
                            "auth_priv": {
                                "noAuthNoPriv": {"need": False},
                                "authNoPriv": {"need": False},
                                "authPriv": {"need": True},
                            },
                        },
                        {
                            "default": i["authoritative_engineID"],
                            "mode": "collector",
                            "type": "text",
                            "key": "authoritative_engineID",
                            "name": _("认证设备"),
                            "description": _("认证设备"),
                        },
                    ]
                    for i in v
                ]
                for k, v in {
                    "auth_json": params.get("auth_info", ""),
                    "template_auth_json": DEFAULT_TRAP_V3_CONFIG["auth_info"],
                }.items()
            }
            trap_config.extend([auth_info])
        trap_config.append(
            {
                "default": params.get("aggregate"),
                "mode": "collector",
                "type": "boolean",
                "key": "aggregate",
                "name": _("是否汇聚"),
                "description": _("是否汇聚"),
            }
        )
        return trap_config

    @property
    def is_split_measurement(self):
        db_name = f"{self.plugin_type}_{self.plugin_id}".lower()
        group_result = api.metadata.query_time_series_group(bk_biz_id=0, time_series_group_name=db_name)
        return bool(group_result)


class CollectorPluginConfig(OperateRecordModelBase):
    """
    采集器插件功能信息
    """

    config_json = JsonField("参数配置", default=None)
    collector_json = JsonField("采集器配置", default=None)
    is_support_remote = models.BooleanField("是否支持远程采集", default=False)

    def __str__(self):
        return f"{self.__class__.__name__}<{self.id}>"

    def config2dict(self, config_params=None):
        if config_params is None:
            config_params = {}

        now_collector_json = copy.deepcopy(self.collector_json)
        if now_collector_json:
            now_collector_json.pop("diff_fields", None)

        return {
            "config_json": config_params.get("config_json", self.config_json),
            "collector_json": config_params.get("collector_json", now_collector_json),
            "is_support_remote": config_params.get("is_support_remote", self.is_support_remote),
        }

    @property
    def diff_fields(self):
        self.collector_json = self.collector_json or {}
        return self.collector_json.get("diff_fields") or ""

    @diff_fields.setter
    def diff_fields(self, value):
        if value:
            self.collector_json = self.collector_json or {}
            self.collector_json.update({"diff_fields": value})
        else:
            if self.collector_json:
                self.collector_json.pop("diff_fields", "")

    @property
    def file_config(self):
        _file_config = dict()
        for key in self.collector_json:
            if key in OperatorSystem.objects.os_type_list():
                _file_config.setdefault(key, self.collector_json[key])

        return _file_config

    @property
    def debug_flag(self):
        return {"debugged": True}


class CollectorPluginInfo(OperateRecordModelBase):
    """
    采集器插件信息
    发布成功后，新纪录的info_version+=1
    草稿下，info_version=0
    """

    plugin_display_name = models.CharField("插件别名", max_length=64, default="")
    metric_json = JsonField("指标配置", default=[])
    description_md = models.TextField("插件描述，markdown文本", default="")
    logo = models.ImageField("logo文件", null=True, storage=get_default_image_storage())
    enable_field_blacklist = models.BooleanField("是否开启黑名单", default=False)

    def __str__(self):
        return f"{self.plugin_display_name}"

    def info2dict(self, info_params=None):
        if info_params is None:
            info_params = {}
            logo_str = self.logo_content
            description_md = self.description_md
        else:
            logo_str = info_params.get("logo", "").split(",")[-1]
            description_md = info_params.get("description_md", "")

        result = {
            "plugin_display_name": info_params.get("plugin_display_name", self.plugin_display_name),
            "description_md": description_md,
            "logo": logo_str,
            "metric_json": info_params.get("metric_json") or self.metric_json,
            "enable_field_blacklist": info_params.get("enable_field_blacklist") or self.enable_field_blacklist,
        }

        return result

    @property
    def logo_content(self):
        """
        logo content with base64 encoding
        :return:
        """
        if not self.logo:
            return ""
        try:
            logo_str = b"".join(self.logo.chunks())
        except Exception:
            return ""
        return base64.b64encode(logo_str)

    @property
    def metric_set(self):
        """
        获取 metric_json 下的所有指标集合
        :return:
        """
        result = set()
        for table_fields in self.metric_json:
            for field in table_fields["fields"]:
                result.add(field["name"])
        return result

    @property
    def table_rule_map(self):
        result = OrderedDict()
        for table_fields in self.metric_json:
            result[table_fields["table_name"]] = table_fields.get("rule_list", [])
        return result


class PluginVersionHistory(OperateRecordModelBase):
    """
    采集插件版本历史
    """

    class Stage(object):
        """
        插件状态
        """

        UNREGISTER = "unregister"
        DEBUG = "debug"
        RELEASE = "release"

    STAGE_CHOICES = (
        (Stage.UNREGISTER, _lazy("未注册版本")),
        (Stage.DEBUG, _lazy("调试版本")),
        (Stage.RELEASE, _lazy("发布版本")),
    )

    plugin = models.ForeignKey(
        CollectorPluginMeta, verbose_name="插件元信息", related_name="versions", on_delete=models.CASCADE
    )
    stage = models.CharField("版本阶段", choices=STAGE_CHOICES, default=Stage.UNREGISTER, max_length=30)
    config = models.ForeignKey(
        CollectorPluginConfig, verbose_name="插件功能配置", related_name="version", on_delete=models.CASCADE
    )
    info = models.ForeignKey(
        CollectorPluginInfo, verbose_name="插件信息配置", related_name="version", on_delete=models.CASCADE
    )
    config_version = models.IntegerField("插件版本", default=1)
    info_version = models.IntegerField("插件信息版本", default=1)
    signature = YamlField("版本签名", default="")
    version_log = models.CharField("版本修改日志", max_length=100, default="")
    is_packaged = models.BooleanField("是否已上传到节点管理", default=False)

    @property
    def os_type_list(self):
        """
        获取该版本支持的操作系统类型
        :return:
        """
        if self.plugin.plugin_type in [
            CollectorPluginMeta.PluginType.JMX,
            CollectorPluginMeta.PluginType.SNMP,
            CollectorPluginMeta.PluginType.BUILT_IN,
            CollectorPluginMeta.PluginType.PUSHGATEWAY,
        ]:
            return ["linux", "windows", "linux_aarch64"]
        else:
            return list(self.config.file_config.keys())

    @property
    def is_release(self):
        if self.stage == "release":
            return True
        return False

    @property
    def version_info(self):
        """
        获取版本号元组，例如 (2, 3)
        major - config_version
        minor - info_version
        """
        return self.config_version, self.info_version

    @property
    def version(self):
        """
        获取版本号字符串，例如 "2.3"
        major - config_version
        minor - info_version
        """
        return ".".join([str(num) for num in self.version_info])

    @property
    def is_official(self):
        # 官方插件ID都是以bkplugin_作为前缀
        return self.plugin.plugin_id.startswith("bkplugin_")

    @property
    def is_safety(self):
        return Signature(self.signature).verificate("safety", self)

    @property
    def collecting_config_count(self):
        """该版本关联的采集配置数量"""
        return self.deployment_versions.values("config_meta_id").distinct().count()

    @property
    def collecting_config_total(self):
        """该版本插件全部版本关联的采集配置数量"""
        return self.plugin.collect_configs.all().count()

    @property
    def collecting_config_detail(self):
        collect_config = list(self.plugin.collect_configs.values())
        return collect_config

    def get_related_config_count(self, bk_biz_id=None):
        if bk_biz_id:
            return self.plugin.collect_configs.filter(bk_biz_id=bk_biz_id).count()
        else:
            return self.plugin.collect_configs.all().count()

    def update_diff_fields(self):
        diff_fields_value = PluginVersionHistory.gen_diff_fields(self.info.metric_json)

        self.config.diff_fields = diff_fields_value

    def save(self, *args, **kwargs):
        self.update_diff_fields()
        self.config.save()

        if self.signature:
            signature = Signature(self.signature)
            new_signature = dict()
            for protocol, ret in signature.iter_verificate(self):
                if ret:
                    new_signature[protocol] = self.signature[protocol]

            self.signature = new_signature or ""
        return super(PluginVersionHistory, self).save(*args, **kwargs)

    @classmethod
    def gen_diff_fields(cls, metric_json):
        diff_fields = []
        for table in metric_json:
            for field in table.get("fields", []):
                if field.get("is_diff_metric", False):
                    diff_fields.append(field["name"])

        if diff_fields:
            return ",".join(sorted(diff_fields))
        else:
            return ""

    @classmethod
    def get_result_table_id(cls, plugin: CollectorPluginMeta, table_name: str):
        """
        根据插件生成结果表名
        """
        from monitor_web.models import CustomEventGroup

        if plugin.plugin_type == PluginType.LOG or plugin.plugin_type == PluginType.SNMP_TRAP:
            name = "{}_{}".format(plugin.plugin_type, plugin.plugin_id)
            table_id = CustomEventGroup.objects.get(name=name).table_id
            return table_id
        else:
            db_name = ("{}_{}".format(plugin.plugin_type, plugin.plugin_id)).lower()
            if plugin.plugin_type == PluginType.PROCESS:
                db_name = "process"
            return "{}.{}".format(db_name, table_name)

    def get_plugin_version_detail(self):
        logo_base64 = self.info.logo_content
        plugin_detail = {
            "plugin_id": self.plugin_id,
            "plugin_display_name": self.info.plugin_display_name,
            "plugin_type": self.plugin.plugin_type,
            "tag": self.plugin.tag,
            "logo": logo_base64,
            "collector_json": self.config.collector_json,
            "config_json": self.config.config_json,
            "metric_json": self.info.metric_json,
            "description_md": self.info.description_md,
            "config_version": self.config_version,
            "info_version": self.info_version,
            "stage": self.stage,
            "bk_biz_id": self.plugin.bk_biz_id,
            "signature": Signature(self.signature).dumps2yaml() if self.signature else "",
            "is_support_remote": self.config.is_support_remote,
            "is_official": self.is_official,
            "is_safety": self.is_safety,
            "create_user": self.create_user,
            "update_user": self.update_user,
            "os_type_list": self.os_type_list,
        }

        # 生成结果表
        for table in plugin_detail["metric_json"]:
            table["table_id"] = self.get_result_table_id(self.plugin, table["table_name"])

        return plugin_detail

    class Meta:
        ordering = ["config_version", "info_version", "create_time", "update_time"]
        unique_together = ["plugin", "config_version", "info_version"]

    def __str__(self):
        return "{}-{}".format(self.plugin_id, self.version)


class OperatorSystemManager(models.Manager):
    @lru_cache(maxsize=32)
    def os_type_list(self):
        supported_os = self.all().values("os_type")
        return [_o["os_type"] for _o in supported_os]

    def get_queryset(self):
        return super(OperatorSystemManager, self).get_queryset().filter(os_type__in=settings.OS_GLOBAL_SWITCH)


class OperatorSystem(models.Model):
    """
    操作系统
    windows,os_type_id=2
    linux,os_type_id=1
    aix(is_enable=False),os_type_id=3
    """

    objects = OperatorSystemManager()

    os_type_id = models.CharField("操作系统类型ID", max_length=10)
    os_type = models.CharField("操作系统类型", max_length=16, unique=True)
