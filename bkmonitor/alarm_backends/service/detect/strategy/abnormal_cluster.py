"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

"""
AbnormalCluster：离群检测算法基于计算平台的计算结果，再基于结果表的is_anomaly数量来进行判断。
"""
import concurrent.futures
import hashlib
import json
import logging
import time
from collections import Counter

from django.conf import settings
from django.utils.translation import gettext as _

from alarm_backends.service.detect import DataPoint
from alarm_backends.service.detect.strategy import (
    BasicAlgorithmsCollection,
    ExprDetectAlgorithms,
    SDKPreDetectMixin,
)
from core.drf_resource import api
from core.prometheus import metrics

logger = logging.getLogger("detect")


class AbnormalCluster(SDKPreDetectMixin, BasicAlgorithmsCollection):
    """
    离群检测
    """

    GROUP_PREDICT_FUNC = api.aiops_sdk.acd_group_predict
    PREDICT_FUNC = api.aiops_sdk.acd_predict

    def pre_detect(self, data_points: list[DataPoint]) -> None:
        """生成按照dimension划分的预测输入数据，调用SDK API进行批量分组预测.

        :param data_points: 待预测的数据
        """
        self._local_pre_detect_results = {}

        item = data_points[0].item
        base_labels = {
            "strategy_id": item.strategy.id,
            "strategy_name": item.strategy.name,
            "bk_biz_id": item.strategy.bk_biz_id,
        }
        if not item.query_configs[0]["intelligent_detect"].get("use_sdk", False):
            return

        # 分组字段
        cluster_fields = set(self.validated_config.get("group", []))
        # 维度字段
        dimension_fields = set(data_points[0].dimension_fields)
        # 分群字段
        not_cluster_fields = list(dimension_fields - cluster_fields)
        predict_args = {
            "nsigma": self.validated_config["args"].get("$sensitivity", 5),
            "cluster": ",".join(not_cluster_fields),
        }

        predict_inputs = {}
        dimension_set = set()
        for data_point in data_points:
            dimension_md5 = data_point.record_id.split(".")[0]
            dimension_set.add(dimension_md5)
            cluster_dimensions = {
                cluster_key: data_point.dimensions[cluster_key] for cluster_key in list(cluster_fields)
            }
            cluster_md5 = self.generate_cluster_hash(cluster_dimensions)
            timestamp = data_point.timestamp
            if cluster_md5 not in predict_inputs:
                predict_inputs[cluster_md5] = {
                    "cluster_data": {},
                }

            if timestamp not in predict_inputs[cluster_md5]["cluster_data"]:
                predict_inputs[cluster_md5]["cluster_data"][timestamp] = {"dimensions": cluster_dimensions, "data": []}

            predict_inputs[cluster_md5]["cluster_data"][timestamp]["data"].append(
                {
                    "__index__": data_point.record_id,
                    "value": data_point.value,
                    "timestamp": data_point.timestamp * 1000,
                    **{field_name: data_point.dimensions[field_name] for field_name in not_cluster_fields},
                }
            )

        # 统计每个策略处理的维度数量
        metrics.AIOPS_DETECT_DIMENSION_COUNT.labels(**base_labels).set(len(dimension_set))

        start_time = time.time()
        tasks = []
        task_dimensions_map = {}  # 存储任务ID到cluster_dimensions的映射

        with concurrent.futures.ThreadPoolExecutor(max_workers=settings.AIOPS_SDK_PREDICT_CONCURRENCY) as executor:
            for cluster_set in predict_inputs.values():
                for clsuter_timed_data in cluster_set["cluster_data"].values():
                    # 保存分组字段-cluster_dimensions信息
                    cluster_dimensions = clsuter_timed_data["dimensions"]
                    future = executor.submit(
                        self.PREDICT_FUNC,
                        **clsuter_timed_data,
                        predict_args=predict_args,
                    )
                    # 将future对象和对应的cluster_dimensions关联起来
                    task_dimensions_map[future] = cluster_dimensions
                    tasks.append(future)

        anomaly_results = {}
        error_counter = Counter()
        for future in concurrent.futures.as_completed(tasks):
            try:
                predict_result = future.result()
                # 补充该任务对应的分组字段维度值-cluster_dimensions
                cluster_dimensions = task_dimensions_map.get(future) or {}
                for output_data in predict_result:
                    if output_data["is_anomaly"]:
                        if output_data["timestamp"] not in anomaly_results:
                            anomaly_results[output_data["timestamp"]] = []
                        # 添加cluster_dimensions信息到返回数据中
                        for cluster_key, cluster_val in cluster_dimensions.items():
                            if cluster_key not in output_data:
                                output_data["cluster_key"] = cluster_val
                        # 作为整体记录到 _cluster_dimensions 中
                        output_data["_cluster_dimensions"] = json.dumps(cluster_dimensions)
                        anomaly_results[output_data["timestamp"]].append(output_data)
            except Exception as e:
                # 统计检测异常的策略
                if isinstance(getattr(e, "data", None), dict) and "code" in e.data:
                    error_counter[e.data["code"]] += 1
                else:
                    error_counter[e.__class__.__name__] += 1
                logger.warning(f"Predict error: {e}")

        for anomaly_list in anomaly_results.values():
            anomaly_list[0]["value"] = len(anomaly_list)
            self._local_pre_detect_results[anomaly_list[0]["__index__"]] = anomaly_list[0]

        metrics.AIOPS_PRE_DETECT_LATENCY.labels(**base_labels).set(time.time() - start_time)
        for error_code, count in error_counter.items():
            metrics.AIOPS_DETECT_ERROR_COUNT.labels(**base_labels, error_code=error_code).set(count)

    def detect(self, data_point):
        if data_point.item.query_configs[0]["intelligent_detect"].get("use_sdk", False):
            # 离群检测只能从预检测结果中获取检测结果，因为必须所有维度放在一个群中进行检测
            if hasattr(self, "_local_pre_detect_results"):
                predict_result_point = self.fetch_pre_detect_result_point(data_point)

                if predict_result_point:
                    return self.detect_by_bkdata(predict_result_point)

            return None
        else:
            return self.detect_by_bkdata(data_point)

    def gen_expr(self):
        expr = "value > 0"
        yield ExprDetectAlgorithms(
            expr,
            (
                _(
                    "{% if value == 1 %} {{ abnormal_clusters }} 维度值发生离群{% endif %}"
                    "{% if value > 1 %} {{ abnormal_clusters }} 等{{ value }}组维度值发生离群{% endif %}"
                )
            ),
        )

    def generate_cluster_hash(self, cluster_dimensions: dict) -> str:
        """生成分群hash.

        :param cluster_dimensions: 分组维度
        :return: 曲线ID
        """
        sorted_key_list = sorted(cluster_dimensions.keys())
        key_values = ":".join(f"{k}_{str(cluster_dimensions[k])}" for k in sorted_key_list)
        md5 = hashlib.md5()
        md5.update(key_values.encode("utf8"))
        return md5.hexdigest()

    def get_context(self, data_point):
        context = super().get_context(data_point)
        abnormal_clusters = parse_cluster(
            data_point.values["cluster"], data_point.values.get("_cluster_dimensions") or "{}"
        )
        context.update({"abnormal_clusters": abnormal_clusters})
        return context

    def anomaly_message_template_tuple(self, data_point):
        prefix, suffix = super().anomaly_message_template_tuple(data_point)
        return prefix, ""


def parse_cluster(cluster_str, group_str):
    groups = json.loads(f"[{group_str}]")
    clusters = json.loads(f"[{cluster_str}]")
    result = []
    if groups:
        for key, value in groups[0].items():
            result.append(f"{key}({value})")
    if clusters:
        for key, value in clusters[0].items():
            result.append(f"{key}({value})")
    result = "[{}]".format("-".join(result))
    return result
