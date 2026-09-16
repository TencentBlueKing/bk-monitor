from django.conf import settings
from django.utils.translation import gettext as _

from bk_monitor_base.metadata.dataflow.node.processor import FilterUnknownTimeNode
from bk_monitor_base.metadata.dataflow.node.source import StreamSourceNode
from bk_monitor_base.metadata.dataflow.node.storage import create_tspider_or_druid_node
from bk_monitor_base.metadata.dataflow.task.base import BaseTask


class FilterUnknownTimeTask(BaseTask):
    """
    过滤掉未来时间，以及一小时前的数据（数据乱序会导致druid存储产生过多的segment）
    """

    def __init__(self, rt_id, metric_field, dimension_fields):
        """

        :param rt_id: 计算平台存在的表名

        1. 根据rt_id查相关表信息
        2. 根据表信息，创建出对应的flow，以及node节点
        3. 最后启动任务
        """
        super(FilterUnknownTimeTask, self).__init__()

        self.rt_id = rt_id

        stream_source_node = StreamSourceNode(rt_id)
        process_node = FilterUnknownTimeNode(
            source_rt_id=stream_source_node.output_table_name,
            agg_interval=0,
            metric_fields=metric_field,
            dimension_fields=dimension_fields,
            parent=stream_source_node,
        )
        storage_node = create_tspider_or_druid_node(
            source_rt_id=process_node.output_table_name,
            storage_expires=settings.metadata.bk_data_data_expires_days,
            parent=process_node,
        )

        self.node_list = [stream_source_node, process_node, storage_node]

    @property
    def flow_name(self):
        return "{} {}".format(_("过滤无效时间"), self.rt_id)
