"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import logging
import random
import time
from datetime import datetime, timezone

from django.utils.translation import gettext as _

from alarm_backends.core.cache.key import FTA_SUB_CONVERGE_DIMENSION_LOCK_KEY
from alarm_backends.service.converge.dimension import (
    DimensionCalculator,
    DimensionHandler,
)
from alarm_backends.service.converge.tasks import run_converge
from alarm_backends.service.converge.utils import list_other_converged_instances
from bkmonitor.models.fta.action import (
    ActionInstance,
    ConvergeInstance,
    ConvergeRelation,
)
from constants.action import (
    ALL_CONVERGE_DIMENSION,
    ActionStatus,
    ConvergeStatus,
    ConvergeType,
)

logger = logging.getLogger("fta_action.converge")


class ConvergeManager:
    def __init__(
        self,
        converge_config,
        dimension,
        start_time,
        instance,
        instance_type=ConvergeType.ACTION,
        end_timestamp=None,
        alerts=None,
    ):
        self.alerts = alerts
        self.converge_config = converge_config
        self.instance_type = instance_type
        self.instance = instance
        self.dimension = dimension
        self.is_created = False
        self.start_time = start_time
        self.end_timestamp = end_timestamp
        self.match_alarm_id_list = []
        self.converge_instance = self.get_converge_instance(start_time)
        self.start_timestamp = int(self.start_time.timestamp())
        self.biz_converge_existed = False
        if self.converge_instance:
            # 如果存在收敛对象的开始时间是介于
            create_timestamp = int(self.converge_instance.create_time.timestamp())
            if self.start_timestamp < create_timestamp:
                self.start_timestamp = self.start_timestamp
        converged_condition = {
            condition_item["dimension"]: self.converge_config["converged_condition"].get(condition_item["dimension"])
            for condition_item in self.converge_config["condition"]
        }

        self.dimension_handler = DimensionHandler(
            self.dimension,
            converged_condition,
            self.start_timestamp,
            instance_id=self.instance.id,
            end_timestamp=self.end_timestamp,
            instance_type=self.instance_type,
            strategy_id=getattr(self.instance, "strategy_id", 0),
            converged_condition=self.converge_config["converged_condition"],
        )

    def do_converge(self):
        """
        收敛计算
        """
        if self.converge_instance:
            # 当前存在同维度的汇总内容，直接返回收敛
            logger.info(
                "%s|converge(%s) skipped because converge(%s) dimension existed already",
                self.instance_type,
                self.instance.id,
                self.converge_instance.id,
            )
            return True

        self.match_alarm_id_list = self.get_related_ids()
        matched_count = len(self.match_alarm_id_list)

        if not self.converge_instance and matched_count >= int(self.converge_config["count"]):
            # create converge_instance record
            logger.info("[create_converge_instance] begin to create converge by %s", self.instance.id)
            try:
                self.create_converge_instance(self.start_time)
            except Exception as error:
                logger.exception(
                    "[create_converge_instance] create converge by instance(%s) failed：%s", self.instance.id, error
                )
                return False

            logger.info(
                "[create_converge_instance] end create converge(%s) by %s ", self.converge_instance.id, self.instance.id
            )

        if not self.converge_instance or matched_count == 0:
            logger.info("$%s no matched_count , return!!", self.instance.id)
            return False

        if (
            self.is_created
            and self.converge_config.get("sub_converge_config")
            and self.converge_config.get("need_biz_converge")
        ):
            # 如果当前收敛事件关联的动作有二级收敛，需要计算维度，并且推送到对应的队列中
            self.push_to_sub_converge_queue()

        return True

    def push_to_sub_converge_queue(self):
        """
        推送二级收敛至收敛队列
        """

        sub_converge_config = self.converge_config.get("sub_converge_config", {})
        sub_converge_config["is_enabled"] = True  # 需要二级收敛的，默认都设置is_enabled为True
        if self.is_biz_converge_existed(sub_converge_config["count"]):
            # 当前已经达到了业务汇总的条件，当前的告警不发出
            self.biz_converge_existed = True

        sub_converge_info = DimensionCalculator(
            self.converge_instance,
            ConvergeType.CONVERGE,
            converge_config=sub_converge_config,
        ).calc_sub_converge_dimension()
        task_id = run_converge.delay(
            sub_converge_config,
            self.converge_instance.id,
            ConvergeType.CONVERGE,
            sub_converge_info["converge_context"],
            alerts=self.alerts,
        )
        logger.info("push converge(%s) to converge queue, task id %s", self.converge_instance.id, task_id)

    def is_biz_converge_existed(self, matched_count):
        client = FTA_SUB_CONVERGE_DIMENSION_LOCK_KEY.client

        # 去除策略ID避免存储被路由到不同的redis
        key_params = self.dimension_handler.get_sub_converge_label_info()
        key_params.pop("strategy_id", None)

        biz_converge_lock_key = FTA_SUB_CONVERGE_DIMENSION_LOCK_KEY.get_key(**key_params)
        if client.incr(biz_converge_lock_key) > matched_count:
            # 如果当前的计数器大于并发数，直接返回异常
            logger.info(
                "action(%s|%s) will be skipped because count of biz_converge_lock_key(%s) is bigger than %s, ",
                self.instance.id,
                self.converge_instance.id,
                biz_converge_lock_key,
                matched_count,
            )
            return True
        client.expire(biz_converge_lock_key, FTA_SUB_CONVERGE_DIMENSION_LOCK_KEY.ttl)
        return False

    def get_related_ids(self):
        """
        获取到当前收敛对象相关的处理动作
        """

        matched_related_ids = self.dimension_handler.get_by_condition()

        # 仅获取同一种收敛事件的id
        matched_related_ids = [
            int(related_id.split("_")[-1]) for related_id in matched_related_ids if self.instance_type in related_id
        ]

        if not matched_related_ids:
            return []

        converge_relations = ConvergeRelation.objects.filter(
            related_id__in=matched_related_ids, related_type=self.instance_type
        )
        if self.converge_instance:
            # 最后计算出来的匹配的，必须是当前收敛的对象中的关联ID或者未关联的
            converge_relations = converge_relations.exclude(converge_id=self.converge_instance.id)

        converged_related_ids = converge_relations.values_list("related_id", flat=True)

        matched_related_ids = list(set(matched_related_ids) - set(converged_related_ids))
        logger.info(
            "$%s:%s dimension alarm list: %s, %s",
            self.instance.id,
            self.instance_type,
            self.dimension,
            len(matched_related_ids),
        )
        return matched_related_ids

    def create_converge_instance(self, start_time=None):
        self.insert_converge_instance()
        if start_time and self.converge_instance.create_time < start_time:
            logger.info(
                "converge(%s) end by start_time (%s < %s)",
                self.converge_instance.id,
                self.converge_instance.create_time,
                start_time,
            )
            self.end_converge_by_id(self.converge_instance.id)

        return self.converge_instance

    @classmethod
    def get_fixed_dimension(cls, dimension):
        return f"{dimension} fixed at {int(datetime.now().timestamp())} {random.randint(100, 999)}"

    @classmethod
    def end_converge_by_id(cls, converge_id, conv_instance=None):
        logger.info("conv_instance end by id %s", converge_id)
        if conv_instance is None:
            conv_instance = ConvergeInstance.objects.get(id=converge_id)
        if conv_instance and not conv_instance.end_time:
            conv_instance.end_time = datetime.now(tz=timezone.utc)
            conv_instance.dimension = cls.get_fixed_dimension(conv_instance.dimension)
            conv_instance.save(update_fields=["end_time", "dimension"])
        if conv_instance.converge_type == ConvergeType.CONVERGE:
            # 如果是多级收敛，需要关闭掉其他的收敛
            for conv_id in ConvergeRelation.objects.filter(converge_id=converge_id).values_list(
                "related_id", flat=True
            ):
                cls.end_converge_by_id(conv_id)
        logger.info("converge(%s) already end at %s", converge_id, conv_instance.end_time)

    def insert_converge_instance(self):
        try:
            converged_condition_display = []
            for converged_condition_key in self.converge_config["converged_condition"]:
                if converged_condition_key == "action_id":
                    continue
                converged_condition_display.append(
                    str(ALL_CONVERGE_DIMENSION.get(converged_condition_key, converged_condition_key))
                )

            description = _("在{}分钟内，当具有相同{}的告警超过{}条以上，在执行相同的处理套餐时，进行告警防御").format(
                self.converge_config["timedelta"] // 60,
                ",".join(converged_condition_display),
                self.converge_config["count"],
            )

            self.converge_instance = ConvergeInstance.objects.create(
                converge_config=self.converge_config,
                bk_biz_id=self.instance.bk_biz_id,
                dimension=self.dimension,
                description=description,
                content=self.converge_config.get("context", "{}"),
                end_time=None,
                converge_func=self.converge_config["converge_func"],
                converge_type=self.instance_type,
                is_visible=True,
            )
        except BaseException as error:
            logger.error("[create converge] insert_converge_instance error %s", str(error))
            self.is_created = False
            self.converge_instance = self.get_converge_instance()

        else:
            self.is_created = True

    def get_converge_instance(self, start_time=None):
        try:
            converge_instance = ConvergeInstance.objects.filter(dimension=self.dimension).first()
        except Exception:
            converge_instance = None
        if converge_instance and start_time and converge_instance.create_time < start_time:
            # 如果存在收敛并且不在当前收敛期的，直接关闭
            logger.info(
                "[do_converge] converge(%s) end by start_time (%s < %s)",
                converge_instance.id,
                converge_instance.create_time,
                start_time,
            )
            self.end_converge_by_id(converge_instance.id)
            converge_instance = None
        self.converge_instance = converge_instance
        return self.converge_instance

    def connect_converge(self, status=ConvergeStatus.SKIPPED):
        """关联告警"""
        try:
            # 判断当前实例是否为主要实例：如果是新创建的收敛实例则为主要实例，否则为关联实例
            is_primary = True if self.is_created else False
            if is_primary:
                converge_status = ConvergeStatus.EXECUTED
            else:
                converge_status = ConvergeStatus.SKIPPED if status else ConvergeStatus.EXECUTED

            ConvergeRelation.objects.create(
                related_id=self.instance.id,
                converge_id=self.converge_instance.id,
                related_type=self.instance_type,
                is_primary=is_primary,
                converge_status=converge_status,
                alerts=getattr(self.instance, "alerts", []),
            )
        except BaseException as error:
            # 创建失败的原因，是由于已经关联过
            logger.info("create converge relation record failed %s, is_created: %s", str(error), self.is_created)
            return

        if self.is_created and self.match_alarm_id_list:
            """ "统计恢复"""
            other_converged_instances = list_other_converged_instances(
                self.match_alarm_id_list, self.instance, self.instance_type
            )
            if self.instance_type == ConvergeType.ACTION:
                other_converged_instances = (
                    ActionInstance.objects.filter(id__in=self.match_alarm_id_list)
                    .exclude(status__in=[ActionStatus.RECEIVED, ActionStatus.SLEEP, ActionStatus.WAITING])
                    .exclude(id=self.instance.id)
                )

            if other_converged_instances.exists():
                ConvergeRelationManager.connect(
                    self.converge_instance.id,
                    set(other_converged_instances.values_list("id", flat=True)),
                    self.instance_type,
                    self.instance.id,
                    converge_status=ConvergeStatus.SKIPPED
                    if self.instance_type == ConvergeType.CONVERGE
                    else ConvergeStatus.EXECUTED,
                )
                if self.instance_type == ConvergeType.CONVERGE:
                    # 当时二级收敛的时候，需要抑制一级收敛
                    other_converged_instances.update(is_visible=False)

        if self.instance_type == ConvergeType.CONVERGE:
            self.instance.is_visible = False
            self.instance.save(update_fields=["is_visible"])

        description = self.converge_config.get("description")
        if not description or description == self.converge_instance.description:
            return

        ConvergeInstance.objects.filter(id=self.converge_instance.id).update(description=description)


class ConvergeRelationManager:
    @staticmethod
    def count(converge_id):
        return ConvergeRelation.objects.filter_by(converge_id=converge_id).count()

    @staticmethod
    def index(converge_id, relate_id):
        related_ids = list(ConvergeRelation.objects.filter(converge_id=converge_id).values_list("relate_id", flat=True))
        return related_ids.index(relate_id)

    @staticmethod
    def connect(converge_id, related_ids, related_type, instance_id, converge_status=ConvergeStatus.SKIPPED):
        """关联收敛关系"""
        try:
            ConvergeRelationManager._connect(converge_id, related_ids, related_type, instance_id, converge_status)
        except BaseException:
            time.sleep(random.randint(1, 100) / 100.0)
            ConvergeRelationManager._connect(converge_id, related_ids, related_type, instance_id, converge_status)

    @staticmethod
    def _connect(
        converge_id,
        related_ids,
        related_type=ConvergeType.ACTION,
        instance_id=None,
        converge_status=ConvergeStatus.SKIPPED,
    ):
        """
        因为必定有很多重复记录，需要使用mysql IGNORE特性
        """
        converge_relations = [
            ConvergeRelation(
                converge_id=converge_id,
                related_id=related_id,
                related_type=related_type,
                converge_status=converge_status,
            )
            for related_id in related_ids
        ]
        ConvergeRelation.objects.ignore_blur_create(converge_relations)

        logger.info("converge(%s) connect: instance_id(%s) len(%s)", converge_id, instance_id, len(related_ids))
