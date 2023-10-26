# -*- coding: utf-8 -*-
from ..base import ComponentAPI


class CollectionsMonitorV3(object):
    """Collections of MONITOR_V3 APIS"""

    def __init__(self, client):
        self.client = client

        self.add_shield = ComponentAPI(
            client=self.client,
            method='POST',
            path='/api/c/compapi{bk_api_ver}/monitor_v3/add_shield/',
            description=u'新增告警屏蔽',
        )
        self.batch_retry_config = ComponentAPI(
            client=self.client,
            method='POST',
            path='/api/c/compapi{bk_api_ver}/monitor_v3/batch_retry_config/',
            description=u'批量重试采集配置的失败实例',
        )
        self.batch_retry_instance_step = ComponentAPI(
            client=self.client,
            method='POST',
            path='/api/c/compapi{bk_api_ver}/monitor_v3/batch_retry_instance_step/',
            description=u'重试失败的节点步骤',
        )
        self.collect_running_status = ComponentAPI(
            client=self.client,
            method='GET',
            path='/api/c/compapi{bk_api_ver}/monitor_v3/collect_running_status/',
            description=u'获取采集配置主机的运行状态',
        )
        self.create_custom_event_group = ComponentAPI(
            client=self.client,
            method='POST',
            path='/api/c/compapi{bk_api_ver}/monitor_v3/create_custom_event_group/',
            description=u'创建自定义事件',
        )
        self.create_custom_time_series = ComponentAPI(
            client=self.client,
            method='POST',
            path='/api/c/compapi{bk_api_ver}/monitor_v3/create_custom_time_series/',
            description=u'创建自定义指标',
        )
        self.custom_time_series = ComponentAPI(
            client=self.client,
            method='GET',
            path='/api/c/compapi{bk_api_ver}/monitor_v3/custom_time_series/',
            description=u'自定义指标列表',
        )
        self.custom_time_series_detail = ComponentAPI(
            client=self.client,
            method='GET',
            path='/api/c/compapi{bk_api_ver}/monitor_v3/custom_time_series_detail/',
            description=u'自定义指标详情',
        )
        self.delete_alarm_strategy = ComponentAPI(
            client=self.client,
            method='POST',
            path='/api/c/compapi{bk_api_ver}/monitor_v3/delete_alarm_strategy/',
            description=u'删除告警策略',
        )
        self.delete_collect_config = ComponentAPI(
            client=self.client,
            method='POST',
            path='/api/c/compapi{bk_api_ver}/monitor_v3/delete_collect_config/',
            description=u'删除采集配置',
        )
        self.delete_custom_event_group = ComponentAPI(
            client=self.client,
            method='POST',
            path='/api/c/compapi{bk_api_ver}/monitor_v3/delete_custom_event_group/',
            description=u'删除自定义事件',
        )
        self.delete_custom_time_series = ComponentAPI(
            client=self.client,
            method='POST',
            path='/api/c/compapi{bk_api_ver}/monitor_v3/delete_custom_time_series/',
            description=u'删除自定义指标',
        )
        self.delete_notice_group = ComponentAPI(
            client=self.client,
            method='POST',
            path='/api/c/compapi{bk_api_ver}/monitor_v3/delete_notice_group/',
            description=u'删除通知组',
        )
        self.disable_shield = ComponentAPI(
            client=self.client,
            method='POST',
            path='/api/c/compapi{bk_api_ver}/monitor_v3/disable_shield/',
            description=u'解除告警屏蔽',
        )
        self.edit_shield = ComponentAPI(
            client=self.client,
            method='POST',
            path='/api/c/compapi{bk_api_ver}/monitor_v3/edit_shield/',
            description=u'编辑告警屏蔽',
        )
        self.export_uptime_check_task = ComponentAPI(
            client=self.client,
            method='GET',
            path='/api/c/compapi{bk_api_ver}/monitor_v3/export_uptime_check_task/',
            description=u'导出拨测任务配置',
        )
        self.get_collect_config_list = ComponentAPI(
            client=self.client,
            method='GET',
            path='/api/c/compapi{bk_api_ver}/monitor_v3/get_collect_config_list/',
            description=u'采集配置列表',
        )
        self.get_collect_log_detail = ComponentAPI(
            client=self.client,
            method='GET',
            path='/api/c/compapi{bk_api_ver}/monitor_v3/get_collect_log_detail/',
            description=u'获取采集下发详细日志',
        )
        self.get_collect_status = ComponentAPI(
            client=self.client,
            method='GET',
            path='/api/c/compapi{bk_api_ver}/monitor_v3/get_collect_status/',
            description=u'查询采集配置节点状态',
        )
        self.get_custom_event_group = ComponentAPI(
            client=self.client,
            method='GET',
            path='/api/c/compapi{bk_api_ver}/monitor_v3/get_custom_event_group/',
            description=u'获取自定义事件详情',
        )
        self.get_es_data = ComponentAPI(
            client=self.client,
            method='POST',
            path='/api/c/compapi{bk_api_ver}/monitor_v3/get_es_data/',
            description=u'获取监控链路时序数据',
        )
        self.get_event_log = ComponentAPI(
            client=self.client,
            method='GET',
            path='/api/c/compapi{bk_api_ver}/monitor_v3/get_event_log/',
            description=u'查询事件流转记录',
        )
        self.get_shield = ComponentAPI(
            client=self.client,
            method='GET',
            path='/api/c/compapi{bk_api_ver}/monitor_v3/get_shield/',
            description=u'获取告警屏蔽',
        )
        self.get_ts_data = ComponentAPI(
            client=self.client,
            method='POST',
            path='/api/c/compapi{bk_api_ver}/monitor_v3/get_ts_data/',
            description=u'获取时序数据',
        )
        self.get_uptime_check_node_list = ComponentAPI(
            client=self.client,
            method='GET',
            path='/api/c/compapi{bk_api_ver}/monitor_v3/get_uptime_check_node_list/',
            description=u'拨测节点列表',
        )
        self.get_uptime_check_task_list = ComponentAPI(
            client=self.client,
            method='GET',
            path='/api/c/compapi{bk_api_ver}/monitor_v3/get_uptime_check_task_list/',
            description=u'拨测任务列表',
        )
        self.import_uptime_check_node = ComponentAPI(
            client=self.client,
            method='POST',
            path='/api/c/compapi{bk_api_ver}/monitor_v3/import_uptime_check_node/',
            description=u'导入拨测节点配置',
        )
        self.import_uptime_check_task = ComponentAPI(
            client=self.client,
            method='POST',
            path='/api/c/compapi{bk_api_ver}/monitor_v3/import_uptime_check_task/',
            description=u'导入拨测任务配置',
        )
        self.list_shield = ComponentAPI(
            client=self.client,
            method='POST',
            path='/api/c/compapi{bk_api_ver}/monitor_v3/list_shield/',
            description=u'获取告警屏蔽列表',
        )
        self.metadata_create_cluster_info = ComponentAPI(
            client=self.client,
            method='POST',
            path='/api/c/compapi{bk_api_ver}/monitor_v3/metadata_create_cluster_info/',
            description=u'创建存储集群信息',
        )
        self.metadata_create_data_id = ComponentAPI(
            client=self.client,
            method='POST',
            path='/api/c/compapi{bk_api_ver}/monitor_v3/metadata_create_data_id/',
            description=u'创建监控数据源',
        )
        self.metadata_create_event_group = ComponentAPI(
            client=self.client,
            method='POST',
            path='/api/c/compapi{bk_api_ver}/monitor_v3/metadata_create_event_group/',
            description=u'创建事件分组',
        )
        self.metadata_create_result_table = ComponentAPI(
            client=self.client,
            method='POST',
            path='/api/c/compapi{bk_api_ver}/monitor_v3/metadata_create_result_table/',
            description=u'创建监控结果表',
        )
        self.metadata_create_result_table_metric_split = ComponentAPI(
            client=self.client,
            method='POST',
            path='/api/c/compapi{bk_api_ver}/monitor_v3/metadata_create_result_table_metric_split/',
            description=u'创建结果表的维度拆分配置',
        )
        self.metadata_create_time_series_group = ComponentAPI(
            client=self.client,
            method='POST',
            path='/api/c/compapi{bk_api_ver}/monitor_v3/metadata_create_time_series_group/',
            description=u'创建自定义时序分组',
        )
        self.metadata_delete_event_group = ComponentAPI(
            client=self.client,
            method='POST',
            path='/api/c/compapi{bk_api_ver}/monitor_v3/metadata_delete_event_group/',
            description=u'删除事件分组',
        )
        self.metadata_delete_time_series_group = ComponentAPI(
            client=self.client,
            method='POST',
            path='/api/c/compapi{bk_api_ver}/monitor_v3/metadata_delete_time_series_group/',
            description=u'删除自定义时序分组',
        )
        self.metadata_get_cluster_info = ComponentAPI(
            client=self.client,
            method='GET',
            path='/api/c/compapi{bk_api_ver}/monitor_v3/metadata_get_cluster_info/',
            description=u'查询指定存储集群信息',
        )
        self.metadata_get_data_id = ComponentAPI(
            client=self.client,
            method='GET',
            path='/api/c/compapi{bk_api_ver}/monitor_v3/metadata_get_data_id/',
            description=u'获取监控数据源具体信息',
        )
        self.metadata_get_event_group = ComponentAPI(
            client=self.client,
            method='GET',
            path='/api/c/compapi{bk_api_ver}/monitor_v3/metadata_get_event_group/',
            description=u'查询事件分组具体内容',
        )
        self.metadata_get_result_table = ComponentAPI(
            client=self.client,
            method='GET',
            path='/api/c/compapi{bk_api_ver}/monitor_v3/metadata_get_result_table/',
            description=u'获取监控结果表具体信息',
        )
        self.metadata_get_result_table_storage = ComponentAPI(
            client=self.client,
            method='GET',
            path='/api/c/compapi{bk_api_ver}/monitor_v3/metadata_get_result_table_storage/',
            description=u'查询指定结果表的指定存储信息',
        )
        self.metadata_get_time_series_group = ComponentAPI(
            client=self.client,
            method='GET',
            path='/api/c/compapi{bk_api_ver}/monitor_v3/metadata_get_time_series_group/',
            description=u'获取自定义时序分组具体内容',
        )
        self.metadata_get_time_series_metrics = ComponentAPI(
            client=self.client,
            method='GET',
            path='/api/c/compapi{bk_api_ver}/monitor_v3/metadata_get_time_series_metrics/',
            description=u'获取自定义时序结果表的metrics信息',
        )
        self.metadata_list_label = ComponentAPI(
            client=self.client,
            method='GET',
            path='/api/c/compapi{bk_api_ver}/monitor_v3/metadata_list_label/',
            description=u'查询当前已有的标签信息',
        )
        self.metadata_list_result_table = ComponentAPI(
            client=self.client,
            method='GET',
            path='/api/c/compapi{bk_api_ver}/monitor_v3/metadata_list_result_table/',
            description=u'查询监控结果表',
        )
        self.metadata_list_transfer_cluster = ComponentAPI(
            client=self.client,
            method='GET',
            path='/api/c/compapi{bk_api_ver}/monitor_v3/metadata_list_transfer_cluster/',
            description=u'获取所有transfer集群信息',
        )
        self.metadata_modify_cluster_info = ComponentAPI(
            client=self.client,
            method='POST',
            path='/api/c/compapi{bk_api_ver}/monitor_v3/metadata_modify_cluster_info/',
            description=u'修改存储集群信息',
        )
        self.metadata_modify_data_id = ComponentAPI(
            client=self.client,
            method='POST',
            path='/api/c/compapi{bk_api_ver}/monitor_v3/metadata_modify_data_id/',
            description=u'修改指定数据源的配置信息',
        )
        self.metadata_modify_event_group = ComponentAPI(
            client=self.client,
            method='POST',
            path='/api/c/compapi{bk_api_ver}/monitor_v3/metadata_modify_event_group/',
            description=u'修改事件分组',
        )
        self.metadata_modify_result_table = ComponentAPI(
            client=self.client,
            method='POST',
            path='/api/c/compapi{bk_api_ver}/monitor_v3/metadata_modify_result_table/',
            description=u'修改监控结果表',
        )
        self.metadata_modify_time_series_group = ComponentAPI(
            client=self.client,
            method='POST',
            path='/api/c/compapi{bk_api_ver}/monitor_v3/metadata_modify_time_series_group/',
            description=u'修改自定义时序分组',
        )
        self.metadata_query_event_group = ComponentAPI(
            client=self.client,
            method='GET',
            path='/api/c/compapi{bk_api_ver}/monitor_v3/metadata_query_event_group/',
            description=u'创建事件分组',
        )
        self.metadata_query_tag_values = ComponentAPI(
            client=self.client,
            method='GET',
            path='/api/c/compapi{bk_api_ver}/monitor_v3/metadata_query_tag_values/',
            description=u'获取自定义时序分组具体内容',
        )
        self.metadata_query_time_series_group = ComponentAPI(
            client=self.client,
            method='GET',
            path='/api/c/compapi{bk_api_ver}/monitor_v3/metadata_query_time_series_group/',
            description=u'查询事件分组',
        )
        self.metadata_upgrade_result_table = ComponentAPI(
            client=self.client,
            method='POST',
            path='/api/c/compapi{bk_api_ver}/monitor_v3/metadata_upgrade_result_table/',
            description=u'将指定的监控单业务结果表升级为全业务结果表',
        )
        self.modify_custom_event_group = ComponentAPI(
            client=self.client,
            method='POST',
            path='/api/c/compapi{bk_api_ver}/monitor_v3/modify_custom_event_group/',
            description=u'修改自定义事件',
        )
        self.modify_custom_time_series = ComponentAPI(
            client=self.client,
            method='POST',
            path='/api/c/compapi{bk_api_ver}/monitor_v3/modify_custom_time_series/',
            description=u'修改自定义指标',
        )
        self.proxy_host_info = ComponentAPI(
            client=self.client,
            method='GET',
            path='/api/c/compapi{bk_api_ver}/monitor_v3/proxy_host_info/',
            description=u'获取自定义上报的proxy主机信息',
        )
        self.query_collect_config = ComponentAPI(
            client=self.client,
            method='POST',
            path='/api/c/compapi{bk_api_ver}/monitor_v3/query_collect_config/',
            description=u'查询采集配置',
        )
        self.query_custom_event_group = ComponentAPI(
            client=self.client,
            method='GET',
            path='/api/c/compapi{bk_api_ver}/monitor_v3/query_custom_event_group/',
            description=u'获取业务下自定义事件列表',
        )
        self.retry_target_nodes = ComponentAPI(
            client=self.client,
            method='POST',
            path='/api/c/compapi{bk_api_ver}/monitor_v3/retry_target_nodes/',
            description=u'重试部分实例或主机',
        )
        self.rollback_deployment_config = ComponentAPI(
            client=self.client,
            method='POST',
            path='/api/c/compapi{bk_api_ver}/monitor_v3/rollback_deployment_config/',
            description=u'采集配置回滚',
        )
        self.save_alarm_strategy = ComponentAPI(
            client=self.client,
            method='POST',
            path='/api/c/compapi{bk_api_ver}/monitor_v3/save_alarm_strategy/',
            description=u'保存告警策略',
        )
        self.save_collect_config = ComponentAPI(
            client=self.client,
            method='POST',
            path='/api/c/compapi{bk_api_ver}/monitor_v3/save_collect_config/',
            description=u'创建/保存采集配置',
        )
        self.save_notice_group = ComponentAPI(
            client=self.client,
            method='POST',
            path='/api/c/compapi{bk_api_ver}/monitor_v3/save_notice_group/',
            description=u'保存通知组',
        )
        self.search_alarm_strategy = ComponentAPI(
            client=self.client,
            method='POST',
            path='/api/c/compapi{bk_api_ver}/monitor_v3/search_alarm_strategy/',
            description=u'查询告警策略',
        )
        self.search_event = ComponentAPI(
            client=self.client,
            method='POST',
            path='/api/c/compapi{bk_api_ver}/monitor_v3/search_event/',
            description=u'查询事件',
        )
        self.search_notice_group = ComponentAPI(
            client=self.client,
            method='POST',
            path='/api/c/compapi{bk_api_ver}/monitor_v3/search_notice_group/',
            description=u'查询通知组',
        )
        self.switch_alarm_strategy = ComponentAPI(
            client=self.client,
            method='POST',
            path='/api/c/compapi{bk_api_ver}/monitor_v3/switch_alarm_strategy/',
            description=u'启停告警策略',
        )
        self.toggle_collect_config_status = ComponentAPI(
            client=self.client,
            method='POST',
            path='/api/c/compapi{bk_api_ver}/monitor_v3/toggle_collect_config_status/',
            description=u'启停采集配置',
        )
        self.upgrade_collect_plugin = ComponentAPI(
            client=self.client,
            method='POST',
            path='/api/c/compapi{bk_api_ver}/monitor_v3/upgrade_collect_plugin/',
            description=u'采集配置插件升级',
        )
        self.validate_custom_event_group_name = ComponentAPI(
            client=self.client,
            method='GET',
            path='/api/c/compapi{bk_api_ver}/monitor_v3/validate_custom_event_group_name/',
            description=u'校验自定义事件名称是否合法',
        )
        self.validate_custom_ts_group_name = ComponentAPI(
            client=self.client,
            method='GET',
            path='/api/c/compapi{bk_api_ver}/monitor_v3/validate_custom_ts_group_name/',
            description=u'校验自定义指标名称是否合法',
        )
