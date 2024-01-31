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
from django.conf import settings
from django.utils.translation import ugettext as _

from bkmonitor.dataflow.node.machine_learning import (
    MultivariateAnomalySceneServiceNode,
    SceneServiceNode,
    SimilarMetricClusteringServiceNode,
)
from bkmonitor.dataflow.node.processor import (
    AlarmStrategyNode,
    BizFilterRealTimeNode,
    BusinessSceneNode,
    MergeNode,
    MultivariateAnomalyAggNode,
)
from bkmonitor.dataflow.node.source import StreamSourceNode
from bkmonitor.dataflow.node.storage import HDFSStorageNode, TSpiderStorageNode
from bkmonitor.dataflow.task.base import BaseTask
from constants.aiops import SceneSet


class StrategyIntelligentModelDetectTask(BaseTask):
    """
    监控策略 对接智能检测模型
    """

    FLOW_NAME_KEY = _("场景服务")

    def __init__(
        self,
        strategy_id,
        rt_id,
        metric_field,
        agg_interval,
        agg_dimensions,
        strategy_sql,
        scene_id,
        plan_id,
        plan_args,
    ):
        """
        :param strategy_id: 策略ID
        :param rt_id:       原始输入表
        :param metric_field:  指标字段
        :param agg_interval:  聚合周期
        :param agg_dimensions:  聚合分组维度
        :param strategy_sql:   直接指定sql语句
        :param scene_id: 场景ID
        :param plan_id: 方案ID
        :param plan_args:   方案参数
        """
        super(StrategyIntelligentModelDetectTask, self).__init__()

        self.strategy_id = strategy_id
        self.rt_id = rt_id

        stream_source_node = StreamSourceNode(rt_id)
        strategy_process_node = AlarmStrategyNode(
            strategy_id=strategy_id,
            source_rt_id=rt_id,
            agg_interval=agg_interval,
            sql=strategy_sql,
            parent=stream_source_node,
        )

        strategy_storage_node = TSpiderStorageNode(
            source_rt_id=strategy_process_node.output_table_name,
            storage_expires=settings.BK_DATA_DATA_EXPIRES_DAYS,
            parent=strategy_process_node,
        )

        scene_service_node = SceneServiceNode(
            source_rt_id=strategy_process_node.output_table_name,
            metric_field=metric_field,
            agg_dimensions=agg_dimensions,
            parent=strategy_process_node,
            plan_args=plan_args,
            plan_id=plan_id,
            scene_id=scene_id,
        )

        tspider_result_storage_node = TSpiderStorageNode(
            source_rt_id=scene_service_node.output_table_name,
            storage_expires=settings.BK_DATA_DATA_EXPIRES_DAYS,
            parent=scene_service_node,
        )

        # hdfs_result_storage_node = HDFSStorageNode(
        #     source_rt_id=scene_service_node.output_table_name,
        #     storage_expires=settings.BK_DATA_DATA_EXPIRES_DAYS_BY_HDFS,
        #     parent=scene_service_node,
        # )

        self.node_list = [
            stream_source_node,
            strategy_process_node,
            strategy_storage_node,
            scene_service_node,
            tspider_result_storage_node,
            # 去除hdfs存储节点
            # hdfs_result_storage_node,
        ]

        self.data_flow = None
        self.output_table_name = scene_service_node.output_table_name

    @property
    def flow_name(self):
        # 模型名称如果有变更，需要同步修改维护dataflow的定时任务逻辑
        return "{} {} {}".format(self.strategy_id, self.FLOW_NAME_KEY, self.rt_id)


class MultivariateAnomalyAggIntelligentModelDetectTask(BaseTask):
    @property
    def flow_name(self):
        return _("【主机场景异常检测】聚合数据源")

    def __init__(self, sources, merge_table_name, result_table_name):
        from bkmonitor.dataflow.utils.multivariate_anomaly.host.utils import (
            build_agg_sql,
            build_agg_trans_sql,
            build_merge_sql,
        )

        self.node_list = []
        self.agg_trans_nodes = []
        for source in sources:
            rt_id = source["result_table_id"]
            bk_data_result_table_id = source["bk_data_result_table_id"]

            stream_source_node = StreamSourceNode(bk_data_result_table_id)

            agg_node = MultivariateAnomalyAggNode(
                source_rt_id=stream_source_node.output_table_name,
                agg_interval=60,
                parent=stream_source_node,
                sql=build_agg_sql(
                    metrics=source["access_metrics"],
                    result_table_id=rt_id,
                    from_rt_id=stream_source_node.output_table_name,
                ),
                table_suffix="agg",
                bk_biz_id=settings.BK_DATA_BK_BIZ_ID,
            )

            agg_trans_node = MultivariateAnomalyAggNode(
                source_rt_id=agg_node.output_table_name,
                agg_interval=None,
                parent=agg_node,
                sql=build_agg_trans_sql(
                    metrics=source["access_metrics"], result_table_id=rt_id, from_rt_id=agg_node.output_table_name
                ),
                table_suffix="trans",
                bk_biz_id=settings.BK_DATA_BK_BIZ_ID,
            )

            tspider_result_storage_node = TSpiderStorageNode(
                source_rt_id=agg_trans_node.output_table_name,
                storage_expires=settings.BK_DATA_DATA_EXPIRES_DAYS,
                parent=agg_trans_node,
            )

            self.node_list.extend([stream_source_node, agg_node, agg_trans_node, tspider_result_storage_node])
            self.agg_trans_nodes.append(agg_trans_node)

        merge_node = MergeNode(
            result_table_name=merge_table_name, bk_biz_id=settings.BK_DATA_BK_BIZ_ID, parent=self.agg_trans_nodes
        )

        result_real_time_node = MultivariateAnomalyAggNode(
            source_rt_id=merge_node.output_table_name,
            agg_interval=60,
            parent=merge_node,
            sql=build_merge_sql(merge_node.output_table_name),
            result_table_name=result_table_name,
            bk_biz_id=settings.BK_DATA_BK_BIZ_ID,
        )

        tspider_result_storage_node = TSpiderStorageNode(
            source_rt_id=result_real_time_node.output_table_name,
            storage_expires=settings.BK_DATA_DATA_EXPIRES_DAYS,
            parent=result_real_time_node,
        )

        # hdfs_result_storage_node = HDFSStorageNode(
        #     source_rt_id=result_real_time_node.output_table_name,
        #     storage_expires=settings.BK_DATA_DATA_EXPIRES_DAYS_BY_HDFS,
        #     parent=result_real_time_node,
        # )

        self.node_list.extend([merge_node, result_real_time_node, tspider_result_storage_node])


class MultivariateAnomalyIntelligentModelDetectTask(BaseTask):
    FLOW_NAME_KEY = _("多指标异常检测")

    SCENE_NAME_MAPPING = {SceneSet.HOST: _("主机场景")}

    def __init__(
        self,
        access_bk_biz_id,
        bk_biz_id,
        scene_name,
        rt_id,
        metric_field,
        agg_dimensions,
        strategy_sql,
        scene_id,
        plan_id,
        plan_args,
    ):
        """
        :param bk_biz_id: 业务ID
        :param rt_id:       原始输入表
        :param metric_field:  指标字段
        :param agg_dimensions:  聚合分组维度
        :param strategy_sql:   直接指定sql语句
        :param scene_id: 场景ID
        :param plan_id: 方案ID
        :param plan_args:   方案参数
        """
        super(MultivariateAnomalyIntelligentModelDetectTask, self).__init__()

        self.access_bk_biz_id = access_bk_biz_id
        self.bk_biz_id = bk_biz_id
        self.scene_name = scene_name
        self.rt_id = rt_id
        self.data_flow = None

        stream_source_node = StreamSourceNode(rt_id)

        strategy_process_node = BusinessSceneNode(
            access_bk_biz_id=self.access_bk_biz_id,
            bk_biz_id=bk_biz_id,
            scene_name=scene_name,
            source_rt_id=rt_id,
            sql=strategy_sql,
            parent=stream_source_node,
        )

        strategy_storage_node = TSpiderStorageNode(
            source_rt_id=strategy_process_node.output_table_name,
            storage_expires=settings.BK_DATA_DATA_EXPIRES_DAYS,
            parent=strategy_process_node,
        )

        scene_service_node = MultivariateAnomalySceneServiceNode(
            source_rt_id=strategy_process_node.output_table_name,
            metric_field=metric_field,
            agg_dimensions=agg_dimensions,
            parent=strategy_process_node,
            plan_args=plan_args,
            plan_id=plan_id,
            scene_id=scene_id,
        )

        tspider_result_storage_node = TSpiderStorageNode(
            source_rt_id=scene_service_node.output_table_name,
            storage_expires=settings.BK_DATA_DATA_EXPIRES_DAYS,
            parent=scene_service_node,
        )

        # hdfs_result_storage_node = HDFSStorageNode(
        #     source_rt_id=scene_service_node.output_table_name,
        #     storage_expires=settings.BK_DATA_DATA_EXPIRES_DAYS_BY_HDFS,
        #     parent=scene_service_node,
        # )

        self.node_list = [
            stream_source_node,
            strategy_process_node,
            strategy_storage_node,
            scene_service_node,
            tspider_result_storage_node,
            # hdfs_result_storage_node,
        ]

        self.data_flow = None
        self.output_table_name = scene_service_node.output_table_name

    @property
    def flow_name(self):
        # 模型名称如果有变更，需要同步修改维护dataflow的定时任务逻辑
        return self.build_flow_name(self.access_bk_biz_id, self.SCENE_NAME_MAPPING[self.scene_name])

    @classmethod
    def build_flow_name(cls, access_bk_biz_id, scene_name):
        return "{} {} {}".format(access_bk_biz_id, cls.FLOW_NAME_KEY, scene_name)


class MetricRecommendTask(BaseTask):
    FLOW_NAME_KEY = _("指标推荐V2")

    def __init__(self, access_bk_biz_id, scene_id, plan_id):
        from monitor_web.aiops.metric_recommend.utils import build_biz_filter_sql

        self.access_bk_biz_id = access_bk_biz_id
        self.node_list = []

        source_rt_id = f"{settings.DEFAULT_BKDATA_BIZ_ID}_{settings.BK_DATA_METRIC_RECOMMEND_SOURCE_PROCESSING_ID}"
        system_stream_source_node = StreamSourceNode(source_rt_id)

        biz_filter_realtime_node = BizFilterRealTimeNode(
            source_rt_id=source_rt_id,
            agg_interval=None,
            access_bk_biz_id=access_bk_biz_id,
            sql=build_biz_filter_sql(source_rt_id, access_bk_biz_id),
            parent=system_stream_source_node,
        )

        biz_filter_storage_node = HDFSStorageNode(
            source_rt_id=biz_filter_realtime_node.output_table_name,
            storage_expires=settings.BK_DATA_DATA_EXPIRES_DAYS_BY_HDFS,
            parent=biz_filter_realtime_node,
        )

        similar_metric_clustering_service_node = SimilarMetricClusteringServiceNode(
            access_bk_biz_id=access_bk_biz_id,
            parent=biz_filter_storage_node,
            source_rt_id=biz_filter_storage_node.output_table_name,
            scene_id=scene_id,
            plan_id=plan_id,
            plan_args={
                "$n_jobs": 10,
                "$bk_biz_id": access_bk_biz_id,
                "$mode": "serving",
            },
        )

        similar_metric_clustering_storage_node = HDFSStorageNode(
            source_rt_id=similar_metric_clustering_service_node.output_table_name,
            storage_expires=settings.BK_DATA_DATA_EXPIRES_DAYS_BY_HDFS,
            parent=similar_metric_clustering_service_node,
        )

        self.node_list = [
            system_stream_source_node,
            biz_filter_realtime_node,
            biz_filter_storage_node,
            similar_metric_clustering_service_node,
            similar_metric_clustering_storage_node,
        ]

    @property
    def flow_name(self):
        return "{} {}".format(self.access_bk_biz_id, self.FLOW_NAME_KEY)
