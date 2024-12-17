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
from dataclasses import asdict, dataclass, field
from typing import List

from django.conf import settings
from django.utils.translation import gettext as _

from bkmonitor.dataflow.node.base import Node


class ProcessorNode(Node, abc.ABC):
    pass


###############
#   RealTime  #
###############
class RealTimeNode(ProcessorNode, abc.ABC):
    """
    实时计算节点
    """

    NODE_TYPE = "realtime"
    DEFAULT_AGG_METHOD = "MAX"

    def __init__(
        self,
        source_rt_id,
        agg_interval,
        agg_method=None,
        metric_fields=None,
        dimension_fields=None,
        sql=None,
        name_prefix=None,
        *args,
        **kwargs,
    ):
        """
        :param source_rt_id:   数据源表(ex: 100147_ieod_system_cpu_detail)
        :param agg_interval:   统计周期
        :param agg_method:     统计方法（SUM、AVG、MIN、MAX、COUNT）
        :param metric_fields:  统计字段
        :param dimension_fields: 统计分组字段
        :param sql: 可选参数，sql语句
        :param name_prefix: 可选参数，节点名称前缀
        """
        super(RealTimeNode, self).__init__(*args, **kwargs)

        self.source_rt_id = source_rt_id
        self.bk_biz_id, _, self.process_rt_id = source_rt_id.partition("_")

        self.bk_biz_id = int(self.bk_biz_id)
        self.agg_interval = agg_interval

        if sql:
            self.sql = sql
        else:
            if agg_interval and (agg_method is None or metric_fields is None or dimension_fields is None):
                raise ValueError(
                    "please provide 'agg_method', 'metric_fields', 'dimension_fields', if 'sql' does not exist."
                )
            temp_sql = self.gen_statistic_sql(self.source_rt_id, agg_method, metric_fields, dimension_fields)
            self.sql = temp_sql.strip()  # 去掉前后空格

        self.name_prefix = name_prefix

        # 指定输出表名
        self.output_rt_id = kwargs.pop("output_rt_id", "")
        _, _, self._process_rt_id = self.output_rt_id.partition("_")

    def __eq__(self, other):
        if isinstance(other, dict):
            config = self.config
            if (
                config.get("from_result_table_ids") == other.get("from_result_table_ids")
                and config.get("table_name") == other.get("table_name")
                and config.get("bk_biz_id") == other.get("bk_biz_id")
            ):
                return True
        elif isinstance(other, self.__class__):
            return self == other.config
        return False

    @property
    @abc.abstractmethod
    def table_name(self):
        """
        输出表名（不带业务ID前缀）
        """
        return self._process_rt_id if self._process_rt_id else self.process_rt_id

    @property
    def output_table_name(self):
        """
        输出表名（带上业务ID前缀）
        """
        return "{}_{}".format(self.bk_biz_id, self.table_name)

    @property
    def name(self):
        prefix = self.name_prefix or self.get_node_type()
        return "{}({})".format(prefix, self.source_rt_id)[:50]  # 数据平台的计算节点名称限制50个字符

    @property
    def config(self):
        base_config = {
            "from_result_table_ids": [self.source_rt_id],
            "table_name": self.table_name,
            "output_name": self.table_name,
            "bk_biz_id": self.bk_biz_id,
            "name": self.name,
            "window_type": "none",
            "sql": self.sql,
        }
        if self.agg_interval:
            base_config.update(
                {
                    "window_type": "scroll",  # 滚动窗口
                    "waiting_time": settings.BK_DATA_REALTIME_NODE_WAIT_TIME,  # 此时添加等待时间，是为了有可能数据延时的情况
                    "count_freq": self.agg_interval,
                }
            )
        return base_config

    def gen_statistic_sql(self, rt_id, agg_method, metric_fields, dimension_fields):
        select = ",".join(metric_fields + dimension_fields)
        group_by = ",".join(dimension_fields)
        return "SELECT {} FROM {} GROUP BY {}".format(select, rt_id, group_by)


class DownsamplingNode(RealTimeNode):
    """
    降采样 实时计算节点
    """

    @property
    def table_name(self):
        if self._process_rt_id:
            return self._process_rt_id

        suffix = "{}s".format(self.agg_interval)
        return "{}_{}".format(self.process_rt_id, suffix)

    def gen_statistic_sql(self, rt_id, agg_method, metric_fields, dimension_fields):
        agg_method = agg_method or self.DEFAULT_AGG_METHOD
        select_fields = []
        for f in metric_fields or []:
            select_fields.append("{}(`{}`) as `{}`".format(agg_method, f, f))

        dimension_fields = dimension_fields or []

        select = ",".join(select_fields + dimension_fields)
        group_by = ",".join(dimension_fields)
        return "SELECT {} FROM {} GROUP BY {}".format(select, rt_id, group_by)


class FilterUnknownTimeNode(RealTimeNode):
    """
    过滤未来数据和过期数据
    """

    EXPIRE_TIME = 3600  # 保留过去1个小时内的数据
    FUTURE_TIME = 60  # 保留未来1分钟内的数据

    @property
    def table_name(self):
        if self._process_rt_id:
            return self._process_rt_id

        return "{}_{}".format(self.process_rt_id, settings.BK_DATA_RAW_TABLE_SUFFIX)

    def gen_statistic_sql(self, rt_id, agg_method, metric_fields, dimension_fields):
        select_fields = ["`{}`".format(i) for i in metric_fields + dimension_fields]
        return """
        SELECT {}
        FROM {}
        WHERE (time> UNIX_TIMESTAMP() - {}) AND (time < UNIX_TIMESTAMP() + {})
        """.format(
            ", ".join(select_fields), rt_id, self.EXPIRE_TIME, self.FUTURE_TIME
        )


class AlarmStrategyNode(DownsamplingNode):
    """
    监控策略节点
    """

    def __init__(self, strategy_id, *args, **kwargs):
        super(AlarmStrategyNode, self).__init__(*args, **kwargs)

        self.strategy_id = strategy_id

    @property
    def table_name(self):
        if self._process_rt_id:
            return self._process_rt_id

        name = "{}_{}_plan".format(self.process_rt_id, self.strategy_id)[-50:]
        while not name[0].isalpha():
            # 保证首字符是英文
            name = name[1:]
        return name


class CMDBPrepareAggregateFullNode(RealTimeNode):
    """
    CMDB 预聚合，  信息补充节点，1条对1条
    """

    CMDB_HOST_TOPO_RT_ID = "591_bkpub_cmdb_host_rels_split_innerip"  # 数据源表 591_bkpub_cmdb_host_rels_split_innerip

    @property
    def table_name(self):
        if self._process_rt_id:
            return self._process_rt_id

        process_rt_id, _, _ = self.process_rt_id.rpartition("_")
        return "{}_{}".format(process_rt_id, settings.BK_DATA_CMDB_FULL_TABLE_SUFFIX)

    @property
    def name(self):
        return _("添加主机拓扑关系数据")

    @property
    def config(self):
        return {
            "from_result_table_ids": [self.source_rt_id, self.CMDB_HOST_TOPO_RT_ID],
            "output_name": self.table_name,
            "table_name": self.table_name,
            "name": self.name,
            "bk_biz_id": self.bk_biz_id,
            "sql": self.sql,
            "window_type": "none",
        }

    def gen_statistic_sql(self, rt_id, agg_method, metric_fields, dimension_fields):
        a_select_fields = ["A.`{}`".format(i) for i in metric_fields + dimension_fields]
        b_select_fields = ["B.bk_host_id", "B.bk_relations"]
        select_fields = ", ".join(a_select_fields + b_select_fields)
        return f"""
            select  {select_fields}
            from {rt_id} A
            LEFT JOIN  {self.CMDB_HOST_TOPO_RT_ID} B
            ON  A.bk_target_cloud_id = B.bk_cloud_id and A.bk_target_ip = B.bk_host_innerip
        """


class CMDBPrepareAggregateSplitNode(RealTimeNode):
    """
    CMDB 预聚合，  将补充的信息进行拆解，1条对多条
    """

    @property
    def table_name(self):
        if self._process_rt_id:
            return self._process_rt_id

        process_rt_id, _, _ = self.process_rt_id.rpartition("_")
        return "{}_{}".format(process_rt_id, settings.BK_DATA_CMDB_SPLIT_TABLE_SUFFIX)

    @property
    def name(self):
        return _("拆分拓扑关系中模块和集群")

    @property
    def config(self):
        return {
            "from_result_table_ids": [self.source_rt_id],
            "output_name": self.table_name,
            "table_name": self.table_name,
            "name": self.name,
            "bk_biz_id": self.bk_biz_id,
            "sql": self.sql,
            "window_type": "none",
        }

    def gen_statistic_sql(self, rt_id, agg_method, metric_fields, dimension_fields):
        a_select_fields = ["`{}`".format(i) for i in metric_fields + dimension_fields]
        b_select_fields = ["bk_host_id", "bk_relations", "bk_obj_id", "bk_inst_id"]
        select_fields = ", ".join(a_select_fields + b_select_fields)
        return f"""select {select_fields}
        from {rt_id},\n
        lateral table(udf_bkpub_cmdb_split_set_module(bk_relations, bk_biz_id)) as T(bk_obj_id, bk_inst_id)
        """


class MultivariateAnomalyAggNode(RealTimeNode):
    def __init__(self, bk_biz_id, table_suffix=None, result_table_name=None, *args, **kwargs):
        super(MultivariateAnomalyAggNode, self).__init__(*args, **kwargs)
        self.table_suffix = table_suffix
        self.bk_biz_id = bk_biz_id
        self.result_table_name = result_table_name

    @property
    def table_name(self):
        if self.result_table_name:
            name = self.result_table_name
        else:
            name = f"{self.source_rt_id}_{self.table_suffix}"
        while not name[0].isalpha():
            # 保证首字符是英文
            name = name[1:]
        return name

    @property
    def name(self):
        return self.table_name


class MergeNode(ProcessorNode):
    NODE_TYPE = "merge"

    def __init__(self, result_table_name, bk_biz_id, *args, **kwargs):
        super(MergeNode, self).__init__(*args, **kwargs)
        self.result_table_name = result_table_name
        self.bk_biz_id = bk_biz_id

    @property
    def table_name(self):
        return self.result_table_name

    @property
    def output_table_name(self):
        return f"{self.bk_biz_id}_{self.table_name}"

    @property
    def name(self):
        return self.table_name

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

    @property
    def config(self):
        base_config = {
            "bk_biz_id": self.bk_biz_id,
            "name": self.table_name,
            "table_name": self.table_name,
            "output_name": self.table_name,
            "from_result_table_ids": [parent.output_table_name for parent in self.parent_list],
            "description": self.table_name,
            "config": [],
        }
        return base_config


class BusinessSceneNode(DownsamplingNode):
    """
    业务指标节点
    """

    def __init__(self, access_bk_biz_id, bk_biz_id, scene_name, strategy_id=None, *args, **kwargs):
        kwargs["agg_interval"] = 0
        super(BusinessSceneNode, self).__init__(*args, **kwargs)

        self.access_bk_biz_id = access_bk_biz_id
        self.bk_biz_id = bk_biz_id
        self.strategy_id = strategy_id
        self.scene_name = scene_name

    @property
    def table_name(self):
        if self._process_rt_id:
            return self._process_rt_id

        if self.strategy_id:
            name = "{}_stra_{}_{}_plan".format(self.process_rt_id, self.strategy_id, self.scene_name)[-50:]
        else:
            name = "{}_{}_{}_plan".format(self.process_rt_id, self.access_bk_biz_id, self.scene_name)[-50:]
        while not name[0].isalpha():
            # 保证首字符是英文
            name = name[1:]
        return name

    @property
    def config(self):
        base_config = {
            "from_result_table_ids": [self.source_rt_id],
            "table_name": self.table_name,
            "output_name": self.table_name,
            "bk_biz_id": self.bk_biz_id,
            "name": self.name,
            "window_type": "none",
            "sql": self.sql,
        }
        return base_config


class BizFilterRealTimeNode(RealTimeNode):
    def __init__(self, access_bk_biz_id, *args, **kwargs):
        self.access_bk_biz_id = access_bk_biz_id
        super(BizFilterRealTimeNode, self).__init__(*args, **kwargs)

    @property
    def table_name(self):
        name = f"{self.source_rt_id}_{self.access_bk_biz_id}"
        while not name[0].isalpha():
            # 保证首字符是英文
            name = name[1:]
        return name

    @property
    def name(self):
        return self.table_name


class OffLineCalculateNode(ProcessorNode, abc.ABC):
    NODE_TYPE = "batchv2"
    SHORT_KEY_WORD = "recommend"
    KEY_WORD = f"metric_{SHORT_KEY_WORD}"

    def __init__(self, access_bk_biz_id, bk_biz_id, sql, suffix, *args, **kwargs):
        kwargs["agg_interval"] = None
        super(OffLineCalculateNode, self).__init__(*args, **kwargs)
        self.access_bk_biz_id = access_bk_biz_id
        self.bk_biz_id = bk_biz_id
        self.suffix = suffix
        self.sql = sql
        self.fields = kwargs.pop("fields", [])

    def __eq__(self, other):
        if isinstance(other, dict):
            config = self.config
            if (
                config.get("outputs") == other.get("outputs")
                and config.get("inputs") == other.get("inputs")
                and config.get("bk_biz_id") == other.get("bk_biz_id")
            ):
                return True
        elif isinstance(other, self.__class__):
            return self == other.config
        return False

    @property
    def table_name(self):
        """输出表名
        :return: 输出表名
        """
        return f"{self.KEY_WORD}_{self.suffix}_{self.access_bk_biz_id}"

    @property
    def output_table_name(self):
        """
        输出表名（带上业务ID前缀）
        """
        return f"{self.bk_biz_id}_{self.table_name}"

    @property
    def name(self):
        return f"{self.access_bk_biz_id}_{self.suffix}"[:50]

    def get_api_params(self, *args, **kwargs):
        api_params = super(OffLineCalculateNode, self).get_api_params(*args, **kwargs)
        config = api_params.setdefault("config", {})
        config["node_type"] = self.get_node_type()
        return api_params

    @property
    def config(self):
        outputs = [
            {
                "bk_biz_id": self.bk_biz_id,
                "output_name": self.table_name,  # 结果表中文描述信息
                "table_name": self.table_name,  # 结果表英文名称
            }
        ]
        inputs = [
            {"id": parent.node_id, "from_result_table_ids": [parent.output_table_name]} for parent in self.parent_list
        ]
        dedicated_config = {
            "sql": self.sql,
            "recovery_config": {"recovery_enable": False, "recovery_times": "1", "recovery_interval": "5m"},
            "schedule_config": {"count_freq": "1", "schedule_period": "day", "start_time": "2022-11-17 00:00:00"},
            "output_config": {
                "output_baseline_type": "upstream_result_table",
                "enable_customize_output": False,
                "output_baseline": "",
                "output_baseline_location": "start",
                "output_offset": "0",
                "output_offset_unit": "hour",
            },
        }
        window_info = [
            {
                "result_table_id": parent.output_table_name,
                "window_type": "scroll",
                "window_offset": "0",  # 窗口偏移值
                "window_offset_unit": "hour",  # 窗口偏移单位
                "dependency_rule": "all_finished",  # 依赖策略
            }
            for parent in self.parent_list
        ]
        base_config = {
            "name": self.name,
            "bk_biz_id": self.bk_biz_id,
            "outputs": outputs,
            "inputs": inputs,
            "dedicated_config": dedicated_config,
            "window_info": window_info,
        }
        return base_config


@dataclass
class FlinkStreamCodeOutputField:
    field_name: str
    field_alias: str
    event_time: bool = False
    field_type: str = "string"
    validate: dict = field(
        default_factory=lambda: {
            "name": {"status": False, "errorMsg": "HOME:必填项不可为空"},
            "alias": {"status": False, "errorMsg": "HOME:必填项不可为空"},
        }
    )


@dataclass
class FlinkStreamCodeDefine:
    args: str
    language: str
    code: str
    output_fields: List[FlinkStreamCodeOutputField]


class FlinkStreamNode(ProcessorNode, abc.ABC):
    NODE_TYPE = "flink_streaming"
    PROJECT_PREFIX = ""

    def __init__(self, source_rt_id, name, *args, **kwargs):
        super(FlinkStreamNode, self).__init__(*args, **kwargs)
        self.source_rt_id = source_rt_id
        self.bk_biz_id, self.process_table_name = source_rt_id.split("_", 1)
        self._name = name

    @property
    def name(self):
        return self._name

    @property
    def code(self) -> FlinkStreamCodeDefine:
        raise NotImplementedError

    @property
    def table_name(self):
        return f"{self.process_table_name}_output"

    @property
    def result_table_id(self):
        return f"{self.bk_biz_id}_{self.table_name}"

    @property
    def config(self):
        return {
            "bk_biz_id": int(self.bk_biz_id),
            "name": self.name,
            "code": self.code.code,
            "processing_name": self.table_name,
            "user_args": self.code.args,
            "programming_language": self.code.language,
            "outputs": [
                {
                    "bk_biz_id": self.bk_biz_id,
                    "fields": [asdict(i) for i in self.code.output_fields],
                    "output_name": self.table_name,
                    "table_name": self.table_name,
                }
            ],
            "advanced": {"use_savepoint": True},
            "from_nodes": [
                {
                    "from_result_table_ids": [
                        self.source_rt_id,
                    ],
                    "id": self.parent_list[0].node_id,
                }
            ],
        }

    def __eq__(self, other):
        if isinstance(other, dict):
            config = self.config
            try:
                if (
                    config["bk_biz_id"] == other["bk_biz_id"]
                    and config["from_nodes"][0]["from_result_table_ids"]
                    == other["from_nodes"][0]["from_result_table_ids"]
                    and config["outputs"][0]["table_name"] == other["outputs"][0]["table_name"]
                ):
                    return True
            except (KeyError, IndexError):
                pass

        elif isinstance(other, self.__class__):
            return self == other.config
        return False
