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


import abc
import logging
from typing import Dict, List

import arrow
from django.conf import settings
from django.utils.functional import cached_property

from bkmonitor.dataflow.constant import get_aiops_env_bkdata_biz_id
from bkmonitor.dataflow.node.base import Node
from constants.aiops import MULTIVARIATE_ANOMALY_DETECTION_SCENE_INPUT_FIELD
from core.drf_resource import api
from monitor_web.aiops.metric_recommend.constant import (
    METRIC_RECOMMAND_SCENE_SERVICE_TEMPLATE,
)

logger = logging.getLogger("bkmonitor.dataflow")


class MachineLearnNode(Node, abc.ABC):
    pass


class SceneServiceNode(MachineLearnNode):
    """
    场景服务节点
    """

    NODE_TYPE = "scenario_app"
    DEFAULT_TIME_FIELD = "timestamp"

    def __init__(
        self,
        scene_id: int,
        plan_id: int,
        source_rt_id: str,
        metric_field: str,
        agg_dimensions: List[str],
        time_field: str = None,
        plan_args: Dict = None,
        *args,
        **kwargs,
    ):
        self.source_rt_id = source_rt_id
        self.bk_biz_id, _, self.process_rt_id = source_rt_id.partition("_")
        self.bk_biz_id = int(self.bk_biz_id)
        self.metric_field = metric_field
        self.time_field = time_field or self.DEFAULT_TIME_FIELD
        self.agg_dimensions = agg_dimensions
        self.scene_id = scene_id
        self.plan_id = plan_id
        self.plan_args = plan_args

        super(SceneServiceNode, self).__init__(*args, **kwargs)

    def __eq__(self, other):
        if isinstance(other, dict):
            config = self.config
            if (
                config["from_result_table_ids"] == other["from_result_table_ids"]
                and config["table_name"] == other["table_name"]
                and config["bk_biz_id"] == other["bk_biz_id"]
                and config["dedicated_config"]["plan_id"] == other["dedicated_config"]["plan_id"]
            ):
                return True
        elif isinstance(other, self.__class__):
            return self == other.config
        return False

    @property
    def name(self):
        return self.plan_info["plan_alias"]

    @property
    def table_name(self):
        """
        输出表名（不带业务ID前缀）
        """
        name = f"{self.process_rt_id}_{self.plan_id}"[-50:]
        while not name[0].isalpha():
            # 保证首字符是英文
            name = name[1:]
        return name

    @property
    def output_table_name(self):
        """
        输出表名（带上业务ID前缀）
        """
        return f"{self.bk_biz_id}_{self.table_name}"

    @property
    def variable_config(self):
        if not self.plan_args:
            return []

        config = [
            {"variable_value": value, "variable_name": name, "variable_type": "parameter"}
            for name, value in self.plan_args.items()
        ]
        return config

    @cached_property
    def plan_info(self):
        return api.bkdata.get_scene_service_plan(plan_id=self.plan_id)

    @property
    def config(self):
        mapping = {
            field: {
                "input_field_name": field,
            }
            for field in self.agg_dimensions
        }
        mapping.update(
            {
                "timestamp": {
                    "input_field_name": self.time_field,
                },
                "value": {
                    "input_field_name": self.metric_field,
                },
            }
        )

        try:
            input_field_name = list(list(self.plan_info["io_info"]["entry_require_mapping"].values())[0].keys())[0]
        except Exception:  # pylint: disable=broad-except
            input_field_name = "model_input_1"

        return {
            "name": self.name,
            "table_name": self.table_name,
            "output_name": self.table_name,
            "bk_biz_id": self.bk_biz_id,
            "result_table_id": f"{self.bk_biz_id}_{self.table_name}",
            "serving_mode": "realtime",
            "from_result_table_ids": [self.source_rt_id],
            "window_info": {},
            "inputs": self.generate_scene_plan_inputs(),
            "outputs": self.generate_scene_plan_outputs(),
            "dedicated_config": {
                "scene_id": self.scene_id,
                "plan_id": self.plan_id,
                "plan_version_id": self.plan_info["latest_plan_version_id"],
                "project_id": settings.BK_DATA_PROJECT_ID,
                "flow_id": 0,  # 创建时填充
                "input_mapping": {
                    input_field_name: {
                        "has_group": bool(self.agg_dimensions),
                        "group_dimension": self.agg_dimensions,
                        "mapping": mapping,
                        "input_dataset_id": self.source_rt_id,
                    }
                },
                "variable_config": self.variable_config,
            },
        }

    def get_api_params(self, flow_id):
        params = super(SceneServiceNode, self).get_api_params(flow_id)
        params["config"]["dedicated_config"]["flow_id"] = flow_id
        return params

    def need_update(self, other_config):
        config = self.config
        for field in ["plan_id", "input_mapping", "variable_config"]:
            if config["dedicated_config"][field] != other_config.get("dedicated_config", {}).get(field):
                return True
        return False

    def generate_scene_plan_inputs(self):
        """根据方案详情生成输入配置.

        :param plan_info: 方案详情
        """
        return [{}]

    def generate_scene_plan_outputs(self):
        """根据方案详情生成输出配置.

        :param plan_info: 方案详情
        """
        return [{}]


# 由于多指标异常检测算法的输入字段不再是value，所以需要继承重写一个
class MultivariateAnomalySceneServiceNode(SceneServiceNode):
    @property
    def config(self):
        config = super(MultivariateAnomalySceneServiceNode, self).config

        mapping = {
            field: {
                "input_field_name": field,
            }
            for field in self.agg_dimensions
        }
        mapping.update(
            {
                "timestamp": {
                    "input_field_name": self.time_field,
                },
                MULTIVARIATE_ANOMALY_DETECTION_SCENE_INPUT_FIELD: {
                    "input_field_name": self.metric_field,
                },
            }
        )

        for input in config["dedicated_config"]["input_mapping"].values():
            input["mapping"] = mapping

        return config


class SimilarMetricClusteringServiceNode(SceneServiceNode):
    def __init__(self, access_bk_biz_id, *args, **kwargs):
        self.access_bk_biz_id = access_bk_biz_id
        kwargs.update({"metric_field": "", "agg_dimensions": []})
        super().__init__(*args, **kwargs)

    @property
    def name(self):
        return METRIC_RECOMMAND_SCENE_SERVICE_TEMPLATE(bk_biz_id=self.access_bk_biz_id)

    @property
    def table_name(self):
        """
        输出表名（不带业务ID前缀）
        """
        return METRIC_RECOMMAND_SCENE_SERVICE_TEMPLATE(bk_biz_id=self.access_bk_biz_id)

    @property
    def output_table_name(self):
        """
        输出表名（带上业务ID前缀）
        """
        return f"{self.bk_biz_id}_{self.table_name}"

    @property
    def config(self):
        from monitor_web.aiops.metric_recommend.constant import (
            METRIC_RECOMMAND_INPUT_MAPPINGS,
        )

        config = super(SimilarMetricClusteringServiceNode, self).config

        mapping = {
            field: {
                "input_field_name": field,
            }
            for field in self.agg_dimensions
        }

        input_field_mapping = {}

        for input_field_src, input_field_target in METRIC_RECOMMAND_INPUT_MAPPINGS.items():
            input_field_mapping[input_field_src] = {"input_field_name": input_field_target}

        mapping.update(
            {
                "timestamp": {
                    "input_field_name": self.time_field,
                },
                **input_field_mapping,
            }
        )

        for input in config["dedicated_config"]["input_mapping"].values():
            input["mapping"] = mapping

        config["output_name"] = self.output_table_name
        config["serving_mode"] = "offline"
        config["dedicated_config"].update(
            {
                "schedule_config": {
                    "schedule_period": "day",
                    "count_freq": "1",
                    "start_time": arrow.now().format('YYYY-MM-DD 00:00:00'),
                },
                "window_info": {
                    "window_type": "scroll",
                },
            }
        )
        return config

    def generate_scene_plan_outputs(self):
        """根据方案详情生成输出配置.

        :param plan_info: 方案详情
        """
        output_configs = self.plan_info["io_info"]["output_config"]

        return [
            {
                "bk_biz_id": self.bk_biz_id,
                "common_fields": output.get("fields", []),
                "data_type": output["data_type"],
                "dataset_alias": output["dataset_alias"],
                "dataset_name": output["dataset_name"],
                "display_name": output["dataset_name"],
                "extra_fields": [],
                "__is_mask": True,
            }
            for output in output_configs
        ]


class ModelApiServingNode(MachineLearnNode):
    """模型API节点"""

    NODE_TYPE = "model_api_serving"
    NODE_NAME_KEY = "api_serving"
    EXCLUDE_UPDATE_FIELD = ["resource_config"]

    def __init__(
        self,
        access_bk_biz_id,
        model_release_id,
        input_node,
        predict_args,
        app_name_key_word,
        node_type="api_serving",
        scene_name="custom",
        *args,
        **kwargs,
    ):
        super(ModelApiServingNode, self).__init__(*args, **kwargs)
        self.access_bk_biz_id = access_bk_biz_id
        self.model_release_id = model_release_id
        self.input_node = input_node
        self.predict_args = predict_args
        self.app_name_key_word = app_name_key_word
        self.node_type = node_type
        self.scene_name = scene_name

    def fetch_model_config(self):
        return api.bkdata.get_release_model_info(model_release_id=self.model_release_id, node_type=self.node_type)

    def __eq__(self, other):
        if isinstance(other, dict):
            config = self.config
            if config.get("table_name") == other.get("table_name") and config.get("bk_biz_id") == other.get(
                "bk_biz_id"
            ):
                return True
        elif isinstance(other, self.__class__):
            return self == other.config
        return False

    def need_update(self, other_config):
        for k, v in self.config.items():
            if k in self.EXCLUDE_UPDATE_FIELD:
                continue

            if v != other_config.get(k):
                return True
        return False

    @property
    def name(self):
        return self.app_name

    @property
    def table_name(self):
        return f"{self.app_name_key_word}_{self.access_bk_biz_id}"

    @property
    def app_name(self):
        return self.table_name

    @property
    def config(self):
        model_config = self.fetch_model_config()
        model_config_template = model_config["model_config_template"]

        input_config_params = model_config_template["input"]["input_node"][0]["input_config"]
        input_config_params["add_on_input"][0]["result_table_name"] = self.input_node.output_table_name
        input_config_params["add_on_input"][0]["result_table_name_alias"] = self.input_node.output_table_name
        input_config_params["add_on_input"][0]["value"] = self.input_node.output_table_name

        input_config = {"input_node": input_config_params}

        output_config_params = model_config_template["output"]["output_node"][0]["output_config"]
        output_config_params["table_alias"] = self.table_name
        output_config_params["table_name"] = self.table_name

        output_config = {"output_node": model_config_template["output"]["output_node"][0]["output_config"]}

        schedule_config = {
            "serving_scheduler_params": model_config_template["serving_scheduler_params"],
            "training_scheduler_params": model_config_template["training_scheduler_params"],
        }

        resource_config = {"service": model_config["resource_config"]["spark_executor"]}

        predict_args = model_config_template["model_extra_config"]["predict_args"]

        for predict_arg in predict_args:
            if self.predict_args.get(predict_arg["field_name"]):
                predict_arg["value"] = self.predict_args.get(predict_arg["field_name"])
        model_extra_config = {"predict_args": predict_args}

        upgrade_config = {
            "notification": False,
            "auto_upgrade": True,
            "specific_update_config": {"specific_update": False, "update_time": "00:00:00"},
        }

        config = {
            "app_name": self.app_name,
            "bk_biz_id": get_aiops_env_bkdata_biz_id(),
            "model_id": model_config["model_id"],
            "model_release_id": self.model_release_id,
            "name": self.name,
            "run_env": "",
            "scene_name": self.scene_name,
            "serving_mode": "api",
            "table_name": self.table_name,
            "input_config": input_config,
            "output_config": output_config,
            "schedule_config": schedule_config,
            "resource_config": resource_config,
            "model_extra_config": model_extra_config,
            "upgrade_config": upgrade_config,
        }
        return config
