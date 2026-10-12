import abc

from django.utils.translation import gettext as _

from bk_monitor_base.metadata.config import settings
from bk_monitor_base.metadata.dataflow.constants import (
    BK_DATA_CMDB_FULL_TABLE_SUFFIX,
    BK_DATA_CMDB_SPLIT_TABLE_SUFFIX,
    BK_DATA_RAW_TABLE_SUFFIX,
)
from bk_monitor_base.metadata.dataflow.node.base import Node


class ProcessorNode(Node, abc.ABC):
    pass


###############
#   RealTime  #
###############
class RealTimeNode(ProcessorNode, abc.ABC):
    """
    实时计算节点
    """

    NODE_TYPE: str = "realtime"
    DEFAULT_AGG_METHOD: str = "MAX"

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
        super().__init__(*args, **kwargs)

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
        return f"{self.bk_biz_id}_{self.table_name}"

    @property
    def name(self):
        prefix = self.name_prefix or self.get_node_type()
        return f"{prefix}({self.source_rt_id})"[:50]  # 数据平台的计算节点名称限制50个字符

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
                    "waiting_time": settings.metadata.bk_data_realtime_node_wait_time,  # 此时添加等待时间，是为了有可能数据延时的情况
                    "count_freq": self.agg_interval,
                }
            )
        return base_config

    def gen_statistic_sql(self, rt_id, agg_method, metric_fields, dimension_fields):
        select = ",".join(metric_fields + dimension_fields)
        group_by = ",".join(dimension_fields)
        return f"SELECT {select} FROM {rt_id} GROUP BY {group_by}"


class DownsamplingNode(RealTimeNode):
    """
    降采样 实时计算节点
    """

    @property
    def table_name(self):
        if self._process_rt_id:
            return self._process_rt_id

        suffix = f"{self.agg_interval}s"
        return f"{self.process_rt_id}_{suffix}"

    def gen_statistic_sql(self, rt_id, agg_method, metric_fields, dimension_fields):
        agg_method = agg_method or self.DEFAULT_AGG_METHOD
        select_fields = []
        for f in metric_fields or []:
            select_fields.append(f"{agg_method}(`{f}`) as `{f}`")

        dimension_fields = dimension_fields or []

        select = ",".join(select_fields + dimension_fields)
        group_by = ",".join(dimension_fields)
        return f"SELECT {select} FROM {rt_id} GROUP BY {group_by}"


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

        return f"{self.process_rt_id}_{BK_DATA_RAW_TABLE_SUFFIX}"

    def gen_statistic_sql(self, rt_id, agg_method, metric_fields, dimension_fields):
        select_fields = [f"`{i}`" for i in metric_fields + dimension_fields]
        return """
        SELECT {}
        FROM {}
        WHERE (time> UNIX_TIMESTAMP() - {}) AND (time < UNIX_TIMESTAMP() + {})
        """.format(", ".join(select_fields), rt_id, self.EXPIRE_TIME, self.FUTURE_TIME)


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
        return f"{process_rt_id}_{BK_DATA_CMDB_FULL_TABLE_SUFFIX}"

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
        a_select_fields = [f"A.`{i}`" for i in metric_fields + dimension_fields]
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
        return f"{process_rt_id}_{BK_DATA_CMDB_SPLIT_TABLE_SUFFIX}"

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
        a_select_fields = [f"`{i}`" for i in metric_fields + dimension_fields]
        b_select_fields = ["bk_host_id", "bk_relations", "bk_obj_id", "bk_inst_id"]
        select_fields = ", ".join(a_select_fields + b_select_fields)
        return f"""select {select_fields}
        from {rt_id},\n
        lateral table(udf_bkpub_cmdb_split_set_module(bk_relations, bk_biz_id)) as T(bk_obj_id, bk_inst_id)
        """
