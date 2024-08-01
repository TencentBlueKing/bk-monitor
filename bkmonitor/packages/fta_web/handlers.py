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
import collections
import os
import traceback

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils.translation import ugettext as _
from fta_web.event_plugin.handler import PackageHandler
from fta_web.event_plugin.resources import (
    CreateEventPluginInstanceResource,
    UpdateEventPluginInstanceResource,
)

from bkmonitor.documents.tasks import rollover_indices
from bkmonitor.models import EventPluginInstance, EventPluginV2
from constants.action import GLOBAL_BIZ_ID


def register_builtin_plugins(sender, **kwargs):
    import json
    import os

    from django.conf import settings

    from bkmonitor.models.fta import ActionPlugin

    print("start to  register_builtin_plugin ")
    initial_file = os.path.join(settings.PROJECT_ROOT, "support-files/fta/action_plugin_initial.json")

    with open(initial_file, "r", encoding="utf-8") as f:
        plugins = json.loads(f.read())
        for plugin in plugins:
            instance, created = ActionPlugin.origin_objects.update_or_create(
                id=plugin.pop("id"), is_builtin=True, defaults=plugin
            )
            print("{} plugin: [{}]".format("register" if created else "update", instance.name))


def register_builtin_action_configs(sender, **kwargs):
    import json
    import os

    from django.conf import settings

    from bkmonitor.models.fta import ActionConfig

    print("start to register_builtin_action_configs")
    initial_file = os.path.join(settings.PROJECT_ROOT, "support-files/fta/action_config_initial.json")

    with open(initial_file, "r", encoding="utf-8") as f:
        action_configs = json.loads(f.read())
        for action_config in action_configs:
            instance, created = ActionConfig.origin_objects.update_or_create(
                id=action_config.pop("id"), defaults=action_config
            )
            print("{} action_config: [{}]".format("register" if created else "update", instance.name))


def migrate_actions(sender, **kwargs):
    """
    迁移监控的告警以及webhook至自愈套餐配置
    """
    import json

    from bkmonitor.action.serializers import ActionConfigDetailSlz, UserGroupDetailSlz
    from bkmonitor.models import (
        Action,
        ActionConfig,
        ActionNoticeMapping,
        GlobalConfig,
        ItemModel,
        NoticeGroup,
        NoticeTemplate,
        StrategyActionConfigRelation,
        StrategyModel,
    )
    from constants.action import ActionSignal

    if GlobalConfig.objects.filter(key="MIGRATE_ACTIONS_OPERATE", value="1").exists():
        print("New action config is ready for FTA ^_^")
        return

    strategies = {item["id"]: item["name"] for item in StrategyModel.objects.all().values("name", "id")}

    def add_new_user_group(old_group: NoticeGroup):
        new_group = {
            "name": old_group.name,
            "desc": old_group.message,
            "bk_biz_id": old_group.bk_biz_id,
            "source": old_group.source,
            "duty_arranges": [
                {
                    "users": [
                        {"type": receiver.split("#")[0], "id": receiver.split("#")[-1]}
                        for receiver in old_group.notice_receiver
                    ]
                }
            ],
        }
        new_user_group_slz = UserGroupDetailSlz(data=new_group)
        new_user_group_slz.is_valid(raise_exception=True)
        new_user_group_slz.save()
        return new_user_group_slz.instance

    def add_notice_action(notice_way, old_action_config, wxwork_group=None):
        notice_actions = []
        try:
            notice_template = NoticeTemplate.objects.get(action_id=old_action_config.id)
        except NoticeTemplate.DoesNotExist:
            notice_template = None

        notice_ways = [{"level": level, "type": notice_type} for level, notice_type in notice_way.items()]
        wxwork_group = wxwork_group or {}
        for level_notice_way in notice_ways:
            if level_notice_way["level"] in wxwork_group:
                level_notice_way["type"].append("wxwork-bot")
                level_notice_way["chatid"] = wxwork_group[level_notice_way["level"]]

            level_notice_way["type"] = ",".join(level_notice_way["type"])

        alarm_interval = old_action_config.config["alarm_interval"]
        notice_config_tmpl = {
            "converge_config": {
                "timedelta": 5 * 60,
                "count": 1,
                "condition": [
                    {"dimension": "bk_biz_id", "value": ["self"]},
                    {"dimension": "strategy_id", "value": ["self"]},
                ],
                "converge_func": "collect",
            },
            "execute_config": {
                "template_detail": {
                    "notify_config": {
                        "notify_type": notice_ways,
                        "message_tmpl": "",
                    },
                    "notify_time_range": "{alarm_start_time}--{alarm_end_time}".format(**old_action_config.config),
                    "notify_interval": alarm_interval * 60,
                    "interval_notify_mode": "standard",
                },
                "timeout": 60,
                "failed_retry": {"is_enabled": False, "max_retry_times": 0, "retry_interval": 0},
            },
            "name": _("%s{signal_name}通知") % strategies.get(old_action_config.strategy_id, "自愈迁移"),
            "desc": _("迁移的通知套餐"),
            "is_enabled": True,
            "plugin_id": 1,
            "bk_biz_id": old_action_config.bk_biz_id,
        }
        anomaly_message_tmpl = "" if notice_template is None else notice_template.anomaly_template
        recovery_message_tmpl = "" if notice_template is None else notice_template.recovery_template

        notice_actions.append(add_notice_config(notice_config_tmpl, anomaly_message_tmpl))

        if old_action_config.config["send_recovery_alarm"]:
            # 创建恢复信号告警
            notice_actions.append(add_notice_config(notice_config_tmpl, recovery_message_tmpl, ActionSignal.RECOVERED))

        no_data_tmpl = ""
        for item in ItemModel.objects.filter(strategy_id=old_action.strategy_id):
            if not item.no_data_config.get("is_enabled"):
                continue
            # 开启了无数据告警，则创建无数据告警事件
            notice_actions.append(add_notice_config(notice_config_tmpl, no_data_tmpl, ActionSignal.NO_DATA))

        return notice_actions

    def add_notice_config(notice_config_tmpl, message_tmpl, action_signal=ActionSignal.ABNORMAL):
        notice_tmpl = json.loads(json.dumps(notice_config_tmpl))
        notice_tmpl["execute_config"]["template_detail"]["notify_config"]["message_tmpl"] = message_tmpl
        notice_tmpl["name"] = notice_tmpl["name"].format(signal_name=ActionSignal.ACTION_SIGNAL_DICT[action_signal])

        ac_slz = ActionConfigDetailSlz(data=notice_tmpl)
        ac_slz.is_valid(raise_exception=True)
        ac_slz.save()
        return action_signal, ac_slz.instance

    def add_webhook_action(url, old_action_config: Action) -> (str, ActionConfig):
        webhook_action_config = {
            "name": _("HTTP回调[%s]") % old_action_config.id,
            "plugin_id": 2,
            "bk_biz_id": old_action_config.bk_biz_id,
            "desc": "",
            "converge_config": {
                "timedelta": 300,
                "count": 1,
                "condition": [{"dimension": "bk_host_id", "value": ["self"]}],
                "converge_func": "skip_when_proceed",
            },
            "execute_config": {
                "template_detail": {
                    "method": "POST",
                    "url": url,
                    "headers": [],
                    "authorize": {"auth_type": "none", "auth_config": {}},
                    "body": {
                        "data_type": "raw",
                        "params": [],
                        "content": "",
                        "content_type": "json",
                    },
                    "query_params": [],
                },
                "notify_config": {
                    "notify_type": [
                        {"level": 1, "type": "mail"},
                        {"level": 2, "type": "mail"},
                        {"level": 3, "type": "mail"},
                    ],
                    "message_tmpl": "",
                },
                "failed_retry": {"is_enabled": True, "max_retry_times": 2, "retry_interval": 60},
                "timeout": 600,
            },
        }

        ac_slz = ActionConfigDetailSlz(data=webhook_action_config)
        ac_slz.is_valid()
        ac_slz.save()
        return ActionSignal.ABNORMAL, ac_slz.instance

    strategy_action_relations = []
    for old_notice_group in NoticeGroup.objects.all():
        new_user_group = add_new_user_group(old_notice_group)
        action_ids = ActionNoticeMapping.objects.filter(notice_group_id=old_notice_group.id).values_list(
            "action_id", flat=True
        )

        if not action_ids:
            continue
        old_actions = Action.objects.filter(id__in=action_ids)

        for old_action in old_actions:
            new_actions = []
            old_action.bk_biz_id = old_notice_group.bk_biz_id
            if old_notice_group.webhook_url:
                new_actions.append(add_webhook_action(old_notice_group.webhook_url, old_action))
            new_actions.extend(
                add_notice_action(old_notice_group.notice_way, old_action, old_notice_group.wxwork_group)
            )
            strategy_id = old_action.strategy_id
            for (signal, new_action) in new_actions:
                strategy_action_relations.append(
                    StrategyActionConfigRelation(
                        config_id=new_action.id, user_groups=[new_user_group.id], strategy_id=strategy_id, signal=signal
                    )
                )

    StrategyActionConfigRelation.objects.bulk_create(strategy_action_relations)
    GlobalConfig.objects.update_or_create(key="MIGRATE_ACTIONS_OPERATE", defaults={"value": 1})


def rollover_es_indices(sender, **kwargs):
    rollover_indices()


def register_global_event_plugin(sender, **kwargs):
    """
    注册内置的告警源插件
    :param sender:
    :param kwargs:
    :return:
    """
    builtin_params = [
        {
            "field": "begin_time",
            "name": _("开始时间"),
            "value": "{{begin_time}}",
            "is_required": True,
            "is_hidden": True,
            "default_value": "{{begin_time}}",
        },
        {
            "field": "end_time",
            "name": _("结束时间"),
            "value": "{{end_time}}",
            "is_required": True,
            "is_hidden": True,
            "default_value": "{{end_time}}",
        },
    ]
    register_event_plugin(builtin_params)


def migrate_event_plugin():
    """
    告警源事件注册
    """

    from fta_web.models.old_fta import AlarmApplication, AlarmType
    from monitor_web.strategies.metric_list_cache import BkFtaAlertCacheManager

    plugin_mapping = {
        "ZABBIX": "zabbix",
        "REST-API": "rest_api",
        "CUSTOM": "rest_pull",
    }
    all_alarm_types = collections.defaultdict(list)
    for alarm_type in AlarmType.objects.filter(source_type__in=plugin_mapping.keys()).using("fta"):
        if alarm_type.pattern == "api_default":
            continue
        all_alarm_types[plugin_mapping[alarm_type.source_type]].append(
            {
                "name": alarm_type.description,
                "rules": [
                    {
                        "key": "alarm_type",
                        "value": [alarm_type.pattern],
                        "method": "eq" if alarm_type.match_mode == 0 else "reg",
                        "condition": "",
                    }
                ],
            }
        )

    try:
        rest_pull_source = AlarmApplication.objects.using("fta").get(source_type="CUSTOM")
        pull_config_params = [
            {
                "field": "url",
                "value": "",
                "name": _("请求url"),
                "is_required": True,
                "default_value": f"{rest_pull_source.app_url}",
            },
            {
                "field": "method",
                "value": "",
                "name": _("请求方法"),
                "is_required": True,
                "default_value": f"{rest_pull_source.app_method.upper()}",
            },
            {
                "field": "begin_time",
                "name": _("开始时间"),
                "value": "{{begin_time}}",
                "is_required": True,
                "is_hidden": True,
                "default_value": "{{begin_time}}",
            },
            {
                "field": "end_time",
                "name": _("结束时间"),
                "value": "{{end_time}}",
                "is_required": True,
                "is_hidden": True,
                "default_value": "{{end_time}}",
            },
        ]
    except AlarmApplication.DoesNotExist:
        pull_config_params = []

    need_install_plugins = [
        plugin_mapping[source_type]
        for source_type in list(
            AlarmApplication.objects.using("fta").filter(is_enabled=True).values_list("source_type", flat=True)
        )
        if source_type in plugin_mapping
    ]

    # step 1 注册插件
    plugins = register_event_plugin(pull_config_params, all_alarm_types)

    # step 2 安装全局插件
    for plugin_id in need_install_plugins:
        install_global_event_plugin(plugins[plugin_id])

    # step 3最后一步，同步自愈指标
    try:
        BkFtaAlertCacheManager(0).run()
    except Exception as e:
        print("[event plugin initial] BkFtaAlertCacheManager error:{}".format(e))


def register_event_plugin(config_params=None, all_alarm_types=None):
    from fta_web.event_plugin.resources import CreateEventPluginResource

    plugins = {}
    document_root = os.path.join(settings.PROJECT_ROOT, "support-files/fta/event_plugins")

    def is_exist_plugin(plugin_id: str, version: str) -> bool:
        """
        通过文件名对应插件ID与插件版本来判断当前的插件是否存在
        :param plugin_id: 插件ID
        :param version: 插件版本
        :return: True: 不存在 False: 存在
        """
        if EventPluginV2.objects.filter(plugin_id=plugin_id, version=version).exists():
            print("[event plugin initial]  plugin({}) already existed".format(file_path))
            return True
        return False

    for plugin_file in os.listdir(document_root):
        try:
            file_path = os.path.join(document_root, plugin_file)
            if not os.path.isfile(file_path):
                continue
            # 判断是否存在，同时从文件名称拆分id与version
            pure_plugin_file_name = plugin_file.rsplit(".tar.gz")[0]
            if not pure_plugin_file_name:
                print("[event plugin initial] none plugin: {}".format(file_path))
                continue
            plugin_version_info = pure_plugin_file_name.rsplit('__', 1)
            plugin_id = plugin_version_info[0]
            version = plugin_version_info[1] if len(plugin_version_info) == 2 else "1.0.0"  # 命名没有默认1.0.0

            if is_exist_plugin(plugin_id=plugin_id, version=version):
                continue
            print("[event plugin initial] package to import: {}".format(file_path))
            with open(file_path, "rb") as tar_obj:
                file_data = SimpleUploadedFile("plugin.tar.gz", tar_obj.read())
                handler = PackageHandler.from_tar_file(file_data)
                plugin_info = handler.parse()
                if plugin_info["plugin_id"] == "rest_pull" and config_params:
                    plugin_info["config_params"] = config_params
                if all_alarm_types and all_alarm_types.get(plugin_info["plugin_id"]):
                    if "alert_config" in plugin_info:
                        plugin_info["alert_config"].extend(all_alarm_types[plugin_info["plugin_id"]])
                    else:
                        plugin_info["alert_config"] = all_alarm_types[plugin_info["plugin_id"]]
                plugin_info["bk_biz_id"] = 0
                plugin_info["version"] = plugin_info.get("version") or "1.0.0"
                if not(plugin_id == plugin_info["plugin_id"] and version == plugin_info["version"]):
                    print("[event plugin initial] match pluginId or version error, plugin:{}, plugin_id：{} version：{}".
                          format(plugin_file, plugin_info["plugin_id"], plugin_info["version"]))
                    continue
                try:
                    plugin = CreateEventPluginResource().perform_request(plugin_info)
                except BaseException as error:
                    print("[fta migration] create plugin({}) error: {}".format(plugin_info["plugin_id"], str(error)))
                    continue
                EventPluginV2.objects.filter(plugin_id=plugin["plugin_id"], version=plugin["version"]).update(
                    package_dir=handler.get_package_dir()
                )
            plugins[plugin["plugin_id"]] = plugin
            print(
                "[register] create plugin success, plugin_id({}), version({})".format(
                    plugin["plugin_id"], plugin["version"]
                )
            )
        except BaseException as error:
            print("[register] create plugin error, plugin_file({}), error info{}".format(plugin_file, str(error)))
    return plugins


def install_global_event_plugin(plugin):
    # 创建安装配置， 默认用全局内容

    print(
        "[fta migration] start to install global plugin plugin_id({}), version({})".format(
            plugin["plugin_id"], plugin["version"]
        )
    )
    inst_info = {
        "bk_biz_id": GLOBAL_BIZ_ID,
        "plugin_id": plugin["plugin_id"],
        "version": plugin["version"],
        "config_params": {param["field"]: param["default_value"] for param in plugin["config_params"]},
    }
    if EventPluginInstance.objects.filter(
        bk_biz_id=0, plugin_id=plugin["plugin_id"], version=plugin["version"]
    ).exists():
        inst_data = UpdateEventPluginInstanceResource().request(inst_info)
    else:
        inst_data = CreateEventPluginInstanceResource().request(inst_info)

    print(
        "[fta migration] install global plugin success, plugin_id({}), version({}), instance_data_id({})".format(
            plugin["plugin_id"], plugin["version"], inst_data["data_id"]
        )
    )


def migrate_fta_strategy(sender, **kwargs):
    """
    故障自愈的套餐迁移
    """
    print("[fta migrate] start to migrate fta from sender(%s)" % sender)
    try:
        migrate_event_plugin()
        migrate_actions_and_strategies(**kwargs)
    except BaseException:
        print("[fta migrate] migrate error, %s" % traceback.format_exc())


def migrate_actions_and_strategies(**kwargs):
    from django.conf import settings
    from fta_web.fta_migrate.strategy import MigrateFTAStrategy
    from fta_web.models.old_fta import AlarmDef, Solution

    bk_biz_ids = kwargs.pop("bk_biz_ids", [])
    if not bk_biz_ids:
        bk_biz_ids = set(Solution.objects.using("fta").values_list("cc_biz_id", flat=True)).union(
            set(AlarmDef.objects.all().using("fta").values_list("cc_biz_id", flat=True))
        )
    skipped_bizs = []
    success_bizs = []
    failed_bizs = []
    migreate_bizs = settings.FTA_MIGRATE_BIZS

    for bk_biz_id in bk_biz_ids:
        if bk_biz_id == 0:
            continue
        if bk_biz_id in migreate_bizs:
            skipped_bizs.append(bk_biz_id)
            continue

        print("[fta migrate] start to migrate strategies for biz(%s)" % bk_biz_id)
        try:
            MigrateFTAStrategy(bk_biz_id).migrate_fta_strategy()
        except BaseException as error:
            print("[fta migrate] failed to migrate strategies for biz({}), error({})".format(bk_biz_id, str(error)))
            failed_bizs.append(bk_biz_id)
            continue
        migreate_bizs.append(bk_biz_id)
        success_bizs.append(bk_biz_id)
        print("[fta migrate] end to migrate strategies for biz(%s)" % bk_biz_id)

    settings.FTA_MIGRATE_BIZS = migreate_bizs

    alarm_def_ids = set(
        AlarmDef.objects.using("fta")
        .filter(cc_biz_id__in=settings.FTA_MIGRATE_BIZS, is_enabled=True)
        .values_list("id", flat=True)
    )
    if alarm_def_ids:
        print("[fta migrate] close old fta alarm defs(%s) " % alarm_def_ids)
        AlarmDef.objects.using("fta").filter(id__in=alarm_def_ids).update(is_enabled=False)

    print(
        "[fta migrate] result success({}), failed({}), skipped({}) ".format(
            len(success_bizs), len(failed_bizs), len(skipped_bizs)
        )
    )
