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


import logging

from django.conf import settings

from alarm_backends import constants
from alarm_backends.core.cache.strategy import StrategyCacheManager
from alarm_backends.core.cluster import filter_bk_biz_ids
from alarm_backends.management.base.base import ConsulDispatchCommand
from alarm_backends.management.base.loaders import load_handler_cls
from bkmonitor import models

logger = logging.getLogger(__name__)


class Command(ConsulDispatchCommand):
    """
    Access Command
    """

    _SERVICE_TYPE_ = ""  # access/detect/trigger/event/action/recovery .etc
    _HANDLER_TYPE_ = ""  # process/celery
    _ACCESS_TYPE_ = ""  # data/real_time_data/gse_event/custom_event/alert
    _HASH_RING_ = 0

    def add_arguments(self, parser):
        super(Command, self).add_arguments(parser)
        parser.add_argument(
            "--hash-ring", choices=["0", "1"], default="0", help="Whether to apply hash ring allocation"
        )
        parser.add_argument(
            "-s",
            "--service-type",
            help="Which service to run.",
        )
        parser.add_argument(
            "-H",
            "--handler-type",
            default="process",
            choices=["process", "celery"],
            help="Which handler does the process use?",
        )
        parser.add_argument("--access-type", choices=["data", "real_time_data", "event", "alert", "incident"])

    # status
    __COMMAND_NAME__ = __name__.split(".")[-1]

    def __init__(self, *args, **kwargs):
        super(Command, self).__init__(*args, **kwargs)
        self.path_prefix = self._PATH_PREFIX_

    def on_start(self, *args, **kwargs):
        self._PATH_PREFIX_ = f"{self.path_prefix}-{self._ACCESS_TYPE_}"
        try:
            handler_cls = load_handler_cls(self._SERVICE_TYPE_, self._HANDLER_TYPE_)
        except Exception:  # noqa
            logger.exception(
                "Error loading Handler, service_type({}),"
                " handler_type({})".format(self._SERVICE_TYPE_, self._HANDLER_TYPE_)
            )
            raise
        else:
            try:
                logger.info(
                    "Starting..."
                    "service({})-handle({})-hash_ring({})-".format(
                        self._SERVICE_TYPE_, self._HANDLER_TYPE_, bool(int(self._HASH_RING_))
                    )
                )
                if int(self._HASH_RING_):
                    if settings.ENVIRONMENT == constants.CONST_DEV:
                        instance_targets = self.query_instance_targets(self.query_host_targets())
                    else:
                        host_targets, instance_targets = self.dispatch()

                    # 最多打100个
                    logger.info("^use targets(%s)...", instance_targets[:100])
                    handler = handler_cls(instance_targets, access_type=self._ACCESS_TYPE_, service=self)
                else:
                    handler = handler_cls(access_type=self._ACCESS_TYPE_, *args, **kwargs)

                handler.handle()
            except Exception:  # noqa
                logger.exception(
                    "Error executing Handler, service_type({}), "
                    "handler_type({})".format(self._SERVICE_TYPE_, self._HANDLER_TYPE_)
                )

    def query_instance_targets(self, host_targets):
        time_series_strategy_ids = StrategyCacheManager.get_time_series_strategy_ids()
        qs = models.StrategyModel.objects.filter(bk_biz_id__in=host_targets, is_enabled=True).values_list(
            "pk", flat=True
        )
        return [val for val in qs if val in time_series_strategy_ids]

    def query_host_targets(self):
        data = StrategyCacheManager.get_all_bk_biz_ids()
        data.extend(settings.BKMONITOR_WORKER_INCLUDE_LIST)
        data = list(set(filter_bk_biz_ids(data)))
        data.sort()

        return data
