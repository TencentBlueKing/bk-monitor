# -*- coding: utf-8 -*-
import collections
import json
import logging

from django.db.models import Q
from django.utils.translation import gettext as _

from bkmonitor.models import (
    ActionConfig,
    AlgorithmModel,
    DetectModel,
    DutyArrange,
    ItemModel,
    QueryConfigModel,
    StrategyActionConfigRelation,
    StrategyModel,
    UserGroup,
)
from core.drf_resource import api
from fta_web.constants import QuickSolutionsConfig
from fta_web.fta_migrate.constants import FTA_MONITOR_MAPPING, NoticeGroupMapping
from fta_web.fta_migrate.solution import MigrateDiySolution
from fta_web.fta_migrate.utils import (
    list_module_instance,
    list_service_template_by_module_ids,
)
from fta_web.models.old_fta import AlarmDef, AlarmType, Solution

logger = logging.getLogger("root")


class MigrateFTAStrategy:
    def __init__(self, bk_biz_id, operator="admin"):
        self.bk_biz_id = bk_biz_id
        self.operator = operator
        self.actions = {}
        self.clean_template_id = self.get_clean_template_id()
        self.builtin_actions = {}
        self.builtin_action_templates = {}
        self.origin_builtin_actions = {
            str(s.id): s.codename or s.title
            for s in Solution.objects.using("fta").filter(
                Q(codename__in=QuickSolutionsConfig.QUICK_SOLUTIONS_TEMPLATE_NAMES.keys())
            )
        }

    def get_clean_template_id(self):
        all_templates = api.sops.get_template_list(bk_biz_id=self.bk_biz_id)
        for template in all_templates:
            if template["name"] == _("【自愈套餐】磁盘清理(适用于Linux)"):
                return template["id"]
        return None

    def migrate_fta_strategy(self):
        # step 0 内置套餐写入

        # 初始化内置套餐
        self.run_init_builtin_action_config()

        # step 1 套餐数据的转换
        logger.info("step 1 转换当前业务 %s的套餐数据", self.bk_biz_id)
        self.actions = self.convert_solution_config()

        # step 2 告警接入的
        logger.info("step 1 转换当前业务 %s的告警接入数据", self.bk_biz_id)
        self.convert_alarm_def()

    def create_notice_action(self):
        # 创建通知事件
        return ActionConfig.objects.create(
            **{
                "is_enabled": True,
                "name": _("告警通知"),
                "desc": _("迁移的通知套餐"),
                "bk_biz_id": self.bk_biz_id,
                "plugin_id": 1,
                "execute_config": {
                    "template_detail": {
                        "notify_interval": 86400,
                        "interval_notify_mode": "standard",
                        "template": [
                            {
                                "signal": "abnormal",
                                "message_tmpl": "{{content.level}}\n{{content.begin_time}}\n{{content.time}}\n"
                                "{{content.duration}}\n{{content.target_type}}\n{{content.data_source}}"
                                "\n{{content.content}}\n{{content.current_value}}\n{{content.biz}}\n"
                                "{{content.target}}\n{{content.dimension}}\n{{content.detail}}\n"
                                "{{content.related_info}}",
                                "title_tmpl": "{{business.bk_biz_name}} - {{alarm.name}}{{alarm.display_type}}",
                            },
                            {
                                "signal": "recovered",
                                "message_tmpl": "{{content.level}}\n{{content.begin_time}}\n{{content.time}}\n"
                                "{{content.duration}}\n{{content.target_type}}\n{{content.data_source}}"
                                "\n{{content.content}}\n{{content.current_value}}\n{{content.biz}}\n"
                                "{{content.target}}\n{{content.dimension}}\n{{content.detail}}\n"
                                "{{content.related_info}}",
                                "title_tmpl": "{{business.bk_biz_name}} - {{alarm.name}}{{alarm.display_type}}",
                            },
                            {
                                "signal": "closed",
                                "message_tmpl": "{{content.level}}\n{{content.begin_time}}\n{{content.time}}\n"
                                "{{content.duration}}\n{{content.target_type}}\n{{content.data_source}}"
                                "\n{{content.content}}\n{{content.current_value}}\n{{content.biz}}\n"
                                "{{content.target}}\n{{content.dimension}}\n{{content.detail}}\n"
                                "{{content.related_info}}",
                                "title_tmpl": "{{business.bk_biz_name}} - {{alarm.name}}{{alarm.display_type}}",
                            },
                        ],
                    },
                    "timeout": 600,
                },
            }
        )

    def get_builtin_action_id(self, solution_id):
        builtin_key = self.origin_builtin_actions.get(str(solution_id), "")
        return self.builtin_actions.get(builtin_key)

    def create_action_strategy_relation(self, alarm_def, strategy_id, group_id, relation=None):
        """
        创建告警处理关系
        """
        action_id_v3 = self.actions.get(str(alarm_def.solution_id)) or self.get_builtin_action_id(alarm_def.solution_id)
        if not action_id_v3:
            logger.info(
                "solution(%s) of alarm def(%s) not exist, origin_builtin_actions is %s",
                alarm_def.solution_id,
                alarm_def.id,
                self.origin_builtin_actions,
            )
            return
        # 有处理套餐，增加处理套餐的内容
        StrategyActionConfigRelation.objects.create(
            strategy_id=strategy_id,
            config_id=action_id_v3,
            relate_type="ACTION",
            user_groups=relation.user_groups if relation else [group_id],
            signal=["abnormal"],
            options={
                "converge_config": {
                    "is_enabled": True,
                    "converge_func": "skip_when_exceed",
                    "timedelta": 60,
                    "count": 3,
                    "condition": [{"dimension": "action_info", "value": ["self"]}],
                    "need_biz_converge": True,
                }
            },
        )

    def convert_alarm_def(self):
        """
        转换自愈告警接入
        """
        alarm_name_mappings = {
            alarm_type.alarm_type: alarm_type.description
            for alarm_type in AlarmType.objects.filter(source_type__in=["CUSTOM", "REST-API"])
            .using("fta")
            .only("alarm_type", "description")
        }
        for alarm_def in AlarmDef.objects.filter(
            is_deleted=False, cc_biz_id=self.bk_biz_id, source_type__in=["CUSTOM", "BKEVENT", "REST-API"]
        ).using("fta"):
            # 创建用户组
            alert_name = alarm_name_mappings.get(alarm_def.alarm_type, alarm_def.alarm_type)
            if not alert_name and alarm_def.source_type != "BKEVENT":
                continue

            # 通知相关
            fta_notify_config = json.loads(alarm_def.notify)
            operate_signal = ["abnormal"]
            action_notify_config = collections.defaultdict(list)
            users = []
            users_is_empty = False
            for config_key, value in fta_notify_config.items():
                if value is False:
                    continue
                if config_key in ["to_extra", "to_role", "to_host_operator", "only_to_host", "only_to_role"]:
                    if config_key == "to_extra":
                        # TODO 包含其他人，告警组需要确认(done)
                        extra_users = [
                            {"id": user, "type": "user"} for user in set(alarm_def.responsible.split(";")) if user
                        ]
                        users.extend(extra_users)
                    else:
                        users.extend(NoticeGroupMapping.USER_GROUP.get(config_key, []))
                    continue
                config_key = config_key.replace("notify", "")
                try:
                    phase, notice_way = config_key.split("__")
                    phase = NoticeGroupMapping.NOTICE_PHASE[phase]
                    operate_signal.append(NoticeGroupMapping.OPERATE_SIGNAL[phase])
                    notice_way = NoticeGroupMapping.NOTICE_WAY.get(notice_way, notice_way)
                    action_notify_config[phase].append(notice_way)
                except BaseException as error:
                    logger.error(
                        "get execute notice way error %s, config_key(%s), alarm def(%s)",
                        str(error),
                        config_key,
                        alarm_def.id,
                    )

            if not users:
                users_is_empty = True
                # 如果没有配置负责人，则设置为主机负责人
                users = NoticeGroupMapping.USER_GROUP.get("to_host_operator", [])

            group_id = UserGroup.objects.create(
                bk_biz_id=self.bk_biz_id,
                name=_("[{}]自愈迁移{}告警组").format(alarm_def.id, alert_name or ""),
                desc=_("自愈迁移"),
                alert_notice=[
                    {
                        "time_range": "00:00:00--23:59:59",
                        "notify_config": [
                            {"type": ["weixin"], "level": 3},
                            {"type": ["weixin"], "level": 2},
                            {"type": ["weixin"], "level": 1},
                        ],
                    }
                ],
                action_notice=[
                    {
                        "time_range": "00:00:00--23:59:59",
                        "notify_config": [
                            {"type": notice_ways, "phase": phase} for phase, notice_ways in action_notify_config.items()
                        ],
                    }
                ],
            ).id

            DutyArrange.objects.create(need_rotation=False, users=users, user_group_id=group_id)
            target = self.get_monitor_target(alarm_def)
            if alarm_def.source_type == "BKEVENT":
                # 蓝鲸监控的策略，添加一个处理事件即可
                self.convert_monitor_strategy(
                    alarm_def, group_id, operate_signal, target, users=users, users_is_empty=users_is_empty
                )
                continue

            strategy_name = alarm_def.title or _("自愈迁移-{}").format(alert_name)
            # 创建一个策略
            new_strategy_inst = StrategyModel.objects.create(
                type="monitor",
                bk_biz_id=self.bk_biz_id,
                scenario="other_rt",
                name="[{}]{}".format(alarm_def.id, strategy_name),
                is_enabled=False,
            )
            # 创建一个监控数据
            item_id = ItemModel.objects.create(
                strategy_id=new_strategy_inst.id,
                name="COUNT({})".format(alert_name),
                expression="a",
                no_data_config={"continuous": 10, "is_enabled": False, "agg_dimension": [], "level": 2},
                origin_sql="",
                target=[target],
            ).id

            # 创建 query_config
            agg_condition = (
                [{"key": "tags.tnm_attr_id", "value": [alarm_def.alarm_attr_id], "method": "eq", "condition": "and"}]
                if alarm_def.alarm_attr_id
                else []
            )
            QueryConfigModel.objects.create(
                strategy_id=new_strategy_inst.id,
                item_id=item_id,
                alias="a",
                data_source_label="bk_fta",
                data_type_label="event",
                metric_id="bk_fta.event.{}".format(alert_name),
                config={
                    "result_table_id": "event",
                    "agg_method": "COUNT",
                    "agg_interval": 60,
                    "agg_dimension": ["ip", "bk_cloud_id"],
                    "agg_condition": agg_condition,
                    "metric_field": alert_name,
                    "unit": "",
                    "index_set_id": "",
                    "query_string": "*",
                    "custom_event_name": alert_name,
                    "functions": [],
                    "time_field": "time",
                    "bkmonitor_strategy_id": alert_name,
                    "alert_name": alert_name,
                },
            )

            # 创建对应的算法和检测内容
            AlgorithmModel.objects.create(
                item_id=item_id,
                type="Threshold",
                strategy_id=new_strategy_inst.id,
                unit_prefix="",
                config=[[{"method": "gte", "threshold": 1}]],
                level=1,
            )
            DetectModel.objects.create(
                level=1,
                strategy_id=new_strategy_inst.id,
                expression="",
                recovery_config={"check_window": 5},
                connector="and",
                trigger_config={"count": 1, "check_window": 1},
            )

            # 创建关联关系
            self.create_action_strategy_relation(alarm_def, new_strategy_inst.id, group_id)

            # 创建通知关联关系
            notice_action = self.create_notice_action()
            StrategyActionConfigRelation.objects.create(
                strategy_id=new_strategy_inst.id,
                config_id=notice_action.id,
                relate_type="NOTICE",
                user_groups=[group_id],
                signal=operate_signal,
                options={
                    "converge_config": {
                        "is_enabled": True,
                        "need_biz_converge": True,
                        "timedelta": 60,
                        "count": 1,
                        "condition": [
                            {"dimension": "strategy_id", "value": ["self"]},
                            {"dimension": "dimensions", "value": ["self"]},
                            {"dimension": "alert_level", "value": ["self"]},
                            {"dimension": "signal", "value": ["self"]},
                            {"dimension": "bk_biz_id", "value": ["self"]},
                            {"dimension": "notice_receiver", "value": ["self"]},
                            {"dimension": "notice_way", "value": ["self"]},
                        ],
                        "converge_func": "collect",
                        "sub_converge_config": {
                            "timedelta": 60,
                            "max_timedelta": 60,
                            "count": 2,
                            "condition": [
                                {"dimension": "bk_biz_id", "value": ["self"]},
                                {"dimension": "notice_receiver", "value": ["self"]},
                                {"dimension": "notice_way", "value": ["self"]},
                                {"dimension": "alert_level", "value": ["self"]},
                                {"dimension": "signal", "value": ["self"]},
                            ],
                            "converge_func": "collect_alarm",
                        },
                    }
                },
            )

    def get_monitor_target(self, alarm_def):
        """
        TODO:
        1、通过接口实时根据模块名获取信息
        2、如果仅存在模块信息，则直接用服务实例的方式
        """
        module_ids = []
        # 当category为"DBA"时，找到当前业务下数据类型为"数据库"的模块
        if alarm_def.category == "DBA":
            module_instance_list = list_module_instance(self.bk_biz_id)
            for item in module_instance_list:
                if item["bk_module_type"] == "2":
                    module_ids.append(item["bk_module_id"])
        else:
            # 根据模块名称获取模块id
            module_names = alarm_def.module_names.split(",") if alarm_def.module_names else []
            module_instance_list = list_module_instance(self.bk_biz_id)
            for item in module_instance_list:
                if item["bk_module_name"] in module_names and module_names:
                    module_ids.append(item["bk_module_id"])

        target_sets = [
            {"bk_inst_id": int(set_id), "bk_obj_id": "set"} for set_id in set(alarm_def.topo_set.split(",")) if set_id
        ]

        if module_ids:
            target_modules = [{"bk_inst_id": int(module_id), "bk_obj_id": "module"} for module_id in module_ids]
        else:
            target_modules = [
                {"bk_inst_id": int(module_id), "bk_obj_id": "module"}
                for module_id in set(alarm_def.module.split(","))
                if module_id
            ]
        target = []
        if not (target_sets or target_modules):
            return target
        if not target_sets and target_modules:
            target_module_ids = [item["bk_inst_id"] for item in target_modules]
            target_service_templates = list_service_template_by_module_ids(
                alarm_def.cc_biz_id, target_module_ids, self.operator
            )
            # 如果查询出module对应的服务模版为0，则target为动态节点
            if target_service_templates == [0]:
                target = [{"field": "host_topo_node", "method": "eq", "value": target_modules}]
                return target
            target = [
                {
                    "field": "host_service_template",
                    "method": "eq",
                    "value": [
                        {"bk_obj_id": "SERVICE_TEMPLATE", "bk_inst_id": template}
                        for template in target_service_templates
                    ],
                }
            ]
            return target

        # 最后再考虑用动态节点
        if target_modules:
            target = [{"field": "host_topo_node", "method": "eq", "value": target_modules}]
        elif target_sets:
            target = [{"field": "host_topo_node", "method": "eq", "value": target_sets}]
        return target

    def convert_monitor_strategy(self, alarm_def, new_group_id, operate_signal, target, **kwargs):
        _, strategy_id = alarm_def.alarm_type.split("_")
        if not strategy_id:
            return
        try:
            strategy = StrategyModel.objects.get(id=strategy_id)
            strategy.id = None
            strategy.is_enabled = False
            strategy.name = _("[{}]自愈迁移-{}").format(alarm_def.id, strategy.name)
            strategy.save()
            new_strategy_id = strategy.id
        except BaseException as error:
            logger.info("migrate monitor strategy(%s) error: %s", strategy_id, str(error))
            return

        try:
            for item in ItemModel.objects.filter(strategy_id=strategy_id):
                old_item_id = item.id
                item.target = [target]
                item.id = None
                item.strategy_id = strategy.id
                item.save()
                for algorithm in AlgorithmModel.objects.filter(item_id=old_item_id):
                    algorithm.strategy_id = new_strategy_id
                    algorithm.item_id = item.id
                    algorithm.id = None
                    algorithm.save()

                for query_config in QueryConfigModel.objects.filter(strategy_id=strategy_id, item_id=old_item_id):
                    query_config.id = None
                    query_config.item_id = item.id
                    query_config.strategy_id = new_strategy_id
                    query_config.save()

            for detect_obj in DetectModel.objects.filter(strategy_id=strategy_id):
                detect_obj.strategy_id = new_strategy_id
                detect_obj.id = None
                detect_obj.save()

        except BaseException as error:
            logger.info("migrate monitor query config of strategy(%s)  error: %s", strategy_id, str(error))
            return

        relation = StrategyActionConfigRelation.objects.filter(strategy_id=strategy_id, relate_type="NOTICE").first()
        if relation:
            try:
                action_config = ActionConfig.objects.get(id=relation.config_id)
                action_config.id = None
                action_config.save()
                relation.id = None
                relation.strategy_id = new_strategy_id
                relation.config_id = action_config.id
                relation.user_groups.append(new_group_id)
                relation.signal.extend(operate_signal)
                relation.save()
            except BaseException as error:
                logger.info(
                    "migrate monitor strategy-action config of strategy(%s)  error: %s", strategy_id, str(error)
                )
                relation = None

        self.create_action_strategy_relation(alarm_def, strategy.id, new_group_id, relation)

    def convert_solution_config(self):
        actions = self.migrate_normal_solutions()
        diy_actions = MigrateDiySolution(self.bk_biz_id, self.builtin_action_templates).migrate_solutions()
        if diy_actions:
            actions.update(diy_actions)
        return actions

    def migrate_normal_solutions(self):
        """
        常规迁移
        :return:
        """
        solution_type_mapping = {"notice": 1, "ijobs": 3, "gcloud": 4, "clean": 4, "http_callback": 2, "http": 2}
        actions = {}
        for solution in (
            Solution.objects.filter(is_deleted=False, cc_biz_id=self.bk_biz_id)
            .exclude(codename__in=["diy_only", "diy"])
            .using("fta")
        ):
            if solution.solution_type not in solution_type_mapping:
                # 仅对当前集中套餐方式进行迁移
                continue

            try:
                config = json.loads(solution.config)
            except BaseException as error:
                logger.error("get solution config error, %s, solution id  %s", str(error), solution.id)
                continue
            convert_function = getattr(self, "convert_{}".format(solution.solution_type), None)
            if convert_function is None:
                continue
            actions[str(solution.id)] = ActionConfig.objects.create(
                **{
                    "name": solution.title,
                    "plugin_id": solution_type_mapping.get(solution.solution_type),
                    "bk_biz_id": solution.cc_biz_id,
                    "desc": _("{}（迁移自愈套餐）").format(solution.title),
                    "execute_config": convert_function(config, solution_id=solution.id),
                    "is_builtin": False,
                }
            ).id
        return actions

    def run_init_builtin_action_config(self):
        # 为业务初始化快捷套餐
        # 在当前业务下注册对应的快捷内容
        for action_config in ActionConfig.objects.filter(
            bk_biz_id__in=[self.bk_biz_id, 0], is_deleted=False, is_builtin=True
        ):
            for key, value in QuickSolutionsConfig.QUICK_SOLUTIONS_CONFIG.items():
                if value["name"] == action_config.name:
                    self.builtin_actions[key] = action_config.id
                    break

        if len(self.builtin_actions.keys()) == 4:
            return

        try:
            if not self.builtin_actions:
                # 监控系统已经生成的内容，不再重复导入
                for template_data in [
                    QuickSolutionsConfig.QUICK_SOLUTIONS_TEMPLATE,
                    QuickSolutionsConfig.IDLE_TEMPLATE,
                ]:
                    api.sops.import_project_template(template_data=template_data, project_id=self.bk_biz_id)
        except BaseException as error:
            logger.exception("[init_builtin_action_config(%s)] error: %s", self.bk_biz_id, str(error))
            return
        all_templates = api.sops.get_template_list(bk_biz_id=self.bk_biz_id)
        for template in all_templates:
            if template["name"] not in QuickSolutionsConfig.QUICK_SOLUTIONS_TEMPLATE_NAMES.values():
                continue

            if template["name"] == QuickSolutionsConfig.QUICK_SOLUTIONS_TEMPLATE_NAMES[QuickSolutionsConfig.CLEAN_DISK]:
                self.clean_template_id = template["id"]
                continue

            for config_key, name in QuickSolutionsConfig.QUICK_SOLUTIONS_TEMPLATE_NAMES.items():
                solution_name = QuickSolutionsConfig.QUICK_SOLUTIONS_CONFIG.get(config_key, {}).get("name")
                if not solution_name:
                    continue

                if (
                    name == template["name"]
                    and not ActionConfig.objects.filter(name=solution_name, bk_biz_id=self.bk_biz_id).exists()
                ):
                    # 当前模板没有创建快捷套餐，则创建
                    action_config = {
                        "is_builtin": True,
                        "name": solution_name,
                        "plugin_id": 4,
                        "bk_biz_id": self.bk_biz_id,
                        "desc": _("系统内置快捷套餐"),
                        "execute_config": {
                            "template_detail": QuickSolutionsConfig.QUICK_SOLUTIONS_CONFIG[config_key][
                                "template_detail"
                            ],
                            "template_id": template["id"],
                            "timeout": 600,
                        },
                    }
                    action = ActionConfig.objects.create(**action_config)
                    self.builtin_actions[config_key] = action.id
                    break
        logger.info(
            "[init_builtin_action_config(%s)] finished, create configs %s",
            self.bk_biz_id,
            ",".join(list(self.builtin_actions.keys())),
        )

    def get_builtin_action_template_ids(self):
        action_key_mapping = {str(act_id): key for key, act_id in self.builtin_actions.items()}
        for action in ActionConfig.objects.filter(id__in=self.builtin_actions.values()):
            template_id = action.execute_config["template_id"]
            self.builtin_action_templates[action_key_mapping[str(action.id)]] = template_id
        self.builtin_action_templates[QuickSolutionsConfig.CLEAN_DISK] = self.clean_template_id

    def get_default_clean_params(self):
        return {
            "${biz_cc_id}": "{{target.business.bk_biz_id}}",
            "${job_ip_list}": "{{target.host.bk_host_innerip}}",
            "${job_account}": "root",
        }

    def convert_diy(self, config, **kwargs):
        # 组合套餐的转移
        pass

    def convert_clean(self, config, **kwargs):
        params_dict = {
            "clean_catalog": "${absolute_path}",
            "clean_date": "${days}",
            "clean_date_custom": "${days}",
            "clean_file": "${file_pattern}",
        }
        params = self.get_default_clean_params()
        for key, value in config.items():
            if key not in ["clean_date", "clean_file", "clean_catalog"]:
                continue
            new_key = params_dict[key]
            if key == "clean_date" and value == "self":
                params[new_key] = config["clean_date_custom"]
                continue
            for fta_v, monitor_v in FTA_MONITOR_MAPPING.items():
                if fta_v in value:
                    value = value.replace(fta_v, monitor_v)
            params[new_key] = value
        return {"template_detail": params, "template_id": self.clean_template_id, "timeout": 600}

    def convert_ijobs(self, config, **kwargs):
        param_prefix = "parms_"
        params = {}
        for key, value in config.items():
            if param_prefix not in key:
                continue
            [category, field] = key.lstrip(param_prefix).split("_")
            new_key = "{}_{}".format(field, category)
            for fta_v, monitor_v in FTA_MONITOR_MAPPING.items():
                if fta_v in value:
                    value = value.replace(fta_v, monitor_v)
            params[new_key] = value
        return {"template_detail": params, "template_id": config.get("task_id"), "timeout": 600}

    def convert_gcloud(self, config, **kwargs):
        param_prefix = "params_"
        params = {}
        for key, value in config.items():
            if param_prefix not in key:
                continue
            new_key = key.lstrip(param_prefix)
            for fta_v, monitor_v in FTA_MONITOR_MAPPING.items():
                if fta_v in value:
                    value = value.replace(fta_v, monitor_v)
            params[new_key] = value
        return {"template_detail": params, "template_id": config.get("template"), "timeout": 600}

    def convert_http(self, config, **kwargs):
        content = json.dumps(
            {
                "ip": "{{target.host.bk_host_innerip}}",
                "source_type": "MONITOR",
                "alarm_type": "{{alarm.name}}",
                "content": "{{alarm.description}}",
                "source_time": "{{alarm.begin_time}}",
                "cc_biz_id": "{{target.business.bk_biz_id}}",
            }
        )
        return {
            "template_detail": {
                "need_poll": False,
                "notify_interval": 120,
                "interval_notify_mode": "standard",
                "method": "POST",
                "url": config.get("url"),
                "headers": [],
                "authorize": {"auth_type": "none", "auth_config": {}},
                "body": {"data_type": "raw", "params": [], "content": content, "content_type": "json"},
                "query_params": [],
                "failed_retry": {"is_enabled": True, "timeout": 600, "max_retry_times": 2, "retry_interval": 2},
            },
            "timeout": 600,
        }

    def convert_http_callback(self, config, **kwargs):
        return self.convert_http(config, **kwargs)
