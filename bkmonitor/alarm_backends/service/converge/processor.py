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
import copy
import hashlib
import logging
from copy import deepcopy
from datetime import datetime, timedelta

from django.conf import settings
from django.utils import timezone
from django.utils.translation import gettext as _

from alarm_backends.constants import CONST_HALF_MINUTE, CONST_MINUTES, CONST_SECOND
from alarm_backends.core.cache.action_config import ActionConfigCacheManager
from alarm_backends.core.cache.key import (
    ACTION_CONVERGE_KEY_PROCESS_LOCK,
    FTA_NOTICE_COLLECT_KEY,
)
from alarm_backends.core.context import ActionContext
from alarm_backends.service.converge.converge_func import ConvergeFunc
from alarm_backends.service.converge.converge_manger import ConvergeManager
from alarm_backends.service.converge.shield import ShieldManager
from alarm_backends.service.converge.shield.shielder import AlertShieldConfigShielder
from alarm_backends.service.converge.utils import get_execute_related_ids
from alarm_backends.service.fta_action import need_poll
from alarm_backends.service.fta_action.tasks import run_action, run_webhook_action
from bkmonitor.models.fta.action import ActionInstance, ConvergeInstance
from bkmonitor.utils import extended_json
from constants.action import (
    ALL_CONVERGE_DIMENSION,
    ActionPluginType,
    ActionStatus,
    ConvergeType,
)
from core.errors.alarm_backends import ActionAlreadyFinishedError, StrategyNotFound
from core.prometheus import metrics

logger = logging.getLogger("fta_action.converge")


class ConvergeLockError(BaseException):
    def __init__(self, *args, **kwargs):  # real signature unknown
        pass


class ConvergeProcessor(object):
    InstanceModel = {ConvergeType.CONVERGE: ConvergeInstance, ConvergeType.ACTION: ActionInstance}

    def __init__(self, converge_config, instance_id, instance_type, converge_context=None, alerts=None):
        """ """

        self.status = converge_context.get("status", "") if converge_context else ""
        self.comment = ""
        self.instance_type = instance_type
        self.shield_manager = ShieldManager()
        self.is_illegal = False
        self.converge_config = {}
        self.sleep_time = CONST_HALF_MINUTE
        self.instance_id = instance_id
        self.dimension = ""
        self.lock_key = ""
        self.need_unlock = False
        self.instance_model = self.InstanceModel[instance_type]
        try:
            self.instance = self.instance_model.objects.get(id=instance_id)
        except Exception as error:
            print("pytest|get {} converge instance({})  failed {}".format(instance_type, instance_id, str(error)))
            raise
        if instance_id == 12:
            print("start to debug")
        print("pytest|get {} converge instance({})  finished".format(instance_type, instance_id))
        self.alerts = alerts
        self.origin_converge_config = copy.deepcopy(converge_config)
        self.context = converge_context
        if self.context is None:
            self.get_converge_context()
        converge_config = self.set_converge_count_and_timedelta(converge_config) if converge_config else {}
        self.converge_config.update(converge_config)

        if converge_config.get("is_enabled", False) is False:
            # 不需要收敛的内容
            self.is_illegal = True
            return

        if self.is_parent_action() or not converge_config:
            # 如果没有收敛参数，表示不需要任何收敛
            # 如果收敛对象对虚拟的主响应动作，不做收敛
            # 如果没有开启告警防御，直接不做收敛处理
            self.is_illegal = True
            return

        if not converge_config.get("condition"):
            self.is_illegal = True
            self.converge_config.update({"description": "illegal converge_config"})
            logger.warning("$%s illegal converge_config %s", self.instance["id"], converge_config["condition"])
            return

        # check timedelta and count
        if converge_config["timedelta"] <= 0:
            self.converge_config.update({"description": "illegal converge_config, timedelta <= 0"})
            self.is_illegal = True
            logger.warning(
                "$%s illegal converge_config #%s: timedelta %s <= 0",
                instance_id,
                converge_config["id"],
                converge_config["timedelta"],
            )
            return

        self.converge_count = converge_config["count"]
        if self.converge_count < 0:
            self.converge_config.update({"description": "illegal converge_config, count < 0"})
            self.is_illegal = True
            logger.warning("$%s illegal converge_config : count %s <= 0", instance_id, self.converge_count)
            return

        # converge_range 设置了最大的收敛延时窗口，则用最大的时间窗口，否则用timedelta作为时间收敛窗口
        self.converge_timedelta = int(self.converge_config["timedelta"]) // CONST_MINUTES
        self.max_converge_timedelta = int(self.converge_config.get("max_timedelta") or 0) // CONST_MINUTES

        self.start_time = self.instance.create_time - timedelta(
            minutes=self.max_converge_timedelta or self.converge_timedelta
        )
        self.start_timestamp = int(self.start_time.timestamp())

        # 第一次进行收敛的时候，只计算可收敛条件，不用持续时间
        self.first_start_timestamp = int(
            (self.instance.create_time - timedelta(minutes=self.converge_timedelta)).timestamp()
        )

        # 添加一个收敛结束的时候，避免大范围内
        self.end_timestamp = int(
            (
                self.instance.create_time + timedelta(minutes=self.max_converge_timedelta or self.converge_timedelta)
            ).timestamp()
        )
        self.dimension = self.get_dimension(safe_length=128)

    def set_converge_count_and_timedelta(self, converge_config):
        """
        设置默认收敛策略
        """
        if self.instance_type == ConvergeType.ACTION:
            if self.instance.action_config["plugin_type"] == ActionPluginType.NOTICE:
                converge_config["timedelta"] = CONST_MINUTES * 2
                converge_config["count"] = 1
                if self.context.get("notice_info"):
                    # 如果不存在notice_info维度信息，可能是老数据，保留原来的收敛维度
                    converge_config["condition"] = [{"dimension": "notice_info", "value": ["self"]}]
            elif not converge_config.get("condition"):
                # 其他处理套餐没有condition的，补充一下
                converge_config["condition"] = [{"dimension": "action_info", "value": ["self"]}]

        if self.instance_type == ConvergeType.CONVERGE:
            converge_config["timedelta"] = settings.MULTI_STRATEGY_COLLECT_WINDOW
            converge_config["count"] = settings.MULTI_STRATEGY_COLLECT_THRESHOLD
        return converge_config

    def get_converge_context(self):
        """根据实例对象获取到收敛上下文"""
        if self.instance_type == ConvergeType.ACTION:
            self.context = ActionContext(self.instance, [], alerts=self.alerts).converge_context.get_dict(
                ALL_CONVERGE_DIMENSION.keys()
            )
        else:
            self.context = self.instance.converge_config["converged_condition"]

    def is_parent_action(self):
        """收敛对象是否为虚拟主任务"""
        return self.instance_type == ConvergeType.ACTION and self.instance.is_parent_action

    def is_alert_shield(self):
        """
        当前告警是否屏蔽
        :return:
        """
        for alert in self.alerts:
            # 关联多告警的内容，只要有其中一个不满足条件，直接就屏蔽
            alert.strategy_id = alert.strategy_id
            shielder = AlertShieldConfigShielder(alert)
            if shielder.is_matched():
                return True, shielder

    def converge_alarm(self):
        """run converge by converge_config"""

        try:
            self.status = self.run_converge()
            self.comment = self.converge_config.get("description")
            # 收敛之后，推送至处理队列或者重新推送至收敛队列
            self.push_to_queue()
        except ConvergeLockError as error:
            raise error
        except ActionAlreadyFinishedError as error:
            logger.info("run action converge(%s) failed: %s", self.instance_id, str(error))
            return
        except StrategyNotFound:
            logger.info(
                "run action converge(%s) skip: strategy(%s) not found", self.instance_id, self.instance.strategy_id
            )
            self.status = ActionStatus.SKIPPED
            self.comment = _("策略({}) 被删除或停用, 跳过.").format(
                self.instance.strategy_id,
            )
            self.push_to_queue()
            return
        except BaseException:
            logger.exception(
                "run converge failed: [%s]",
                self.converge_config,
            )
            # 收敛失败的，则重新推入收敛队列, 1分钟之后再做收敛检测
            self.push_converge_queue()
            return
        finally:
            self.unlock()

    def lock(self):
        client = ACTION_CONVERGE_KEY_PROCESS_LOCK.client
        parallel_converge_count = max(int(self.converge_count) // 2, 1)
        self.lock_key = ACTION_CONVERGE_KEY_PROCESS_LOCK.get_key(dimension=self.dimension)
        if client.incr(self.lock_key) > parallel_converge_count:
            # 如果当前的计数器大于并发数，直接返回异常
            client.decr(self.lock_key)
            ttl = client.ttl(self.lock_key)
            if ttl is None or ttl < 0:
                # 如果没有ttl的情况，很有可能是并发抢占，需要设置一下ttl, 避免长期占用
                client.expire(self.lock_key, ACTION_CONVERGE_KEY_PROCESS_LOCK.ttl)
            raise ConvergeLockError(
                "get parallel converge failed, current_parallel_converge_count is {}, converge condition is {}".format(
                    parallel_converge_count, self.dimension
                )
            )
        client.expire(self.lock_key, ACTION_CONVERGE_KEY_PROCESS_LOCK.ttl)
        # 当获取到锁的情况下才需要去解锁
        self.need_unlock = True

    def unlock(self):
        if self.need_unlock is False:
            return
        client = ACTION_CONVERGE_KEY_PROCESS_LOCK.client
        if int(client.get(self.lock_key) or 0) > 0:
            # 当前key没有过期的时候，需要进行递减
            client.decr(self.lock_key)

    def run_converge(self):
        # 告警屏蔽优先级最高，如果屏蔽了，则都不需要处理，直接不做收敛
        if self.instance_type == ConvergeType.ACTION:
            if self.instance.status in ActionStatus.END_STATUS:
                # 已经结束不再进行收敛防御
                raise ActionAlreadyFinishedError({"action_id": self.instance_id, "action_status": self.instance.status})

            if self.instance.status == ActionStatus.SLEEP and self.is_sleep_timeout():
                # 超时的任务直接忽略收敛
                return ActionStatus.SKIPPED
            if self.instance.is_parent_action is False:
                # 收敛的时候，非主任务需要判断当前的Action是否是屏蔽状态的
                is_shielded, shielder = self.shield_manager.shield(self.instance, self.alerts)
                if is_shielded:
                    # 如果告警是处理屏蔽状态的，直接忽略
                    logger.info("action({}) shielded".format(self.instance_id))
                    self.converge_config["description"] = "Stop to converge because of shielded"
                    shield_detail = extended_json.loads(shielder.detail)
                    self.instance.outputs = {"shield": {"type": shielder.type, "detail": shield_detail}}
                    self.instance.ex_data = shield_detail
                    # 屏蔽的时候，将不会执行，所以此处执行次数默认加1
                    self.instance.execute_times += 1
                    self.instance.insert_alert_log(
                        description=_("套餐处理【{}】已屏蔽， 屏蔽原因：{}").format(
                            self.instance.name, shield_detail.get("message", "others")
                        )
                    )
                    return ActionStatus.SHIELD

        if self.instance_type == ConvergeType.CONVERGE and self.instance.end_time:
            # 如果为二级收敛并且结束，直接抛出完成的异常
            raise ActionAlreadyFinishedError(
                {
                    "action_id": "{}-{}".format(self.instance_id, self.instance_type),
                    "action_status": ActionStatus.SUCCESS,
                }
            )

        if self.is_illegal:
            # 不需要收敛的直接返回
            return False

        converge_manager = ConvergeManager(
            self.converge_config,
            self.dimension,
            self.start_time,
            self.instance,
            self.instance_type,
            end_timestamp=self.end_timestamp,
            alerts=self.alerts,
        )

        converged_instance = converge_manager.converge_instance
        if self.need_get_lock(converged_instance):
            # 当没有生成收敛记录的时候，才进行分布式锁控制
            # 当前生成了收敛记录，但是关联数量不够的情况下， 也需要进行加锁控制
            self.get_dimension_lock()

        if converge_manager.do_converge() is False:
            return False

        converge_instance = converge_manager.converge_instance

        converge_func = ConvergeFunc(
            self.instance,
            converge_manager.match_alarm_id_list,
            converge_manager.is_created,
            converge_instance,
            self.converge_config,
            converge_manager.biz_converge_existed,
        )
        converge_method = getattr(converge_func, self.converge_config["converge_func"])
        self.status = False if converge_method is None else converge_method()
        converge_manager.connect_converge(status=self.status)
        if self.status == ActionStatus.SKIPPED and self.instance_type == ConvergeType.ACTION:
            # 忽略的时候，需要在日志中插入记录
            action_name = ActionConfigCacheManager.get_action_config_by_id(self.instance.action_config_id).get("name")
            # 忽略的时候，将不会执行，所以此处执行次数默认加1
            self.instance.execute_times += 1
            self.instance.insert_alert_log(
                description=_("套餐【{}】已收敛， 收敛原因：{}").format(action_name, converge_instance.description)
            )
        return self.status

    def get_dimension_lock(self):
        """
        获取收敛维度锁
        """
        try:
            self.lock()
        except ConvergeLockError as error:
            # 获取锁错误的时候，进入收敛等待队列
            self.sleep_time = CONST_SECOND * 3
            self.push_converge_queue()
            raise error

    def need_get_lock(self, conv_inst: ConvergeInstance = None):
        if conv_inst is None:
            # 不存在converge_inst的时候，
            return True

        if self.instance_type == ConvergeType.CONVERGE or self.converge_count <= 1:
            # 已经业务汇总并产生了收敛实例， 不需要
            # 当前收敛个数为1,已经产生了，一定不需要
            return False

        if get_execute_related_ids(conv_inst.id, self.instance_type).count() < self.converge_count:
            return True

    def is_sleep_timeout(self):
        """check wether timeout for 'sleep' status"""
        if self.instance_type != ConvergeType.ACTION:
            return False

        execute_config = self.instance.action_config["execute_config"]
        max_timeout = max(int(execute_config["timeout"]), self.max_converge_timedelta * 60)
        if int(self.instance.create_time.timestamp()) + max_timeout < int(datetime.now().timestamp()):
            # 如果创建时间已经超过了处理的超时时间，则忽略不处理
            return True
        return False

    def get_dimension_value(self, value):
        """
        获取指定维度的哈希值
        """
        if isinstance(value, list):
            if len(value) >= 4:
                h = hashlib.md5(value).hexdigest()[:5]
                value = [value[0], "{}.{}".format(h, len(value) - 2), value[-1]]
            dimension_value = ",".join(map(str, value))
        else:
            dimension_value = value
        return dimension_value

    def get_dimension(self, safe_length=0):
        """
        通过收敛条件中配置的收敛规则获取到维度信息
        """
        converge_dimension = ["#%s" % self.converge_config["converge_func"]]
        self.converge_config["converged_condition"] = {}
        dimension_conditions = {
            condition["dimension"]: condition for condition in self.converge_config.get("condition")
        }
        # 同步原始设置的key
        dimension_conditions.update(
            {condition["dimension"]: condition for condition in self.origin_converge_config.get("condition", [])}
        )
        dimension_conditions = collections.OrderedDict(sorted(dimension_conditions.items()))

        # 这里需要去重
        for dimension_condition in dimension_conditions.values():
            # replace "self" to real value
            key = dimension_condition["dimension"]
            values = deepcopy(dimension_condition["value"])
            for index, value in enumerate(values):
                if value == "self":
                    values[index] = self.context.get(key, "")
                converge_dimension.append("|{}:{}".format(key, self.get_dimension_value(values[index])))
            self.converge_config["converged_condition"][key] = [
                value[0] if isinstance(value, list) else value for value in values
            ]
        dimension = "".join(converge_dimension)
        sha1 = hashlib.sha1(dimension.encode("utf-8"))
        dimension = "!sha1#%s" % sha1.hexdigest()
        return dimension[:safe_length]

    def push_to_queue(self):
        """update status in DB && push into queue"""
        end_time = datetime.now(tz=timezone.utc) if self.status in ActionStatus.END_STATUS else None
        if isinstance(self.instance, ActionInstance):
            # 如果是处理动作的收敛，需要更新处理动作的状态和对象
            self.instance.status = self.status if self.status else ActionStatus.CONVERGED
            self.instance.outputs = {"message": self.comment}
            self.instance.end_time = end_time
            self.instance.update_time = end_time
            if end_time:
                self.instance.need_poll = need_poll(self.instance)
            self.instance.save(
                update_fields=["outputs", "status", "end_time", "update_time", "need_poll", "ex_data", "execute_times"]
            )
            if self.instance.status in ActionStatus.END_STATUS:
                return

        if self.status == ActionStatus.SLEEP:
            # 如果还在等待中的收敛，则重新推入收敛队列, 1分钟之后再做收敛检测
            self.push_converge_queue()
        else:
            self.push_to_action_queue()

    def push_to_action_queue(self):
        """push alarm to action queue"""
        logger.info("converge: ready to push to action queue %s instance id %s", self.instance_type, self.instance_id)
        if self.instance_type != ConvergeType.ACTION:
            # 非动作类的事件，仅仅是为了做收敛，不做具体的事件处理
            return

        if self.status in [ActionStatus.SKIPPED, ActionStatus.SHIELD]:
            # 为忽略状态的任务表示收敛不处理，不需要推送至队列
            return

        plugin_type = self.instance.action_plugin["plugin_type"]
        action_info = {
            "id": self.instance_id,
            "function": "create_approve_ticket" if self.status == ActionStatus.WAITING else "execute",
            "alerts": self.alerts,
        }
        collect_key = ""
        if plugin_type == ActionPluginType.NOTICE and self.instance.is_parent_action is False:
            # 通知子任务需要记录通知方式，触发信号，告警ID进行后续的汇总合并
            client = FTA_NOTICE_COLLECT_KEY.client
            collect_key = FTA_NOTICE_COLLECT_KEY.get_key(
                **{
                    "notice_way": self.context["group_notice_way"],
                    "action_signal": self.instance.signal,
                    "alert_id": "_".join([str(a) for a in self.instance.alerts]),
                }
            )
            # 设置key
            client.hset(collect_key, self.context["notice_receiver"], self.instance_id)
            client.expire(collect_key, FTA_NOTICE_COLLECT_KEY.ttl)
            task_id = run_action.apply_async((plugin_type, action_info), countdown=1)
        elif plugin_type in [
            ActionPluginType.WEBHOOK,
            ActionPluginType.MESSAGE_QUEUE,
        ]:
            task_id = run_webhook_action.delay(plugin_type, action_info)
        else:
            task_id = run_action.delay(plugin_type, action_info)
        logger.info(
            "$ %s push fta action %s %s to rabbitmq, alerts %s, collect_key %s",
            task_id,
            self.instance_id,
            plugin_type,
            self.instance.alerts,
            collect_key,
        )
        metrics.CONVERGE_PUSH_ACTION_COUNT.labels(
            bk_biz_id=self.instance.bk_biz_id,
            plugin_type=plugin_type,
            strategy_id=metrics.TOTAL_TAG,
            signal=self.instance.signal,
        ).inc()

    def push_converge_queue(self):
        # 如果还在等待中的收敛，则重新推入收敛队列, 1分钟之后再做收敛检测
        from alarm_backends.service.converge.tasks import run_converge

        task_id = run_converge.apply_async(
            (self.origin_converge_config, self.instance_id, self.instance_type, self.context, self.alerts),
            countdown=self.sleep_time,
        )

        logger.info(
            "push %s(%s) to converge queue again, delay %s, task_id(%s)",
            self.instance_type,
            self.instance_id,
            self.sleep_time,
            task_id,
        )
        metrics.CONVERGE_PUSH_CONVERGE_COUNT.labels(
            bk_biz_id=self.instance.bk_biz_id, instance_type=self.instance_type
        ).inc()
