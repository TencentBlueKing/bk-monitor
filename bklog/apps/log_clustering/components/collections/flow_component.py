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

from django.utils.translation import gettext_lazy as _
from pipeline.builder import ServiceActivity, Var
from pipeline.component_framework.component import Component
from pipeline.core.flow.activity import StaticIntervalGenerator

from apps.log_clustering.constants import StrategiesType
from apps.log_clustering.handlers.clustering_monitor import ClusteringMonitorHandler
from apps.log_clustering.handlers.dataflow.dataflow_handler import DataFlowHandler
from apps.log_clustering.models import ClusteringConfig
from apps.log_search.constants import DataFlowResourceUsageType, InnerTag
from apps.log_search.models import LogIndexSet
from apps.utils.pipline import BaseService


class CreatePredictFlowService(BaseService):
    name = _("创建预测flow")
    interval = StaticIntervalGenerator(BaseService.TASK_POLLING_INTERVAL)

    def _execute(self, data, parent_data):
        index_set_id = data.get_one_of_inputs("index_set_id")
        flow = DataFlowHandler().create_predict_flow(index_set_id=index_set_id)
        DataFlowHandler().set_dataflow_resource(index_set_id, flow["flow_id"], DataFlowResourceUsageType.online)
        LogIndexSet.set_tag(index_set_id, InnerTag.CLUSTERING.value)
        DataFlowHandler().operator_flow(flow_id=flow["flow_id"], consuming_mode="from_tail")
        return True


class CreatePredictFlowComponent(Component):
    name = "CreatePredictFlow"
    code = "create_predict_flow"
    bound_service = CreatePredictFlowService


class CreatePredictFlow:
    def __init__(self, index_set_id: int, collector_config_id: int = None):
        self.create_predict_flow = ServiceActivity(
            component_code="create_predict_flow", name=f"create_predict_flow:{index_set_id}_{collector_config_id}"
        )
        self.create_predict_flow.component.inputs.collector_config_id = Var(
            type=Var.SPLICE, value="${collector_config_id}"
        )
        self.create_predict_flow.component.inputs.index_set_id = Var(type=Var.SPLICE, value="${index_set_id}")


class CreateLogCountAggregationFlowService(BaseService):
    name = _("创建日志数量聚类-flow")
    interval = StaticIntervalGenerator(BaseService.TASK_POLLING_INTERVAL)

    def _execute(self, data, parent_data):
        index_set_id = data.get_one_of_inputs("index_set_id")
        flow = DataFlowHandler().create_log_count_aggregation_flow(index_set_id=index_set_id)
        DataFlowHandler().set_dataflow_resource(index_set_id, flow["flow_id"], DataFlowResourceUsageType.agg)
        DataFlowHandler().operator_flow(flow_id=flow["flow_id"], consuming_mode="continue")
        # 添加索引集表标签
        LogIndexSet.set_tag(index_set_id, InnerTag.CLUSTERING.value)
        return True


class CreateLogCountAggregationFlowComponent(Component):
    name = "CreateLogCountAggregationFlow"
    code = "create_log_count_aggregation_flow"
    bound_service = CreateLogCountAggregationFlowService


class CreateLogCountAggregationFlow:
    def __init__(self, index_set_id: int, collector_config_id: int = None):
        self.create_log_count_aggregation_flow = ServiceActivity(
            component_code="create_log_count_aggregation_flow",
            name=f"create_log_count_aggregation_flow:{index_set_id}_{collector_config_id}",
        )
        self.create_log_count_aggregation_flow.component.inputs.collector_config_id = Var(
            type=Var.SPLICE, value="${collector_config_id}"
        )
        self.create_log_count_aggregation_flow.component.inputs.index_set_id = Var(
            type=Var.SPLICE, value="${index_set_id}"
        )


class CreateStrategyService(BaseService):
    name = _("创建告警策略")

    def _execute(self, data, parent_data):
        index_set_id = data.get_one_of_inputs("index_set_id")
        clustering_config = ClusteringConfig.get_by_index_set_id(index_set_id=index_set_id)
        handler = ClusteringMonitorHandler(index_set_id=index_set_id)
        if clustering_config.new_cls_strategy_enable:
            handler.create_or_update_clustering_strategy(StrategiesType.NEW_CLS_strategy)
        if clustering_config.normal_strategy_enable:
            handler.create_or_update_clustering_strategy(StrategiesType.NORMAL_STRATEGY)
        return True


class CreateStrategyComponent(Component):
    name = "CreateStrategy"
    code = "create_strategy"
    bound_service = CreateStrategyService


class CreateStrategy:
    def __init__(self, index_set_id: int):
        self.create_strategy = ServiceActivity(
            component_code="create_strategy",
            name=f"create_strategy:{index_set_id}",
        )
        self.create_strategy.component.inputs.index_set_id = Var(type=Var.SPLICE, value="${index_set_id}")


class UpdateFilterRulesService(BaseService):
    name = _("更新过滤条件")

    def _execute(self, data, parent_data):
        index_set_id = data.get_one_of_inputs("index_set_id")
        clustering_config = ClusteringConfig.get_by_index_set_id(index_set_id=index_set_id)
        if clustering_config.predict_flow_id:
            # 更新 predict_flow filter_rule
            DataFlowHandler().update_predict_flow_filter_rules(index_set_id=index_set_id)
        elif clustering_config.pre_treat_flow_id:
            # 更新filter_rule
            DataFlowHandler().update_filter_rules(index_set_id=index_set_id)
        return True


class UpdateFilterRulesComponent(Component):
    name = "UpdateFilterRules"
    code = "update_filter_rules"
    bound_service = UpdateFilterRulesService


class UpdateFilterRules:
    def __init__(self, index_set_id: int):
        self.update_filter_rules = ServiceActivity(
            component_code="update_filter_rules",
            name=f"update_filter_rules:{index_set_id}",
        )
        self.update_filter_rules.component.inputs.index_set_id = Var(type=Var.SPLICE, value="${index_set_id}")


class UpdateOnlineModelService(BaseService):
    name = _("更新聚类模型")

    def _execute(self, data, parent_data):
        index_set_id = data.get_one_of_inputs("index_set_id")
        DataFlowHandler().update_predict_nodes_and_online_tasks(index_set_id=index_set_id)
        return True


class UpdateOnlineModelComponent(Component):
    name = "UpdateOnlineModel"
    code = "update_online_model"
    bound_service = UpdateOnlineModelService


class UpdateOnlineModel:
    def __init__(self, index_set_id: int):
        self.update_online_model = ServiceActivity(
            component_code="update_online_model",
            name=f"update_online_model:{index_set_id}",
        )
        self.update_online_model.component.inputs.index_set_id = Var(type=Var.SPLICE, value="${index_set_id}")


class UpdateClusteringFieldService(BaseService):
    name = _("更新聚类字段")

    def _execute(self, data, parent_data):
        index_set_id = data.get_one_of_inputs("index_set_id")
        clustering_config = ClusteringConfig.get_by_index_set_id(index_set_id=index_set_id)
        if clustering_config.predict_flow_id:
            # 更新flow 中的参与聚类和非参与聚类的节点
            DataFlowHandler().update_predict_flow(index_set_id=index_set_id)
        elif self.data.pre_treat_flow_id:
            # 更新flow
            DataFlowHandler().update_flow(index_set_id=index_set_id)
        return True


class UpdateClusteringFieldComponent(Component):
    name = "UpdateClusteringField"
    code = "update_clustering_field"
    bound_service = UpdateClusteringFieldService


class UpdateClusteringField:
    def __init__(self, index_set_id: int):
        self.update_clustering_field = ServiceActivity(
            component_code="update_clustering_field",
            name=f"update_clustering_field:{index_set_id}",
        )
        self.update_clustering_field.component.inputs.index_set_id = Var(type=Var.SPLICE, value="${index_set_id}")
