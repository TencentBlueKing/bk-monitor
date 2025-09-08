# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
import json
import logging
import traceback

from django.conf import settings
from django.core.management.base import BaseCommand

from constants.common import DEFAULT_TENANT_ID
from metadata.models import (
    DataSource,
    DataSourceOption,
    ResultTableOption,
    TimeSeriesGroup,
    TimeSeriesMetric,
)
from metadata.utils import consul_tools
from monitor_web.commons.data_access import PluginDataAccessor
from monitor_web.models import CollectorPluginMeta

logger = logging.getLogger("metadata")


class Command(BaseCommand):
    DATA_SOURCE_OPTION_TEMPLATE = {
        "allow_dimensions_missing": 'true',
        "is_split_measurement": 'true',
        "disable_metric_cutter": 'true',
    }

    BLACKLIST_MUST_FIELD = "metrics_report_path"
    TABLE_OPTION_TEMPLATE = {
        "enable_default_value": 'false',
        "is_split_measurement": 'true',
    }

    DUI = "[\033[32m√\033[0m] "
    CUO = "[\033[31mx\033[0m] "

    @classmethod
    def mark(cls, msg, ok=True):
        if ok:
            return f"\n{cls.DUI}{msg}"
        else:
            return f"\n{cls.CUO}{msg}"

    @staticmethod
    def description(msg):
        return "- Description: " + msg

    @staticmethod
    def fail(msg):
        return msg + "\nScript escape"

    def judge_option_data(self, data, template_data, enable_field_blacklist=False):
        correct_flag = True
        result = ""
        for option_key, option_value in template_data.items():
            if option_key not in data:
                result += f"\n\t{self.CUO}{option_key}: 该字段不存在[{option_key}为必需项]"
                correct_flag = False
                continue
            actual_option_value = data.pop(option_key)
            if isinstance(actual_option_value, bool):
                actual_option_value = str(actual_option_value).lower()
            if actual_option_value != option_value:
                result += f"\n\t{self.CUO}{option_key}: {actual_option_value} 该字段值应该是{option_value}"
                correct_flag = False
                continue
            result += f"\n\t{self.DUI}{option_key}: {option_value}"
        for key, value in data.items():
            if key == "enable_field_black_list":
                if str(value).lower() != str(enable_field_blacklist).lower():
                    result += f"\n\t{self.CUO}{key}: {value}"
                    correct_flag = False
                    continue
            result += f"\n\t{self.DUI}{key}: {str(value).lower()}"
        return result, correct_flag

    def handle(self, *args, **options):
        plugin_id = options["plugin_id"]
        bk_tenant_id = options["bk_tenant_id"]
        if settings.ROLE != "api":
            print(f"try with: ./bin/api_manage.sh check_plugin_status --plugin_id={plugin_id}")
            return
        # 获取 plugin 信息
        try:
            plugin = CollectorPluginMeta.objects.get(plugin_id=plugin_id, bk_tenant_id=bk_tenant_id)
        except CollectorPluginMeta.DoesNotExist:
            print(f"can not find plugin, plugin_id:{plugin_id}")
            return

        plugin_data_info = PluginDataAccessor(plugin.current_version, operator=None)
        # 0. 插件的基本信息
        print("==============================================")
        print("==================插件基本信息==================")
        print(self.description(f"插件 ID 为：{plugin_id}"))
        print(self.description(f"插件类型为：{plugin.plugin_type}"))
        print(self.description(f"插件关联 data id 为：{plugin_data_info.data_id}"))
        try:
            ts = TimeSeriesGroup.objects.get(time_series_group_name=f"{plugin.plugin_type}_{plugin.plugin_id}".lower())
            print(self.description("Time series group 基本信息: "))
            print(f"\ttime series group name: {ts.time_series_group_name}")
            print(f"\ttime series group id: {ts.time_series_group_id}")
            ts_metrics = TimeSeriesMetric.objects.filter(group_id=ts.time_series_group_id).values_list(
                "field_name", flat=True
            )
            print(f"\ttime series metrics: {list(ts_metrics)}")
        except TimeSeriesGroup.DoesNotExist:
            print(self.fail("无法获取Time series group 相关信息，请确认该插件是否为单指标单表类型插件"))
            return
        print("==============================================")
        # 1. 确认当前是否开启自动发现
        check_db_data_msg = "Check data from database"
        db_result = ""
        try:
            enable_field_blacklist = plugin.current_version.info.enable_field_blacklist
            db_result += "\n" + self.description(f"插件是否开启自动发现: {str(enable_field_blacklist).lower()}")
            db_result += "\n" + self.description("datasourceoption 相关信息:")
            # data source 部分
            data_source_data = dict(
                DataSourceOption.objects.filter(bk_data_id=plugin_data_info.data_id).values_list("name", "value")
            )
            db_ds_option_result, db_ds_correct_flag = self.judge_option_data(
                data_source_data, self.DATA_SOURCE_OPTION_TEMPLATE, enable_field_blacklist
            )
            db_result += db_ds_option_result
            if enable_field_blacklist:
                if self.BLACKLIST_MUST_FIELD not in data_source_data:
                    db_ds_correct_flag = False
                    db_result += (
                        f"\n\t{self.CUO}{self.BLACKLIST_MUST_FIELD}: 该字段不存在[在自动发现下，{self.BLACKLIST_MUST_FIELD}为必需项]"
                    )
            db_result += "\n" + self.description("resulttableoption 相关信息:")
            rt_data = dict(ResultTableOption.objects.filter(table_id=ts.table_id).values_list("name", "value"))
            db_rt_option_result, db_rt_correct_flag = self.judge_option_data(
                rt_data, self.TABLE_OPTION_TEMPLATE, enable_field_blacklist
            )
            db_result += db_rt_option_result
            print(self.mark(check_db_data_msg, ok=all([db_ds_correct_flag, db_rt_correct_flag])) + db_result)
        except Exception:
            error_string = traceback.format_exc()
            print(self.mark(check_db_data_msg, False) + db_result)
            print(self.fail(f"get database data failed, the reason is: \n{error_string}"))
            return
        print("==============================================")
        # 2. 检查consul 中黑名单 option
        check_consul_option_msg = "Check data from consul"
        consul_result = ""
        try:
            hash_consul = consul_tools.HashConsul()
            consul_raw_data = hash_consul.get(
                key=DataSource.objects.get(bk_data_id=plugin_data_info.data_id).consul_config_path
            )
            consul_data = json.loads(consul_raw_data[1]["Value"])
            consul_enable_field_blacklist = consul_data["result_table_list"][0]["option"]["enable_field_black_list"]
            black_status_correct_flag = True
            if consul_enable_field_blacklist == enable_field_blacklist:
                check_black_status = f" {self.DUI}"
            else:
                black_status_correct_flag = False
                check_black_status = f" {self.CUO}consul 数据与用户设置不一致，请排查 ResultTableOption 内数据"
            consul_result += "\n" + self.description(
                f"consul 数据中是否开启自动发现: {str(consul_enable_field_blacklist).lower()}{check_black_status}"
            )
            consul_result += "\n" + self.description("datasourceoption 相关信息:")
            consul_ds_option_result, consul_ds_correct_flag = self.judge_option_data(
                consul_data["option"], self.DATA_SOURCE_OPTION_TEMPLATE, consul_enable_field_blacklist
            )
            consul_result += consul_ds_option_result
            if enable_field_blacklist:
                if self.BLACKLIST_MUST_FIELD not in consul_data["option"]:
                    consul_ds_correct_flag = False
                    print(f"\t{self.CUO}{self.BLACKLIST_MUST_FIELD}: 该字段不存在[在自动发现下，{self.BLACKLIST_MUST_FIELD}为必需项]")

            consul_result += "\n" + self.description("resulttableoption 相关信息:")
            consul_rt_option_result, consul_rt_correct_flag = self.judge_option_data(
                consul_data["result_table_list"][0]["option"], self.TABLE_OPTION_TEMPLATE, enable_field_blacklist
            )
            consul_result += consul_rt_option_result
            metric_list = []
            for table in consul_data["result_table_list"]:
                for field in table["field_list"]:
                    if field["tag"] == "metric":
                        metric_list.append(field["field_name"])
            consul_result += "\n" + self.description(f"consul 中的指标信息: {metric_list}")
            print(
                self.mark(
                    check_consul_option_msg,
                    all([consul_ds_correct_flag, consul_rt_correct_flag, black_status_correct_flag]),
                )
                + consul_result
            )
        except Exception:
            error_string = traceback.format_exc()
            print(self.mark(check_consul_option_msg, False) + db_result)
            print(self.fail(f"get consul config failed, the reason is: \n{error_string}"))
            return
        # 3. 检查 redis 是否有数据
        print("==============================================")
        check_redis_metric_msg = "Check redis metric data"
        if not enable_field_blacklist or not consul_enable_field_blacklist:
            print(self.mark(check_redis_metric_msg, False))
            print(
                self.fail("Auto-discovery is not enabled or the plugin is inconsistent with the consul configuration")
            )
            return
        try:
            redis_data = ts.get_metrics_from_redis()
            print(self.mark(check_redis_metric_msg))
            print(self.description(f"redis data: \n{json.dumps(redis_data)}"))
        except Exception:
            error_string = traceback.format_exc()
            print(self.mark(check_redis_metric_msg, False))
            print(self.fail(f"get redis metric data failed, the reason is: \n{error_string}"))
            return

    def add_arguments(self, parser):
        parser.add_argument("--bk_tenant_id", type=str, default=DEFAULT_TENANT_ID, help="租户 ID")
        parser.add_argument("--plugin_id", type=str, required=True, help="插件 ID")
