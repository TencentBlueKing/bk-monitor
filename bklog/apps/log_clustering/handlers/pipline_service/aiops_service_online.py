# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
License for BK-LOG 蓝鲸日志平台:
--------------------------------------------------------------------
Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all copies or substantial
portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN
NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
We undertake not to change the open source license (MIT license) applicable to the current version of
the project delivered to anyone in the future.
"""
import arrow
from pipeline.builder import Data, EmptyEndEvent, EmptyStartEvent, Var, build_tree
from pipeline.parser import PipelineParser

from apps.feature_toggle.handlers.toggle import FeatureToggleObject
from apps.feature_toggle.plugins.constants import BKDATA_CLUSTERING_TOGGLE
from apps.log_clustering.components.collections.data_access_component import (
    AddProjectData,
    AddResourceGroupSet,
    CreateBkdataDataId,
    SyncBkdataEtl,
)
from apps.log_clustering.components.collections.flow_component import (
    CreateLogCountAggregationFlow,
    CreatePredictFlow,
    CreateStrategy,
    UpdateClusteringField,
    UpdateFilterRules,
    UpdateOnlineModel,
)
from apps.log_clustering.handlers.pipline_service.base_pipline_service import (
    BasePipeLineService,
)
from apps.log_clustering.handlers.pipline_service.constants import OperatorServiceEnum
from apps.log_clustering.models import ClusteringConfig


class AiopsLogOnlineService(BasePipeLineService):
    """采集项 在线训练服务"""

    def build_data_context(self, params, *args, **kwargs) -> Data:
        data_context = Data()
        data_context.inputs["${description}"] = Var(type=Var.PLAIN, value=params["description"])
        data_context.inputs["${model_name}"] = Var(type=Var.PLAIN, value=params["model_name"])
        data_context.inputs["${min_members}"] = Var(type=Var.PLAIN, value=params["min_members"])
        data_context.inputs["${max_dist_list}"] = Var(type=Var.PLAIN, value=params["max_dist_list"])
        data_context.inputs["${predefined_varibles}"] = Var(type=Var.PLAIN, value=params["predefined_varibles"])
        data_context.inputs["${delimeter}"] = Var(type=Var.PLAIN, value=params["delimeter"])
        data_context.inputs["${max_log_length}"] = Var(type=Var.PLAIN, value=params["max_log_length"])
        data_context.inputs["${is_case_sensitive}"] = Var(type=Var.PLAIN, value=params["is_case_sensitive"])
        data_context.inputs["${project_id}"] = Var(type=Var.PLAIN, value=params["project_id"])
        data_context.inputs["${bk_biz_id}"] = Var(type=Var.PLAIN, value=params["bk_biz_id"])
        data_context.inputs["${index_set_id}"] = Var(type=Var.PLAIN, value=params["index_set_id"])
        data_context.inputs["${collector_config_id}"] = Var(type=Var.PLAIN, value=params["collector_config_id"])

        return data_context

    def build_pipeline(self, data_context: Data, *args, **kwargs):
        start = EmptyStartEvent()
        end = EmptyEndEvent()
        collector_config_id = kwargs.get("collector_config_id")
        index_set_id = kwargs.get("index_set_id")
        start.extend(
            CreateBkdataDataId(index_set_id=index_set_id, collector_config_id=collector_config_id).create_bkdata_data_id
        ).extend(
            SyncBkdataEtl(index_set_id=index_set_id, collector_config_id=collector_config_id).sync_bkdata_etl
        ).extend(
            AddProjectData(index_set_id=index_set_id, collector_config_id=collector_config_id).add_project_data
        ).extend(
            CreatePredictFlow(index_set_id=index_set_id, collector_config_id=collector_config_id).create_predict_flow
        ).extend(
            # 创建日志数量聚合 dataflow
            CreateLogCountAggregationFlow(index_set_id=index_set_id).create_log_count_aggregation_flow
        ).extend(
            CreateStrategy(index_set_id=index_set_id).create_strategy
        ).extend(
            end
        )
        tree = build_tree(start, data=data_context)
        parser = PipelineParser(pipeline_tree=tree)
        pipeline = parser.parse()
        return pipeline


class AiopsBkdataOnlineService(BasePipeLineService):
    """计算平台 在线训练服务"""

    def build_data_context(self, params, *args, **kwargs) -> Data:
        data_context = Data()
        data_context.inputs["${description}"] = Var(type=Var.PLAIN, value=params["description"])
        data_context.inputs["${model_name}"] = Var(type=Var.PLAIN, value=params["model_name"])
        data_context.inputs["${min_members}"] = Var(type=Var.PLAIN, value=params["min_members"])
        data_context.inputs["${max_dist_list}"] = Var(type=Var.PLAIN, value=params["max_dist_list"])
        data_context.inputs["${predefined_varibles}"] = Var(type=Var.PLAIN, value=params["predefined_varibles"])
        data_context.inputs["${delimeter}"] = Var(type=Var.PLAIN, value=params["delimeter"])
        data_context.inputs["${max_log_length}"] = Var(type=Var.PLAIN, value=params["max_log_length"])
        data_context.inputs["${is_case_sensitive}"] = Var(type=Var.PLAIN, value=params["is_case_sensitive"])
        data_context.inputs["${project_id}"] = Var(type=Var.PLAIN, value=params["project_id"])
        data_context.inputs["${bk_biz_id}"] = Var(type=Var.PLAIN, value=params["bk_biz_id"])
        data_context.inputs["${index_set_id}"] = Var(type=Var.PLAIN, value=params["index_set_id"])
        data_context.inputs["${collector_config_id}"] = Var(type=Var.PLAIN, value=params["collector_config_id"])

        return data_context

    def build_pipeline(self, data_context: Data, *args, **kwargs):
        start = EmptyStartEvent()
        end = EmptyEndEvent()
        index_set_id = kwargs.get("index_set_id")
        start.extend(AddResourceGroupSet(index_set_id=index_set_id).add_resource_group).extend(
            AddProjectData(index_set_id=index_set_id).add_project_data
        ).extend(CreatePredictFlow(index_set_id=index_set_id).create_predict_flow).extend(
            CreateLogCountAggregationFlow(index_set_id=index_set_id).create_log_count_aggregation_flow
        ).extend(
            CreateStrategy(index_set_id=index_set_id).create_strategy
        ).extend(
            end
        )
        tree = build_tree(start, data=data_context)
        parser = PipelineParser(pipeline_tree=tree)
        pipeline = parser.parse()
        return pipeline


class UpdateOnlineService(BasePipeLineService):
    """更新流程"""

    def build_data_context(self, params, *args, **kwargs) -> Data:
        data_context = Data()
        data_context.inputs["${index_set_id}"] = Var(type=Var.PLAIN, value=params["index_set_id"])
        return data_context

    def build_pipeline(self, data_context: Data, *args, **kwargs):
        current = start = EmptyStartEvent()
        end = EmptyEndEvent()
        index_set_id = kwargs.get("index_set_id")
        params = kwargs.get("params")

        # 1. 检查过滤条件是否有变更
        clustering_config = ClusteringConfig.get_by_index_set_id(index_set_id=index_set_id)
        if "filter_rules" in params and clustering_config.filter_rules != params["filter_rules"]:
            clustering_config.filter_rules = params["filter_rules"]
            clustering_config.save(update_fields=["filter_rules"])
            current = current.extend(UpdateFilterRules(index_set_id=index_set_id).update_filter_rules)

        # 2. 检查模型参数是否有变更
        model_fields = [
            "min_members",
            "predefined_varibles",
            "delimeter",
            "max_log_length",
            "is_case_sensitive",
            "regex_rule_type",
            "regex_template_id",
        ]
        model_field_modified = False
        for field in model_fields:
            if field in params and getattr(clustering_config, field) != params[field]:
                setattr(clustering_config, field, params[field])
                model_field_modified = True

        if model_field_modified:
            clustering_config.save(update_fields=model_fields)
            current = current.extend(UpdateOnlineModel(index_set_id=index_set_id).update_online_model)

        # 3. 检查聚类字段是否有变更
        if "clustering_fields" in params and clustering_config.clustering_fields != params["clustering_fields"]:
            clustering_config.clustering_fields = params["clustering_fields"]
            clustering_config.save(update_fields=["clustering_fields"])
            current = current.extend(UpdateClusteringField(index_set_id=index_set_id).update_clustering_field)

        if current.type() == start.type():
            # 没有任何修改则不做处理
            return None

        current.extend(end)

        tree = build_tree(start, data=data_context)
        parser = PipelineParser(pipeline_tree=tree)
        pipeline = parser.parse()
        return pipeline


def operator_aiops_service_online(index_set_id):
    """
    aiops服务执行 create或者 update
    :param index_set_id: 索引集id
    :return:
    """
    conf = FeatureToggleObject.toggle(BKDATA_CLUSTERING_TOGGLE).feature_config
    clustering_config = ClusteringConfig.get_by_index_set_id(index_set_id=index_set_id)
    rt_name = (
        clustering_config.collector_config_name_en
        if clustering_config.collector_config_name_en
        else "bkdata_{}".format(clustering_config.source_rt_name.split("_", 2)[-1])
    )
    model_name = f"{clustering_config.bk_biz_id}_bklog_model_{index_set_id}"
    params = {
        "model_name": model_name,
        "bk_biz_id": conf["bk_biz_id"],
        "description": f"{clustering_config.bk_biz_id}_bklog_{rt_name}",
        "collector_config_id": clustering_config.collector_config_id,
        "project_id": conf["project_id"],
        "is_case_sensitive": clustering_config.is_case_sensitive,
        "max_log_length": clustering_config.max_log_length,
        "delimeter": clustering_config.delimeter,
        "predefined_varibles": clustering_config.predefined_varibles,
        "max_dist_list": clustering_config.max_dist_list,
        "min_members": clustering_config.min_members,
        "index_set_id": clustering_config.index_set_id,
    }
    # 根据页面操作 进行创建 分两条路：计算平台 or 采集项
    service = ClusteringOnlineService.get_instance(clustering_config=clustering_config)
    data = service.build_data_context(params)
    pipeline = service.build_pipeline(data, **params)
    service.start_pipeline(pipeline)

    now_time = arrow.now()
    clustering_config.task_records.append(
        {"operate": OperatorServiceEnum.CREATE, "task_id": pipeline.id, "time": int(now_time.timestamp())}
    )
    clustering_config.save(update_fields=["task_records"])

    return pipeline.id


class ClusteringOnlineService(object):
    @classmethod
    def get_instance(cls, clustering_config):
        if clustering_config.collector_config_id:
            return AiopsLogOnlineService()
        return AiopsBkdataOnlineService()
